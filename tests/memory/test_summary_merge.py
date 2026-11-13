"""MEMORY-SUMMARY with interleaved arcs (MEMORY-MERGE-S05): a part summary reads the memory of the end of its part."""
import pytest

from storygen.generation.timeline_summary import block_inputs, end_of_part_memory
from storygen.memory.summaries import block_state
from storygen.memory.summary_blocks import summary_blocks
from storygen.storage.memory_merges import merge_point, save_merge
from tests.memory.merge_helpers import arc_book


def confirm(repo, story, point):
    memory_ids = [repo.get_scene(h).heads['memory'] for h in point.heads]
    return save_merge(repo, story.id, point.key, {}, repo.get_story(story.id).revision, memory_ids)


def test_part_with_two_heads_needs_the_merge_for_its_summary(tmp_path):
    repo, story, scenes = arc_book(tmp_path, 'A B A B C', [['A', 'B'], ['C']])
    view = repo.context_view(story.id)
    block = summary_blocks(story, scenes)[0]
    assert block.scene_ids == tuple(s.id for s in scenes[:4])
    with pytest.raises(ValueError, match='злиття'):
        block_inputs(view, story, scenes, block)
    story, merge_id = confirm(repo, story, merge_point(story, scenes, scene_id=scenes[4].id))
    view = repo.context_view(story.id)
    assert end_of_part_memory(view, story, repo.list_scenes(story.id), block) == merge_id
    assert merge_id in block_inputs(view, story, repo.list_scenes(story.id), block)


def test_last_part_summary_reads_the_book_end_merge(tmp_path):
    repo, story, scenes = arc_book(tmp_path, 'Z A B A B', [['Z'], ['A', 'B']])
    block = summary_blocks(story, scenes)[1]
    with pytest.raises(ValueError, match='злиття'):
        block_inputs(repo.context_view(story.id), story, scenes, block)
    story, merge_id = confirm(repo, story, merge_point(story, scenes, book_end=True))
    assert end_of_part_memory(repo.context_view(story.id), story, repo.list_scenes(story.id), block) == merge_id


def test_single_head_part_is_unchanged(tmp_path):
    repo, story, scenes = arc_book(tmp_path, 'A A B B C', [['A', 'B'], ['C']])
    view = repo.context_view(story.id)
    block = summary_blocks(story, scenes)[0]
    assert end_of_part_memory(view, story, scenes, block) == scenes[3].heads['memory']
    assert block_inputs(view, story, scenes, block) == [s.heads['memory'] for s in scenes[:4]]
    assert block_state(view, story, scenes, block)[0] == 'none'
