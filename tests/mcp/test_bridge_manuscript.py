"""R-48 PR 2 (design §6): `import_manuscript` and `start_run(action='rebuild_memory')` through the real Obscura app.
No provider calls: the worker is not started (the test client is not a context manager)."""
import base64
import os

import anyio
import pytest

pytest.importorskip('mcp')

from fastapi.testclient import TestClient  # noqa: E402
from mcp import Client  # noqa: E402

from storygen.application.settings import AppSettings  # noqa: E402
from storygen.mcp import bridge as bridge_module  # noqa: E402
from storygen.mcp.bridge import BRIDGE_HEADERS, MEMORY_CHAT_PATH, MEMORY_FINGERPRINT, MEMORY_PLAN_STALE, TOOLS, build_server  # noqa: E402
from storygen.web.app import create_app  # noqa: E402

from tests.generation.test_memory_build import give_memory, with_cards, written_book  # noqa: E402
from tests.mcp.test_bridge import call, text  # noqa: E402
from tests.mcp.test_bridge_settings import ok  # noqa: E402

BOOK = '\n\n'.join(['# Книга', '## Глава перша', 'Текст першої глави. ' * 5, '## Глава друга', 'Текст другої глави. ' * 5])


def bridge(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))
    http = TestClient(app, base_url='http://127.0.0.1:8765')
    http.headers.update(BRIDGE_HEADERS)
    return app, http, build_server(http)


def author_mode(app, story, mode):
    """The writing mode is the author's: the bridge client may not change it, so a client without the bridge header does."""
    revision = app.state.repo.get_story(story.id).revision
    response = TestClient(app, base_url='http://127.0.0.1:8765').put(
        f'/api/stories/{story.id}/writing-mode', json={'writing_mode': mode, 'expected_revision': revision})
    assert response.status_code == 200, response.text


def manuscript(tmp_path, name='book.md', content=BOOK):
    path = tmp_path / 'files' / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(content, encoding='utf-8')
    return str(path)


def preview(server, **arguments):
    return ok(call(server, 'import_manuscript', arguments))


def test_import_manuscript_preview_from_path(tmp_path):
    app, http, server = bridge(tmp_path / 'data')
    data = preview(server, file_path=manuscript(tmp_path))
    assert set(data) == {'import_id', 'fingerprint', 'file_name', 'title_suggestion', 'chapter_source', 'scenes', 'parts', 'warnings',
                         'tracked_changes', 'edition'}
    assert data['file_name'] == 'book.md' and data['edition'] == {'parts_allowed': True, 'series_allowed': True}
    assert [scene['title'] for scene in data['scenes']] == ['Глава перша', 'Глава друга']
    assert set(data['scenes'][0]) == {'start', 'end', 'title', 'words', 'part_index', 'proposed', 'warnings'}
    assert app.state.repo.list_stories() == []


def test_import_manuscript_preview_from_base64(tmp_path):
    app, http, server = bridge(tmp_path / 'data')
    content = base64.b64encode(BOOK.encode('utf-8')).decode()
    data = preview(server, file_name='rukopys.md', content_base64=content, language='en')
    assert data['file_name'] == 'rukopys.md' and len(data['scenes']) == 2
    again = preview(server, import_id=data['import_id'], chapter_markers=['Розділ'])
    assert again['import_id'] == data['import_id'] and again['fingerprint'] != data['fingerprint']


def test_import_manuscript_confirm_creates_book_with_proposed_scenes(tmp_path):
    app, http, server = bridge(tmp_path / 'data')
    data = preview(server, file_path=manuscript(tmp_path))
    created = ok(call(server, 'import_manuscript', {'confirm': True, 'import_id': data['import_id'], 'fingerprint': data['fingerprint'],
                                                     'title': 'Моя книга',
                                                     'content_rating': {'sexual': 0, 'violence': 1, 'themes': 0}}))
    assert len(created['scene_ids']) == 2 and 'rebuild_memory' in created['next_steps']
    assert created['next_steps'].count(created['story_id']) == 1
    repo = app.state.repo
    assert repo.get_story(created['story_id']).title == 'Моя книга'
    assert [scene.title for scene in repo.list_scenes(created['story_id'])] == ['Глава перша', 'Глава друга']
    # The import is spent: a second confirm of the same preview is refused with the hint to preview again.
    again = call(server, 'import_manuscript', {'confirm': True, 'import_id': data['import_id'], 'fingerprint': data['fingerprint'], 'title': 'Ще'})
    assert again.is_error and 'ще раз' in text(again)


