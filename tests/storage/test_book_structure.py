import sqlite3

import pytest

from storygen.book.structure import effective_structure
from storygen.domain import RevisionConflict, SceneCreate, StoryCreate
from storygen.storage.book_structure import assign_scene, clear_structure, put_structure
from storygen.storage.integrity import check_integrity
from storygen.storage.repository import Repository


def setup(tmp_path, n=3):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    scenes = [repo.create_scene(story.id, SceneCreate(title=f'Scene {i+1}')) for i in range(n)]
    return repo, repo.get_story(story.id), scenes


def two_parts():
    return [{'id': 'p1', 'title': 'Перша', 'arcs': [{'id': 'a1', 'title': 'Ранок'}, {'id': 'a2', 'title': ''}]},
            {'id': 'p2', 'title': 'Друга', 'arcs': [{'id': 'b1', 'title': ''}]}]


def structured(tmp_path, n=3):
    repo, story, scenes = setup(tmp_path, n)
    arcs = ['a1', 'a2', 'b1'][:n] + ['b1'] * max(0, n - 3)
    story = put_structure(repo, story.id, two_parts(), {s.id: a for s, a in zip(scenes, arcs)}, story.revision)
    return repo, story, scenes


def view(repo, story_id):
    return effective_structure(repo.get_story(story_id), repo.list_scenes(story_id, include_trashed=True))


def test_put_structure_saves_parts_and_bumps_revision(tmp_path):
    repo, story, scenes = setup(tmp_path)
    saved = put_structure(repo, story.id, two_parts(), {scenes[0].id: 'a1', scenes[1].id: 'a2', scenes[2].id: 'b1'}, story.revision)
    assert saved.revision == story.revision + 1
    assert [p.id for p in saved.book_structure.parts] == ['p1', 'p2']
    assert view(repo, story.id).kind == 'structured'


def test_put_structure_gives_ids_to_new_items(tmp_path):
    repo, story, scenes = setup(tmp_path, 1)
    saved = put_structure(repo, story.id, [{'id': None, 'title': 'Х', 'arcs': [{'id': None, 'title': ''}]}], {}, story.revision)
    arc = saved.book_structure.parts[0].arcs[0].id
    assert arc and saved.book_structure.parts[0].id
    assert saved.scene_arcs == {scenes[0].id: arc}


def test_put_structure_conflict_writes_nothing(tmp_path):
    repo, story, scenes = setup(tmp_path)
    with pytest.raises(RevisionConflict):
        put_structure(repo, story.id, two_parts(), {s.id: 'a1' for s in scenes}, story.revision - 1)
    assert repo.get_story(story.id) == story


def test_put_structure_rejects_mixed_parts(tmp_path):
    repo, story, scenes = setup(tmp_path)
    with pytest.raises(ValueError, match='Scene 2'):
        put_structure(repo, story.id, two_parts(), {scenes[0].id: 'b1', scenes[1].id: 'a1', scenes[2].id: 'a2'}, story.revision)
    assert repo.get_story(story.id) == story


def test_put_structure_rejects_part_without_arcs(tmp_path):
    repo, story, scenes = setup(tmp_path)
    parts = two_parts() + [{'id': 'p3', 'title': '', 'arcs': []}]
    with pytest.raises(ValueError):
        put_structure(repo, story.id, parts, {s.id: 'a1' for s in scenes}, story.revision)
    assert repo.get_story(story.id) == story


def test_put_structure_rejects_unknown_arc_and_unassigned_scene(tmp_path):
    repo, story, scenes = setup(tmp_path)
    with pytest.raises(ValueError):
        put_structure(repo, story.id, two_parts(), {scenes[0].id: 'zz', scenes[1].id: 'a1', scenes[2].id: 'a1'}, story.revision)
    with pytest.raises(ValueError):
        put_structure(repo, story.id, [{'id': 'p1', 'arcs': [{'id': 'a1'}, {'id': 'a2'}]}], {scenes[0].id: 'a1'}, story.revision)


def test_new_scene_takes_arc_of_previous(tmp_path):
    repo, story, scenes = structured(tmp_path)
    last = repo.create_scene(story.id, SceneCreate(title='End'))
    middle = repo.create_scene(story.id, SceneCreate(title='Middle', position=1))
    arcs = repo.get_story(story.id).scene_arcs
    assert arcs[last.id] == 'b1' and arcs[middle.id] == 'a1'
    first = repo.create_scene(story.id, SceneCreate(title='First', position=0))
    assert repo.get_story(story.id).scene_arcs[first.id] == 'a1'


