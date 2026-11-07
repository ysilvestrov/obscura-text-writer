import json

from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import SceneCreate, StageAttempt, StoryCreate, new_id
from storygen.run_models import Run, RunRequest
from storygen.web.app import create_app

PAYLOAD = {'items': [{'operation': 'facts.add, елемент 1', 'code': 'evidence_unknown'},
                     {'operation': 'Операція 2', 'code': 'add_limit'},
                     {'operation': 'Відповідь', 'code': 'target_unknown'}], 'total': 3}


def _run_with_context(repo, context):
    story = repo.create_story(StoryCreate(title='Порушення'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена'))
    run = Run(id=new_id(), story_id=story.id, request_id=new_id(),
              request=RunRequest(story_id=story.id, scene_id=scene.id, mode='stage',stage='memory'),
              state='failed', tasks=[{'scene_id': scene.id, 'stage': 'memory'}])
    repo.enqueue_run(run)
    repo.save_attempt(StageAttempt(id=new_id(), run_id=run.id, story_id=story.id, scene_id=scene.id, stage='memory',
                                   state='failed', context=context, partial_path='partial.txt'))
    return run.id


def test_run_details_expose_memory_violations_without_context(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        run_id = _run_with_context(app.state.repo, {
            'fragments': 'СЕКРЕТНИЙ ТЕКСТ', 'memory_violations': PAYLOAD, 'memory_warnings': ['Попередження']})
        attempt = client.get(f'/api/runs/{run_id}').json()['attempts'][-1]
        assert attempt['memory_violations']['total'] == 3
        assert {i['code'] for i in attempt['memory_violations']['items']} == {'evidence_unknown', 'add_limit', 'target_unknown'}
        assert attempt['memory_warnings'] == ['Попередження']
        assert 'context' not in attempt and 'СЕКРЕТНИЙ' not in json.dumps(attempt, ensure_ascii=False)


def test_run_details_without_violations_have_no_key(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        run_id = _run_with_context(app.state.repo, {'x': 1})
        attempt = client.get(f'/api/runs/{run_id}').json()['attempts'][-1]
        assert 'memory_violations' not in attempt and 'memory_warnings' not in attempt


def test_run_details_ignore_wrongly_typed_diagnostics(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        run_id = _run_with_context(app.state.repo, {'memory_violations': ['x'], 'memory_warnings': 'x'})
        attempt = client.get(f'/api/runs/{run_id}').json()['attempts'][-1]
        assert 'memory_violations' not in attempt and 'memory_warnings' not in attempt
