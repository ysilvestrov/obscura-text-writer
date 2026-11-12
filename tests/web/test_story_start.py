"""MCP-BRIDGE package 2: a story is created with its rating, and a plan is written only over the plan that was read."""
import pytest

from storygen.domain import RevisionConflict

from tests.web.test_scene_text import client_for, plain_scene

RATING = {'sexual': 0, 'violence': 1, 'themes': 0}


def plan_versions(repo, story_id):
    return sorted(v.id for v in repo.context_view(story_id).versions.values() if v.kind == 'scene_plan')


def patch(client, story, scene_id, revision, **body):
    return client.patch(f'/api/scenes/{scene_id}', json={'story_id': story.id, 'expected_revision': revision, **body})


def with_plan_head(client, repo, story, scene, text='Анна знаходить лист.'):
    response = patch(client, story, scene.id, repo.get_scene(scene.id).revision, beats=text)
    assert response.status_code == 200, response.text
    return repo.get_scene(scene.id).heads['plan']


@pytest.mark.req('MCP-BRIDGE')
@pytest.mark.unrated_stories
def test_create_story_with_rating_sets_current_and_initial(tmp_path):
    app, *_ = plain_scene(tmp_path)
    with client_for(app) as client:
        response = client.post('/api/stories', json={'title': 'Острів', 'content_rating': RATING})
    assert response.status_code == 200, response.text
    story = app.state.repo.get_story(response.json()['id'])
    assert story.content_rating.model_dump() == RATING and story.initial_content_rating.model_dump() == RATING


@pytest.mark.req('MCP-BRIDGE')
@pytest.mark.unrated_stories
def test_create_story_without_rating_stays_unrated(tmp_path):
    app, *_ = plain_scene(tmp_path)
    with client_for(app) as client:
        response = client.post('/api/stories', json={'title': 'Острів'})
    assert response.status_code == 200, response.text
    assert response.json()['content_rating'] is None and response.json()['initial_content_rating'] is None


@pytest.mark.req('MCP-BRIDGE')
@pytest.mark.unrated_stories
def test_store_edition_refuses_rating_over_limit_and_creates_nothing(tmp_path, store_edition):
    app, repo, *_ = plain_scene(tmp_path)
    before = [s['id'] for s in client_for(app).get('/api/stories').json()]
    with client_for(app) as client:
        response = client.post('/api/stories', json={'title': 'Острів', 'content_rating': {'sexual': 2, 'violence': 0, 'themes': 0}})
        after = [s['id'] for s in client.get('/api/stories').json()]
    assert response.status_code == 400, response.text
    assert after == before


@pytest.mark.req('MCP-BRIDGE')
def test_stale_plan_is_409_and_saves_no_version(tmp_path):
    app, repo, story, scene = plain_scene(tmp_path)
    with client_for(app) as client:
        read_id = with_plan_head(client, repo, story, scene, 'Анна знаходить лист.')
        with_plan_head(client, repo, story, scene, 'Анна знаходить лист і ключ.')
        versions = plan_versions(repo, story.id)
        response = patch(client, story, scene.id, repo.get_scene(scene.id).revision, beats='План із чату.', expected_plan_version_id=read_id)
    assert response.status_code == 409, response.text
    assert 'get_scene_text' in response.json()['detail_original']
    assert plan_versions(repo, story.id) == versions
    assert repo.get_scene(scene.id).beats == 'Анна знаходить лист і ключ.'


@pytest.mark.req('MCP-BRIDGE')
def test_identical_plan_with_stale_id_is_409(tmp_path):
    app, repo, story, scene = plain_scene(tmp_path)
    with client_for(app) as client:
        read_id = with_plan_head(client, repo, story, scene, 'Перший план.')
        with_plan_head(client, repo, story, scene, 'Другий план.')
        response = patch(client, story, scene.id, repo.get_scene(scene.id).revision, beats='Другий план.', expected_plan_version_id=read_id)
    assert response.status_code == 409, response.text


