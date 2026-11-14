"""SERIES-S06: an edition without long prose opens a series book read-only; MCP get_story reports the series."""
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.book.guard import READ_ONLY_SERIES
from storygen.domain import SceneCreate, StoryCreate
from storygen.storage import series as store
from storygen.web.app import create_app


def series_book(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path / 'data', env_file=tmp_path / 'absent.env'))
    repo = app.state.repo
    item = store.create_series(repo, 'Сага')
    story = repo.create_story(StoryCreate(title='Книга'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена'))
    store.set_story_series(repo, story.id, item.id, 1, None, repo.get_story(story.id).revision)
    return TestClient(app, base_url='http://127.0.0.1'), repo, repo.get_story(story.id), repo.get_scene(scene.id)


def test_store_opens_a_series_book_read_only(tmp_path, store_edition):
    client, repo, story, scene = series_book(tmp_path)
    assert client.get(f'/api/stories/{story.id}').status_code == 200
    refused = client.patch(f'/api/scenes/{scene.id}', json={'story_id': story.id, 'title': 'Інша', 'expected_revision': scene.revision})
    assert refused.status_code == 400 and READ_ONLY_SERIES in refused.json()['detail_original']
    assert repo.get_scene(scene.id).title == 'Сцена'


def test_full_edition_edits_a_series_book(tmp_path):
    client, repo, story, scene = series_book(tmp_path)
    response = client.patch(f'/api/scenes/{scene.id}', json={'story_id': story.id, 'title': 'Інша', 'expected_revision': scene.revision})
    assert response.status_code == 200, response.text


def test_mcp_get_story_reports_the_series(tmp_path):
    from storygen.mcp.bridge import story_series
    client, repo, story, scene = series_book(tmp_path)
    data = client.get(f'/api/stories/{story.id}').json()
    assert story_series(data) == {'title': 'Сага', 'number': 1, 'start': None, 'status': 'first',
                                  'prequel': False, 'resolved_count': 0}
    lone = repo.create_story(StoryCreate(title='Окрема'))
    assert story_series(client.get(f'/api/stories/{lone.id}').json()) is None
