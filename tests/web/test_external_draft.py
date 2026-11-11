import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.authoring.imports import SourceFile, import_sources
from storygen.domain import SceneCreate, StoryCreate
from storygen.generation.dependencies import writing_fingerprint
from storygen.web.app import create_app

ORIGIN = {'client': 'Claude Desktop', 'model': 'test-model'}


def setup(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк'))
    scene = repo.create_scene(story.id, SceneCreate(title='Лист', beats='Анна знаходить лист.'))
    client = TestClient(app, base_url='http://127.0.0.1:8765')
    return client, repo, story, scene


def characters(repo, story_id, names):
    text = '# Персонажі\n\n' + '\n\n'.join(f'## {name}\nОпис {name}.' for name in names)
    import_sources(repo, story_id, [SourceFile(name='characters.md', raw=text.encode(), kind='source_characters')])


def fingerprint(client, scene_id):
    repo = client.app.state.repo
    return writing_fingerprint(repo, repo.get_scene(scene_id))


def save(client, scene_id, revision, fp, text='Анна відчинила скриньку.', origin=ORIGIN):
    body = {'text': text, 'expected_revision': revision, 'content_format': 'markdown', 'expected_context_fingerprint': fp}
    if origin is not None:
        body['external_origin'] = origin
    return client.post(f'/api/scenes/{scene_id}/draft', json=body)


@pytest.mark.req('MCP-BRIDGE')
def test_external_draft_becomes_current_and_keeps_previous(tmp_path):
    client, repo, story, scene = setup(tmp_path)
    first = repo.save_version(story.id, scene.id, 'draft', 'Стара чернетка.', [])
    scene = repo.set_head(scene.id, 'draft', first.id, scene.revision)
    response = save(client, scene.id, scene.revision, fingerprint(client, scene.id))
    assert response.status_code == 200, response.text
    version = response.json()['version']
    assert version['external_origin'] == ORIGIN
    assert repo.get_scene(scene.id).heads['draft'] == version['id']
    assert {v.id for v in repo.list_versions(story.id, scene.id, 'draft')} >= {first.id, version['id']}


@pytest.mark.req('MCP-BRIDGE')
def test_same_text_from_external_client_still_creates_a_version(tmp_path):
    client, repo, story, scene = setup(tmp_path)
    one = save(client, scene.id, scene.revision, fingerprint(client, scene.id)).json()
    two = save(client, scene.id, one['scene']['revision'], fingerprint(client, scene.id))
    assert two.status_code == 200, two.text
    assert two.json()['version']['id'] != one['version']['id']


@pytest.mark.req('MCP-BRIDGE')
def test_stale_revision_is_rejected_and_draft_unchanged(tmp_path):
    client, repo, story, scene = setup(tmp_path)
    fp = fingerprint(client, scene.id)
    ok = save(client, scene.id, scene.revision, fp)
    assert ok.status_code == 200
    stale = save(client, scene.id, scene.revision, fingerprint(client, scene.id), text='Інший текст.')
    assert stale.status_code == 409
    assert repo.get_scene(scene.id).heads['draft'] == ok.json()['version']['id']


@pytest.mark.req('MCP-BRIDGE')
def test_changed_cards_between_read_and_write_are_rejected(tmp_path):
    client, repo, story, scene = setup(tmp_path)
    characters(repo, story.id, ['Анна'])
    fp = fingerprint(client, scene.id)
    revision = repo.get_scene(scene.id).revision
    characters(repo, story.id, ['Марія'])
    assert repo.get_scene(scene.id).revision == revision
    response = save(client, scene.id, revision, fp)
    assert response.status_code == 409
    assert 'Контекст сцени змінився' in response.text
    assert 'draft' not in repo.get_scene(scene.id).heads


@pytest.mark.req('MCP-BRIDGE')
def test_external_origin_requires_fingerprint(tmp_path):
    client, repo, story, scene = setup(tmp_path)
    response = save(client, scene.id, scene.revision, None)
    assert response.status_code in {400, 422}
    assert 'draft' not in repo.get_scene(scene.id).heads


@pytest.mark.req('STORY-LANGUAGE')
def test_external_draft_locks_story_language(tmp_path):
    client, repo, story, scene = setup(tmp_path)
    assert repo.story_language_locked(story.id) is False
    assert save(client, scene.id, scene.revision, fingerprint(client, scene.id)).status_code == 200
    assert repo.story_language_locked(story.id) is True


@pytest.mark.req('MCP-BRIDGE')
def test_external_origin_client_name_is_validated(tmp_path):
    client, repo, story, scene = setup(tmp_path)
    response = save(client, scene.id, scene.revision, fingerprint(client, scene.id), origin={'client': '<script>'})
    assert response.status_code == 422
