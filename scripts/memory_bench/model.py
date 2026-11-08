"""Pure data for the memory retrieval bench: records, scene snapshots, selections, rendering, token measures.

Texts live only inside these objects; nothing here prints or serializes them."""
import math
from dataclasses import dataclass
from typing import Literal, Mapping, Sequence

from storygen.memory.journal import CATEGORIES
from storygen.token_budget.core import canonical

# Ukrainian tokenizer fertility (tokens per word) from ukrqualbench (https://github.com/grayodesa/ukrqualbench),
# measured on the UA-GEC 2.1.3 gec-only test target side: 238 096 characters, 35 122 words.
UA_CHARS_PER_WORD = 238096 / 35122
FERTILITY = {'qwen3': 3.38, 'claude': 2.96, 'deepseek': 2.94, 'gpt': 2.38, 'gemma': 2.26, 'lapa': 1.53}
DEFAULT_TOKENIZER = 'qwen3'  # the project's local models are Qwen; also the most pessimistic ratio


def chars_per_token(tokenizer: str) -> float:
    return UA_CHARS_PER_WORD / FERTILITY[tokenizer]


_ratio = chars_per_token(DEFAULT_TOKENIZER)


def set_tokenizer(tokenizer: str) -> float:
    """Select the realistic chars-per-token ratio for this process (CLI flag); returns it."""
    global _ratio
    _ratio = chars_per_token(tokenizer)
    return _ratio


def realistic_ratio() -> float:
    return _ratio

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
    atmosphere_ids: tuple[str, ...] = ()


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
    return math.ceil(len(text) / _ratio)
