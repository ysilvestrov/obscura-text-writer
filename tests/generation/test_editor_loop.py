import json
import threading

import pytest
from pydantic import ValidationError

from storygen.domain import StoryCreate,SceneCreate
from storygen.storage.repository import Repository
from storygen.providers.models import RoleSettings,ProviderSettings
from storygen.providers.streaming import GenerationEvent
from storygen.authoring.blueprints import save_role_settings
from storygen.generation.worker import RunCoordinator
from storygen.run_models import RunRequest
from storygen.generation.copyedit_review import copyedit_preview,select_copyedits


SOURCE='Вона йшов до дома. На вулиці тихо.'


def patch(original,replacement):
    return json.dumps({'edits':[dict(fragment_id='f000001',original=original,replacement=replacement,category='grammar')]},ensure_ascii=False)


def seeded(tmp_path,responses,mode='patches',limit=5):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Багато проходів'))
    scene=repo.create_scene(story.id,SceneCreate(title='Сцена'))
    draft=repo.save_version(story.id,scene.id,'draft',SOURCE,[])
    repo.set_head(scene.id,'draft',draft.id,scene.revision)
    role=RoleSettings(provider=ProviderSettings(model='synthetic'),edit_mode=mode)
    save_role_settings(repo,story.id,'editor',role,repo.get_story(story.id).revision)
    calls=[]
    class Gateway:
        def stream(self,ctx,cancel):
            calls.append(ctx)
            raw=responses[len(calls)-1]
            if callable(raw):raw=raw(ctx,cancel)
            if isinstance(raw,GenerationEvent):yield raw;return
            yield GenerationEvent(type='delta',text=raw)
            yield GenerationEvent(type='terminal',finish_reason='stop')
    worker=RunCoordinator(repo,lambda _:Gateway())
    request=RunRequest(story_id=story.id,scene_id=scene.id,mode='edit_loop',edit_pass_limit=limit)
    run=worker.enqueue(request,'loop')
    return repo,scene,draft,worker,run,calls


@pytest.mark.parametrize('value',[0,11,True,2.5,'5'])
def test_limit_is_explicit_bounded_integer(value):
    with pytest.raises(ValidationError):RunRequest(story_id='s',scene_id='c',mode='edit_loop',edit_pass_limit=value)


@pytest.mark.parametrize('mode',['patches','diff'])
def test_chain_and_one_final_subset_review(tmp_path,mode):
    texts=['Вона йшла до дома. На вулиці тихо.','Вона йшла додому. На вулиці тихо.','Вона йшла додому. На вулиці тихо.']
    responses=[patch('йшов','йшла'),patch('до дома','додому'),'ДОДАТКОВИЙ ВИКЛИК'] if mode=='patches' else texts
    if mode=='patches':responses[2]='{"edits":[]}'
    repo,scene,draft,worker,run,calls=seeded(tmp_path,responses,mode)
    worker._execute(run.id)
    current=worker.get_run(run.id)
    assert current.state=='needs_review' and len(calls)==3
    assert 'Вона йшла до дома. На вулиці тихо.' in calls[1].user_text
    assert repo.get_scene(scene.id).heads=={'draft':draft.id}
    assert current.editor_loop['stop_reason']=='no_changes'
    a=repo.get_attempt(current.editor_loop['proposal_attempt_id'])
    p=copyedit_preview(repo,scene.id,a.id)
    assert p['protocol_version']==2 and p['original']==SOURCE
    assert p['preview']=='Вона йшла додому. На вулиці тихо.' and p['default_selected_indices']==[]
    result=select_copyedits(repo,scene.id,a.id,list(range(len(p['edits']))),p['expected_revision'],p['proposal_fingerprint'])
    assert repo.read_text(result['version'].id)=='Вона йшла додому. На вулиці тихо.'
    assert repo.get_scene(scene.id).heads['draft']==draft.id
    assert worker.get_run(run.id).state=='completed'
    assert result['run'].state=='completed'
    assert len(calls)==3


def test_first_no_changes_completes_without_acceptance(tmp_path):
    repo,scene,draft,worker,run,calls=seeded(tmp_path,['{"edits":[]}'])
    worker._execute(run.id);current=worker.get_run(run.id)
    assert current.state=='completed' and len(calls)==1
    assert current.editor_loop['stop_reason']=='no_changes'
    assert not current.editor_loop.get('proposal_attempt_id')
    assert repo.get_scene(scene.id).heads=={'draft':draft.id}


