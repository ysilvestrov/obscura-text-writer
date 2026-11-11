import pytest

from scripts.capture_screenshots import STORIES, seed
from storygen.storage.repository import Repository


@pytest.mark.req('DOCS-SITE')
def test_seed_creates_neutral_stories_in_both_languages(tmp_path):
    ids=seed(tmp_path/'data')
    repo=Repository(tmp_path/'data')
    assert set(ids)=={'uk','en'}
    for lang,spec in STORIES.items():
        story=repo.get_story(ids[lang]['story_id'])
        assert story.title==spec['title'] and story.language==lang
        scene=repo.get_scene(ids[lang]['scene_id'])
        assert scene.heads.get('draft') and scene.heads.get('brief')


class _Exited:
    def poll(self):return 1


@pytest.mark.req('DOCS-SITE')
def test_wait_for_refuses_another_server_when_ours_exited():
    import http.server,threading
    from scripts.capture_screenshots import wait_for
    other=http.server.HTTPServer(('127.0.0.1',0),http.server.SimpleHTTPRequestHandler)
    threading.Thread(target=other.serve_forever,daemon=True).start()
    try:
        with pytest.raises(RuntimeError):
            wait_for(f'http://127.0.0.1:{other.server_port}/',_Exited(),timeout=5)
    finally:other.shutdown();other.server_close()


@pytest.mark.req('DOCS-SITE')
def test_busy_port_is_refused_before_start():
    import socket
    from scripts.capture_screenshots import ensure_port_free
    with socket.socket() as busy:
        busy.bind(('127.0.0.1',0));busy.listen()
        with pytest.raises(SystemExit):ensure_port_free(busy.getsockname()[1])


@pytest.mark.req('DOCS-SITE')
def test_server_env_has_no_provider_keys(monkeypatch):
    from scripts.capture_screenshots import server_env
    monkeypatch.setenv('VENICE_API_KEY','secret');monkeypatch.setenv('OPENROUTER_API_KEY','secret')
    env=server_env()
    assert 'VENICE_API_KEY' not in env and 'OPENROUTER_API_KEY' not in env and env['PYTHONPATH'].endswith('src')
