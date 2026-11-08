"""Scene-selection endpoints read one SQL snapshot per request and answer exactly as the per-call path."""
import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.application.workspace_bench import configure_roles
from storygen.domain import SceneCreate, StageAttempt
from storygen.generation.dependencies import save_manual_prose
from storygen.storage.context_view import ContextView
from storygen.storage.repository import Repository
from storygen.web.app import create_app
from tests.memory.test_forwarding import apply, memory_view, seeded


def _fixture(root):
    """Three scenes with prose and memory, a hidden forwarded fact (stale chain), a legacy draft,
    a trashed scene, and copyedit/rewrite proposals on a live and on the trashed scene."""
    repo, story, scenes = seeded(root)
    draft = repo.save_version(story.id, scenes[2].id, 'draft', 'Легасі чернетка.', [])
    repo.set_head(scenes[2].id, 'draft', draft.id, repo.get_scene(scenes[2].id).revision)
    claim = memory_view(repo, scenes[1].id)['rows'][0]['claim_id']
    apply(repo, scenes[1], {claim: False})
    trashed = repo.create_scene(story.id, SceneCreate(title='Кошик'))
    save_manual_prose(repo, trashed.id, 'Текст у кошику.', trashed.revision)
    trashed = repo.get_scene(trashed.id)
    configure_roles(repo, story.id)
    for n, scene_id in enumerate([scenes[2].id, trashed.id]):
        for key, state in [('copyedit_proposal', 'completed'), ('copyedit_proposal', 'failed'), ('rewrite_proposal', 'needs_review')]:
            repo.save_attempt(StageAttempt(id=f'a{n}{key[0]}{state[0]}', story_id=story.id, scene_id=scene_id, stage='edit',
                                           state=state, context={key: {'x': 1}}, partial_path='p.txt'))
    repo.set_scene_trashed(story.id, trashed.id, trashed.revision, restore=False)
    assert any(v.stale for v in repo.list_versions(story.id))
    return repo, story, [s.id for s in scenes], trashed.id, draft.id


def _urls(scene_ids, trashed_id, draft_id):
    urls = []
    for scene_id in [*scene_ids, trashed_id, 'missing']:
        urls += [f'/api/scenes/{scene_id}/versions', f'/api/scenes/{scene_id}/copyedits', f'/api/scenes/{scene_id}/rewrites']
        urls += [f'/api/scenes/{scene_id}/statistics?stage={stage}' for stage in ('brief', 'draft', 'edit', 'memory')]
    urls.append(f'/api/scenes/{scene_ids[2]}/statistics?stage=edit&editor_source_head=draft&editor_source_version_id={draft_id}')
    return urls


def _per_call_path(monkeypatch, repo):
    """The pre-change reads: every repository call opens its own snapshot and the routes ignore the shared view."""
    get_scene, list_versions = Repository.get_scene, Repository.list_versions
    monkeypatch.setattr(Repository, 'get_scene', lambda self, id, include_trashed=False, *, view=None: get_scene(self, id, include_trashed))
    monkeypatch.setattr(Repository, 'list_versions',
                        lambda self, story_id, scene_id=None, kind=None, *, view=None: list_versions(self, story_id, scene_id, kind))
    monkeypatch.setattr(Repository, 'active_scene_story_id', lambda self, id: get_scene(self, id).story_id)
    monkeypatch.setattr(ContextView, 'list_acceptances', lambda self, story_id: repo.list_acceptances(story_id))


def _responses(client, urls):
    return {url: (r.status_code, r.json()) for url in urls for r in [client.get(url)]}


def test_scene_endpoints_on_one_view_equal_per_call_responses(tmp_path, monkeypatch):
    repo, story, scene_ids, trashed_id, draft_id = _fixture(tmp_path)
    client = TestClient(create_app(AppSettings(data_dir=tmp_path, env_file=tmp_path / 'none.env')), base_url='http://127.0.0.1:8765')
    urls = _urls(scene_ids, trashed_id, draft_id)
    shared = _responses(client, urls)
    _per_call_path(monkeypatch, client.app.state.repo)
    assert _responses(client, urls) == shared
    statuses = {url: status for url, (status, _) in shared.items()}
    assert all(statuses[u] == 200 for u in urls if '/missing/' not in u and f'/{trashed_id}/' not in u)
    assert all(statuses[u] == 404 for u in urls if '/missing/' in u or f'/{trashed_id}/' in u)
    attempts = shared[f'/api/scenes/{scene_ids[2]}/copyedits'][1]['attempts']
    assert [a['id'] for a in attempts] == ['a0cc']
    assert [a['id'] for a in shared[f'/api/scenes/{scene_ids[2]}/rewrites'][1]['attempts']] == ['a0rn']
    assert shared[f'/api/scenes/{scene_ids[2]}/versions'][1]['acceptances'] == []


