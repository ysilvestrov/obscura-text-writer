"""CHARACTER-EXTRACT (R-51): pure logic of finding characters in prose by a model; no IO, no provider calls.

The runner (a later task) reads scenes in groups, shows the model short ids (`s<N>` scenes, `c<N>` catalogue cards) and
feeds every answer through `parse_extract` and `apply_group`; `finalize` turns the running state into the proposal."""
import json
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from ..memory.selection import MentionIndex, name_stems
from ..model_json import unwrap_model_json
from ..scene_description import name_key

SKIP_INPUT_LIMIT = "не вміщується в ліміт входу ролі «Пам'ять»"
PROTAGONIST_THRESHOLD = 1.0
PROTAGONIST_CANDIDATES = 3

_DASHES = frozenset('‐‑‒–—―−')
_APOSTROPHES = frozenset("’ʼ'`")
_QUOTES = frozenset('«»„“”"')
_EDGE = ' ."…'


# ---------------------------------------------------------------- quotes

def _spans(text: str) -> tuple[str, list[int], list[int]]:
    """Normalised text with, for each of its characters, the start and end of the original characters it came from."""
    out, starts, ends = [], [], []
    i, size = 0, len(text)
    while i < size:
        j = i + 1
        while j < size and unicodedata.combining(text[j]):
            j += 1
        for char in unicodedata.normalize('NFC', text[i:j]):
            if char == '*':
                continue  # Markdown emphasis is not prose
            if char.isspace():
                if out and out[-1] == ' ':
                    ends[-1] = j
                else:
                    out.append(' '); starts.append(i); ends.append(j)
                continue
            if char in _DASHES:
                char = '-'
            elif char in _APOSTROPHES:
                char = "'"
            elif char in _QUOTES:
                char = '"'
            for lowered in char.lower():
                out.append(lowered); starts.append(i); ends.append(j)
        i = j
    return ''.join(out), starts, ends


def normalize_with_map(text: str) -> tuple[str, list[int]]:
    """Normalised text (CHARACTER-EXTRACT rules) and, for each of its characters, its position in the original."""
    normalized, starts, _ = _spans(text)
    return normalized, starts


@dataclass(frozen=True)
class SceneProse:
    scene_id: str
    version_id: str
    text: str


@dataclass(frozen=True)
class QuoteHit:
    scene_id: str
    version_id: str
    quote: str  # the exact fragment of the original prose


def _prepare(scenes):
    return [(scene, *_spans(scene.text)) for scene in scenes]


def _find(prepared, quote: str) -> QuoteHit | None:
    needle = _spans(quote)[0].strip(_EDGE)
    if not needle:
        return None
    for scene, normalized, starts, ends in prepared:  # per scene: a quote never crosses a scene boundary
        at = normalized.find(needle)
        if at >= 0:
            return QuoteHit(scene.scene_id, scene.version_id, scene.text[starts[at]:ends[at + len(needle) - 1]])
    return None


def find_quote(scenes: list[SceneProse], quote: str) -> QuoteHit | None:
    return _find(_prepare(scenes), quote)


# ---------------------------------------------------------------- groups

def plan_groups(scenes: list[tuple[str, int, int]], group_words: int,
                fits: Callable[[list[str]], bool]) -> tuple[list[list[str]], list[tuple[str, str]]]:
    """Whole scenes, greedily, up to `group_words`; a scene over the budget is its own group. `scenes` are
    (scene_id, words, chars); a group that does not `fits` is halved, a single scene that does not fit is skipped."""
    raw, current, words = [], [], 0
    for scene_id, scene_words, _chars in scenes:
        if current and words + scene_words > group_words:
            raw.append(current); current, words = [], 0
        current.append(scene_id); words += scene_words
    if current:
        raw.append(current)
    groups, skipped = [], []

    def place(ids):
        if fits(ids):
            groups.append(ids)
        elif len(ids) == 1:
            skipped.append((ids[0], SKIP_INPUT_LIMIT))
        else:
            half = len(ids) // 2
            place(ids[:half]); place(ids[half:])
    for ids in raw:
        place(ids)
    return groups, skipped


# ---------------------------------------------------------------- response

_Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
_Quote = Annotated[str, StringConstraints(min_length=1, max_length=300)]


class _Part(BaseModel):
    model_config = ConfigDict(extra='ignore', strict=True, allow_inf_nan=False)


class NewCard(_Part):
    key: str = Field(min_length=1)
    name: _Name
    other_names: list[_Name] = Field(default_factory=list, max_length=10)
    quotes: list[_Quote] = Field(default_factory=list, max_length=2)  # a card left without quotes is dropped later


class CardUpdate(_Part):
    id: str
    other_names: list[_Name] = Field(default_factory=list, max_length=10)


class SceneCast(_Part):
    scene: str
    participants: list[str] = Field(default_factory=list)


class Candidate(_Part):
    id: str
    score: float = Field(ge=0, le=1)


