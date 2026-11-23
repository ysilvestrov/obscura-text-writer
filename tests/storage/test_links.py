import json
import threading
import pytest
from storygen.domain import StoryCreate, SceneCreate, ExternalOrigin, new_id
from storygen.run_models import Run, RunRequest
from storygen.storage.repository import Repository
from storygen.storage.links import scene_links, scene_validity, link_state, memory_digest, model_made
from storygen.storage.link_records import write_verdict
from storygen.providers.models import RoleSettings, ProviderSettings
from storygen.generation.pipeline import generate_scene
from storygen.generation.context import build_context
from storygen.generation.dependencies import save_manual_prose, save_manual_draft
from storygen.memory.service import save_scene_memory
from tests.generation.test_scene_pipeline import FakeGateway
from tests.storage.test_link_records import verdict

pytestmark = pytest.mark.req('VALID-LINKS')


def roles(**changes):
    return {role: RoleSettings(provider=ProviderSettings(model=role), memory_mode='snapshot', **changes)
            for role in ['planner', 'writer', 'editor', 'memory']}


def run_for(repo, story, scene, request_id):
    run = Run(id=new_id(), story_id=story.id, request_id=request_id,
              request=RunRequest(story_id=story.id, scene_id=scene.id, mode='remaining'), state='completed', tasks=[])
    repo.enqueue_run(run)
    return run.id


def book(tmp_path, count=1, **role_changes):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Твір'))
    scenes = [repo.create_scene(story.id, SceneCreate(title=f'Сцена {i}', beats='Студія')) for i in range(count)]
    for scene in scenes:
        attempts = generate_scene(repo, scene.id, roles(**role_changes), lambda _: FakeGateway(repo, scene.id),
                                  threading.Event(), lambda *_: None, run_id=run_for(repo, story, scene, 'gen-' + scene.id))
        assert all(a.state == 'completed' for a in attempts), [(a.stage, a.state, a.error) for a in attempts]
    return repo, story, [repo.get_scene(s.id) for s in scenes]


def statuses(repo, story, scene):
    view = repo.context_view(story.id)
    return {link: (state.status, state.source, state.reason) for link, state in scene_links(view, scene.id).items()}


ALL_VALID = {link: ('valid', 'construction', None) for link in ('brief', 'prose', 'memory')}


