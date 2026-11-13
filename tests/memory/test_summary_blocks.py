"""MEMORY-SUMMARY-S01: blocks of timeline summaries — a part of a structured book, ten scenes of a flat one."""
import json

from storygen.domain import Arc, BookStructure, Part, SceneCreate, Story, StoryCreate
from storygen.memory.summary_blocks import limit, recommended, replaces, summary_blocks
from storygen.storage.repository import Repository


def flat(tmp_path, count):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    for i in range(count):
        repo.create_scene(story.id, SceneCreate(title=f'С{i + 1}'))
    return repo, repo.get_story(story.id)


def test_flat_book_has_full_blocks_of_ten(tmp_path):
    repo, story = flat(tmp_path, 25)
    scenes = repo.list_scenes(story.id)
    blocks = summary_blocks(story, scenes)
    assert [b.key for b in blocks] == ['range:1-10', 'range:11-20']
    assert blocks[0].scene_ids == tuple(s.id for s in scenes[:10])
    assert (blocks[1].first_number, blocks[1].last_number, blocks[1].part) == (11, 20, False)
    assert limit(blocks[0]) == 1200


def test_trashed_scenes_do_not_count(tmp_path):
    repo, story = flat(tmp_path, 11)
    scenes = repo.list_scenes(story.id)
    trashed = [s.model_copy(update={'trashed_at': '2026-11-12T00:00:00Z'}) for s in scenes[:2]]
    assert summary_blocks(story, trashed + scenes[2:]) == []
    assert summary_blocks(story, trashed[:1] + scenes[1:])[0].scene_ids == tuple(s.id for s in scenes[1:])


def test_structured_book_has_a_block_per_part(tmp_path):
    repo, story = flat(tmp_path, 5)
    scenes = repo.list_scenes(story.id)
    structure = BookStructure(parts=[Part(id='p1', title='Місто', arcs=[Arc(id='a1')]), Part(id='p2', arcs=[Arc(id='b1')]),
                                     Part(id='p3', arcs=[Arc(id='c1')])])
    arcs = {s.id: 'a1' for s in scenes[:3]} | {s.id: 'b1' for s in scenes[3:]}
    story = story.model_copy(update={'book_structure': structure, 'scene_arcs': arcs})
    blocks = summary_blocks(story, scenes)
    assert [(b.key, b.title, b.first_number, b.last_number, b.part) for b in blocks] == [
        ('part:p1', 'Місто', 1, 3, True), ('part:p2', 'Частина 2', 4, 5, True)]
    assert limit(blocks[0]) == 2000


def test_recommendation_and_replacement_thresholds(tmp_path):
    repo, story = flat(tmp_path, 30)
    first, second = summary_blocks(story, repo.list_scenes(story.id))[:2]
    assert not recommended(first, 20) and recommended(first, 21)
    assert not recommended(second, 30) and recommended(second, 31)
    assert not replaces(first, 21) and replaces(first, 22) and replaces(first, 23)
    assert not replaces(second, 31) and replaces(second, 32)


def test_old_story_payload_reads_without_heads():
    payload = json.loads(Story(id='s', title='Т').model_dump_json())
    payload.pop('timeline_summary_heads')
    assert Story.model_validate(payload).timeline_summary_heads == {}


def test_a_part_with_a_gap_has_no_block(tmp_path):
    # Cross-review #2: a part whose scenes are not contiguous (an invalid transient structure) gets no block, so a
    # summary never claims the scenes of another part in between.
    repo, story = flat(tmp_path, 4)
    scenes = repo.list_scenes(story.id)
    structure = BookStructure(parts=[Part(id='p1', arcs=[Arc(id='a1')]), Part(id='p2', arcs=[Arc(id='b1')])])
    arcs = dict(zip([s.id for s in scenes], ['a1', 'b1', 'a1', 'b1']))
    story = story.model_copy(update={'book_structure': structure, 'scene_arcs': arcs})
    assert summary_blocks(story, scenes) == []
    arcs[scenes[1].id] = 'a1'
    story = story.model_copy(update={'scene_arcs': arcs})
    assert [(b.key, b.first_number, b.last_number) for b in summary_blocks(story, scenes)] == [('part:p1', 1, 3), ('part:p2', 4, 4)]
