"""STORE-MCP-001 S05: edition refusals reach the chat as a hint about the paid version with the waitlist link."""
import anyio
import httpx
import pytest

pytest.importorskip('mcp')
from mcp import Client  # noqa: E402

from storygen.book.guard import NO_LONG_PROSE, READ_ONLY, READ_ONLY_SERIES, TRIAL_BOOK_ALONE, TRIAL_SERIES_FULL, TRIAL_USED  # noqa: E402
from storygen.domain import ContentRating  # noqa: E402
from storygen.mcp.bridge import build_server  # noqa: E402
from storygen.mcp.edition import TRIAL_AVAILABLE_TEXT, TRIAL_USED_TEXT, edition_refusal  # noqa: E402
from storygen.rating.guard import enforce_rating_limit  # noqa: E402

WAITLIST = 'https://example.com/waitlist'


def limit_text(store_edition) -> str:
    with pytest.raises(ValueError) as raised:
        enforce_rating_limit(ContentRating(sexual=2, violence=0, themes=0))
    return str(raised.value)


@pytest.mark.req('STORE-MCP-001')
@pytest.mark.parametrize('kind', ['no_long_prose', 'read_only', 'read_only_series', 'edition_limit'])
def test_edition_texts_become_a_paid_version_hint(kind, store_edition):
    detail = {'no_long_prose': NO_LONG_PROSE, 'read_only': READ_ONLY, 'read_only_series': READ_ONLY_SERIES,
              'edition_limit': limit_text(store_edition) if kind == 'edition_limit' else ''}[kind]
    hint = edition_refusal(detail, WAITLIST)
    assert hint is not None and detail in hint
    assert 'платної версії' in hint and 'paid version' in hint and WAITLIST in hint


@pytest.mark.req('STORE-MCP-001')
def test_empty_waitlist_has_no_link():
    hint = edition_refusal(NO_LONG_PROSE, '')
    assert hint is not None and 'https://' not in hint


@pytest.mark.req('STORE-MCP-001')
def test_other_refusals_stay_as_they_are(store_edition):
    assert edition_refusal('Сцену не знайдено', WAITLIST) is None
    assert edition_refusal(limit_text(store_edition)[:-10], WAITLIST) is None
    assert edition_refusal(NO_LONG_PROSE + ' і ще щось', WAITLIST) is None


@pytest.mark.req('STORE-MCP-001')
def test_bridge_tool_error_carries_the_hint(store_edition):
    limit, info = limit_text(store_edition), []

    def handler(request):
        if request.url.path == '/api/app-info':
            info.append(1)
            return httpx.Response(200, json={'waitlist_url': WAITLIST})
        return httpx.Response(403, json={'detail': 'Generation is blocked…', 'detail_original': limit})
    http = httpx.Client(base_url='http://127.0.0.1:8765', transport=httpx.MockTransport(handler))

    async def run():
        async with Client(build_server(http)) as client:
            return [await client.call_tool('get_scene_text', {'scene_id': 'scene-1', 'material': 'draft'}) for _ in range(2)]
    results = anyio.run(run)
    for result in results:
        text = ''.join(getattr(item, 'text', '') for item in result.content)
        assert result.is_error and WAITLIST in text and 'платної версії' in text
    assert info == [1, 1]  # LONG-PROSE-TRIAL: read on every edition refusal, so the trial state is current


def structured_obscura(tmp_path, monkeypatch):
    """The real Obscura in the Store edition with a book in parts and arcs (read-only there)."""
    from fastapi.testclient import TestClient

    from storygen import build_edition
    from storygen.application.settings import AppSettings
    from storygen.domain import SceneCreate, StoryCreate
    from storygen.storage.book_structure import put_structure
    from storygen.web.app import create_app
    edition = build_edition.BuildEdition(edition='store', waitlist_url=WAITLIST)
    monkeypatch.setattr(build_edition, 'current', lambda: edition)
    app = create_app(AppSettings(data_dir=tmp_path / 'data', env_file=tmp_path / 'absent.env'))
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Книга'))
    first = repo.create_scene(story.id, SceneCreate(title='Перша'))
    second = repo.create_scene(story.id, SceneCreate(title='Друга'))
    parts = [{'id': 'p1', 'arcs': [{'id': 'a1'}]}, {'id': 'p2', 'arcs': [{'id': 'b1'}]}]
    put_structure(repo, story.id, parts, {first.id: 'a1', second.id: 'b1'}, repo.get_story(story.id).revision)
    return TestClient(app, base_url='http://127.0.0.1:8765'), first


@pytest.mark.req('STORE-MCP-001')
def test_real_server_refusal_reaches_the_chat_as_a_hint(tmp_path, monkeypatch):
    # The real Obscura prefixes validation refusals («Некоректні дані: …»): the hint must survive the server format.
    http, scene = structured_obscura(tmp_path, monkeypatch)

    async def run():
        async with Client(build_server(http)) as client:
            return await client.call_tool('get_scene_context', {'scene_id': scene.id})
    result = anyio.run(run)
    text = ''.join(getattr(item, 'text', '') for item in result.content)
    assert result.is_error and READ_ONLY in text
    assert 'платної версії' in text and WAITLIST in text


