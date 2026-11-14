"""SERIES-S11 (server part): the sources in the status, the prequel in MCP get_story and the future in the writing context."""
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.book.series import series_status
from storygen.mcp.bridge import story_series
from storygen.web.app import create_app
from tests.series.test_series_decisions import setup as prequel_setup
from tests.series.test_series_prequel_merge import enter, series_with_prequel


def client_for(tmp_path):
    return TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765')


def test_status_lists_the_sources_of_a_book_after_prequel(tmp_path):
    repo, item, first, prequel, third, cloth = series_with_prequel(tmp_path)
    third = enter(repo, third, item, 3, ('Рік 2', 1))
    status = series_status(repo, third)
    assert status.sources == [first.id, prequel.id] and len(status.resolved) == 1
    assert series_status(repo, repo.get_story(first.id)).sources == []


def test_get_story_shows_prequel_and_review_state(tmp_path):
    repo, item, first, scenes, prequel, scene = prequel_setup(tmp_path)
    with client_for(tmp_path) as client:
        series = story_series(client.get(f'/api/stories/{prequel.id}').json())
        first_series = story_series(client.get(f'/api/stories/{first.id}').json())
    assert (series['prequel'], series['status'], series['resolved_count']) == (True, 'fresh', 0)
    assert (first_series['prequel'], first_series['status']) == (False, 'first')


def test_scene_context_of_a_prequel_has_future(tmp_path):
    repo, item, first, scenes, prequel, scene = prequel_setup(tmp_path)
    with client_for(tmp_path) as client:
        context = client.get(f'/api/scenes/{scene.id}/writing-context').json()
    assert '- Анна: Халат' in context['future']


def test_settings_page_has_the_facts_review(tmp_path):
    repo, item, first, scenes, prequel, scene = prequel_setup(tmp_path)
    with client_for(tmp_path) as client:
        html = client.get(f'/stories/{prequel.id}/settings').text
    assert 'data-series-facts' in html and 'id="series-facts-dialog"' in html and '/static/series-facts.js' in html
