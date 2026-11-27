"""Pure functions of the paraphrase query set for the Voyage retrieval bench: content words, level checks,
sampling of target records, the text-free manifest and snapshot, and the owner's spot-check file.

No numpy and no anthropic here: the module imports in the plain research and product environments."""
import hashlib
import json
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from memory_bench.extract import name_stems
from memory_bench.model import Record, SceneInput
from memory_bench.strategies import _WORD, Params, _norm, record_layers

ROOT = Path(__file__).resolve().parents[2]
LEVELS = ('same', 'syn', 'desc')
MAX_NO = 4
STOPWORDS = frozenset(
    'який яка яке які там тут щоб але або для від при про над під без між через після перед цей ця це ці той та те ті '
    'вже ще лише теж так його її їх він вона воно вони був була було були має мав мала собі себе свій своя своє свої '
    'весь вся все всі коли якщо ніж навіть саме дуже знову'.split())


@dataclass(frozen=True)
class Query:
    claim_id: str
    level: str
    text: str
    status: str  # 'ok' | 'rejected'
    record_sha256: str = ''  # sha256 of the record text the query was generated from


def _inside_repo(path) -> bool:
    return Path(path).resolve().is_relative_to(ROOT.resolve())


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def share_stem(a: str, b: str) -> bool:
    """A common start of at least 3 letters when the shorter word has 3-4 letters (the longer word then differs
    from it by an ending of at most 3 letters), otherwise at least 4."""
    prefix = 0
    for x, y in zip(a, b):
        if x != y:
            break
        prefix += 1
    short, long_ = sorted((len(a), len(b)))
    if short <= 4:
        return prefix >= 3 and long_ - prefix <= 3
    return prefix >= 4


def content_words(text: str, names: Iterable[str]) -> list[str]:
    stems = [s for name in names for s in name_stems(name)]
    out = []
    for word in _WORD.findall(_norm(text)):
        if len(word) < 3 or word in STOPWORDS or any(share_stem(word, s) for s in stems):
            continue
        out.append(word)
    return out


def shared_stems(query: str, record_text: str, names) -> int:
    names = list(names)
    q_words = set(content_words(query, names))
    return sum(1 for w in set(content_words(record_text, names)) if any(share_stem(w, q) for q in q_words))


def level_ok(level: str, query: str, record_text: str, names) -> bool:
    shared = shared_stems(query, record_text, names)
    return shared >= 2 if level == 'same' else shared == 0


def _eligible(record: Record, layers: dict[str, str]) -> bool:
    return record.claim_id not in layers and record.timeline_kind != 'timeline'


def sampling_frame(scenes: list[SceneInput], params: Params) -> list[Record]:
    found: dict[str, Record] = {}
    for scene in scenes:
        layers = record_layers(scene, params)
        for record in scene.records:
            if _eligible(record, layers):
                found.setdefault(record.claim_id, record)
    return [found[k] for k in sorted(found)]


def _third(record: Record, n_scenes: int) -> int:
    return min(2, ((record.source_scene or 1) - 1) * 3 // n_scenes)


def sample_targets(frame: list[Record], n_scenes: int, n: int, seed: int) -> list[Record]:
    if n >= len(frame):
        return sorted(frame, key=lambda r: r.claim_id)
    strata: dict[tuple[str, int], list[Record]] = {}
    for record in sorted(frame, key=lambda r: r.claim_id):
        strata.setdefault((record.category, _third(record, n_scenes)), []).append(record)
    keys = sorted(strata)
    take = {k: 0 for k in keys}
    if n < len(keys):
        for k in keys[:n]:
            take[k] = 1
    else:
        for k in keys:
            take[k] = 1
        remaining = n - len(keys)
        while remaining > 0:
            elig = [k for k in keys if take[k] < len(strata[k])]
            if not elig:
                break
            total = sum(len(strata[k]) for k in elig)
            quota = {k: remaining * len(strata[k]) / total for k in elig}
            floors = {k: min(int(quota[k]), len(strata[k]) - take[k]) for k in elig}
            for k, f in floors.items():
                take[k] += f
            remaining -= sum(floors.values())
            if remaining <= 0:
                break
            order = sorted(elig, key=lambda k: (-(quota[k] - int(quota[k])), k))
            for k in order[:remaining]:
                if take[k] < len(strata[k]):
                    take[k] += 1
                    remaining -= 1
    chosen = []
    for k in keys:
        if take[k]:
            rng = random.Random(f'{seed}:{k[0]}:{k[1]}')
            chosen += rng.sample(strata[k], take[k])
    return sorted(chosen, key=lambda r: r.claim_id)


def in_plan_scene(record: Record, scenes: list[SceneInput], params: Params) -> SceneInput | None:
    if record.source_scene is None:
        return None
    for scene in sorted(scenes, key=lambda s: s.number):
        if scene.number <= record.source_scene:
            continue
        if any(r.claim_id == record.claim_id for r in scene.records) and _eligible(record, record_layers(scene, params)):
            return scene
    return None


def _level_rank(level: str) -> int:
    return LEVELS.index(level) if level in LEVELS else len(LEVELS)


def manifest(queries: list[Query], meta: dict) -> dict:
    ordered = sorted(queries, key=lambda q: (q.claim_id, _level_rank(q.level)))
    return {'meta': meta, 'queries': [{'claim_id': q.claim_id, 'level': q.level, 'status': q.status,
                                       'sha256': _sha(q.text), 'record_sha256': q.record_sha256} for q in ordered]}


def snapshot_hash(manifest: dict) -> str:
    return _sha(json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(',', ':')))


