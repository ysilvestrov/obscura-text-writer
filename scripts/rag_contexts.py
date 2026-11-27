"""Record contexts of the Voyage retrieval bench (#25): asks Claude Haiku for a one-or-two-sentence context (who, where,
when) for each memory record of one story's ranking pools, from the prose of the record's source scene, caches the
contexts outside the repository and writes a manifest without texts.

Story texts go only to the --out directory outside the repository; stdout carries one JSON of counters or {"error": code}.
The API key is read from the environment or --env-file and is never printed. Every refusal is checked before the
Anthropic client is created. contexts.json in --out is also the cache: a rerun reuses 'ok' items with a matching key and
pays only for 'failed' items and new keys."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from memory_bench.cloud_spend import BudgetExceeded, LedgerMissing, SpendLedger  # noqa: E402
from memory_bench.context_gen import (CONTEXT_MAX_TOKENS, CONTEXT_PROMPT_ID, HAIKU, PRICES_DATE, PROVIDER,  # noqa: E402
                                      build_context_prompt, context_key, context_snapshot, context_targets, estimate_usd,
                                      generate_context)
from memory_bench.paraphrase import _inside_repo, _write_atomic  # noqa: E402
from rag_paraphrases import (DEFAULT_ENV, DEFAULT_LEDGER, BenchError, _print, _refuse, cloud_allowed, load_story,  # noqa: E402,F401
                             read_key)

CONTEXTS_NAME = 'contexts.json'


def make_client(api_key: str):
    from memory_bench.paraphrase_gen import AnthropicClient
    return AnthropicClient(api_key, max_tokens=CONTEXT_MAX_TOKENS)


class _Counting:
    """Passes calls to the client, keeps its stop_reason for generate_context and counts replies cut off by max_tokens."""

    def __init__(self, inner):
        self.inner, self.truncated, self.last_stop_reason = inner, 0, None

    def complete(self, prompt):
        reply = self.inner.complete(prompt)
        self.last_stop_reason = getattr(self.inner, 'last_stop_reason', None)
        self.truncated += self.last_stop_reason == 'max_tokens'
        return reply


class _CacheWriteFailed(Exception):
    """contexts.json could not be written; carries nothing."""


def _load_items(path: Path) -> dict:
    """Items of an earlier run (texts, so the file lives outside the repository); unreadable means empty."""
    import json
    try:
        items = json.loads(path.read_text(encoding='utf-8'))['items']
        return items if isinstance(items, dict) else {}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def _save(path: Path, meta: dict, items: dict) -> None:
    try:
        _write_atomic(path, {'meta': meta, 'items': items, 'snapshot': context_snapshot(items)})
    except (OSError, ValueError, TypeError):
        raise _CacheWriteFailed from None


def _run(args) -> int:
    if _inside_repo(args.out):
        return _refuse('inside_repo')
    story_id, scenes = load_story(args)
    if not cloud_allowed(story_id, args.cloud_stories.split(',')):
        return _refuse('cloud_not_allowed')
    ledger = SpendLedger.open(Path(args.spend_ledger), {PROVIDER: args.anthropic_max_usd})  # missing -> LedgerMissing
    ledger.check(PROVIDER, 0.0)  # an exhausted ledger refuses before any client exists
    key = read_key(args.env_file)
    if not key:
        return _refuse('anthropic_key_missing')
    targets, no_source = context_targets(scenes)
    est_usd_per_call = (sum(estimate_usd(build_context_prompt(r, p)) for r, p in targets) / len(targets)) if targets else 0.0
    client = _Counting(make_client(key))
    before = ledger.spent(PROVIDER)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / CONTEXTS_NAME
    old = _load_items(path)
    meta = {'model': HAIKU, 'prompt_id': CONTEXT_PROMPT_ID, 'story': story_id, 'prices_date': PRICES_DATE}
    items: dict = {}
    cached = done = 0
    code = None
    try:
        for record, prose in targets:
            k = context_key(record, prose)
            found = old.get(k)
            if isinstance(found, dict) and found.get('status') == 'ok' and isinstance(found.get('context'), str):
                items[k] = {'claim_id': record.claim_id, 'source_scene': record.source_scene, 'status': 'ok', 'context': found['context']}
                cached += 1
                continue
            text, status = generate_context(record, prose, client, ledger)
            if status == 'budget':
                code = 'cloud_budget_exceeded'
                break
            item = {'claim_id': record.claim_id, 'source_scene': record.source_scene, 'status': 'ok' if text else 'failed'}
            if text:
                item['context'] = text
            items[k] = item
            done += 1
            _save(path, meta, items)
    except (LedgerMissing, Exception) as error:
        code = ('spend_ledger_missing' if isinstance(error, LedgerMissing)
                else 'cache_write_failed' if isinstance(error, _CacheWriteFailed) else 'anthropic_call_failed')
    if code is not None:
        try:
            _save(path, meta, items)  # everything paid so far stays
        except _CacheWriteFailed:
            code = 'cache_write_failed' if code != 'cloud_budget_exceeded' else code
        if code == 'cloud_budget_exceeded':
            _print({'error': code})
        else:
            _print({'error': code, 'usd_spent': round(ledger.spent(PROVIDER) - before, 6), 'records_done': done})
        return 2
    _save(path, meta, items)  # also covers the all-cached and no-target runs
    snapshot = context_snapshot(items)
    mani = {'meta': meta, 'snapshot': snapshot, 'items': {k: {n: v[n] for n in ('claim_id', 'source_scene', 'status')} for k, v in items.items()}}
    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    _write_atomic(manifest_path, mani)
    _print({'targets': len(targets), 'ok': sum(1 for v in items.values() if v['status'] == 'ok'),
            'failed': sum(1 for v in items.values() if v['status'] == 'failed'), 'truncated': client.truncated,
            'no_source': no_source, 'cached': cached, 'usd_spent': round(ledger.spent(PROVIDER) - before, 6),
            'usd_ledger_total': round(ledger.spent(PROVIDER), 6), 'est_usd_per_call': round(est_usd_per_call, 8),
            'prices_date': PRICES_DATE, 'snapshot': snapshot})
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', help='copy of the data directory (the working one is refused)')
    parser.add_argument('--story', help='story ID prefix')
    parser.add_argument('--out', help='directory for contexts.json; must lie outside the repository')
    parser.add_argument('--manifest', help='manifest without texts (allowed inside the repository)')
    parser.add_argument('--cloud-stories', default='', help='comma-separated story ID prefixes allowed to go to the cloud')
    parser.add_argument('--spend-ledger', default=DEFAULT_LEDGER)
    parser.add_argument('--anthropic-max-usd', type=float, default=5.0)
    parser.add_argument('--env-file', default=DEFAULT_ENV)
    args = parser.parse_args(argv)
    if not all((args.data, args.story, args.out, args.manifest)):
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
