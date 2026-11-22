import threading
from contextlib import contextmanager
from typing import Iterator, Literal, Protocol

import httpx
from pydantic import Field

from ..domain import DomainModel
from ..generation.context import ContextBundle
from .client import build_openai_client, ProviderConfigurationError
from .models import ProviderSettings
from .policy import check_consent, ModelPolicyBlocked
from .retirement import retirement_from
from .venice import validate_model, VeniceModelUnavailable
from .catalog import ModelLimitsError, validate_limits
from .requests import generation_request, sdk_arguments, strict_schema
from .accounting import require_accounting, normalize_usage
from ..billing.models import BudgetError


NONSTREAM_TIMEOUT = 300  # Seconds; the longest successful Venice answer in the log took 181 s.


class BackgroundCall:
    """One blocking provider call in a daemon thread, so cancellation never waits for the answer."""

    def __init__(self,work):
        self.response=None
        self.error=None
        self._done=threading.Event()
        self._lock=threading.Lock()
        self._late=None
        self._work=work
        threading.Thread(target=self._run,daemon=True).start()

    def _run(self):
        try:
            self.response=self._work()
        except BaseException as exc:
            self.error=exc
        with self._lock:
            self._done.set()
            late=self._late
        if late:
            late(self)

    def wait(self,cancel,poll=0.25):
        """True once the call finished; False as soon as `cancel` is set first."""
        while not self._done.wait(poll):
            if cancel.is_set():
                with self._lock:
                    if not self._done.is_set():
                        return False
        return True

    def on_late(self,callback):
        with self._lock:
            if not self._done.is_set():
                self._late=callback
                return
        callback(self)

    def result(self):
        if self.error is not None:
            raise self.error
        return self.response


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


WHITESPACE_RUNAWAY_LIMIT=1024


