"""MEMORY-CARRY: only the internal enqueue (storage/carry_queue.py) creates a carry run; the public runs API refuses it."""
import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import SceneCreate, StoryCreate
from storygen.web.app import create_app


@pytest.mark.req('VALID-MEMORY')
def test_public_runs_api_refuses_memory_carry(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Книга'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена'))
    body = {'request_id': 'forged-carry', 'request': {'story_id': story.id, 'scene_id': scene.id, 'mode': 'memory_carry'}}
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        for path in ('/api/runs', '/api/runs/cancel-request'):
            response = client.post(path, json=body)
            assert response.status_code == 422, (path, response.text)
            assert 'Перенос пам’яті' in response.json()['detail']
    assert repo.list_runs(story.id) == []


@pytest.mark.req('VALID-MEMORY')
def test_mcp_start_run_cannot_name_the_carry():
    from storygen.mcp.bridge import RUN_ACTIONS
    assert 'memory_carry' not in RUN_ACTIONS
