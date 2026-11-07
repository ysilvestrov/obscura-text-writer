import json
import pytest
from tests.review.test_store import setup
from tests.memory.wire_helpers import v3_response
from storygen.generation.worker import RunCoordinator
from storygen.run_models import RunRequest
from storygen.providers.streaming import GenerationEvent
from storygen.authoring.blueprints import get_role_settings,save_role_settings


def fixture(root,concern=False,memory_fail=False,third=False):
    repo,story,first,second,ref,old,target=setup(root)
    old.state='cancelled';repo.save_run(old)
    save_role_settings(repo,story.id,'memory',get_role_settings(repo,story.id)['planner'],repo.get_story(story.id).revision)
    if third:
        from storygen.generation.dependencies import save_manual_prose
        s=repo.list_scenes(story.id)[2]
        save_manual_prose(repo,s.id,'Марія прочитала лист.',s.revision)
    calls=[]
    class Gateway:
        def stream(self,ctx,cancel):
            calls.append(ctx)
            if ctx.stage=='memory':
                if memory_fail:
                    yield GenerationEvent(type='error',message='Memory unavailable');return
                raw=json.loads(v3_response())
            else:
                p=json.loads(ctx.user_text)
                raw=dict(complete=True,changes=[],questions=[]) if p['phase']=='delta' else dict(complete=True,concerns=[],carry_refs=[])
                if concern and p['phase']=='check':
                    t=next(k for k,v in p['evidence'].items() if v['kind']=='target');s=next(k for k,v in p['evidence'].items() if v['kind']=='source')
                    raw['concerns']=[dict(kind='issue',message='Перевірте згадку листа.',target_refs=[t],source_refs=[s],change_refs=[p['evidence'][s]['change']])]
            yield GenerationEvent(type='delta',text=json.dumps(raw,ensure_ascii=False))
            yield GenerationEvent(type='terminal',finish_reason='stop')
    worker=RunCoordinator(repo,lambda _:Gateway())
    from storygen.review.readiness import readiness
    request=RunRequest(story_id=story.id,mode='impact',impact_protocol=3)
    ready=readiness(repo,request);assert ready['ready'],ready
    request.impact_plan_fingerprint=ready['fingerprint']
    run=worker.enqueue(request,'review3')
    return repo,story,first,second,ref,worker,run,calls


def test_clean_advances_and_findings_pause(tmp_path):
    repo,story,first,second,ref,worker,run,calls=fixture(tmp_path)
    worker._execute(run.id);run=repo.get_run(run.id)
    assert run.state=='completed',run.error
    assert not repo.get_version(ref.id).stale
    assert repo.get_scene(second.id).heads.get('memory')
    assert [c.stage for c in calls].count('memory')==2
    assert any(e.type=='state' and e.data.get('scene_cursor')==1 for e in worker.list_events(run.id))


def test_findings_wait_for_author_without_memory_of_current_scene(tmp_path):
    repo,story,first,second,ref,worker,run,calls=fixture(tmp_path,concern=True)
    worker._execute(run.id);run=repo.get_run(run.id)
    assert run.state=='needs_review',run.error
    assert run.impact['phase']=='awaiting_author'
    assert repo.get_version(ref.id).stale
    with pytest.raises(ValueError,match='автор'):worker.resume(run.id,True)
    assert not repo.get_scene(second.id).heads.get('memory')


def test_memory_failure_and_explicit_retry(tmp_path):
    repo,story,first,second,ref,worker,run,calls=fixture(tmp_path,memory_fail=True)
    worker._execute(run.id);run=repo.get_run(run.id)
    assert run.state=='failed' and 'Memory unavailable' in run.error
    with pytest.raises(ValueError):worker.resume(run.id)
    assert worker.resume(run.id,True).state=='queued'


def test_order_change_pauses(tmp_path):
    repo,story,first,second,ref,worker,run,calls=fixture(tmp_path)
    run=repo.get_run(run.id);run.impact['scene_order'].reverse();repo.save_run(run)
    worker._execute(run.id)
    assert repo.get_run(run.id).state=='alternative'
    assert not calls


