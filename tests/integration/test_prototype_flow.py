import json
import threading
import time
from pathlib import Path

from storygen.authoring.imports import SourceFile, import_sources
from storygen.authoring.blueprints import save_role_settings
from storygen.application.exports import export_story
from storygen.domain import StoryCreate
from storygen.storage.repository import Repository
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.providers.streaming import GenerationEvent
from storygen.memory.models import MemorySnapshot, MemoryEntry
from storygen.memory.service import memory_before
from storygen.memory.journal import load_memory
from storygen.generation.worker import RunCoordinator, RunRequest


class StoryGateway:
    def __init__(self,repo,refuse=False):self.repo=repo;self.calls=[];self.refuse=refuse
    def stream(self,context,cancel):
        self.calls.append((context.scene_id,context.stage))
        if self.refuse:
            yield GenerationEvent(type='delta',text='Відмова моделі',refusal=True)
            yield GenerationEvent(type='error',message='Відмова провайдера',refusal=True)
            return
        scene=self.repo.get_scene(context.scene_id)
        if context.stage=='brief':text=json.dumps({'objective':scene.title,'beats':[scene.beats]})
        elif context.stage in {'draft','edit'}:text=f'Олена уважно оглянула кімнату. Це сцена номер {scene.position+1}.'
        else:
            prior=memory_before(self.repo,scene.id)
            prose=scene.heads['prose']
            snapshot=prior.model_copy(deep=True)
            snapshot.source_prose_ids.append(prose)
            snapshot.facts.append(MemoryEntry(text=f'Подія {scene.position+1}',source_version_id=prose,quote='Олена уважно оглянула кімнату.'))
            text=snapshot.model_dump_json()
        yield GenerationEvent(type='delta',text=text)
        yield GenerationEvent(type='terminal',finish_reason='stop')


