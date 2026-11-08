"""Per-scene metrics and aggregates. Output holds counts and ratios only: no texts, no claim IDs."""
from typing import Mapping

from .model import SceneInput, Selection


def scene_metrics(scene: SceneInput, sel: Selection) -> dict:
    chosen = set(sel.record_ids)
    return {'chars': sel.chars, 'tokens_conservative': sel.tokens_conservative, 'tokens_realistic': sel.tokens_realistic,
            'overflow': sel.overflow, 'dropped_by_budget': sel.dropped_by_budget, 'targets': len(scene.targets),
            'targets_hit': len(scene.targets & chosen), 'core_size': sel.layers.get('core', 0),
            'atmosphere_count': sel.layers.get('atmosphere', 0), 'first_meetings': scene.first_meetings,
            'layers': dict(sel.layers)}


def _stats(values):
    return {'mean': round(sum(values) / len(values), 1), 'max': max(values)} if values else None


def _jaccard(a, b):
    a, b = set(a), set(b)
    return 1.0 if not a and not b else len(a & b) / len(a | b)


def aggregate(rows: list[dict], selections: list[Selection]) -> dict:
    n = len(rows)
    targets = sum(r['targets'] for r in rows)
    pairs = [_jaccard(x.atmosphere_ids, y.atmosphere_ids) for x, y in zip(selections, selections[1:])
             if x.atmosphere_ids or y.atmosphere_ids]
    return {
        'scene_count': n,
        'chars': _stats([r['chars'] for r in rows]),
        'tokens_conservative': _stats([r['tokens_conservative'] for r in rows]),
        'tokens_realistic': _stats([r['tokens_realistic'] for r in rows]),
        'fits_rate': round(sum(not r['overflow'] for r in rows) / n, 3) if n else None,
        'overflow_scenes': sum(r['overflow'] for r in rows),
        'dropped_by_budget': _stats([r['dropped_by_budget'] for r in rows]),
        'target_recall': round(sum(r['targets_hit'] for r in rows) / targets, 3) if targets else None,
        'targets_total': targets,
        'scenes_with_missed_target': sum(r['targets_hit'] < r['targets'] for r in rows),
        'core_size': _stats([r['core_size'] for r in rows]),
        'atmosphere_mean': round(sum(r['atmosphere_count'] for r in rows) / n, 2) if n else None,
        'atmosphere_jaccard_adjacent': round(sum(pairs) / len(pairs), 3) if pairs else None,
        'first_meetings_total': sum(r['first_meetings'] for r in rows),
    }


def control_hits(cases: list[dict], scenes: Mapping[str, SceneInput], selections: Mapping[str, Selection]) -> list[dict]:
    """Owner's control cases {scene_id, claim_id} → hit flags by index; IDs never leave this function."""
    out = []
    for index, case in enumerate(cases):
        scene = scenes.get(case.get('scene_id'))
        if scene is None or case.get('scene_id') not in selections:
            out.append({'index': index, 'hit': None, 'reason': 'scene_skipped'})
        elif case.get('claim_id') not in {r.claim_id for r in scene.records}:
            out.append({'index': index, 'hit': None, 'reason': 'missing_in_memory'})
        else:
            out.append({'index': index, 'hit': case['claim_id'] in selections[case['scene_id']].record_ids, 'reason': None})
    return out
