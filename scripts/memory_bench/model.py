"""Pure data for the memory retrieval bench: records, scene snapshots, selections, rendering, token measures.

Texts live only inside these objects; nothing here prints or serializes them."""
import math
from dataclasses import dataclass
from typing import Literal, Mapping, Sequence

from storygen.memory.journal import CATEGORIES
from storygen.token_budget.core import canonical

# Realistic ratio from docs/research/2026-10-26-local-token-counting.md: one real request measured 13 590 tokens
# for a 62 710-byte conservative estimate (~4.6 UTF-8 bytes per token). Mostly Cyrillic text is ~2 bytes per char,
# so ~2.3 chars per token; ASCII JSON overhead only raises it, so 2.3 is the conservative edge.
CHARS_PER_TOKEN = 2.3

LABELS = {'facts': 'ФАКТИ', 'character_states': 'ПОТОЧНІ СТАНИ', 'open_threads': 'ВІДКРИТІ ЛІНІЇ', 'timeline': 'ХРОНОЛОГІЯ'}


@dataclass(frozen=True)
class Record:
    claim_id: str
    category: str
    text: str
    character_ids: tuple[str, ...]
    source_scene: int | None
    last_changed_scene: int | None
    timeline_kind: Literal['timeline', 'retired_thread'] | None = None


@dataclass(frozen=True)
class SceneInput:
    scene_id: str
    number: int
    cast: tuple[str, ...]
    plan_text: str
    prose_text: str
    records: tuple[Record, ...]
    timeline: tuple[Record, ...]
    protagonist: str
    names: Mapping[str, str]
    targets: frozenset[str]
    first_meetings: int


@dataclass(frozen=True)
class Selection:
    strategy: str
    record_ids: tuple[str, ...]
    layers: Mapping[str, int]
    chars: int
    tokens_conservative: int
    tokens_realistic: int
    overflow: bool
    dropped_by_budget: int


def render(records: Sequence[Record], timeline: Sequence[Record], summary_chars: int = 0) -> str:
    """Same layout as storygen.memory.projection.project_memory."""
    sections = []
    for category in CATEGORIES:
        if category == 'timeline':
            lines = ['— ' + (f'Сцена {r.source_scene}: ' if r.source_scene is not None else '') + r.text for r in timeline]
            if summary_chars > 0:
                lines.insert(0, '— ' + 'x' * summary_chars)
        else:
            lines = ['— ' + r.text for r in records if r.category == category]
        sections.append(LABELS[category] + '\n' + ('\n'.join(lines) if lines else 'Немає.'))
    return '\n\n'.join(sections)


def tokens_conservative(text: str) -> int:
    """utf8_body_conservative fallback of storygen.token_budget.core.estimate, applied to one section."""
    return len(canonical(text).encode('utf-8')) + 256


def tokens_realistic(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN)
