import json
import pytest
from storygen.domain import StoryCreate,SceneCreate
from storygen.storage.repository import Repository
from storygen.providers.models import RoleSettings,ProviderSettings
from storygen.generation.context import build_context


def prepared(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Час відомостей'))
    scenes=[repo.create_scene(story.id,SceneCreate(title=str(i),beats='План',character_ids=['A'])) for i in range(3)]
    cards=[{'schema_version':2,'id':'A','name':'Анна','entries':[
        {'id':'future','text':'ПРИХОВАНИЙ МАЙБУТНІЙ ФАКТ','availability':'from_scene','available_from_scene_id':scenes[2].id,'origin':'author','sources':[]},
        {'id':'unknown','text':'Неперевірений опис','availability':'unclassified','available_from_scene_id':None,'origin':'author','sources':[]}]}]
    ref=repo.save_version(story.id,None,'character_cards',json.dumps(cards),[])
    repo.publish_story_material(story.id,'characters_version_id',ref.id,repo.get_story(story.id).revision)
    for head,kind,text in [('brief','brief','{"objective":"Подія","beats":["Подія"]}'),('draft','draft','Чернетка')]:
        ref=repo.save_version(story.id,scenes[0].id,kind,text,[])
        repo.set_head(scenes[0].id,head,ref.id,repo.get_scene(scenes[0].id).revision)
    return repo,story,scenes


@pytest.mark.parametrize('stage',['brief','draft','edit'])
def test_each_literary_stage_excludes_future_character_facts_and_warns(tmp_path,stage):
    repo,story,scenes=prepared(tmp_path)
    ctx=build_context(repo,scenes[0].id,stage,RoleSettings(provider=ProviderSettings(model='fake')))
    assert 'ПРИХОВАНИЙ МАЙБУТНІЙ ФАКТ' not in ctx.user_text
    assert 'Неперевірений опис' in ctx.user_text
    assert ctx.context_warnings and 'не перевірено' in ctx.context_warnings[0]


def test_context_warning_persists_without_api_call_or_prose_buffer_changes(tmp_path):
    from storygen.authoring.blueprints import save_role_settings
    from storygen.generation.worker import RunCoordinator,RunRequest
    from storygen.providers.streaming import GenerationEvent
    repo,story,scenes=prepared(tmp_path)
    save_role_settings(repo,story.id,'planner',RoleSettings(provider=ProviderSettings(model='fake')),repo.get_story(story.id).revision)
    class Gateway:
        def stream(self,*_):
            yield GenerationEvent(type='delta',text='{"objective":"Подія","beats":["План"]}')
            yield GenerationEvent(type='terminal',finish_reason='stop')
    worker=RunCoordinator(repo,lambda _:Gateway())
    run=worker.enqueue(RunRequest(story_id=story.id,scene_id=scenes[0].id,mode='stage',stage='brief'),'warning')
    worker._execute(run.id)
    assert worker.get_run(run.id).state=='completed'
    assert 'не перевірено' in worker.get_run(run.id).warning
    assert any(e.type=='context_warning' for e in worker.list_events(run.id))
    assert Repository(tmp_path).get_run(run.id).warning==worker.get_run(run.id).warning


def test_evaluator_error_preserves_existing_context_warning(tmp_path):
    from storygen.evaluation.story_adapter import EvaluationSettings,save_evaluation_settings
    from storygen.evaluation.models import EvaluatorConfig
    from storygen.evaluation.gateway import GatewayFailure
    from storygen.generation.worker import RunCoordinator,RunRequest
    repo,story,scenes=prepared(tmp_path)
    ref=repo.save_version(story.id,scenes[0].id,'manual','Анна увійшла.',[])
    repo.set_head(scenes[0].id,'prose',ref.id,repo.get_scene(scenes[0].id).revision)
    save_evaluation_settings(repo,story.id,EvaluationSettings(config=EvaluatorConfig(provider='local',model='fake',max_input_chars=100000)))
    class Gateway:
        def complete(self,*_):raise GatewayFailure('Технічна причина')
    worker=RunCoordinator(repo,evaluator_factory=lambda _:Gateway())
    run=worker.enqueue(RunRequest(story_id=story.id,scene_id=scenes[0].id,mode='evaluate'),'evaluate-warning')
    run.warning='Попередження контексту';worker._save(run)
    worker._evaluate(run)
    assert 'Попередження контексту' in worker.get_run(run.id).warning
    assert 'Технічна причина' in worker.get_run(run.id).warning
