"""STORY-TIME-S06: a book without flashbacks gets the same requests, fingerprints and snapshots as before (neutral examples).

The rest of the invariance is the existing suite, which passes unchanged (as for BOOK-LINEAGE-S01)."""
import json

from storygen.generation.context import build_context
from tests.memory.merge_helpers import arc_book
from tests.memory.test_core_review import role, two_scenes


def contexts(repo, scenes, stages):
    return [build_context(repo, scene.id, stage, role()) for scene in scenes for stage in stages]


def books(tmp_path):
    repo, story, scenes = arc_book(tmp_path / 'arcs', 'A B A', [['A', 'B']])
    flat, _, s1, s2, _, _ = two_scenes(tmp_path / 'flat')
    return [(repo, scenes), (flat, [s1, s2])]


def test_book_without_flashbacks_writes_nothing_new(tmp_path):
    for repo, scenes in books(tmp_path):
        for context in contexts(repo, scenes, ['brief', 'memory']):
            assert not any(s.field in {'flashback', 'flashback_facts'} for s in context.dependency_snapshot.selectors)
            assert 'МИНУЛЕ ІНШИХ АРОК' not in context.user_text
            if context.stage == 'memory':
                assert 'flashback' not in json.loads(context.fragments['memory_schema_bounds'])

