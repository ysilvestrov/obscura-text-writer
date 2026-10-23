import threading
from typing import Iterator, Literal, Protocol

import httpx
from pydantic import Field

from ..domain import DomainModel
from ..generation.context import ContextBundle
from .client import build_openai_client
from .models import ProviderSettings
from .venice import validate_model, VeniceModelUnavailable
from .requests import generation_request, sdk_arguments, strict_schema
from .accounting import require_accounting, normalize_usage
from ..billing.models import BudgetError


class GenerationEvent(DomainModel):
    type: Literal['delta','terminal','error','cancelled']
    text: str = ''
    finish_reason: str | None = None
    usage: dict = Field(default_factory=dict)
    message: str = ''
    refusal: bool = False
    failure: dict = Field(default_factory=dict)


class GenerationGateway(Protocol):
    def stream(self,context: ContextBundle,cancel: threading.Event) -> Iterator[GenerationEvent]: ...


def output_limit_message(context,usage,has_text):
    details=usage.get('completion_tokens_details',{})
    reasoning=details.get('reasoning_tokens') if isinstance(details,dict) else None
    completion=usage.get('completion_tokens')
    if not has_text and type(reasoning) is int and type(completion) is int and completion>0 and reasoning>=completion:
        return (f'Вичерпано вихідний ліміт ({context.settings.max_output_tokens} токенів): провайдер витратив {reasoning} токенів на reasoning і не повернув тексту. '
                'Це не переповнення вхідного контексту. Для сумісної моделі вимкніть або зменште reasoning у налаштуваннях; автоматичного повтору немає.')
    return (f'Модель вичерпала ліміт відповіді ({context.settings.max_output_tokens} токенів). Частковий текст збережено. '
            'Перевірте резерв відповіді та витрати reasoning; збільшення вхідного контексту не збільшує вихідний ліміт. Автоматичного повтору немає.')


def empty_output_message(context,usage):
    subject='Редактор повернув' if context.stage=='edit' else 'Модель повернула'
    message=f'{subject} порожню відповідь із finish_reason=stop: фінального тексту немає. '
    details=usage.get('completion_tokens_details',{})
    reasoning=details.get('reasoning_tokens') if isinstance(details,dict) else None
    completion=usage.get('completion_tokens')
    if type(reasoning) is int and reasoning>0:
        amount=f'{reasoning} із {completion}' if type(completion) is int and completion>=reasoning else str(reasoning)
        message+=f'На reasoning витрачено {amount} вихідних токенів. Для сумісної моделі вимкніть або зменште reasoning. '
    return message+'Автоматичного повтору немає.'


class OpenAIGenerationGateway:
    def __init__(self,settings: ProviderSettings,http_client=None,accounting=None):
        self.settings=settings
        self.http_client=http_client
        self.accounting=accounting

    def bind_accounting(self,accounting):
        self.accounting=accounting

    def stream(self,context: ContextBundle,cancel: threading.Event) -> Iterator[GenerationEvent]:
        if cancel.is_set():
            yield GenerationEvent(type='cancelled')
            return
        finish=None
        usage={}
        has_text=False
        refusal=False
        complete=False
        cost=None
        response_id=None
        try:
            require_accounting(self.settings,self.accounting)
            with build_openai_client(self.settings,self.http_client) as client:
                body=context.api_request or generation_request(context.stage,context.settings,context.system_text,context.user_text,context.fragments)
                if self.settings.provider=='venice':
                    validate_model(client,self.settings.model,'response_format' in body)
                if cancel.is_set():
                    yield GenerationEvent(type='cancelled',usage=usage)
                    return
                if self.accounting and not self.accounting.before(self.settings,body,client,cancelled=cancel.is_set):
                    yield GenerationEvent(type='cancelled',usage=usage)
                    return
                with client.chat.completions.create(**sdk_arguments(body)) as stream:
                    for chunk in stream:
                        response_id=getattr(chunk,'id',response_id)
                        if cancel.is_set():
                            yield GenerationEvent(type='cancelled',usage=usage)
                            return
                        if chunk.usage is not None:
                            usage=normalize_usage(chunk.usage)
                        chunk_cost=getattr(chunk,'cost',None)
                        if chunk_cost is not None:
                            cost=chunk_cost
                            usage['cost']=cost
                        if getattr(chunk,'error',None):
                            raise RuntimeError('Provider stream error')
                        for choice in chunk.choices or []:
                            if choice.index!=0:
                                continue
                            delta=choice.delta
                            denied=getattr(delta,'refusal',None)
                            if denied:
                                refusal=True
                                yield GenerationEvent(type='delta',text=denied,refusal=True)
                            if delta.content:
                                has_text=True
                                yield GenerationEvent(type='delta',text=delta.content)
                            if choice.finish_reason:
                                finish=choice.finish_reason
                complete=finish is not None
                if cancel.is_set():
                    yield GenerationEvent(type='cancelled',usage=usage)
                elif finish=='stop' and has_text and not refusal:
                    yield GenerationEvent(type='terminal',finish_reason=finish,usage=usage)
                elif finish=='length' and not refusal:
                    yield GenerationEvent(type='error',finish_reason=finish,usage=usage,message=output_limit_message(context,usage,has_text))
                elif finish=='stop' and not has_text and not refusal:
                    yield GenerationEvent(type='error',finish_reason=finish,usage=usage,message=empty_output_message(context,usage),failure={'category':'empty_output'})
                else:
                    yield GenerationEvent(type='error',finish_reason=finish,usage=usage,refusal=refusal,message='Відповідь відхилено моделлю' if refusal else 'Немає повної відповіді з finish_reason=stop')
        except BudgetError as exc:
            yield GenerationEvent(type='error',usage=usage,message=str(exc),failure={'category':'budget','message':str(exc)} if context.stage in {'classify','publication_suggest'} else {})
        except VeniceModelUnavailable as exc:
            yield GenerationEvent(type='error',usage=usage,message=str(exc),failure={'category':'configuration','message':str(exc)} if context.stage in {'classify','publication_suggest'} else {})
        except Exception as exc:
            # SDK errors may contain request bodies, headers or server echoes. Never serialize them.
            if context.stage in {'classify','publication_suggest'} and not cancel.is_set():
                import os
                from ..evaluation.failures import api_failure
                detail=api_failure(exc,secret=os.environ.get(self.settings.key_env or ''),documents=(context.system_text,context.user_text)).model_dump(mode='json')
                role='класифікатора' if context.stage=='classify' else 'планувальника'
                detail['message']=detail['message'].replace('оцінювача',role).replace('оцінювачем',role).replace('Оцінювач','Планувальник' if context.stage=='publication_suggest' else 'Класифікатор')
                yield GenerationEvent(type='error',finish_reason=finish,usage=usage,message=detail['message'],failure=detail,refusal=detail['category'].startswith('refusal_'))
            else:
                yield GenerationEvent(type='cancelled' if cancel.is_set() else 'error',finish_reason=finish,usage=usage,message='Запит перервано або провайдер недоступний. Автоматичного повтору немає.')
        finally:
            if self.accounting:
                self.accounting.finish(self.settings,usage,complete=complete,cost=cost,response_id=response_id)


def build_generation_gateway(settings: ProviderSettings,http_client: httpx.Client | None = None,accounting=None) -> GenerationGateway:
    return OpenAIGenerationGateway(settings,http_client,accounting)
