"""Memory selection strategies with an explicit budget: nothing is cut silently.

full / all_active / full_a — baselines and approach A; structural — approach B; structural_fts — approach C."""
import hashlib
import json
import math
import re
import sqlite3
from dataclasses import dataclass
from typing import Callable, Iterable, Literal

from .extract import name_stems
from .model import CHARS_PER_TOKEN, Record, SceneInput, Selection, render, tokens_conservative, tokens_realistic

LAYERS = ('core', 'present', 'general', 'threads', 'facts', 'timeline', 'atmosphere', 'fts')


@dataclass(frozen=True)
class Params:
    memory_budget_tokens: int
    measure: Literal['conservative', 'realistic']
    core_mode: Literal['upper', 'lower']
    core_recent_scenes: int = 3
    atmosphere_share: float = 0.10
    timeline_window: int = 20
    chapter_scenes: int = 10
    summary_chars: int = 600


_WORD = re.compile(r"[\w'’ʼ]+")


def _norm(text: str) -> str:
    return text.lower().replace('’', "'").replace('ʼ', "'")


def mentions(record: Record, stems: Iterable[str]) -> bool:
    words = _WORD.findall(_norm(record.text))
    return any(word.startswith(stem) for stem in stems for word in words)


def _line_cost(text: str, measure: str) -> float:
    """Upper bound of what one rendered line adds: JSON-escaped newline in the conservative measure."""
    line = '— ' + text
    if measure == 'conservative':
        return len(line.encode('utf-8')) + 2
    return (len(line) + 1) / CHARS_PER_TOKEN


def _base_cost(measure: str) -> float:
    empty = render([], [])
    return tokens_conservative(empty) if measure == 'conservative' else len(empty) / CHARS_PER_TOKEN


def _selection(name, records, timeline, summary_chars, layers, overflow, dropped, atmosphere=()):
    text = render(records, timeline, summary_chars)
    ids = tuple(r.claim_id for r in records) + tuple(r.claim_id for r in timeline)
    return Selection(name, ids, {k: layers.get(k, 0) for k in LAYERS}, len(text), tokens_conservative(text),
                     tokens_realistic(text), overflow, dropped, tuple(atmosphere))


def _over(selection: Selection, params: Params) -> bool:
    used = selection.tokens_conservative if params.measure == 'conservative' else selection.tokens_realistic
    return used > params.memory_budget_tokens


def _cast_filter(scene: SceneInput):
    cast = set(scene.cast)
    return [r for r in scene.records
            if not (r.category == 'character_states' and cast and r.character_ids and not cast.intersection(r.character_ids))]


def _split_timeline(scene: SceneInput, params: Params):
    start = scene.number - params.timeline_window
    recent = [r for r in scene.timeline if r.source_scene is None or r.source_scene >= start]
    old = len(scene.timeline) - len(recent)
    old_scenes = max(0, start - 1)
    summary = math.ceil(old_scenes / params.chapter_scenes) * params.summary_chars if old else 0
    return recent, old, summary


def full(scene: SceneInput, params: Params) -> Selection:
    records = _cast_filter(scene)
    sel = _selection('full', records, scene.timeline, 0, {'timeline': len(scene.timeline)}, False, 0)
    return _with_overflow(sel, params)


def all_active(scene: SceneInput, params: Params) -> Selection:
    sel = _selection('all_active', list(scene.records), scene.timeline, 0, {'timeline': len(scene.timeline)}, False, 0)
    return _with_overflow(sel, params)


def full_a(scene: SceneInput, params: Params) -> Selection:
    recent, _, summary = _split_timeline(scene, params)
    sel = _selection('full_a', _cast_filter(scene), recent, summary, {'timeline': len(recent)}, False, 0)
    return _with_overflow(sel, params)


def _with_overflow(sel: Selection, params: Params) -> Selection:
    return Selection(**{**sel.__dict__, 'overflow': _over(sel, params)})


class _Budget:
    def __init__(self, params: Params):
        self.params, self.left = params, params.memory_budget_tokens - _base_cost(params.measure)

    def take(self, cost: float) -> bool:
        if cost <= self.left:
            self.left -= cost
            return True
        return False


def _layers(scene: SceneInput, params: Params):
    hero = scene.protagonist
    cast = set(scene.cast)
    stems_all = tuple(s for id in cast | {hero} for s in name_stems(scene.names.get(id, '')))
    stems_others = tuple(s for id in cast - {hero} for s in name_stems(scene.names.get(id, '')))
    stems_hero = name_stems(scene.names.get(hero, ''))
    core, present, general, threads, facts, atmosphere = [], [], [], [], [], []
    recent_from = scene.number - params.core_recent_scenes
    for r in scene.records:
        if r.category == 'character_states':
            if hero and hero in r.character_ids:
                old = params.core_mode == 'lower' and (r.last_changed_scene or 0) < recent_from
                (atmosphere if old else core).append(r)
            elif r.character_ids and cast.intersection(r.character_ids):
                present.append(r)
            elif not r.character_ids:
                general.append(r)
        elif r.category == 'open_threads' and mentions(r, stems_all):
            threads.append(r)
        elif r.category == 'facts' and mentions(r, stems_all):
            hero_only = params.core_mode == 'lower' and mentions(r, stems_hero) and not mentions(r, stems_others)
            (atmosphere if hero_only else facts).append(r)
    rotate = lambda r: hashlib.sha256(f'{scene.scene_id}:{r.claim_id}'.encode()).hexdigest()
    return core, present, general, threads, facts, sorted(atmosphere, key=rotate)


