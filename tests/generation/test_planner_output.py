import json,threading
import pytest
from storygen.generation.context import build_context
from storygen.generation.stages import execute_stage
from storygen.generation.models import WritersBrief
from storygen.providers.streaming import GenerationEvent
from tests.generation.test_scene_pipeline import prepare


def run_output(root,raw):
    repo,scene,_,roles=prepare(root)
    context=build_context(repo,scene.id,'brief',roles['planner'])
    class Gateway:
        calls=0
        def stream(self,*args):
            self.calls+=1
            yield GenerationEvent(type='delta',text=raw)
            yield GenerationEvent(type='terminal',finish_reason='stop')
    gateway=Gateway()
    attempt=execute_stage(repo,scene.id,'brief',context,gateway,threading.Event(),lambda _:None)
    assert gateway.calls==1
    assert repo.files.resolve(attempt.partial_path).read_text(encoding='utf-8')==raw
    return repo,scene,attempt


@pytest.mark.parametrize('tag',['json','JSON',''])
def test_planner_accepts_one_outer_json_fence_and_keeps_raw(tmp_path,tag):
    payload={'objective':'Мета','beats':['Відчинити двері'],'proposed_changes':[]}
    raw='\n\n```'+tag+'\n'+json.dumps(payload,ensure_ascii=False)+'\n```\n'
    repo,scene,attempt=run_output(tmp_path,raw)
    assert attempt.state=='completed',attempt.error
    assert attempt.context['planner_warnings']
    assert repo.get_scene(scene.id).heads['brief']==attempt.result_version_id
    assert WritersBrief.model_validate_json(repo.read_text(attempt.result_version_id)).beats==payload['beats']


def test_wrapped_planner_proposals_still_require_review(tmp_path):
    raw='```json\n'+json.dumps({'objective':'Мета','beats':['Подія'],'proposed_changes':['Змінити план']})+'\n```'
    repo,scene,attempt=run_output(tmp_path,raw)
    assert attempt.state=='needs_review' and attempt.result_version_id
    assert 'brief' not in repo.get_scene(scene.id).heads


@pytest.mark.parametrize('raw,reason',[
    ('Пояснення\n```json\n{}\n```','JSON'),
    ('{}\n{}','JSON'),
    ('{"objective":"a","objective":"b","beats":["c"]}','повтор'),
    ('{"objective":NaN,"beats":["c"]}','числов'),
    ('{"objective":"a","beats":"PRIVATE_VALUE"}','beats'),
    ('{"objective":"a","beats":[]}','beats'),
    ('{"objective":"a","beats":["c"],"PRIVATE_FIELD":"PRIVATE_VALUE"}','Зайве'),
])
def test_planner_failures_are_concrete_and_do_not_echo_values(tmp_path,raw,reason):
    repo,scene,attempt=run_output(tmp_path,raw)
    assert attempt.state=='failed' and not attempt.result_version_id
    assert reason.lower() in attempt.error.lower()
    assert 'PRIVATE' not in attempt.error
    assert attempt.context['planner_failure']['category'] in {'json','schema'}
    assert 'brief' not in repo.get_scene(scene.id).heads


def test_prepare_uses_same_envelope_with_its_own_schema(tmp_path):
    from storygen.generation.context import make_context
    repo,scene,_,roles=prepare(tmp_path)
    context=make_context(repo,repo.get_story(scene.story_id),None,'prepare',roles['planner'],[],[])
    raw='```json\n'+json.dumps({'canon':'Канон','characters':[],'scenes':[{'title':'Перша'}]})+'\n```'
    class Gateway:
        def stream(self,*args):
            yield GenerationEvent(type='delta',text=raw)
            yield GenerationEvent(type='terminal',finish_reason='stop')
    attempt=execute_stage(repo,None,'prepare',context,Gateway(),threading.Event(),lambda _:None)
    assert attempt.state=='completed',attempt.error
    assert attempt.context['planner_warnings']
    assert json.loads(repo.read_text(attempt.result_version_id))['canon']=='Канон'


def test_worker_reports_envelope_warning_without_another_call(tmp_path):
    from storygen.generation.worker import RunCoordinator,RunRequest
    from storygen.authoring.blueprints import save_role_settings
    repo,scene,_,roles=prepare(tmp_path)
    save_role_settings(repo,scene.story_id,'planner',roles['planner'],repo.get_story(scene.story_id).revision)
    class Gateway:
        calls=0
        def stream(self,*args):
            self.calls+=1
            yield GenerationEvent(type='delta',text='```json\n{"objective":"Мета","beats":["Подія"]}\n```')
            yield GenerationEvent(type='terminal',finish_reason='stop')
    gateway=Gateway();worker=RunCoordinator(repo,lambda _:gateway)
    from tests.generation.test_worker import wait_until
    worker.start()
    try:
        run=worker.enqueue(RunRequest(story_id=scene.story_id,scene_id=scene.id,mode='stage',stage='brief'),'fenced')
        wait_until(lambda:worker.get_run(run.id).state in {'completed','failed'})
        current=worker.get_run(run.id)
    finally:worker.stop()
    assert current.state=='completed' and 'Markdown' in current.warning
    assert gateway.calls==1
    assert any(event.type=='context_warning' and 'Markdown' in str(event.data) for event in worker.list_events(run.id))