def test_import_manuscript_custom_boundaries(tmp_path):
    app, http, server = bridge(tmp_path / 'data')
    data = preview(server, file_path=manuscript(tmp_path))
    first = data['scenes'][0]['start']
    created = ok(call(server, 'import_manuscript', {
        'confirm': True, 'import_id': data['import_id'], 'fingerprint': data['fingerprint'], 'title': 'Одна сцена',
        'scenes': [{'start': first, 'title': 'Усе разом'}]}))
    assert len(created['scene_ids']) == 1
    assert [scene.title for scene in app.state.repo.list_scenes(created['story_id'])] == ['Усе разом']


def test_import_manuscript_confirm_needs_the_previewed_values(tmp_path):
    app, http, server = bridge(tmp_path / 'data')
    result = call(server, 'import_manuscript', {'confirm': True, 'import_id': 'a' * 32})
    assert result.is_error and 'fingerprint' in text(result)
    stale = call(server, 'import_manuscript', {'confirm': True, 'import_id': 'a' * 32, 'fingerprint': 'x', 'title': 'T'})
    assert stale.is_error and 'без confirm' in text(stale)
    assert app.state.repo.list_stories() == []


def _directory(tmp_path):
    folder = tmp_path / 'files' / 'folder.md'
    folder.mkdir(parents=True)
    return {'file_path': str(folder)}


def _symlink(tmp_path):
    target = manuscript(tmp_path)
    link = tmp_path / 'files' / 'link.md'
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        pytest.skip('symbolic links are not available')
    return {'file_path': str(link)}


def _extension(tmp_path):
    return {'file_path': manuscript(tmp_path, 'book.pdf')}


def _huge(tmp_path):
    path = tmp_path / 'files' / 'huge.txt'
    path.parent.mkdir(exist_ok=True)
    with open(path, 'wb') as handle:
        handle.truncate(20 * 1024 * 1024 + 1)  # a sparse file: nothing near 20 MiB is held in memory
    return {'file_path': str(path)}


def _missing(tmp_path):
    return {'file_path': str(tmp_path / 'files' / 'none.md')}


def _both(tmp_path):
    return {'file_path': manuscript(tmp_path), 'content_base64': base64.b64encode(b'x').decode(), 'file_name': 'a.md'}


def _base64_extension(tmp_path):
    return {'file_name': 'a.exe', 'content_base64': base64.b64encode(b'x').decode()}


@pytest.mark.parametrize('make, expected', [(_directory, 'звичайним файлом'), (_symlink, 'посиланням'), (_extension, '.docx, .md або .txt'),
                                            (_huge, '20 MiB'), (_missing, 'не знайдено'), (_both, 'не обидва'),
                                            (_base64_extension, '.docx, .md або .txt')])
def test_import_manuscript_rejects_directory_symlink_extension_and_size(tmp_path, monkeypatch, make, expected):
    opened = []
    real_open = open
    monkeypatch.setattr(bridge_module, 'open', lambda *a, **k: opened.append(a) or real_open(*a, **k), raising=False)
    app, http, server = bridge(tmp_path / 'data')
    result = call(server, 'import_manuscript', make(tmp_path))
    assert result.is_error and expected in text(result)
    assert opened == []  # refused before the file was read
    assert not (tmp_path / 'data' / 'manuscript-import').exists() or not list((tmp_path / 'data' / 'manuscript-import').iterdir())