def whitespace_runaway_message():
    return (f'Модель зациклилася на пробілах у структурованій відповіді (понад {WHITESPACE_RUNAWAY_LIMIT} поспіль); потік зупинено, частковий текст збережено. '
            'Імовірно, промпт не описує обов’язкове поле JSON-схеми. Автоматичного повтору немає.')


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
        # MODEL-RETIREMENT-S02: the provider's removal notice for the called model, read from the catalog check of the call.
        self.retirement=None

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
        used_key=None
        cost=None
        response_id=None
        blank_run=0
        deferred=False
        hold={'late':False}
        try:
            require_accounting(self.settings,self.accounting)
            with self._client(hold) as client:
                # SECURITY-002: error texts are cleaned of the credential this request was sent with; the stored key
                # may be replaced or deleted before the provider answers.
                used_key=client.api_key if self.settings.provider!='local' else None
                body=context.api_request or generation_request(context.stage,context.settings,context.system_text,context.user_text,context.fragments)
                structured='response_format' in body
                output_limit=body.get('max_completion_tokens',body.get('max_tokens'))
                request_context=context.estimated_tokens+(output_limit if type(output_limit) is int and output_limit>0 else context.settings.max_output_tokens)
                if self.settings.provider=='venice':
                    spec=validate_model(client,self.settings.model,'response_format' in body,context_tokens=request_context,max_output_tokens=output_limit,require_uncensored=False)
                    self.retirement=retirement_from('venice',{'model_spec':spec})
                    if context.policy_role and self.accounting is not None:
                        check_consent(self.accounting.repo,context.policy_role,self.settings,context.policy_rating,spec.get('uncensored') is True)
                elif self.settings.provider=='openrouter':
                    row=next((m.model_dump() for m in client.models.list() if m.id==self.settings.model),None)
                    if row:
                        self.retirement=retirement_from('openrouter',row)
                        top=row.get('top_provider');top=top if isinstance(top,dict) else {}
                        validate_limits(row.get('context_length'),top.get('max_completion_tokens'),request_context,output_limit)
                if cancel.is_set():
                    yield GenerationEvent(type='cancelled',usage=usage)
                    return
                if self.accounting and not self.accounting.before(self.settings,body,client,cancelled=cancel.is_set):
                    yield GenerationEvent(type='cancelled',usage=usage)
                    return
                if body.get('stream') is False:
                    call=BackgroundCall(lambda:self._complete(client,body))
                    if not call.wait(cancel):
                        # The provider still bills the whole answer: the call records it when it arrives, and the
                        # client (with an injected http client under it) stays open for it until then.
                        deferred=True
                        hold['late']=True
                        call.on_late(lambda done:self._finish_late(done,client))
                        yield GenerationEvent(type='cancelled',usage=usage)
                        return
                    response=call.result()
                    response_id=getattr(response,'id',response_id)
                    if response.usage is not None:
                        usage=normalize_usage(response.usage)
                    chunk_cost=getattr(response,'cost',None)
                    if chunk_cost is not None:
                        cost=chunk_cost
                        usage['cost']=cost
                    for choice in response.choices or []:
                        if choice.index!=0:
                            continue
                        message=choice.message
                        denied=getattr(message,'refusal',None)
                        if denied:
                            refusal=True
                            yield GenerationEvent(type='delta',text=denied,refusal=True)
                        if message.content:
                            has_text=True
                            yield GenerationEvent(type='delta',text=message.content)
                            if structured and len(message.content)-len(message.content.rstrip())>WHITESPACE_RUNAWAY_LIMIT:
                                yield GenerationEvent(type='error',usage=usage,message=whitespace_runaway_message(),failure={'category':'degenerate_output'})
                                return
                        finish=choice.finish_reason
                else:
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
                                    if structured:
                                        stripped=delta.content.rstrip()
                                        blank_run=blank_run+len(delta.content) if not stripped else len(delta.content)-len(stripped)
                                        if blank_run>WHITESPACE_RUNAWAY_LIMIT:
                                            # Constrained decoding with a masked closing token degenerates into whitespace until the cap.
                                            yield GenerationEvent(type='error',usage=usage,message=whitespace_runaway_message(),failure={'category':'degenerate_output'})
                                            return
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
            yield GenerationEvent(type='error',usage=usage,message=str(exc),failure={'category':'budget','message':str(exc)})
        except ModelPolicyBlocked as exc:
            yield GenerationEvent(type='error',usage=usage,message=str(exc),failure={'category':'model_policy','message':str(exc)})
        except (VeniceModelUnavailable,ModelLimitsError,ProviderConfigurationError) as exc:
            yield GenerationEvent(type='error',usage=usage,message=str(exc),failure={'category':'configuration','message':str(exc)})
        except Exception as exc:
            # SDK errors may contain request bodies, headers or server echoes. Never serialize them.
            if not cancel.is_set():
                from ..evaluation.failures import api_failure
                from .secrets import resolve_key
                from openai import APIError
                detail=(api_failure(exc,secret=used_key or resolve_key(self.settings.key_env),documents=(context.system_text,context.user_text)).model_dump(mode='json')
                    if isinstance(exc,APIError) else {'category':'technical','http_status':None,'message':'Не вдалося завершити запит; точну причину не встановлено.'})
                role={'classify':'класифікатора','publication_suggest':'письменника'}.get(context.stage,'провайдера')
                detail['message']=detail['message'].replace('оцінювача',role).replace('оцінювачем',{'classify':'класифікатором','publication_suggest':'письменником'}.get(context.stage,'провайдером')).replace('Оцінювач',{'publication_suggest':'Письменник','classify':'Класифікатор'}.get(context.stage,'Провайдер'))
                status=detail.get('http_status')
                if status is not None:detail['message']=f"HTTP {status}: {detail['message']}"
                detail['message']+=' Автоматичного повтору немає.'
                yield GenerationEvent(type='error',finish_reason=finish,usage=usage,message=detail['message'],failure=detail,refusal=detail['category'].startswith('refusal_'))
            else:
                yield GenerationEvent(type='cancelled' if cancel.is_set() else 'error',finish_reason=finish,usage=usage,message='Запит перервано або провайдер недоступний. Автоматичного повтору немає.')
        finally:
            if self.accounting and not deferred:
                self.accounting.finish(self.settings,usage,complete=complete,cost=cost,response_id=response_id)

    @contextmanager
    def _client(self,hold):
        client=build_openai_client(self.settings,self.http_client)
        try:
            yield client
        finally:
            if not hold['late']:
                client.close()

    def _complete(self,client,body):
        return client.with_options(timeout=NONSTREAM_TIMEOUT).chat.completions.create(**sdk_arguments(body))

    def _finish_late(self,call,client=None):
        """Close the budget reservation of a cancelled non-streamed call with what the provider reported."""
        try:
            self._settle_late(call)
        finally:
            if client is not None:
                client.close()

    def _settle_late(self,call):
        if not self.accounting:
            return
        usage,cost,response_id,complete={},None,None,False
        response=call.response
        if response is not None:
            usage=normalize_usage(response.usage) if response.usage is not None else {}
            cost=getattr(response,'cost',None)
            if cost is not None:
                usage['cost']=cost
            response_id=getattr(response,'id',None)
            complete=any(choice.finish_reason for choice in response.choices or [])
        try:
            self.accounting.finish(self.settings,usage,complete=complete,cost=cost,response_id=response_id)
        except Exception:
            pass  # A late reconciliation must never raise in a background thread; the record stays unresolved.


def build_generation_gateway(settings: ProviderSettings,http_client: httpx.Client | None = None,accounting=None) -> GenerationGateway:
    return OpenAIGenerationGateway(settings,http_client,accounting)
