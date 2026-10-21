import json
import threading
import pytest
from storygen.domain import StoryCreate, SceneCreate
from storygen.storage.repository import Repository
from storygen.providers.models import RoleSettings, ProviderSettings
from storygen.providers.streaming import GenerationEvent
from storygen.generation.pipeline import generate_scene


class FakeGateway:
    def __init__(self,repo=None,scene_id=None): self.contexts=[];self.repo=repo;self.scene_id=scene_id;self.invalid=None
    def stream(self,context,cancel):
        self.contexts.append(context)
        texts={'brief':json.dumps({'objective':'Ранок','beats':['Студія'],'constraints':[],'proposed_changes':[]},ensure_ascii=False),'draft':'Олена прийшла у нову бібліотеку.','edit':'Олена увійшла до нової бібліотеки.'}
        if context.stage=='memory':
            scene=self.repo.get_scene(context.scene_id)
            texts['memory']=json.dumps({'facts':[{'text':'Олена у бібліотеки','source_version_id':scene.heads['prose'],'quote':'Олена увійшла'}],'source_prose_ids':[scene.heads['prose']]},ensure_ascii=False)
        if context.stage==self.invalid: text='not JSON'
        else: text=texts[context.stage]
        yield GenerationEvent(type='delta',text=text)
        yield GenerationEvent(type='terminal',finish_reason='stop')


def prepare(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Твір'))
    scene=repo.create_scene(story.id,SceneCreate(title='Ранок',beats='Студія'))
    gateway=FakeGateway(repo,scene.id)
    roles={role:RoleSettings(provider=ProviderSettings(model=role),memory_mode='snapshot') for role in ['planner','writer','editor','memory']}
    return repo,scene,gateway,roles


def test_scene_pipeline_uses_edited_text_for_memory(tmp_path):
    repo,scene,gateway,roles=prepare(tmp_path)
    attempts=generate_scene(repo,scene.id,roles,lambda _:gateway,threading.Event(),lambda *_:None)
    assert [c.stage for c in gateway.contexts]==['brief','draft','edit','memory']
    assert all(a.state=='completed' for a in attempts)
    assert 'Олена увійшла' in gateway.contexts[-1].user_text
    assert 'Олена прийшла' not in gateway.contexts[-1].user_text
    current=repo.get_scene(scene.id)
    assert repo.get_version(current.heads['memory']).input_refs


@pytest.mark.parametrize('invalid,expected', [('brief',1),('memory',4)])
def test_invalid_brief_or_memory_stops_pipeline(tmp_path,invalid,expected):
    repo,scene,gateway,roles=prepare(tmp_path);gateway.invalid=invalid
    attempts=generate_scene(repo,scene.id,roles,lambda _:gateway,threading.Event(),lambda *_:None)
    assert len(gateway.contexts)==expected and attempts[-1].state=='failed'
    assert repo.files.resolve(attempts[-1].partial_path).read_text(encoding="utf-8")=='not JSON'
    assert invalid not in repo.get_scene(scene.id).heads


def test_manual_edit_during_generation_keeps_alternative_result(tmp_path):
    repo,scene,gateway,roles=prepare(tmp_path)
    original=gateway.stream
    def changing(context,cancel):
        yield from original(context,cancel)
        if context.stage=='edit':
            current=repo.get_scene(scene.id)
            manual=repo.save_version(scene.story_id,scene.id,'manual','Авторська правка',[])
            repo.set_head(scene.id,'prose',manual.id,current.revision)
    gateway.stream=changing
    attempts=generate_scene(repo,scene.id,roles,lambda _:gateway,threading.Event(),lambda *_:None)
    assert attempts[-1].state=='alternative'
    assert repo.read_text(repo.get_scene(scene.id).heads['prose'])=='Авторська правка'
    assert repo.read_text(attempts[-1].result_version_id)=='Олена увійшла до нової бібліотеки.'



def test_crash_after_completed_blob_does_not_advance_head_without_commit(tmp_path,monkeypatch):
    repo,scene,gateway,roles=prepare(tmp_path)
    def crash(*args): raise RuntimeError('simulated crash before transaction')
    monkeypatch.setattr(repo,'commit_stage_result',crash)
    with pytest.raises(RuntimeError): generate_scene(repo,scene.id,roles,lambda _:gateway,threading.Event(),lambda *_:None)
    reopened=Repository(tmp_path)
    assert 'brief' not in reopened.get_scene(scene.id).heads
    assert reopened.list_versions(scene.story_id,scene.id,'brief')
    assert reopened.list_attempts(scene.story_id)[-1].state=='running'
