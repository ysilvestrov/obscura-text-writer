from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from tests.generation.test_edit_classification import fixture,Gateway
import json
import pytest


@pytest.mark.parametrize('protocol',[1,2])
def test_historical_no_changes_cannot_preview_subset_or_publish(tmp_path,protocol):
    repo,scene,a=fixture(tmp_path)
    raw=a.context['copyedit_proposal']
    original=repo.read_text(raw['draft_id'])
    raw['protocol_version']=protocol
    raw['proposal']={'edits':[]} if protocol==1 else dict(algorithm_version=1,candidate_text=original,edits=[])
    repo.save_attempt(a)
    with TestClient(create_app(AppSettings(data_dir=tmp_path)),base_url='http://127.0.0.1:8765') as client:
        url=f'/api/scenes/{scene.id}/copyedits/{a.id}'
        p=client.get(url).json()
        assert not p['can_apply'] and not p['has_changes']
        assert not p['can_classify']
        body=dict(expected_revision=p['expected_revision'],proposal_fingerprint=p['proposal_fingerprint'],selected_indices=[])
        before=len(repo.list_versions(scene.story_id,scene.id))
        for suffix in ['', '/selection-preview']:
            result=client.post(url+suffix,json=body)
            assert result.status_code==400 and 'не запропонував змін' in result.json()['detail']
        assert len(repo.list_versions(scene.story_id,scene.id))==before
        assert not repo.get_scene(scene.id).heads.get('prose')


def test_diff_preview_classification_and_subset_api(tmp_path):
    repo,scene,a=fixture(tmp_path)
    payload={'changes':[dict(index=i,category='grammar',assessment='uncertain',explanation='Перевірити.') for i in [0,1]]}
    app=create_app(AppSettings(data_dir=tmp_path),gateway_factory=lambda _:Gateway(json.dumps(payload)))
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        url=f'/api/scenes/{scene.id}/copyedits/{a.id}'
        p=client.get(url).json()
        body=dict(expected_revision=p['expected_revision'],proposal_fingerprint=p['proposal_fingerprint'],selected_indices=[0])
        res=client.post(url+'/selection-preview',json=body)
        assert res.status_code==200 and res.json()['text']=='Вона йшла.\n\nВона співаю.'
        assert not repo.get_scene(scene.id).heads.get('prose')
        bad=client.post(url+'/selection-preview',json={**body,'selected_indices':[True]})
        assert bad.status_code==422
        run=client.post(url+'/classify',json={'request_id':'test-classify','proposal_fingerprint':p['proposal_fingerprint']})
        assert run.status_code==200 and run.json()['request']['mode']=='classify'
        applied=client.post(url,json=body)
        assert applied.status_code==200
        assert repo.read_text(applied.json()['version']['id'])=='Вона йшла.\n\nВона співаю.'


def test_classifier_json_validation_identifies_field_without_echo(tmp_path):
    repo,scene,_=fixture(tmp_path)
    app=create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        settings=client.get(f'/api/stories/{scene.story_id}/settings').json()
        role=settings['roles']['editor'];role['classification']['max_output_tokens']='secret-invalid-value'
        result=client.put(f'/api/stories/{scene.story_id}/settings',json=dict(expected_revision=settings['story']['revision'],role='editor',settings=role))
        assert result.status_code==422
        assert 'max_output_tokens' in result.json()['detail']
        assert 'secret-invalid-value' not in result.text