@pytest.mark.parametrize('limit',[1,2])
def test_limit_and_candidate_cycle_stop_without_extra_call(tmp_path,limit):
    repo,scene,_,worker,run,calls=seeded(tmp_path,[patch('йшов','йшла'),patch('йшла','йшов')],limit=limit)
    worker._execute(run.id);current=worker.get_run(run.id)
    assert current.state=='needs_review' and len(calls)==limit
    assert current.editor_loop['stop_reason']==('limit' if limit==1 else 'cycle')
    p=copyedit_preview(repo,scene.id,current.editor_loop['proposal_attempt_id'])
    assert p['preview']=='Вона йшла до дома. На вулиці тихо.'


def test_error_keeps_working_candidate_without_publishing_or_retry(tmp_path):
    repo,scene,draft,worker,run,calls=seeded(tmp_path,[patch('йшов','йшла'),GenerationEvent(type='error',message='Тестовий timeout')])
    worker._execute(run.id);current=worker.get_run(run.id)
    assert current.state=='needs_review' and 'timeout' in current.warning and len(calls)==2
    assert repo.read_text(current.editor_loop['current_version_id'])=='Вона йшла до дома. На вулиці тихо.'
    assert repo.get_scene(scene.id).heads=={'draft':draft.id}
    assert current.editor_loop['stop_reason']=='pass_failed'
    proposal=copyedit_preview(repo,scene.id,current.editor_loop['proposal_attempt_id'])
    assert proposal['preview']=='Вона йшла до дома. На вулиці тихо.'
    assert repo.list_attempts(scene.story_id,run.id)[1].state=='failed'


def test_four_successful_diff_passes_survive_reasoning_only_fifth(tmp_path):
    texts=['Вона йшла до дома. На вулиці тихо.','Вона йшла додому. На вулиці тихо.',
        'Вона йшла додому. Надворі тихо.','Вона йшла додому. Надворі було тихо.']
    failure=GenerationEvent(type='error',finish_reason='length',message='8192 токенів на reasoning; тексту немає',usage={'completion_tokens':8192})
    repo,scene,draft,worker,run,calls=seeded(tmp_path,texts+[failure],mode='diff')
    worker._execute(run.id);current=worker.get_run(run.id)
    assert current.state=='needs_review' and len(calls)==5
    assert current.editor_loop['attempt_count']==5 and current.editor_loop['stop_reason']=='pass_failed'
    assert '8192' in current.warning and '4' in current.warning
    summary=repo.get_attempt(current.editor_loop['proposal_attempt_id'])
    failed=repo.get_attempt(summary.context['edit_loop_summary']['failed_attempt_id'])
    assert failed.state=='failed' and failed.finish_reason=='length' and failed.usage['completion_tokens']==8192
    preview=copyedit_preview(repo,scene.id,summary.id)
    assert preview['preview']==texts[-1] and repo.get_scene(scene.id).heads=={'draft':draft.id}
    result=select_copyedits(repo,scene.id,summary.id,list(range(len(preview['edits']))),preview['expected_revision'],preview['proposal_fingerprint'])
    assert repo.read_text(result['version'].id)==texts[-1] and worker.get_run(run.id).state=='completed'
    assert len(calls)==5


def test_partial_failure_checkpoint_recovers_without_another_call(tmp_path,monkeypatch):
    from storygen.generation import editor_loop
    repo,scene,_,worker,run,calls=seeded(tmp_path,[patch('йшов','йшла'),GenerationEvent(type='error',message='timeout')])
    real=editor_loop.finish
    monkeypatch.setattr(editor_loop,'finish',lambda *args: (_ for _ in ()).throw(RuntimeError('checkpoint crash')))
    worker._execute(run.id)
    assert worker.get_run(run.id).editor_loop['stop_reason']=='pass_failed'
    monkeypatch.setattr(editor_loop,'finish',real)
    interrupted=worker.get_run(run.id);interrupted.state='interrupted';repo.save_run(interrupted)
    worker.resume(run.id);worker._execute(run.id)
    assert worker.get_run(run.id).state=='needs_review' and len(calls)==2


