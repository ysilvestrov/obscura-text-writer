from fastapi.testclient import TestClient

from storygen import build_edition
from storygen.application.settings import AppSettings
from storygen.build_edition import BuildEdition
from storygen.web.app import create_app


def page(tmp_path, **headers):
    app = create_app(AppSettings(data_dir=tmp_path / 'data', env_file=tmp_path / 'absent.env'))
    response = TestClient(app, base_url='http://127.0.0.1').get('/', headers=headers)
    assert response.status_code == 200
    return response.text


def test_full_edition_has_no_app_links(tmp_path):
    html = page(tmp_path)
    assert 'app-links' not in html and 'app.link.' not in html


def test_store_edition_shows_report_link_only_when_others_are_empty(tmp_path, store_edition):
    html = page(tmp_path)
    assert html.count('class="app-link"') == 1
    assert 'href="https://example.test/report"' in html and 'data-i18n="app.link.report"' in html
    assert 'target="_blank"' in html and 'rel="noopener noreferrer"' in html
    assert 'Поскаржитися на результат' in html


def test_all_three_links_in_fixed_order(tmp_path, monkeypatch):
    edition = BuildEdition(edition='store', support_url='https://example.test/s', waitlist_url='https://example.test/w',
                           report_url='https://example.test/r')
    monkeypatch.setattr(build_edition, 'current', lambda: edition)
    html = page(tmp_path)
    assert html.count('class="app-link"') == 3
    assert html.index('app.link.support') < html.index('app.link.waitlist') < html.index('app.link.report')
    assert html.index('https://example.test/s') < html.index('https://example.test/w') < html.index('https://example.test/r')


def test_link_labels_are_translated(tmp_path, store_edition):
    assert 'Report a result' in page(tmp_path, **{'accept-language': 'en'})
