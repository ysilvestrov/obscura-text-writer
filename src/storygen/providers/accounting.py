"""One call envelope across streaming, evaluation and calibration."""
from dataclasses import dataclass
from ..billing.models import BudgetError, money
from ..billing.pricing import resolve
from ..billing.service import reserve, mark_sent, settle
from ..token_budget.core import measure
from ..storage.billing_store import call_lease


def _amount(value):
    try:
        money(value)
        return str(value)
    except (ValueError, TypeError): return None


def normalize_usage(value):
    """Malformed provider telemetry must never discard a valid response."""
    try:
        raw = value if isinstance(value, dict) else value.model_dump(exclude_none=True)
    except Exception:
        return {}
    if not isinstance(raw, dict): return {}
    result = {}
    for key in ('prompt_tokens', 'completion_tokens', 'total_tokens', 'input_tokens', 'output_tokens'):
        if type(raw.get(key)) is int and raw[key] >= 0: result[key] = raw[key]
    for key in ('prompt_tokens_details', 'completion_tokens_details'):
        if isinstance(raw.get(key), dict):
            result[key] = {k:v for k,v in raw[key].items() if k in {'cached_tokens','reasoning_tokens','audio_tokens','accepted_prediction_tokens','rejected_prediction_tokens'} and type(v) is int and v >= 0}
    if _amount(raw.get('cost')) is not None: result['cost'] = raw['cost']
    return result


def normalize_cost(provider, top_level_cost, usage):
    if provider == 'venice':
        if not isinstance(top_level_cost, dict): return None, None
        return _amount(top_level_cost.get('usd')), _amount(top_level_cost.get('diem'))
    if provider == 'openrouter': return _amount(usage.get('cost')), None
    return None, None


@dataclass
class CallAccounting:
    repo: object
    scope: str
    run_id: str
    call_id: str
    attempt_id: str | None = None
    run_limit_usd: str | None = None
    started: bool = False
    result: dict | None = None
    warning: str | None = None

    def __post_init__(self):
        if self.run_limit_usd is not None:
            try:money(self.run_limit_usd)
            except ValueError:raise BudgetError('Некоректний ліміт окремого запуску') from None

    def before(self, settings, body, client=None, cancelled=None):
        self._lease = call_lease(self.repo, self.call_id)
        try:
            self._lease.__enter__()
        except RuntimeError:
            raise BudgetError('Цей виклик уже активний') from None
        try:
            result = self._before(settings, body, client, cancelled)
            if not result: self._lease.__exit__(None, None, None)
            return result
        except BaseException:
            self._lease.__exit__(None, None, None)
            raise

    def _before(self, settings, body, client=None, cancelled=None):
        if settings.provider in {'venice', 'openrouter'}:
            if self.repo.billing('summary', scope=self.scope)['limit_nanos'] is None:
                raise BudgetError('Спершу задайте явний ліміт бюджету')
            resolve(self.repo, settings, client)
            if cancelled and cancelled():return False
            output_cap = body.get('max_completion_tokens', body.get('max_tokens'))
            if type(output_cap) is not int or output_cap < 1: raise BudgetError('Потрібен явний вихідний ліміт виклику')
            item = measure(settings.provider, settings.base_url, body)
            reserve(self.repo, scope=self.scope, run_id=self.run_id, call_id=self.call_id,
                attempt_id=self.attempt_id, provider=settings.provider, model=settings.model, base_url=settings.base_url,
                request_hash=item['request_hash'], input_tokens=item['body_bytes'] + 256, output_tokens=output_cap,
                run_limit_nanos=money(self.run_limit_usd) if self.run_limit_usd is not None else None)
        else:
            if cancelled and cancelled():return False
            self.repo.billing('unpriced', scope=self.scope, run_id=self.run_id, call_id=self.call_id,
                attempt_id=self.attempt_id, provider=settings.provider, model=settings.model, request_hash=measure(settings.provider, settings.base_url, body)['request_hash'])
        mark_sent(self.repo, self.call_id)
        self.started = True
        return True

    def finish(self, settings, usage, *, complete=False, cost=None, response_id=None):
        if not self.started: return self.result
        usd, diem = normalize_cost(settings.provider, cost, usage)
        try:
            self.result = settle(self.repo, self.call_id, usage=usage, complete=complete, reported_usd=usd,
                reported_diem=diem, response_id=response_id)
            return self.result
        except Exception:
            # The durable sent reserve remains counted. Never discard already received prose.
            self.warning = 'Не вдалося завершити облік вартості; резерв збережений для звірки.'
            usage['accounting_warning'] = self.warning
            return None
        finally:
            self.started = False
            self._lease.__exit__(None, None, None)


def require_accounting(settings, accounting):
    if settings.provider in {'venice', 'openrouter'} and accounting is None:
        raise BudgetError('Cloud-виклик потребує явного бюджетного scope; completion не надіслано')