def test_new_scene_in_flat_book_has_no_binding(tmp_path):
    repo, story, _ = setup(tmp_path)
    repo.create_scene(story.id, SceneCreate(title='More'))
    assert repo.get_story(story.id).scene_arcs == {}


def test_reorder_that_mixes_arcs_is_refused(tmp_path):
    repo, story, scenes = structured(tmp_path)
    with pytest.raises(ValueError, match='Scene'):
        repo.reorder_scenes(story.id, [scenes[2].id, scenes[0].id, scenes[1].id], story.revision)
    assert [s.id for s in repo.list_scenes(story.id)] == [s.id for s in scenes]
    assert repo.get_story(story.id).revision == story.revision


def test_restore_scene_whose_arc_was_removed_takes_previous_arc(tmp_path):
    repo, story, scenes = structured(tmp_path)
    repo.set_scene_trashed(story.id, scenes[1].id, repo.get_scene(scenes[1].id).revision, restore=False)
    story = repo.get_story(story.id)
    parts = [{'id': 'p1', 'title': 'Перша', 'arcs': [{'id': 'a1', 'title': 'Ранок'}]}, two_parts()[1]]
    story = put_structure(repo, story.id, parts, {scenes[0].id: 'a1', scenes[2].id: 'b1'}, story.revision)
    assert scenes[1].id not in story.scene_arcs
    trashed = repo.get_scene(scenes[1].id, include_trashed=True)
    repo.set_scene_trashed(story.id, scenes[1].id, trashed.revision, restore=True)
    after = repo.get_story(story.id)
    assert after.scene_arcs[scenes[1].id] == 'a1'


def test_restore_never_breaks_sequence(tmp_path):
    repo, story, scenes = structured(tmp_path, 4)
    # Scene 2 (arc a2) goes to the trash; then scene 4 (b1) moves before scene 3, and scene 2 comes back at position 1.
    repo.set_scene_trashed(story.id, scenes[1].id, repo.get_scene(scenes[1].id).revision, restore=False)
    story = repo.get_story(story.id)
    story = assign_scene(repo, story.id, scenes[2].id, 'a1', story.revision)
    trashed = repo.get_scene(scenes[1].id, include_trashed=True)
    repo.set_scene_trashed(story.id, scenes[1].id, trashed.revision, restore=True)
    after = repo.get_story(story.id)
    # Arcs of a part may interleave (project 2): the restored scene keeps its arc a2 between two a1 scenes.
    assert after.scene_arcs[scenes[1].id] == 'a2'


def test_trash_keeps_binding(tmp_path):
    repo, story, scenes = structured(tmp_path)
    repo.set_scene_trashed(story.id, scenes[1].id, repo.get_scene(scenes[1].id).revision, restore=False)
    assert repo.get_story(story.id).scene_arcs[scenes[1].id] == 'a2'


def test_assign_scene_checks_sequence_and_revision(tmp_path):
    repo, story, scenes = structured(tmp_path)
    with pytest.raises(ValueError):
        assign_scene(repo, story.id, scenes[0].id, 'b1', story.revision)
    with pytest.raises(RevisionConflict):
        assign_scene(repo, story.id, scenes[1].id, 'a1', story.revision - 1)
    saved = assign_scene(repo, story.id, scenes[1].id, 'a1', story.revision)
    assert saved.scene_arcs[scenes[1].id] == 'a1' and saved.revision == story.revision + 1


def test_clear_structure_returns_flat(tmp_path):
    repo, story, scenes = structured(tmp_path)
    saved = clear_structure(repo, story.id, story.revision)
    assert saved.book_structure is None and saved.scene_arcs == {}
    assert view(repo, story.id).kind == 'flat'


def test_fsck_reports_broken_structure_as_limitation(tmp_path):
    repo, story, scenes = structured(tmp_path)
    broken = repo.get_story(story.id).model_copy(update={'scene_arcs': {scenes[0].id: 'b1', scenes[1].id: 'a1', scenes[2].id: 'gone'}})
    db = sqlite3.connect(tmp_path / 'storygen.sqlite3')
    db.execute('UPDATE stories SET payload=? WHERE id=?', (broken.model_dump_json(), story.id))
    db.commit()
    db.close()
    report = check_integrity(tmp_path)
    assert not report.issues
    assert any('book_structure_parts_mixed' in item for item in report.limitations)
    assert any('book_structure_unknown_arc' in item for item in report.limitations)
