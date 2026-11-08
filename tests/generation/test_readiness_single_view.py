from storygen.authoring.blueprints import save_role_settings
from storygen.authoring.imports import SourceFile, import_sources
from storygen.domain import StoryCreate, SceneCreate
from storygen.generation.readiness import preview
from storygen.providers.models import RoleSettings, ProviderSettings
from storygen.run_models import RunRequest
from storygen.storage.context_view import ContextView
from storygen.storage.repository import Repository
from storygen.storage.snapshots import compare_snapshot


def seeded(tmp_path, scenes=3):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Один знімок'))
    created = [repo.create_scene(story.id, SceneCreate(title=f'Сцена {i + 1}', beats=f'План {i + 1}')) for i in range(scenes)]
    for role in ['planner', 'writer', 'editor', 'memory']:
        save_role_settings(repo, story.id, role, RoleSettings(provider=ProviderSettings(model=role)), repo.get_story(story.id).revision)
    return repo, story, created


def count_views(monkeypatch):
    calls = []
    original = ContextView.__init__

    def counting(self, *args, **kwargs):
        calls.append(1)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(ContextView, '__init__', counting)
    return calls


def test_preview_builds_one_context_view_for_stage_operations(tmp_path, monkeypatch):
    repo, story, scenes = seeded(tmp_path)
    calls = count_views(monkeypatch)
    result = preview(repo, RunRequest(story_id=story.id, scene_id=scenes[0].id, mode='stage', stage='brief'))
    assert result['ready'], result['reason']
    assert len(calls) == 1


def test_preview_errors_unchanged_without_scene_and_for_missing_material(tmp_path):
    repo, story, scenes = seeded(tmp_path)
    result = preview(repo, RunRequest.model_construct(story_id=story.id, scene_id=None, mode='stage', stage='brief', edit_workflow='single', edit_pass_limit=5, memory_approval=None))
    assert not result['ready'] and result['reason'] == 'Оберіть сцену'
    request = RunRequest(story_id=story.id, scene_id=scenes[2].id, mode='stage', stage='brief')
    scene = repo.get_scene(scenes[2].id)
    repo.set_scene_trashed(story.id, scene.id, scene.revision, restore=False)
    result = preview(repo, request)
    assert not result['ready'] and result['reason'] == 'Оберіть сцену'
    # A scene that vanishes after the request was built keeps the same message.
    result = preview(repo, RunRequest(story_id=story.id, scene_id='missing', mode='stage', stage='brief'))
    assert result['reason'] == 'Оберіть сцену'


def test_preview_missing_material_message_when_scene_disappears_mid_check(tmp_path, monkeypatch):
    repo, story, scenes = seeded(tmp_path)
    request = RunRequest(story_id=story.id, scene_id=scenes[0].id, mode='stage', stage='brief')
    original = ContextView.list_scenes

    def trash_after_list(self, story_id):
        result = original(self, story_id)
        self.scenes[scenes[0].id].trashed_at = '2026-01-01T00:00:00+00:00'
        return result

    monkeypatch.setattr(ContextView, 'list_scenes', trash_after_list)
    result = preview(repo, request)
    assert not result['ready'] and result['reason'] == 'Матеріал не знайдено; оновіть сторінку'


def test_source_preamble_parses_plan_once_per_view(tmp_path, monkeypatch):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Вступ'))
    import_sources(repo, story.id, [SourceFile(name='p.md', raw='Вступ\n## Сцена 1: Початок\nТекст'.encode(), kind='source_plan')])
    scene = repo.list_scenes(story.id)[0]
    from storygen.generation.context import build_context
    context = build_context(repo, scene.id, 'brief', RoleSettings(provider=ProviderSettings(model='synthetic')))
    view = repo.context_view(story.id)
    import storygen.plan_sections as plan_sections
    original = plan_sections.split_plan
    calls = []
    monkeypatch.setattr(plan_sections, 'split_plan', lambda text: calls.append(1) or original(text))
    compare_snapshot(view, context.dependency_snapshot)
    compare_snapshot(view, context.dependency_snapshot)
    assert len(calls) == 1


def test_source_preamble_cache_misses_on_different_sha256(tmp_path, monkeypatch):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Вступ'))
    import_sources(repo, story.id, [SourceFile(name='p.md', raw='Вступ\n## Сцена 1: Початок\nТекст'.encode(), kind='source_plan')])
    view = repo.context_view(story.id)
    ref = view.active_source(story.id, 'source_plan')
    import storygen.plan_sections as plan_sections
    from storygen.storage.snapshots import source_preamble
    original = plan_sections.split_plan
    calls = []
    monkeypatch.setattr(plan_sections, 'split_plan', lambda text: calls.append(1) or original(text))
    assert source_preamble(view, ref) == ref.id
    assert source_preamble(view, ref) == ref.id
    assert len(calls) == 1
    other = ref.model_copy(update={'sha256': 'f' * 64})
    assert source_preamble(view, other) == ref.id
    assert len(calls) == 2
    assert set(view.preamble_cache) == {(ref.id, ref.sha256), (ref.id, 'f' * 64)}


