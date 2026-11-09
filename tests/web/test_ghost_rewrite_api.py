"""#55: POST /api/scenes/{id}/ghost-rewrite saves the author's rewrite as a manual draft linked to the AI draft."""
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.characters.acquaintance import lineage_brief
from storygen.generation.context import build_context
from storygen.generation.dependencies import save_manual_draft
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.web.app import create_app
from tests.characters.test_acquaintance_history import setup, brief, run
from tests.characters.test_brief_link_lineage import edges

AI = 'Вона відчинила двері й побачила порожній коридор.\n\n***\n\n' + 'Довгий абзац про дощ і вітер, що гнав листя вулицею. ' * 4
AUTHOR = 'Двері піддалися, і за ними був тільки порожній коридор.\n\n***\n\nДощ не вщухав.'


def client(tmp_path):
    return TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765')


def ai_draft(repo, story, scene, content_format='plain'):
    b = brief(repo, story, scene, ['B'])
    d = repo.save_version(story.id, scene.id, 'draft', AI, [b.id], source_run_id='run-1', content_format=content_format)
    repo.set_head(scene.id, 'draft', d.id, repo.get_scene(scene.id).revision)
    return b, d


def body(repo, scene, source, **extra):
    data = {'source_draft_id': source, 'text': AUTHOR, 'expected_revision': repo.get_scene(scene.id).revision,
            'client_stats': {'peeks': 3, 'peek_ms': 4200, 'pastes_blocked': 1, 'blocks_skipped': 0}}
    data.update(extra)
    return data


def test_save_creates_manual_draft_linked_to_ai_draft(tmp_path):
    repo, story, (s1, s2) = setup(tmp_path, casts=[['A', 'B'], ['A', 'B']])
    b, d = ai_draft(repo, story, s1)
    before = repo.get_version(d.id)
    with client(tmp_path) as http:
        done = http.post(f'/api/scenes/{s1.id}/ghost-rewrite', json=body(repo, s1, d.id))
        assert done.status_code == 200, done.text
        version = done.json()['version']
    ghost = repo.get_version(version['id'])
    assert ghost.kind == 'draft' and ghost.source_run_id is None
    assert ghost.author_lineage.parent_version_id == d.id
    stats = ghost.ghost_rewrite
    assert (stats.source_draft_id, stats.blocks, stats.blocks_written, stats.blocks_skipped) == (d.id, 2, 2, 0)
    assert (stats.peeks, stats.peek_ms, stats.pastes_blocked, stats.min_block_chars) == (3, 4200, 1, 160)
    assert 0.0 <= stats.overlap_4gram < 0.5
    assert repo.get_scene(s1.id).heads['draft'] == ghost.id
    assert repo.read_text(ghost.id) == AUTHOR
    after = repo.get_version(d.id)
    assert (after.sha256, after.stale, after.input_refs) == (before.sha256, before.stale, before.input_refs)
    assert repo.read_text(d.id) == AI
    # Dependencies are those of an ordinary manual draft: the AI draft is lineage, never an input.
    assert d.id not in ghost.input_refs and d.id not in ghost.dependency_snapshot.refs and d.id not in edges(repo, ghost.id)
    plain = save_manual_draft(repo, s1.id, 'Звичайна ручна чернетка.', repo.get_scene(s1.id).revision)
    assert sorted(ghost.input_refs) == sorted(plain.input_refs)
    assert ghost.dependency_snapshot.refs == plain.dependency_snapshot.refs
    assert edges(repo, ghost.id) == edges(repo, plain.id)


def test_prose_from_author_draft_reaches_the_brief(tmp_path):
    repo, story, (s1, s2) = setup(tmp_path, casts=[['A', 'B', 'C'], ['A']])
    b, d = ai_draft(repo, story, s1)
    with client(tmp_path) as http:
        ghost_id = http.post(f'/api/scenes/{s1.id}/ghost-rewrite', json=body(repo, s1, d.id)).json()['version']['id']
        context = build_context(repo, s1.id, 'edit', RoleSettings(provider=ProviderSettings(model='test'), edit_mode='patches'))
        assert ghost_id in context.input_refs, 'the regular editor takes the author draft'
    edited = repo.save_version(story.id, s1.id, 'edited', 'Вичитана проза.', [ghost_id])
    repo.set_head(s1.id, 'prose', edited.id, repo.get_scene(s1.id).revision)
    view = repo.context_view(story.id)
    assert lineage_brief(view, view.get_scene(s1.id)).id == b.id
    assert run(repo, story, 1).known == {'B': 1}, 'brief introduced, not the fallback (which would add C)'


def test_format_follows_ai_draft(tmp_path):
    repo, story, (s1,) = setup(tmp_path, casts=[['A']])
    _, d = ai_draft(repo, story, s1, content_format='markdown')
    with client(tmp_path) as http:
        version = http.post(f'/api/scenes/{s1.id}/ghost-rewrite', json=body(repo, s1, d.id)).json()['version']
    assert version['content_format'] == 'markdown'


def test_skipped_blocks_and_errors(tmp_path):
    repo, story, (s1, s2) = setup(tmp_path, casts=[['A'], ['A']])
    b, d = ai_draft(repo, story, s1)
    _, other = ai_draft(repo, story, s2)
    url = f'/api/scenes/{s1.id}/ghost-rewrite'
    with client(tmp_path) as http:
        assert http.post(url, json=body(repo, s1, 'missing')).status_code == 404
        assert http.post(url, json=body(repo, s1, other.id)).status_code == 400
        assert http.post(url, json=body(repo, s1, b.id)).status_code == 400
        too_many = body(repo, s1, d.id)
        too_many['client_stats']['blocks_skipped'] = 3
        assert http.post(url, json=too_many).status_code == 400
        english = http.post(url, json=body(repo, s1, other.id), headers={'accept-language': 'en'})
        assert 'Only a complete draft' in english.json()['detail']
        assert http.post(url, json=body(repo, s1, d.id, text='  ')).status_code == 400
        skipped = body(repo, s1, d.id)
        skipped['client_stats']['blocks_skipped'] = 1
        version = http.post(url, json=skipped).json()['version']
        assert (version['ghost_rewrite']['blocks_written'], version['ghost_rewrite']['blocks_skipped']) == (1, 1)


def test_revision_conflict_keeps_version_in_history(tmp_path):
    repo, story, (s1,) = setup(tmp_path, casts=[['A']])
    _, d = ai_draft(repo, story, s1)
    stale = body(repo, s1, d.id, expected_revision=repo.get_scene(s1.id).revision - 1)
    with client(tmp_path) as http:
        result = http.post(f'/api/scenes/{s1.id}/ghost-rewrite', json=stale)
    assert result.status_code == 409
    assert repo.get_scene(s1.id).heads['draft'] == d.id
    kept = [v for v in repo.list_versions(story.id, s1.id, 'draft') if v.ghost_rewrite]
    assert len(kept) == 1 and kept[0].author_lineage.parent_version_id == d.id
