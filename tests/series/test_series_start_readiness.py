"""MANUSCRIPT-IMPORT §4.2: before an import into a series, the preview asks whether the previous book's memory is built,
so it can warn with a link to that book (read only, nothing is created). Neutral examples."""
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.storage import series as store
from storygen.web.app import create_app
from tests.series.helpers import book, finished_book, into_series


def client_for(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path / 'data', env_file=tmp_path / 'absent.env'))
    return TestClient(app, base_url='http://127.0.0.1'), app.state.repo


def test_readiness_names_the_previous_book_without_memory(tmp_path):
    client, repo = client_for(tmp_path)
    with client:
        item = store.create_series(repo, 'Маяки')
        first, _ = book(repo, 'Перший маяк', written=False)
        into_series(repo, first, item.id, 1)
        before = len(repo.list_stories())
        answer = client.get(f'/api/series/{item.id}/start-readiness', params={'number': 2})
        assert answer.status_code == 200
        assert answer.json() == {'state': 'no_summary', 'source_story_id': first.id, 'source_title': 'Перший маяк', 'source_number': 1}
        assert client.get(f'/api/series/{item.id}/start-readiness', params={'number': 1}).json()['state'] == 'first'
        assert len(repo.list_stories()) == before  # read only


def test_readiness_with_a_finished_previous_book(tmp_path):
    client, repo = client_for(tmp_path)
    with client:
        item = store.create_series(repo, 'Маяки')
        first, _, _ = finished_book(repo)
        into_series(repo, first, item.id, 1)
        data = client.get(f'/api/series/{item.id}/start-readiness', params={'number': 2}).json()
        assert data['state'] == 'source_finished' and data['source_story_id'] == first.id


def test_readiness_of_an_unknown_series_or_bad_number(tmp_path):
    client, repo = client_for(tmp_path)
    with client:
        assert client.get('/api/series/missing/start-readiness', params={'number': 2}).status_code == 404
        item = store.create_series(repo, 'Маяки')
        assert client.get(f'/api/series/{item.id}/start-readiness', params={'number': 0}).status_code in (400, 422)