def test_generated_scene_is_valid_by_construction(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    assert statuses(repo, story, scene) == ALL_VALID
    assert scene_validity(repo.context_view(story.id), scene.id) == 'valid'


def test_generated_second_scene_is_valid_by_construction(tmp_path):
    repo, story, scenes = book(tmp_path, 2)
    assert statuses(repo, story, scenes[1]) == ALL_VALID


def test_patches_edit_chain_is_construction(tmp_path):
    # A copyedit selection: an edited version from a patches context over the writer's draft, saved by the run.
    repo, story, (scene,) = book(tmp_path)
    current = repo.get_scene(scene.id)
    context = build_context(repo, scene.id, 'edit', RoleSettings(provider=ProviderSettings(model='editor'), edit_mode='patches'))
    assert context.dependency_snapshot.scope == 'patches'
    edited = repo.save_version(story.id, scene.id, 'edited', 'Олена тихо увійшла.', context.input_refs, run_for(repo, story, scene, 'patches'),
                               dependency_snapshot=context.dependency_snapshot)
    repo.set_head(scene.id, 'prose', edited.id, current.revision)
    assert statuses(repo, story, scene)['prose'] == ('valid', 'construction', None)


def test_manual_draft_in_the_chain_breaks_construction(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    save_manual_draft(repo, scene.id, 'Ручна чернетка.', repo.get_scene(scene.id).revision)
    current = repo.get_scene(scene.id)
    context = build_context(repo, scene.id, 'edit', RoleSettings(provider=ProviderSettings(model='editor'), edit_mode='patches'))
    edited = repo.save_version(story.id, scene.id, 'edited', 'Ручна, але відредагована.', context.input_refs, run_for(repo, story, scene, 'patches'),
                               dependency_snapshot=context.dependency_snapshot)
    repo.set_head(scene.id, 'prose', edited.id, current.revision)
    assert statuses(repo, story, scene)['prose'] == ('unchecked', None, None)


def save_manual_brief(repo, scene):
    text = json.dumps({'objective': 'Інше', 'beats': ['Студія'], 'constraints': [], 'proposed_changes': []}, ensure_ascii=False)
    ref = repo.save_version(scene.story_id, scene.id, 'brief', text, [])
    return repo.set_head(scene.id, 'brief', ref.id, repo.get_scene(scene.id).revision)


def test_manual_brief_unchecks_brief_and_prose_links(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    save_manual_brief(repo, scene)
    result = statuses(repo, story, scene)
    assert result['brief'] == ('unchecked', None, None)
    assert result['prose'] == ('unchecked', None, None)
    assert result['memory'] == ('valid', 'construction', None)
    assert scene_validity(repo.context_view(story.id), scene.id) == 'unchecked'


def test_manual_prose_unchecks_prose_and_memory_links(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    save_manual_prose(repo, scene.id, 'Олена увійшла до старої бібліотеки.', repo.get_scene(scene.id).revision)
    result = statuses(repo, story, scene)
    assert result['brief'] == ('valid', 'construction', None)
    assert result['prose'] == ('unchecked', None, None)
    assert result['memory'] == ('unchecked', None, None)


def memory_text(repo, scene):
    return repo.read_text(repo.get_scene(scene.id).heads['memory'])


def test_manual_memory_keeps_scene_and_unchecks_next(tmp_path):
    repo, story, scenes = book(tmp_path, 2)
    journal = json.loads(memory_text(repo, scenes[0]))
    journal['events'][-1]['text'] = 'Олена в бібліотеці вночі'
    save_scene_memory(repo, scenes[0].id, json.dumps(journal, ensure_ascii=False), repo.get_scene(scenes[0].id).revision)
    assert statuses(repo, story, scenes[0])['memory'] == ('valid', 'construction', None)
    after = statuses(repo, story, scenes[1])
    assert after['brief'][0] == 'unchecked' and after['prose'][0] == 'unchecked'
    assert after['memory'] == ('valid', 'construction', None)


def test_same_own_events_keep_next_scene_valid(tmp_path):
    repo, story, scenes = book(tmp_path, 2)
    before = memory_digest(repo.context_view(story.id), repo.get_scene(scenes[0].id).heads['memory'])
    save_scene_memory(repo, scenes[0].id, memory_text(repo, scenes[0]), repo.get_scene(scenes[0].id).revision)
    view = repo.context_view(story.id)
    assert memory_digest(view, repo.get_scene(scenes[0].id).heads['memory']) == before
    assert statuses(repo, story, scenes[1]) == ALL_VALID


def test_draft_change_keeps_validity(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    save_manual_draft(repo, scene.id, 'Ручна чернетка.', repo.get_scene(scene.id).revision)
    assert statuses(repo, story, scene) == ALL_VALID


def test_chat_stage_result_is_model_made_and_save_draft_is_not(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    view = repo.context_view(story.id)
    heads = view.scenes[scene.id].heads
    brief = view.versions[heads['brief']]
    assert model_made(brief.model_copy(update={'source_run_id': None, 'external_origin': ExternalOrigin(client='Claude')}))
    draft = save_manual_draft(repo, scene.id, 'Чернетка з чату.', repo.get_scene(scene.id).revision)
    assert draft.dependency_snapshot.scope == 'author_text'
    assert not model_made(draft.model_copy(update={'external_origin': ExternalOrigin(client='Claude')}))


def test_missing_previous_memory_is_unavailable(tmp_path):
    repo, story, scenes = book(tmp_path, 2)
    first = repo.get_scene(scenes[0].id)
    with repo.db.connection() as db:
        payload = first.model_copy(update={'heads': {k: v for k, v in first.heads.items() if k != 'memory'}})
        db.execute('UPDATE scenes SET payload=? WHERE id=?', (payload.model_dump_json(), first.id))
    result = statuses(repo, story, scenes[1])
    assert result['brief'] == ('unavailable', None, 'no_previous_memory')
    assert result['prose'] == ('unavailable', None, 'no_previous_memory')
    assert statuses(repo, story, scenes[0])['memory'] == ('unavailable', None, 'no_memory')


def test_incomplete_scene_links_are_missing(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Твір'))
    scene = repo.create_scene(story.id, SceneCreate(title='Порожня', beats='x'))
    view = repo.context_view(story.id)
    assert {s.status for s in scene_links(view, scene.id).values()} == {'missing'}
    assert scene_validity(view, scene.id) == 'incomplete'


def test_legacy_memory_without_snapshot_is_unchecked(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    current = repo.get_scene(scene.id)
    legacy = repo.save_version(story.id, scene.id, 'memory', memory_text(repo, scene), [current.heads['prose']])
    repo.set_head(scene.id, 'memory', legacy.id, current.revision)
    assert statuses(repo, story, scene)['memory'] == ('unchecked', None, None)


def test_trashed_scene_links_are_missing(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    repo.set_scene_trashed(story.id, scene.id, repo.get_scene(scene.id).revision, False)
    view = repo.context_view(story.id)
    assert {s.status for s in scene_links(view, scene.id).values()} == {'missing'}


def test_author_verdict_with_current_fingerprint_validates(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    save_manual_brief(repo, scene)
    state = link_state(repo.context_view(story.id), scene.id, 'brief')
    for fingerprint in ('0' * 64, state.fingerprint):
        with repo.db.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            write_verdict(db, verdict(story.id, scene.id, 'brief', fingerprint))
    assert statuses(repo, story, scene)['brief'] == ('valid', 'author', None)
    save_manual_brief(repo, scene)  # a new brief: the old verdict no longer applies
    assert statuses(repo, story, scene)['brief'] == ('unchecked', None, None)
