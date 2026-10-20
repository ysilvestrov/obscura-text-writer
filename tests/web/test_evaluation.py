import json
import time
from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from storygen.domain import StoryCreate, SceneCreate
from storygen.generation.dependencies import save_manual_prose
from storygen.evaluation.models import GatewayResult


def test_candidate_profile_is_not_presented_as_quality_pass(tmp_path):
    calls=[]
    class Gateway:
        def complete(self,request):
            calls.append(request)
            data=json.loads(request.messages[1]['content'])
            report={'assessments':[{'criterion_id':key,'status':'assessed','score':4,'explanation':'Перевірено'} for key in data['required_criteria']], 'findings':[], 'checked_document_ids':[d['id'] for d in data['documents']],'limitations':[]}
            return GatewayResult(text=json.dumps(report),finish_reason='stop')
    app=create_app(AppSettings(data_dir=tmp_path),evaluator_factory=lambda _:Gateway());repo=app.state.repo
    story=repo.create_story(StoryCreate(title='Оцінка'));scene=repo.create_scene(story.id,SceneCreate(title='Ранок'));save_manual_prose(repo,scene.id,'Лєра увійшла до студії.',0)
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        assert client.put(f'/api/stories/{story.id}/evaluator',json={'config':{'provider':'codex_cli','max_input_chars':100000},'context_tokens':128000}).status_code==200
        run=client.post(f'/api/stories/{story.id}/evaluate',json={'scene_id':scene.id,'mode':'scene','request_id':'judge'}).json()
        deadline=time.monotonic()+5
        while time.monotonic()<deadline and app.state.coordinator.get_run(run['id']).state not in {'completed','failed'}:time.sleep(.01)
        assert app.state.coordinator.get_run(run['id']).state=='completed'
        reports=client.get(f'/api/stories/{story.id}/evaluations').json()['evaluations']
        assert len(calls)==1 and reports[0]['outcome']['status']=='incomplete'
        save_manual_prose(repo,scene.id,'Змінена сцена',repo.get_scene(scene.id).revision)
        assert repo.get_version(reports[0]['version']['id']).stale
