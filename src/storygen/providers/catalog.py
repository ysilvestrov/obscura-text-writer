"""Public catalog metadata and known limits; never infer missing prices/caps."""
from .models import ModelOption
from ..billing.models import Tariff
from ..billing.pricing import from_catalog, ENDPOINTS


class ModelLimitsError(ValueError):
    pass


def known_limit(value):
    if isinstance(value,str) and value.isascii() and value.isdecimal() and len(value)<=20:value=int(value)
    return value if type(value) is int and value > 0 else None


def model_option(provider, row, repo=None):
    spec = row.get('model_spec')
    spec = spec if isinstance(spec,dict) else {}
    top = row.get('top_provider')
    top = top if isinstance(top,dict) else {}
    context = spec.get('availableContextTokens') if provider == 'venice' else row.get('context_length')
    output = spec.get('maxCompletionTokens') if provider == 'venice' else top.get('max_completion_tokens')
    tariff = None
    if provider in ENDPOINTS:
        try:
            tariff = from_catalog(provider, row['id'], row)
        except (KeyError, TypeError, ValueError, ArithmeticError):
            pass
        if repo is not None:
            raw = repo.billing('tariff_get', provider=provider, model=row['id'], base_url=ENDPOINTS[provider])
            if raw:
                try:saved = Tariff.model_validate(raw)
                except ValueError:raise ValueError('Некоректний збережений тариф; перевірте бюджет') from None
                if (saved.provider,saved.model,saved.base_url)!=(provider,row['id'],ENDPOINTS[provider]):
                    raise ValueError('Збережений тариф належить іншій моделі або endpoint')
                if saved.kind == 'manual' or saved.current(): tariff = saved
    name = spec.get('name') if provider == 'venice' else row.get('name')
    privacy, tee, schema, uncensored = 'unknown', False, None, None
    if provider == 'venice':
        caps = spec.get('capabilities')
        caps = caps if isinstance(caps,dict) else {}
        privacy = spec.get('privacy') if spec.get('privacy') in ('anonymized','private') else 'unknown'
        tee = caps.get('supportsTeeAttestation') is True or caps.get('supportsE2EE') is True
        schema = caps.get('supportsResponseSchema') is True if 'supportsResponseSchema' in caps else None
        uncensored = spec.get('uncensored') is True
    elif provider == 'openrouter' and isinstance(row.get('supported_parameters'),list):
        schema = 'structured_outputs' in row['supported_parameters']
    return ModelOption(id=row['id'], name=name if isinstance(name,str) and name else None, context_tokens=known_limit(context),
        max_output_tokens=known_limit(output), uncensored=uncensored, tariff=tariff, privacy=privacy, tee=tee, supports_schema=schema)


def validate_limits(context_cap, output_cap, context_tokens=None, max_output_tokens=None):
    for value, cap, label in [(context_tokens, known_limit(context_cap), 'Контекст'), (max_output_tokens, known_limit(output_cap), 'Вихідний ліміт')]:
        if cap is not None and value is not None and value > cap:
            raise ModelLimitsError(f'{label} {value} перевищує ліміт вибраної моделі {cap} токенів. Змініть налаштування; автоматичного повтору немає.')
