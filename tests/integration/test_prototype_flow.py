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
        elif context.stage in {'draft','edit'}:text=f'Лєра уважно оглянула кімнату. Це сцена номер {scene.position+1}.'
        else:
            prior=memory_before(self.repo,scene.id)
            prose=scene.heads['prose']
            snapshot=prior.model_copy(deep=True)
            snapshot.source_prose_ids.append(prose)
            snapshot.facts.append(MemoryEntry(text=f'Подія {scene.position+1}',source_version_id=prose,quote='Лєра уважно оглянула кімнату.'))
            text=snapshot.model_dump_json()
        yield GenerationEvent(type='delta',text=text)
        yield GenerationEvent(type='terminal',finish_reason='stop')


def fixture(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Двері — технічний прогін'))
    import_sources(repo,story.id,[SourceFile(name='plan.md',raw=Path('tests/fixtures/prototype/plan.md').read_bytes())])
    for role in ['planner','writer','editor','memory']:
        save_role_settings(repo,story.id,role,RoleSettings(provider=ProviderSettings(model='fake-'+role),context_tokens=32768,max_output_tokens=3000),repo.get_story(story.id).revision)
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
        snapshot=MemorySnapshot.model_validate_json(repo.read_text(current[-1].heads['memory']))
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
