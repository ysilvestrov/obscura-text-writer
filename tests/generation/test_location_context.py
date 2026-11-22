"""MEMORY-LOCATIONS-S02, S03, S06: the «ЛОКАЦІЇ СЦЕНИ» section of the writing context and the location selectors."""
import json

import pytest

from storygen.domain import SceneCreate, StoryCreate
from storygen.generation.context import build_context
from storygen.generation.models import StyleProfile
from storygen.locations import location_id, normalize
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage import locations as store
from storygen.storage.repository import Repository
from storygen.storage.snapshots import build_dependency_snapshot, resolve_freshness


BRIEF = '{"objective":"Юлія чекає","beats":["Юлія чекає"],"constraints":[],"proposed_changes":[],"introduced":[]}'
HEAD = 'ЛОКАЦІЇ СЦЕНИ'


def role(edit_mode='prose', memory_mode='evidence_delta'):
    return RoleSettings(provider=ProviderSettings(model='fake'), context_tokens=262144, edit_mode=edit_mode, memory_mode=memory_mode)


def setup(tmp_path, beats='Хто бере участь: Юлія\nЛокація: Дім / кухня\nЮлія чекає.', language='uk', other='Локація: Ліс'):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Пристань', language=language))
    cards = [{'schema_version': 2, 'id': 'j', 'name': 'Юлія', 'entries': []}]
    ref = repo.save_version(story.id, None, 'character_cards', json.dumps(cards, ensure_ascii=False), [])
    repo.publish_story_material(story.id, 'characters_version_id', ref.id, repo.get_story(story.id).revision)
    style = repo.save_version(story.id, None, 'style', StyleProfile().model_dump_json(), [])
    repo.publish_story_material(story.id, 'style_version_id', style.id, repo.get_story(story.id).revision)
    scene = repo.create_scene(story.id, SceneCreate(title='Ранок', beats=beats, character_ids=['j']))
    second = repo.create_scene(story.id, SceneCreate(title='Ліс', beats='Хто бере участь: Юлія\n' + other, character_ids=['j']))
    return repo, repo.get_story(story.id), scene, second


def lid(story, *parts):
    return location_id(story.id, normalize(parts))


def write(repo, action):
    with repo.db.connection() as db:
        action(db)
    repo.db.bump_generation()


def section(text):
    return text.split(HEAD + '\n')[1].split('\n\n')[0] if HEAD + '\n' in text else None


def with_brief(repo, story, scene):
    brief = repo.save_version(story.id, scene.id, 'brief', BRIEF, [])
    repo.set_head(scene.id, 'brief', brief.id, repo.get_scene(scene.id).revision)
    return repo.get_scene(scene.id)


@pytest.mark.req('MEMORY-LOCATIONS')
def test_section_lists_scene_locations_with_ancestors_and_descriptions(tmp_path):
    repo, story, scene, _ = setup(tmp_path)
    assert section(build_context(repo, scene.id, 'brief', role()).user_text) == '— Дім\n— Дім / кухня'
    write(repo, lambda db: store.set_description(db, story.id, lid(story, 'Дім', 'кухня'), 'Тісна, вікно у двір.'))
    brief = build_context(repo, scene.id, 'brief', role()).user_text
    assert section(brief) == '— Дім\n— Дім / кухня: Тісна, вікно у двір.'
    scene = with_brief(repo, story, scene)
    assert section(build_context(repo, scene.id, 'draft', role()).user_text) == section(brief)


@pytest.mark.req('MEMORY-LOCATIONS')
def test_memory_and_patches_get_no_section_and_english_label(tmp_path):
    repo, story, scene, _ = setup(tmp_path)
    scene = with_brief(repo, story, scene)
    draft = repo.save_version(story.id, scene.id, 'draft', 'Юлія чекала.', [])
    repo.set_head(scene.id, 'draft', draft.id, repo.get_scene(scene.id).revision)
    assert HEAD not in build_context(repo, scene.id, 'edit', role('patches')).user_text
    assert section(build_context(repo, scene.id, 'edit', role('prose')).user_text) == '— Дім\n— Дім / кухня'
    repo, story, scene, _ = setup(tmp_path / 'en', language='en', beats='Characters: Юлія\nLocation: House')
    assert 'SCENE LOCATIONS\n— House' in build_context(repo, scene.id, 'brief', role()).user_text


@pytest.mark.req('MEMORY-LOCATIONS')
def test_scene_without_locations_has_no_section_and_no_new_selectors(tmp_path):
    repo, story, scene, _ = setup(tmp_path, beats='Хто бере участь: Юлія\nЮлія чекає.')
    bundle = build_context(repo, scene.id, 'brief', role())
    assert HEAD not in bundle.user_text
    fields = {s.field for s in bundle.dependency_snapshot.selectors}
    assert not fields & {'location_neighbourhood', 'location_context', 'location_ids'}


