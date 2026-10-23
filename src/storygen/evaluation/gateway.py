import os
import time
from pathlib import Path
from typing import Protocol

import httpx
from dotenv import load_dotenv
from openai import APIError

from .inputs import read_json
from .models import EvaluationRequest, EvaluatorConfig, GatewayResult, FailureDetail
from .failures import api_failure, refusal_detail
from ..providers.venice import validate_model, VeniceModelUnavailable
from ..providers.requests import evaluation_request, sdk_arguments
from ..providers.accounting import require_accounting, normalize_usage
from ..billing.models import BudgetError
from ..providers.client import build_openai_client


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
    def __init__(self, config: EvaluatorConfig, http_client: httpx.Client | None = None, accounting=None):
        self.config = config
        self.accounting = accounting
        load_dotenv(Path.cwd() / ".env")
        key = os.environ.get(config.api_key_env) if config.provider in {"openrouter", 'venice'} else "local-model"
        if not key:
            raise GatewayFailure("missing_api_key: Не задано ключ провайдера", detail=FailureDetail(category='missing_key', message='Не задано ключ провайдера у серверному середовищі.'))
        self._key = key
        self.client = build_openai_client(config,http_client)

    def close(self):
        self.client.close()

    def bind_accounting(self, accounting):
        self.accounting = accounting

    def complete(self, request: EvaluationRequest) -> GatewayResult:
        body = evaluation_request(self.config,request)
        params = sdk_arguments(body)
        started = time.monotonic()
        response = None
        try:
            require_accounting(self.config,self.accounting)
            if self.config.provider == 'venice':
                validate_model(self.client, self.config.model, request.response_mode == 'json_schema')
            if self.accounting: self.accounting.before(self.config,body,self.client)
            response = self.client.chat.completions.create(**params)
        except BudgetError as exc:
            raise GatewayFailure(str(exc),detail=FailureDetail(category='budget',message=str(exc))) from None
        except VeniceModelUnavailable as exc:
            raise GatewayFailure(str(exc), detail=FailureDetail(category='capability', message=str(exc))) from None
        except APIError as exc:
            detail = api_failure(exc, self._key, [m['content'] for m in request.messages])
            raise GatewayFailure(detail.message, detail=detail) from None
        finally:
            if self.accounting:
                self.accounting.finish(self.config,normalize_usage(getattr(response, "usage", None)),
                    complete=response is not None,cost=getattr(response,'cost',None),response_id=getattr(response,'id',None))
        if not response.choices:
            raise GatewayFailure("empty_response: Провайдер не повернув відповіді")
        choice = response.choices[0]
        envelope = GatewayResult(text=choice.message.content or "", finish_reason=choice.finish_reason, refusal=choice.message.refusal,
            usage=normalize_usage(response.usage), duration_seconds=time.monotonic() - started)
        if getattr(response,'cost',None) is not None: envelope.usage['cost'] = response.cost
        envelope.response_id=getattr(response,'id',None)
        if self.accounting:
            envelope.accounting=self.accounting.result or {'warning':self.accounting.warning}
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
