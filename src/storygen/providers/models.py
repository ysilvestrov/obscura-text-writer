from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import Field, model_validator

from ..domain import DomainModel


class ProviderSettings(DomainModel):
    provider: Literal['local','openrouter','venice'] = 'local'
    model: str = Field(min_length=1, max_length=300)
    base_url: str | None = None
    timeout: float | int | None = None
    key_env: str | None = None
    include_usage: bool = False
    response_mode: Literal['prompt_json','json_schema'] = 'prompt_json'
    venice_include_system_prompt: bool = False
    venice_disable_thinking: bool = False

    @model_validator(mode='after')
    def endpoint(self):
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


class RoleSettings(DomainModel):
    provider: ProviderSettings
    context_tokens: int = Field(default=8192,ge=512)
    max_output_tokens: int = Field(default=2048,ge=1)
    max_input_chars: int = Field(default=80000,ge=1)
    temperature: float | int = Field(default=0.7,ge=0,le=2)
    prompt_version_id: str | None = None
    prepare_prompt_version_id: str | None = None
    memory_mode: Literal['snapshot', 'evidence_delta'] = 'snapshot'
    edit_mode: Literal['prose', 'patches'] = 'prose'
    stop_sequences: list[Annotated[str,Field(min_length=1,max_length=200)]] = Field(default_factory=list,max_length=4)

    @model_validator(mode='after')
    def reserve(self):
        if self.max_output_tokens>=self.context_tokens:
            raise ValueError('Вихід має лишати місце для вхідного контексту')
        return self


class ModelOption(DomainModel):
    id: str
    context_tokens: int | None = None
    uncensored: bool | None = None
