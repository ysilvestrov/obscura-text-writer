"""MEMORY-SUMMARY-S06 (storage): summary versions, heads with CAS, author corrections and fsck."""
import json

import pytest

from storygen.domain import RevisionConflict
from storygen.memory.summary_blocks import summary_blocks
from storygen.storage.integrity import check_integrity
from storygen.storage.timeline_summaries import publish_summary, read_summary, save_author_summary, save_summary_version
from tests.memory.summary_helpers import long_story


def model_summary(repo, story, block, text='Підсумок першого блоку.'):
    scenes = repo.list_scenes(story.id)
    memory_ids = [s.heads['memory'] for s in scenes if s.id in block.scene_ids]
    return save_summary_version(repo, story.id, block, memory_ids, text, 'model', 'uk')


def test_publish_sets_the_head_with_cas(tmp_path):
    repo, story = long_story(tmp_path, 12)
    block = summary_blocks(story, repo.list_scenes(story.id))[0]
    ref = model_summary(repo, story, block)
    payload = read_summary(repo, ref.id)
    assert payload['block_key'] == 'range:1-10' and payload['origin'] == 'model' and payload['scene_ids'] == list(block.scene_ids)
    assert payload['memory_version_id'] == repo.list_scenes(story.id)[9].heads['memory']
    assert len(ref.input_refs) == 10
    with pytest.raises(RevisionConflict):
        publish_summary(repo, story.id, block.key, ref.id, story.revision - 1)
    assert repo.get_story(story.id).timeline_summary_heads == {}
    updated = publish_summary(repo, story.id, block.key, ref.id, repo.get_story(story.id).revision)
    assert updated.timeline_summary_heads == {'range:1-10': ref.id} and updated.revision == story.revision + 1


def test_publish_refuses_a_foreign_block_or_kind(tmp_path):
    repo, story = long_story(tmp_path, 12)
    block = summary_blocks(story, repo.list_scenes(story.id))[0]
    ref = model_summary(repo, story, block)
    with pytest.raises(ValueError):
        publish_summary(repo, story.id, 'range:11-20', ref.id, story.revision)
    memory_id = repo.list_scenes(story.id)[0].heads['memory']
    with pytest.raises(ValueError):
        publish_summary(repo, story.id, block.key, memory_id, story.revision)


def test_new_head_makes_texts_built_with_the_old_one_stale(tmp_path):
    repo, story = long_story(tmp_path, 12)
    block = summary_blocks(story, repo.list_scenes(story.id))[0]
    old = model_summary(repo, story, block)
    publish_summary(repo, story.id, block.key, old.id, repo.get_story(story.id).revision)
    scene = repo.list_scenes(story.id)[11]
    built = repo.save_version(story.id, scene.id, 'brief', '{}', [old.id])
    new = model_summary(repo, story, block, 'Інший підсумок першого блоку.')
    publish_summary(repo, story.id, block.key, new.id, repo.get_story(story.id).revision)
    assert repo.get_version(built.id).stale and not repo.get_version(new.id).stale


def test_author_correction_is_a_new_version_with_cas_on_the_head(tmp_path):
    repo, story = long_story(tmp_path, 12)
    block = summary_blocks(story, repo.list_scenes(story.id))[0]
    ref = model_summary(repo, story, block)
    story = publish_summary(repo, story.id, block.key, ref.id, repo.get_story(story.id).revision)
    with pytest.raises(RevisionConflict):
        save_author_summary(repo, story.id, block.key, 'Виправлено.', 'other-version', story.revision)
    with pytest.raises(ValueError, match='1200'):
        save_author_summary(repo, story.id, block.key, 'а' * 1201, ref.id, story.revision)
    with pytest.raises(ValueError):
        save_author_summary(repo, story.id, block.key, '   ', ref.id, story.revision)
    story = save_author_summary(repo, story.id, block.key, 'Виправлено автором.', ref.id, story.revision)
    head = story.timeline_summary_heads[block.key]
    payload = read_summary(repo, head)
    assert head != ref.id and payload['origin'] == 'author' and payload['text'] == 'Виправлено автором.'
    assert payload['memory_version_id'] == read_summary(repo, ref.id)['memory_version_id']
    assert ref.id in repo.get_version(head).input_refs


def test_prose_change_in_the_block_makes_the_summary_stale(tmp_path):
    repo, story = long_story(tmp_path, 12)
    block = summary_blocks(story, repo.list_scenes(story.id))[0]
    ref = model_summary(repo, story, block)
    from storygen.generation.dependencies import save_manual_prose
    scene = repo.list_scenes(story.id)[4]
    save_manual_prose(repo, scene.id, 'Нова проза п’ятої сцени.', repo.get_scene(scene.id).revision)
    assert repo.get_version(ref.id).stale


def test_fsck_reports_a_head_on_a_wrong_version(tmp_path):
    repo, story = long_story(tmp_path, 12)
    memory_id = repo.list_scenes(story.id)[0].heads['memory']
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        current = repo._active_story(db, story.id)
        repo._save_story(db, current.model_copy(update={'timeline_summary_heads': {'range:1-10': memory_id}}))
    report = check_integrity(tmp_path)
    assert any(issue.code == 'invalid_summary_head' for issue in report.issues)
