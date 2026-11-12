"""MCP-BRIDGE package 4: publication from the chat through the real Obscura app (S26-S30)."""
import io
import os

import httpx
import pytest

pytest.importorskip('mcp')

from storygen.domain import SceneCreate, StoryCreate  # noqa: E402
from storygen.mcp.bridge import build_server  # noqa: E402
from storygen.publication.genres import genre_catalog  # noqa: E402

from tests.mcp.test_bridge import _recording_server, call, obscura, text  # noqa: E402

BASE = 'http://127.0.0.1:8765'


def ok(result):
    assert not result.is_error, text(result)
    return result.structured_content


def png_bytes(size=(60, 90)):
    from PIL import Image
    buffer = io.BytesIO()
    Image.new('RGB', size, (40, 60, 90)).save(buffer, 'PNG')
    return buffer.getvalue()


def written_story(app, http, scenes=1, prose=True):
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк'))
    for index in range(scenes):
        scene = repo.create_scene(story.id, SceneCreate(title=f'Сцена {index + 1}', beats='План.'))
        if prose:
            response = http.post(f'/api/scenes/{scene.id}/prose', json={'text': 'Анна піднялася сходами маяка.', 'expected_revision': repo.get_scene(scene.id).revision})
            assert response.status_code == 200, response.text
    return story


@pytest.mark.req('MCP-BRIDGE')
def test_get_publication_reads_card_signatures_and_genres(tmp_path):
    app, http = obscura(tmp_path)
    story = written_story(app, http)
    server = build_server(http)
    signature = ok(call(server, 'add_signature', {'display_name': 'А. Маяківна'}))
    data = ok(call(server, 'get_publication', {'story_id': story.id, 'genres_language': 'en'}))
    assert data['card']['revision'] == 0 and data['card']['title'] == '' and data['effective_title'] == 'Маяк'
    assert data['cover'] is None
    assert data['signatures'] == [{'id': signature['id'], 'display_name': 'А. Маяківна', 'revision': 0, 'archived': False}]
    assert data['genres'] == [{'code': code, 'label': label} for code, label in genre_catalog('en')]
    assert 'genres' not in ok(call(server, 'get_publication', {'story_id': story.id}))


@pytest.mark.req('MCP-BRIDGE')
def test_update_publication_changes_only_named_fields(tmp_path):
    app, http = obscura(tmp_path)
    story = written_story(app, http)
    server = build_server(http)
    first = ok(call(server, 'update_publication', {'story_id': story.id, 'expected_revision': 0, 'fields': {'annotation': 'Про маяк.', 'keywords': ['маяк']}}))
    second = ok(call(server, 'update_publication', {'story_id': story.id, 'expected_revision': first['revision'], 'fields': {'publisher': 'Видавництво'}}))
    card = second['card']
    assert (card['annotation'], card['keywords'], card['publisher'], second['revision']) == ('Про маяк.', ['маяк'], 'Видавництво', 2)


@pytest.mark.req('MCP-BRIDGE')
def test_stale_revision_is_refused_without_put(tmp_path):
    app, http = obscura(tmp_path)
    story = written_story(app, http)
    server = build_server(http)
    ok(call(server, 'update_publication', {'story_id': story.id, 'expected_revision': 0, 'fields': {'annotation': 'Автор.'}}))
    puts = []
    original = http.request

    def spy(method, url, **kwargs):
        if method == 'PUT':
            puts.append(url)
        return original(method, url, **kwargs)
    http.request = spy
    result = call(server, 'update_publication', {'story_id': story.id, 'expected_revision': 0, 'fields': {'annotation': 'Чат.'}})
    assert result.is_error and '409' in text(result) and 'get_publication' in text(result)
    assert puts == [] and http.get(f'/api/stories/{story.id}/publication').json()['card']['annotation'] == 'Автор.'


@pytest.mark.req('MCP-BRIDGE')
@pytest.mark.parametrize('fields', [{}, {'story_id': 'x'}, {'revision': 5}, {'colour': 'red'}])
def test_unknown_or_empty_fields_are_refused_without_request(fields):
    seen = []
    result = call(_recording_server(seen), 'update_publication', {'story_id': 'S1', 'expected_revision': 0, 'fields': fields})
    assert result.is_error and seen == []


@pytest.mark.req('MCP-BRIDGE')
def test_fb2_needs_author_and_genre(tmp_path):
    app, http = obscura(tmp_path)
    story = written_story(app, http)
    server = build_server(http)
    author = ok(call(server, 'add_signature', {'display_name': 'А. Маяківна'}))
    revision = ok(call(server, 'update_publication', {'story_id': story.id, 'expected_revision': 0, 'fields': {'author_ids': [author['id']]}}))['revision']
    no_genre = call(server, 'export_book', {'story_id': story.id, 'format': 'fb2'})
    assert no_genre.is_error and 'жанр' in text(no_genre)
    bad = call(server, 'update_publication', {'story_id': story.id, 'expected_revision': revision, 'fields': {'genres': ['no_such_genre']}})
    assert bad.is_error and 'genres_language' in text(bad)
    ok(call(server, 'update_publication', {'story_id': story.id, 'expected_revision': revision, 'fields': {'genres': ['prose_classic']}}))
    data = ok(call(server, 'export_book', {'story_id': story.id, 'format': 'fb2'}))
    assert data['download_url'].startswith(f'{BASE}/api/stories/{story.id}/exports/') and data['download_url'].endswith('.fb2')
    assert data['complete'] is True and data['word_count'] == 4 and data['format'] == 'fb2'
    assert http.get(data['download_url'].removeprefix(BASE)).status_code == 200


