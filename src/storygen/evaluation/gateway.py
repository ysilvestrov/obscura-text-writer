import os
import time
from pathlib import Path
from typing import Protocol

import httpx
from dotenv import load_dotenv
from openai import APIError, OpenAI

from .inputs import read_json
from .models import EvaluationRequest, EvaluatorConfig, GatewayResult, FailureDetail
from .failures import api_failure, refusal_detail
from ..providers.venice import validate_model, VeniceModelUnavailable


class GatewayFailure(Exception):
    """Безпечна помилка, без оригінального payload або ключів."""

    def __init__(self, message: str, *, result: GatewayResult | None = None, detail: FailureDetail | None = None):
        super().__init__(message)
        self.result = result
        self.detail = detail or FailureDetail(category='provider_error', message=message)


class CompletionGateway(Protocol):
    def complete(self, request: EvaluationRequest) -> GatewayResult: ...


def load_config(path: Path) -> EvaluatorConfig:
    return EvaluatorConfig.model_validate(read_json(path))


class OpenAICompatibleGateway:
    def __init__(self, config: EvaluatorConfig, http_client: httpx.Client | None = None):
        self.config = config
        load_dotenv(Path.cwd() / ".env")
        key = os.environ.get(config.api_key_env) if config.provider in {"openrouter", 'venice'} else "local-model"
        if not key:
            raise GatewayFailure("missing_api_key: Не задано ключ провайдера", detail=FailureDetail(category='missing_key', message='Не задано ключ провайдера у серверному середовищі.'))
        self._key = key
        self.client = OpenAI(base_url=config.base_url, api_key=key, max_retries=0,
            timeout=config.timeout_seconds or (3600 if config.provider == "local" else 180), http_client=http_client)

    def close(self):
        self.client.close()

    def complete(self, request: EvaluationRequest) -> GatewayResult:
        params = dict(model=self.config.model, messages=request.messages, max_tokens=request.max_output_tokens)
        if request.temperature is not None:
            params["temperature"] = request.temperature
        if request.response_mode == "json_schema":
            params["response_format"] = {"type": "json_schema", "json_schema": {"name": "story_evaluation", "strict": True, "schema": request.response_schema}}
            if self.config.provider == "openrouter":
                params["extra_body"] = {"provider": {"require_parameters": True}}
        started = time.monotonic()
        try:
            if self.config.provider == 'venice':
                validate_model(self.client, self.config.model, request.response_mode == 'json_schema')
                params['extra_body'] = {'venice_parameters': {
                    'include_venice_system_prompt': self.config.venice_include_system_prompt,
                    'disable_thinking': self.config.venice_disable_thinking,
                    'enable_web_search': 'off', 'enable_web_scraping': False, 'enable_x_search': False}}
            response = self.client.chat.completions.create(**params)
        except VeniceModelUnavailable as exc:
            raise GatewayFailure(str(exc), detail=FailureDetail(category='capability', message=str(exc))) from None
        except APIError as exc:
            detail = api_failure(exc, self._key, [m['content'] for m in request.messages])
            raise GatewayFailure(detail.message, detail=detail) from None
        if not response.choices:
            raise GatewayFailure("empty_response: Провайдер не повернув відповіді")
        choice = response.choices[0]
        envelope = GatewayResult(text=choice.message.content or "", finish_reason=choice.finish_reason, refusal=choice.message.refusal,
            usage=response.usage.model_dump(exclude_none=True) if response.usage else {}, duration_seconds=time.monotonic() - started)
        if choice.message.refusal or choice.finish_reason == 'content_filter':
            detail = refusal_detail(choice.message.refusal or '', content_filter=choice.finish_reason == 'content_filter')
            raise GatewayFailure(detail.message, result=envelope, detail=detail)
        if choice.finish_reason != "stop" or not choice.message.content:
            raise GatewayFailure(f"partial_response: Незавершена відповідь ({choice.finish_reason})", result=envelope)
        return envelope


def build_gateway(config: EvaluatorConfig, *, http_client: httpx.Client | None = None) -> CompletionGateway:
    if config.provider == "codex_cli":
        from .codex_gateway import CodexGateway
        return CodexGateway(config)
    return OpenAICompatibleGateway(config, http_client)
