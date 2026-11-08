from storygen.application.workspace_bench import OPERATIONS, build_story, measure
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
