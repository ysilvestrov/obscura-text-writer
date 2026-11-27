"""Paraphrase query set of the Voyage retrieval bench (#25): samples target records of one story, asks Claude Haiku for
three mentions of each (same words, synonyms, description) and writes the set and the owner's spot-check file.

Story texts go only to the --out directory outside the repository; stdout carries one JSON of counters or {"error": code}.
The API key is read from the environment or --env-file and is never printed. Every refusal is checked before the
Anthropic client is created."""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from memory_bench.cloud_spend import BudgetExceeded, LedgerMissing, SpendLedger  # noqa: E402
from memory_bench.paraphrase import (LEVELS, Query, _inside_repo, _write_atomic, manifest, owner_sample,  # noqa: E402
                                     sample_targets, sampling_frame, snapshot_hash, write_owner_file)
from memory_bench.paraphrase_gen import HAIKU, PRICE_IN, PRICE_OUT, PROMPT_ID, PROVIDER, PRICES_DATE, generate  # noqa: E402,F401
from memory_bench.strategies import Params  # noqa: E402

DEFAULT_LEDGER = r'C:\tmp\rag-bench\spend.json'
DEFAULT_ENV = r'C:\Projects\text-generator\.env'
KEY_NAME = 'ANTHROPIC_API_KEY'
# Layers do not depend on the budget: the frame excludes only records a structural layer always holds.
FRAME_PARAMS = Params(memory_budget_tokens=100000, measure='conservative', core_mode='upper')


class BenchError(Exception):
    """Carries a stable error code."""


def cloud_allowed(story_id: str, prefixes) -> bool:
    """Same rule as memory_bench.embeddings.cloud_allowed, copied so the CLI needs no numpy."""
    return any(p and story_id.startswith(p) for p in prefixes)


def load_story(args):
    """Story id and scenes for the chosen story, opened the way annotate_pairs does (copy of the data, never the live one)."""
    from memory_bench.extract import extract_story
    from storygen.application.workspace_bench import _check_data_dir
    try:
        data = _check_data_dir(args.data, True)
    except ValueError as error:
        raise BenchError(str(error).split(':')[0])
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
    names = sorted({name for s in scenes for name in s.names.values()})
    client = make_client(key)
    before = ledger.spent(PROVIDER)
    try:
        queries = generate(targets, names, client, ledger)
    except BudgetExceeded:
        raise
    except Exception:
        return _refuse('anthropic_call_failed')
    meta = {'story': story_id, 'seed': args.seed, 'n': args.n, 'model': HAIKU, 'prompt_id': PROMPT_ID, 'levels': list(LEVELS)}
    queries = sorted(queries, key=lambda q: (q.claim_id, LEVELS.index(q.level)))
    mani = manifest(queries, meta)
    snapshot = snapshot_hash(mani)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    _write_atomic(out / 'set.json', {'meta': meta, 'queries': [
        {'claim_id': q.claim_id, 'level': q.level, 'text': q.text, 'status': q.status, 'record_sha256': q.record_sha256}
        for q in queries]})
    write_owner_file(out / 'owner-check.json', owner_sample(queries, args.owner_k, args.seed), snapshot,
                     {r.claim_id: r.text for r in targets})
    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    _write_atomic(manifest_path, {**mani, 'snapshot': snapshot})
    _print({'targets': len(targets), 'queries_ok': _counts(queries, 'ok'), 'rejected': _counts(queries, 'rejected'),
            'usd_spent': round(ledger.spent(PROVIDER) - before, 6), 'usd_ledger_total': round(ledger.spent(PROVIDER), 6),
            'snapshot': snapshot})
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