@pytest.mark.req('MCP-BRIDGE')
def test_export_of_unfinished_story_needs_permission(tmp_path):
    app, http = obscura(tmp_path)
    story = written_story(app, http, scenes=1, prose=False)
    server = build_server(http)
    refused = call(server, 'export_book', {'story_id': story.id, 'format': 'epub'})
    assert refused.is_error and '400' in text(refused)
    data = ok(call(server, 'export_book', {'story_id': story.id, 'format': 'epub', 'allow_incomplete': True}))
    assert data['complete'] is False and data['warnings']


@pytest.mark.req('MCP-BRIDGE')
def test_export_format_is_checked_before_request():
    seen = []
    result = call(_recording_server(seen), 'export_book', {'story_id': 'S1', 'format': 'docx'})
    assert result.is_error and seen == []


@pytest.mark.req('MCP-BRIDGE')
def test_cover_from_a_local_png_and_bound_through_the_card(tmp_path):
    app, http = obscura(tmp_path)
    story = written_story(app, http)
    cover = tmp_path / 'Cover.PNG'
    cover.write_bytes(png_bytes())
    server = build_server(http)
    data = ok(call(server, 'upload_cover', {'story_id': story.id, 'file_path': str(cover.resolve())}))
    assert set(data) == {'cover_id', 'width', 'height', 'mime_type'} and (data['width'], data['height'], data['mime_type']) == (60, 90, 'image/png')
    card = ok(call(server, 'update_publication', {'story_id': story.id, 'expected_revision': 0, 'fields': {'cover_id': data['cover_id']}}))
    assert card['card']['cover_id'] == data['cover_id']
    read = ok(call(server, 'get_publication', {'story_id': story.id}))
    assert read['cover'] == {'id': data['cover_id'], 'width': 60, 'height': 90, 'mime_type': 'image/png'}
    assert 'relative_path' not in text(call(server, 'get_publication', {'story_id': story.id}))


@pytest.mark.req('MCP-BRIDGE')
@pytest.mark.parametrize('path', [r'\\host\share\cover.png', '//host/share/cover.png', r'\\?\C:\cover.png', r'\\.\pipe\cover.png'])
def test_network_and_device_paths_are_refused_before_touching_files(path, monkeypatch):
    import storygen.mcp.bridge as bridge

    def touched(*args, **kwargs):
        raise AssertionError('the file system was touched')
    monkeypatch.setattr(bridge.os.path, 'realpath', touched)
    monkeypatch.setattr(bridge.os, 'stat', touched)
    seen = []
    result = call(_recording_server(seen), 'upload_cover', {'story_id': 'S1', 'file_path': path})
    assert result.is_error and 'мережев' in text(result) and seen == []


@pytest.mark.req('MCP-BRIDGE')
def test_bad_cover_files_are_refused(tmp_path):
    seen = []
    server = _recording_server(seen)
    gif = tmp_path / 'cover.gif'
    gif.write_bytes(b'GIF89a')
    huge = tmp_path / 'huge.png'
    with huge.open('wb') as handle:
        handle.truncate(10 * 1024 * 1024 + 1)
    for path in ['cover.png', str(gif.resolve()), str(huge.resolve()), str((tmp_path / 'missing.png').resolve()), str(tmp_path.resolve())]:
        result = call(server, 'upload_cover', {'story_id': 'S1', 'file_path': path})
        assert result.is_error, path
    assert seen == []


@pytest.mark.req('MCP-BRIDGE')
def test_not_an_image_is_refused_by_obscura(tmp_path):
    app, http = obscura(tmp_path)
    story = written_story(app, http)
    fake = tmp_path / 'fake.png'
    fake.write_bytes(b'not an image')
    result = call(build_server(http), 'upload_cover', {'story_id': story.id, 'file_path': str(fake.resolve())})
    assert result.is_error and '400' in text(result)


@pytest.mark.req('MCP-BRIDGE')
@pytest.mark.parametrize('tool,arguments', [
    ('get_publication', {'story_id': '..'}),
    ('update_publication', {'story_id': 'S1', 'expected_revision': 0, 'fields': {'author_ids': ['../x']}}),
    ('update_publication', {'story_id': 'S1', 'expected_revision': 0, 'fields': {'cover_id': 'a/b'}}),
    ('upload_cover', {'story_id': 'a?b', 'file_path': 'C:/x.png'}),
    ('export_book', {'story_id': '../trash', 'format': 'pdf'}),
])
def test_identifiers_are_checked_before_the_request(tool, arguments):
    seen = []
    result = call(_recording_server(seen), tool, arguments)
    assert result.is_error and seen == []