class ExtractResponse(_Part):
    new_cards: list[NewCard] = Field(default_factory=list)
    card_updates: list[CardUpdate] = Field(default_factory=list)
    scenes: list[SceneCast] = Field(default_factory=list)
    protagonist_candidates: list[Candidate] = Field(default_factory=list, max_length=PROTAGONIST_CANDIDATES)

    # Over-limit values are trimmed, never a reason to lose the whole answer; only structural errors reject it.
    @field_validator('new_cards', mode='before')
    @classmethod
    def _trim_cards(cls, value):
        if not isinstance(value, list):
            return value
        result = []
        for item in value:
            if isinstance(item, dict):
                name = item.get('name')
                if isinstance(name, str) and not 1 <= len(name.strip()) <= 80:
                    continue
                item = {**item, 'other_names': _fitting(item.get('other_names', []), 1, 80, 10),
                        'quotes': _fitting(item.get('quotes', []), 1, 300, 2)}
            result.append(item)
        return result

    @field_validator('card_updates', mode='before')
    @classmethod
    def _trim_updates(cls, value):
        if not isinstance(value, list):
            return value
        return [{**item, 'other_names': _fitting(item.get('other_names', []), 1, 80, 10)} if isinstance(item, dict) else item
                for item in value]

    @field_validator('protagonist_candidates', mode='before')
    @classmethod
    def _trim_candidates(cls, value):
        if not isinstance(value, list):
            return value

        def out_of_range(item):
            score = item.get('score') if isinstance(item, dict) else None
            return isinstance(score, (int, float)) and not isinstance(score, bool) and not 0 <= score <= 1
        return [item for item in value if not out_of_range(item)][:PROTAGONIST_CANDIDATES]


def _fitting(items, low, high, limit):
    """The strings of a list within their length limits, the first `limit` of them; other types stay for validation."""
    if not isinstance(items, list):
        return items
    kept = [item for item in items if not isinstance(item, str) or low <= len(item.strip()) <= high]
    return kept[:limit]


def parse_extract(text: str) -> ExtractResponse:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Повторний ключ JSON')
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError('Нечислова константа JSON')
    try:
        return ExtractResponse.model_validate(
            json.loads(unwrap_model_json(text), object_pairs_hook=pairs, parse_constant=invalid_constant))
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValueError('Відповідь пошуку персонажів не відповідає JSON чи схемі') from exc


# ---------------------------------------------------------------- state

class NameChoice(BaseModel):
    name: str
    suggested: bool = True


class QuoteRef(BaseModel):
    version_id: str
    scene_id: str
    quote: str


class CatalogueCard(BaseModel):
    ref: str  # the id of an author card, or `new<N>` of a card found in this run
    name: str
    names: list[str] = Field(default_factory=list)  # every known name; may or may not repeat `name`
    existing: bool = False
    added_names: list[NameChoice] = Field(default_factory=list)  # names this run added to the card
    quotes: list[QuoteRef] = Field(default_factory=list)
    first_scene_id: str | None = None


class ExtractState(BaseModel):
    catalogue: list[CatalogueCard] = Field(default_factory=list)
    casts: dict[str, list[str]] = Field(default_factory=dict)
    scores: dict[str, float] = Field(default_factory=dict)
    skipped: list[tuple[str, str]] = Field(default_factory=list)
    groups_done: int = 0
    calls: int = 0
    scene_order: list[str] = Field(default_factory=list)  # every scene to read, in reading order: `s<N>` numbers


@dataclass(frozen=True)
class SceneMeta:
    scene_id: str
    cast_eligible: bool  # manual prose and no participants line in the plan
    cast: list[str]  # card ids in the scene cast now


def _others(card: CatalogueCard) -> list[str]:
    seen, result = {name_key(card.name)}, []
    for name in card.names:
        if name_key(name) not in seen:
            seen.add(name_key(name)); result.append(name)
    return result


def catalogue_text(state: ExtractState) -> str:
    lines = []
    for number, card in enumerate(state.catalogue, 1):
        others = _others(card)
        lines.append(f'c{number}: {card.name}' + (f" (інші імена: {', '.join(others)})" if others else ''))
    return '\n'.join(lines) or '(порожньо)'


