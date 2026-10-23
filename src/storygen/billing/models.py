from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from typing import Literal
from pydantic import Field, field_validator, model_validator
from ..domain import DomainModel


class BudgetError(ValueError):
    """Safe public accounting failure; never includes request text or keys."""


def utcnow():
    return datetime.now(timezone.utc)


def money(value):
    if isinstance(value, bool): raise ValueError('Некоректна сума')
    try: number = Decimal(str(value))
    except (InvalidOperation, ValueError): raise ValueError('Некоректна сума') from None
    if not number.is_finite() or number < 0 or number > Decimal('1000000000'):
        raise ValueError('Сума має бути скінченною в межах 0…1000000000')
    return int((number * 10**9).to_integral_value(rounding=ROUND_CEILING))


class Tariff(DomainModel):
    provider: Literal['venice', 'openrouter']
    model: str = Field(min_length=1, max_length=300)
    base_url: str
    input_per_million: Decimal = Field(ge=0, allow_inf_nan=False)
    output_per_million: Decimal = Field(ge=0, allow_inf_nan=False)
    request_usd: Decimal = Field(default=Decimal('0'), ge=0, allow_inf_nan=False)
    source: str = Field(min_length=1, max_length=1000)
    kind: Literal['official', 'manual']
    fetched_at: str = Field(default_factory=lambda: utcnow().isoformat())
    expires_at: str

    @field_validator('input_per_million', 'output_per_million', 'request_usd', mode='before')
    @classmethod
    def decimal_amount(cls, value):
        money(value)
        return Decimal(str(value))

    @model_validator(mode='after')
    def provider_endpoint(self):
        expected = {'venice': 'https://api.venice.ai/api/v1', 'openrouter': 'https://openrouter.ai/api/v1'}
        if self.base_url != expected[self.provider]: raise ValueError('Endpoint не відповідає провайдеру')
        if datetime.fromisoformat(self.expires_at.replace('Z', '+00:00')) <= datetime.fromisoformat(self.fetched_at.replace('Z', '+00:00')):
            raise ValueError('Строк тарифу має завершуватися після його отримання')
        return self

    @field_validator('source')
    @classmethod
    def nonempty(cls, value):
        if not value.strip(): raise ValueError('Потрібне джерело тарифу')
        return value

    @field_validator('base_url')
    @classmethod
    def endpoint(cls, value):
        if value.rstrip('/') not in {'https://api.venice.ai/api/v1', 'https://openrouter.ai/api/v1'}:
            raise ValueError('Потрібен офіційний endpoint')
        return value.rstrip('/')

    @field_validator('fetched_at', 'expires_at')
    @classmethod
    def aware_date(cls, value):
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None: raise ValueError('Потрібен часовий пояс')
        return value

    def current(self):
        return datetime.fromisoformat(self.fetched_at.replace('Z', '+00:00')) <= utcnow() < datetime.fromisoformat(self.expires_at.replace('Z', '+00:00'))

    def price(self, input_tokens, output_tokens):
        if any(type(value) is not int or value < 0 for value in (input_tokens, output_tokens)):
            raise ValueError('Некоректна usage')
        return money(self.request_usd + (input_tokens * self.input_per_million + output_tokens * self.output_per_million) / 10**6)
