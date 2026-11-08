import json
import re

import pytest
from pydantic import BaseModel

from storygen.application.workspace_bench import OPERATIONS, _shallow_model_copy, build_story, measure
from storygen.impact.presentation import scene_status
from storygen.storage.repository import Repository


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