def short_ids(state: ExtractState, group_scene_ids: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    """(`c<N>` -> card ref, `s<N>` -> scene id). Scene numbers count the scenes read in the book (`scene_order`)."""
    cards = {f'c{number}': card.ref for number, card in enumerate(state.catalogue, 1)}
    numbers = {scene_id: number for number, scene_id in enumerate(state.scene_order, 1)}
    for scene_id in group_scene_ids:  # a scene missing from the order still gets a number of its own
        numbers.setdefault(scene_id, len(numbers) + 1)
    return cards, {f's{numbers[scene_id]}': scene_id for scene_id in group_scene_ids}


# ---------------------------------------------------------------- applying one group

def _owner(state: ExtractState, name: str) -> CatalogueCard | None:
    key = name_key(name)
    for card in state.catalogue:
        if name_key(card.name) == key or any(name_key(known) == key for known in card.names):
            return card
    return None


def _add_names(state: ExtractState, card: CatalogueCard, names, index: MentionIndex) -> None:
    for name in names:
        stems = name_stems(name)
        if _owner(state, name) is not None or not stems or index.first(stems) is None:
            continue  # known to a card (this one included) or absent from the prose of the group
        card.names.append(name)
        card.added_names.append(NameChoice(name=name, suggested=not name[:1].islower()))


def apply_group(state: ExtractState, response: ExtractResponse, group: list[SceneProse], *,
                scene_numbers: Mapping[str, str], card_numbers: Mapping[str, str]) -> ExtractState:
    """The state after one group's response (CHARACTER-EXTRACT validation); `state` itself is not changed.
    `scene_numbers` maps `s<N>` to scene ids and `card_numbers` maps `c<N>` to card refs (see `short_ids`)."""
    result = state.model_copy(deep=True)
    prepared = _prepare(group)
    index = MentionIndex('\n\n'.join(scene.text for scene in group))
    by_ref = {card.ref: card for card in result.catalogue}
    refs = {short: ref for short, ref in card_numbers.items() if ref in by_ref}
    group_ids = {scene.scene_id for scene in group}
    keys: dict[str, str] = {}
    seen_keys: set[str] = set()
    for new in response.new_cards:
        if new.key in refs or new.key in seen_keys:
            continue  # a key that names a known card or an earlier new card is ambiguous: the card is not taken
        seen_keys.add(new.key)
        target = _owner(result, new.name)
        if target is not None:  # a duplicate: only its names count, its quotes are dropped
            _add_names(result, target, new.other_names, index)
            keys[new.key] = target.ref
            continue
        quotes: list[QuoteRef] = []
        for quote in new.quotes:
            hit = _find(prepared, quote)
            if hit and all(hit.quote != known.quote for known in quotes):
                quotes.append(QuoteRef(version_id=hit.version_id, scene_id=hit.scene_id, quote=hit.quote))
        if not quotes:
            continue  # a card without a verbatim quote is not proposed
        card = CatalogueCard(ref=f'new{1 + sum(not item.existing for item in result.catalogue)}', name=new.name,
                             names=[new.name], quotes=quotes, first_scene_id=quotes[0].scene_id)
        result.catalogue.append(card)
        _add_names(result, card, new.other_names, index)
        keys[new.key] = card.ref
        by_ref[card.ref] = card

    def resolve(short):
        return keys.get(short) or refs.get(short)
    for update in response.card_updates:
        card = by_ref.get(refs.get(update.id, ''))
        if card is not None:
            _add_names(result, card, update.other_names, index)
    for item in response.scenes:
        scene_id = scene_numbers.get(item.scene)
        if scene_id not in group_ids:
            continue
        cast = result.casts.setdefault(scene_id, [])
        for short in item.participants:
            ref = resolve(short)
            if ref and ref not in cast:
                cast.append(ref)
    best: dict[str, float] = {}
    for candidate in response.protagonist_candidates:
        ref = resolve(candidate.id)
        if ref:
            best[ref] = max(best.get(ref, 0.0), candidate.score)
    for ref, score in best.items():
        result.scores[ref] = result.scores.get(ref, 0.0) + score
    result.groups_done += 1
    return result


# ---------------------------------------------------------------- proposal

def finalize(state: ExtractState, scenes_meta: Mapping[str, SceneMeta], has_author_protagonist: bool) -> dict:
    """The proposal of CHARACTER-EXTRACT (spec 4.1) without `source`, `fingerprint`, `partial` and `cost_usd`."""
    names = lambda card: [item.model_dump() for item in card.added_names]
    cards = [{'key': card.ref, 'name': card.name, 'other_names': names(card),
              'quotes': [quote.model_dump() for quote in card.quotes], 'first_scene_id': card.first_scene_id}
             for card in state.catalogue if not card.existing]
    name_updates = [{'card_id': card.ref, 'names': names(card)}
                    for card in state.catalogue if card.existing and card.added_names]
    protagonist = None
    if not has_author_protagonist:
        order = {card.ref: number for number, card in enumerate(state.catalogue)}
        sums = {ref: round(score, 6) for ref, score in state.scores.items() if ref in order}  # 0.7+0.2+0.1 is 0.9999999999999999
        top = sorted(sums, key=lambda ref: (-sums[ref], order[ref]))[:PROTAGONIST_CANDIDATES]
        if top and sums[top[0]] >= PROTAGONIST_THRESHOLD:
            protagonist = {'ref': top[0], 'scores': [{'ref': ref, 'score': sums[ref]} for ref in top]}
    casts = []
    for scene_id, participants in state.casts.items():
        meta = scenes_meta.get(scene_id)
        if meta is None or not meta.cast_eligible:
            continue
        missing = [ref for ref in participants if ref not in meta.cast]
        if missing:
            casts.append({'scene_id': scene_id, 'mode': 'add' if meta.cast else 'set', 'participants': missing})
    return {'cards': cards, 'name_updates': name_updates, 'protagonist': protagonist, 'casts': casts,
            'skipped_scenes': [{'scene_id': scene_id, 'reason': reason} for scene_id, reason in state.skipped],
            'calls': state.calls}