def fixture(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Двері — технічний прогін'))
    import_sources(repo,story.id,[SourceFile(name='plan.md',raw=Path('tests/fixtures/prototype/plan.md').read_bytes())])
    for role in ['planner','writer','editor','memory']:
        save_role_settings(repo,story.id,role,RoleSettings(provider=ProviderSettings(model='fake-'+role),context_tokens=32768,max_output_tokens=3000,memory_mode='snapshot'),repo.get_story(story.id).revision)
    return repo,story,repo.list_scenes(story.id)


def wait(worker,id,states):
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        run=worker.get_run(id)
        if run.state in states:return run
        time.sleep(.01)
    raise AssertionError(worker.get_run(id))


def test_seven_scene_flow_to_export(tmp_path):
    repo,story,scenes=fixture(tmp_path);gateway=StoryGateway(repo);worker=RunCoordinator(repo,lambda _:gateway);worker.start()
    try:
        run=worker.enqueue(RunRequest(story_id=story.id,scene_id=scenes[0].id,mode='remaining'),'seven')
        assert wait(worker,run.id,{'completed','failed'}).state=='completed'
        assert len(gateway.calls)==28
        current=repo.list_scenes(story.id)
        assert all(set(s.heads)>={'brief','draft','prose','memory'} for s in current)
        snapshot=load_memory(repo.read_text(current[-1].heads['memory']))
        assert snapshot.source_prose_ids==[s.heads['prose'] for s in current]
        assert export_story(repo,story.id,'md').exists()
    finally:worker.stop()


def test_restart_after_scene_three_resumes_without_duplicate_calls(tmp_path):
    repo,story,scenes=fixture(tmp_path);gateway=StoryGateway(repo);worker=RunCoordinator(repo,lambda _:gateway);worker.start()
    for index in range(3):
        run=worker.enqueue(RunRequest(story_id=story.id,scene_id=scenes[index].id,mode='scene'),'scene'+str(index))
        assert wait(worker,run.id,{'completed','failed'}).state=='completed'
    worker.stop();reopened=Repository(tmp_path)
    restarted=RunCoordinator(reopened,lambda _:gateway);restarted.start()
    try:
        run=restarted.enqueue(RunRequest(story_id=story.id,scene_id=scenes[0].id,mode='remaining'),'resume-all')
        assert wait(restarted,run.id,{'completed','failed'}).state=='completed'
        assert len(gateway.calls)==28
        assert len([e for e in restarted.list_events(run.id) if e.type=='reused'])==12
    finally:restarted.stop()


def test_model_refusal_does_not_trigger_provider_fallback(tmp_path):
    repo,story,scenes=fixture(tmp_path);gateway=StoryGateway(repo,refuse=True);worker=RunCoordinator(repo,lambda _:gateway);worker.start()
    try:
        run=worker.enqueue(RunRequest(story_id=story.id,scene_id=scenes[0].id,mode='scene'),'refusal')
        assert wait(worker,run.id,{'completed','failed'}).state=='failed'
        assert len(gateway.calls)==1
        assert not repo.get_scene(scenes[0].id).heads.get('brief')
        assert 'Відмова' in repo.files.resolve(repo.list_attempts(story.id)[-1].partial_path).read_text(encoding='utf-8')
    finally:worker.stop()


def test_seven_scenes_accept_alternative_restart_and_export(tmp_path):
    from storygen.generation.dependencies import save_manual_draft
    from storygen.evaluation.story_adapter import EvaluationSettings,save_evaluation_settings
    from storygen.evaluation.models import EvaluatorConfig,GatewayResult
    repo,story,scenes=fixture(tmp_path)
    settings=EvaluationSettings(config=EvaluatorConfig(provider='local',model='offline-judge',max_input_chars=100000),context_tokens=128000)
    save_evaluation_settings(repo,story.id,settings)
    plan_a=repo.get_scene(scenes[5].id).heads['plan']
    class Gateway(StoryGateway):
        changed_draft=False
        changed_future=False
        def stream(self,context,cancel):
            if context.stage=='edit' and context.scene_id==scenes[0].id and not self.changed_draft:
                self.changed_draft=True
                current=repo.get_scene(context.scene_id)
                save_manual_draft(repo,current.id,'Авторська альтернатива чернетки',current.revision)
            if context.stage=='memory' and context.scene_id==scenes[1].id and not self.changed_future:
                self.changed_future=True
                future=repo.get_scene(scenes[5].id)
                repo.update_scene_plan(future.id,'Нерелевантна майбутня зміна',future.revision)
            yield from super().stream(context,cancel)
    judge_calls=[]
    class Judge:
        def complete(self,request):
            judge_calls.append(request)
            # A technical invalid response is an unconfirmed report, never a literary penalty.
            return GatewayResult(text='{}',finish_reason='stop')
    gateway=Gateway(repo)
    worker=RunCoordinator(repo,lambda _:gateway,lambda _:Judge())
    def execute(worker,id):
        current=worker.get_run(id);current.state='running';worker._save(current)
        worker._execute(id)
        return worker.get_run(id)
    run=worker.enqueue(RunRequest(story_id=story.id,scene_id=scenes[0].id,mode='remaining',pause_after=['memory']),'seven-reviewed')
    stopped=execute(worker,run.id)
    assert stopped.state=='alternative' and stopped.cursor==2
    alternative=repo.list_attempts(story.id,run.id)[-1]
    ref=repo.get_version(alternative.result_version_id)
    preview=repo.preview_acceptance(scenes[0].id,ref.id)
    accepted=repo.accept_version(scenes[0].id,ref.id,preview.expected_revision,preview.preview_fingerprint)
    worker.continue_after_acceptance(run.id,ref.id,stopped.cursor,accepted.scene.revision,accepted.acceptance.id)
    assert execute(worker,run.id).state=='paused'
    # Reopen the catalog and coordinator; paused work must not restart itself.
    reopened=Repository(tmp_path)
    worker=RunCoordinator(reopened,lambda _:gateway,lambda _:Judge())
    worker.recover_interrupted()
    assert worker.get_run(run.id).state=='paused'
    worker.resume(run.id)
    assert execute(worker,run.id).state=='paused'
    second=reopened.get_scene(scenes[1].id)
    assert not reopened.get_version(second.heads['memory']).stale
    # Return exactly to A: existing model text regains freshness without another call.
    future=reopened.get_scene(scenes[5].id)
    reopened.set_head(future.id,'plan',plan_a,future.revision)
    current=worker.get_run(run.id);current.request.pause_after=[];worker._save(current)
    worker.resume(run.id)
    assert execute(worker,run.id).state=='completed'
    assert len(gateway.calls)==28 and len(judge_calls)==7
    assert reopened.get_attempt(alternative.id).state=='alternative'
    assert reopened.get_scene(scenes[0].id).heads['prose']==ref.id
    current=reopened.list_scenes(story.id)
    memory=load_memory(reopened.read_text(current[-1].heads['memory']))
    assert memory.source_prose_ids==[s.heads['prose'] for s in current]
    reports=reopened.list_versions(story.id,kind='evaluation')
    assert len(reports)==7 and all(not r.stale for r in reports)
    assert all(r.dependency_snapshot and reopened.get_scene(r.scene_id).heads['prose'] in r.input_refs for r in reports)
    assert export_story(reopened,story.id,'md').exists()
