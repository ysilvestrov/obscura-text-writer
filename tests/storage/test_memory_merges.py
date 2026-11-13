"""MEMORY-MERGE-S03/S05 (storage): merge points, memory_merge versions, heads with CAS, staleness and fsck."""
import json
import sqlite3

import pytest

from storygen.domain import RevisionConflict
from storygen.memory.journal import load_memory, replay_memory
from storygen.storage.integrity import check_integrity
from storygen.storage.memory_merges import merge_point, merge_state, read_merge, save_merge, usable_merge
from tests.memory.merge_helpers import arc_book, save_scene_journal, slot_add, slot_update


def coat_events(n, prose_id, previous):
    """Scene 1 dresses Anna in a coat; scenes 2 and 3 (arcs A and B) change it differently."""
    if n == 1:
        return [slot_add('Анна в пальті', prose_id)]
    record = next(e for e in replay_memory(previous).values() if e.slot == 'clothing')
    return [slot_update(record, {2: 'Анна в куртці', 3: 'Анна в плащі'}.get(n, f'Анна {n}'), prose_id)]


def meeting_book(tmp_path):
    # Part 1: one arc Z (scene 1). Part 2: A and B interleave (2 A, 3 B), scene 4 is their meeting.
    return arc_book(tmp_path, 'Z A B A+B', [['Z'], ['A', 'B']], coat_events)


def point(repo, story, n):
    scenes = repo.list_scenes(story.id)
    return merge_point(story, scenes, scene_id=scenes[n - 1].id)


def test_merge_point_of_a_meeting_scene(tmp_path):
    repo, story, scenes = meeting_book(tmp_path)
    found = point(repo, story, 4)
    assert found.heads == (scenes[1].id, scenes[2].id) and found.target_scene_ids == (scenes[3].id,)
    assert point(repo, story, 3) is None


def test_state_lists_the_conflict(tmp_path):
    repo, story, scenes = meeting_book(tmp_path)
    state = merge_state(repo.context_view(story.id), story, scenes, point(repo, story, 4))
    assert state['state'] == 'none'
    assert [(c['key'], c['values']) for c in state['conflicts']] == [
        ('slot:c1:clothing', {scenes[1].id: 'Анна в куртці', scenes[2].id: 'Анна в плащі'})]


def test_save_publishes_version_and_head(tmp_path):
    repo, story, scenes = meeting_book(tmp_path)
    found = point(repo, story, 4)
    memory_ids = [scenes[1].heads['memory'], scenes[2].heads['memory']]
    story, version_id = save_merge(repo, story.id, found.key, {'slot:c1:clothing': {'choice': scenes[2].id}}, story.revision, memory_ids)
    ref = repo.get_version(version_id)
    assert ref.scene_id is None and ref.kind == 'memory_merge' and sorted(ref.input_refs) == sorted(memory_ids)
    assert story.memory_merge_heads == {found.key: version_id}
    payload = read_merge(repo, version_id)
    journal = load_memory(json.dumps(payload['journal']))
    assert journal.source_prose_ids == [s.heads['prose'] for s in scenes[:3]]
    assert any(e.text == 'Анна в плащі' for e in replay_memory(journal).values())
    assert usable_merge(repo.context_view(story.id), story, repo.list_scenes(story.id), found) == version_id


def test_stale_head_memory_blocks_save(tmp_path):
    repo, story, scenes = meeting_book(tmp_path)
    prose = repo.save_version(story.id, scenes[0].id, 'manual', 'Сцена 1. Анна йде містом. Інший текст.', [])
    repo.set_head(scenes[0].id, 'prose', prose.id, repo.get_scene(scenes[0].id).revision)
    story = repo.get_story(story.id)
    state = merge_state(repo.context_view(story.id), story, repo.list_scenes(story.id), point(repo, story, 4))
    assert state['state'] == 'blocked' and 'застаріла' in state['reason']
    with pytest.raises(ValueError):
        save_merge(repo, story.id, state['key'], {}, story.revision, [h['memory_id'] for h in state['heads']])


def test_revision_conflict_keeps_nothing(tmp_path):
    repo, story, scenes = meeting_book(tmp_path)
    found = point(repo, story, 4)
    memory_ids = [scenes[1].heads['memory'], scenes[2].heads['memory']]
    with pytest.raises(RevisionConflict):
        save_merge(repo, story.id, found.key, {'slot:c1:clothing': {'choice': scenes[1].id}}, story.revision - 1, memory_ids)
    with pytest.raises(RevisionConflict):
        save_merge(repo, story.id, found.key, {'slot:c1:clothing': {'choice': scenes[1].id}}, story.revision, memory_ids[::-1])
    assert repo.get_story(story.id).memory_merge_heads == {}


def test_new_head_memory_makes_merge_unusable_and_carries_decisions(tmp_path):
    repo, story, scenes = meeting_book(tmp_path)
    found = point(repo, story, 4)
    decisions = {'slot:c1:clothing': {'choice': 'author', 'text': 'Анна в дощовику'}}
    story, version_id = save_merge(repo, story.id, found.key, decisions, story.revision,
                                   [scenes[1].heads['memory'], scenes[2].heads['memory']])
    # Scene 3 gets a new memory with the same coat value and one more fact: the conflict is the same.
    previous = load_memory(repo.read_text(scenes[0].heads['memory']))
    record = next(e for e in replay_memory(previous).values() if e.slot == 'clothing')
    from tests.memory.merge_helpers import fact
    save_scene_journal(repo, repo.get_scene(scenes[2].id), previous,
                       [slot_update(record, 'Анна в плащі', scenes[2].heads['prose']), fact('Анна знайшла ключ', scenes[2].heads['prose'])])
    story = repo.get_story(story.id)
    view = repo.context_view(story.id)
    assert usable_merge(view, story, repo.list_scenes(story.id), found) is None
    state = merge_state(view, story, repo.list_scenes(story.id), found)
    assert state['state'] == 'stale' and state['carried'] == decisions


def test_old_payload_reads_empty_merge_heads(tmp_path):
    repo, story, _ = meeting_book(tmp_path)
    raw = json.loads(story.model_dump_json())
    raw.pop('memory_merge_heads')
    assert type(story).model_validate(raw).memory_merge_heads == {}


def test_fsck_reports_foreign_merge_head(tmp_path):
    repo, story, scenes = meeting_book(tmp_path)
    broken = story.model_copy(update={'memory_merge_heads': {'heads:x,y': scenes[0].heads['memory']}})
    db = sqlite3.connect(tmp_path / 'storygen.sqlite3')
    db.execute('UPDATE stories SET payload=? WHERE id=?', (broken.model_dump_json(), story.id))
    db.commit()
    db.close()
    assert any(issue.code == 'invalid_memory_merge_head' for issue in check_integrity(tmp_path).issues)


def test_merge_markers_follow_the_merge(tmp_path):
    # MEMORY-MERGE harness: the scene list marks the target scene of a point until its merge is confirmed.
    from storygen.storage.memory_merges import merge_markers
    repo, story, scenes = meeting_book(tmp_path)
    assert merge_markers(repo.context_view(story.id), story, scenes) == {scenes[3].id: 'required'}
    found = point(repo, story, 4)
    save_merge(repo, story.id, found.key, {'slot:c1:clothing': {'choice': scenes[1].id}}, story.revision,
               [repo.get_scene(h).heads['memory'] for h in found.heads])
    story = repo.get_story(story.id)
    assert merge_markers(repo.context_view(story.id), story, repo.list_scenes(story.id)) == {scenes[3].id: 'fresh'}
