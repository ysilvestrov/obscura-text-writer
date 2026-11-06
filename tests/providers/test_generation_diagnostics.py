import threading

import httpx
import pytest

from storygen.generation.context import ContextBundle
from storygen.providers.models import ProviderSettings,RoleSettings
from storygen.providers.streaming import build_generation_gateway


def context(provider='local',stage='memory',output=32000,window=262144):
    return ContextBundle(story_id='s',scene_id='c',stage=stage,scene_revision=0,story_revision=0,settings=RoleSettings(provider=ProviderSettings(provider=provider,model='test'),max_output_tokens=output,context_tokens=window),system_text='Synthetic system',user_text='Synthetic private document that must never appear in diagnostics.',input_refs=[],fingerprint='f',estimated_tokens=100)


@pytest.mark.parametrize('provider',['venice','openrouter'])
@pytest.mark.parametrize('output,window',[ (32000,200000), (16000,262144) ])
def test_known_limits_block_before_completion_post(monkeypatch,accounted_call,provider,output,window):
    monkeypatch.setenv('VENICE_API_KEY','synthetic-key');monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-key')
    methods=[]
    def handler(request):
        methods.append(request.method)
        if request.method=='GET':
            return httpx.Response(200,json={'data':[{'id':'test','object':'model','context_length':200000,'top_provider':{'max_completion_tokens':24000},'model_spec':{'uncensored':True,'offline':False,'availableContextTokens':200000,'maxCompletionTokens':24000}}]})
        return httpx.Response(400,json={'error':{'message':'Should not reach completion'}})
    ctx=context(provider,output=output,window=window)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        events=list(build_generation_gateway(ctx.settings.provider,client,accounted_call(provider,'test')).stream(ctx,threading.Event()))
    assert methods==['GET']
    assert events[-1].failure['category']=='configuration'
    assert '24000' in events[-1].message or '200000' in events[-1].message
    assert ctx.settings.max_output_tokens==output and ctx.settings.context_tokens==window


@pytest.mark.parametrize('stage',['draft','brief','edit','memory','prepare','rewrite','impact_part','review_part','classify','publication_suggest'])
def test_http_status_is_specific_and_structured_for_all_stages(stage):
    ctx=context(stage=stage,output=1000,window=8192)
    with httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(429,json={'error':{'code':'rate_limit_exceeded','message':'Slow down'}}))) as client:
        event=list(build_generation_gateway(ctx.settings.provider,client).stream(ctx,threading.Event()))[-1]
    assert event.type=='error' and event.failure['category']=='rate_limit'
    assert event.failure['http_status']==429
    assert '429' in event.message


def test_provider_echo_and_credentials_never_become_diagnostics():
    ctx=context(output=1000,window=8192)
    message='Bearer synthetic-key '+ctx.user_text
    with httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(400,json={'error':{'code':'invalid_parameter','message':message}}))) as client:
        event=list(build_generation_gateway(ctx.settings.provider,client).stream(ctx,threading.Event()))[-1]
    assert event.failure['http_status']==400
    assert 'synthetic-key' not in str(event.failure) and ctx.user_text not in event.message


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
