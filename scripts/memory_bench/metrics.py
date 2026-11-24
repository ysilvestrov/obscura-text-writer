"""Per-scene metrics and aggregates. Output holds counts and ratios only: no texts, no claim IDs."""
from typing import Mapping

from .model import SceneInput, Selection


def _atmosphere_ids(scene: SceneInput) -> set[str]:
    if scene.product is None:
        return set()
    from storygen.memory.selection import classify
    return {item.claim_id for item in classify(scene.product)['atmosphere']}


def scene_metrics(scene: SceneInput, sel: Selection) -> dict:
    chosen = set(sel.record_ids)
    atmosphere = scene.targets & _atmosphere_ids(scene)
    core = scene.targets - atmosphere
    return {'chars': sel.chars, 'tokens_conservative': sel.tokens_conservative, 'tokens_realistic': sel.tokens_realistic,
            'overflow': sel.overflow, 'dropped_by_budget': sel.dropped_by_budget, 'targets': len(scene.targets),
            'targets_hit': len(scene.targets & chosen), 'targets_core': len(core), 'targets_core_hit': len(core & chosen),
            'targets_atmosphere': len(atmosphere), 'targets_atmosphere_hit': len(atmosphere & chosen), 'core_size': sel.layers.get('core', 0),
            'atmosphere_count': sel.layers.get('atmosphere', 0), 'first_meetings': scene.first_meetings,
            'layers': dict(sel.layers)}


def _stats(values):
    return {'mean': round(sum(values) / len(values), 1), 'max': max(values)} if values else None


def _jaccard(a, b):
    a, b = set(a), set(b)
    return 1.0 if not a and not b else len(a & b) / len(a | b)


def _recall(rows, total_key, hit_key):
    total = sum(r[total_key] for r in rows)
    return round(sum(r[hit_key] for r in rows) / total, 3) if total else None


def aggregate(rows: list[dict], selections: list[Selection]) -> dict:
    n = len(rows)
    targets = sum(r['targets'] for r in rows)
    fitting = [r for r in rows if not r['overflow']]
    fitting_targets = sum(r['targets'] for r in fitting)
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
        'target_recall_core': _recall(rows, 'targets_core', 'targets_core_hit'),
        'target_recall_atmosphere': _recall(rows, 'targets_atmosphere', 'targets_atmosphere_hit'),
        'target_recall_fitting': round(sum(r['targets_hit'] for r in fitting) / fitting_targets, 3) if fitting_targets else None,
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


def pair_hits(annotation: Mapping[str, list[str]], pairs: dict, scenes_by_number: Mapping[int, SceneInput],
              selections_by_number: Mapping[int, Selection]) -> list[dict]:
    """Planted pairs and controls → one row each: whether the repeat scene's selection holds an annotated record
    (hit) and whether the retrieval layer took it (by_retrieval). Rows carry pair IDs only, never claim IDs."""
    out = []
    for kind, key in (('pair', 'pairs'), ('control', 'controls')):
        for entry in pairs.get(key, []):
            row = {'id': entry['id'], 'kind': kind, 'hit': None, 'by_retrieval': None, 'reason': None}
            ids = set(annotation.get(entry['id']) or ())
            scene, sel = scenes_by_number.get(entry['repeat']), selections_by_number.get(entry['repeat'])
            if not ids:
                row['reason'] = 'not_annotated'
            elif scene is None or sel is None:
                row['reason'] = 'scene_skipped'
            else:
                present = ids & {r.claim_id for r in scene.records}
                if not present:
                    row['reason'] = 'missing_in_memory'
                else:
                    row['hit'] = bool(present & set(sel.record_ids))
                    row['by_retrieval'] = bool(present & set(sel.retrieval_ids))
            out.append(row)
    return out


def pair_summary(rows: list[dict]) -> dict:
    result = {}
    for kind in ('pair', 'control'):
        counted = [r for r in rows if r['kind'] == kind and r['reason'] is None]
        result[kind] = {'hit': sum(bool(r['hit']) for r in counted), 'by_retrieval': sum(bool(r['by_retrieval']) for r in counted),
                        'total': len(counted)}
    return result
