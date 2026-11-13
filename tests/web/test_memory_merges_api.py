"""MEMORY-MERGE-S02/S05 (API and pipeline): the merge endpoints, the stop before a merge scene and readiness."""
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.storage.memory_merges import merge_point
from storygen.web.app import create_app
from tests.memory.merge_helpers import arc_book
from tests.storage.test_memory_merges import coat_events


def app_book(tmp_path, tokens='Z A B A+B', parts=(['Z'], ['A', 'B'])):
    app = create_app(AppSettings(data_dir=tmp_path / 'data', env_file=tmp_path / 'absent.env'))
    repo, story, scenes = arc_book(None, tokens, list(parts), coat_events, repo=app.state.repo)
    return TestClient(app, base_url='http://127.0.0.1'), repo, story, scenes


def test_get_and_put_merge(tmp_path):
    client, repo, story, scenes = app_book(tmp_path)
    url = f'/api/stories/{story.id}/memory-merges'
    assert client.get(url, params={'scene_id': scenes[2].id}).json()['state'] == 'not_needed'
    state = client.get(url, params={'scene_id': scenes[3].id}).json()
    assert state['state'] == 'none' and [c['key'] for c in state['conflicts']] == ['slot:c1:clothing']
    body = {'decisions': {'slot:c1:clothing': {'choice': scenes[1].id}}, 'expected_revision': state['story_revision'],
            'expected_head_memory_ids': [h['memory_id'] for h in state['heads']]}
    saved = client.put(f'{url}/{state["key"]}', json=body)
    assert saved.status_code == 200, saved.text
    after = client.get(url, params={'scene_id': scenes[3].id}).json()
    assert after['state'] == 'fresh' and after['carried'] == {'slot:c1:clothing': {'choice': scenes[1].id}}


def test_put_merge_revision_conflict_and_missing_decision(tmp_path):
    client, repo, story, scenes = app_book(tmp_path)
    url = f'/api/stories/{story.id}/memory-merges'
    state = client.get(url, params={'scene_id': scenes[3].id}).json()
    heads = [h['memory_id'] for h in state['heads']]
    stale = client.put(f'{url}/{state["key"]}', json={'decisions': {'slot:c1:clothing': {'choice': 'author', 'text': 'Анна в шубі'}},
                                                     'expected_revision': state['story_revision'] - 1, 'expected_head_memory_ids': heads})
    assert stale.status_code == 409
    missing = client.put(f'{url}/{state["key"]}', json={'decisions': {}, 'expected_revision': state['story_revision'],
                                                       'expected_head_memory_ids': heads})
    assert missing.status_code == 400 and 'slot:c1:clothing' in missing.text
    assert client.put(f'{url}/heads:x,y', json={'decisions': {}, 'expected_revision': state['story_revision'],
                                                'expected_head_memory_ids': heads}).status_code == 400
    assert repo.get_story(story.id).memory_merge_heads == {}


def test_book_end_merge_does_not_stop_the_last_scene(tmp_path):
    client, repo, story, scenes = app_book(tmp_path, 'A B A B', (['A', 'B'],))
    state = client.get(f'/api/stories/{story.id}/memory-merges', params={'point': 'book_end'}).json()
    assert state['state'] == 'none' and [h['scene_id'] for h in state['heads']] == [scenes[2].id, scenes[3].id]
    assert merge_point(story, scenes, scene_id=scenes[3].id) is None


def test_store_edition_refuses_merge_put(tmp_path, store_edition):
    client, repo, story, scenes = app_book(tmp_path)
    url = f'/api/stories/{story.id}/memory-merges'
    state = client.get(url, params={'scene_id': scenes[3].id}).json()
    response = client.put(f'{url}/{state["key"]}', json={'decisions': {'slot:c1:clothing': {'choice': scenes[1].id}},
                                                         'expected_revision': state['story_revision'],
                                                         'expected_head_memory_ids': [h['memory_id'] for h in state['heads']]})
    assert response.status_code == 400
    assert repo.get_story(story.id).memory_merge_heads == {}