def test_import_manuscript_rejects_base64_over_2_mib(tmp_path):
    app, http, server = bridge(tmp_path / 'data')
    content = base64.b64encode(b'a' * (2 * 1024 * 1024)).decode()  # about 2.67 MiB of base64
    result = call(server, 'import_manuscript', {'file_name': 'big.txt', 'content_base64': content})
    assert result.is_error and '2 MiB' in text(result)


def obscura_book(tmp_path, texts, mode='obscura', names=()):
    repo, story, scenes = written_book(tmp_path, texts)
    if names:
        story = with_cards(repo, story, *names)
    app, http, server = bridge(tmp_path)
    if mode != story.writing_mode:
        author_mode(app, story, mode)
    return app, http, server, story, scenes


def test_rebuild_memory_preview_has_cost_and_fingerprint(tmp_path):
    repo, story, scenes = written_book(tmp_path, ['Перша.', 'Друга.', 'Третя.'])
    app, http, server = bridge(tmp_path)
    author_mode(app, story, 'obscura')
    data = ok(call(server, 'start_run', {'story_id': story.id, 'action': 'rebuild_memory'}))
    assert data['started'] is False
    shown = data['preview']
    assert shown['ready'] is True, shown['reason']
    assert shown['scene_id'] == scenes[0].id and shown['scenes_count'] == 3 and shown['calls'] == 3
    assert shown['cost']['calls'] == 3 and isinstance(shown['unfit_scenes'], list) and len(shown['plan_fingerprint']) == 64
    assert {'series_refresh', 'cast', 'budget'} <= set(shown)
    assert app.state.coordinator.list_runs() == []


def test_rebuild_memory_confirm_requires_fingerprint(tmp_path):
    app, http, server, story, scenes = obscura_book(tmp_path, ['Перша.', 'Друга.'])
    refused = call(server, 'start_run', {'story_id': story.id, 'action': 'rebuild_memory', 'confirm': True})
    assert refused.is_error and MEMORY_FINGERPRINT in text(refused)
    stale = call(server, 'start_run', {'story_id': story.id, 'action': 'rebuild_memory', 'confirm': True, 'plan_fingerprint': 'a' * 64})
    assert stale.is_error and MEMORY_PLAN_STALE in text(stale)
    assert app.state.coordinator.list_runs() == []


def test_rebuild_memory_confirm_starts_run(tmp_path):
    app, http, server, story, scenes = obscura_book(tmp_path, ['Оля побачила Марка.', 'Тиша.'], names=('Марко', 'Оля'))
    assert app.state.repo.get_scene(scenes[0].id).character_ids == []
    shown = ok(call(server, 'start_run', {'story_id': story.id, 'action': 'rebuild_memory'}))['preview']
    assert shown['cast']['scenes_to_fill'] == 1
    data = ok(call(server, 'start_run', {'story_id': story.id, 'action': 'rebuild_memory', 'confirm': True,
                                         'plan_fingerprint': shown['plan_fingerprint'], 'budget_limit_usd': '0.50'}))
    assert data['started'] is True and data['state'] == 'queued'
    run = app.state.coordinator.get_run(data['run_id'])
    assert run.origin == 'mcp' and run.request.mode == 'rebuild_memory' and run.request.scene_id == scenes[0].id
    assert run.request.memory_plan_fingerprint == shown['plan_fingerprint'] and run.request.budget_limit_usd == '0.50'
    assert app.state.repo.get_scene(scenes[0].id).character_ids  # the cast was filled in before the run
    assert ok(call(server, 'get_run', {'run_id': run.id}))['action'] == 'rebuild_memory'