# ---- Task 2: all operations of one request share one view -------------------------------------------
import pytest

from storygen.generation.worker import RunCoordinator
from storygen.generation.dependencies import save_manual_prose

OPERATIONS = ('prepare', 'brief', 'draft', 'edit', 'memory', 'scene', 'remaining', 'rebuild_memory', 'edit_loop')


def _finish_prose(repo, scene_id, text='Завершена проза.'):
    save_manual_prose(repo, scene_id, text, repo.get_scene(scene_id).revision)


def _together_and_separate(repo, story_id, scene_id):
    coordinator = RunCoordinator(repo)
    together = coordinator.readiness(story_id, scene_id)['operations']
    separate = {op: coordinator.readiness(story_id, scene_id, operation=op)['operations'][op] for op in OPERATIONS}
    return together, separate


def _rebuild_request(story_id, scene_id):
    return RunRequest.model_construct(story_id=story_id, scene_id=scene_id, mode='rebuild_memory', stage=None,
                                      edit_workflow='single', edit_pass_limit=5, memory_approval=None)


def test_operations_constant_matches_coordinator(tmp_path):
    repo, story, scenes = seeded(tmp_path)
    assert tuple(RunCoordinator(repo).readiness(story.id, scenes[0].id)['operations']) == OPERATIONS


def test_all_operations_build_one_view(tmp_path, monkeypatch):
    repo, story, scenes = seeded(tmp_path)
    calls = count_views(monkeypatch)
    RunCoordinator(repo).readiness(story.id, scenes[0].id)
    assert len(calls) == 1


def test_all_operations_equal_separate_requests_with_finished_and_unfinished_prose(tmp_path):
    repo, story, scenes = seeded(tmp_path, scenes=4)
    _finish_prose(repo, scenes[0].id)
    _finish_prose(repo, scenes[1].id)
    together, separate = _together_and_separate(repo, story.id, scenes[0].id)
    assert together == separate
    # The next scene has no finished prose: the reason names its number, in both forms.
    assert together['rebuild_memory']['reason'] == 'Спершу виберіть завершену прозу сцени 3'
    # With every scene finished, rebuild_memory passes the prose check.
    for scene in scenes[2:]:
        _finish_prose(repo, scene.id)
    together, separate = _together_and_separate(repo, story.id, scenes[0].id)
    assert together == separate
    assert not (together['rebuild_memory']['reason'] or '').startswith('Спершу виберіть завершену прозу')


def test_all_operations_equal_separate_requests_without_scene(tmp_path):
    repo, story, scenes = seeded(tmp_path)
    together, separate = _together_and_separate(repo, story.id, None)
    assert together == separate
    assert together['brief']['reason'] == 'Оберіть сцену'
    assert together['rebuild_memory']['reason'] == 'Оберіть сцену'


def test_all_operations_equal_separate_requests_for_trashed_scene(tmp_path):
    repo, story, scenes = seeded(tmp_path)
    scene = repo.get_scene(scenes[1].id)
    repo.set_scene_trashed(story.id, scene.id, scene.revision, restore=False)
    together, separate = _together_and_separate(repo, story.id, scene.id)
    assert together == separate
    assert together['brief']['reason'] == 'Оберіть сцену'


def test_all_operations_equal_separate_requests_with_missing_plan(tmp_path):
    repo, story, scenes = seeded(tmp_path)
    repo.create_scene(story.id, SceneCreate(title='Без плану'))
    together, separate = _together_and_separate(repo, story.id, scenes[0].id)
    assert together == separate
    assert together['remaining']['reason'] == 'Спершу додайте план сцени 4'
    assert together['brief']['ready'] is True


def test_memory_approval_does_not_affect_later_operations(tmp_path):
    from tests.memory.test_author_reuse import workspace
    repo, first, second, old, new, memory, role = workspace(tmp_path, True)
    for name in ['planner', 'writer', 'editor']:
        save_role_settings(repo, first.story_id, name, RoleSettings(provider=ProviderSettings(model=name)), repo.get_story(first.story_id).revision)
    save_role_settings(repo, first.story_id, 'memory', role, repo.get_story(first.story_id).revision)
    together, separate = _together_and_separate(repo, first.story_id, second.id)
    assert together == separate
    assert together['memory'].get('can_confirm') is True


