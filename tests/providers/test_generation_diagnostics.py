import threading

import httpx
import pytest

from storygen.generation.context import ContextBundle
from storygen.providers.models import ProviderSettings,RoleSettings
from storygen.providers.streaming import build_generation_gateway


def context(provider='local',stage='memory',output=32000,window=262144):
    return ContextBundle(story_id='s',scene_id='c',stage=stage,scene_revision=0,story_revision=0,settings=RoleSettings(provider=ProviderSettings(provider=provider,model='test'),max_output_tokens=output,context_tokens=window),system_text='Synthetic system',user_text='Synthetic private document that must never appear in diagnostics.',input_refs=[],fingerprint='f',estimated_tokens=100)


@pytest.mark.parametrize('provider',['venice','openrouter'])
@pytest.mark.parametrize('output,input_tokens,expected',[(32000,100,'Вихідний ліміт 32000 перевищує ліміт вибраної моделі 24000 токенів. Змініть налаштування; автоматичного повтору немає.'),(16000,246144,'Контекст 262144 перевищує ліміт вибраної моделі 200000 токенів. Змініть налаштування; автоматичного повтору немає.')])
def test_known_limits_block_before_completion_post(monkeypatch,accounted_call,provider,output,input_tokens,expected):
    monkeypatch.setenv('VENICE_API_KEY','synthetic-key');monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-key')
    methods=[]
    def handler(request):
        methods.append(request.method)
        if request.method=='GET':
            return httpx.Response(200,json={'data':[{'id':'test','object':'model','context_length':200000,'top_provider':{'max_completion_tokens':24000},'model_spec':{'uncensored':True,'offline':False,'availableContextTokens':200000,'maxCompletionTokens':24000}}]})
        return httpx.Response(400,json={'error':{'message':'Should not reach completion'}})
    ctx=context(provider,output=output,window=262144);ctx.estimated_tokens=input_tokens
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        events=list(build_generation_gateway(ctx.settings.provider,client,accounted_call(provider,'test')).stream(ctx,threading.Event()))
    assert methods==['GET']
    assert events[-1].failure['category']=='configuration'
    assert events[-1].message==expected
    assert ctx.settings.max_output_tokens==output and ctx.settings.context_tokens==262144


@pytest.mark.parametrize('stage',['draft','brief','edit','memory','prepare','rewrite','impact_delta','impact_check','impact_part','review_part','classify','publication_suggest'])
@pytest.mark.parametrize('provider',['local','venice','openrouter'])
@pytest.mark.parametrize('status,code,reason,category',[(400,'invalid_parameter','Synthetic invalid parameter','provider_error'),(401,'invalid_api_key','Провайдер не прийняв API-ключ.','authentication'),(429,'rate_limit_exceeded','Перевищено ліміт частоти запитів провайдера.','rate_limit')])
def test_http_status_is_specific_and_structured_for_all_stages(monkeypatch,accounted_call,stage,provider,status,code,reason,category):
    monkeypatch.setenv('VENICE_API_KEY','synthetic-key');monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-key')
    ctx=context(provider,stage=stage,output=1000,window=8192);calls=[]
    def handler(request):
        calls.append(request.method)
        if request.method=='GET':return httpx.Response(200,json={'data':[{'id':'test','object':'model','model_spec':{'uncensored':True,'offline':False}}]})
        return httpx.Response(status,json={'error':{'code':code,'message':reason}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        event=list(build_generation_gateway(ctx.settings.provider,client,accounted_call(provider,'test') if provider!='local' else None).stream(ctx,threading.Event()))[-1]
    assert event.type=='error' and event.failure['category']==category
    assert event.failure['http_status']==status
    assert event.message==f'HTTP {status}: {reason} Автоматичного повтору немає.'
    assert calls==(['POST'] if provider=='local' else ['GET','POST'])


def test_provider_echo_and_credentials_never_become_diagnostics(monkeypatch):
    ctx=context(output=1000,window=8192)
    monkeypatch.setenv('SYNTHETIC_PROVIDER_KEY','synthetic-key');ctx.settings.provider.key_env='SYNTHETIC_PROVIDER_KEY'
    message='synthetic-key '+ctx.user_text
    with httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(400,json={'error':{'code':'invalid_parameter','message':message}}))) as client:
        event=list(build_generation_gateway(ctx.settings.provider,client).stream(ctx,threading.Event()))[-1]
    assert event.failure['http_status']==400
    assert event.failure['provider_message']=='Пояснення провайдера містить відлуння запиту; текст приховано.'
    assert event.message=='HTTP 400: Пояснення провайдера містить відлуння запиту; текст приховано. Автоматичного повтору немає.'


