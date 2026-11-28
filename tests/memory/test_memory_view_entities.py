"""MEMORY-ENTITIES-S05: the memory table row shows the effective entities (overlay) and where they come from."""
import pytest

from storygen.memory.forwarding import memory_view
from storygen.storage import locations as store

from tests.generation.test_character_names_context import setup
from tests.memory.test_memory_view_participants import remember_with


def a_place(repo, story_id):
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        (place,) = store.ensure_locations(db, story_id, [('Маяк',)])
    return place


def revision(repo, story_id):
    return repo.get_story(story_id).revision


def row_of(repo, scene):
    return memory_view(repo, scene.id)['rows'][0]


@pytest.mark.req('MEMORY-ENTITIES')
def test_row_shows_overlay_participants_and_locations(tmp_path):
    repo, scenes = setup(tmp_path)
    row = remember_with(repo, scenes, [])
    place = a_place(repo, scenes[0].story_id)
    repo.apply_entity_marks(scenes[0].story_id, {row['claim_id']: (['j'], [place])}, revision(repo, scenes[0].story_id))
    row = row_of(repo, scenes[0])
    assert row['participants'] == ['Юлія']
    assert row['participant_ids'] == ['j']
    assert row['location_ids'] == [place]
    assert row['locations'] == ['Маяк']
    assert row['entities_source'] == 'model'


@pytest.mark.req('MEMORY-ENTITIES')
def test_author_mark_is_shown_as_author(tmp_path):
    repo, scenes = setup(tmp_path)
    row = remember_with(repo, scenes, [])
    sid = scenes[0].story_id
    repo.update_memory_entities(sid, row['claim_id'], ['h'], [], revision(repo, sid))
    row = row_of(repo, scenes[0])
    assert (row['participants'], row['entities_source']) == (['Хазяїн'], 'author')


@pytest.mark.req('MEMORY-ENTITIES')
def test_event_entities_are_shown_as_event_and_unmarked_as_none(tmp_path):
    repo, scenes = setup(tmp_path)
    row = remember_with(repo, scenes, ['j'])
    assert (row['participant_ids'], row['entities_source']) == (['j'], 'event')
    bare = remember_with(repo, scenes, [], index=1)
    assert (bare['participant_ids'], bare['location_ids'], bare['entities_source']) == ([], [], None)


@pytest.mark.req('MEMORY-ENTITIES')
def test_row_drops_a_deleted_participant_id(tmp_path):
    repo, scenes = setup(tmp_path)
    row = remember_with(repo, scenes, ['gone'])
    assert row['participant_ids'] == []
    assert row['participants'] == []
    assert row['entities_source'] is None
