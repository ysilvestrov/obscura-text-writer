import json
import pytest
from tests.impact.test_runner import runner
from storygen.generation.dependencies import save_manual_prose
from storygen.authoring.blueprints import save_role_settings
from storygen.providers.models import RoleSettings,ProviderSettings
from storygen.generation.impact_context import readiness
from storygen.providers.streaming import GenerationEvent
from storygen.run_models import RunRequest


def chunk_runner(root):
    repo,story,first,second,ref,worker,oldrun,_=runner(root)
    worker.cancel(oldrun.id)
    save_manual_prose(repo,first.id,'Марія знає про лист. '*120,repo.get_scene(first.id).revision)
    head=save_manual_prose(repo,second.id,'Марія читає лист і посміхається. '*140,repo.get_scene(second.id).revision)
    save_manual_prose(repo,first.id,'Марія знає про лист. Вечір настав. '*120,repo.get_scene(first.id).revision)
    save_role_settings(repo,story.id,'planner',RoleSettings(provider=ProviderSettings(model='synthetic-impact'),context_tokens=24000,max_output_tokens=2048,max_input_chars=14000),repo.get_story(story.id).revision)
    calls=[]
    class Gateway:
        def stream(self,ctx,cancel):
            calls.append(ctx);data=json.loads(ctx.user_text)
            raw=dict(covered_ids=data['required_coverage'],summary='Передумови перевірено, суперечностей немає.',verdict='no_impact',findings=[],evidence=[],uncertainty=None)
            yield GenerationEvent(type='delta',text=json.dumps(raw,ensure_ascii=False))
            yield GenerationEvent(type='terminal',finish_reason='stop',usage={'prompt_tokens':100,'completion_tokens':50})
    worker.gateway_factory=lambda _:Gateway()
    request=RunRequest(story_id=story.id,mode='impact')
    preview=readiness(repo,request)
    assert preview['ready'],preview['reason']
    assert preview['protocol']==2
    request.impact_plan_fingerprint=preview['chunk_manifest']['fingerprint']
    run=worker.enqueue(request,'chunked')
    return repo,story,second,worker,run,calls,preview


def test_chunk_run_full_coverage_and_replayable_report(tmp_path):
    repo,story,second,worker,run,calls,preview=chunk_runner(tmp_path)
    worker._execute(run.id)
    assert worker.get_run(run.id).state=='completed',worker.get_run(run.id).error
    assert len(calls)==preview['calls']
    rows=repo.impact('state',story_id=story.id)
    assert rows and rows[-1]['record'].schema_version==2 and rows[-1]['current']
    assert not repo.get_version(repo.get_scene(second.id).heads['prose']).stale
    assert len(rows[-1]['record'].proof_attempt_ids)>2


def test_recovery_and_settings_change(tmp_path,monkeypatch):
    from storygen.generation import impact_chunk_runner
    repo,story,second,worker,run,calls,preview=chunk_runner(tmp_path)
    original=impact_chunk_runner.advance
    monkeypatch.setattr(impact_chunk_runner,'advance',lambda *args:(_ for _ in ()).throw(RuntimeError('crash before checkpoint')))
    worker._execute(run.id)
    assert len(calls)==1
    monkeypatch.setattr(impact_chunk_runner,'advance',original)
    worker.resume(run.id);worker._execute(run.id)
    assert worker.get_run(run.id).state=='completed',worker.get_run(run.id).error
    assert len(calls)==preview['calls']


def test_refusal_stops_chunk_series(tmp_path):
    repo,story,second,worker,run,calls,preview=chunk_runner(tmp_path)
    class Refuses:
        def stream(self,ctx,cancel):
            calls.append(ctx);yield GenerationEvent(type='terminal',finish_reason='stop',refusal=True,message='Не можу оцінити.')
    worker.gateway_factory=lambda _:Refuses()
    worker._execute(run.id)
    assert worker.get_run(run.id).state=='failed' and len(calls)==1
    assert not repo.impact('state',story_id=story.id)
    assert repo.list_attempts(story.id,run.id)[0].context['impact_failure']['category']=='refusal_unknown'


def test_chunk_report_backup_and_missing_proof(tmp_path):
    from storygen.storage.integrity import check_integrity
    from storygen.storage.backup import create_backup,restore_backup
    from storygen.storage.repository import Repository
    repo,story,second,worker,run,calls,preview=chunk_runner(tmp_path/'data')
    worker._execute(run.id)
    assert worker.get_run(run.id).state=='completed'
    assert check_integrity(repo.root).ok
    create_backup(repo.root,tmp_path/'backup');restore_backup(tmp_path/'backup',tmp_path/'restored')
    restored=Repository(tmp_path/'restored')
    rows=restored.impact('state',story_id=story.id);assert rows[-1]['current']
    record=rows[-1]['record'];missing=next(iter(record.proof_attempt_ids.values()))
    with restored.db.connection() as db:db.execute('DELETE FROM stage_attempts WHERE id=?',(missing,))
    assert not restored.impact('state',story_id=story.id)[-1]['current']
    assert not check_integrity(restored.root).ok