def mocked(routes):
    """A bridge over a mock Obscura: `routes` maps a path to (status, json); /api/app-info gives the waitlist link."""
    def handler(request):
        if request.url.path == '/api/app-info':
            return httpx.Response(200, json={'waitlist_url': WAITLIST})
        status, body = routes[request.url.path]
        return httpx.Response(status, json=body)
    return build_server(httpx.Client(base_url='http://127.0.0.1:8765', transport=httpx.MockTransport(handler)))


def call(server, name, arguments):
    async def run():
        async with Client(server) as client:
            return await client.call_tool(name, arguments)
    result = anyio.run(run)
    return result, ''.join(getattr(item, 'text', '') for item in result.content)


@pytest.mark.req('STORE-MCP-001')
def test_stage_result_422_edition_refusal_is_a_hint():
    server = mocked({'/api/scenes/scene-1/chat-result/brief': (422, {'detail': 'x', 'detail_original': 'Некоректні дані: ' + NO_LONG_PROSE})})
    result, text = call(server, 'save_stage_result', {'scene_id': 'scene-1', 'stage': 'brief', 'task_fingerprint': 'f', 'result': '{}'})
    assert result.is_error and NO_LONG_PROSE in text and 'платної версії' in text and WAITLIST in text


@pytest.mark.req('STORE-MCP-001')
@pytest.mark.parametrize('confirm', [False, True])
def test_start_run_readiness_edition_limit_is_a_hint(confirm, store_edition):
    limit = limit_text(store_edition)
    server = mocked({'/api/stories/story-1': (200, {'story': {'writing_mode': 'obscura'}}),
                     '/api/stories/story-1/readiness': (200, {'operations': {'draft': {'ready': False, 'reason': limit}}}),
                     '/api/stories/story-1/budget': (200, {})})
    result, text = call(server, 'start_run', {'story_id': 'story-1', 'action': 'draft', 'scene_id': 'scene-1', 'confirm': confirm})
    assert result.is_error is confirm
    assert limit in text and 'платної версії' in text and WAITLIST in text


@pytest.mark.req('LONG-PROSE-TRIAL')
@pytest.mark.parametrize('detail', [TRIAL_USED, TRIAL_SERIES_FULL, TRIAL_BOOK_ALONE])
def test_trial_refusals_are_edition_refusals(detail):
    hint = edition_refusal(detail, WAITLIST, {'state': 'used'})
    assert hint is not None and detail in hint and TRIAL_USED_TEXT in hint and WAITLIST in hint


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_hint_names_the_trial_by_its_state():
    assert TRIAL_AVAILABLE_TEXT in edition_refusal(READ_ONLY, WAITLIST, {'state': 'available'})
    for state in (None, {'state': 'none'}, {}):
        hint = edition_refusal(READ_ONLY, WAITLIST, state)
        assert TRIAL_AVAILABLE_TEXT not in hint and TRIAL_USED_TEXT not in hint


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_bridge_reads_the_trial_state_with_the_refusal():
    def handler(request):
        if request.url.path == '/api/app-info':
            return httpx.Response(200, json={'waitlist_url': WAITLIST, 'long_prose_trial': {'state': 'available'}})
        return httpx.Response(400, json={'detail': 'x', 'detail_original': 'Некоректні дані: ' + READ_ONLY})
    http = httpx.Client(base_url='http://127.0.0.1:8765', transport=httpx.MockTransport(handler))

    async def run():
        async with Client(build_server(http)) as client:
            return await client.call_tool('get_scene_text', {'scene_id': 'scene-1', 'material': 'draft'})
    result = anyio.run(run)
    text = ''.join(getattr(item, 'text', '') for item in result.content)
    assert result.is_error and TRIAL_AVAILABLE_TEXT in text


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_import_confirm_never_sends_trial(tmp_path, store_edition, monkeypatch):
    """LONG-PROSE-TRIAL-S07: the chat never turns the trial on; the author does it in the Obscura window."""
    from tests.mcp.test_bridge import call
    from tests.mcp.test_bridge_manuscript import bridge, manuscript
    from tests.mcp.test_bridge_settings import ok
    from storygen.storage.long_prose_trial import trial_state
    app, http, server = bridge(tmp_path)
    book = '\n\n'.join(['# Книга', 'Частина 1. Берег', '## Глава перша', 'Текст першої глави. ' * 5,
                        'Частина 2. Море', '## Глава друга', 'Текст другої глави. ' * 5])
    preview = ok(call(server, 'import_manuscript', {'file_path': manuscript(tmp_path, content=book)}))
    assert preview['edition']['trial']['state'] == 'available' and preview['parts']
    sent, original = [], http.request
    def record(method, url, **kwargs):
        if method == 'POST' and url.startswith('/api/manuscript-import/') and not url.endswith('/preview'):
            sent.append(kwargs.get('json'))
        return original(method, url, **kwargs)
    monkeypatch.setattr(http, 'request', record)
    call(server, 'import_manuscript', {'confirm': True, 'import_id': preview['import_id'], 'fingerprint': preview['fingerprint'],
                                       'title': 'Книга'})
    assert sent and all('trial' not in body for body in sent)
    assert trial_state(app.state.repo)['state'] == 'available'