def test_rebuild_memory_stale_fingerprint_changes_nothing(tmp_path):
    app, http, server, story, scenes = obscura_book(tmp_path, ['Оля побачила Марка.', 'Тиша.'], names=('Марко', 'Оля'))
    shown = ok(call(server, 'start_run', {'story_id': story.id, 'action': 'rebuild_memory'}))['preview']
    stale = 'b' * 64 if shown['plan_fingerprint'][0] != 'b' else 'c' * 64
    refused = call(server, 'start_run', {'story_id': story.id, 'action': 'rebuild_memory', 'confirm': True, 'plan_fingerprint': stale})
    assert refused.is_error and MEMORY_PLAN_STALE in text(refused)
    assert app.state.repo.get_scene(scenes[0].id).character_ids == [] and app.state.coordinator.list_runs() == []


def test_rebuild_memory_in_a_chat_story_names_the_chat_path(tmp_path):
    app, http, server, story, scenes = obscura_book(tmp_path, ['Перша.'], mode='chat')
    refused = call(server, 'start_run', {'story_id': story.id, 'action': 'rebuild_memory'})
    assert refused.is_error and MEMORY_CHAT_PATH in text(refused) and 'get_stage_task' in text(refused)


def test_rebuild_memory_with_nothing_to_build(tmp_path):
    repo, story, scenes = written_book(tmp_path, ['Перша.'])
    give_memory(repo, story, scenes[0])
    app, http, server = bridge(tmp_path)
    author_mode(app, story, 'obscura')
    refused = call(server, 'start_run', {'story_id': story.id, 'action': 'rebuild_memory'})
    assert refused.is_error and 'будувати нічого' in text(refused)


def test_tools_list_includes_import_manuscript(tmp_path):
    app, http, server = bridge(tmp_path)

    async def run():
        async with Client(server) as client:
            return {tool.name: tool for tool in (await client.list_tools()).tools}
    tools = anyio.run(run)
    assert 'import_manuscript' in TOOLS and 'import_manuscript' in tools
    assert {'file_path', 'content_base64', 'confirm', 'fingerprint', 'scenes'} <= set(tools['import_manuscript'].input_schema['properties'])


# --- fix round 1: language, file-check branches, restart, stale mapping ---

def test_confirm_uses_the_language_of_the_preview(tmp_path):
    app, http, server = bridge(tmp_path / 'data')
    data = preview(server, file_path=manuscript(tmp_path), language='en')
    created = ok(call(server, 'import_manuscript', {'confirm': True, 'import_id': data['import_id'], 'fingerprint': data['fingerprint'],
                                                     'title': 'English book'}))
    assert app.state.repo.get_story(created['story_id']).language == 'en'


def test_confirm_refuses_another_language_than_the_preview(tmp_path):
    app, http, server = bridge(tmp_path / 'data')
    data = preview(server, file_path=manuscript(tmp_path), language='en')
    refused = call(server, 'import_manuscript', {'confirm': True, 'import_id': data['import_id'], 'fingerprint': data['fingerprint'],
                                                  'title': 'T', 'language': 'uk'})
    assert refused.is_error and 'мови перегляду' in text(refused) and app.state.repo.list_stories() == []


def fake_lstat(monkeypatch, target, mode, attributes=0):
    real = os.lstat

    def lstat(path, *a, **k):
        info = real(path, *a, **k)
        if str(path) != target:
            return info
        return type('Info', (), {'st_mode': mode, 'st_size': info.st_size, 'st_ino': info.st_ino, 'st_dev': info.st_dev,
                                 'st_file_attributes': attributes})()
    monkeypatch.setattr(bridge_module.os, 'lstat', lstat)


def test_symlink_and_reparse_point_are_refused_without_privileges(tmp_path, monkeypatch):
    import stat as st
    app, http, server = bridge(tmp_path / 'data')
    path = manuscript(tmp_path)
    fake_lstat(monkeypatch, path, st.S_IFLNK | 0o777)
    result = call(server, 'import_manuscript', {'file_path': path})
    assert result.is_error and 'посиланням' in text(result)
    fake_lstat(monkeypatch, path, st.S_IFREG | 0o644, 0x400)
    result = call(server, 'import_manuscript', {'file_path': path})
    assert result.is_error and 'посиланням' in text(result)