@pytest.mark.parametrize('error_type,category',[('timeout','timeout'),('connection','connection')])
def test_transport_failures_are_specific_and_never_retried(error_type,category):
    ctx=context(output=1000,window=8192);calls=[]
    def handler(request):
        calls.append(request)
        error={'timeout':httpx.ReadTimeout,'connection':httpx.ConnectError}[error_type]
        raise error('Synthetic transport failure',request=request)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        event=list(build_generation_gateway(ctx.settings.provider,client).stream(ctx,threading.Event()))[-1]
    assert len(calls)==1
    assert event.failure['category']==category and event.failure['http_status'] is None
    assert 'Synthetic transport failure' not in event.message


def test_missing_provider_key_is_safe_configuration_failure(monkeypatch,accounted_call):
    monkeypatch.delenv('VENICE_API_KEY',raising=False)
    ctx=context('venice');calls=[]
    with httpx.Client(transport=httpx.MockTransport(lambda r:calls.append(r))) as client:
        event=list(build_generation_gateway(ctx.settings.provider,client,accounted_call('venice','test')).stream(ctx,threading.Event()))[-1]
    assert calls==[] and event.failure['category']=='configuration'
    assert 'Ключ провайдера відсутній' in event.message


@pytest.mark.parametrize('provider',['venice','openrouter'])
def test_failed_cloud_catalog_never_starts_completion(monkeypatch,accounted_call,provider):
    monkeypatch.setenv('VENICE_API_KEY','synthetic-key');monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-key')
    calls=[]
    def handler(request):
        calls.append(request.method)
        return httpx.Response(503,json={'error':{'message':'Synthetic catalog unavailable'}})
    ctx=context(provider)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        event=list(build_generation_gateway(ctx.settings.provider,client,accounted_call(provider,'test')).stream(ctx,threading.Event()))[-1]
    assert calls==['GET']
    assert event.failure['http_status']==503 and event.type=='error'


def test_unexpected_internal_failure_is_neutral_and_never_echoed(monkeypatch):
    import storygen.providers.streaming as streaming
    ctx=context(output=1000,window=8192)
    def fail(*_):raise RuntimeError('Synthetic private internals')
    monkeypatch.setattr(streaming,'sdk_arguments',fail)
    with httpx.Client(transport=httpx.MockTransport(lambda _:None)) as client:
        event=list(build_generation_gateway(ctx.settings.provider,client).stream(ctx,threading.Event()))[-1]
    assert event.failure['category']=='technical'
    assert event.message=='Не вдалося завершити запит; точну причину не встановлено. Автоматичного повтору немає.'


@pytest.mark.parametrize('provider',['venice','openrouter'])
@pytest.mark.parametrize('caps',['missing','boundary','large_setting'])
def test_successful_catalog_allows_unknown_or_fitting_actual_request(monkeypatch,accounted_call,provider,caps):
    monkeypatch.setenv('VENICE_API_KEY','synthetic-key');monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-key')
    calls=[]
    row={'id':'test','object':'model','model_spec':{'uncensored':True,'offline':False}}
    if caps!='missing':
        row.update(context_length=256000,top_provider={'max_completion_tokens':8192})
        row['model_spec'].update(availableContextTokens=256000,maxCompletionTokens=8192)
    def handler(request):
        calls.append(request.method)
        if request.method=='GET':return httpx.Response(200,json={'data':[row]})
        return httpx.Response(200,headers={'content-type':'text/event-stream'},text='data: {"id":"synthetic","choices":[{"index":0,"delta":{"content":"Done"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')
    ctx=context(provider,output=8192,window=262144)
    ctx.estimated_tokens=247808 if caps=='boundary' else 101778
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        events=list(build_generation_gateway(ctx.settings.provider,client,accounted_call(provider,'test')).stream(ctx,threading.Event()))
    assert calls==['GET','POST']
    assert events[-1].type=='terminal',events[-1].message
    assert ctx.settings.context_tokens==262144


def test_secret_scrub_uses_configured_key_without_bearer_or_echo(monkeypatch):
    ctx=context(output=1000,window=8192)
    monkeypatch.setenv('SYNTHETIC_PROVIDER_KEY','synthetic-credential');ctx.settings.provider.key_env='SYNTHETIC_PROVIDER_KEY'
    with httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(400,json={'error':{'message':'Denied synthetic-credential'}}))) as client:
        event=list(build_generation_gateway(ctx.settings.provider,client).stream(ctx,threading.Event()))[-1]
    assert event.failure['provider_message']=='Denied [ключ приховано]'


def test_openrouter_successful_catalog_missing_alias_still_completes(monkeypatch,accounted_call):
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-key');calls=[]
    def handler(request):
        calls.append(request.method)
        if request.method=='GET':return httpx.Response(200,json={'data':[]})
        return httpx.Response(200,headers={'content-type':'text/event-stream'},text='data: {"choices":[{"index":0,"delta":{"content":"Done"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')
    ctx=context('openrouter',output=1000,window=8192)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        event=list(build_generation_gateway(ctx.settings.provider,client,accounted_call('openrouter','test')).stream(ctx,threading.Event()))[-1]
    assert calls==['GET','POST'] and event.type=='terminal'