def test_settings_change_stops_before_next_dispatch(tmp_path):
    repo,story,second,worker,run,calls,preview=chunk_runner(tmp_path)
    original=worker.gateway_factory
    class ChangesSettings:
        def stream(self,ctx,cancel):
            yield from original(None).stream(ctx,cancel)
            changed=ctx.settings.model_copy(update={'temperature':0.1})
            save_role_settings(repo,story.id,'planner',changed,repo.get_story(story.id).revision)
    worker.gateway_factory=lambda _:ChangesSettings()
    worker._execute(run.id)
    assert worker.get_run(run.id).state=='failed' and len(calls)==1
    assert 'Налаштування' in worker.get_run(run.id).error
    assert not repo.impact('state',story_id=story.id)


def test_changed_target_does_not_publish_chunk_report(tmp_path):
    repo,story,second,worker,run,calls,preview=chunk_runner(tmp_path)
    original=worker.gateway_factory
    class ChangesText:
        def stream(self,ctx,cancel):
            yield from original(None).stream(ctx,cancel)
            save_manual_prose(repo,second.id,'Інший текст.',repo.get_scene(second.id).revision)
    worker.gateway_factory=lambda _:ChangesText()
    worker._execute(run.id)
    assert worker.get_run(run.id).state=='alternative' and len(calls)==1
    assert not repo.impact('state',story_id=story.id)


def test_actual_api_body_is_part_of_chunk_proof(tmp_path):
    repo,story,second,worker,run,calls,preview=chunk_runner(tmp_path)
    worker._execute(run.id)
    record=repo.impact('state',story_id=story.id)[-1]['record']
    attempt=repo.get_attempt(record.attempt_id)
    attempt.context['api_request']['messages'][1]['content']='Інший запит'
    repo.save_attempt(attempt)
    assert not repo.impact('state',story_id=story.id)[-1]['current']


def test_pause_and_cancel_preserve_completed_parts(tmp_path):
    from storygen.generation import impact_chunk_runner
    repo,story,second,worker,run,calls,preview=chunk_runner(tmp_path)
    original=worker.gateway_factory
    class Pause:
        def stream(self,ctx,cancel):
            yield from original(None).stream(ctx,cancel)
            worker.pause(run.id)
    worker.gateway_factory=lambda _:Pause()
    worker._execute(run.id)
    paused=worker.get_run(run.id)
    assert paused.state=='paused' and paused.cursor==1 and len(calls)==1
    worker.cancel(run.id)
    assert worker.get_run(run.id).state=='cancelled'
    assert len(repo.list_attempts(story.id,run.id))==1 and not repo.impact('state',story_id=story.id)


def test_memory_parts_preserve_historical_journal(tmp_path):
    from tests.memory.test_forwarding import seeded
    from storygen.generation.worker import RunCoordinator
    repo,story,scenes=seeded(tmp_path)
    original={s.heads['memory']:repo.read_text(s.heads['memory']) for s in scenes}
    first=repo.get_scene(scenes[0].id)
    save_manual_prose(repo,first.id,repo.read_text(first.heads['prose'])+' Настав вечір.'*400,first.revision)
    save_role_settings(repo,story.id,'planner',RoleSettings(provider=ProviderSettings(model='synthetic-impact'),context_tokens=32768,max_output_tokens=2048,max_input_chars=10000),repo.get_story(story.id).revision)
    class Gateway:
        def stream(self,ctx,cancel):
            d=json.loads(ctx.user_text);raw=dict(covered_ids=d['required_coverage'],summary='Перевірено всі частини.',verdict='no_impact',findings=[],evidence=[],uncertainty=None)
            yield GenerationEvent(type='delta',text=json.dumps(raw,ensure_ascii=False))
            yield GenerationEvent(type='terminal',finish_reason='stop')
    worker=RunCoordinator(repo,lambda _:Gateway());request=RunRequest(story_id=story.id,mode='impact')
    prepared=readiness(repo,request);assert prepared['ready'],prepared['reason']
    assert prepared['protocol']==2
    request.impact_plan_fingerprint=prepared['chunk_manifest']['fingerprint']
    run=worker.enqueue(request,'memory-chunks');worker._execute(run.id)
    assert worker.get_run(run.id).state=='completed',worker.get_run(run.id).error
    rows=repo.impact('state',story_id=story.id)
    assert rows and all(row['record'].memory_semantic_impact=='none_found' for row in rows)
    assert all(row['memory_evidence_status']=='historical' and row['memory_needs_update'] for row in rows)
    for id,text in original.items():assert repo.read_text(id)==text


