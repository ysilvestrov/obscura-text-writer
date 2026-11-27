"""Cumulative spend ledger of the cloud calls of the research bench: one file for all runs, written atomically.

Carries codes only, no texts: the file holds provider totals, the exceptions hold nothing but the code."""
import json
import os
from pathlib import Path

PRICES_DATE = '2026-11-27'
_FIELDS = ('usd', 'input_tokens', 'output_tokens', 'calls')


class LedgerMissing(Exception):
    def __init__(self):
        super().__init__('spend_ledger_missing')


class BudgetExceeded(Exception):
    def __init__(self):
        super().__init__('cloud_budget_exceeded')


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        providers = data['providers']
        if not isinstance(providers, dict) or not all(isinstance(v, dict) for v in providers.values()):
            raise TypeError
        if not isinstance(data.get('prices_date', ''), str):
            raise TypeError
    except (OSError, ValueError, KeyError, TypeError):
        raise LedgerMissing from None
    return data


def _write(path: Path, data: dict) -> None:
    tmp = Path(f'{path}.{os.getpid()}.tmp')
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True), encoding='utf-8')
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


class SpendLedger:
    def __init__(self, path: Path, caps: dict[str, float], data: dict):
        self.path, self.caps, self.data = Path(path), dict(caps), data

    @classmethod
    def open(cls, path: Path, caps: dict[str, float], create: bool = False) -> 'SpendLedger':
        path = Path(path)
        if create and not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            _write(path, {'providers': {}, 'prices_date': PRICES_DATE})
        return cls(path, caps, _read(path))

    def usage(self, provider: str) -> dict:
        found = self.data['providers'].get(provider, {})
        return {k: found.get(k, 0) for k in _FIELDS}

    def spent(self, provider: str) -> float:
        return self.usage(provider)['usd']

    def check(self, provider: str, est_usd: float) -> None:
        """Refuses a call whose estimate would take the provider's total over its cap; no cap means no budget."""
        if self.spent(provider) + est_usd > self.caps.get(provider, 0.0):
            raise BudgetExceeded

    def record(self, provider: str, usd: float, input_tokens: int, output_tokens: int) -> None:
        """Adds to what is on disk now, so two ledgers opened on one file do not overwrite each other."""
        self.data = _read(self.path)
        total = self.usage(provider)
        total['usd'] += usd
        total['input_tokens'] += input_tokens
        total['output_tokens'] += output_tokens
        total['calls'] += 1
        self.data['providers'][provider] = total
        _write(self.path, self.data)
