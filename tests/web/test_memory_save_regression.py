from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from storygen.domain import StoryCreate,SceneCreate
from storygen.generation.dependencies import save_manual_prose
from storygen.memory.models import MemorySnapshot


def test_stale_memory_buffer_reports_revision_conflict_before_source_validation(tmp_path):
 app=create_app(AppSettings(data_dir=tmp_path));repo=app.state.repo
 story=repo.create_story(StoryCreate(title='Память'));scene=repo.create_scene(story.id,SceneCreate(title='Перша'))
 old=save_manual_prose(repo,scene.id,'Старий текст.',scene.revision);revision=repo.get_scene(scene.id).revision
 snapshot=MemorySnapshot(source_prose_ids=[old.id])
 save_manual_prose(repo,scene.id,'Нова проза.',revision)
 with TestClient(app,base_url='http://127.0.0.1:8765') as client:
  response=client.post(f'/api/scenes/{scene.id}/memory',json={'expected_revision':revision,'text':snapshot.model_dump_json()})
  assert response.status_code==409
  assert 'Пам’ять' in response.json()['detail'] and 'відкрийте' in response.json()['detail'].lower()
  assert 'memory' not in repo.get_scene(scene.id).heads
