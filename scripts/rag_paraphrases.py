"""Paraphrase query set of the Voyage retrieval bench (#25): samples target records of one story, asks Claude Haiku for
three mentions of each (same words, synonyms, description) and writes the set and the owner's spot-check file.

Story texts go only to the --out directory outside the repository; stdout carries one JSON of counters or {"error": code}.
The API key is read from the environment or --env-file and is never printed. Every refusal is checked before the
Anthropic client is created."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from memory_bench.cloud_spend import BudgetExceeded, LedgerMissing, SpendLedger  # noqa: E402
from memory_bench.paraphrase import (FRAME_PARAMS, LEVELS, Query, _inside_repo, _write_atomic, manifest,  # noqa: E402
                                     owner_sample, sample_targets, sampling_frame, snapshot_hash, story_names,
                                     write_owner_file)
from memory_bench.paraphrase_gen import _estimate_usd, build_prompt, generate_one  # noqa: E402
from memory_bench.paraphrase_gen import HAIKU, PRICE_IN, PRICE_OUT, PROMPT_ID, PROVIDER, PRICES_DATE, generate  # noqa: E402,F401

DEFAULT_LEDGER = r'C:\tmp\rag-bench\spend.json'
DEFAULT_ENV = r'C:\Projects\text-generator\.env'
KEY_NAME = 'ANTHROPIC_API_KEY'


class BenchError(Exception):
    """Carries a stable error code."""


def cloud_allowed(story_id: str, prefixes) -> bool:
    """Same rule as memory_bench.embeddings.cloud_allowed, copied so the CLI needs no numpy."""
    return any(p and story_id.startswith(p) for p in prefixes)


DATA_CODES = ('live_data', 'not_a_data_copy')


def _data_code(error: Exception) -> str:
    """Only a known code leaves this function; anything else (a path, a message) becomes data_invalid."""
    code = str(error).split(':')[0]
    return code if code in DATA_CODES else 'data_invalid'


def load_story(args):
    """Story id and scenes for the chosen story, opened the way annotate_pairs does (copy of the data, never the live one)."""
    from memory_bench.extract import extract_story
    from storygen.application.workspace_bench import _check_data_dir
    try:
        data = _check_data_dir(args.data, True)
    except ValueError as error:
        raise BenchError(_data_code(error))
    try:
        from storygen.storage.repository import Repository
        repo = Repository(data)
        stories = repo.list_stories()
    except Exception:
        raise BenchError('db_unreadable')
    chosen = [s for s in stories if s.id.startswith(args.story)]
    if not chosen:
        raise BenchError('story_not_found')
    story = max(chosen, key=lambda s: (len(repo.list_scenes(s.id)), s.id))
    scenes, _ = extract_story(repo, story.id)
    return story.id, scenes


def read_key(env_file) -> str:
    """The key from the environment, else from KEY=VALUE lines of the env file; '' when absent."""
    value = os.environ.get(KEY_NAME, '').strip()
    if value:
        return value
    try:
        lines = Path(env_file).read_text(encoding='utf-8').splitlines()
    except OSError:
        return ''
    for line in lines:
        line = line.strip()
        if line.startswith('export '):
            line = line[len('export '):].lstrip()
        name, sep, raw = line.partition('=')
        if sep and not line.startswith('#') and name.strip() == KEY_NAME:
            return raw.strip().strip('"\'').strip()
    return ''


def make_client(api_key: str):
    from memory_bench.paraphrase_gen import AnthropicClient
    return AnthropicClient(api_key)


CACHE_NAME = 'gen-cache.json'


def _cache_key(record) -> str:
    return f"{hashlib.sha256(record.text.encode('utf-8')).hexdigest()}|{PROMPT_ID}|{HAIKU}"


def _load_cache(path: Path) -> dict:
    """Finished records of earlier runs (texts, so it lives in --out outside the repository); unreadable means empty."""
    try:
        entries = json.loads(path.read_text(encoding='utf-8'))['entries']
        return entries if isinstance(entries, dict) else {}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


class _TruncationCounter:
    """Passes calls to the client and counts replies whose stop_reason was 'max_tokens' (clients without
    last_stop_reason count none)."""

    def __init__(self, inner):
        self.inner, self.truncated = inner, 0

    def complete(self, prompt):
        reply = self.inner.complete(prompt)
        self.truncated += getattr(self.inner, 'last_stop_reason', None) == 'max_tokens'
        return reply


OWNER_NAME = 'owner-check.json'


def _owner_snapshot(path: Path) -> str | None:
    """Snapshot of an existing owner file; None when it is missing or unreadable (or the snapshot is not hex)."""
    try:
        snapshot = json.loads(path.read_text(encoding='utf-8'))['snapshot']
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(snapshot, str) or len(snapshot) < 8 or any(c not in '0123456789abcdef' for c in snapshot):
        return None
    return snapshot


def _save_owner_file(out: Path, sample, snapshot: str, record_texts: dict) -> str:
    """Keeps an owner file of the same snapshot untouched (the owner's verdicts survive a rerun); moves one of another
    snapshot aside to owner-check.<first 8 of its snapshot>.json before writing; a missing or unreadable one is
    simply written. Returns 'kept', 'rotated' or 'written'."""
    path = out / OWNER_NAME
    old = _owner_snapshot(path)
    if old == snapshot:
        return 'kept'
    if old is not None:
        os.replace(path, out / f'owner-check.{old[:8]}.json')
    write_owner_file(path, sample, snapshot, record_texts)
    return 'rotated' if old is not None else 'written'


def _counts(queries, status):
    return {level: sum(1 for q in queries if q.level == level and q.status == status) for level in LEVELS}


def _print(data: dict) -> None:
    print(json.dumps(data, sort_keys=True))


def _refuse(code: str) -> int:
    _print({'error': code})
    return 2


def _run(args) -> int:
    caps = {PROVIDER: args.anthropic_max_usd}
    if args.init_spend_ledger:
        _print({'usd_spent': SpendLedger.open(Path(args.spend_ledger), caps, create=True).spent(PROVIDER)})
        return 0
    if _inside_repo(args.out):
        return _refuse('inside_repo')
    story_id, scenes = load_story(args)
    if not cloud_allowed(story_id, args.cloud_stories.split(',')):
        return _refuse('cloud_not_allowed')
    ledger = SpendLedger.open(Path(args.spend_ledger), caps)
    ledger.check(PROVIDER, 0.0)  # an exhausted ledger refuses before any client exists
    key = read_key(args.env_file)
    if not key:
        return _refuse('anthropic_key_missing')
    frame = sampling_frame(scenes, FRAME_PARAMS)
    targets = sample_targets(frame, max((s.number for s in scenes), default=0), args.n, args.seed)
    names = story_names(scenes)
    client = _TruncationCounter(make_client(key))
    est_usd_per_call = (sum(_estimate_usd(build_prompt(r, names)) for r in targets) / len(targets)) if targets else 0.0
    before = ledger.spent(PROVIDER)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cache = _load_cache(out / CACHE_NAME)
    queries: list[Query] = []
    done = 0
    try:
        for record in targets:
            key = _cache_key(record)
            if key in cache:
                found = [Query(record.claim_id, q['level'], q['text'], q['status'], key.split('|')[0]) for q in cache[key]['queries']]
            else:
                found, used = generate_one(record, names, client, ledger)
                cache[key] = {'queries': [{'level': q.level, 'text': q.text, 'status': q.status} for q in found], 'attempts': used}
                _write_atomic(out / CACHE_NAME, {'entries': cache})
            queries += found
            done += 1
    except (BudgetExceeded, LedgerMissing, Exception) as error:
        code = ('cloud_budget_exceeded' if isinstance(error, BudgetExceeded)
                else 'spend_ledger_missing' if isinstance(error, LedgerMissing) else 'anthropic_call_failed')
        _print({'error': code, 'usd_spent': round(ledger.spent(PROVIDER) - before, 6), 'records_done': done})
        return 2
    meta = {'story': story_id, 'protagonist': scenes[0].protagonist if scenes else None, 'seed': args.seed, 'n': args.n, 'model': HAIKU, 'prompt_id': PROMPT_ID, 'levels': list(LEVELS),
            'owner_k': args.owner_k}
    queries = sorted(queries, key=lambda q: (q.claim_id, LEVELS.index(q.level)))
    mani = manifest(queries, meta)
    snapshot = snapshot_hash(mani)
    _write_atomic(out / 'set.json', {'meta': meta, 'queries': [
        {'claim_id': q.claim_id, 'level': q.level, 'text': q.text, 'status': q.status, 'record_sha256': q.record_sha256}
        for q in queries]})
    owner_file = _save_owner_file(out, owner_sample(queries, args.owner_k, args.seed, {r.claim_id: r.category for r in targets}),
                                  snapshot, {r.claim_id: r.text for r in targets})
    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    _write_atomic(manifest_path, {**mani, 'snapshot': snapshot})
    _print({'targets': len(targets), 'queries_ok': _counts(queries, 'ok'), 'rejected': _counts(queries, 'rejected'),
            'usd_spent': round(ledger.spent(PROVIDER) - before, 6), 'usd_ledger_total': round(ledger.spent(PROVIDER), 6),
            'snapshot': snapshot, 'owner_file': owner_file, 'truncated': client.truncated,
            'est_usd_per_call': round(est_usd_per_call, 8), 'prices_date': PRICES_DATE})
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', help='copy of the data directory (the working one is refused)')
    parser.add_argument('--story', help='story ID prefix')
    parser.add_argument('--out', help='directory for set.json and owner-check.json; must lie outside the repository')
    parser.add_argument('--manifest', help='manifest without texts (allowed inside the repository)')
    parser.add_argument('--n', type=int, default=40)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--owner-k', type=int, default=20)
    parser.add_argument('--cloud-stories', default='', help='comma-separated story ID prefixes allowed to go to the cloud')
    parser.add_argument('--spend-ledger', default=DEFAULT_LEDGER)
    parser.add_argument('--anthropic-max-usd', type=float, default=5.0)
    parser.add_argument('--init-spend-ledger', action='store_true', help='create the ledger file if it does not exist, then print the total')
    parser.add_argument('--env-file', default=DEFAULT_ENV)
    args = parser.parse_args(argv)
    if not args.init_spend_ledger and not all((args.data, args.story, args.out, args.manifest)):
        parser.error('--data, --story, --out and --manifest are required')
    try:
        return _run(args)
    except BenchError as error:
        return _refuse(str(error))
    except LedgerMissing:
        return _refuse('spend_ledger_missing')
    except BudgetExceeded:
        return _refuse('cloud_budget_exceeded')


if __name__ == '__main__':
    raise SystemExit(main())
