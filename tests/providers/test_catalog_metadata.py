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
