"""Memory selection under a character budget (#60, MEMORY-SELECT): pure functions, no IO besides an in-memory FTS5 index.

Selection runs only when the full memory section does not fit the request. Candidates are the lines of the full
projection (memory_items), so a selected section is always a subset of the full one. The core is never cut."""
import hashlib
import re
from dataclasses import dataclass, field
from typing import Mapping

from .projection import MemoryItem, render_memory

LAYERS=('core','hero_recent','threads','present','general','facts','timeline','atmosphere','fts')
TIMELINE_WINDOW=20
RECENT_SCENES=3
ATMOSPHERE_SHARE=0.10


class CoreOverflow(ValueError):
    def __init__(self, needed: int, budget: int):
        self.needed=needed
        self.budget=budget
        super().__init__(f'Ядро пам’яті не вміщається: потрібно {needed} символів, доступно {budget}.')


@dataclass(frozen=True)
class SelectionInput:
    items: tuple[MemoryItem,...]
    scene_id: str
    scene_number: int
    cast: tuple[str,...]
    tracked: tuple[str,...]
    names: Mapping[str,str]
    query_text: str = ''
    kinds: Mapping[str,str] = field(default_factory=dict)       # author overrides: claim_id -> 'core' | 'atmosphere'
    scene_day: str | None = None
    day_keys: Mapping[int,str|None] = field(default_factory=dict)  # scene number -> day key


@dataclass(frozen=True)
class MemorySelection:
    text: str
    selected_claim_ids: tuple[str,...]
    layers: dict[str,int]
    dropped: dict[str,int]
    timeline_note: str | None
    char_budget: int


_WORD=re.compile(r"[\w'’ʼ]+")


def _norm(text: str) -> str:
    return text.lower().replace('’',"'").replace('ʼ',"'")


def name_stems(name: str) -> tuple[str,...]:
    # Same rule as the retrieval bench: drop one inflection letter of longer words, keep stems of 3+ letters.
    stems=[]
    for word in _norm(name).split():
        stem=word[:-1] if len(word)>4 else word
        if len(stem)>=3:stems.append(stem)
    return tuple(stems)


def mentions(text: str, stems) -> bool:
    words=_WORD.findall(_norm(text))
    return any(word.startswith(stem) for stem in stems for word in words)


def _recent(inp: SelectionInput, item: MemoryItem) -> bool:
    # Fresh = changed on the scene's story day or within the last RECENT_SCENES scenes. The day alone missed half of the
    # updated states in a story whose every scene starts a new date (bench, 10.11.2026).
    if item.source_scene is None:return False
    source_day=inp.day_keys.get(item.source_scene)
    same_day=bool(inp.scene_day and source_day and source_day==inp.scene_day)
    return same_day or item.source_scene>=inp.scene_number-RECENT_SCENES


def classify(inp: SelectionInput) -> dict[str,list[MemoryItem]]:
    """Every candidate lands in exactly one layer: the first whose rule matches (MEMORY-SELECT-S02)."""
    layers={name:[] for name in LAYERS}
    cast=set(inp.cast)
    heroes=set(inp.tracked)&cast
    stems=lambda ids:tuple(s for cid in sorted(ids) for s in name_stems(inp.names.get(cid,'')))
    cast_stems,hero_stems,other_stems=stems(cast),stems(heroes),stems(cast-heroes)
    for item in inp.items:
        kind=inp.kinds.get(item.claim_id)
        if item.section=='core' or kind=='core':layer='core'
        elif kind=='atmosphere':layer='atmosphere'
        elif item.section=='timeline':layer='timeline'
        elif item.section=='character_states':
            ids=set(item.character_ids)
            if ids&heroes:layer='hero_recent' if _recent(inp,item) else 'atmosphere'
            elif ids&cast:layer='present'
            elif not ids:layer='general'
            else:layer='fts'
        elif item.section=='open_threads':
            layer='threads' if mentions(item.text,cast_stems) else 'fts'
        elif item.section=='facts' and mentions(item.text,cast_stems):
            hero_only=mentions(item.text,hero_stems) and not mentions(item.text,other_stems)
            layer='atmosphere' if hero_only else 'facts'
        else:layer='fts'
        layers[layer].append(item)
    rotate=lambda item:hashlib.sha256(f'{inp.scene_id}:{item.claim_id}'.encode()).hexdigest()
    layers['atmosphere'].sort(key=rotate)
    return layers


def fts_rank(items: list[MemoryItem], query_text: str) -> list[MemoryItem]:
    """BM25 over a trigram FTS5 index of candidate texts; ties by claim_id. An empty query ranks nothing."""
    from ..storage.fts import bm25_rank
    terms=sorted({w.replace('"','') for w in _WORD.findall(_norm(query_text)) if len(w)>=3})
    rows=bm25_rank([_norm(item.text) for item in items],terms)
    return [items[i] for i,_ in sorted(rows,key=lambda row:(row[1],items[row[0]].claim_id))]


def _ranges(numbers) -> str:
    parts=[];numbers=sorted(set(numbers))
    i=0
    while i<len(numbers):
        j=i
        while j+1<len(numbers) and numbers[j+1]==numbers[j]+1:j+=1
        parts.append(str(numbers[i]) if i==j else f'{numbers[i]}–{numbers[j]}')
        i=j+1
    return ', '.join(parts)


