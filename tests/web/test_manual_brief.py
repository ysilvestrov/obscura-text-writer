import json
import pytest
from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from storygen.generation.context import build_context
from storygen.providers.models import RoleSettings,ProviderSettings
from tests.memory.test_forwarding import seeded,apply
from storygen.memory.forwarding import memory_view


@pytest.mark.parametrize('proposals',[False,True])
def test_edit_generated_brief_after_forwarding_can_save_with_cas_and_review(tmp_path,proposals):
    repo,story,scenes=seeded(tmp_path)
    target=repo.get_scene(scenes[2].id)
    role=RoleSettings(provider=ProviderSettings(model='offline'))
    context=build_context(repo,target.id,'brief',role)
    original={'objective':'Мета','beats':['Подія'],'constraints':[],'proposed_changes':[]}
    old=repo.save_version(story.id,target.id,'brief',json.dumps(original),context.input_refs,dependency_snapshot=context.dependency_snapshot)
    target=repo.set_head(target.id,'brief',old.id,target.revision)
    claim=memory_view(repo,scenes[1].id)['rows'][0]['claim_id']
    apply(repo,scenes[1],{claim:False})
    assert repo.get_version(old.id).stale
    original['objective']='Авторська правка'
    original['proposed_changes']=['Змінити план'] if proposals else []
    body={'text':json.dumps(original),'expected_revision':target.revision}
    with TestClient(create_app(AppSettings(data_dir=tmp_path)),base_url='http://127.0.0.1:8765') as client:
        result=client.post(f'/api/scenes/{target.id}/brief',json=body)
        assert result.status_code==200,result.text
        data=result.json();ref=repo.get_version(data['version']['id'])
        assert ref.id!=old.id and not ref.stale and ref.manual_projection_policy==[claim]
        assert json.loads(repo.read_text(ref.id))['objective']=='Авторська правка'
        assert repo.get_version(old.id).stale
        if proposals:
            assert data['needs_review'] and repo.get_scene(target.id).heads['brief']==old.id
            accepted=client.post(f'/api/scenes/{target.id}/accept-brief',json={'version_id':ref.id,'expected_revision':target.revision})
            assert accepted.status_code==200,accepted.text
        assert repo.get_scene(target.id).heads['brief']==ref.id
        conflict=client.post(f'/api/scenes/{target.id}/brief',json=body)
        assert conflict.status_code==409
        assert repo.get_scene(target.id).heads['brief']==ref.id
        apply(repo,repo.get_scene(scenes[1].id),{claim:True})
        assert repo.get_version(ref.id).stale

@pytest.mark.parametrize('source_kind',['accepted','candidate','legacy','wrong'])
def test_edit_brief_preserves_only_selected_head_acceptance(tmp_path,source_kind):
    repo,story,scenes=seeded(tmp_path)
    scene=repo.get_scene(scenes[2].id)
    accepted={'objective':'Прийнята мета','beats':['Подія'],'constraints':[],'proposed_changes':['Уточнити план']}
    selected=repo.save_version(story.id,scene.id,'brief',json.dumps(accepted),[])
    scene=repo.set_head(scene.id,'brief',selected.id,scene.revision)
    candidate=repo.save_version(story.id,scene.id,'brief',json.dumps({**accepted,'objective':'Нова пропозиція'}),[])
    body={'text':json.dumps({**accepted,'objective':'Авторська правка'}),'expected_revision':scene.revision}
    if source_kind!='legacy':body['source_brief_id']={'accepted':selected.id,'candidate':candidate.id,'wrong':'not-a-version'}[source_kind]
    with TestClient(create_app(AppSettings(data_dir=tmp_path)),base_url='http://127.0.0.1:8765') as client:
        result=client.post(f'/api/scenes/{scene.id}/brief',json=body)
        assert result.status_code==200,result.text
        saved=result.json();head=repo.get_scene(scene.id).heads['brief']
        if source_kind=='accepted':
            assert saved['needs_review'] is False and head==saved['version']['id']
        else:
            assert saved['needs_review'] is True and head==selected.id

def test_stale_accepted_source_cannot_replace_new_head(tmp_path):
    repo,story,scenes=seeded(tmp_path);scene=repo.get_scene(scenes[2].id)
    brief={'objective':'Прийняте','beats':['Подія'],'constraints':[],'proposed_changes':['Пропозиція']}
    first=repo.save_version(story.id,scene.id,'brief',json.dumps(brief),[]);scene=repo.set_head(scene.id,'brief',first.id,scene.revision)
    revision=scene.revision
    newer=repo.save_version(story.id,scene.id,'brief',json.dumps({**brief,'objective':'Інша вкладка'}),[]);repo.set_head(scene.id,'brief',newer.id,revision)
    with TestClient(create_app(AppSettings(data_dir=tmp_path)),base_url='http://127.0.0.1:8765') as client:
        response=client.post(f'/api/scenes/{scene.id}/brief',json={'text':json.dumps({**brief,'objective':'Моя правка'}),'expected_revision':revision,'source_brief_id':first.id})
        assert response.status_code==409
        assert repo.get_scene(scene.id).heads['brief']==newer.id
