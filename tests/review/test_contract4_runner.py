import json
import pytest
from storygen.run_models import RunRequest
from storygen.providers.streaming import GenerationEvent
from tests.review.test_runner import fixture


def run4(root,mode='clean',wrapper=None,raw_outputs=None):
    assert 'review_contract_version' in RunRequest.model_fields, 'Контракт4 ще не підключено до runtime'
    repo,story,first,second,ref,worker,run,calls=fixture(root)
    worker.cancel(run.id)
    from tests.review.counter4 import activate_counter4
    activate_counter4(repo,second.id)
    request=RunRequest(story_id=story.id,mode='impact',impact_protocol=3,review_contract_version=4)
    from storygen.review.readiness import readiness
    p=readiness(repo,request);assert p['ready'],p
    request.impact_plan_fingerprint=p['fingerprint']
    worker.cancel_event.clear()
    class Gateway:
        def stream(self,ctx,cancel):
            calls.append(ctx)
            if ctx.stage=='memory':raw=dict(schema_version=2,operations=[])
            else:
                p=json.loads(ctx.user_text)
                raw=dict(analysis_status='done',reason=None,candidates=[])
                if p['phase']=='delta':raw['changes']=[]
                if p['phase']=='check' and mode!='clean':
                    s=next(k for k,v in p['evidence'].items() if v['kind']=='source')
                    t=next(k for k,v in p['evidence'].items() if v['kind']=='target')
                    def ep(ref):return dict(ref=ref,start=0,end=len(p['evidence'][ref]['text']),quote=p['evidence'][ref]['text'])
                    good=dict(type='contradiction',left=ep(s),right=ep(t),explanation='Несумісність із чинною передумовою.')
                    raw['candidates']=[good]
                    if mode=='partial':
                        bad=json.loads(json.dumps(good));bad['right']['quote']='Підробка';raw['candidates'].append(bad)
                    if mode=='unable':raw.update(analysis_status='unable',reason='Не можу завершити аналіз.')
            text=json.dumps(raw,ensure_ascii=False)
            if wrapper:text=wrapper[0]+text+wrapper[1]
            if raw_outputs is not None:raw_outputs.append((ctx.stage,text))
            yield GenerationEvent(type='delta',text=text)
            yield GenerationEvent(type='terminal',finish_reason='stop')
    worker.gateway_factory=lambda _:Gateway()
    run=worker.enqueue(request,'review4-'+mode)
    return repo,story,first,second,ref,worker,run,calls


@pytest.mark.parametrize('mode',['clean','concern','partial','unable'])
def test_contract4_preserves_findings_and_never_accepts_partial(tmp_path,mode):
    from storygen.review.decisions import preview,decide
    repo,story,first,second,ref,worker,run,calls=run4(tmp_path,mode)
    worker._execute(run.id);run=repo.get_run(run.id)
    assert run.state==('failed' if mode in {'partial','unable'} else 'needs_review'),run.error
    p=preview(repo,story.id,run.id);report=p['report']
    assert report and report['schema_version']==4
    assert report['execution_state']==('partial' if mode in {'partial','unable'} else 'complete')
    assert repo.get_version(ref.id).stale
    assert any(json.loads(c.user_text).get('phase')=='premise_check' for c in calls if c.stage=='review_part')
    if mode=='clean':
        # No profile has been qualified for automatic model authority by this test.
        assert not report['concerns'] and not p['automatic_acceptance_allowed']
        decide(worker,story.id,run.id,p['fingerprint'],'author-clean',{})
        assert not repo.get_version(ref.id).stale
    elif mode=='concern':assert report['concerns'][0]['kind']=='issue'
    else:
        assert report['concerns'] and report['diagnostics']
        assert report['unresolved_task_ids']
        assert all('task_id' in d for d in report['diagnostics'])
        with pytest.raises(ValueError):decide(worker,story.id,run.id,p['fingerprint'],'bypass',{})


