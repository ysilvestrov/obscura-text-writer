"""Usability of timeline summaries (#68, MEMORY-SUMMARY-S04): computed at every context build, never stored.

A head is usable for scene n when its block is complete before n, its scene IDs equal the current block, its memory version
is the selected memory of the block's last scene, and neither that memory nor the summary is stale."""
import json
from dataclasses import dataclass

from ..generation.context_labels import label
from .summary_blocks import replaces, summary_blocks


@dataclass(frozen=True)
class SummaryCandidate:
    block_key: str
    version_id: str
    first_number: int
    last_number: int
    line: str


@dataclass(frozen=True)
class StaleSummary:
    block_key: str
    first_number: int
    last_number: int
    reason: str


def summary_line(block, text: str, language: str) -> str:
    if block.part:
        return '— ' + label('summary_part', language, title=block.title, first=block.first_number, last=block.last_number, text=text)
    return '— ' + label('summary_scenes', language, first=block.first_number, last=block.last_number, text=text)


def block_state(view, story, scenes, block):
    """('none'|'fresh'|'stale', reason, payload or None) for the block's current head."""
    head = story.timeline_summary_heads.get(block.key)
    if not head:
        return 'none', None, None
    try:
        ref = view.get_version(head)
        payload = json.loads(view.read_text(head))
    except (KeyError, ValueError, OSError):
        return 'stale', 'stale', None
    by_id = {s.id: s for s in scenes}
    memory_id = by_id[block.scene_ids[-1]].heads.get('memory') if block.scene_ids[-1] in by_id else None
    if tuple(payload.get('scene_ids', ())) != block.scene_ids:
        return 'stale', 'blocks_changed', payload
    if payload.get('memory_version_id') != memory_id:
        return 'stale', 'memory_changed', payload
    if ref.stale or view.get_version(memory_id).stale:
        return 'stale', 'stale', payload
    return 'fresh', None, payload


def usable_summaries(view, story, scenes, scene_number: int, language: str):
    """Candidates for the request of scene n (blocks part of which left n's window) and unusable heads of earlier blocks."""
    candidates, stale = [], []
    for block in summary_blocks(story, scenes):
        if block.last_number >= scene_number or block.key not in story.timeline_summary_heads:
            continue
        state, reason, payload = block_state(view, story, scenes, block)
        if state == 'fresh':
            if replaces(block, scene_number):
                candidates.append(SummaryCandidate(block.key, story.timeline_summary_heads[block.key], block.first_number,
                                                   block.last_number, summary_line(block, payload['text'], language)))
        else:
            stale.append(StaleSummary(block.key, block.first_number, block.last_number, reason))
    return candidates, stale
