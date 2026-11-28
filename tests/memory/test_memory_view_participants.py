"""MEMORY-ENTITIES-S04: the memory table row lists the record's participants by their current names."""
import pytest

from storygen.memory.forwarding import memory_view
from storygen.memory.journal import MemoryJournal, _add_event
from storygen.storage.repository import Repository

from tests.generation.test_character_names_context import setup


def remember_with(repo, scenes, participants, index=0):
    """The memory of scenes[index] holds one fact with the given participant_ids; returns the view row."""
    story_id = scenes[0].story_id
    scene = scenes[index]
    prose = repo.save_version(story_id, scene.id, 'manual', 'Юлія йде.', [])
    repo.set_head(scene.id, 'prose', prose.id, repo.get_scene(scene.id).revision)
    event = _add_event('facts', 'Ключ лежить у коморі', prose.id, 'Юлія йде.', 0, participant_ids=participants)
    journal = MemoryJournal(schema_version=4, source_prose_ids=[prose.id], events=[event])
    memory = repo.save_version(story_id, scene.id, 'memory', journal.model_dump_json(), [prose.id])
    repo.set_head(scene.id, 'memory', memory.id, repo.get_scene(scene.id).revision)
    return memory_view(repo, scene.id)['rows'][0]


@pytest.mark.req('MEMORY-ENTITIES')
def test_memory_view_row_has_participant_names(tmp_path):
    repo, scenes = setup(tmp_path)
    row = remember_with(repo, scenes, ['j', 'h'])
    assert row['participants'] == ['Юлія', 'Хазяїн']


@pytest.mark.req('MEMORY-ENTITIES')
def test_memory_view_row_shows_the_name_current_in_the_scene(tmp_path):
    repo, scenes = setup(tmp_path)
    # The card «h» is called «Джон» from the second scene on: the row follows the scene of the table.
    assert remember_with(repo, scenes, ['h'], index=1)['participants'] == ['Джон']


@pytest.mark.req('MEMORY-ENTITIES')
def test_unknown_participant_is_skipped(tmp_path):
    repo, scenes = setup(tmp_path)
    row = remember_with(repo, scenes, ['gone'])
    assert row['participants'] == []


@pytest.mark.req('MEMORY-ENTITIES')
def test_record_without_participants_has_an_empty_list(tmp_path):
    repo, scenes = setup(tmp_path)
    assert remember_with(repo, scenes, [])['participants'] == []