@pytest.mark.req('MCP-BRIDGE')
def test_plan_with_current_id_is_saved(tmp_path):
    app, repo, story, scene = plain_scene(tmp_path)
    with client_for(app) as client:
        current = with_plan_head(client, repo, story, scene)
        response = patch(client, story, scene.id, repo.get_scene(scene.id).revision, beats='План із чату.', expected_plan_version_id=current)
    assert response.status_code == 200, response.text
    head = repo.get_scene(scene.id).heads['plan']
    assert head != current and repo.read_text(head) == 'План із чату.'
    assert repo.context_view(story.id).get_version(head).external_origin is None


@pytest.mark.req('MCP-BRIDGE')
def test_plan_with_null_id_when_no_plan_version(tmp_path):
    app, repo, story, scene = plain_scene(tmp_path)
    assert 'plan' not in scene.heads
    with client_for(app) as client:
        response = patch(client, story, scene.id, scene.revision, beats='План із чату.', expected_plan_version_id=None)
        stale = patch(client, story, scene.id, repo.get_scene(scene.id).revision, beats='Ще план.', expected_plan_version_id=None)
    assert response.status_code == 200, response.text
    assert repo.read_text(repo.get_scene(scene.id).heads['plan']) == 'План із чату.'
    assert stale.status_code == 409, stale.text


@pytest.mark.req('MCP-BRIDGE')
def test_plan_version_id_without_beats_is_400(tmp_path):
    app, repo, story, scene = plain_scene(tmp_path)
    with client_for(app) as client:
        response = patch(client, story, scene.id, scene.revision, title='Нова', expected_plan_version_id=None)
    assert response.status_code == 400, response.text
    assert repo.get_scene(scene.id).title == 'Лист'


@pytest.mark.req('MCP-BRIDGE')
@pytest.mark.parametrize('field,status', [({'title': ''}, 400), ({'target_words': 0}, 400), ({'prose_language': 'de'}, 422)])
def test_bad_field_with_plan_changes_nothing(tmp_path, field, status):
    app, repo, story, scene = plain_scene(tmp_path)
    with client_for(app) as client:
        current = with_plan_head(client, repo, story, scene)
        before, versions = repo.get_scene(scene.id), plan_versions(repo, story.id)
        response = patch(client, story, scene.id, before.revision, beats='План із чату.', expected_plan_version_id=current, **field)
    assert response.status_code == status, response.text
    assert repo.get_scene(scene.id) == before and plan_versions(repo, story.id) == versions


@pytest.mark.req('MCP-BRIDGE')
def test_race_after_plan_reports_plan_applied(tmp_path, monkeypatch):
    app, repo, story, scene = plain_scene(tmp_path)

    def raced(*args, **kwargs):
        raise RevisionConflict('Сцену вже змінено')
    monkeypatch.setattr('storygen.web.routes_stories.update_scene', raced)
    with client_for(app) as client:
        current = with_plan_head(client, repo, story, scene)
        response = patch(client, story, scene.id, repo.get_scene(scene.id).revision, beats='План із чату.', expected_plan_version_id=current, title='Нова')
    assert response.status_code == 409, response.text
    body = response.json()
    assert body['plan_applied'] is True and body['revision'] == repo.get_scene(scene.id).revision
    assert repo.get_scene(scene.id).beats == 'План із чату.'


@pytest.mark.req('MCP-BRIDGE')
def test_plan_from_chat_does_not_lock_language(tmp_path):
    app, repo, story, scene = plain_scene(tmp_path)
    with client_for(app) as client:
        response = patch(client, story, scene.id, scene.revision, beats='План із чату.', expected_plan_version_id=None)
        assert response.status_code == 200, response.text
        changed = client.put(f'/api/stories/{story.id}/language', json={'language': 'en', 'expected_revision': repo.get_story(story.id).revision})
    assert changed.status_code == 200, changed.text
