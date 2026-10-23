"""Current catalog prices or explicitly confirmed manual snapshots."""
from datetime import timedelta
from decimal import Decimal
from .models import Tariff, utcnow, BudgetError

ENDPOINTS = {'venice': 'https://api.venice.ai/api/v1', 'openrouter': 'https://openrouter.ai/api/v1'}


def from_catalog(provider, model, row):
    if provider == 'venice':
        rates = row['model_spec']['pricing']
        input_rate, output_rate = rates['input']['usd'], rates['output']['usd']
        request_rate = '0'
    else:
        rates = row['pricing']
        input_rate, output_rate = Decimal(rates['prompt']) * 10**6, Decimal(rates['completion']) * 10**6
        request_rate = rates.get('request', '0')
    return Tariff(provider=provider, model=model, base_url=ENDPOINTS[provider], input_per_million=input_rate,
        output_per_million=output_rate, request_usd=request_rate, kind='official',
        source=ENDPOINTS[provider] + '/models', expires_at=(utcnow() + timedelta(hours=24)).isoformat())


def refresh(repo, settings, client):
    try:
        query = {'extra_query': {'type': 'text'}} if settings.provider == 'venice' else {}
        row = next((m.model_dump() for m in client.models.list(**query) if m.id == settings.model), None)
        if row is None: raise ValueError('missing model')
        tariff = from_catalog(settings.provider, settings.model, row)
    except Exception:
        raise BudgetError('Не вдалося отримати чинний тариф із каталогу; задайте ручний тариф із джерелом і строком') from None
    repo.billing('tariff_set', tariff=tariff.model_dump(mode='json'))
    return tariff


def resolve(repo, settings, client):
    raw = repo.billing('tariff_get', provider=settings.provider, model=settings.model, base_url=settings.base_url)
    if raw:
        tariff = Tariff.model_validate(raw)
        if tariff.current(): return tariff
        if tariff.kind == 'manual': raise BudgetError('Ручний тариф прострочений; підтвердьте новий або оновіть каталог')
    return refresh(repo, settings, client)