def timeline_note(dropped: list[MemoryItem]) -> str | None:
    if not dropped:return None
    numbers=[item.source_scene for item in dropped if item.source_scene is not None]
    scenes=f' (сцени {_ranges(numbers)})' if numbers else ''
    return f'Не показано записів: {len(dropped)}{scenes}.'


def _render(inp: SelectionInput, chosen: set[str], note: str | None) -> str:
    return render_memory([item for item in inp.items if item.claim_id in chosen],list(inp.tracked),dict(inp.names),timeline_note=note)


def minimal_chars(inp: SelectionInput) -> int:
    """The smallest valid section: the whole core plus a note for every timeline line."""
    layers=classify(inp)
    return len(_render(inp,{item.claim_id for item in layers['core']},timeline_note(layers['timeline'])))


def select_memory(inp: SelectionInput, char_budget: int) -> MemorySelection:
    layers=classify(inp)
    core={item.claim_id for item in layers['core']}
    needed=len(_render(inp,core,timeline_note(layers['timeline'])))
    if needed>char_budget:raise CoreOverflow(needed,char_budget)
    chosen=set(core)
    taken={name:0 for name in LAYERS};taken['core']=len(core)
    dropped={name:0 for name in LAYERS}
    added=[]  # (layer, item) in the order of addition, for the final trim
    left=char_budget-len(_render(inp,core,None))

    def take(layer,item,cap=None):
        nonlocal left
        cost=len(item.line)+1
        if cost<=left and (cap is None or cost<=cap):
            left-=cost;chosen.add(item.claim_id);taken[layer]+=1;added.append((layer,item))
            return cost
        dropped[layer]+=1
        return 0

    for layer in ('hero_recent','threads','present','general','facts'):
        for item in layers[layer]:take(layer,item)
    window=inp.scene_number-TIMELINE_WINDOW
    for item in layers['timeline']:
        if item.source_scene is not None and item.source_scene<window:dropped['timeline']+=1
        else:take('timeline',item)
    quota=int(ATMOSPHERE_SHARE*char_budget)
    for item in layers['atmosphere']:quota-=take('atmosphere',item,quota)
    ranked=fts_rank(layers['fts'],inp.query_text)
    for item in ranked:take('fts',item)
    dropped['fts']+=len(layers['fts'])-len(ranked)

    # Exact render: the greedy pass is approximate ('Немає.' lines, the timeline note), so the last additions go back
    # until the section fits. Every removed line is counted as dropped in its layer.
    def note():
        return timeline_note([item for item in layers['timeline'] if item.claim_id not in chosen])
    text=_render(inp,chosen,note())
    while len(text)>char_budget:
        layer,item=added.pop()
        chosen.discard(item.claim_id);taken[layer]-=1;dropped[layer]+=1
        text=_render(inp,chosen,note())
    return MemorySelection(text,tuple(item.claim_id for item in inp.items if item.claim_id in chosen),taken,dropped,note(),char_budget)


NARROW_FTS_STATES=20


@dataclass(frozen=True)
class NarrowCatalog:
    keep: frozenset[str]
    hidden: int
    mutable_shown: int
    immutable_shown: int


def narrow_catalog(journal, cast, tracked, names, prose: str, scene_number: int, source_numbers: Mapping[str,int]) -> NarrowCatalog:
    """Claims the memory stage still sees when its full catalog overflows (MEMORY-SELECT-S07): the core and every thread,
    states of the cast and general states, up to NARROW_FTS_STATES other states ranked by the scene prose, facts that
    mention a participant and the timeline of the last TIMELINE_WINDOW scenes."""
    from .journal import replay_memory
    active=list(replay_memory(journal).values())
    every,cast=set(tracked),set(cast)
    stems=tuple(s for cid in sorted(cast) for s in name_stems(names.get(cid,'')))
    keep=set();pool=[];mutable=immutable=absent=0
    for event in active:
        if event.slot and event.character_ids[0] in every:
            # Core slots: a participant's is always shown; an absent tracked character's is in neither catalog (nor in
            # the bounds), so narrowing does not hide it.
            if event.character_ids[0] in cast:keep.add(event.claim_id)
            else:absent+=1
        elif event.category=='open_threads':keep.add(event.claim_id)
        elif event.category=='character_states':
            if not event.character_ids or cast&set(event.character_ids):keep.add(event.claim_id);mutable+=1
            else:pool.append(event)
        elif event.category=='facts':
            if mentions(event.text,stems):keep.add(event.claim_id);immutable+=1
        elif event.category=='timeline':
            number=source_numbers.get(event.source_version_id)
            if number is None or number>=scene_number-TIMELINE_WINDOW:keep.add(event.claim_id);immutable+=1
    ranked=fts_rank(pool,prose)[:NARROW_FTS_STATES]
    keep.update(event.claim_id for event in ranked);mutable+=len(ranked)
    return NarrowCatalog(frozenset(keep),len(active)-absent-len(keep),mutable,immutable)
