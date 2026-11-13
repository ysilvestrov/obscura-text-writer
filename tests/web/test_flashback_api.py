"""STORY-TIME-S07: the flashback flag over HTTP in every edition, and arcs with an unknown start (neutral examples)."""
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import SceneCreate, StoryCreate
from storygen.generation.context import build_context
from storygen.generation.context_labels import label
from storygen.storage.book_structure import put_structure
from storygen.storage.repository import Repository
from storygen.web.app import create_app
from tests.memory.test_core_review import role, two_scenes


def client_for(tmp_path):
    return TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765')


def test_patch_flashback_in_an_edition_without_long_prose(tmp_path, store_edition):
    repo, story, s1, s2, journal, claims = two_scenes(tmp_path)
    with client_for(tmp_path) as client:
        response = client.patch(f'/api/scenes/{s2.id}', json={'story_id': story.id, 'expected_revision': s2.revision, 'flashback': True})
        assert response.status_code == 200, response.text
        listed = {s['id']: s for s in client.get(f'/api/stories/{story.id}').json()['scenes']}
    assert listed[s2.id]['flashback'] is True and listed[s2.id]['flashback_marked'] is False
    assert label('memory_header', 'uk') not in build_context(repo, s2.id, 'brief', role()).user_text


def test_flashback_messages_are_translated():
    from storygen.memory.flashbacks import FLASHBACK_FACTS_ONLY, FOREIGN_LIMIT_WARNING
    from storygen.web.localization import diagnostic
    assert diagnostic(FLASHBACK_FACTS_ONLY, 'en') == 'A flashback adds only facts'
    assert diagnostic(FOREIGN_LIMIT_WARNING.format(shown=40, total=42), 'en') == 'The past of other arcs: 40 of 42 facts shown.'
    assert diagnostic('Рядок «Спогад:» має бути «так» або «ні»; прапорець не поставлено.', 'en').startswith('The «Flashback:» line')


def test_scene_list_reports_the_mark(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Оповідання'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена 1', beats='Початок: Рік -2 (спогад)'))
    with client_for(tmp_path) as client:
        listed = client.get(f'/api/stories/{story.id}').json()['scenes']
    assert listed[0]['id'] == scene.id and listed[0]['flashback'] is False and listed[0]['flashback_marked'] is True


def test_structure_reports_arcs_with_unknown_start_only_with_a_flashback(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    scenes = [repo.create_scene(story.id, SceneCreate(title=f'Сцена {n}', beats=beats))
              for n, beats in enumerate(['Початок: Рік 1', 'Анна йде містом.'], 1)]
    parts = [{'id': 'p1', 'title': 'Частина', 'arcs': [{'id': 'A', 'title': 'Перша'}, {'id': 'B', 'title': 'Друга'}]}]
    put_structure(repo, story.id, parts, {scenes[0].id: 'A', scenes[1].id: 'B'}, repo.get_story(story.id).revision)
    with client_for(tmp_path) as client:
        assert client.get(f'/api/stories/{story.id}').json()['book_structure']['arc_start_unknown'] == []
        repo.create_scene(story.id, SceneCreate(title='Сцена 3', beats='Початок: Рік -9 (спогад)'))
        assert client.get(f'/api/stories/{story.id}').json()['book_structure']['arc_start_unknown'] == ['B']