def _structural(scene: SceneInput, params: Params, name: str):
    core, present, general, threads, facts, atmosphere = _layers(scene, params)
    budget, measure = _Budget(params), params.measure
    chosen, layers, dropped = list(core), {'core': len(core)}, 0
    budget.left -= sum(_line_cost(r.text, measure) for r in core)
    recent, old, summary = _split_timeline(scene, params)
    if budget.left < 0:
        rest = len(present) + len(general) + len(threads) + len(facts) + len(recent) + old + len(atmosphere)
        return chosen, [], 0, layers, True, rest, budget
    for layer, items in (('present', present), ('general', general), ('threads', threads), ('facts', facts)):
        for r in items:
            if budget.take(_line_cost(r.text, measure)):
                chosen.append(r)
                layers[layer] = layers.get(layer, 0) + 1
            else:
                dropped += 1
    timeline = []
    if summary and not budget.take(_line_cost('x' * summary, measure)):
        summary, dropped = 0, dropped + old
    for r in recent:
        line = (f'Сцена {r.source_scene}: ' if r.source_scene is not None else '') + r.text
        if budget.take(_line_cost(line, measure)):
            timeline.append(r)
        else:
            dropped += 1
    layers['timeline'] = len(timeline)
    quota = params.atmosphere_share * params.memory_budget_tokens
    for r in atmosphere:
        cost = _line_cost(r.text, measure)
        if cost <= quota and budget.take(cost):
            quota -= cost
            chosen.append(r)
            layers.setdefault('_atmosphere_ids', []).append(r.claim_id)
            layers['atmosphere'] = layers.get('atmosphere', 0) + 1
        else:
            dropped += 1
    return chosen, timeline, summary, layers, False, dropped, budget


def structural(scene: SceneInput, params: Params) -> Selection:
    chosen, timeline, summary, layers, overflow, dropped, _ = _structural(scene, params, 'structural')
    return _selection('structural', chosen, timeline, summary, layers, overflow, dropped, layers.get('_atmosphere_ids', ()))


def fts_rank(candidates: list[Record], query_text: str) -> list[Record]:
    """BM25 over a trigram FTS5 index of candidate texts; ties by claim_id. Empty query ranks nothing."""
    terms = sorted({w.replace('"', '') for w in _WORD.findall(_norm(query_text)) if len(w) >= 3})
    if not terms or not candidates:
        return []
    db = sqlite3.connect(':memory:')
    try:
        db.execute("CREATE VIRTUAL TABLE t USING fts5(body, tokenize='trigram')")
        db.executemany('INSERT INTO t(rowid, body) VALUES (?, ?)', [(i, _norm(r.text)) for i, r in enumerate(candidates)])
        query = ' OR '.join(f'"{t}"' for t in terms)
        rows = db.execute('SELECT rowid, bm25(t) FROM t WHERE t MATCH ?', (query,)).fetchall()
    finally:
        db.close()
    return [candidates[i] for i, _ in sorted(rows, key=lambda row: (row[1], candidates[row[0]].claim_id))]


def structural_fts(scene: SceneInput, params: Params) -> Selection:
    chosen, timeline, summary, layers, overflow, dropped, budget = _structural(scene, params, 'structural_fts')
    if not overflow:
        taken = {r.claim_id for r in chosen}
        # Timeline-category claims are rendered by the timeline layer, never as records.
        pool = [r for r in scene.records if r.claim_id not in taken and r.category != 'timeline']
        for r in fts_rank(pool, scene.plan_text):
            if budget.take(_line_cost(r.text, params.measure)):
                chosen.append(r)
                layers['fts'] = layers.get('fts', 0) + 1
    return _selection('structural_fts', chosen, timeline, summary, layers, overflow, dropped, layers.get('_atmosphere_ids', ()))


MUTABLE = {'character_states', 'open_threads'}


def _catalog(name, mutable, immutable):
    text = json.dumps({'mutable': [{'claim_id': r.claim_id, 'category': r.category, 'text': r.text,
                                    'character_ids': list(r.character_ids)} for r in mutable],
                       'immutable': [{'category': r.category, 'text': r.text} for r in immutable]},
                      ensure_ascii=False, separators=(',', ':'))
    return Selection(name, tuple(r.claim_id for r in mutable), {k: 0 for k in LAYERS}, len(text),
                     tokens_conservative(text), tokens_realistic(text), False, 0)


def catalog_full(scene: SceneInput) -> Selection:
    """Same layout as storygen.memory.projection.memory_catalog_v3 over the scene's active records."""
    return _catalog('catalog_full', [r for r in scene.records if r.category in MUTABLE],
                    [r for r in scene.records if r.category not in MUTABLE])


def catalog_narrow(scene: SceneInput, params: Params, fts_top: int = 20) -> Selection:
    """Mutable records of core (upper), present, general and linked threads, plus FTS top-k over the scene's prose;
    immutable records only where structural would pick them (to avoid repeats)."""
    upper = Params(**{**params.__dict__, 'core_mode': 'upper'})
    core, present, general, threads, facts, _ = _layers(scene, upper)
    mutable = core + present + general + threads
    taken = {r.claim_id for r in mutable}
    extra = fts_rank([r for r in scene.records if r.category in MUTABLE and r.claim_id not in taken], scene.prose_text)
    return _catalog('catalog_narrow', mutable + extra[:fts_top], facts)


STRATEGIES: dict[str, Callable[[SceneInput, Params], Selection]] = {
    'full': full, 'all_active': all_active, 'full_a': full_a, 'structural': structural, 'structural_fts': structural_fts}
