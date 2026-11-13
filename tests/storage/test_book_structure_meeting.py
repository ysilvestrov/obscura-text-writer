"""BOOK-STRUCTURE, project 2: meeting scenes and interleaved arcs in storage and the API."""
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import SceneCreate, StoryCreate
from storygen.storage.book_structure import put_structure
from storygen.web.app import create_app

PARTS = [{'id': 'p1', 'title': 'Перша', 'arcs': [{'id': 'a1', 'title': 'Ранок'}, {'id': 'a2', 'title': ''}]},
         {'id': 'p2', 'title': 'Друга', 'arcs': [{'id': 'b1', 'title': ''}]}]


def setup(tmp_path, n=3):
    app = create_app(AppSettings(data_dir=tmp_path / 'data', env_file=tmp_path / 'absent.env'))
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Книга'))
    scenes = [repo.create_scene(story.id, SceneCreate(title=f'Scene {i+1}')) for i in range(n)]
    return TestClient(app, base_url='http://127.0.0.1'), repo, repo.get_story(story.id), scenes


def test_single_arc_is_stored_as_string(tmp_path):
    _, repo, story, scenes = setup(tmp_path)
    saved = put_structure(repo, story.id, PARTS, {scenes[0].id: ['a1'], scenes[1].id: ['a1', 'a2'], scenes[2].id: 'a2'}, story.revision)
    assert saved.scene_arcs == {scenes[0].id: 'a1', scenes[1].id: ['a1', 'a2'], scenes[2].id: 'a2'}
    assert repo.get_story(story.id).scene_arcs == saved.scene_arcs


def test_assign_meeting_scene(tmp_path):
    client, repo, story, scenes = setup(tmp_path)
    story = put_structure(repo, story.id, PARTS, {scenes[0].id: 'a1', scenes[1].id: 'a2', scenes[2].id: 'b1'}, story.revision)
    url = f'/api/stories/{story.id}/scenes/{scenes[1].id}/arc'
    response = client.put(url, json={'arc_ids': ['a1', 'a2'], 'expected_revision': story.revision})
    assert response.status_code == 200, response.text
    assert response.json()['scene_arcs'][scenes[1].id] == ['a1', 'a2']
    story = repo.get_story(story.id)
    assert client.put(url, json={'arc_id': 'a2', 'expected_revision': story.revision}).status_code == 200
    story = repo.get_story(story.id)
    assert client.put(url, json={'arc_id': 'a2', 'arc_ids': ['a1', 'a2'], 'expected_revision': story.revision}).status_code == 422
    assert client.put(url, json={'arc_ids': ['a1', 'b1'], 'expected_revision': story.revision}).status_code == 400


def test_interleaved_reorder_is_allowed(tmp_path):
    _, repo, story, scenes = setup(tmp_path)
    story = put_structure(repo, story.id, PARTS, {scenes[0].id: 'a1', scenes[1].id: 'a2', scenes[2].id: 'a1'}, story.revision)
    repo.reorder_scenes(story.id, [scenes[1].id, scenes[0].id, scenes[2].id], story.revision)
    assert [s.id for s in repo.list_scenes(story.id)] == [scenes[1].id, scenes[0].id, scenes[2].id]


def test_new_scene_after_meeting_scene(tmp_path):
    _, repo, story, scenes = setup(tmp_path)
    story = put_structure(repo, story.id, PARTS, {scenes[0].id: 'a2', scenes[1].id: ['a1', 'a2'], scenes[2].id: 'b1'}, story.revision)
    new = repo.create_scene(story.id, SceneCreate(title='After', position=2))
    assert repo.get_story(story.id).scene_arcs[new.id] == 'a2'


def test_restore_meeting_scene_never_refuses(tmp_path):
    _, repo, story, scenes = setup(tmp_path)
    story = put_structure(repo, story.id, PARTS, {scenes[0].id: 'a1', scenes[1].id: ['a1', 'a2'], scenes[2].id: 'b1'}, story.revision)
    repo.set_scene_trashed(story.id, scenes[1].id, repo.get_scene(scenes[1].id).revision, restore=False)
    story = repo.get_story(story.id)
    parts = [{'id': 'p1', 'title': 'Перша', 'arcs': [{'id': 'a1', 'title': 'Ранок'}]}, PARTS[1]]
    story = put_structure(repo, story.id, parts, {scenes[0].id: 'a1', scenes[2].id: 'b1'}, story.revision)
    trashed = repo.get_scene(scenes[1].id, include_trashed=True)
    repo.set_scene_trashed(story.id, scenes[1].id, trashed.revision, restore=True)
    assert repo.get_story(story.id).scene_arcs[scenes[1].id] == 'a1'