def test_crash_reuses_completed_search_attempt(tmp_path,monkeypatch):
    repo,story,first,second,ref,worker,run,calls=fixture(tmp_path)
    original=worker._save
    def crash(value):
        if value.impact.get('proofs'):raise RuntimeError('after persisted answer')
        return original(value)
    monkeypatch.setattr(worker,'_save',crash)
    with pytest.raises(RuntimeError):worker._execute(run.id)
    search_calls=sum(c.stage=='review_part' for c in calls)
    monkeypatch.setattr(worker,'_save',original)
    current=repo.get_run(run.id);current.state='interrupted';repo.save_run(current)
    worker.resume(run.id);worker._execute(run.id)
    assert repo.get_run(run.id).state=='completed'
    assert sum(c.stage=='review_part' for c in calls)==search_calls+2


def test_settings_change_applies_to_next_part(tmp_path,monkeypatch):
    repo,story,first,second,ref,worker,run,calls=fixture(tmp_path)
    original=worker.gateway_factory;changed=False
    def factory(provider):
        base=original(provider)
        class Gateway:
            def stream(self,ctx,cancel):
                nonlocal changed
                yield from base.stream(ctx,cancel)
                if ctx.stage=='review_part' and not changed:
                    changed=True
                    role=get_role_settings(repo,story.id)['planner'].model_copy(deep=True);role.provider.model='new-planner'
                    save_role_settings(repo,story.id,'planner',role,repo.get_story(story.id).revision)
        return Gateway()
    worker.gateway_factory=factory;worker._execute(run.id)
    assert repo.get_run(run.id).state=='completed',repo.get_run(run.id).error
    models=[c.settings.provider.model for c in calls if c.stage=='review_part']
    assert models[0]=='synthetic-impact' and models[1:]==['new-planner','new-planner']


def test_memory_failure_keeps_author_acceptance(tmp_path):
    from storygen.review.decisions import preview,decide
    repo,story,first,second,ref,worker,run,calls=fixture(tmp_path,concern=True)
    worker._execute(run.id);p=preview(repo,story.id,run.id)
    decide(worker,story.id,run.id,p['fingerprint'],'dismiss',{c['id']:'reject' for c in p['report']['concerns']})
    original=worker.gateway_factory
    class Fails:
        def stream(self,ctx,cancel):
            yield GenerationEvent(type='error',message='Temporary memory failure')
    worker.gateway_factory=lambda _:Fails();worker._execute(run.id)
    assert repo.get_run(run.id).state=='failed'
    assert repo.get_run(run.id).impact['phase']=='memory_refresh'
    assert not repo.get_version(ref.id).stale
    worker.gateway_factory=original;worker.resume(run.id,True);worker._execute(run.id)
    assert repo.get_run(run.id).state=='completed'
    assert sum(c.stage=='review_part' for c in calls)==3


def test_next_scene_uses_author_revised_live_prose(tmp_path):
    from storygen.review.decisions import preview,decide,finish
    from storygen.generation.dependencies import save_manual_prose
    repo,story,first,second,ref,worker,run,calls=fixture(tmp_path,concern=True,third=True)
    worker._execute(run.id);p=preview(repo,story.id,run.id)
    decide(worker,story.id,run.id,p['fingerprint'],'select',{c['id']:'fix' for c in p['report']['concerns']})
    new=save_manual_prose(repo,second.id,'Марія передала лист сестрі.',repo.get_scene(second.id).revision)
    p=preview(repo,story.id,run.id);finish(worker,story.id,run.id,p['fingerprint'],'finish')
    worker._execute(run.id);current=repo.get_run(run.id)
    assert current.state=='needs_review',current.error
    assert current.impact['scene_cursor']==2
    plan=current.impact['scene_plan']
    assert any(c['new_ref']==new.id for target in plan['targets'] for c in target['changes'])
    assert any('передала лист сестрі' in c.user_text for c in calls if c.stage=='review_part' and c.scene_id!=second.id)


def test_external_edit_after_author_acceptance_stops_before_memory(tmp_path):
    from storygen.review.decisions import preview,decide
    from storygen.generation.dependencies import save_manual_prose
    repo,story,first,second,ref,worker,run,calls=fixture(tmp_path,concern=True)
    worker._execute(run.id);p=preview(repo,story.id,run.id)
    decide(worker,story.id,run.id,p['fingerprint'],'dismiss',{c['id']:'reject' for c in p['report']['concerns']})
    before=len(calls)
    save_manual_prose(repo,second.id,'Зовнішня нова версія.',repo.get_scene(second.id).revision)
    worker._execute(run.id)
    assert repo.get_run(run.id).state=='alternative'
    assert len(calls)==before


