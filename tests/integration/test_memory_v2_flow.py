import json
import threading
import pytest
from storygen.domain import StoryCreate,SceneCreate
from storygen.storage.repository import Repository
from storygen.authoring.blueprints import save_role_settings
from storygen.providers.models import RoleSettings,ProviderSettings
from storygen.providers.streaming import GenerationEvent
from storygen.generation.worker import RunCoordinator,RunRequest
from storygen.generation.context import build_context
from storygen.generation.stages import execute_stage
from storygen.memory.journal import load_memory,legacy_view,replay_memory


@pytest.mark.parametrize('count',[7,15])
def test_forward_memory_scale_and_cold_restore(tmp_path,count):
    from storygen.storage.integrity import check_integrity
    from storygen.storage.backup import create_backup,restore_backup
    root=tmp_path/'data';repo=Repository(root)
    story=repo.create_story(StoryCreate(title='Масштаб пам’яті'))
    scenes=[repo.create_scene(story.id,SceneCreate(title=str(i),beats='Наступний епізод',character_ids=['A'])) for i in range(count)]
    roles={name:RoleSettings(provider=ProviderSettings(model='fake-'+name),context_tokens=32768,max_input_chars=150000) for name in ['planner','writer','editor','memory']}
    for name,role in roles.items():save_role_settings(repo,story.id,name,role,repo.get_story(story.id).revision)
    contexts=[]
    class Gateway:
        def stream(self,context,cancel):
            scene=repo.get_scene(context.scene_id);i=scene.position+1
            prose=f'A перейшов до кімнати {i}. Позначка {i}. '+('Докладне підтвердження події. '*35)
            if i==3:prose+=' Пошук ключа завершено.'
            if context.stage=='brief':raw=json.dumps({'objective':'Епізод','beats':['Подія']})
            elif context.stage in {'draft','edit'}:raw=prose
            else:
                contexts.append(context)
                prior=load_memory(context.fragments['previous_memory'])
                active=list(replay_memory(prior).values())
                state=next((e for e in active if e.category=='character_states'),None)
                ops=[{'action':'update' if state else 'add','category':'character_states','claim_id':state.claim_id if state else None,
                    'text':f'A у кімнаті {i}','character_ids':['A'],'evidence_id':'f000001'},
                    {'action':'add','category':'facts','claim_id':None,'text':f'Позначка {i}','character_ids':[],'evidence_id':'f000001'},
                    {'action':'add','category':'timeline','claim_id':None,'text':f'Перехід {i}','character_ids':[],'evidence_id':'f000001'}]
                if i==1:ops.append({'action':'add','category':'open_threads','claim_id':None,'text':'Пошук ключа','character_ids':[],'evidence_id':'f000001'})
                if i==3:
                    target=next(e for e in active if e.category=='open_threads')
                    ops.append({'action':'retire','category':'open_threads','claim_id':target.claim_id,'text':'Пошук ключа завершено','character_ids':[],'evidence_id':'f000001'})
                raw=json.dumps({'schema_version':2,'operations':ops})
            yield GenerationEvent(type='delta',text=raw)
            yield GenerationEvent(type='terminal',finish_reason='stop')
    worker=RunCoordinator(repo,lambda _:Gateway())
    run=worker.enqueue(RunRequest(story_id=story.id,scene_id=scenes[0].id,mode='remaining'),'scale')
    worker._execute(run.id)
    assert worker.get_run(run.id).state=='completed',worker.get_run(run.id).error
    current=repo.list_scenes(story.id)
    last=load_memory(repo.read_text(current[-1].heads['memory']))
    assert last.source_prose_ids==[s.heads['prose'] for s in current]
    assert len({e.event_id for e in last.events})==len(last.events)
    assert sum(e.category=='character_states' for e in replay_memory(last).values())==1
    assert not any(e.category=='open_threads' for e in replay_memory(last).values())
    early=build_context(repo,scenes[1].id,'draft',roles['writer'])
    section=early.user_text.split('ЗДІЙСНЕНІ ПОДІЇ — ПЕРЕВІРЕНА ПАМ’ЯТЬ\n')[1].split('\n\nЗАВЕРШЕННЯ')[0]
    assert 'A у кімнаті 1' in section and f'A у кімнаті {count}' not in section
    assert contexts[-1].memory_metrics['catalog_chars']<contexts[-1].memory_metrics['journal_chars']/2
    late=build_context(repo,current[-1].id,'brief',roles['planner'])
    prior=load_memory(contexts[-1].fragments['previous_memory'])
    assert late.memory_metrics['projection_chars']<len(legacy_view(prior).model_dump_json())/2
    first_memory=load_memory(repo.read_text(current[0].heads['memory']))
    legacy=repo.save_version(story.id,current[0].id,'memory',legacy_view(first_memory).model_dump_json(),first_memory.source_prose_ids)
    (tmp_path/'measurements.json').write_text(json.dumps({'scenes':count,'journal_chars':len(last.model_dump_json()),
        'literary_projection':late.memory_metrics,'memory_catalog':contexts[-1].memory_metrics,
        'memory_request_chars':len(contexts[-1].system_text)+len(contexts[-1].user_text),
        'literary_request_chars':len(late.system_text)+len(late.user_text)},ensure_ascii=False),encoding='utf-8')
    assert check_integrity(root).ok
    backup=create_backup(root,tmp_path/'backup');restore_backup(backup,tmp_path/'restored')
    restored=Repository(tmp_path/'restored')
    assert restored.read_text(current[-1].heads['memory'])==repo.read_text(current[-1].heads['memory'])
    assert restored.read_text(legacy.id)==repo.read_text(legacy.id)


@pytest.mark.parametrize('change,expected',[('cast','alternative'),('prose','alternative'),('future','completed')])
def test_v2_publication_uses_frozen_evidence_and_scope(tmp_path,change,expected):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Гонка'))
    first=repo.create_scene(story.id,SceneCreate(title='Перша',character_ids=['A']))
    future=repo.create_scene(story.id,SceneCreate(title='Майбутня'))
    prose=repo.save_version(story.id,first.id,'manual','A у бібліотеки.',[]);repo.set_head(first.id,'prose',prose.id,0)
    context=build_context(repo,first.id,'memory',RoleSettings(provider=ProviderSettings(model='fake')))
    class Gateway:
        def stream(self,*_):
            scene=repo.get_scene(first.id)
            if change=='cast':repo.update_scene_metadata(first.id,{'character_ids':['B']},scene.revision)
            elif change=='prose':
                new=repo.save_version(story.id,first.id,'manual','Інша проза',[]);repo.set_head(first.id,'prose',new.id,scene.revision)
            else:repo.update_scene_plan(future.id,'Новий майбутній план',0)
            yield GenerationEvent(type='delta',text=json.dumps({'schema_version':2,'operations':[{
                'action':'add','category':'character_states','claim_id':None,'text':'A у бібліотеки','character_ids':['A'],'evidence_id':'f000001'}]}))
            yield GenerationEvent(type='terminal',finish_reason='stop')
    attempt=execute_stage(repo,first.id,'memory',context,Gateway(),threading.Event(),lambda _:None)
    assert attempt.state==expected,attempt.error
    assert load_memory(repo.read_text(attempt.result_version_id)).events[0].source_version_id==prose.id
