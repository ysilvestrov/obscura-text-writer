"""Synthetic long stories built from aggregate rates of a real story, plus a plain linear growth fit.

Only aggregate rates cross from real data into the generator; synthetic texts are filler words and names."""
import random
from dataclasses import dataclass, field

from .extract import name_stems
from .model import Record, SceneInput
from .strategies import mentions

CATS = ('facts', 'character_states', 'open_threads')
MUTABLE = ('character_states', 'open_threads')
_CONSONANTS = 'бвгджзклмнпрстф'
_FILLER = ('слово', 'річ', 'день', 'море', 'дім', 'шлях', 'вечір', 'тінь', 'світло', 'двері')


@dataclass(frozen=True)
class Rates:
    active_per_scene: dict = field(default_factory=dict)
    timeline_per_scene: float = 0.0
    updates_per_scene: dict = field(default_factory=dict)
    text_len: dict = field(default_factory=dict)
    cast_size: float = 0.0
    hero_share: float = 0.0
    first_meetings_per_scene: float = 0.0
    hero_state_share: float = 0.0
    other_state_share: float = 0.0
    mention_share: float = 0.0


def _mean(values):
    return sum(values) / len(values) if values else 0.0


def measure_rates(scenes: list[SceneInput]) -> Rates:
    if not scenes:
        raise ValueError('no_scenes')
    last = max(scenes, key=lambda s: s.number)
    n = last.number
    by_cat = {c: [r for r in last.records if r.category == c] for c in CATS}
    updates = {c: 0 for c in MUTABLE}
    for s in scenes:
        category = {r.claim_id: r.category for r in s.records}
        for claim in s.targets:
            if category.get(claim) in updates:
                updates[category[claim]] += 1
    states = by_cat['character_states']
    linkable = by_cat['facts'] + by_cat['open_threads']
    stems = tuple(st for name in last.names.values() for st in name_stems(name))
    return Rates(
        active_per_scene={c: len(by_cat[c]) / n for c in CATS},
        timeline_per_scene=len(last.timeline) / n,
        updates_per_scene={c: updates[c] / len(scenes) for c in MUTABLE},
        text_len={**{c: _mean([len(r.text) for r in by_cat[c]]) for c in CATS},
                  'timeline': _mean([len(r.text) for r in last.timeline])},
        cast_size=_mean([len(s.cast) for s in scenes]),
        hero_share=_mean([1.0 if s.protagonist in s.cast else 0.0 for s in scenes]),
        first_meetings_per_scene=_mean([s.first_meetings for s in scenes]),
        hero_state_share=_mean([1.0 if last.protagonist in r.character_ids else 0.0 for r in states]),
        other_state_share=_mean([1.0 if r.character_ids and last.protagonist not in r.character_ids else 0.0 for r in states]),
        mention_share=_mean([1.0 if mentions(r, stems) else 0.0 for r in linkable]))


def _name(i: int) -> str:
    """Equal-length unique names, so no name stem is a prefix of another."""
    c = _CONSONANTS
    return 'Ка' + c[i // 225 % 15] + c[i // 15 % 15] + c[i % 15] + 'о'


def _count(rng, mean):
    whole = int(mean)
    return whole + (1 if rng.random() < mean - whole else 0)


def _text(rng, length, lead=''):
    words = [lead] if lead else []
    target = max(10, int(length * rng.uniform(0.5, 1.5)))
    while len(' '.join(words)) < target:
        words.append(rng.choice(_FILLER))
    return ' '.join(words)


def generate(rates: Rates, scene_count: int, seed: int = 0, sample_every: int = 1) -> list[SceneInput]:
    """Deterministic synthetic story; SceneInput is materialized for every sample_every-th scene and the last one."""
    rng = random.Random(seed)
    names = {'c0': _name(0)}
    introduced, active, timeline, out, counter = ['c0'], {}, [], [], 0
    others_mean = max(0.0, rates.cast_size - rates.hero_share)
    for i in range(1, scene_count + 1):
        new = []
        for _ in range(_count(rng, rates.first_meetings_per_scene)):
            cid = f'c{len(introduced)}'
            names[cid] = _name(len(introduced))
            introduced.append(cid)
            new.append(cid)
        cast = ['c0'] if rng.random() < rates.hero_share else []
        others = [c for c in introduced[1:] if c not in new]
        wanted = _count(rng, others_mean)
        picked = new[:wanted] + rng.sample(others, min(len(others), max(0, wanted - len(new))))
        cast += picked
        targets = []
        for category in MUTABLE:
            pool = [r.claim_id for r in active.values() if r.category == category]
            targets += rng.sample(pool, min(len(pool), _count(rng, rates.updates_per_scene.get(category, 0.0))))
        if (i - 1) % sample_every == 0 or i == scene_count:
            plan = ' '.join(names[c] for c in cast) + ' план сцени'
            prose = ' '.join([names[c] for c in cast] + [' '.join(active[t].text.split()[:3]) for t in targets])
            out.append(SceneInput(f's{i}', i, tuple(cast), plan, prose, tuple(active.values()), tuple(timeline), 'c0',
                                  dict(names), frozenset(targets), len(new)))
        for claim in targets:
            old = active[claim]
            active[claim] = Record(claim, old.category, _text(rng, rates.text_len.get(old.category, 60), old.text.split()[0]),
                                   old.character_ids, i, i)
        for category in CATS:
            for _ in range(_count(rng, rates.active_per_scene.get(category, 0.0))):
                counter += 1
                scope, lead = (), ''
                if category == 'character_states':
                    roll = rng.random()
                    pool = [c for c in cast if c != 'c0'] or introduced[1:]
                    if roll < rates.hero_state_share:
                        scope = ('c0',)
                    elif roll < rates.hero_state_share + rates.other_state_share and pool:
                        scope = (rng.choice(pool),)
                    lead = names[scope[0]] if scope else ''
                elif rng.random() < rates.mention_share and (cast or introduced):
                    lead = names[rng.choice(cast or introduced)]
                claim = f'm{counter}'
                active[claim] = Record(claim, category, _text(rng, rates.text_len.get(category, 60), lead), scope, i, i)
        for _ in range(_count(rng, rates.timeline_per_scene)):
            counter += 1
            timeline.append(Record(f'h{counter}', 'timeline', _text(rng, rates.text_len.get('timeline', 50)), (), i, i,
                                   'timeline'))
    return out


def fit_linear(points: list[tuple[int, float]]) -> tuple[float, float]:
    """Least squares (slope, intercept)."""
    if len(points) < 2:
        raise ValueError('need_two_points')
    n = len(points)
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    sxx = sum((x - mx) ** 2 for x, _ in points)
    if sxx == 0:
        raise ValueError('degenerate_x')
    slope = sum((x - mx) * (y - my) for x, y in points) / sxx
    return slope, my - slope * mx
