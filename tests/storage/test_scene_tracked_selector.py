"""BOOK-LINEAGE-S04: tracked characters are recorded per scene once a book has an explicit arc protagonist (neutral examples)."""
from storygen.storage.book_structure import put_structure
from tests.storage.test_memory_core_selectors import memory_version, reasons, setup


def parts(protagonist=None):
    return [{'id': 'p1', 'title': '', 'arcs': [{'id': 'X', 'title': ''}]},
            {'id': 'p2', 'title': '', 'arcs': [{'id': 'Y', 'title': '', 'protagonist_id': protagonist}]}]


def structure(repo, story, s1, s2, protagonist=None):
    put_structure(repo, story.id, parts(protagonist), {s1.id: 'X', s2.id: 'Y'}, repo.get_story(story.id).revision)


def tracked(snap):
    return {(s.kind, s.owner_id): s.expected for s in snap.selectors if s.field == 'tracked_characters'}


def changed(repo, story, ref):
    return ('selector_changed', 'tracked_characters') in reasons(repo, story, ref)


def test_without_explicit_protagonists_the_story_selector_stays(tmp_path):
    repo, story, (s1, s2) = setup(tmp_path)
    structure(repo, story, s1, s2)
    _, snap = memory_version(repo, story, s2)
    assert tracked(snap) == {('story', story.id): ['A']}


def test_explicit_protagonist_records_the_scene_selector(tmp_path):
    repo, story, (s1, s2) = setup(tmp_path)
    structure(repo, story, s1, s2, 'B')
    _, snap = memory_version(repo, story, s2)
    assert tracked(snap) == {('scene', s2.id): ['B']}


def test_arc_protagonist_change_stales_only_its_arc(tmp_path):
    repo, story, (s1, s2) = setup(tmp_path)
    structure(repo, story, s1, s2, 'B')
    first, _ = memory_version(repo, story, s1)
    second, _ = memory_version(repo, story, s2)
    structure(repo, story, s1, s2, 'A')
    assert changed(repo, story, second) and not changed(repo, story, first)


def test_late_protagonist_stales_only_written_scenes_of_its_arc(tmp_path):
    # Owner's question: scenes written with the book hero in earlier arcs are not rewritten when a later arc gets a protagonist.
    repo, story, (s1, s2) = setup(tmp_path)
    structure(repo, story, s1, s2)
    first, _ = memory_version(repo, story, s1)
    second, _ = memory_version(repo, story, s2)
    structure(repo, story, s1, s2, 'B')
    assert changed(repo, story, second) and not changed(repo, story, first)


def test_late_protagonist_stales_only_the_brief_of_its_arc(tmp_path):
    # Cross-review: a writing-stage snapshot finds its scene through scene/title, not order/prefix.
    from storygen.providers.models import ProviderSettings, RoleSettings
    from storygen.storage.snapshots import build_dependency_snapshot
    repo, story, (s1, s2) = setup(tmp_path)
    structure(repo, story, s1, s2)
    def brief(scene):
        snap = build_dependency_snapshot(repo.context_view(story.id), scene.id, 'brief', RoleSettings(provider=ProviderSettings(model='fake')), [])
        assert not any(s.kind == 'order' and s.field == 'prefix' for s in snap.selectors)
        return repo.save_version(story.id, scene.id, 'brief', 'Бриф.', [], dependency_snapshot=snap)
    first, second = brief(s1), brief(s2)
    structure(repo, story, s1, s2, 'B')
    assert changed(repo, story, second) and not changed(repo, story, first)


def test_removing_explicit_protagonists_keeps_matching_scene_snapshots(tmp_path):
    repo, story, (s1, s2) = setup(tmp_path)
    structure(repo, story, s1, s2, 'B')
    first, snap = memory_version(repo, story, s1)
    assert tracked(snap) == {('scene', s1.id): ['A']}
    structure(repo, story, s1, s2)
    assert not changed(repo, story, first)