def test_bad_anchor_after_success_uses_last_valid_candidate(tmp_path):
    repo,scene,_,worker,run,calls=seeded(tmp_path,[patch('йшов','йшла'),patch('НЕТОЧНИЙ ОРИГІНАЛ','заміна')])
    worker._execute(run.id);current=worker.get_run(run.id)
    assert current.state=='needs_review' and len(calls)==2
    p=copyedit_preview(repo,scene.id,current.editor_loop['proposal_attempt_id'])
    assert p['preview']=='Вона йшла до дома. На вулиці тихо.'
    assert 'якір' in current.warning


def test_cancel_after_success_does_not_create_summary(tmp_path):
    def cancel_pass(ctx,cancel):
        cancel.set();return GenerationEvent(type='cancelled')
    repo,scene,draft,worker,run,calls=seeded(tmp_path,[patch('йшов','йшла'),cancel_pass])
    worker._execute(run.id);current=worker.get_run(run.id)
    assert current.state=='cancelled' and len(calls)==2
    assert not current.editor_loop.get('proposal_attempt_id')
    assert repo.get_scene(scene.id).heads=={'draft':draft.id}


def test_failed_pass_with_changed_source_does_not_offer_partial_acceptance(tmp_path):
    repo,scene,_,worker,run,calls=seeded(tmp_path,[])
    responses=[patch('йшов','йшла')]
    class Gateway:
        def stream(self,ctx,cancel):
            calls.append(ctx)
            if len(calls)==1:
                yield GenerationEvent(type='delta',text=responses[0]);yield GenerationEvent(type='terminal',finish_reason='stop')
            else:
                ref=repo.save_version(scene.story_id,scene.id,'draft','Авторська заміна.',[])
                repo.set_head(scene.id,'draft',ref.id,repo.get_scene(scene.id).revision)
                yield GenerationEvent(type='error',finish_reason='length',message='output limit')
    worker.gateway_factory=lambda _:Gateway()
    worker._execute(run.id);current=worker.get_run(run.id)
    assert current.state=='failed' and len(calls)==2
    assert not current.editor_loop.get('proposal_attempt_id')


def test_storage_or_stream_exception_is_not_reclassified_on_resume(tmp_path):
    def broken(ctx,cancel):raise OSError('checkpoint unavailable')
    repo,_,_,worker,run,calls=seeded(tmp_path,[patch('йшов','йшла'),broken])
    worker._execute(run.id)
    assert worker.get_run(run.id).state=='failed'
    worker.resume(run.id,True);worker._execute(run.id)
    current=worker.get_run(run.id)
    assert current.state=='failed' and current.editor_loop.get('stop_reason')!='pass_failed'
    assert not current.editor_loop.get('proposal_attempt_id')


def test_failure_saved_before_stop_checkpoint_recovers_locally(tmp_path,monkeypatch):
    from storygen.generation import editor_loop
    repo,_,_,worker,run,calls=seeded(tmp_path,[patch('йшов','йшла'),GenerationEvent(type='error',message='timeout')])
    real=editor_loop.stop_after_failure
    monkeypatch.setattr(editor_loop,'stop_after_failure',lambda *args: (_ for _ in ()).throw(RuntimeError('crash before stop save')))
    worker._execute(run.id)
    assert worker.get_run(run.id).editor_loop['stop_reason'] is None
    assert worker.run_readiness(run.id)['calls']==0
    monkeypatch.setattr(editor_loop,'stop_after_failure',real)
    worker.resume(run.id);worker._execute(run.id)
    assert worker.get_run(run.id).state=='needs_review' and len(calls)==2


def test_checkpoint_write_failure_requires_explicit_retry_not_partial_success(tmp_path,monkeypatch):
    repo,_,_,worker,run,calls=seeded(tmp_path,[patch('йшов','йшла'),'{"edits":[]}'])
    original=repo.files.open_partial;opens=[]
    def broken(path):
        opens.append(path)
        if len(opens)==2:raise OSError('storage unavailable')
        return original(path)
    monkeypatch.setattr(repo.files,'open_partial',broken)
    worker._execute(run.id)
    with pytest.raises(ValueError,match='явне'):worker.resume(run.id)
    assert worker.get_run(run.id).editor_loop.get('stop_reason') is None and len(calls)==1
    monkeypatch.setattr(repo.files,'open_partial',original)
    worker.resume(run.id,True);worker._execute(run.id)
    current=worker.get_run(run.id)
    assert current.state=='needs_review' and current.editor_loop['stop_reason']=='no_changes'
    assert len(calls)==2