def saved(repo, story, scene, kind, bundle):
    return repo.save_version(story.id, scene.id, kind, 'Текст.', bundle.input_refs, dependency_snapshot=bundle.dependency_snapshot)


def stale_fields(repo, story, ref):
    return {r.selector.field for r in resolve_freshness(repo.context_view(story.id), ref.id).reasons if r.selector}


def memory_version(repo, story, scene):
    snap = build_dependency_snapshot(repo.context_view(story.id), scene.id, 'memory', role(), [])
    return repo.save_version(story.id, scene.id, 'memory', '{}', [], dependency_snapshot=snap)


@pytest.mark.req('MEMORY-LOCATIONS')
def test_description_change_stales_brief_of_scenes_that_show_it_only(tmp_path):
    repo, story, scene, second = setup(tmp_path)
    brief = saved(repo, story, scene, 'brief', build_context(repo, scene.id, 'brief', role()))
    write(repo, lambda db: store.set_description(db, story.id, lid(story, 'Ліс'), 'Темний ліс.'))
    assert stale_fields(repo, story, brief) == set()
    write(repo, lambda db: store.set_description(db, story.id, lid(story, 'Дім'), 'Старий дім.'))
    assert 'location_context' in stale_fields(repo, story, brief)


@pytest.mark.req('MEMORY-LOCATIONS')
def test_location_line_change_stales_memory(tmp_path):
    repo, story, scene, _ = setup(tmp_path)
    ref = memory_version(repo, story, scene)
    assert stale_fields(repo, story, ref) == set()
    repo.update_scene_plan(scene.id, 'Хто бере участь: Юлія\nЛокація: Ліс\nЮлія чекає.', repo.get_scene(scene.id).revision)
    assert 'location_ids' in stale_fields(repo, story, ref)


@pytest.mark.req('MEMORY-LOCATIONS')
def test_merge_in_the_neighbourhood_stales_and_outside_does_not(tmp_path):
    repo, story, scene, second = setup(tmp_path, other='Локація: Ліс, Ліс біля озера, Хата')
    mem = memory_version(repo, story, scene)
    brief = saved(repo, story, scene, 'brief', build_context(repo, scene.id, 'brief', role()))
    write(repo, lambda db: store.merge_location(db, story.id, lid(story, 'Ліс біля озера'), lid(story, 'Ліс')))
    assert stale_fields(repo, story, mem) == set() and stale_fields(repo, story, brief) == set()
    write(repo, lambda db: store.merge_location(db, story.id, lid(story, 'Хата'), lid(story, 'Дім', 'кухня')))
    assert 'location_neighbourhood' in stale_fields(repo, story, mem)
    assert 'location_neighbourhood' in stale_fields(repo, story, brief)


def memory_scene(tmp_path, beats):
    repo = Repository(tmp_path)
    item = repo.create_story(StoryCreate(title='Каталог'))
    scene = repo.create_scene(item.id, SceneCreate(title='1', beats=beats, character_ids=[]))
    prose = repo.save_version(item.id, scene.id, 'manual', 'Анна вдома.', [])
    repo.set_head(scene.id, 'prose', prose.id, repo.get_scene(scene.id).revision)
    return repo, repo.get_story(item.id), repo.get_scene(scene.id)


@pytest.mark.req('MEMORY-LOCATIONS')
def test_memory_stage_allows_the_scene_places_and_their_ancestors(tmp_path):
    repo, story, scene = memory_scene(tmp_path, 'Локація: Дім / кухня')
    context = build_context(repo, scene.id, 'memory', role())
    places = [lid(story, 'Дім'), lid(story, 'Дім', 'кухня')]
    assert json.loads(context.fragments['memory_schema_bounds'])['location_ids'] == places
    head = 'ДОЗВОЛЕНІ LOCATION_IDS'
    line = next(part for part in context.user_text.split('\n\n') if part.startswith(head))
    assert json.loads(line.split('\n', 1)[1]) == {places[0]: 'Дім', places[1]: 'Дім / кухня'}
    assert HEAD + '\n' not in context.user_text


@pytest.mark.req('MEMORY-LOCATIONS')
def test_memory_stage_of_a_scene_without_places_is_unchanged(tmp_path):
    repo, story, scene = memory_scene(tmp_path, 'Вдома')
    context = build_context(repo, scene.id, 'memory', role())
    assert 'location_ids' not in context.fragments['memory_schema_bounds']
    assert 'LOCATION_IDS' not in context.user_text


