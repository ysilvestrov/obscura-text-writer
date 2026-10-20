import json
import threading
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from storygen.domain import StoryCreate, SceneCreate
from storygen.storage.repository import Repository
from storygen.authoring.imports import SourceFile, import_sources
from storygen.authoring.blueprints import save_role_settings
from storygen.generation.context import build_context, make_context
from storygen.generation.stages import execute_stage
from storygen.generation.worker import RunCoordinator, RunRequest
from storygen.generation.dependencies import save_manual_prose
from storygen.providers.models import RoleSettings, ProviderSettings
from storygen.providers.streaming import GenerationEvent, build_generation_gateway
from storygen.memory.models import MemorySnapshot
from storygen.memory.service import memory_before, rebuild_memory
from storygen.application.exports import export_story
from storygen.evaluation.models import EvaluatorConfig
from storygen.evaluation.story_adapter import EvaluationSettings, save_evaluation_settings


def setup(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Регресія'))
    scene=repo.create_scene(story.id,SceneCreate(title='Ранок',beats='Студія'))
    return repo,story,scene


def test_reimport_characters_invalidates_existing_and_inflight_context(tmp_path):
    repo,story,scene=setup(tmp_path)
    imported=import_sources(repo,story.id,[SourceFile(name='characters.txt',raw='Лєрі 27 років.'.encode(),kind='source_characters')])
    old=imported.version_ids[0]
    prose=repo.save_version(story.id,scene.id,'edited','Лєрі 27 років.',[old]);repo.set_head(scene.id,'prose',prose.id,0)
    context=build_context(repo,scene.id,'brief',RoleSettings(provider=ProviderSettings(model='fake')))
    import_sources(repo,story.id,[SourceFile(name='characters.txt',raw='Лєрі 28 років.'.encode(),kind='source_characters')])
    assert repo.get_story(story.id).revision>context.story_revision
    assert repo.get_version(prose.id).stale
    class Gateway:
        def stream(self,*args):
            yield GenerationEvent(type='delta',text='{"objective":"Ранок","beats":["Студія"]}')
            yield GenerationEvent(type='terminal',finish_reason='stop')
    attempt=execute_stage(repo,scene.id,'brief',context,Gateway(),threading.Event(),lambda _:None)
    assert attempt.state=='alternative' and 'brief' not in repo.get_scene(scene.id).heads


def test_memory_rebuild_does_not_accept_unreviewed_prose(tmp_path):
    repo,story,first=setup(tmp_path);second=repo.create_scene(story.id,SceneCreate(title='Друга'))
    save_manual_prose(repo,first.id,'Ранок',0);save_manual_prose(repo,second.id,'Вечір',0)
    class Gateway:
        def stream(self,context,cancel):
            snapshot=memory_before(repo,context.scene_id)
            snapshot.source_prose_ids.append(repo.get_scene(context.scene_id).heads['prose'])
            yield GenerationEvent(type='delta',text=snapshot.model_dump_json())
            yield GenerationEvent(type='terminal',finish_reason='stop')
    settings=RoleSettings(provider=ProviderSettings(model='fake'))
    rebuild_memory(repo,first.id,lambda _:Gateway(),threading.Event(),lambda *_:None,settings=settings)
    save_manual_prose(repo,first.id,'Змінений ранок',repo.get_scene(first.id).revision)
    assert repo.get_scene(second.id).needs_review
    rebuild_memory(repo,first.id,lambda _:Gateway(),threading.Event(),lambda *_:None,settings=settings)
    assert repo.get_scene(second.id).needs_review
    with pytest.raises(ValueError):export_story(repo,story.id,'md')


def test_uncertain_evaluator_requires_explicit_repeat(tmp_path):
    repo,story,scene=setup(tmp_path);save_manual_prose(repo,scene.id,'Лєра увійшла.',0)
    settings=EvaluationSettings(config=EvaluatorConfig(provider='codex_cli',model='fake',max_input_chars=100000),context_tokens=128000)
    save_evaluation_settings(repo,story.id,settings)
    class CrashGateway:
        def complete(self,request):raise RuntimeError('Simulated process death')
    worker=RunCoordinator(repo,evaluator_factory=lambda _:CrashGateway())
    run=worker.enqueue(RunRequest(story_id=story.id,scene_id=scene.id,mode='evaluate'),'uncertain')
    run.state='running';worker._save(run)
    with pytest.raises(RuntimeError):worker._execute(run.id)
    restarted=RunCoordinator(repo)
    with restarted.lock:restarted.recover_interrupted()
    with pytest.raises(ValueError,match='явне'):restarted.resume(run.id)
    assert repo.list_attempts(story.id,run.id)[0].state=='interrupted'


def test_strict_generation_schema_requires_every_property(tmp_path):
    repo,story,scene=setup(tmp_path)
    role=RoleSettings(provider=ProviderSettings(model='fake',response_mode='json_schema'))
    context=build_context(repo,scene.id,'brief',role)
    captured=[]
    def handler(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200,headers={'content-type':'text/event-stream'},content='data: [DONE]\n\n')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        list(build_generation_gateway(role.provider,http_client=client).stream(context,threading.Event()))
    schema=captured[0]['response_format']['json_schema']['schema']
    def check(node):
        if isinstance(node,dict):
            if 'properties' in node:assert set(node['required'])==set(node['properties'])
            for value in node.values():check(value)
        elif isinstance(node,list):
            for item in node:check(item)
    check(schema)


def test_planner_brief_override_does_not_replace_prepare_prompt(tmp_path):
    repo,story,scene=setup(tmp_path)
    custom=repo.save_version(story.id,None,'prompt','Тільки завдання письменнику.',[])
    role=RoleSettings(provider=ProviderSettings(model='fake'),prompt_version_id=custom.id)
    prepared=make_context(repo,repo.get_story(story.id),None,'prepare',role,['Джерело'],[])
    assert '"canon"' in prepared.system_text
    assert custom.id not in prepared.input_refs


def test_unchanged_default_prompt_is_not_saved_as_override(tmp_path):
    app=create_app(AppSettings(data_dir=tmp_path));repo=app.state.repo;story=repo.create_story(StoryCreate(title='Роль'))
    role=RoleSettings(provider=ProviderSettings(model='fake'))
    story=save_role_settings(repo,story.id,'planner',role,story.revision)
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        view=client.get(f'/api/stories/{story.id}/settings').json()
        client.put(f'/api/stories/{story.id}/settings',json={'expected_revision':story.revision,'role':'planner','settings':role.model_dump(),'prompt_text':view['prompts']['planner']})
        saved=client.get(f'/api/stories/{story.id}/settings').json()
        assert saved['roles']['planner']['prompt_version_id'] is None


def test_plan_preamble_is_in_versioned_scene_context(tmp_path):
    repo,story,scene=setup(tmp_path)
    import_sources(repo,story.id,[SourceFile(name='plan.txt',raw='Глобальна вимога: ненадійний оповідач.\nСцена 1. Ранок\nСтудія'.encode())])
    context=build_context(repo,scene.id,'brief',RoleSettings(provider=ProviderSettings(model='fake')))
    assert 'Глобальна вимога: ненадійний оповідач.' in context.user_text


def test_author_can_edit_brief_and_proposals_need_separate_acceptance(tmp_path):
    app=create_app(AppSettings(data_dir=tmp_path));repo=app.state.repo
    story=repo.create_story(StoryCreate(title='Завдання'));scene=repo.create_scene(story.id,SceneCreate(title='Ранок'))
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        brief={'objective':'Ранок','beats':['Студія'],'proposed_changes':[]}
        result=client.post(f'/api/scenes/{scene.id}/brief',json={'text':json.dumps(brief),'expected_revision':scene.revision})
        assert result.status_code==200
        assert repo.get_scene(scene.id).heads['brief']==result.json()['version']['id']
        brief['proposed_changes']=['Змінити місце фіналу']
        proposal=client.post(f'/api/scenes/{scene.id}/brief',json={'text':json.dumps(brief),'expected_revision':1}).json()
        assert proposal['needs_review']
        assert repo.get_scene(scene.id).heads['brief']!=proposal['version']['id']


def test_evaluation_resume_reuses_completed_windows(tmp_path,monkeypatch):
    from storygen.evaluation import story_adapter
    from storygen.evaluation.models import GatewayResult
    repo,story,first=setup(tmp_path);second=repo.create_scene(story.id,SceneCreate(title='Друга'))
    save_manual_prose(repo,first.id,'Перший текст',0);save_manual_prose(repo,second.id,'Другий текст',0)
    settings=EvaluationSettings(config=EvaluatorConfig(provider='codex_cli',model='fake',max_input_chars=100000),context_tokens=128000)
    save_evaluation_settings(repo,story.id,settings)
    cases=[story_adapter.build_evaluation_case(repo,story.id,s.id,'scene') for s in [first,second]]
    monkeypatch.setattr(story_adapter,'plan_evaluation_windows',lambda *_:cases)
    def result(request):
        data=json.loads(request.messages[1]['content'])
        report={'assessments':[{'criterion_id':k,'status':'assessed','score':4,'explanation':'Перевірено'} for k in data['required_criteria']],'findings':[],'checked_document_ids':[d['id'] for d in data['documents']],'limitations':[]}
        return GatewayResult(text=json.dumps(report),finish_reason='stop')
    initial=[]
    class CrashSecond:
        def complete(self,request):
            initial.append(request)
            if len(initial)==2:raise RuntimeError('crash during window two')
            return result(request)
    worker=RunCoordinator(repo,evaluator_factory=lambda _:CrashSecond())
    run=worker.enqueue(RunRequest(story_id=story.id,mode='evaluate',evaluation_mode='story'),'windows')
    run.state='running';worker._save(run)
    with pytest.raises(RuntimeError):worker._execute(run.id)
    repeated=[]
    class ResumeSecond:
        def complete(self,request):repeated.append(request);return result(request)
    restarted=RunCoordinator(repo,evaluator_factory=lambda _:ResumeSecond())
    with restarted.lock:restarted.recover_interrupted()
    restarted.resume(run.id,repeat_interrupted=True)
    restarted._execute(run.id)
    assert restarted.get_run(run.id).state=='completed'
    assert len(repeated)==1
    assert any(e.type=='reused' and e.data['stage']=='evaluate' for e in restarted.list_events(run.id))


def test_story_evaluation_includes_author_characters_and_exposes_missing_plan(tmp_path):
    from storygen.evaluation.story_adapter import build_evaluation_case
    repo,story,scene=setup(tmp_path)
    raw=import_sources(repo,story.id,[SourceFile(name='characters.txt',raw='Лєрі двадцять сім років.'.encode(),kind='source_characters')])
    save_manual_prose(repo,scene.id,'Лєра увійшла.',0)
    case=build_evaluation_case(repo,story.id,scene.id,'scene')
    assert any(d.version==raw.version_ids[0] and d.kind=='canon' for d in case.documents)
    assert case.coverage.unchecked_links


def test_memory_context_contains_only_prose_and_past_snapshot(tmp_path):
    repo,story,scene=setup(tmp_path)
    source=import_sources(repo,story.id,[SourceFile(name='characters.txt',raw='ЗОВНІШНІЙ КАНОН: Лєрі 27 років.'.encode(),kind='source_characters')]).version_ids[0]
    repo.create_scene(story.id,SceneCreate(title='Майбутній фінал',beats='МАЙБУТНЯ ПОДІЯ: відкрити студію'))
    prose=save_manual_prose(repo,scene.id,'Лєра відчинила двері.',0)
    context=build_context(repo,scene.id,'memory',RoleSettings(provider=ProviderSettings(model='fake')))
    assert 'ЗОВНІШНІЙ КАНОН' not in context.user_text
    assert 'МАЙБУТНЯ ПОДІЯ' not in context.user_text
    assert source not in context.input_refs
    assert prose.id in context.input_refs
    assert json.loads(context.fragments['expected_source_prose_ids'])==[prose.id]
