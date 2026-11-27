import http.client
import json
import threading

import pytest

import rag_owner_review as review
from memory_bench.paraphrase import ROOT


pytestmark = pytest.mark.loopback


def make_file(tmp_path, n=6):
    items = [{'claim_id': f'c{i}', 'level': ('same', 'syn', 'desc')[i % 3], 'sha256': 'x', 'text': f'Запит {i} <b>',
              'record_text': f'Запис {i}', 'verdict': None} for i in range(n)]
    path = tmp_path / 'owner-check.json'
    path.write_text(json.dumps({'snapshot': 's', 'items': items}, ensure_ascii=False), encoding='utf-8')
    return path


@pytest.fixture
def served(tmp_path):
    path = make_file(tmp_path)
    server = review.make_server(path, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield path, server
    server.shutdown()
    server.server_close()


def call(server, method, route, body=None, headers=None):
    conn = http.client.HTTPConnection('127.0.0.1', server.server_address[1], timeout=5)
    data = None if body is None else json.dumps(body)
    conn.request(method, route, body=data, headers={'Content-Type': 'application/json', **(headers or {})})
    resp = conn.getresponse()
    raw = resp.read()
    conn.close()
    return resp.status, raw


def verdicts(path):
    return [i['verdict'] for i in json.loads(path.read_text(encoding='utf-8'))['items']]


def test_server_binds_localhost_only(served):
    assert served[1].server_address[0] == '127.0.0.1'


def test_page_served(served):
    status, raw = call(served[1], 'GET', '/')
    assert status == 200 and 'Годиться' in raw.decode('utf-8') and 'innerHTML' not in raw.decode('utf-8')


def test_get_items_and_post_verdict_updates_file(served):
    path, server = served
    status, raw = call(server, 'GET', '/items')
    data = json.loads(raw)
    assert status == 200 and len(data['items']) == 6 and data['items'][0]['index'] == 0
    assert set(data['items'][0]) == {'index', 'level', 'record_text', 'text', 'verdict'}
    assert data['summary'] == {'yes': 0, 'no': 0, 'pending': 6, 'failed': False}
    status, raw = call(server, 'POST', '/verdict', {'index': 1, 'verdict': 'yes'})
    assert status == 200 and json.loads(raw)['yes'] == 1
    assert verdicts(path)[1] == 'yes'
    status, raw = call(server, 'POST', '/verdict', {'index': 1, 'verdict': None})
    assert status == 200 and verdicts(path)[1] is None


def test_bad_verdict_and_unknown_route(served):
    path, server = served
    status, raw = call(server, 'POST', '/verdict', {'index': 0, 'verdict': 'Так'})
    assert status == 400 and json.loads(raw) == {'error': 'bad_verdict'}
    status, raw = call(server, 'POST', '/verdict', {'index': 99, 'verdict': 'yes'})
    assert status == 400
    status, _ = call(server, 'POST', '/verdict', None)
    assert status == 400
    assert call(server, 'GET', '/etc')[0] == 404
    assert call(server, 'POST', '/items', {})[0] == 404
    assert set(verdicts(path)) == {None}


def test_foreign_origin_rejected(served):
    path, server = served
    port = server.server_address[1]
    status, _ = call(server, 'POST', '/verdict', {'index': 0, 'verdict': 'yes'}, {'Origin': 'https://example.com'})
    assert status == 403 and verdicts(path)[0] is None
    assert call(server, 'GET', '/items', headers={'Origin': 'https://example.com'})[0] == 403
    status, _ = call(server, 'POST', '/verdict', {'index': 0, 'verdict': 'no'}, {'Origin': f'http://127.0.0.1:{port}'})
    assert status == 200 and verdicts(path)[0] == 'no'


def test_get_items_unreadable_file_is_500_without_path(served):
    path, server = served
    path.write_text('{broken', encoding='utf-8')
    status, raw = call(server, 'GET', '/items')
    assert status == 500 and json.loads(raw) == {'error': 'owner_check_missing'}
    assert str(path) not in raw.decode('utf-8')


def test_cli_refuses_repo_dir_and_missing_file(tmp_path, capsys):
    assert review.main(['--dir', str(ROOT / 'docs'), '--no-browser']) == 1
    assert json.loads(capsys.readouterr().out) == {'error': 'inside_repo'}
    assert review.main(['--dir', str(tmp_path), '--no-browser']) == 1
    assert json.loads(capsys.readouterr().out) == {'error': 'owner_check_missing'}


def test_server_is_silent(served, capsys):
    call(served[1], 'GET', '/items')
    out = capsys.readouterr()
    assert out.out == '' and out.err == ''


def test_concurrent_posts_lose_no_updates(served):
    path, server = served
    threads = [threading.Thread(target=call, args=(server, 'POST', '/verdict', {'index': n, 'verdict': 'yes'}))
               for n in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert verdicts(path) == ['yes'] * 6
