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
