import json
import pytest
import httpx
from storygen.storage.repository import Repository
from storygen.providers.accounting import CallAccounting
from storygen.providers.models import ProviderSettings
from storygen.billing.service import set_limit,save_tariff
from storygen.billing.models import Tariff,utcnow,BudgetError
from datetime import timedelta


def test_live_cli_cannot_be_manually_settled(accounted_call):
    accounting=accounted_call('openrouter','m')
    config=ProviderSettings(provider='openrouter',model='m')
    accounting.before(config,{'model':'m','messages':[],'max_tokens':10})
    try:
        with pytest.raises(BudgetError):
            accounting.repo.billing('manual',scope=accounting.scope,call_id=accounting.call_id,amount_nanos=0,source='incorrect active reconciliation')
    finally:accounting.finish(config,{},complete=False)


@pytest.mark.parametrize('refusal',[None,'I cannot evaluate this content'])
def test_invalid_usage_does_not_destroy_text_or_refusal(monkeypatch,accounted_call,refusal):
    from storygen.evaluation.gateway import OpenAICompatibleGateway,GatewayFailure
    from storygen.evaluation.models import EvaluatorConfig,EvaluationRequest
    monkeypatch.setenv('OPENROUTER_API_KEY','test')
    response={'id':'r','object':'chat.completion','created':0,'model':'m',
        'choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':'{}','refusal':refusal}}],'usage':'invalid'}
    accounting=accounted_call('openrouter','m')
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=response))) as client:
        gateway=OpenAICompatibleGateway(EvaluatorConfig(provider='openrouter',model='m',max_input_chars=10000),client,accounting)
        request=EvaluationRequest(messages=[{'role':'user','content':'text'}],response_schema={},response_mode='prompt_json',temperature=None,max_output_tokens=10)
        if refusal:
            with pytest.raises(GatewayFailure) as caught:gateway.complete(request)
            assert caught.value.detail.category.startswith('refusal_')
        else:assert gateway.complete(request).text=='{}'
    assert accounting.repo.billing('calls',scope=accounting.scope)[0]['state']=='unresolved'


def test_lease_released_after_failure_allows_reconciliation(accounted_call):
    accounting=accounted_call('openrouter','m')
    config=ProviderSettings(provider='openrouter',model='m')
    accounting.before(config,{'model':'m','messages':[],'max_tokens':10})
    accounting.finish(config,{},complete=False)
    result=accounting.repo.billing('manual',scope=accounting.scope,call_id=accounting.call_id,amount_nanos=0,source='provider dashboard verified no charge')
    assert result['state']=='settled' and result['counted_nanos']==0


@pytest.mark.parametrize('final_usage',[{'prompt_tokens':100},'bad'])
def test_stream_final_usage_is_one_snapshot(monkeypatch,accounted_call,final_usage):
    import threading
    from storygen.generation.context import ContextBundle
    from storygen.providers.models import RoleSettings
    from storygen.providers.streaming import build_generation_gateway
    monkeypatch.setenv('OPENROUTER_API_KEY','test')
    config=ProviderSettings(provider='openrouter',model='m',include_usage=True)
    ctx=ContextBundle(story_id='s',scene_id='c',stage='draft',scene_revision=0,story_revision=0,
        settings=RoleSettings(provider=config),system_text='system',user_text='text',input_refs=[],fingerprint='f',estimated_tokens=10)
    chunks=[{'id':'r','object':'chat.completion.chunk','created':0,'model':'m','usage':{'prompt_tokens':1,'completion_tokens':1},
        'choices':[{'index':0,'delta':{'content':'prose'},'finish_reason':None}]},
        {'id':'r','object':'chat.completion.chunk','created':0,'model':'m','usage':final_usage,
        'choices':[{'index':0,'delta':{},'finish_reason':'stop'}]}]
    payload=''.join('data: '+json.dumps(c)+'\n\n' for c in chunks)+'data: [DONE]\n\n'
    accounting=accounted_call('openrouter','m')
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,text=payload,headers={'content-type':'text/event-stream'}))) as client:
        events=list(build_generation_gateway(config,client,accounting).stream(ctx,threading.Event()))
    assert events[-1].type=='terminal' and events[0].text=='prose'
    item=accounting.repo.billing('calls',scope=accounting.scope)[0]
    assert item['state']=='unresolved' and item['counted_nanos']==item['reserved_nanos']


def test_budget_cli_respects_root_lock(tmp_path,capsys):
    from storygen.storage.locking import AppInstanceLock
    from storygen.billing.cli import main
    with AppInstanceLock(tmp_path):
        assert main(['--data-dir',str(tmp_path),'--scope','cli:test','summary'])==2
    assert not (tmp_path/'storygen.sqlite3').exists()
    assert main(['--data-dir',str(tmp_path),'--scope','cli:test','summary'])==0


def test_unpriced_scope_validated_before_write(tmp_path):
    repo=Repository(tmp_path)
    with pytest.raises(BudgetError):
        repo.billing('unpriced',scope='foo',run_id='r',call_id='c',provider='local',model='m',request_hash='h')
    assert repo.billing('calls',scope='foo')==[]
