import json
from storygen.authoring.blueprints import save_role_settings
from storygen.providers.models import RoleSettings,ProviderSettings
from storygen.providers.streaming import GenerationEvent
from storygen.generation.worker import RunCoordinator
from storygen.run_models import RunRequest
from storygen.impact.planning import plan_impact
from storygen.generation.dependencies import save_manual_prose
from tests.impact.test_planning import seeded


def runner(root,verdict='no_impact'):
    repo,story,first,second,ref=seeded(root)
    save_manual_prose(repo,first.id,'Марія знає про лист. Вечір настав.',repo.get_scene(first.id).revision)
    save_role_settings(repo,story.id,'planner',RoleSettings(provider=ProviderSettings(model='synthetic-impact'),context_tokens=32768,max_output_tokens=2048),repo.get_story(story.id).revision)
    calls=[]
    class Gateway:
        def stream(self,ctx,cancel):
            calls.append(ctx);target=json.loads(ctx.fragments['impact_target']);ids=[c['id'] for c in target['changes'] if c['changed']]
            if ctx.stage=='impact_delta':raw=dict(covered_change_ids=ids,items=[],uncertainty=None)
            else:raw=dict(materials=[dict(version_id=target['version_id'],verdict=verdict,covered_change_ids=ids,explanation='Перевірено всі передумови.',findings=[])],memory_semantic_impact='unchecked',memory_explanation='Потрібне окреме оновлення.')
            yield GenerationEvent(type='delta',text=json.dumps(raw,ensure_ascii=False))
            yield GenerationEvent(type='terminal',finish_reason='stop',usage={'prompt_tokens':100,'completion_tokens':50})
    worker=RunCoordinator(repo,lambda _:Gateway());plan=plan_impact(repo.context_view(story.id))
    request=RunRequest(story_id=story.id,mode='impact',impact_plan_fingerprint=plan.fingerprint)
    run=worker.enqueue(request,'impact')
    return repo,story,first,second,ref,worker,run,calls


def test_two_phase_analysis_publishes_no_impact_without_rewriting(tmp_path):
    repo,story,first,second,ref,worker,run,calls=runner(tmp_path)
    worker._execute(run.id)
    current=worker.get_run(run.id)
    assert current.state=='completed',current.error
    assert [c.stage for c in calls]==['impact_delta','impact_check']
    assert not repo.get_version(ref.id).stale
    assert repo.get_scene(second.id).heads['prose']==ref.id
    assert repo.read_text(ref.id)=='Марія згадала лист.'


def test_saved_attempt_recovery_never_repeats_model(tmp_path,monkeypatch):
    from storygen.generation import impact_runner
    repo,story,first,second,ref,worker,run,calls=runner(tmp_path)
    real=impact_runner.advance
    def crash(*args):raise RuntimeError('saved before checkpoint')
    monkeypatch.setattr(impact_runner,'advance',crash)
    worker._execute(run.id)
    assert len(calls)==1
    monkeypatch.setattr(impact_runner,'advance',real)
    worker.resume(run.id);worker._execute(run.id)
    assert worker.get_run(run.id).state=='completed' and len(calls)==2

import pytest

@pytest.mark.parametrize('event,category',[
    (GenerationEvent(type='terminal',finish_reason='stop',refusal=True,message='Контент недоступний.'),'refusal_unknown'),
    (GenerationEvent(type='error',finish_reason='content_filter',message='Відмова провайдера.'),'refusal_content'),
    (GenerationEvent(type='error',message='HTTP 503'),'technical'),
    (GenerationEvent(type='terminal',finish_reason='length'),'output_limit'),
])
def test_failure_stops_series_without_clearing_or_retry(tmp_path,event,category):
    repo,story,first,second,ref,worker,run,calls=runner(tmp_path)
    class Fails:
        def stream(self,ctx,cancel):
            calls.append(ctx);yield event
    worker.gateway_factory=lambda _:Fails()
    worker._execute(run.id)
    assert worker.get_run(run.id).state=='failed' and len(calls)==1
    attempt=repo.list_attempts(story.id,run.id)[0]
    assert attempt.context['impact_failure']['category']==category
    assert repo.get_version(ref.id).stale and not repo.impact('state',story_id=story.id)


