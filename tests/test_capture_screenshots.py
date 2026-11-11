import pytest

from scripts.capture_screenshots import STORIES, seed
from storygen.storage.repository import Repository


@pytest.mark.req('DOCS-SITE')
def test_seed_creates_neutral_stories_in_both_languages(tmp_path):
    ids=seed(tmp_path/'data')
    repo=Repository(tmp_path/'data')
    assert set(ids)=={'uk','en'}
    for lang,title,word in [('uk','Маяк на пристані','анна'),('en','Lighthouse pier','anna')]:
        story=repo.get_story(ids[lang]['story_id'])
        assert story.title==title and story.language==lang
        scene=repo.get_scene(ids[lang]['scene_id'])
        for kind in ('brief','draft'):
            version=repo.get_version(scene.heads[kind])
            assert version.kind==kind
            assert word in repo.read_text(version.id).lower()


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


@pytest.mark.req('DOCS-SITE')
def test_server_command_uses_an_isolated_env_file(tmp_path):
    from scripts.capture_screenshots import server_command,ROOT
    command=server_command(tmp_path/'data',8811,tmp_path/'empty.env')
    assert command[command.index('--env-file')+1]==str(tmp_path/'empty.env')
    assert str(ROOT/'.env') not in command


@pytest.mark.req('DOCS-SITE')
def test_relative_work_dir_is_resolved_before_seeding(tmp_path,monkeypatch):
    from scripts.capture_screenshots import resolve_work_dir
    monkeypatch.chdir(tmp_path)
    assert resolve_work_dir('shots')==(tmp_path/'shots').resolve()
