"""BOOK-LINEAGE-S04: a core slot is core in the scenes of its owner's arcs; elsewhere it is an ordinary state (neutral examples)."""
import json

import pytest

from storygen.memory.journal import MemoryJournal
from storygen.storage.book_structure import put_structure
from tests.generation.test_context_selection import story_with_memory

SLOT_TEXT = 'Синій халат'
HERO = 'Роль: Головна героїня'


def arcs_book(tmp_path):
    """Scene 1 in arc X (book hero A), scene 2 in arc Y with protagonist B; both scenes carry A's clothing slot in memory."""
    repo, second, journal, prose = story_with_memory(tmp_path)
    story_id = second.story_id
    first = repo.list_scenes(story_id)[0]
    data = [dict(schema_version=2, id=i, name=n, entries=[dict(id='e' + i, text=HERO if i == 'A' else 'Опис', availability='timeless', origin='author')])
            for i, n in [('A', 'Анна'), ('B', 'Борис')]]
    cards = repo.save_version(story_id, None, 'character_cards', json.dumps(data, ensure_ascii=False), []).id
    repo.publish_story_material(story_id, 'characters_version_id', cards, repo.get_story(story_id).revision)
    parts = [{'id': 'p1', 'title': '', 'arcs': [{'id': 'X', 'title': ''}]},
             {'id': 'p2', 'title': '', 'arcs': [{'id': 'Y', 'title': '', 'protagonist_id': 'B'}]}]
    put_structure(repo, story_id, parts, {first.id: 'X', second.id: 'Y'}, repo.get_story(story_id).revision)
    # Publishing the cards stales the first memory; save it again on top of the new materials.
    renewed = repo.save_version(story_id, first.id, 'memory', journal.model_dump_json(), [prose.id])
    repo.set_head(first.id, 'memory', renewed.id, repo.get_scene(first.id).revision)
    own = repo.save_version(story_id, second.id, 'manual', 'Борис біля маяка.', [])
    repo.set_head(second.id, 'prose', own.id, repo.get_scene(second.id).revision)
    later = MemoryJournal(schema_version=3, source_prose_ids=[prose.id, own.id], events=journal.events)
    memory = repo.save_version(story_id, second.id, 'memory', later.model_dump_json(), [prose.id, own.id])
    repo.set_head(second.id, 'memory', memory.id, repo.get_scene(second.id).revision)
    slot = next(e.claim_id for e in journal.events if e.text == SLOT_TEXT)
    return repo, story_id, first, repo.get_scene(second.id), slot


def slot_row(repo, scene_id, claim_id):
    from storygen.memory.forwarding import memory_view
    return next(row for row in memory_view(repo, scene_id)['rows'] if row['claim_id'] == claim_id)


def test_other_arc_protagonist_slot_is_an_ordinary_state(tmp_path):
    repo, _, first, second, slot = arcs_book(tmp_path)
    assert slot_row(repo, first.id, slot)['slot'] is True
    assert slot_row(repo, second.id, slot)['slot'] is False


def test_mark_is_refused_only_where_the_slot_is_core(tmp_path):
    repo, story_id, first, second, slot = arcs_book(tmp_path)
    refused = '^Слот ядра завжди показується; тип не змінюється$'
    with pytest.raises(ValueError, match=refused):
        repo.update_memory_kind(story_id, slot, 'atmosphere', repo.get_story(story_id).revision, scene_id=first.id)
    with pytest.raises(ValueError, match=refused):
        repo.update_memory_kind(story_id, slot, 'atmosphere', repo.get_story(story_id).revision)
    marked = repo.update_memory_kind(story_id, slot, 'atmosphere', repo.get_story(story_id).revision, scene_id=second.id)
    assert marked.memory_kind_overrides == {slot: 'atmosphere'}
    with pytest.raises(KeyError):
        repo.update_memory_kind(story_id, slot, 'core', marked.revision, scene_id='missing')


def test_memory_stage_tracks_the_scene_protagonist(tmp_path):
    from storygen.generation.context import memory_projection
    repo, story_id, first, second, _ = arcs_book(tmp_path)
    view = repo.context_view(story_id)
    story, scenes = view.get_story(story_id), view.list_scenes(story_id)
    assert memory_projection(view, story, second, scenes, 'uk')[4] == ['B']
    assert memory_projection(view, story, first, scenes, 'uk')[4] == ['A']