def test_changed_sources_during_check_preserve_attempt_but_do_not_apply(tmp_path):
    repo,story,first,second,ref,worker,run,calls=runner(tmp_path)
    original=worker.gateway_factory
    class Race:
        def stream(self,ctx,cancel):
            if ctx.stage=='impact_check':save_manual_prose(repo,first.id,'Змінено під час перевірки.',repo.get_scene(first.id).revision)
            yield from original(None).stream(ctx,cancel)
    worker.gateway_factory=lambda _:Race()
    worker._execute(run.id)
    assert worker.get_run(run.id).state=='alternative' and len(calls)==2
    assert repo.get_version(ref.id).stale and not repo.impact('state',story_id=story.id)


def test_pause_before_provider_call_does_not_dispatch(tmp_path,monkeypatch):
    from storygen.generation import impact_runner
    repo,story,first,second,ref,worker,run,calls=runner(tmp_path)
    original=impact_runner.build_impact_context
    def pause(*args,**kwargs):
        context=original(*args,**kwargs);worker.pause(run.id);return context
    monkeypatch.setattr(impact_runner,'build_impact_context',pause)
    worker._execute(run.id)
    assert worker.get_run(run.id).state=='paused' and not calls

def test_valid_delta_optional_null_omission_preserves_original_proof(tmp_path):
    repo,story,first,second,ref,worker,run,calls=runner(tmp_path)
    original=worker.gateway_factory
    class Omit:
        def stream(self,ctx,cancel):
            for event in original(None).stream(ctx,cancel):
                if ctx.stage=='impact_delta' and event.type=='delta':
                    raw=json.loads(event.text);raw.pop('uncertainty',None);event=event.model_copy(update={'text':json.dumps(raw)})
                yield event
    worker.gateway_factory=lambda _:Omit()
    worker._execute(run.id)
    assert worker.get_run(run.id).state=='completed',worker.get_run(run.id).error


def test_hard_cloud_run_limit_prevents_provider_dispatch(tmp_path,monkeypatch):
    import httpx
    from datetime import datetime,timedelta,timezone
    from storygen.billing.models import Tariff
    from storygen.billing.service import set_limit,save_tariff
    from storygen.providers.streaming import build_generation_gateway
    repo,story,first,second,ref,worker,old,calls=runner(tmp_path)
    worker.cancel(old.id)
    config=ProviderSettings(provider='openrouter',model='synthetic-impact')
    save_role_settings(repo,story.id,'planner',RoleSettings(provider=config,context_tokens=32768),repo.get_story(story.id).revision)
    set_limit(repo,'story:'+story.id,'10',0)
    save_tariff(repo,Tariff(provider='openrouter',model=config.model,base_url=config.base_url,input_per_million='1',output_per_million='2',source='synthetic',kind='manual',expires_at=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()))
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-key')
    plan=plan_impact(repo.context_view(story.id))
    new=worker.enqueue(RunRequest(story_id=story.id,mode='impact',impact_plan_fingerprint=plan.fingerprint,budget_limit_usd='0'),'zero-run')
    requests=[]
    with httpx.Client(transport=httpx.MockTransport(lambda r:requests.append(r) or httpx.Response(500))) as http:
        worker.gateway_factory=lambda settings:build_generation_gateway(settings,http_client=http)
        worker._execute(new.id)
    assert worker.get_run(new.id).state=='failed'
    assert not any(r.method=='POST' for r in requests)
    assert repo.get_version(ref.id).stale

def test_completed_final_check_recovers_locally_after_settings_change(tmp_path,monkeypatch):
    from storygen.generation import impact_runner
    repo,story,first,second,ref,worker,run,calls=runner(tmp_path)
    real=impact_runner.advance
    def crash(worker,current,attempt):
        if attempt.stage=='impact_check':raise RuntimeError('completed check before publication')
        return real(worker,current,attempt)
    monkeypatch.setattr(impact_runner,'advance',crash)
    worker._execute(run.id)
    assert len(calls)==2 and worker.get_run(run.id).state=='failed'
    save_role_settings(repo,story.id,'planner',RoleSettings(provider=ProviderSettings(model='different'),max_input_chars=1),repo.get_story(story.id).revision)
    monkeypatch.setattr(impact_runner,'advance',real)
    assert worker.run_readiness(run.id)['ready'] and worker.run_readiness(run.id)['calls']==0
    worker.resume(run.id);worker._execute(run.id)
    assert worker.get_run(run.id).state=='completed' and len(calls)==2


