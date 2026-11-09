from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from tests.memory.test_core_review import two_scenes, v4_scene


def client(tmp_path):
    return TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765')


def test_get_core_review_route(tmp_path):
    repo, story, scene, claims, attempt = v4_scene(tmp_path)
    with client(tmp_path) as http:
        response = http.get(f'/api/scenes/{scene.id}/core-review')
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {'scene_id', 'memory_version_id', 'revision', 'has_wire', 'day_change', 'confirmation', 'slots', 'threads'}
        assert body['has_wire'] is True and body['threads'][0]['status'] == 'closed'
        english = http.get(f'/api/scenes/{scene.id}/core-review', headers={'accept-language': 'en'}).json()
        assert english['slots'][0]['label'] == 'clothing'
        assert http.get('/api/scenes/missing/core-review').status_code == 404


def test_fragments_route_requires_query_or_scene(tmp_path):
    repo, story, s1, s2, journal, claims = two_scenes(tmp_path)
    with client(tmp_path) as http:
        url = f'/api/scenes/{s2.id}/core-review/fragments'
        missing = http.get(url)
        assert missing.status_code == 422 and missing.json()['detail'] == 'Вкажіть сцену або текст для пошуку фрагмента'
        english = http.get(url, headers={'accept-language': 'en'})
        assert english.status_code == 422 and english.json()['detail'] == 'Choose a scene or enter text to search for a fragment'
        assert http.get(url, params={'q': '  '}).status_code == 422
        assert http.get(f'/api/scenes/{s1.id}/core-review/fragments', params={'scene_id': s2.id}).status_code == 422
        found = http.get(url, params={'q': 'пальто'})
        assert found.status_code == 200 and [f['text'] for f in found.json()] == ['Анна вдягла пальто.']
        by_scene = http.get(url, params={'scene_id': s1.id})
        assert by_scene.status_code == 200 and len(by_scene.json()) == 3


def test_scenes_route(tmp_path):
    repo, story, s1, s2, journal, claims = two_scenes(tmp_path)
    with client(tmp_path) as http:
        response = http.get(f'/api/scenes/{s2.id}/core-review/scenes')
        assert response.status_code == 200
        assert [(s['scene_id'], s['scene_number'], s['title']) for s in response.json()] == [(s1.id, 1, 'С1'), (s2.id, 2, 'С2')]


def test_post_core_review_route(tmp_path):
    from tests.memory.test_core_review import manual_scene
    repo, story, scene, claims = manual_scene(tmp_path)
    url = f'/api/scenes/{scene.id}/core-review'
    base = {'expected_revision': scene.revision, 'memory_version_id': scene.heads['memory']}
    keep = {'kind': 'slot', 'character_id': 'A', 'slot': 'carried', 'action': 'keep'}
    with client(tmp_path) as http:
        rejected = http.post(url, json={**base, 'edits': [keep]})
        assert rejected.status_code == 422
        assert rejected.json()['detail'] == 'Лишити попереднє недоступне: у цієї версії немає відповіді моделі'
        english = http.post(url, json={**base, 'edits': [keep]}, headers={'accept-language': 'en'})
        assert english.status_code == 422 and english.json()['detail'] == 'Keep previous is unavailable: this version has no model answer'
        quote = {'kind': 'slot', 'character_id': 'A', 'slot': 'body', 'action': 'set', 'text': 'Втомлена', 'quote': 'Немає такого.'}
        assert http.post(url, json={**base, 'edits': [quote]}).json()['detail'] == 'Цитату не знайдено в прозі цієї або попередніх сцен'
        # A set without a value is a malformed body.
        assert http.post(url, json={**base, 'edits': [{**quote, 'text': None, 'quote': None}]}).status_code == 422
        stale = http.post(url, json={**base, 'expected_revision': scene.revision - 1})
        assert stale.status_code == 409
        confirmed = http.post(url, json=base)
        assert confirmed.status_code == 200 and confirmed.json()['confirmation']['by'] == 'author'
        assert confirmed.json()['memory_version_id'] == scene.heads['memory']
        edited = http.post(url, json={**base, 'edits': [{**quote, 'quote': None}]})
        assert edited.status_code == 200
        body = edited.json()
        assert body['memory_version_id'] != scene.heads['memory'] and body['confirmation'] is not None
        assert body['revision'] == repo.get_scene(scene.id).revision
        # The reviewed head is no longer current: a second post on it is a conflict.
        assert http.post(url, json={**base, 'expected_revision': body['revision']}).status_code == 409
