"""R-44 PR 1: a new impact check is refused; saved impact runs and their attempts stay readable."""
import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import SceneCreate, StageAttempt, StoryCreate
from storygen.run_models import IMPACT_REMOVED, Run, RunRequest
from storygen.web.app import create_app

STAMP = 'a' * 64


def saved_impact_run(repo, story, scene, state='needs_review'):
    run = Run(id='old-impact', story_id=story.id, request_id='old-impact', state=state,
              request=RunRequest(story_id=story.id, mode='impact', impact_protocol=3, review_contract_version=4,
                                 impact_plan_fingerprint=STAMP),
              tasks=[{'scene_id': scene.id, 'stage': 'review_scene'}], impact={'protocol': 3, 'phase': 'review'})
    repo.enqueue_run(run)
    for stage in ('impact_part', 'review_part'):
        repo.save_attempt(StageAttempt(id=f'{stage}-1', run_id=run.id, story_id=story.id, scene_id=scene.id, stage=stage,
                                       state='completed', context={'review_result': {'x': 1}},
                                       partial_path=f'stories/{story.id}/runs/{stage}-1/partial.txt'))
    return run


@pytest.mark.req('R28-REMOVED')
def test_new_impact_run_is_refused(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))
    story = app.state.repo.create_story(StoryCreate(title='Книга'))
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        response = client.post('/api/runs', json={'request_id': 'new-impact', 'request': {
            'story_id': story.id, 'mode': 'impact', 'impact_protocol': 3, 'review_contract_version': 4,
            'impact_plan_fingerprint': STAMP}})
    assert response.status_code == 400 and IMPACT_REMOVED in response.text
    assert app.state.repo.list_runs(story.id) == []


@pytest.mark.req('R28-REMOVED')
def test_saved_impact_run_and_attempts_stay_readable(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Книга'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена'))
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        run = saved_impact_run(repo, story, scene)  # after start-up recovery, so the run stays needs_review
        listed = client.get(f'/api/stories/{story.id}/runs')
        assert listed.status_code == 200
        assert [(r['id'], r['request']['mode'], r['impact']) for r in listed.json()['runs']] == [
            (run.id, 'impact', {'protocol': 3, 'phase': 'review'})]
        detail = client.get(f'/api/runs/{run.id}')
        assert detail.status_code == 200
        assert [a['stage'] for a in detail.json()['attempts']] == ['impact_part', 'review_part']
        readiness = client.get(f'/api/runs/{run.id}/readiness').json()
        assert readiness['ready'] is False and readiness['reason'] == IMPACT_REMOVED
        resumed = client.post(f'/api/runs/{run.id}/resume', json={'repeat_interrupted': True})
        assert resumed.status_code == 400 and IMPACT_REMOVED in resumed.text
        assert client.post(f'/api/runs/{run.id}/cancel').status_code == 200
        assert client.get(f'/stories/{story.id}').status_code == 200


@pytest.mark.req('R28-REMOVED')
def test_queued_impact_run_from_an_old_session_is_cancelled_not_executed(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Книга'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена'))
    run = saved_impact_run(repo, story, scene, state='queued')
    with TestClient(app, base_url='http://127.0.0.1:8765'):
        saved = repo.get_run(run.id)
    assert (saved.state, saved.error) == ('cancelled', IMPACT_REMOVED)
    with pytest.raises(ValueError, match='Перевірку впливу вилучено'):
        app.state.coordinator._execute(run.id)


@pytest.mark.req('R28-REMOVED')
@pytest.mark.parametrize('state', ['paused', 'needs_review', 'alternative', 'interrupted'])
def test_stopped_impact_run_is_cancelled_on_start_and_blocks_nothing(tmp_path, state):
    app = create_app(AppSettings(data_dir=tmp_path))
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Книга'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена'))
    run = saved_impact_run(repo, story, scene, state=state)
    with TestClient(app, base_url='http://127.0.0.1:8765'):
        saved = repo.get_run(run.id)
        assert (saved.state, saved.error) == ('cancelled', IMPACT_REMOVED)
        assert repo.update_story_language(story.id, 'en', repo.get_story(story.id).revision).language == 'en'
    assert [a.stage for a in repo.list_attempts(story.id, run.id)] == ['impact_part', 'review_part']