@pytest.mark.parametrize("persisted_state",["failed","running"])
def test_raised_transport_requires_explicit_repeat(tmp_path,persisted_state):
    repo,story,first,second,ref,worker,run,calls=fixture(tmp_path)
    class Broken:
        def stream(self,ctx,cancel):
            yield GenerationEvent(type='delta',text='{')
            raise RuntimeError('connection broke')
    worker.gateway_factory=lambda _:Broken()
    with pytest.raises(RuntimeError):worker._execute(run.id)
    current=repo.get_run(run.id);current.state='interrupted';repo.save_run(current)
    attempt=repo.list_attempts(story.id,run.id)[-1];attempt.state=persisted_state;repo.save_attempt(attempt)
    repo.recover_running_attempts()
    with pytest.raises(ValueError,match='повтор'):worker.resume(run.id)


def test_saved_answer_settings_change_does_not_repeat(tmp_path,monkeypatch):
    repo,story,first,second,ref,worker,run,calls=fixture(tmp_path)
    original=worker._save
    def crash(value):
        if value.impact.get('proofs'):raise RuntimeError('before checkpoint')
        return original(value)
    monkeypatch.setattr(worker,'_save',crash)
    with pytest.raises(RuntimeError):worker._execute(run.id)
    monkeypatch.setattr(worker,'_save',original)
    role=get_role_settings(repo,story.id)['planner'];role.provider.model='changed-after-crash'
    save_role_settings(repo,story.id,'planner',role,repo.get_story(story.id).revision)
    current=repo.get_run(run.id);current.state='interrupted';repo.save_run(current)
    worker.resume(run.id);worker._execute(run.id)
    assert repo.get_run(run.id).state=='completed'
    assert sum(c.stage=='review_part' for c in calls)==3


@pytest.mark.parametrize('generated,hidden',[(False,False),(False,True),(True,True)])
def test_manual_memory_is_not_discarded_on_automatic_rebuild(tmp_path,generated,hidden):
    from storygen.memory.journal import MemoryJournal,MemoryEvent
    from storygen.generation.dependencies import save_manual_prose
    from storygen.storage.snapshots import build_dependency_snapshot
    from storygen.memory.forwarding import memory_view_from_view,save_forwarding
    repo,story,first,second,ref,worker,run,calls=fixture(tmp_path)
    scene=repo.get_scene(first.id);prose=scene.heads['prose'];quote='Марія знає про лист.'
    journal=MemoryJournal(source_prose_ids=[prose],events=[MemoryEvent(event_id='manual-event',claim_id='manual-claim',operation='add',category='facts',text='Авторський факт про лист.',source_version_id=prose,quote=quote)])
    snapshot=build_dependency_snapshot(repo.context_view(story.id),first.id,'memory',get_role_settings(repo,story.id)['memory'],[prose])
    memory=repo.save_version(story.id,first.id,'memory',journal.model_dump_json(),[prose],dependency_snapshot=snapshot)
    repo.set_head(first.id,'memory',memory.id,scene.revision)
    if generated:
        from storygen.generation.context import build_context
        from storygen.generation.stages import execute_stage
        import threading
        class Adds:
            def stream(self,ctx,cancel):
                yield GenerationEvent(type='delta',text=v3_response(facts_add=[dict(text='Факт про лист.',evidence_ids=['f000001'])]))
                yield GenerationEvent(type='terminal',finish_reason='stop')
        context=build_context(repo,first.id,'memory',get_role_settings(repo,story.id)['memory'])
        a=execute_stage(repo,first.id,'memory',context,Adds(),threading.Event(),lambda _:None,run.id)
        assert a.state=='completed',a.error
        memory=repo.get_version(a.result_version_id)
    p=memory_view_from_view(repo.context_view(story.id),first.id)
    if hidden:save_forwarding(repo,first.id,{p['rows'][0]['claim_id']:False},p['expected_revision'],p['fingerprint'])
    save_manual_prose(repo,first.id,quote+' Вечір настав. Вітер ущух.',repo.get_scene(first.id).revision)
    worker._execute(run.id)
    current=repo.get_run(run.id)
    assert current.state=='failed' and 'пам’ят' in current.error
    assert repo.get_scene(first.id).heads['memory']==memory.id
    assert not calls
