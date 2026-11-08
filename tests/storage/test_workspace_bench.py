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
    expected = {f'readiness:{n}' for n in OPERATIONS} | {'story_view', 'list_attempts', 'list_runs', 'scene_select'}
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
