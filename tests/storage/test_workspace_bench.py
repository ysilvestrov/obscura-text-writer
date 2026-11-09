import json
import re

import pytest
from pydantic import BaseModel

from storygen.application.workspace_bench import OPERATIONS, _shallow_model_copy, build_story, measure
from storygen.impact.presentation import scene_status
from storygen.storage.repository import Repository

# The bench must rate its own synthetic story; the conftest default rating would hide a missing rating.
pytestmark = pytest.mark.unrated_stories


def test_bench_digest_is_stable_and_synthetic_story_has_requested_size(tmp_path):
    repo = Repository(tmp_path)
    story_id = build_story(repo, 5)
    scenes = repo.context_view(story_id).list_scenes(story_id)
    assert len(scenes) == 5
    assert all({'plan', 'prose', 'memory'} <= set(s.heads) for s in scenes)
    first, second = measure(repo, story_id), measure(repo, story_id)
    assert first['digest'] == second['digest'] and len(first['digest']) == 64
    assert len(OPERATIONS) == 9 and first['scenes'] == 5
    expected = {f'readiness:{n}' for n in OPERATIONS} | {'readiness:all', 'story_view', 'list_attempts', 'list_runs', 'scene_select'}
    assert set(first['timings']) == expected
    assert 'readiness:brief' in expected and 'readiness:edit_loop' in expected


def _structure(repo, story_id):
    """Story, scenes, versions and head texts as JSON with ids numbered by first appearance and timestamps removed."""
    view = repo.context_view(story_id)
    scenes = view.list_scenes(story_id)
    data = {'story': repo.get_story(story_id).model_dump(mode='json'),
            'scenes': [s.model_dump(mode='json') for s in scenes],
            'versions': [v.model_dump(mode='json') for v in repo.list_versions(story_id)],
            'texts': [[repo.read_text(s.heads[h]) for h in ('plan', 'prose', 'memory')] for s in scenes],
            'status': [scene_status(view)[s.id] for s in scenes]}
    text = json.dumps(data, ensure_ascii=False, default=str)
    text = re.sub(r'\d{4}-\d\d-\d\dT[\d:.]+(?:\+00:00|Z)?', 'TS', text)
    text = re.sub(r'\b[0-9a-f]{64}\b', 'SHA', text)  # content hashes include the random memory event ids
    ids = {}
    return re.sub(r'\b(?:(?:me|mc)_[0-9a-f]{24}|[0-9a-f]{32})\b', lambda m: ids.setdefault(m.group(0), f'ID{len(ids)}'), text)


def test_shallow_copy_build_matches_normal_build_and_restores_model_copy(tmp_path):
    original = BaseModel.model_copy
    normal, shallow = Repository(tmp_path / 'a'), Repository(tmp_path / 'b')
    first = build_story(normal, 5)
    second = build_story(shallow, 5, shallow_copies=True)
    assert BaseModel.model_copy is original
    assert _structure(normal, first) == _structure(shallow, second)
    assert measure(shallow, second)['scenes'] == 5
    with pytest.raises(RuntimeError):
        with _shallow_model_copy(True):
            assert BaseModel.model_copy is not original
            raise RuntimeError
    assert BaseModel.model_copy is original


def test_synthetic_story_reaches_full_readiness_path(tmp_path):
    """The synthetic build saves roles, so readiness passes the role check and builds context."""
    from storygen.application.workspace_bench import BENCH_ROLES, _request
    from storygen.authoring.blueprints import get_role_settings
    from storygen.generation.readiness import preview
    repo = Repository(tmp_path)
    story_id = build_story(repo, 5, shallow_copies=True)
    assert set(BENCH_ROLES) <= set(get_role_settings(repo, story_id))
    assert repo.get_story(story_id).content_rating is not None
    middle = repo.context_view(story_id).list_scenes(story_id)[2].id
    for name in ['brief', 'scene', 'memory', 'rebuild_memory', 'remaining']:
        result = preview(repo, _request(story_id, middle, name))
        assert result['ready'] is True, name
        assert result['roles']


