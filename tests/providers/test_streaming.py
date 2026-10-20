import json
import threading
import httpx
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.providers.streaming import build_generation_gateway
from storygen.generation.context import ContextBundle


def context():
    return ContextBundle(story_id='s',scene_id='c',stage='draft',scene_revision=0,story_revision=0,settings=RoleSettings(provider=ProviderSettings(model='test')),system_text='Українська',user_text='Пиши',input_refs=[],fingerprint='f',estimated_tokens=10)


def stream_response(chunks):
    return httpx.Response(200,headers={'content-type':'text/event-stream'},content=''.join('data: '+json.dumps(c,ensure_ascii=False)+'\n\n' for c in chunks)+'data: [DONE]\n\n')


def chunk(delta=None,finish=None):
    return {'id':'r','object':'chat.completion.chunk','created':0,'model':'test','choices':[{'index':0,'delta':delta or {},'finish_reason':finish}]}


def test_deltas_and_terminal_are_preserved():
    calls=[]
    def handler(request):
        calls.append(request)
        return stream_response([chunk({'content':'Лєра '}),chunk({'content':'увійшла.'}),chunk(finish='stop'),{'id':'r','object':'chat.completion.chunk','created':0,'model':'test','choices':[],'usage':{'prompt_tokens':5,'completion_tokens':3,'total_tokens':8}}])
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        events=list(build_generation_gateway(context().settings.provider,http_client=http).stream(context(),threading.Event()))
    assert ''.join(e.text for e in events if e.type=='delta')=='Лєра увійшла.'
    assert events[-1].type=='terminal' and events[-1].finish_reason=='stop'
    assert events[-1].usage['total_tokens']==8 and len(calls)==1


def test_length_refusal_and_disconnect_keep_partial():
    for finish,delta in [('length',{'content':'Частина'}),('stop',{'refusal':'Не можу'})]:
        with httpx.Client(transport=httpx.MockTransport(lambda r:stream_response([chunk(delta),chunk(finish=finish)]))) as http:
            events=list(build_generation_gateway(context().settings.provider,http_client=http).stream(context(),threading.Event()))
        assert events[-1].type=='error'
        assert events[0].text in {'Частина','Не можу'}


def test_timeout_has_one_attempt():
    calls=[]
    def handler(request):
        calls.append(request);raise httpx.ReadTimeout('private key must not leak')
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        events=list(build_generation_gateway(context().settings.provider,http_client=http).stream(context(),threading.Event()))
    assert len(calls)==1 and events[-1].type=='error'
    assert 'private' not in events[-1].message


def test_cancel_during_stream_closes_reader():
    cancel=threading.Event()
    with httpx.Client(transport=httpx.MockTransport(lambda r:stream_response([chunk({'content':'Раз'}),chunk({'content':'Два'}),chunk(finish='stop')]))) as http:
        stream=build_generation_gateway(context().settings.provider,http_client=http).stream(context(),cancel)
        assert next(stream).text=='Раз'
        cancel.set()
        assert list(stream)[-1].type=='cancelled'


def test_disconnect_without_stop_keeps_delta():
    class BrokenStream(httpx.SyncByteStream):
        def __iter__(self):
            yield ('data: '+json.dumps(chunk({'content':'Збережена частина'}),ensure_ascii=False)+'\n\n').encode()
            raise httpx.ReadError('connection lost')
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,headers={'content-type':'text/event-stream'},stream=BrokenStream()))) as http:
        events=list(build_generation_gateway(context().settings.provider,http_client=http).stream(context(),threading.Event()))
    assert events[0].text=='Збережена частина'
    assert events[-1].type=='error' and events[-1].finish_reason is None


def test_explicit_protocol_stop_is_sent_without_changing_prompts():
    from storygen.providers.models import RoleSettings,ProviderSettings
    from storygen.generation.context import ContextBundle
    role=RoleSettings(provider=ProviderSettings(model='c4ai-command-r-08-2024'),stop_sequences=['<|END_OF_TURN_TOKEN|>'])
    context=ContextBundle(story_id='s',scene_id='c',stage='draft',scene_revision=0,story_revision=0,settings=role,system_text='Українська',user_text='Пиши без підміни.',input_refs=[],fingerprint='f',estimated_tokens=10)
    requests=[]
    def handler(request):
        requests.append(json.loads(request.content))
        return stream_response([chunk({'content':'Готово'}),chunk(finish='stop')])
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        events=list(build_generation_gateway(role.provider,http_client=http).stream(context,threading.Event()))
    assert requests[0]['stop']==['<|END_OF_TURN_TOKEN|>']
    assert requests[0]['messages'][1]['content']=='Пиши без підміни.'
    assert events[-1].finish_reason=='stop'


def test_evidence_delta_and_copyedits_use_their_own_structured_schemas():
    for stage,mode,expected in [('memory',{'memory_mode':'evidence_delta'},'facts'),('edit',{'edit_mode':'patches'},'edits')]:
        ctx=context();ctx.stage=stage
        ctx.settings=RoleSettings(provider=ProviderSettings(model='test',response_mode='json_schema'),**mode)
        requests=[]
        def handler(request):
            requests.append(json.loads(request.content))
            return stream_response([chunk({'content':'{}'}),chunk(finish='stop')])
        with httpx.Client(transport=httpx.MockTransport(handler)) as http:
            assert list(build_generation_gateway(ctx.settings.provider,http_client=http).stream(ctx,threading.Event()))[-1].type=='terminal'
        schema=requests[0]['response_format']['json_schema']['schema']
        assert expected in schema['properties']
        assert 'source_prose_ids' not in schema['properties']


def test_output_length_limit_has_actionable_error_without_retry():
 calls=[]
 def handler(request):
  calls.append(request)
  return stream_response([chunk({'content':'Часткова відповідь'}),chunk(finish='length')])
 ctx=context()
 with httpx.Client(transport=httpx.MockTransport(handler)) as http:
  events=list(build_generation_gateway(ctx.settings.provider,http_client=http).stream(ctx,threading.Event()))
 assert len(calls)==1 and events[-1].type=='error'
 assert 'ліміт' in events[-1].message.lower() and str(ctx.settings.max_output_tokens) in events[-1].message
