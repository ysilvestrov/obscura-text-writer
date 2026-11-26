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


@pytest.mark.req('EDITOR-IMPORT')
def test_editor_import_docx_gives_a_changed_scene_and_a_comment(tmp_path):
    from scripts.capture_screenshots import editor_import_docx
    from storygen.application.editor_import import preview_import
    ids=seed(tmp_path/'data')
    repo=Repository(tmp_path/'data')
    for lang in ('uk','en'):
        story=ids[lang]['story_id']
        preview=preview_import(repo,story,editor_import_docx(repo,story,lang))
        by_id={scene.scene_id:scene for scene in preview.scenes}
        first,second=by_id[ids[lang]['first_id']],by_id[ids[lang]['scene_id']]
        assert (first.status,first.edits)==('changed',1)
        assert second.status=='comments_only' and second.comments==1
        assert not preview.choice_required and not preview.unmatched


@pytest.mark.req('MANUSCRIPT-IMPORT')
def test_manuscript_sample_gives_chapters_a_separator_and_a_proposed_boundary(tmp_path):
    from scripts.capture_screenshots import manuscript_sample
    from storygen.application.manuscript_import import preview
    from storygen.publication.manuscript_structure import ParseSettings
    for lang,epilogue in (('uk','Епілог'),('en','Epilogue')):
        name,content=manuscript_sample(lang)
        result=preview(Repository(tmp_path/lang),content,name,ParseSettings())
        titles=[scene.title for scene in result.scenes]
        assert result.chapter_source=='markers' and len(titles)==5 and titles[-1]==epilogue
        assert [scene.proposed for scene in result.scenes]==[False,False,False,True,False] and not result.warnings


def test_character_proposal_seed_is_acceptable_and_quotes_are_verbatim(tmp_path):
    """CHARACTER-EXTRACT-S11: the site shot's neutral proposal is one the server accepts (fingerprint, run, verbatim quotes)."""
    from scripts.capture_screenshots import seed_character_proposal
    from storygen.characters.extract_accept import AcceptRequest, accept_proposal, current_proposal
    for lang in ('uk','en'):
        repo=Repository(tmp_path/lang)
        story=seed_character_proposal(tmp_path/lang,lang)
        found=current_proposal(repo,story)
        proposal=found['proposal']
        for quote in proposal['cards'][0]['quotes']:
            assert quote['quote'] in repo.read_text(quote['version_id'])
        result=accept_proposal(repo,story,AcceptRequest(run_id=found['run_id'],fingerprint=proposal['fingerprint'],
                                                        cards=[{'key':'n1','names':[]}],protagonist=True,dry_run=True))
        assert {item['kind'] for item in result['applied']}=={'card','protagonist'} and not result['skipped']