def test_a_link_in_the_parent_path_is_refused(tmp_path, monkeypatch):
    app, http, server = bridge(tmp_path / 'data')
    path = manuscript(tmp_path)
    monkeypatch.setattr(bridge_module.os.path, 'realpath', lambda value: str(value) + '-elsewhere')
    result = call(server, 'import_manuscript', {'file_path': path})
    assert result.is_error and 'проходить через посилання' in text(result)


def test_network_paths_are_refused(tmp_path):
    app, http, server = bridge(tmp_path / 'data')
    for path in ('\\\\server\\share\\book.md', '//server/share/book.md'):
        result = call(server, 'import_manuscript', {'file_path': path})
        assert result.is_error and 'локальному диску' in text(result)


def test_file_swapped_between_check_and_read_is_refused(tmp_path, monkeypatch):
    app, http, server = bridge(tmp_path / 'data')
    path = manuscript(tmp_path)
    real = os.fstat

    def fstat(fd):
        info = real(fd)
        return type('Info', (), {'st_mode': info.st_mode, 'st_ino': info.st_ino + 1, 'st_dev': info.st_dev})()
    monkeypatch.setattr(bridge_module.os, 'fstat', fstat)
    result = call(server, 'import_manuscript', {'file_path': path})
    assert result.is_error and 'змінився' in text(result)


def test_confirm_without_scenes_after_a_re_preview_refuses_the_old_fingerprint(tmp_path):
    app, http, server = bridge(tmp_path / 'data')
    first = preview(server, file_path=manuscript(tmp_path))
    second = preview(server, import_id=first['import_id'], chapter_markers=['Розділ'])
    assert second['fingerprint'] != first['fingerprint']
    refused = call(server, 'import_manuscript', {'confirm': True, 'import_id': first['import_id'], 'fingerprint': first['fingerprint'],
                                                  'title': 'T'})
    assert refused.is_error and 'без confirm' in text(refused) and app.state.repo.list_stories() == []


def test_confirm_without_scenes_after_a_bridge_restart_is_refused(tmp_path):
    app, http, server = bridge(tmp_path / 'data')
    data = preview(server, file_path=manuscript(tmp_path))
    restarted = build_server(http)
    refused = call(restarted, 'import_manuscript', {'confirm': True, 'import_id': data['import_id'], 'fingerprint': data['fingerprint'],
                                                    'title': 'T'})
    assert refused.is_error and 'без confirm' in text(refused) and app.state.repo.list_stories() == []


def test_rebuild_memory_with_an_explicit_scene_id(tmp_path):
    app, http, server, story, scenes = obscura_book(tmp_path, ['Перша.', 'Друга.', 'Третя.'])
    shown = ok(call(server, 'start_run', {'story_id': story.id, 'action': 'rebuild_memory', 'scene_id': scenes[0].id}))['preview']
    assert shown['scene_id'] == scenes[0].id and shown['calls'] == 3
    other = ok(call(server, 'start_run', {'story_id': story.id, 'action': 'rebuild_memory', 'scene_id': scenes[2].id}))['preview']
    assert other['scene_id'] == scenes[2].id and other['calls'] == 1 and other['scenes_count'] is None


def test_enqueue_conflict_asks_for_a_new_preview(tmp_path, monkeypatch):
    from storygen.domain import RevisionConflict
    from storygen.generation.memory_build import MEMORY_PLAN_CHANGED
    app, http, server, story, scenes = obscura_book(tmp_path, ['Перша.', 'Друга.'])
    shown = ok(call(server, 'start_run', {'story_id': story.id, 'action': 'rebuild_memory'}))['preview']

    def refuse(*args, **kwargs):
        raise RevisionConflict(MEMORY_PLAN_CHANGED)
    monkeypatch.setattr(app.state.coordinator, 'enqueue', refuse)
    result = call(server, 'start_run', {'story_id': story.id, 'action': 'rebuild_memory', 'confirm': True,
                                        'plan_fingerprint': shown['plan_fingerprint']})
    assert result.is_error and MEMORY_PLAN_STALE in text(result)