def test_recovery_after_report_publication_does_not_duplicate_report(tmp_path,monkeypatch):
    from storygen.generation import impact_runner
    repo,story,first,second,ref,worker,run,calls=runner(tmp_path)
    real=worker._save
    def fail_checkpoint(current):
        if current.cursor==2:raise RuntimeError('after report before run checkpoint')
        return real(current)
    monkeypatch.setattr(worker,'_save',fail_checkpoint)
    worker._execute(run.id)
    assert len(repo.impact('state',story_id=story.id))==1
    monkeypatch.setattr(worker,'_save',real)
    worker.resume(run.id);worker._execute(run.id)
    assert worker.get_run(run.id).state=='completed' and len(calls)==2
    assert len(repo.impact('state',story_id=story.id))==1

def test_shared_delta_and_topological_review_basis(tmp_path):
    repo,story,first,second,ref,worker,old,calls=runner(tmp_path)
    worker.cancel(old.id)
    third=repo.list_scenes(story.id)[2]
    # This target's historical input uses the same changed first-scene prose pair.
    from storygen.dependency_models import DependencySelector
    from storygen.storage.snapshots import build_author_baseline
    snapshot=ref.dependency_snapshot.model_copy(deep=True)
    snapshot.selectors=[s.model_copy(update={'owner_id':third.id,'expected':getattr(third,s.field)}) if s.kind=='scene' and s.owner_id==second.id and s.field in {'title','target_words','character_ids'} else s for s in snapshot.selectors]
    old_first=next(id for id in snapshot.refs if repo.get_version(id).scene_id==first.id)
    repo.set_head(first.id,'prose',old_first,repo.get_scene(first.id).revision)
    later=repo.save_version(story.id,third.id,'edited','Марія пригадувала вечір.',list(snapshot.refs),dependency_snapshot=snapshot)
    repo.set_head(third.id,'prose',later.id,repo.get_scene(third.id).revision)
    save_manual_prose(repo,first.id,'Марія знає про лист. Вечір настав.',repo.get_scene(first.id).revision)
    plan=plan_impact(repo.context_view(story.id))
    run=worker.enqueue(RunRequest(story_id=story.id,mode='impact',impact_plan_fingerprint=plan.fingerprint),'shared')
    worker._execute(run.id)
    assert worker.get_run(run.id).state=='completed',worker.get_run(run.id).error
    assert len([c for c in calls if c.stage=='impact_delta'])==1
    assert len([c for c in calls if c.stage=='impact_check'])==2

@pytest.mark.parametrize('text,category',[(json.dumps({'refusal':'I cannot assess sexual content.'}),'refusal_content'),('I cannot assist with this request.','refusal_unknown')])
def test_explicit_refusal_body_is_distinct_from_protocol_error(tmp_path,text,category):
    repo,story,first,second,ref,worker,run,calls=runner(tmp_path)
    class Refuses:
        def stream(self,ctx,cancel):
            calls.append(ctx);yield GenerationEvent(type='delta',text=text);yield GenerationEvent(type='terminal',finish_reason='stop')
    worker.gateway_factory=lambda _:Refuses();worker._execute(run.id)
    attempt=repo.list_attempts(story.id,run.id)[0]
    assert attempt.context['impact_failure']['category']==category
    assert worker.get_run(run.id).state=='failed' and len(calls)==1


def test_impact_character_limit_is_not_reported_as_token_overflow(tmp_path):
    from storygen.generation.impact_context import build_impact_context
    from storygen.generation.context import ContextOverflow
    repo,story,first,second,ref,worker,run,calls=runner(tmp_path)
    role=RoleSettings(provider=ProviderSettings(model='synthetic-impact'),context_tokens=262144,max_output_tokens=16384,max_input_chars=1)
    save_role_settings(repo,story.id,'planner',role,repo.get_story(story.id).revision)
    target=plan_impact(repo.context_view(story.id)).targets[0]
    with pytest.raises(ContextOverflow) as caught:
        build_impact_context(repo,target,'impact_delta')
    assert caught.value.estimated_tokens<caught.value.limit
    assert 'Перевищено операційний ліміт входу' in str(caught.value)
    assert 'дозволено 1' in str(caught.value)
    assert not calls
