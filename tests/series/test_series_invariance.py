"""SERIES-S05: a book outside a series is unchanged — no series selector, no new input, old snapshots stay fresh;
a series without prequels keeps the 4a snapshot and selectors (SERIES-S10)."""
from storygen.generation.context import build_context
from storygen.storage.snapshots import compare_snapshot
from tests.memory.merge_helpers import arc_book
from tests.memory.test_core_review import role, two_scenes
from tests.series.test_series_memory import write_brief, write_scene_memory


def assert_no_series_input(repo, story_id, scene, stages=('brief', 'memory')):
    for stage in stages:
        context = build_context(repo, scene.id, stage, role())
        assert not any(repo.get_version(id).kind == 'series_start' for id in context.input_refs)


def test_book_outside_series_is_unchanged(tmp_path):
    repo, story, s1, s2, journal, _ = two_scenes(tmp_path / 'chain')
    assert_no_series_input(repo, story.id, s2)
    brief, memory = write_brief(repo, s2), write_scene_memory(repo, s2)
    arcs, book, scenes = arc_book(tmp_path / 'arcs', 'A B A', [['A', 'B']])
    arc_brief = write_brief(arcs, scenes[1])
    for owner, id in ((repo, brief), (repo, memory), (arcs, arc_brief)):
        ref = owner.get_version(id)
        assert not any(s.field == 'series_start' for s in ref.dependency_snapshot.selectors)
        assert compare_snapshot(owner.context_view(ref.story_id), ref.dependency_snapshot) == []
        assert not ref.stale


def test_sequential_series_is_unchanged(tmp_path):
    import json
    from storygen.memory.series_start import read_series_start
    from tests.series.test_series_memory import second_book
    repo, item, second, scene, cloth = second_book(tmp_path)
    raw = json.loads(repo.read_text(second.series_start_version_id))
    data = read_series_start(json.dumps(raw), second.series_start_version_id)
    assert len(data.source['sources']) == 1 and data.source['resolved'] == []
    assert not {'decisions', 'future', 'start_memory', 'origins'} & set(raw)
    assert data.decisions is None and data.future == []
    fields = {s.field for s in repo.get_version(write_brief(repo, scene)).dependency_snapshot.selectors}
    assert 'series_start' in fields and 'series_future' not in fields
