"""#44: GET/POST /api/scenes/{id}/brief-link."""
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from tests.characters.test_acquaintance_history import setup, brief, prose, with_brief_prose, run


def client(tmp_path):
    return TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765')


def orphan(repo, story, scene, introduced=None):
    """Prose without a brief in its lineage, plus a current brief head (the #44 shape)."""
    b = brief(repo, story, scene, introduced)
    repo.set_head(scene.id, 'brief', b.id, repo.get_scene(scene.id).revision)
    p = prose(repo, story, scene)
    return b, p


def test_state_needed_and_confirm(tmp_path):
    repo, story, (s1, s2, s3) = setup(tmp_path, casts=[['A', 'B', 'C'], ['A', 'B'], ['A']])
    b, p = orphan(repo, story, s1)
    orphan(repo, story, s2)
    with client(tmp_path) as http:
        state = http.get(f'/api/scenes/{s1.id}/brief-link').json()
        assert state['needed'] is True and state['source'] == 'fallback' and state['hero_id'] == 'A'
        assert [c['id'] for c in state['cast']] == ['B', 'C'] and not any(c['checked'] for c in state['cast'])
        assert state['brief']['version_id'] == b.id and state['next_scene_id'] == s2.id
        body = {'prose_version_id': p.id, 'brief_version_id': b.id, 'introduced': ['C'], 'expected_revision': state['revision']}
        done = http.post(f'/api/scenes/{s1.id}/brief-link', json=body)
        assert done.status_code == 200 and done.json()['version']['brief_link']['introduced'] == ['C']
        after = http.get(f'/api/scenes/{s1.id}/brief-link').json()
        assert after['needed'] is False and after['source'] == 'link'
        assert [c['checked'] for c in after['cast']] == [False, True]
    assert run(repo, story, 2).known == {'C': 1, 'B': 2}


def test_confirm_changes_nothing_else(tmp_path):
    repo, story, (s1, s2) = setup(tmp_path, casts=[['A', 'B'], ['A']])
    b, p = orphan(repo, story, s1)
    before_scene = repo.get_scene(s1.id)
    before = repo.get_version(p.id)
    with client(tmp_path) as http:
        http.post(f'/api/scenes/{s1.id}/brief-link', json={'prose_version_id': p.id, 'brief_version_id': b.id, 'introduced': [], 'expected_revision': before_scene.revision}).raise_for_status()
    after_scene = repo.get_scene(s1.id)
    after = repo.get_version(p.id)
    assert (after_scene.revision, after_scene.heads) == (before_scene.revision, before_scene.heads)
    assert (after.sha256, after.input_refs, after.dependency_snapshot, after.stale) == (before.sha256, before.input_refs, before.dependency_snapshot, before.stale)
    assert run(repo, story, 1).known == {}


def test_conflicts_and_validation(tmp_path):
    repo, story, (s1, s2) = setup(tmp_path, casts=[['A', 'B'], ['A']])
    b, p = orphan(repo, story, s1)
    rev = repo.get_scene(s1.id).revision
    with client(tmp_path) as http:
        url = f'/api/scenes/{s1.id}/brief-link'
        assert http.post(url, json={'prose_version_id': p.id, 'brief_version_id': b.id, 'introduced': ['A'], 'expected_revision': rev}).status_code == 400
        assert http.post(url, json={'prose_version_id': p.id, 'brief_version_id': b.id, 'introduced': ['B', 'B'], 'expected_revision': rev}).status_code == 400
        newer = brief(repo, story, s1, None)
        repo.set_head(s1.id, 'brief', newer.id, rev)
        stale = http.post(url, json={'prose_version_id': p.id, 'brief_version_id': b.id, 'introduced': [], 'expected_revision': repo.get_scene(s1.id).revision})
        assert stale.status_code == 409
        english = http.post(url, json={'prose_version_id': p.id, 'brief_version_id': b.id, 'introduced': [], 'expected_revision': 0}, headers={'accept-language': 'en'})
        assert english.status_code == 409 and 'confirmation was not saved' in english.json()['detail']
        assert http.get('/api/scenes/missing/brief-link').status_code == 404


def test_not_needed_without_brief_head_or_other_participants(tmp_path):
    repo, story, (s1, s2, s3) = setup(tmp_path, casts=[['A', 'B'], ['A'], ['A']])
    prose(repo, story, s1)              # prose but no brief head
    orphan(repo, story, s2)             # hero alone
    with client(tmp_path) as http:
        assert http.get(f'/api/scenes/{s1.id}/brief-link').json()['needed'] is False
        state = http.get(f'/api/scenes/{s2.id}/brief-link').json()
        assert state['needed'] is False and state['cast'] == [] and state['next_scene_id'] is None


def test_checked_prefers_current_brief_then_lineage(tmp_path):
    repo, story, (s1, s2) = setup(tmp_path, casts=[['A', 'B', 'C'], ['A']])
    b, p = orphan(repo, story, s1, ['B'])
    with client(tmp_path) as http:
        state = http.get(f'/api/scenes/{s1.id}/brief-link').json()
        assert state['needed'] is True and [c['checked'] for c in state['cast']] == [True, False]


def test_lineage_brief_with_introduced_is_not_needed(tmp_path):
    repo, story, (s1, s2) = setup(tmp_path, casts=[['A', 'B'], ['A']])
    with_brief_prose(repo, story, s1, ['B'])
    repo.set_head(s1.id, 'brief', brief(repo, story, s1, ['B']).id, repo.get_scene(s1.id).revision)
    with client(tmp_path) as http:
        state = http.get(f'/api/scenes/{s1.id}/brief-link').json()
        assert state['needed'] is False and state['source'] == 'lineage'