def test_scene_change_stops_next_call_and_prevents_final_publication(tmp_path):
    repo,scene,_,worker,run,calls=seeded(tmp_path,[])
    def response(ctx,cancel):
        ref=repo.save_version(scene.story_id,scene.id,'draft','Авторська зміна.',[])
        repo.set_head(scene.id,'draft',ref.id,repo.get_scene(scene.id).revision)
        return patch('йшов','йшла')
    # Gateway closes over the mutable list used by seeded.
    calls_ref=calls
    responses=[response]
    class Gateway:
        def stream(self,ctx,cancel):
            calls_ref.append(ctx)
            yield GenerationEvent(type='delta',text=responses[0](ctx,cancel))
            yield GenerationEvent(type='terminal',finish_reason='stop')
    worker.gateway_factory=lambda _:Gateway()
    worker._execute(run.id)
    assert worker.get_run(run.id).state=='failed' and len(calls)==1
    assert not repo.get_scene(scene.id).heads.get('prose')


def test_initial_source_prefers_selected_prose(tmp_path):
    repo,scene,draft,worker,run,calls=seeded(tmp_path,['{"edits":[]}'])
    prose=repo.save_version(scene.story_id,scene.id,'manual','Поточна авторська проза.',[])
    repo.set_head(scene.id,'prose',prose.id,repo.get_scene(scene.id).revision)
    worker._execute(run.id)
    assert 'Поточна авторська проза.' in calls[0].user_text
    assert worker.get_run(run.id).editor_loop['source_version_id']==prose.id
    assert repo.get_scene(scene.id).heads['draft']==draft.id


def test_pause_resume_and_completed_checkpoint_do_not_repeat_model(tmp_path,monkeypatch):
    repo,scene,_,worker,run,calls=seeded(tmp_path,[patch('йшов','йшла'),'{"edits":[]}'])
    run.request.pause_after=['edit'];repo.save_run(run)
    worker._execute(run.id)
    paused=worker.get_run(run.id)
    assert paused.state=='paused' and len(calls)==1
    # Simulate crash before committing progress for an already saved model result.
    paused.cursor=0
    paused.editor_loop['current_version_id']=paused.editor_loop['base_version_id']
    paused.editor_loop['candidate_version_ids']=[]
    paused.editor_loop['seen_hashes']=paused.editor_loop['seen_hashes'][:1]
    paused.state='interrupted';repo.save_run(paused)
    worker.resume(run.id);worker._execute(run.id)
    assert len(calls)==1 and worker.get_run(run.id).cursor==1
    worker.resume(run.id);worker._execute(run.id)
    assert worker.get_run(run.id).state=='needs_review' and len(calls)==2


def test_checkpoint_after_no_changes_never_calls_model_again(tmp_path,monkeypatch):
    from storygen.generation import editor_loop
    repo,_,_,worker,run,calls=seeded(tmp_path,['{"edits":[]}'])
    real_finish=editor_loop.finish
    monkeypatch.setattr(editor_loop,'finish',lambda *args: (_ for _ in ()).throw(RuntimeError('simulated crash')))
    worker._execute(run.id)
    assert len(calls)==1
    interrupted=worker.get_run(run.id);interrupted.state='interrupted';repo.save_run(interrupted)
    monkeypatch.setattr(editor_loop,'finish',real_finish)
    worker.resume(run.id);worker._execute(run.id)
    assert len(calls)==1 and worker.get_run(run.id).state=='completed'


def test_cancel_between_passes_preserves_heads_and_requires_explicit_repeat(tmp_path):
    repo,scene,draft,worker,run,calls=seeded(tmp_path,[])
    class Gateway:
        def stream(self,ctx,cancel):
            calls.append(ctx)
            worker.cancel(run.id)
            yield GenerationEvent(type='cancelled')
    worker.gateway_factory=lambda _:Gateway()
    worker._execute(run.id)
    assert worker.get_run(run.id).state=='cancelled' and len(calls)==1
    assert repo.get_scene(scene.id).heads=={'draft':draft.id}
    with pytest.raises(ValueError,match='явне'):worker.resume(run.id)


def test_failed_attempt_consumes_pass_limit_and_does_not_sneak_retry(tmp_path):
    repo,_,_,worker,run,calls=seeded(tmp_path,[GenerationEvent(type='error',message='Тест')],limit=1)
    worker._execute(run.id)
    worker.resume(run.id,True);worker._execute(run.id)
    assert len(calls)==1 and worker.get_run(run.id).state=='completed'
    assert worker.get_run(run.id).editor_loop['stop_reason']=='limit'