def test_rebuild_memory_does_not_snapshot_per_scene(tmp_path, monkeypatch):
    repo, story, scenes = seeded(tmp_path, scenes=6)
    for scene in scenes:
        _finish_prose(repo, scene.id)
    spy = []
    original = Repository.get_version

    def counting(self, version_id):
        spy.append(version_id)
        return original(self, version_id)

    monkeypatch.setattr(Repository, 'get_version', counting)
    result = preview(repo, _rebuild_request(story.id, scenes[0].id))
    assert result['calls'] == 6
    assert spy == []


def test_peek_version_matches_get_version_for_rebuild_memory_checks(tmp_path):
    repo, story, scenes = seeded(tmp_path, scenes=2)
    _finish_prose(repo, scenes[0].id)
    repo.save_version(story.id, scenes[1].id, 'draft', 'Чернетка.', [])
    view = repo.context_view(story.id)
    checked = 0
    for scene in repo.list_scenes(story.id):
        for head in scene.heads.values():
            ref, copy = view.peek_version(head), repo.get_version(head)
            assert (ref.complete, ref.kind) == (copy.complete, copy.kind)
            checked += 1
    assert checked >= 1


def test_view_read_text_matches_repo_read_text(tmp_path):
    repo, story, scenes = seeded(tmp_path)
    plan = repo.save_version(story.id, scenes[0].id, 'scene_plan', 'Інший план.', [])
    view = repo.context_view(story.id)
    assert view.read_text(plan.id) == repo.read_text(plan.id)
    with pytest.raises(KeyError):
        view.read_text('missing')
    with pytest.raises(KeyError):
        repo.read_text('missing')


# ---- edit_loop readiness on a shared view equals the repository (view-less) path ----------------------
def _edit_loop_request(story_id, scene_id, version_id):
    return RunRequest.model_construct(story_id=story_id, scene_id=scene_id, mode='edit_loop', stage=None, edit_workflow='single',
                                      edit_pass_limit=5, memory_approval=None, editor_source_head='draft', editor_source_version_id=version_id)


def _assert_edit_loop_matches_repository_path(repo, story_id, request):
    from storygen.generation import editor_loop
    old = editor_loop.readiness(repo, request)
    assert preview(repo, request, repo.context_view(story_id)) == old
    assert RunCoordinator(repo).readiness(story_id, request.scene_id, editor_source_head='draft',
                                          editor_source_version_id=request.editor_source_version_id, operation='edit_loop')['operations']['edit_loop'] == old
    return old


def test_edit_loop_legacy_draft_with_hidden_memory_forwarding_matches_repository_path(tmp_path):
    from tests.memory.test_forwarding import seeded as memory_seeded, apply, memory_view
    repo, story, scenes = memory_seeded(tmp_path)
    save_role_settings(repo, story.id, 'editor', RoleSettings(provider=ProviderSettings(model='editor')), repo.get_story(story.id).revision)
    draft = repo.save_version(story.id, scenes[2].id, 'draft', 'Легасі чернетка.', [])
    repo.set_head(scenes[2].id, 'draft', draft.id, repo.get_scene(scenes[2].id).revision)
    claim = memory_view(repo, scenes[1].id)['rows'][0]['claim_id']
    apply(repo, scenes[1], {claim: False})
    old = _assert_edit_loop_matches_repository_path(repo, story.id, _edit_loop_request(story.id, scenes[2].id, draft.id))
    assert old['ready'] is False and old['reason']


def test_edit_loop_legacy_draft_with_corrupted_blob_matches_repository_path(tmp_path):
    repo, story, scenes = seeded(tmp_path)
    save_role_settings(repo, story.id, 'editor', RoleSettings(provider=ProviderSettings(model='editor')), repo.get_story(story.id).revision)
    draft = repo.save_version(story.id, scenes[0].id, 'draft', 'Легасі чернетка.', [])
    repo.set_head(scenes[0].id, 'draft', draft.id, repo.get_scene(scenes[0].id).revision)
    (repo.root / draft.relative_path).write_bytes(b'broken')
    old = _assert_edit_loop_matches_repository_path(repo, story.id, _edit_loop_request(story.id, scenes[0].id, draft.id))
    assert old['ready'] is False and old['reason']


def test_edit_loop_ready_legacy_draft_matches_repository_path(tmp_path):
    repo, story, scenes = seeded(tmp_path)
    save_role_settings(repo, story.id, 'editor', RoleSettings(provider=ProviderSettings(model='editor')), repo.get_story(story.id).revision)
    draft = repo.save_version(story.id, scenes[0].id, 'draft', 'Легасі чернетка.', [])
    repo.set_head(scenes[0].id, 'draft', draft.id, repo.get_scene(scenes[0].id).revision)
    old = _assert_edit_loop_matches_repository_path(repo, story.id, _edit_loop_request(story.id, scenes[0].id, draft.id))
    assert old['editor_source_version_id'] == draft.id