def test_reused_workdir_must_hold_requested_completed_workload(tmp_path):
    from storygen.application.workspace_bench import SYNTHETIC_TITLE, run
    from storygen.domain import SceneCreate, StoryCreate
    first = run(synthetic=3, workdir=tmp_path / 'w')
    assert first['scenes'] == 3
    assert run(synthetic=3, workdir=tmp_path / 'w')['digest'] == first['digest']
    with pytest.raises(ValueError, match='synthetic_mismatch'):
        run(synthetic=5, workdir=tmp_path / 'w')
    # An interrupted (or older) build has scenes but no bench roles.
    repo = Repository(tmp_path / 'i')
    story = repo.create_story(StoryCreate(title=SYNTHETIC_TITLE))
    for i in range(2):
        repo.create_scene(story.id, SceneCreate(title=f'Scene {i + 1}', beats='b'))
    with pytest.raises(ValueError, match='synthetic_incomplete'):
        run(synthetic=2, workdir=tmp_path / 'i')
    repo.create_story(StoryCreate(title=SYNTHETIC_TITLE))
    with pytest.raises(ValueError, match='synthetic_ambiguous'):
        run(synthetic=2, workdir=tmp_path / 'i')
    # A completed build from before content ratings has roles but no story rating.
    from storygen.application.workspace_bench import configure_roles
    old = Repository(tmp_path / 'o')
    story = old.create_story(StoryCreate(title=SYNTHETIC_TITLE))
    for i in range(2):
        old.create_scene(story.id, SceneCreate(title=f'Scene {i + 1}', beats='b'))
    configure_roles(old, story.id)
    with pytest.raises(ValueError, match='synthetic_unrated'):
        run(synthetic=2, workdir=tmp_path / 'o')


def test_scene_select_requests_the_editor_urls_and_enters_the_digest(tmp_path, monkeypatch):
    from storygen.storage.repository import Repository as Repo
    repo = Repository(tmp_path)
    story_id = build_story(repo, 3, shallow_copies=True)
    first = measure(repo, story_id)
    assert set(first['scene_select_requests']) == {'readiness', 'runs', 'versions', 'statistics', 'comments',
                                                   'copyedits', 'rewrites', 'evaluator'}
    assert repo.list_runs(story_id) == [] and not (tmp_path / 'worker.lock').exists()
    original = Repo.get_comment_state
    monkeypatch.setattr(Repo, 'get_comment_state', lambda self, scene_id: {**original(self, scene_id), 'changed': 1})
    changed = measure(repo, story_id)
    assert changed['digest'] != first['digest'] and changed['digest_core'] == first['digest_core']


def test_run_refuses_a_data_dir_without_database_and_creates_nothing(tmp_path):
    from storygen.application.workspace_bench import run
    empty = tmp_path / 'empty'
    empty.mkdir()
    with pytest.raises(ValueError, match='not_a_data_copy'):
        run(data=empty)
    assert list(empty.iterdir()) == []
    with pytest.raises(ValueError, match='not_a_data_copy'):
        run(data=tmp_path / 'absent')
    assert not (tmp_path / 'absent').exists()


def test_run_refuses_the_working_data_dir(tmp_path, monkeypatch):
    """<repo root>/data, and the main checkout's data when the code runs from a git worktree, are refused
    before a Repository is opened, even when they hold a database."""
    from storygen.application import workspace_bench
    opened = []
    monkeypatch.setattr(workspace_bench, 'Repository', lambda *a, **k: opened.append(a) or pytest.fail('opened'))
    main, worktree = tmp_path / 'main', tmp_path / 'wt'
    for root in [main, worktree]:
        (root / 'data').mkdir(parents=True)
        (root / 'data' / 'storygen.sqlite3').write_bytes(b'')
    (main / '.git' / 'worktrees' / 'wt').mkdir(parents=True)
    (worktree / '.git').write_text(f'gitdir: {main / ".git" / "worktrees" / "wt"}\n', encoding='utf-8')
    monkeypatch.setattr(workspace_bench, 'REPO_ROOT', worktree)
    for data in [worktree / 'data', main / 'data', main / 'data' / '..' / 'data']:
        with pytest.raises(ValueError, match='live_data'):
            workspace_bench.run(data=data, story='x')
    with pytest.raises(ValueError, match='live_data'):
        workspace_bench.run(synthetic=3, workdir=main / 'data')
    monkeypatch.setattr(workspace_bench, 'REPO_ROOT', main)
    with pytest.raises(ValueError, match='live_data'):
        workspace_bench.run(data=main / 'data', story='x')
    assert opened == []


def test_failing_scene_select_endpoint_is_a_clear_error_with_exit_code_2(tmp_path, monkeypatch, capsys):
    import importlib.util
    from pathlib import Path
    from storygen.storage.repository import Repository as Repo
    from storygen.application.workspace_bench import run
    run(synthetic=3, workdir=tmp_path / 'w')

    def broken(self, scene_id):
        raise RuntimeError('boom')
    monkeypatch.setattr(Repo, 'get_comment_state', broken)
    with pytest.raises(ValueError, match='scene_select_failed: comments returned HTTP 500'):
        run(synthetic=3, workdir=tmp_path / 'w')
    path = Path(__file__).resolve().parents[2] / 'scripts' / 'workspace_bench.py'
    spec = importlib.util.spec_from_file_location('workspace_bench_script', path)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    capsys.readouterr()
    assert script.main(['--synthetic', '3', '--workdir', str(tmp_path / 'w')]) == 2
    out = capsys.readouterr()
    assert 'scene_select_failed: comments' in out.err and 'Traceback' not in out.err and out.out == ''
