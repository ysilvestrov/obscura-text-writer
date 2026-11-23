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


@pytest.mark.req('VALID-LINKS')
def test_generated_scene_is_valid_by_construction(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    assert statuses(repo, story, scene) == ALL_VALID
    assert scene_validity(repo.context_view(story.id), scene.id) == 'valid'


@pytest.mark.req('VALID-LINKS')
def test_generated_second_scene_is_valid_by_construction(tmp_path):
    repo, story, scenes = book(tmp_path, 2)
    assert statuses(repo, story, scenes[1]) == ALL_VALID


@pytest.mark.req('VALID-LINKS')
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


@pytest.mark.req('VALID-LINKS')
def test_manual_draft_in_the_chain_breaks_construction(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    save_manual_draft(repo, scene.id, 'Ручна чернетка.', repo.get_scene(scene.id).revision)
    current = repo.get_scene(scene.id)
    context = build_context(repo, scene.id, 'edit', RoleSettings(provider=ProviderSettings(model='editor'), edit_mode='patches'))
    edited = repo.save_version(story.id, scene.id, 'edited', 'Ручна, але відредагована.', context.input_refs, run_for(repo, story, scene, 'patches'),
                               dependency_snapshot=context.dependency_snapshot)
    repo.set_head(scene.id, 'prose', edited.id, current.revision)
    assert statuses(repo, story, scene)['prose'] == ('unchecked', None, None)


@pytest.mark.req('VALID-LINKS')
@pytest.mark.parametrize('mode', ['patches', 'prose'])
def test_edit_of_accepted_author_prose_is_not_construction(tmp_path, mode):
    # Final review 2a: an edit whose source is the author's prose still records head/draft = the model draft; the chain
    # must follow the version actually edited, so a model edit cannot turn author prose into a valid-by-construction link.
    from storygen.generation import editor_loop
    from storygen.storage.acceptance import preview_acceptance, accept_version
    repo, story, (scene,) = book(tmp_path)
    save_manual_prose(repo, scene.id, 'Авторський текст повністю іншої сцени.', repo.get_scene(scene.id).revision)
    current = repo.get_scene(scene.id)
    preview = preview_acceptance(repo, scene.id, current.heads['prose'])
    accept_version(repo, scene.id, current.heads['prose'], preview.expected_revision, preview.preview_fingerprint)
    current = repo.get_scene(scene.id)
    context = editor_loop.context(repo, scene.id, RoleSettings(provider=ProviderSettings(model='editor'), edit_mode=mode),
                                  current.heads['prose'])
    edited = repo.save_version(story.id, scene.id, 'edited', 'Авторський текст, вичитаний.', context.input_refs,
                               run_for(repo, story, scene, 'edit-' + mode), dependency_snapshot=context.dependency_snapshot)
    repo.set_head(scene.id, 'prose', edited.id, current.revision)
    assert statuses(repo, story, scene)['prose'] == ('unchecked', None, None)


def save_manual_brief(repo, scene):
    text = json.dumps({'objective': 'Інше', 'beats': ['Студія'], 'constraints': [], 'proposed_changes': []}, ensure_ascii=False)
    ref = repo.save_version(scene.story_id, scene.id, 'brief', text, [])
    return repo.set_head(scene.id, 'brief', ref.id, repo.get_scene(scene.id).revision)


@pytest.mark.req('VALID-LINKS')
def test_manual_brief_unchecks_brief_and_prose_links(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    save_manual_brief(repo, scene)
    result = statuses(repo, story, scene)
    assert result['brief'] == ('unchecked', None, None)
    assert result['prose'] == ('unchecked', None, None)
    assert result['memory'] == ('valid', 'construction', None)
    assert scene_validity(repo.context_view(story.id), scene.id) == 'unchecked'


@pytest.mark.req('VALID-LINKS')
def test_manual_prose_unchecks_prose_and_memory_links(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    save_manual_prose(repo, scene.id, 'Олена увійшла до старої бібліотеки.', repo.get_scene(scene.id).revision)
    result = statuses(repo, story, scene)
    assert result['brief'] == ('valid', 'construction', None)
    assert result['prose'] == ('unchecked', None, None)
    assert result['memory'] == ('unchecked', None, None)


def memory_text(repo, scene):
    return repo.read_text(repo.get_scene(scene.id).heads['memory'])


@pytest.mark.req('VALID-LINKS')
def test_manual_memory_keeps_scene_and_unchecks_next(tmp_path):
    repo, story, scenes = book(tmp_path, 2)
    journal = json.loads(memory_text(repo, scenes[0]))
    journal['events'][-1]['text'] = 'Олена в бібліотеці вночі'
    save_scene_memory(repo, scenes[0].id, json.dumps(journal, ensure_ascii=False), repo.get_scene(scenes[0].id).revision)
    assert statuses(repo, story, scenes[0])['memory'] == ('valid', 'construction', None)
    after = statuses(repo, story, scenes[1])
    assert after['brief'][0] == 'unchecked' and after['prose'][0] == 'unchecked'
    assert after['memory'] == ('valid', 'construction', None)


@pytest.mark.req('VALID-LINKS')
def test_same_own_events_keep_next_scene_valid(tmp_path):
    repo, story, scenes = book(tmp_path, 2)
    before = memory_digest(repo.context_view(story.id), repo.get_scene(scenes[0].id).heads['memory'])
    save_scene_memory(repo, scenes[0].id, memory_text(repo, scenes[0]), repo.get_scene(scenes[0].id).revision)
    view = repo.context_view(story.id)
    assert memory_digest(view, repo.get_scene(scenes[0].id).heads['memory']) == before
    assert statuses(repo, story, scenes[1]) == ALL_VALID


@pytest.mark.req('VALID-LINKS')
def test_draft_change_keeps_validity(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    save_manual_draft(repo, scene.id, 'Ручна чернетка.', repo.get_scene(scene.id).revision)
    assert statuses(repo, story, scene) == ALL_VALID


@pytest.mark.req('VALID-LINKS')
def test_chat_texts_are_model_made_and_author_drafts_are_not(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    view = repo.context_view(story.id)
    heads = view.scenes[scene.id].heads
    brief = view.versions[heads['brief']]
    assert model_made(brief.model_copy(update={'source_run_id': None, 'external_origin': ExternalOrigin(client='Claude')}))
    draft = save_manual_draft(repo, scene.id, 'Авторська чернетка.', repo.get_scene(scene.id).revision)
    assert draft.dependency_snapshot.scope == 'author_text' and not model_made(draft)
    assert model_made(draft.model_copy(update={'external_origin': ExternalOrigin(client='Claude')}))


@pytest.mark.req('VALID-LINKS')
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


@pytest.mark.req('VALID-LINKS')
def test_incomplete_scene_links_are_missing(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Твір'))
    scene = repo.create_scene(story.id, SceneCreate(title='Порожня', beats='x'))
    view = repo.context_view(story.id)
    assert {s.status for s in scene_links(view, scene.id).values()} == {'missing'}
    assert scene_validity(view, scene.id) == 'incomplete'


@pytest.mark.req('VALID-LINKS')
def test_legacy_memory_without_snapshot_is_unchecked(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    current = repo.get_scene(scene.id)
    legacy = repo.save_version(story.id, scene.id, 'memory', memory_text(repo, scene), [current.heads['prose']])
    repo.set_head(scene.id, 'memory', legacy.id, current.revision)
    assert statuses(repo, story, scene)['memory'] == ('unchecked', None, None)


@pytest.mark.req('VALID-LINKS')
def test_trashed_scene_links_are_missing(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    repo.set_scene_trashed(story.id, scene.id, repo.get_scene(scene.id).revision, False)
    view = repo.context_view(story.id)
    assert {s.status for s in scene_links(view, scene.id).values()} == {'missing'}


@pytest.mark.req('VALID-LINKS')
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


@pytest.mark.req('VALID-LINKS')
def test_chat_mode_scene_holds_the_prose_link_by_construction(tmp_path):
    # A chat writes the draft through MCP save_draft (bound to the writing context) and the edit as a chat stage result.
    from storygen.application.writing_context import context_fingerprint
    repo, story, (scene,) = book(tmp_path)
    current = repo.get_scene(scene.id)
    origin = ExternalOrigin(client='Claude')
    save_manual_draft(repo, scene.id, 'Олена прийшла з чату.', current.revision, external_origin=origin,
                      expected_context_fingerprint=context_fingerprint(repo, scene.id),
                      expected_draft_version_id=current.heads['draft'])
    context = build_context(repo, scene.id, 'edit', RoleSettings(provider=ProviderSettings(model='chat')))
    edited = repo.save_version(story.id, scene.id, 'edited', 'Олена увійшла з чату.', context.input_refs,
                               dependency_snapshot=context.dependency_snapshot, external_origin=origin)
    repo.set_head(scene.id, 'prose', edited.id, repo.get_scene(scene.id).revision)
    assert statuses(repo, story, scene)['prose'] == ('valid', 'construction', None)
    save_manual_brief(repo, scene)  # the chat draft was written from the old brief
    assert statuses(repo, story, scene)['prose'] == ('unchecked', None, None)


def numbered_book(tmp_path):
    """Own numbering from 2 (as an imported plan may have): scene «А» with a plan head, «Б» and «Д» with numbered beats
    only, all generated, and a trailing empty «Кінець». Trashing the trailing scene renumbers every scene before it
    without changing their previous memories (an insertion before a scene would change its P0)."""
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Твір'))
    first = repo.create_scene(story.id, SceneCreate(title='А', beats='Сцена 2: А'))
    repo.update_scene_plan(first.id, 'Сцена 2: А\nСтудія.', repo.get_scene(first.id).revision)
    middle = repo.create_scene(story.id, SceneCreate(title='Б', beats='Сцена 3: Б\nСтудія.'))
    third = repo.create_scene(story.id, SceneCreate(title='Д', beats='Сцена 4: Д\nСтудія.'))
    for scene in (first, middle, third):
        attempts = generate_scene(repo, scene.id, roles(), lambda _, s=scene: FakeGateway(repo, s.id), threading.Event(),
                                  lambda *_: None, run_id=run_for(repo, story, scene, 'gen-' + scene.id))
        assert all(a.state == 'completed' for a in attempts), [(a.stage, a.state, a.error) for a in attempts]
    tail = repo.create_scene(story.id, SceneCreate(title='Кінець', beats='Сцена 5: Кінець'))
    return repo, story, [repo.get_scene(s.id) for s in (first, middle, third, tail)]


@pytest.mark.req('VALID-LINKS')
def test_renumber_keeps_the_brief_link(tmp_path):
    from storygen.authoring.trash import trash_scene
    from storygen.scene_description import explicit_scene_number
    repo, story, (first, middle, third, tail) = numbered_book(tmp_path)
    save_manual_brief(repo, third)
    state = link_state(repo.context_view(story.id), third.id, 'brief')
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        write_verdict(db, verdict(story.id, third.id, 'brief', state.fingerprint, inputs=state.inputs))
    assert statuses(repo, story, third)['brief'] == ('valid', 'author', None)
    old_plan = repo.get_scene(first.id).heads['plan']
    trash_scene(repo, story.id, tail.id, repo.get_scene(tail.id).revision)
    renumbered = repo.get_scene(first.id)
    assert renumbered.heads['plan'] != old_plan
    assert explicit_scene_number(repo.read_text(renumbered.heads['plan'])) == 1
    assert explicit_scene_number(repo.get_scene(middle.id).beats) == 2
    assert statuses(repo, story, first)['brief'] == ('valid', 'construction', None)
    assert statuses(repo, story, middle)['brief'] == ('valid', 'construction', None)
    assert statuses(repo, story, third)['brief'] == ('valid', 'author', None)


@pytest.mark.req('VALID-LINKS')
def test_real_plan_edit_still_unchecks_the_brief(tmp_path):
    repo, story, (first, middle, _, _) = numbered_book(tmp_path)
    repo.update_scene_plan(first.id, 'Сцена 2: А\nБібліотека.', repo.get_scene(first.id).revision)
    assert statuses(repo, story, first)['brief'] == ('unchecked', None, None)
    current = repo.get_scene(middle.id)  # beats without a plan head (legacy scene): changed in place
    with repo.db.connection() as db:
        payload = current.model_copy(update={'beats': 'Сцена 3: Б\nБібліотека.'})
        db.execute('UPDATE scenes SET payload=? WHERE id=?', (payload.model_dump_json(), middle.id))
    assert statuses(repo, story, middle)['brief'] == ('unchecked', None, None)


@pytest.mark.req('VALID-LINKS')
def test_insertion_renumbers_scenes_without_unchecking_them(tmp_path):
    from storygen.scene_description import explicit_scene_number
    repo, story, (first, middle, third, _) = numbered_book(tmp_path)
    repo.create_scene(story.id, SceneCreate(title='Вставка', position=1), plan_template=True)
    # The insertion renumbers the list from 1: «А» (first, same P0) gets a new plan version with number 1.
    assert explicit_scene_number(repo.read_text(repo.get_scene(first.id).heads['plan'])) == 1
    assert statuses(repo, story, first)['brief'] == ('valid', 'construction', None)
    # «Б» has a new predecessor without memory; «Д» keeps «Б» before it.
    assert statuses(repo, story, middle)['brief'] == ('unavailable', None, 'no_previous_memory')
    assert statuses(repo, story, third)['brief'] == ('valid', 'construction', None)
