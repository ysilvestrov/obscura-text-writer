"""BOOK-LINEAGE-S04: the arc protagonist is saved with the structure and must name a current card (neutral examples)."""
import json

import pytest

from storygen.domain import Scene
from storygen.storage.book_structure import place_imported, put_structure
from tests.storage.test_book_structure import setup


def parts(protagonist):
    return [{'id': 'p1', 'title': 'Перша', 'arcs': [{'id': 'a1', 'title': ''}]},
            {'id': 'p2', 'title': 'Друга', 'arcs': [{'id': 'b1', 'title': '', 'protagonist_id': protagonist}]}]


def with_cards(tmp_path):
    repo, story, scenes = setup(tmp_path, 2)
    data = [dict(schema_version=2, id=i, name=n, entries=[dict(id='e' + i, text='Опис', availability='timeless', origin='author')])
            for i, n in [('A', 'Анна'), ('B', 'Богдан')]]
    cards = repo.save_version(story.id, None, 'character_cards', json.dumps(data, ensure_ascii=False), []).id
    repo.publish_story_material(story.id, 'characters_version_id', cards, story.revision)
    return repo, repo.get_story(story.id), scenes


def test_put_structure_saves_the_protagonist(tmp_path):
    repo, story, (s1, s2) = with_cards(tmp_path)
    saved = put_structure(repo, story.id, parts('B'), {s1.id: 'a1', s2.id: 'b1'}, story.revision)
    assert saved.revision == story.revision + 1
    assert saved.book_structure.parts[1].arcs[0].protagonist_id == 'B'
    assert repo.get_story(story.id).book_structure.parts[0].arcs[0].protagonist_id is None


def test_unknown_card_is_refused_without_saving(tmp_path):
    repo, story, (s1, s2) = with_cards(tmp_path)
    with pytest.raises(ValueError, match='^Протагоніст арки — картка, якої немає серед персонажів$'):
        put_structure(repo, story.id, parts('Z'), {s1.id: 'a1', s2.id: 'b1'}, story.revision)
    assert repo.get_story(story.id).revision == story.revision and repo.get_story(story.id).book_structure is None


def test_import_continuation_keeps_the_protagonist(tmp_path):
    repo, story, (s1, s2) = with_cards(tmp_path)
    story = put_structure(repo, story.id, parts('B'), {s1.id: 'a1', s2.id: 'b1'}, story.revision)
    new = Scene(id='s3', story_id=story.id, title='Нова', position=2)
    placed = place_imported(story, [s1, s2, new], [(new, 'Друга', None, 0)], True)
    assert placed.book_structure.parts[1].arcs[0].protagonist_id == 'B' and placed.scene_arcs['s3'] == 'b1'
