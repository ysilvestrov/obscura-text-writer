from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest

from storygen.billing.models import Tariff, utcnow
from storygen.providers.discovery import discover_models
from storygen.providers.models import ProviderSettings


def row(provider):
    if provider == 'venice':
        return {'id':'test','object':'model','model_spec':{'uncensored':True,'offline':False,'availableContextTokens':200000,'maxCompletionTokens':24000,'pricing':{'input':{'usd':0.07},'output':{'usd':0.4}}}}
    return {'id':'test','object':'model','context_length':128000,'top_provider':{'max_completion_tokens':16000},'pricing':{'prompt':'0.000001','completion':'0.000002','request':'0.01'}}


@pytest.mark.parametrize('provider,context,output,input_rate,output_rate,fee',[('venice',200000,24000,'0.07','0.4','0'),('openrouter',128000,16000,'1','2','0.01')])
def test_catalog_exposes_exact_tariff_units_and_limits(monkeypatch,provider,context,output,input_rate,output_rate,fee):
    monkeypatch.setenv('VENICE_API_KEY','synthetic-key');monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-key')
    with httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(200,json={'data':[row(provider)]}))) as client:
        found=discover_models(ProviderSettings(provider=provider,model='test'),client)
    assert found[0].context_tokens==context
    assert found[0].max_output_tokens==output
    tariff=found[0].tariff
    assert tariff.input_per_million==Decimal(input_rate)
    assert tariff.output_per_million==Decimal(output_rate)
    assert tariff.request_usd==Decimal(fee)
    assert tariff.kind=='official' and tariff.current()


def test_manual_tariff_is_displayed_even_if_expired_and_local_is_unknown(monkeypatch):
    monkeypatch.setenv('VENICE_API_KEY','synthetic-key')
    manual=Tariff(provider='venice',model='test',base_url='https://api.venice.ai/api/v1',input_per_million='3',output_per_million='4',source='Synthetic manual quote',kind='manual',fetched_at=(utcnow()-timedelta(days=2)).isoformat(),expires_at=(utcnow()-timedelta(days=1)).isoformat())
    repo=SimpleNamespace(billing=lambda *_args,**_kwargs:manual.model_dump(mode='json'))
    with httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(200,json={'data':[row('venice')]}))) as client:
        found=discover_models(ProviderSettings(provider='venice',model='test'),client,repo=repo)
    assert found[0].tariff==manual and not found[0].tariff.current()
    with httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(200,json={'data':[{'id':'local-model','object':'model'}]}))) as client:
        found=discover_models(ProviderSettings(model='local-model'),client)
    assert found[0].tariff is None and found[0].max_output_tokens is None


def test_invalid_metadata_is_unknown_not_free_or_unlimited(monkeypatch):
    monkeypatch.setenv('VENICE_API_KEY','synthetic-key')
    invalid=row('venice');invalid['model_spec'].update(availableContextTokens=True,maxCompletionTokens=-1,pricing={'input':{'usd':-1},'output':{'usd':0}})
    with httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(200,json={'data':[invalid]}))) as client:
        found=discover_models(ProviderSettings(provider='venice',model='test'),client)
    assert found[0].context_tokens is None and found[0].max_output_tokens is None
    assert found[0].tariff is None


def test_current_cached_official_tariff_matches_billing_snapshot(monkeypatch):
    monkeypatch.setenv('VENICE_API_KEY','synthetic-key')
    cached=Tariff(provider='venice',model='test',base_url='https://api.venice.ai/api/v1',input_per_million='5',output_per_million='6',source='https://api.venice.ai/api/v1/models',kind='official',expires_at=(utcnow()+timedelta(hours=1)).isoformat())
    repo=SimpleNamespace(billing=lambda *_args,**_kwargs:cached.model_dump(mode='json'))
    with httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(200,json={'data':[row('venice')]}))) as client:
        found=discover_models(ProviderSettings(provider='venice',model='test'),client,repo=repo)
    assert found[0].tariff==cached


def venice_row(id,privacy='private',uncensored=False,schema=False,e2ee=False,tee=False,offline=False):
    caps={'supportsResponseSchema':schema,'supportsE2EE':e2ee,'supportsTeeAttestation':tee}
    return {'id':id,'object':'model','model_spec':{'name':id.upper(),'privacy':privacy,'uncensored':uncensored,'offline':offline,'capabilities':caps,
        'availableContextTokens':1000,'pricing':{'input':{'usd':1},'output':{'usd':2}}}}


def or_row(id,params):
    r={'id':id,'object':'model','name':id.upper(),'context_length':1000}
    if params is not None:r['supported_parameters']=params
    return r


def discover(rows,provider):
    with httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(200,json={'data':rows}))) as client:
        return discover_models(ProviderSettings(provider=provider,model='test'),client)


@pytest.mark.req('MODEL-005')
def test_venice_catalog_fields_become_badges(monkeypatch):
    monkeypatch.setenv('VENICE_API_KEY','synthetic-key')
    # anonymized uncensored, private schema, tee: all three are returned, offline is not
    rows=[venice_row('a',privacy='anonymized',uncensored=True),venice_row('p',privacy='private',schema=True),
          venice_row('t',privacy='private',e2ee=True,tee=True),venice_row('off',offline=True)]
    found={m.id:m for m in discover(rows,'venice')}
    assert set(found)=={'a','p','t'}
    assert (found['a'].privacy,found['a'].uncensored,found['a'].tee)==('anonymized',True,False)
    assert (found['p'].uncensored,found['p'].supports_schema)==(False,True)
    assert found['t'].tee is True and found['t'].privacy=='private' and found['t'].name=='T'


@pytest.mark.req('MODEL-005')
def test_missing_fields_stay_unknown(monkeypatch):
    monkeypatch.setenv('VENICE_API_KEY','synthetic-key')
    row=venice_row('x'); del row['model_spec']['privacy']; del row['model_spec']['pricing']
    m=discover([row],'venice')[0]
    assert m.privacy=='unknown' and m.tariff is None


@pytest.mark.req('MODEL-005')
def test_openrouter_schema_from_supported_parameters(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-key')
    rows=[or_row('s',['response_format','structured_outputs']),or_row('j',['response_format']),or_row('n',None)]
    found={m.id:m for m in discover(rows,'openrouter')}
    assert (found['s'].supports_schema,found['j'].supports_schema,found['n'].supports_schema)==(True,False,None)
    assert all(m.privacy=='unknown' and m.uncensored is None and m.tee is False for m in found.values())
    assert found['s'].name=='S'


@pytest.mark.req('MODEL-005')
def test_local_catalog_fields_are_unknown():
    m=discover([{'id':'l','object':'model'}],'local')[0]
    assert (m.privacy,m.tee,m.supports_schema,m.uncensored,m.name)==('unknown',False,None,None,None)