def owner_sample(queries: list[Query], k: int, seed: int) -> list[Query]:
    pools = {}
    for level in LEVELS:
        pool = sorted((q for q in queries if q.status == 'ok' and q.level == level), key=lambda q: q.claim_id)
        random.Random(f'{seed}:{level}').shuffle(pool)
        pools[level] = pool
    out: list[Query] = []
    position = 0
    while len(out) < k and any(pools[level] for level in LEVELS):
        pool = pools[LEVELS[position % len(LEVELS)]]
        position += 1
        if pool:
            out.append(pool.pop(0))
    return out


def _write_atomic(path: Path, data: dict) -> None:
    tmp = Path(f'{path}.{os.getpid()}.tmp')
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def write_owner_file(path: Path, sample: list[Query], snapshot: str, record_texts: dict[str, str]) -> None:
    if _inside_repo(path):
        raise ValueError('inside_repo')
    items = [{'claim_id': q.claim_id, 'level': q.level, 'sha256': _sha(q.text), 'text': q.text,
              'record_text': record_texts.get(q.claim_id, ''), 'verdict': None} for q in sample]
    _write_atomic(Path(path), {'snapshot': snapshot, 'items': items})


def _normalize(verdict) -> str | None:
    return verdict.strip().lower() if isinstance(verdict, str) else None


def _summary(items: list[dict]) -> dict:
    verdicts = [_normalize(i.get('verdict')) for i in items]
    yes, no = verdicts.count('yes'), verdicts.count('no')
    return {'yes': yes, 'no': no, 'pending': sum(1 for i in items if i.get('verdict') is None), 'failed': no > MAX_NO}


def set_verdict(path: Path, index: int, verdict: str | None) -> dict:
    if _inside_repo(path):
        raise ValueError('inside_repo')
    value = None if verdict is None else _normalize(verdict)
    if verdict is not None and value not in ('yes', 'no'):
        raise ValueError('bad_verdict')
    path = Path(path)
    data = json.loads(path.read_text(encoding='utf-8'))
    items = data['items']
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(items):
        raise ValueError('bad_verdict')
    items[index]['verdict'] = value
    _write_atomic(path, data)
    return _summary(items)


def check_owner_file(path: Path, queries: list[Query], snapshot: str, max_no: int = MAX_NO) -> tuple[str | None, dict]:
    summary = {'yes': 0, 'no': 0, 'invalid': 0}
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        items = data['items']
        file_snapshot = data['snapshot']
        if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
            raise TypeError
    except (OSError, ValueError, KeyError, TypeError):
        return 'owner_check_missing', summary
    if file_snapshot != snapshot:
        return 'owner_check_stale', summary
    current = {(q.claim_id, q.level): _sha(q.text) for q in queries}
    if any(current.get((i.get('claim_id'), i.get('level'))) != i.get('sha256') for i in items):
        return 'owner_check_stale', summary
    verdicts = [_normalize(i.get('verdict')) for i in items]
    summary = {'yes': verdicts.count('yes'), 'no': verdicts.count('no'),
               'invalid': sum(1 for v in verdicts if v not in ('yes', 'no'))}
    if summary['invalid']:
        return 'owner_check_missing', summary
    if summary['no'] > max_no:
        return 'owner_check_failed', summary
    return None, summary
