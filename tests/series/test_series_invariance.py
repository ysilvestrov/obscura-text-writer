"""SERIES-S05: a book outside a series is unchanged — no series selector, no new input, old snapshots stay fresh."""
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
