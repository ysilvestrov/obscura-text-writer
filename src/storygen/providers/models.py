from datetime import date
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_serializer, model_validator

from ..domain import DomainModel
from ..billing.models import Tariff


class ProviderSettings(DomainModel):
    provider: Literal['local','openrouter','venice'] = 'local'
    model: str = Field(min_length=1, max_length=300)
    base_url: str | None = None
    timeout: float | int | None = None
    key_env: str | None = None
    include_usage: bool = False
    response_mode: Literal['prompt_json','json_schema'] = 'prompt_json'
    venice_include_system_prompt: bool = False
    local_disable_thinking: bool = False
    venice_disable_thinking: bool = False
    venice_reasoning_effort: Literal['none','low','medium','high','xhigh','max'] | None = None
    # OPENROUTER-REASONING: None sends nothing; 'none' disables reasoning (models with mandatory reasoning reject it).
    openrouter_reasoning_effort: Literal['none','minimal','low','medium','high','xhigh','max'] | None = None

    @model_serializer(mode='wrap')
    def without_unset_openrouter_reasoning(self, handler):
        # OPENROUTER-REASONING-S03: an unset field stays out of every dump, so stored roles, scene-context
        # fingerprints and impact manifest stamps made before the field existed keep matching.
        data = handler(self)
        if isinstance(data, dict) and data.get('openrouter_reasoning_effort') is None:
            data.pop('openrouter_reasoning_effort', None)
        return data

    @model_validator(mode='after')
    def endpoint(self):
        if self.venice_disable_thinking and self.venice_reasoning_effort is not None:
            raise ValueError('Оберіть або вимкнення thinking, або reasoning effort')
        if self.openrouter_reasoning_effort is not None and self.provider!='openrouter':
            raise ValueError('Reasoning OpenRouter задається лише для провайдера OpenRouter')
        endpoints={'local':'http://localhost:1235/v1','openrouter':'https://openrouter.ai/api/v1','venice':'https://api.venice.ai/api/v1'}
        self.base_url=self.base_url or endpoints[self.provider]
        self.key_env=self.key_env or ('VENICE_API_KEY' if self.provider=='venice' else 'OPENROUTER_API_KEY')
        parsed=urlparse(self.base_url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('URL не може містити облікових даних або параметрів')
        if self.provider=='local':
            if parsed.scheme!='http' or parsed.hostname not in {'localhost','127.0.0.1','::1'} or parsed.path.rstrip('/')!='/v1':
                raise ValueError('Локальний endpoint має бути loopback /v1')
        elif self.base_url.rstrip('/')!=endpoints[self.provider]:
            raise ValueError('Потрібен офіційний endpoint провайдера')
        self.timeout=self.timeout if self.timeout is not None else (3600 if self.provider=='local' else 180)
        if self.timeout<=0:
            raise ValueError('Timeout має бути додатним')
        return self


class ClassificationSettings(DomainModel):
    provider: ProviderSettings
    context_tokens: int = Field(default=32768,ge=512)
    max_output_tokens: int = Field(default=4096,ge=1)
    max_input_chars: int = Field(default=80000,ge=1)
    temperature: float = Field(default=0.2,ge=0,le=2)

    @model_validator(mode='after')
    def reserve(self):
        if self.max_output_tokens>=self.context_tokens:
            raise ValueError('Резерв класифікатора має лишати місце для входу')
        return self


class RoleVariant(DomainModel):
    """MODEL-001: the writer's own model for scenes whose effective rating has no axis at 2; the prompt stays shared."""
    provider: ProviderSettings
    context_tokens: int = Field(default=8192,ge=512)
    max_output_tokens: int = Field(default=2048,ge=1)
    max_input_chars: int = Field(default=80000,ge=1)
    temperature: float | int = Field(default=0.7,ge=0,le=2)
    timeout: float | int | None = Field(default=None,gt=0)

    @model_validator(mode='after')
    def reserve(self):
        if self.max_output_tokens>=self.context_tokens:
            raise ValueError('Вихід має лишати місце для вхідного контексту')
        return self


class RoleSettings(DomainModel):
    provider: ProviderSettings
    future_plan_mode: Literal['all','next_n','current'] = 'all'
    future_plan_count: int = Field(default=2,ge=0,le=1000)
    context_tokens: int = Field(default=8192,ge=512)
    max_output_tokens: int = Field(default=2048,ge=1)
    max_input_chars: int = Field(default=80000,ge=1)
    temperature: float | int = Field(default=0.7,ge=0,le=2)
    prompt_version_id: str | None = None
    prepare_prompt_version_id: str | None = None
    # Auditor only (MODEL-001): custom prompts of the audit_brief / audit_memory stages; prompt_version_id is audit_prose.
    stage_prompt_version_ids: dict[str,str] = Field(default_factory=dict)
    memory_mode: Literal['evidence_delta'] = 'evidence_delta'
    edit_mode: Literal['prose', 'patches', 'diff'] = 'prose'
    edit_review: Literal['auto', 'review'] = 'auto'
    edit_pass_limit: int = Field(default=5,ge=1,le=10)  # EDIT-LOOP: passes of a run whose request has no limit
    classification: ClassificationSettings | None = None
    stop_sequences: list[Annotated[str,Field(min_length=1,max_length=200)]] = Field(default_factory=list,max_length=4)
    low_rating_variant: RoleVariant | None = None

    @field_validator('stage_prompt_version_ids')
    @classmethod
    def stage_prompt_keys(cls,value):
        if set(value)-{'audit_brief','audit_memory'}:
            raise ValueError('Окремі промпти етапів можливі лише для audit_brief і audit_memory')
        return value

    @field_validator('memory_mode',mode='before')
    @classmethod
    def legacy_memory_mode(cls,value):
        # Snapshot is gone for new calls: a stored role reads as evidence_delta and its next call uses wire v4.
        return 'evidence_delta' if value=='snapshot' else value

    @model_validator(mode='after')
    def reserve(self):
        if self.max_output_tokens>=self.context_tokens:
            raise ValueError('Вихід має лишати місце для вхідного контексту')
        return self


class ModelRetirement(DomainModel):
    """MODEL-RETIREMENT: the provider's notice that it removes the model on this date (replacement only from Venice)."""
    date: date
    replacement: str | None = None


REASONING_EFFORTS = ('max','xhigh','high','medium','low','minimal')


class ReasoningCapability(DomainModel):
    """OPENROUTER-REASONING: what the catalog says the model allows (efforts: None = all levels, [] = no level choice)."""
    mandatory: bool = False
    default_enabled: bool | None = None
    efforts: list[Literal['max','xhigh','high','medium','low','minimal']] | None = None
    default_effort: str | None = None


class ModelOption(DomainModel):
    id: str
    name: str | None = None
    context_tokens: int | None = None
    uncensored: bool | None = None
    max_output_tokens: int | None = None
    tariff: Tariff | None = None
    privacy: Literal['anonymized','private','unknown'] = 'unknown'
    tee: bool = False
    supports_schema: bool | None = None
    retirement: ModelRetirement | None = None
    reasoning: ReasoningCapability | None = None
