"""Blocks of timeline summaries (#68, MEMORY-SUMMARY-S01): a part of a structured book, ten active scenes of a flat one.

A scene number is the position among active scenes + 1, the same number the timeline lines carry. The last incomplete
block of a flat book has no summary: it always lies inside the timeline window."""
from dataclasses import dataclass

from .selection import TIMELINE_WINDOW

BLOCK_SIZE = 10
BLOCK_LIMIT = 1200
PART_LIMIT = 2000


@dataclass(frozen=True)
class SummaryBlock:
    key: str
    title: str
    scene_ids: tuple[str, ...]
    first_number: int
    last_number: int
    part: bool


def summary_blocks(story, scenes) -> list[SummaryBlock]:
    from ..book.structure import effective_structure
    active = sorted((s for s in scenes if not s.trashed_at), key=lambda s: s.position)
    structure = effective_structure(story, active)
    if structure.kind == 'structured':
        word = 'Part' if story.language == 'en' else 'Частина'
        blocks = []
        for index, part in enumerate(structure.parts, 1):
            numbers = [(n, s.id) for n, s in enumerate(active, 1) if structure.part_of_arc.get(structure.arc_of.get(s.id)) == part.id]
            if numbers:
                blocks.append(SummaryBlock(f'part:{part.id}', part.title or f'{word} {index}', tuple(i for _, i in numbers),
                                           numbers[0][0], numbers[-1][0], True))
        return blocks
    return [SummaryBlock(f'range:{start + 1}-{start + BLOCK_SIZE}', '', tuple(s.id for s in active[start:start + BLOCK_SIZE]),
                         start + 1, start + BLOCK_SIZE, False)
            for start in range(0, len(active) - BLOCK_SIZE + 1, BLOCK_SIZE)]


def limit(block: SummaryBlock) -> int:
    return PART_LIMIT if block.part else BLOCK_LIMIT


def recommended(block: SummaryBlock, last_memory_number: int) -> bool:
    """The button is active once the next scene after the last one with memory no longer sees the block's first scene."""
    return block.first_number < last_memory_number + 1 - TIMELINE_WINDOW


def replaces(block: SummaryBlock, scene_number: int) -> bool:
    """A usable summary replaces the whole block in the request of scene n once part of the block left n's window."""
    return block.first_number < scene_number - TIMELINE_WINDOW and block.last_number < scene_number
