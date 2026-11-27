"""R-47 (LONG-PROSE-TRIAL-S07): what the Obscura window needs to offer the trial and to work inside it."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from storygen import build_edition
from storygen.book import guard
from storygen.domain import StoryCreate
from storygen.storage import long_prose_trial as trials
from storygen.storage import series as store
from tests.web.test_long_prose_guard import setup
from tests.web.test_long_prose_trial_api import structured_book

ROOT = Path(__file__).resolve().parents[2]
REFUSALS = {'used': 'TRIAL_USED', 'series_full': 'TRIAL_SERIES_FULL', 'in_series': 'TRIAL_IN_SERIES',
            'confirm': 'TRIAL_CONFIRM', 'not_needed': 'TRIAL_NOT_NEEDED', 'book_alone': 'TRIAL_BOOK_ALONE',
            'bible_used': 'TRIAL_BIBLE_USED'}


def _store(monkeypatch):
    edition = build_edition.BuildEdition(edition='store', report_url='https://example.test/report')
    monkeypatch.setattr(build_edition, 'current', lambda: edition)


def _no_trial_reads(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError('an edition with long prose must not read the trial')
    for name in ('trial', 'trial_state', 'read_trial'):
        monkeypatch.setattr(trials, name, fail)


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_story_view_long_prose_full_reads_no_trial(tmp_path, monkeypatch):
    client, app, repo, story, scene = setup(tmp_path)
    _no_trial_reads(monkeypatch)
    response = client.get(f'/api/stories/{story.id}')
    assert response.status_code == 200 and response.json()['long_prose'] is True
    page = client.get('/')
    assert page.status_code == 200 and 'href="/series"' in page.text


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_story_view_long_prose_store(tmp_path, store_edition):
    client, app, repo, story, scene = setup(tmp_path, structured=False)
    other = structured_book(repo, 'Інша')
    assert client.get(f'/api/stories/{story.id}').json()['long_prose'] is False
    assert client.post('/api/long-prose-trial', json={'story_id': story.id, 'confirm': True}).status_code == 200
    assert client.get(f'/api/stories/{story.id}').json()['long_prose'] is True
    assert client.get(f'/api/stories/{other.id}').json()['long_prose'] is False


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_library_template_store_states(tmp_path, monkeypatch):
    client, app, repo, story, scene = setup(tmp_path, structured=False)
    other = store.create_series(repo, 'Чужа')
    store.create_book(repo, other.id, 'Чужа книга')
    _store(monkeypatch)
    free = client.get('/').text
    assert 'href="/series"' in free and 'id="manuscript-import-series-row"' in free
    assert f'href="/series/{other.id}"' not in free  # another edition's series opens nowhere here
    saga = store.create_series(repo, 'Сага', trial=True)
    store.create_book(repo, saga.id, 'Перша')
    on_series = client.get('/').text
    assert 'href="/series"' in on_series and f'href="/series/{saga.id}"' in on_series
    assert f'href="/series/{other.id}"' not in on_series


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_library_template_store_trial_on_a_book(tmp_path, store_edition):
    client, app, repo, story, scene = setup(tmp_path, structured=False)
    assert client.post('/api/long-prose-trial', json={'story_id': story.id, 'confirm': True}).status_code == 200
    page = client.get('/').text
    assert 'href="/series"' not in page and 'id="manuscript-import-series-row"' not in page


def test_trial_refusals_are_translated():
    from storygen.web.localization import diagnostic, translate
    for suffix, name in REFUSALS.items():
        text = getattr(guard, name)
        assert translate(f'trial.refusal.{suffix}', 'uk') == text
        english = diagnostic(text, 'en')
        assert english != text and not re.search('[а-яіїєґ]', english, re.I), (name, english)


def test_trial_ui_texts_exist_in_both_languages():
    from storygen.web.localization import translate
    assert translate('trial.used', 'uk', p0='Маяк') == 'Пробу використано на «Маяк»'
    assert translate('trial.used', 'en', p0='Lighthouse') == 'The trial is used on “Lighthouse”'
    for key in ('offer_book', 'offer_series', 'create_series', 'confirm', 'used_untitled', 'import_checkbox',
                'import_hint', 'leave_warning', 'series_list_hint'):
        assert translate(f'trial.{key}', 'uk') != f'trial.{key}' and translate(f'trial.{key}', 'en') != translate(f'trial.{key}', 'uk')


def test_trial_module_helpers():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node потрібен для перевірки ES module')
    result = subprocess.run([node, str(ROOT / 'tests/web/js/long_prose_trial.mjs'), str(ROOT)],
                            capture_output=True, encoding='utf-8', errors='replace', timeout=15)
    assert result.returncode == 0, result.stderr


def test_fixture_server_resets_the_trial():
    text = (ROOT / 'tests/web/browser/server.py').read_text(encoding='utf-8')
    assert "@app.post('/test-reset-trial')" in text


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_series_index_store_states(tmp_path, store_edition):
    client, app, repo, story, scene = setup(tmp_path, structured=False)
    page = client.get('/series')
    assert page.status_code == 200 and 'id="series-create"' in page.text and '/static/series-page.js' in page.text
    saga = client.post('/api/series', json={'title': 'Сага', 'trial': True}).json()
    assert client.get('/series').status_code == 200 and client.get(f"/series/{saga['id']}").status_code == 200


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_series_index_is_gone_with_a_book_trial(tmp_path, store_edition):
    client, app, repo, story, scene = setup(tmp_path, structured=False)
    assert client.post('/api/long-prose-trial', json={'story_id': story.id, 'confirm': True}).status_code == 200
    assert client.get('/series').status_code == 404
