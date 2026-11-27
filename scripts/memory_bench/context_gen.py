"""Context generator of the Voyage retrieval bench (#25): asks Claude Haiku for one or two sentences (who, where, when)
for each memory record of the ranking pools, from the prose of the record's source scene, so that a contextual column
can search by `context + record`. Pays through the cumulative spend ledger.

Texts (records, prose, contexts) go only into the request prompt and the cache file outside the repository; nothing here
logs or raises text. No numpy and no anthropic at import."""
import hashlib
import json
import math

from memory_bench.cloud_spend import BudgetExceeded, SpendLedger
from memory_bench.model import Record, SceneInput
from memory_bench.paraphrase_gen import (EST_OUT_TOKENS, HAIKU, PRICE_IN, PRICE_OUT, PRICES_DATE, PROVIDER,  # noqa: F401
                                         CompletionClient)

CONTEXT_PROMPT = (
    "Нижче — сцена історії і один запис пам'яті, зроблений за цією сценою. Напиши одне-два коротких речення контексту: "
    'хто, де і коли в історії стосується цей запис, щоб запис можна було знайти пошуком серед інших записів цієї '
    'історії. Не переказуй запис і не додавай нового. Відповідай лише текстом контексту.')
CONTEXT_PROMPT_ID = hashlib.sha256(CONTEXT_PROMPT.encode('utf-8')).hexdigest()
CONTEXT_MAX_TOKENS = 4096
ATTEMPTS = 3
SCENE_PREFIX = 'Сцена:\n'
RECORD_PREFIX = 'Запис: '


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def context_key(record: Record, prose: str) -> str:
    """sha256 of '|'.join(model, prompt id, claim_id, str(source_scene), sha256(record text), sha256(prose))."""
    return _sha('|'.join((HAIKU, CONTEXT_PROMPT_ID, record.claim_id, str(record.source_scene), _sha(record.text), _sha(prose))))


def context_targets(scenes: list[SceneInput]) -> tuple[list[tuple[Record, str]], int]:
    """Unique (by claim_id and text) ranking-pool records (category != 'timeline') whose source_scene is among the
    scenes, each with the prose of that source scene, in first-seen order; and the number of unique pool records without
    a source_scene or without that scene (no_source)."""
    prose_of = {s.number: s.prose_text for s in scenes}
    seen: set[tuple[str, str]] = set()
    targets: list[tuple[Record, str]] = []
    no_source = 0
    for scene in scenes:
        for record in scene.records:
            if record.category == 'timeline' or (record.claim_id, record.text) in seen:
                continue
            seen.add((record.claim_id, record.text))
            if record.source_scene is None or record.source_scene not in prose_of:
                no_source += 1
            else:
                targets.append((record, prose_of[record.source_scene]))
    return targets, no_source


def build_context_prompt(record: Record, prose: str) -> str:
    one_line = ' '.join(record.text.split())
    return f'{CONTEXT_PROMPT}\n\n{SCENE_PREFIX}{prose}\n\n{RECORD_PREFIX}{one_line}'


def estimate_usd(prompt: str) -> float:
    """Estimate of one call: ceil(chars / 2) input tokens plus 600 output tokens at the Haiku prices."""
    return (math.ceil(len(prompt) / 2) * PRICE_IN + EST_OUT_TOKENS * PRICE_OUT) / 1e6


def generate_context(record: Record, prose: str, client: CompletionClient, ledger: SpendLedger) -> tuple[str | None, str]:
    """(context, status). 'ok' carries the stripped context. A reply cut off by max_tokens (the client's
    last_stop_reason) or empty after strip() is paid for but never kept and is retried, up to 3 attempts; then
    (None, reason of the last attempt), 'truncated' or 'empty' (the caller stores that as failed). 'budget' means the
    ledger refused the next call (None, nothing is called)."""
    prompt = build_context_prompt(record, prose)
    status = 'empty'
    for _ in range(ATTEMPTS):
        try:
            ledger.check(PROVIDER, estimate_usd(prompt))
        except BudgetExceeded:
            return None, 'budget'
        text, tokens_in, tokens_out = client.complete(prompt)
        ledger.record(PROVIDER, (tokens_in * PRICE_IN + tokens_out * PRICE_OUT) / 1e6, tokens_in, tokens_out)
        if getattr(client, 'last_stop_reason', None) == 'max_tokens':
            status = 'truncated'
        elif not text.strip():
            status = 'empty'
        else:
            return text.strip(), 'ok'
    return None, status


def context_snapshot(items: dict) -> str:
    """sha256 (hex) of json.dumps(sorted([[key, status], ...])) with the default separators and ensure_ascii, over every
    item of `items` (key -> {'status': ...}); texts do not take part."""
    return _sha(json.dumps(sorted([key, item['status']] for key, item in items.items())))
