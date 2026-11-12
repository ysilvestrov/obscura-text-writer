import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import SceneCreate, StoryCreate
from storygen.web.app import create_app



def setup(tmp_path, n=3):
    app = create_app(AppSettings(data_dir=tmp_path / 'data', env_file=tmp_path / 'absent.env'))
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Книга'))
    scenes = [repo.create_scene(story.id, SceneCreate(title=f'Scene {i+1}')) for i in range(n)]
    return TestClient(app, base_url='http://127.0.0.1'), repo, repo.get_story(story.id), scenes


PARTS = [{'id': 'p1', 'title': 'Перша', 'arcs': [{'id': 'a1', 'title': 'Ранок'}, {'id': 'a2', 'title': ''}]},
         {'id': 'p2', 'title': '', 'arcs': [{'id': 'b1', 'title': ''}]}]


def put(client, story, scenes, arcs, revision=None):
    return client.put(f'/api/stories/{story.id}/structure', json={
        'expected_revision': story.revision if revision is None else revision, 'parts': PARTS,
        'scene_arcs': {s.id: a for s, a in zip(scenes, arcs)}})


def test_story_view_of_flat_book_has_implicit_structure(tmp_path):
    client, _, story, scenes = setup(tmp_path)
    data = client.get(f'/api/stories/{story.id}').json()
    assert data['book_structure']['kind'] == 'flat' and not data['book_structure']['explicit']
    assert [len(p['arcs']) for p in data['book_structure']['parts']] == [1]
    assert {s['arc_id'] for s in data['scenes']} == {'implicit-arc'}


def test_put_structure_and_story_view(tmp_path):
    client, _, story, scenes = setup(tmp_path)
    response = put(client, story, scenes, ['a1', 'a2', 'b1'])
    assert response.status_code == 200, response.text
    data = client.get(f'/api/stories/{story.id}').json()
    assert data['book_structure']['kind'] == 'structured' and data['book_structure']['explicit']
    assert [p['id'] for p in data['book_structure']['parts']] == ['p1', 'p2']
    assert [s['arc_id'] for s in data['scenes']] == ['a1', 'a2', 'b1']


def test_put_structure_conflict_and_sequence_errors(tmp_path):
    client, repo, story, scenes = setup(tmp_path)
    assert put(client, story, scenes, ['a1', 'a2', 'b1'], story.revision - 1).status_code == 409
    mixed = put(client, story, scenes, ['a2', 'a1', 'b1'])
    assert mixed.status_code == 400 and 'Scene 2' in mixed.text
    assert repo.get_story(story.id).book_structure is None


def test_assign_arc_and_dissolve(tmp_path):
    client, repo, story, scenes = setup(tmp_path)
    assert put(client, story, scenes, ['a1', 'a2', 'b1']).status_code == 200
    story = repo.get_story(story.id)
    response = client.put(f'/api/stories/{story.id}/scenes/{scenes[1].id}/arc', json={'arc_id': 'a1', 'expected_revision': story.revision})
    assert response.status_code == 200, response.text
    assert response.json()['scene_arcs'][scenes[1].id] == 'a1'
    story = repo.get_story(story.id)
    bad = client.put(f'/api/stories/{story.id}/scenes/{scenes[0].id}/arc', json={'arc_id': 'b1', 'expected_revision': story.revision})
    assert bad.status_code == 400
    gone = client.request('DELETE', f'/api/stories/{story.id}/structure', json={'expected_revision': story.revision})
    assert gone.status_code == 200, gone.text
    assert client.get(f'/api/stories/{story.id}').json()['book_structure']['explicit'] is False


def test_structure_routes_refused_without_long_prose(tmp_path, store_edition):
    client, repo, story, scenes = setup(tmp_path)
    assert put(client, story, scenes, ['a1', 'a2', 'b1']).status_code == 400
    assert client.put(f'/api/stories/{story.id}/scenes/{scenes[0].id}/arc', json={'arc_id': 'a1', 'expected_revision': story.revision}).status_code == 400
    assert client.request('DELETE', f'/api/stories/{story.id}/structure', json={'expected_revision': story.revision}).status_code == 400
    assert repo.get_story(story.id).revision == story.revision