@pytest.mark.parametrize('path,limit', [('versions', 1), ('statistics?stage=draft', 1), ('statistics?stage=edit', 1),
                                        ('copyedits', 0), ('rewrites', 0)])
def test_scene_endpoint_builds_at_most_one_view(tmp_path, monkeypatch, path, limit):
    repo, story, scene_ids, trashed_id, draft_id = _fixture(tmp_path)
    client = TestClient(create_app(AppSettings(data_dir=tmp_path, env_file=tmp_path / 'none.env')), base_url='http://127.0.0.1:8765')
    calls = []
    original = ContextView.__init__

    def counting(self, *args, **kwargs):
        calls.append(1)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(ContextView, '__init__', counting)
    for scene_id in scene_ids:
        calls.clear()
        assert client.get(f'/api/scenes/{scene_id}/{path}').status_code == 200
        assert len(calls) <= limit, (path, len(calls))


def test_versions_acceptances_come_from_the_same_snapshot(tmp_path):
    """The acceptance journal in the versions response equals Repository.list_acceptances, in order."""
    from tests.storage.test_freshness import setup
    repo, story, scene, draft, prose = setup(tmp_path)
    other = repo.save_version(story.id, scene.id, 'draft', 'B', [])
    repo.set_head(scene.id, 'draft', other.id, repo.get_scene(scene.id).revision)
    for _ in range(2):
        preview = repo.preview_acceptance(scene.id, prose.id)
        repo.accept_version(scene.id, prose.id, preview.expected_revision, preview.preview_fingerprint)
        repo.set_head(scene.id, 'draft', draft.id if _ else other.id, repo.get_scene(scene.id).revision)
    client = TestClient(create_app(AppSettings(data_dir=tmp_path, env_file=tmp_path / 'none.env')), base_url='http://127.0.0.1:8765')
    data = client.get(f'/api/scenes/{scene.id}/versions').json()
    expected = [r.model_dump(mode='json') for r in repo.list_acceptances(story.id)]
    assert len(expected) == 2 and data['acceptances'] == expected


def test_edit_statistics_for_legacy_draft_keep_view_freshness(tmp_path):
    """Scene statistics judge an explicit edit source by the view's recomputed freshness, as before #27
    (322646d): only edit_loop readiness uses the stored (Repository.get_version) semantics."""
    repo, story, scene_ids, trashed_id, draft_id = _fixture(tmp_path)
    assert repo.get_version(draft_id).stale is False and repo.context_view(story.id).get_version(draft_id).stale is True
    client = TestClient(create_app(AppSettings(data_dir=tmp_path, env_file=tmp_path / 'none.env')), base_url='http://127.0.0.1:8765')
    data = client.get(f'/api/scenes/{scene_ids[2]}/statistics?stage=edit&editor_source_head=draft&editor_source_version_id={draft_id}').json()
    assert data['context']['available'] is False
    assert data['context']['reason'] == 'Вибрана проза або чернетка потребує оновлення'
    assert data['materials']['draft']['stale'] is True


def test_proposal_lists_survive_a_corrupt_acceptance_journal(tmp_path):
    """Recorded deviation (SPEC PERF-001): copyedit and rewrite lists need no context view, so they still answer
    on a story whose view cannot be built; view-based endpoints keep failing there."""
    repo, story, scene_ids, trashed_id, draft_id = _fixture(tmp_path)
    with repo.db.connection() as db:
        db.execute('INSERT INTO app_settings VALUES(?,?)', (f'acceptance:{story.id}:broken', '{"id": "x"}'))
    with pytest.raises(ValueError):
        repo.context_view(story.id)
    client = TestClient(create_app(AppSettings(data_dir=tmp_path, env_file=tmp_path / 'none.env')),
                        base_url='http://127.0.0.1:8765', raise_server_exceptions=False)
    copyedits = client.get(f'/api/scenes/{scene_ids[2]}/copyedits')
    rewrites = client.get(f'/api/scenes/{scene_ids[2]}/rewrites')
    assert copyedits.status_code == 200 and [a['id'] for a in copyedits.json()['attempts']] == ['a0cc']
    assert rewrites.status_code == 200 and [a['id'] for a in rewrites.json()['attempts']] == ['a0rn']
    assert client.get(f'/api/scenes/{trashed_id}/copyedits').status_code == 404
    assert client.get(f'/api/scenes/{scene_ids[2]}/versions').status_code != 200