@pytest.mark.req('MEMORY-LOCATIONS')
def test_writing_memory_keeps_a_state_of_an_absent_character_in_the_same_place(tmp_path):
    from storygen.memory.journal import MemoryJournal, _add_event
    repo, story, first, second = setup(tmp_path, other='Локація: Дім / кухня')
    prose = repo.save_version(story.id, first.id, 'manual', 'Олег чекав у кухні.', [])
    repo.set_head(first.id, 'prose', prose.id, repo.get_scene(first.id).revision)
    events = [_add_event('character_states', 'Олег чекає біля плити', prose.id, 'Олег чекав у кухні.', 0, ['o'],
                         location_ids=[lid(story, 'Дім', 'кухня')])]
    memory = repo.save_version(story.id, first.id, 'memory',
                               MemoryJournal(schema_version=3, source_prose_ids=[prose.id], events=events).model_dump_json(), [prose.id])
    repo.set_head(first.id, 'memory', memory.id, repo.get_scene(first.id).revision)
    assert 'Олег чекає біля плити' in build_context(repo, second.id, 'brief', role()).user_text
    repo.update_scene_plan(second.id, 'Хто бере участь: Юлія\nЛокація: Ліс', repo.get_scene(second.id).revision)
    assert 'Олег чекає біля плити' not in build_context(repo, second.id, 'brief', role()).user_text


@pytest.mark.req('MEMORY-LOCATIONS')
def test_writing_context_lists_locations_and_a_description_changes_the_fingerprint(tmp_path):
    from storygen.application.writing_context import writing_context
    repo, story, scene, _ = setup(tmp_path)
    before = writing_context(repo, scene.id)
    assert before['locations'] == [{'path': 'Дім', 'description': ''}, {'path': 'Дім / кухня', 'description': ''}]
    write(repo, lambda db: store.set_description(db, story.id, lid(story, 'Дім', 'кухня'), 'Тісна.'))
    after = writing_context(repo, scene.id)
    assert after['locations'][1] == {'path': 'Дім / кухня', 'description': 'Тісна.'}
    assert after['context_fingerprint'] != before['context_fingerprint']
    repo, story, scene, _ = setup(tmp_path / 'plain', beats='Хто бере участь: Юлія\nЮлія чекає.')
    assert 'locations' not in writing_context(repo, scene.id)


@pytest.mark.req('MEMORY-LOCATIONS')
def test_manual_snapshot_has_the_location_selectors(tmp_path):
    from storygen.generation.dependencies import _manual_snapshot
    repo, story, scene, _ = setup(tmp_path)
    write(repo, lambda db: store.set_description(db, story.id, lid(story, 'Дім'), 'Старий дім.'))
    scene = repo.get_scene(scene.id)
    author = {s.field for s in _manual_snapshot(repo, scene, 'prose').selectors}
    mcp = {s.field for s in _manual_snapshot(repo, scene, 'draft', day_selectors=True).selectors}
    assert 'location_neighbourhood' in author and 'location_context' not in author
    assert {'location_neighbourhood', 'location_context'} <= mcp


@pytest.mark.req('MEMORY-LOCATIONS')
def test_memory_view_rows_name_their_locations_as_the_merge_target(tmp_path):
    from storygen.memory.forwarding import memory_view
    from storygen.memory.journal import MemoryJournal, _add_event
    repo, story, first, _ = setup(tmp_path, other='Локація: Хата')
    prose = repo.save_version(story.id, first.id, 'manual', 'Олег чекав у кухні.', [])
    repo.set_head(first.id, 'prose', prose.id, repo.get_scene(first.id).revision)
    events = [_add_event('facts', 'Плита гаряча', prose.id, 'Олег чекав у кухні.', 0, location_ids=[lid(story, 'Хата')]),
              _add_event('facts', 'Надворі ніч', prose.id, 'Олег чекав у кухні.', 0)]
    memory = repo.save_version(story.id, first.id, 'memory',
                               MemoryJournal(schema_version=3, source_prose_ids=[prose.id], events=events).model_dump_json(), [prose.id])
    repo.set_head(first.id, 'memory', memory.id, repo.get_scene(first.id).revision)
    rows = {r['text']: r['locations'] for r in memory_view(repo, first.id)['rows']}
    assert rows == {'Плита гаряча': ['Хата'], 'Надворі ніч': []}
    write(repo, lambda db: store.merge_location(db, story.id, lid(story, 'Хата'), lid(story, 'Дім', 'кухня')))
    assert {r['text']: r['locations'] for r in memory_view(repo, first.id)['rows']}['Плита гаряча'] == ['Дім / кухня']