@pytest.mark.parametrize('wrapper',[None,("'","'"),('```json\n','\n```')])
def test_report4_replay_and_backup_are_exact(tmp_path,wrapper):
    from storygen.review.proofs import verify_report
    from storygen.storage.backup import create_backup,restore_backup
    from storygen.storage.repository import Repository
    from storygen.storage.integrity import check_integrity
    expected_raw=[]
    repo,story,first,second,ref,worker,run,calls=run4(tmp_path/'data','concern',wrapper,expected_raw)
    worker._execute(run.id)
    view=repo.context_view(story.id);report=next(iter(view.review_reports.values()))
    assert verify_report(report,view.review_proofs,repo.files.read_partial)
    attempts=[a for a in repo.list_attempts(story.id) if a.stage=='review_part' and a.state=='completed']
    assert [repo.files.read_partial(a.partial_path) for a in attempts]==[text for stage,text in expected_raw if stage=='review_part']
    assert len(attempts)==sum(c.stage=='review_part' for c in calls)
    changed=report.model_copy(deep=True);changed.concerns[0].kind='question'
    with pytest.raises(ValueError):verify_report(changed,view.review_proofs,repo.files.read_partial)
    backup=create_backup(repo.root,tmp_path/'backup.zip')
    restore_backup(backup,tmp_path/'restored')
    restored=Repository(tmp_path/'restored');assert check_integrity(restored.root).ok
    with restored.db.connection() as db:
        row=db.execute("SELECT key,payload FROM app_settings WHERE key LIKE 'review4:%:report:%'").fetchone()
        data=json.loads(row[1]);data['concerns'][0]['kind']='question'
        db.execute('UPDATE app_settings SET payload=? WHERE key=?',(json.dumps(data),row[0]))
    assert not check_integrity(restored.root).ok


def test_partial_retry_requires_consent_and_reuses_only_complete_tasks(tmp_path):
    repo,story,first,second,ref,worker,run,calls=run4(tmp_path,'partial')
    worker._execute(run.id);failed=repo.get_run(run.id)
    assert failed.state=='failed'
    with pytest.raises(ValueError,match='повтор'):worker.resume(run.id)
    before=len([c for c in calls if c.stage=='review_part'])
    base=worker.gateway_factory
    class Repaired:
        def stream(self,ctx,cancel):
            for event in base(ctx.settings.provider).stream(ctx,cancel):
                if event.type=='delta' and ctx.stage=='review_part':
                    raw=json.loads(event.text)
                    if 'candidates' in raw:raw['candidates']=raw['candidates'][:1]
                    event=GenerationEvent(type='delta',text=json.dumps(raw,ensure_ascii=False))
                yield event
    worker.gateway_factory=lambda _:Repaired()
    worker.resume(run.id,True);worker._execute(run.id)
    current=repo.get_run(run.id)
    assert current.state=='needs_review',current.error
    assert len([c for c in calls if c.stage=='review_part'])==before+2  # check and its final synthesis
    reports=list(repo.context_view(story.id).review_reports.values())
    assert len(reports)==2 and not reports[0].complete and reports[1].complete


def test_author_acceptance4_rechecks_original_raw(tmp_path):
    from storygen.review.decisions import preview,decide
    repo,story,first,second,ref,worker,run,calls=run4(tmp_path,'concern')
    worker._execute(run.id);p=preview(repo,story.id,run.id)
    decide(worker,story.id,run.id,p['fingerprint'],'accept',{c['id']:'reject' for c in p['report']['concerns']})
    assert not repo.get_version(ref.id).stale
    view=repo.context_view(story.id);report=next(iter(view.review_reports.values()))
    attempt=repo.get_attempt(next(iter(report.proofs.values())))
    (repo.root/attempt.partial_path).write_text('{}',encoding='utf-8')
    assert repo.get_version(ref.id).stale


def test_preview_counts_include_forced_premise_synthesis(tmp_path):
    from storygen.review.readiness import readiness
    repo,story,first,second,ref,worker,run,calls=run4(tmp_path,'clean')
    preview=readiness(repo,run.request)
    worker._execute(run.id)
    actual=sum(c.stage=='review_part' for c in calls)
    assert preview['calls']>=actual
    assert preview['part_counts']['premise_synthesis']>=1


def test_review4_acceptance_makes_legacy_version_current(tmp_path):
    from storygen.domain import VersionRef
    from storygen.review.decisions import preview,decide
    repo,story,first,second,ref,worker,run,calls=run4(tmp_path,'clean')
    with repo.db.connection() as db:
        raw=repo._get(db,'versions',ref.id,VersionRef)
        raw.dependency_snapshot=None;raw.input_refs=[];raw.stale=True
        db.execute('UPDATE versions SET payload=? WHERE id=?',(raw.model_dump_json(),ref.id))
        db.execute('DELETE FROM dependency_edges WHERE target_id=?',(ref.id,))
    worker._execute(run.id);p=preview(repo,story.id,run.id)
    assert p['report']['coverage']['plan']['basis_modes'][ref.id]=='current_consistency'
    decide(worker,story.id,run.id,p['fingerprint'],'accept-legacy',{})
    assert not repo.get_version(ref.id).stale
