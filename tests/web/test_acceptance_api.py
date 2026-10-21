from fastapi.testclient import TestClient
from storygen.web.app import create_app
from storygen.application.settings import AppSettings
from storygen.domain import StoryCreate, SceneCreate


def test_acceptance_http_preview_commit_and_conflict(tmp_path):
    app=create_app(AppSettings(data_dir=tmp_path))
    repo=app.state.repo
    story=repo.create_story(StoryCreate(title='Автор'))
    scene=repo.create_scene(story.id,SceneCreate(title='Сцена'))
    ref=repo.save_version(story.id,scene.id,'draft','Історична чернетка',[])
    client=TestClient(app,base_url='http://127.0.0.1:8765')
    url=f'/api/scenes/{scene.id}'
    preview=client.get(url+'/acceptance-preview',params={'version_id':ref.id})
    assert preview.status_code==200
    data=preview.json()
    assert data['text']=='Історична чернетка'
    body={key:data[key] for key in ['version_id','expected_revision','preview_fingerprint']}
    accepted=client.post(url+'/accept-version',json=body)
    assert accepted.status_code==200
    assert accepted.json()['scene']['heads']['draft']==ref.id
    history=client.get(url+'/versions').json()['acceptances']
    assert history[0]['id']==accepted.json()['acceptance']['id']
    assert client.post(url+'/accept-version',json=body).status_code==409
    memory=repo.save_version(story.id,scene.id,'memory','{}',[])
    assert client.get(url+'/acceptance-preview',params={'version_id':memory.id}).status_code==400
    from storygen.run_models import Run,RunRequest
    from storygen.domain import StageAttempt,new_id
    run=Run(id=new_id(),story_id=story.id,request_id='continue-http',request=RunRequest(story_id=story.id,scene_id=scene.id,mode='stage',stage='draft'),state='alternative',tasks=[{'stage':'draft','scene_id':scene.id}])
    repo.enqueue_run(run)
    attempt=StageAttempt(id=new_id(),run_id=run.id,story_id=story.id,scene_id=scene.id,stage='draft',state='alternative',context={'run_cursor':0},partial_path='partial.txt',result_version_id=ref.id)
    repo.save_attempt(attempt)
    continued=client.post(f'/api/runs/{run.id}/continue-after-acceptance',json={'version_id':ref.id,'expected_cursor':0,'expected_scene_revision':accepted.json()['scene']['revision'],'acceptance_id':accepted.json()['acceptance']['id']})
    assert continued.status_code==200 and continued.json()['cursor']==1
    assert repo.get_attempt(attempt.id).state=='alternative'


def test_acceptance_preview_rejects_other_scene_and_changed_sources(tmp_path):
    app=create_app(AppSettings(data_dir=tmp_path));repo=app.state.repo
    story=repo.create_story(StoryCreate(title='Твір'))
    scene=repo.create_scene(story.id,SceneCreate(title='Сцена'))
    other=repo.create_scene(story.id,SceneCreate(title='Друга'))
    ref=repo.save_version(story.id,other.id,'manual','Текст',[])
    client=TestClient(app,base_url='http://127.0.0.1:8765')
    url=f'/api/scenes/{scene.id}'
    assert client.get(url+'/acceptance-preview',params={'version_id':ref.id}).status_code==400
    ref=repo.save_version(story.id,scene.id,'manual','Свій текст',[])
    data=client.get(url+'/acceptance-preview',params={'version_id':ref.id}).json()
    repo.update_scene_plan(other.id,'Новий план',other.revision)
    body={key:data[key] for key in ['version_id','expected_revision','preview_fingerprint']}
    assert client.post(url+'/accept-version',json=body).status_code==409
    assert repo.list_acceptances(story.id)==[]
