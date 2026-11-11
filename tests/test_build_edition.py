import json

import pytest

from storygen import build_edition
from storygen.build_edition import BuildEdition, load_build_edition
from storygen.domain import ContentRating

REPORT = 'https://example.test/report'


def write(tmp_path, data):
    path = tmp_path / 'build_edition.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    return path


def test_no_marker_file_is_full_edition(tmp_path):
    loaded = load_build_edition(tmp_path / 'absent.json')
    assert loaded == BuildEdition() and loaded.edition == 'full'
    assert loaded.max_rating == ContentRating(sexual=2, violence=2, themes=2)


def test_repository_ships_without_marker():
    assert build_edition.current().edition == 'full'


def test_store_edition_caps_only_sexual(tmp_path):
    loaded = load_build_edition(write(tmp_path, {'edition': 'store', 'report_url': REPORT, 'support_url': 'https://example.test/s'}))
    assert loaded.max_rating == ContentRating(sexual=1, violence=2, themes=2)
    assert (loaded.support_url, loaded.waitlist_url) == ('https://example.test/s', '')


def test_store_edition_requires_report_url(tmp_path):
    with pytest.raises(ValueError, match='report_url'):
        load_build_edition(write(tmp_path, {'edition': 'store'}))


@pytest.mark.parametrize('data', [
    {'edition': 'pro'},
    {'edition': 'store', 'report_url': REPORT, 'extra': 1},
    {'edition': 'store', 'report_url': 'javascript:alert(1)'},
    {'edition': 'full', 'support_url': 'http://example.test'},
    [],
])
def test_invalid_marker_is_rejected_not_ignored(tmp_path, data):
    with pytest.raises(ValueError, match='build_edition.json') as error:
        load_build_edition(write(tmp_path, data))
    # The message never echoes the file's content.
    assert 'javascript' not in str(error.value) and 'example.test' not in str(error.value)


def test_broken_json_is_rejected(tmp_path):
    path = tmp_path / 'build_edition.json'
    path.write_text('{', encoding='utf-8')
    with pytest.raises(ValueError, match='build_edition.json'):
        load_build_edition(path)


def test_over_limit_lists_axes(store_edition):
    assert build_edition.over_limit(ContentRating(sexual=2, violence=2, themes=2)) == ['sexual']
    assert build_edition.over_limit(ContentRating(sexual=1, violence=2, themes=2)) == []


def test_marker_that_is_not_a_file_is_rejected(tmp_path):
    # A present but unreadable marker must not silently become the full edition.
    path = tmp_path / 'build_edition.json'
    path.mkdir()
    with pytest.raises(ValueError, match='build_edition.json'):
        load_build_edition(path)


@pytest.mark.parametrize('url', ['https://', 'https:// example.test', 'https://example.test/a b', 'https://exa\nmple.test',
    'HTTPS://example.test/x y', 'https://example.test/\x07'])
def test_link_must_be_a_clean_https_url(tmp_path, url):
    with pytest.raises(ValueError, match='build_edition.json'):
        load_build_edition(write(tmp_path, {'edition': 'store', 'report_url': url}))


def test_clean_https_url_with_path_and_query_is_kept(tmp_path):
    url = 'https://example.test/form?src=obscura#top'
    assert load_build_edition(write(tmp_path, {'edition': 'store', 'report_url': url})).report_url == url
