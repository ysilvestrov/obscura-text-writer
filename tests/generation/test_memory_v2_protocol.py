import json
import threading
from storygen.domain import StoryCreate,SceneCreate
from storygen.storage.repository import Repository
from storygen.providers.models import RoleSettings,ProviderSettings
from storygen.providers.streaming import GenerationEvent
from storygen.generation.context import build_context
from storygen.generation.stages import execute_stage
from storygen.memory.journal import load_memory,replay_memory


def test_new_default_preserves_old_stored_missing_mode(tmp_path):
    from storygen.authoring.blueprints import get_role_settings
    assert RoleSettings(provider=ProviderSettings(model='new')).memory_mode=='evidence_delta'
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Defaults'))
    raw=RoleSettings(provider=ProviderSettings(model='old')).model_dump();raw.pop('memory_mode')
    repo.write_role_settings(story.id,{'memory':raw},story.revision)
    with repo.db.connection() as db:
        db.execute('UPDATE role_settings SET payload=? WHERE story_id=? AND role=?',(json.dumps(raw),story.id,'memory'))
    assert get_role_settings(repo,story.id)['memory'].memory_mode=='snapshot'


def test_v2_stage_sends_catalog_and_publishes_history(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Журнал'))
    scenes=[repo.create_scene(story.id,SceneCreate(title=str(i),character_ids=['A'])) for i in range(2)]
    texts=['A сидів у бібліотеки, готуючи знімки.','A вийшов зі бібліотеки, закривши двері.']
    ids=[]
    for scene,text in zip(scenes,texts):
        prose=repo.save_version(story.id,scene.id,'manual',text,[]);ids.append(prose.id)
        repo.set_head(scene.id,'prose',prose.id,scene.revision)
    role=RoleSettings(provider=ProviderSettings(model='fake'),memory_mode='evidence_delta',context_tokens=32768)
    class Gateway:
        def __init__(self,raw):self.raw=raw
        def stream(self,*_):
            yield GenerationEvent(type='delta',text=self.raw)
            yield GenerationEvent(type='terminal',finish_reason='stop')
    def run(index,action,text,claim=None):
        context=build_context(repo,scenes[index].id,'memory',role)
        raw=json.dumps({'schema_version':2,'operations':[{'action':action,'category':'character_states',
            'text':text,'claim_id':claim,'character_ids':['A'],'evidence_id':'f000001'}]})
        attempt=execute_stage(repo,scenes[index].id,'memory',context,Gateway(raw),threading.Event(),lambda _:None)
        assert attempt.state=='completed',attempt.error
        return context,load_memory(repo.read_text(attempt.result_version_id))
    _,first=run(0,'add','A у бібліотеки')
    context,second=run(1,'update','A за межами бібліотеки',first.events[0].claim_id)
    assert texts[0] not in context.user_text and ids[0] not in context.user_text
    assert first.events[0].claim_id in context.user_text
    assert len(second.events)==2 and list(replay_memory(second).values())[0].text=='A за межами бібліотеки'
    assert context.memory_metrics['catalog_chars']>0
