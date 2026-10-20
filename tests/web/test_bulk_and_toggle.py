from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.web.app import create_app


def test_shared_provider_is_atomic_preserves_role_prompts_and_modes(tmp_path):
 app=create_app(AppSettings(data_dir=tmp_path))
 with TestClient(app,base_url='http://127.0.0.1:8765') as c:
  sid=c.post('/api/stories',json={'title':'Спільна модель'}).json()['id']
  before=c.get(f'/api/stories/{sid}/settings').json()
  c.put(f'/api/stories/{sid}/settings',json={'expected_revision':before['story']['revision'],'role':'editor','settings':{'provider':{'model':'old'},'edit_mode':'patches'},'prompt_text':'Власний промпт редактора'})
  before=c.get(f'/api/stories/{sid}/settings').json()
  body={'expected_revision':before['story']['revision'],'provider':{'provider':'venice','model':'qwen-3-6-plus'}}
  result=c.put(f'/api/stories/{sid}/settings/shared-provider',json=body)
  assert result.status_code==200
  after=c.get(f'/api/stories/{sid}/settings').json()
  assert set(after['roles'])=={'planner','writer','editor','memory'}
  assert all(role['provider']['model']=='qwen-3-6-plus' for role in after['roles'].values())
  assert all(role['provider']['key_env']=='VENICE_API_KEY' for role in after['roles'].values())
  assert after['roles']['editor']['edit_mode']=='patches'
  assert after['prompts']['editor']=='Власний промпт редактора'
  stale=c.put(f'/api/stories/{sid}/settings/shared-provider',json={**body,'provider':{'model':'wrong'}})
  assert stale.status_code==409
  assert c.get(f'/api/stories/{sid}/settings').json()['roles']==after['roles']


def test_evaluator_switch_off_preserves_config_and_prevents_manual_queue(tmp_path):
 app=create_app(AppSettings(data_dir=tmp_path))
 with TestClient(app,base_url='http://127.0.0.1:8765') as c:
  sid=c.post('/api/stories',json={'title':'Без оцінювача'}).json()['id']
  # Disabling must work even before evaluator is configured.
  result=c.put(f'/api/stories/{sid}/evaluator/policy',json={'policy':'off'})
  assert result.status_code==200 and result.json()['policy']=='off'
  settings=result.json();settings['config']['model']='test-judge'
  assert c.put(f'/api/stories/{sid}/evaluator',json=settings).status_code==200
  assert c.put(f'/api/stories/{sid}/evaluator/policy',json={'policy':'report'}).status_code==200
  off=c.put(f'/api/stories/{sid}/evaluator/policy',json={'policy':'off'}).json()
  assert off['config']['model']=='test-judge'
  result=c.post(f'/api/stories/{sid}/evaluate',json={'mode':'story','request_id':'disabled'})
  assert result.status_code==400 and 'вимкнено' in result.json()['detail']
  assert c.get(f'/api/stories/{sid}/runs').json()['runs']==[]


def test_bulk_save_includes_current_role_changes_without_copying_its_prompt(tmp_path):
 app=create_app(AppSettings(data_dir=tmp_path))
 with TestClient(app,base_url='http://127.0.0.1:8765') as c:
  story=c.post('/api/stories',json={'title':'Промпти окремо'}).json();sid=story['id']
  body={'expected_revision':story['revision'],'provider':{'model':'same'},'role':'editor','settings':{'provider':{'model':'same'},'edit_mode':'patches','temperature':0.2},'prompt_text':'Тільки для редактора'}
  assert c.put(f'/api/stories/{sid}/settings/shared-provider',json=body).status_code==200
  result=c.get(f'/api/stories/{sid}/settings').json()
  assert result['prompts']['editor']=='Тільки для редактора'
  assert all(result['roles'][role]['prompt_version_id'] is None for role in ['planner','writer','memory'])
  assert result['roles']['editor']['edit_mode']=='patches'
  assert result['roles']['writer']['temperature']==0.7
