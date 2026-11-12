"""MCP-BRIDGE package 4: the FB2 genre catalogue route and the publication page noticing outside changes."""
import shutil
import subprocess
from pathlib import Path

import pytest

from storygen.publication.genres import genre_catalog

from tests.web.test_scene_text import client_for, plain_scene


@pytest.mark.req('MCP-BRIDGE')
@pytest.mark.parametrize('language', ['uk', 'en'])
def test_genres_route_matches_the_catalogue(tmp_path, language):
    app, *_ = plain_scene(tmp_path)
    with client_for(app) as client:
        response = client.get('/api/publication/genres', params={'language': language})
    assert response.status_code == 200, response.text
    assert response.json() == {'genres': [{'code': code, 'label': label} for code, label in genre_catalog(language)]}


@pytest.mark.req('MCP-BRIDGE')
def test_genres_route_refuses_unknown_language(tmp_path):
    app, *_ = plain_scene(tmp_path)
    with client_for(app) as client:
        assert client.get('/api/publication/genres', params={'language': 'de'}).status_code == 422


@pytest.mark.req('MCP-BRIDGE')
def test_publication_page_decides_on_outside_changes():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node потрібен для перевірки ES module')
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([node, str(root / 'tests/web/js/publication_sync.mjs')], capture_output=True, encoding='utf-8', errors='replace', timeout=15)
    assert result.returncode == 0, result.stderr