def test_chunk_hard_run_budget_prevents_paid_dispatch(tmp_path,monkeypatch):
    import httpx
    from datetime import datetime,timedelta,timezone
    from storygen.billing.models import Tariff
    from storygen.billing.service import set_limit,save_tariff
    from storygen.providers.streaming import build_generation_gateway
    repo,story,second,worker,old,calls,prepared=chunk_runner(tmp_path)
    worker.cancel(old.id)
    role=RoleSettings(provider=ProviderSettings(provider='openrouter',model='synthetic-impact'),context_tokens=24000,max_output_tokens=2048,max_input_chars=14000)
    save_role_settings(repo,story.id,'planner',role,repo.get_story(story.id).revision)
    set_limit(repo,'story:'+story.id,'10',0)
    save_tariff(repo,Tariff(provider='openrouter',model=role.provider.model,base_url=role.provider.base_url,input_per_million='1',output_per_million='2',source='synthetic',kind='manual',expires_at=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()))
    request=RunRequest(story_id=story.id,mode='impact',budget_limit_usd='0')
    prepared=readiness(repo,request);assert prepared['ready'],prepared['reason']
    assert prepared['upper_cost_nanos']>0
    request.impact_plan_fingerprint=prepared['chunk_manifest']['fingerprint']
    run=worker.enqueue(request,'zero-budget-chunks');requests=[]
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-key')
    with httpx.Client(transport=httpx.MockTransport(lambda r:requests.append(r) or httpx.Response(500))) as http:
        worker.gateway_factory=lambda settings:build_generation_gateway(settings,http_client=http)
        worker._execute(run.id)
    assert worker.get_run(run.id).state=='failed'
    assert not any(r.method=='POST' for r in requests)
    assert not repo.impact('state',story_id=story.id)


def test_native_schema_and_findings_survive_synthesis(tmp_path,monkeypatch):
    from storygen.impact import chunking
    monkeypatch.setattr(chunking,'wire_version_for',lambda role:1)
    repo,story,second,worker,old,calls,prepared=chunk_runner(tmp_path)
    worker.cancel(old.id)
    role=RoleSettings(provider=ProviderSettings(model='synthetic-impact',response_mode='json_schema'),context_tokens=24000,max_output_tokens=2048,max_input_chars=14000)
    save_role_settings(repo,story.id,'planner',role,repo.get_story(story.id).revision)
    request=RunRequest(story_id=story.id,mode='impact');prepared=readiness(repo,request)
    assert prepared['ready'],prepared['reason']
    request.impact_plan_fingerprint=prepared['chunk_manifest']['fingerprint'];run=worker.enqueue(request,'native-parts')
    issued=[]
    class Findings:
        def stream(self,ctx,cancel):
            d=json.loads(ctx.user_text);assert 'covered_ids' in ctx.api_request['response_format']['json_schema']['schema']['properties']
            findings={json.dumps(f,sort_keys=True):f for child in d['results'].values() for f in child['findings']} if d['phase'].startswith('reduce_') else {}
            if d['phase']=='check' and not issued and any(u['changed'] and d['documents'][u['document_id']] for u in d['sources']):
                u=next(u for u in d['sources'] if u['changed'] and d['documents'][u['document_id']])
                finding=dict(target_quote=d['target']['text'][:8],change_ids=[u['change_id']],explanation='Уточніть подію.',evidence=[dict(source_id=u['source_id'],quote=d['documents'][u['document_id']][:8])])
                findings['one']=finding;issued.append(True)
            raw=dict(covered_ids=d['required_coverage'],summary='Зведено перевірені частини.',verdict='changes_required' if findings else 'no_impact',findings=list(findings.values()),evidence=[],uncertainty=None)
            yield GenerationEvent(type='delta',text=json.dumps(raw,ensure_ascii=False))
            yield GenerationEvent(type='terminal',finish_reason='stop')
    worker.gateway_factory=lambda _:Findings();worker._execute(run.id)
    assert worker.get_run(run.id).state=='completed',worker.get_run(run.id).error
    row=repo.impact('state',story_id=story.id)[-1]
    assert row['current'] and row['record'].verdict.verdict=='changes_required' and len(row['record'].verdict.findings)==1
