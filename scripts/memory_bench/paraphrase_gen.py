"""Generator of the paraphrase query set: asks Claude Haiku for three mentions of a memory record (same words, synonyms,
description), keeps the first variant per level that passes level_ok, and pays through the cumulative spend ledger.

Record texts go only into the request prompt; nothing here logs or raises text. No numpy and no anthropic at import."""
import hashlib
import json
import re
from typing import Protocol

from memory_bench.cloud_spend import PRICES_DATE, SpendLedger  # noqa: F401  (PRICES_DATE is re-exported)
from memory_bench.model import Record
from memory_bench.paraphrase import LEVELS, Query, level_ok, mentions_name

HAIKU = 'claude-haiku-5-5'
PRICE_IN = 0.10   # USD per million input tokens
PRICE_OUT = 0.50  # USD per million output tokens
PROVIDER = 'anthropic'
MAX_TOKENS = 4096  # adaptive thinking counts toward max_tokens; 1024 truncated 42 of ~120 replies on the main work
EST_OUT_TOKENS = 600

PROMPT = (
    "Ти допомагаєш перевіряти пошук у пам'яті історії. Нижче — один запис пам'яті історії. Напиши три речення-згадки, "
    'так, як цю деталь міг би згадати план пізнішої сцени, щоб вони повертали ту саму деталь:\n'
    '- "same": речення, що містить два-три слова запису (у тій самій або іншій формі);\n'
    '- "syn": та сама деталь, передана синонімами; жодне змістовне слово запису не повторюється, навіть в іншій формі;\n'
    '- "desc": та сама деталь через ознаку, наслідок чи вигляд, без жодного слова запису.\n'
    'Не вживай жодних імен зі списку імен. Кожне речення має бути короткою, природною згадкою з плану сцени, не '
    'переказом і не поясненням. Відповідай лише JSON з трьома ключами "same", "syn", "desc" і текстом речень як '
    'значеннями, без жодного іншого тексту.')
PROMPT_ID = hashlib.sha256(PROMPT.encode('utf-8')).hexdigest()
RECORD_PREFIX = 'Запис: '
_CATEGORY_PREFIX = 'Категорія: '
_NAMES_PREFIX = 'Імена (не вживати): '
_FENCE = re.compile(r'^\s*```[a-zA-Z]*\s*(.*?)\s*```\s*$', re.DOTALL)


class CompletionClient(Protocol):
    def complete(self, prompt: str) -> tuple[str, int, int]:
        """Returns the reply text, input tokens and output tokens."""


class AnthropicClient:
    """One non-streaming Messages API call. Haiku 5.5 thinks adaptively by default; effort is set to low.
    last_stop_reason holds the stop_reason of the latest reply ('max_tokens' means the reply was cut off)."""

    def __init__(self, api_key: str, model: str = HAIKU):
        import anthropic
        self.model = model
        self.last_stop_reason: str | None = None
        self._client = anthropic.Anthropic(api_key=api_key)

    def complete(self, prompt: str) -> tuple[str, int, int]:
        reply = self._client.messages.create(model=self.model, max_tokens=MAX_TOKENS, output_config={'effort': 'low'},
                                             messages=[{'role': 'user', 'content': prompt}])
        self.last_stop_reason = getattr(reply, 'stop_reason', None)
        text = ''.join(block.text for block in reply.content if block.type == 'text')
        return text, reply.usage.input_tokens, reply.usage.output_tokens


def build_prompt(record: Record, names: list[str]) -> str:
    one_line = ' '.join(record.text.split())
    return f'{PROMPT}\n\n{RECORD_PREFIX}{one_line}\n{_CATEGORY_PREFIX}{record.category}\n{_NAMES_PREFIX}{", ".join(names)}'


def _parse(reply: str) -> dict | None:
    body = reply.strip()
    fenced = _FENCE.match(body)
    if fenced:
        body = fenced.group(1)
    try:
        found = json.loads(body)
    except ValueError:
        return None
    return found if isinstance(found, dict) else None


def _estimate_usd(prompt: str) -> float:
    return (len(prompt) / 2 * PRICE_IN + EST_OUT_TOKENS * PRICE_OUT) / 1e6


def generate_one(record: Record, names: list[str], client: CompletionClient, ledger: SpendLedger,
                 attempts: int = 3) -> tuple[list[Query], int]:
    """Queries of one record and the number of calls it took."""
    prompt = build_prompt(record, names)
    sha = hashlib.sha256(record.text.encode('utf-8')).hexdigest()
    fixed: dict[str, str] = {}
    last: dict[str, str] = {}
    used = 0
    for _ in range(attempts):
        pending = [level for level in LEVELS if level not in fixed]
        if not pending:
            break
        ledger.check(PROVIDER, _estimate_usd(prompt))
        text, tokens_in, tokens_out = client.complete(prompt)
        used += 1
        ledger.record(PROVIDER, (tokens_in * PRICE_IN + tokens_out * PRICE_OUT) / 1e6, tokens_in, tokens_out)
        parsed = _parse(text)
        if parsed is None:
            continue
        for level in pending:
            variant = parsed.get(level)
            if not isinstance(variant, str) or not variant.strip():
                continue
            if level in ('syn', 'desc') and mentions_name(variant, names):
                last[level] = variant  # a name form in syn / desc fails this attempt for the level
            elif level_ok(level, variant, record.text, names):
                fixed[level] = variant
            else:
                last[level] = variant
    return [Query(record.claim_id, level, fixed[level], 'ok', sha) if level in fixed
            else Query(record.claim_id, level, last.get(level, ''), 'rejected', sha) for level in LEVELS], used


def generate(records: list[Record], names: list[str], client: CompletionClient, ledger: SpendLedger,
             attempts: int = 3) -> list[Query]:
    return [q for record in records for q in generate_one(record, names, client, ledger, attempts)[0]]
