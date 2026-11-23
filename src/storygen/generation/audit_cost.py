"""Upper bound on the cost of an audit run (R-44 PR 4, design §9), priced from the stored tariff only.

A read-only preview never fetches a catalog: a cloud model without a current stored tariff shows its calls without USD.
Local models have no USD at all. Any failure here leaves the price unknown and never refuses the run.
"""
from decimal import ROUND_CEILING, Decimal

CLOUD = frozenset({'venice', 'openrouter'})
STALE_PRICE = 'Ціна моделі застаріла; оновіть ціни в налаштуваннях'
NO_PRICE = 'Ціни моделі немає; оновіть ціни в налаштуваннях'
# Tokens of the request around the input: the formula the plan fixes for the bound.
INPUT_OVERHEAD = 256
CHARS_TO_TOKENS = 4


def empty() -> dict:
    return {'per_call_usd': None, 'total_usd': None, 'reason': None}


def usd(nanos: int) -> str:
    """Dollars with four decimals, rounded up: an upper bound never prints below the priced amount."""
    return str((Decimal(nanos) / 10**9).quantize(Decimal('0.0001'), rounding=ROUND_CEILING))


def _per_call_nanos(repo, settings) -> tuple[int | None, str | None]:
    from ..billing.models import Tariff
    provider = settings.provider
    try:
        raw = repo.billing('tariff_get', provider=provider.provider, model=provider.model, base_url=provider.base_url)
        if not raw:
            return None, NO_PRICE
        tariff = Tariff.model_validate(raw)
        if not tariff.current():
            return None, STALE_PRICE
        return tariff.price(settings.max_input_chars * CHARS_TO_TOKENS + INPUT_OVERHEAD, settings.max_output_tokens), None
    except Exception:  # a broken stored row is an unknown price, not a refused preview
        return None, NO_PRICE


def upper_bound(repo, settings, calls: int) -> dict:
    """`tariff.price(max_input_chars*4+256, max_output_tokens) × calls` for a cloud auditor; no USD for a local one."""
    result = empty()
    if settings is None or settings.provider.provider not in CLOUD:
        return result
    per_call, reason = _per_call_nanos(repo, settings)
    if per_call is not None:
        result['per_call_usd'] = usd(per_call)
    if calls == 0:
        result['total_usd'] = usd(0)  # nothing is called, so nothing is paid whatever the tariff
        return result
    if per_call is None:
        result['reason'] = reason
        return result
    result['total_usd'] = usd(per_call * calls)
    return result