def test_prose_based_result_stays_fresh_after_replacing_its_source(tmp_path):
    repo,scene,draft,worker,run,calls=seeded(tmp_path,[patch('йшов','йшла'),'{"edits":[]}'])
    prose=repo.save_version(scene.story_id,scene.id,'manual',SOURCE,[])
    repo.set_head(scene.id,'prose',prose.id,repo.get_scene(scene.id).revision)
    worker._execute(run.id)
    a=worker.get_run(run.id).editor_loop['proposal_attempt_id']
    p=copyedit_preview(repo,scene.id,a)
    result=select_copyedits(repo,scene.id,a,[0],p['expected_revision'],p['proposal_fingerprint'])
    assert not repo.get_version(result['version'].id).stale
    assert repo.get_scene(scene.id).heads['draft']==draft.id


def test_guards_stop_without_advancing(tmp_path):
    repo,scene,draft,worker,run,calls=seeded(tmp_path,[patch('відсутній','замінити')])
    worker._execute(run.id)
    assert worker.get_run(run.id).state=='failed' and len(calls)==1
    assert 'якір' in worker.get_run(run.id).error
    assert worker.get_run(run.id).editor_loop['current_version_id']==worker.get_run(run.id).editor_loop['base_version_id']
    assert repo.get_scene(scene.id).heads=={'draft':draft.id}


def test_zero_cloud_budget_blocks_loop_model_call(tmp_path,monkeypatch):
    import httpx
    from datetime import datetime,timedelta,timezone
    from storygen.billing.models import Tariff
    from storygen.billing.service import set_limit,save_tariff
    from storygen.providers.streaming import build_generation_gateway
    repo,scene,draft,worker,run,_=seeded(tmp_path,[])
    config=ProviderSettings(provider='openrouter',model='synthetic')
    save_role_settings(repo,scene.story_id,'editor',RoleSettings(provider=config,edit_mode='patches'),repo.get_story(scene.story_id).revision)
    set_limit(repo,'story:'+scene.story_id,'0',0)
    save_tariff(repo,Tariff(provider='openrouter',model='synthetic',base_url=config.base_url,input_per_million='1',output_per_million='2',
        source='synthetic',kind='manual',expires_at=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()))
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-key')
    requests=[]
    with httpx.Client(transport=httpx.MockTransport(lambda r:requests.append(r) or httpx.Response(500))) as http:
        worker.gateway_factory=lambda settings:build_generation_gateway(settings,http_client=http)
        worker._execute(run.id)
    assert worker.get_run(run.id).state=='failed'
    assert 'бюджет' in worker.get_run(run.id).error.lower()
    assert not any(r.method=='POST' for r in requests)
    assert repo.get_scene(scene.id).heads=={'draft':draft.id}


def test_completed_stop_recovers_without_requiring_editor_settings(tmp_path,monkeypatch):
    from storygen.generation import stages
    repo,scene,_,worker,run,calls=seeded(tmp_path,['{"edits":[]}'])
    real=stages.execute_stage
    def crash_after_save(*args,**kwargs):
        real(*args,**kwargs)
        raise RuntimeError('crash before run checkpoint')
    monkeypatch.setattr(stages,'execute_stage',crash_after_save)
    worker._execute(run.id)
    save_role_settings(repo,scene.story_id,'editor',RoleSettings(provider=ProviderSettings(model='changed'),edit_mode='prose'),repo.get_story(scene.story_id).revision)
    monkeypatch.setattr(stages,'execute_stage',real)
    worker.resume(run.id);worker._execute(run.id)
    assert len(calls)==1 and worker.get_run(run.id).state=='completed'
    assert worker.get_run(run.id).editor_loop['attempt_count']==1


def test_stream_exception_counts_attempt_and_limit_recovery_is_local(tmp_path):
    repo,_,_,worker,run,calls=seeded(tmp_path,[],limit=1)
    class Gateway:
        def stream(self,ctx,cancel):
            calls.append(ctx)
            yield GenerationEvent(type='delta',text='partial')
            raise RuntimeError('stream lost')
    worker.gateway_factory=lambda _:Gateway()
    worker._execute(run.id)
    assert worker.get_run(run.id).state=='failed'
    assert worker.get_run(run.id).editor_loop['attempt_count']==1
    worker.resume(run.id,True);worker._execute(run.id)
    assert len(calls)==1 and 'Спроб: 1 із 1' in worker.get_run(run.id).warning
