from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import StoryCreate
from storygen.generation.worker import RunRequest
from storygen.run_models import Run
from storygen.storage.repository import Repository
from storygen.web.app import create_app

SHORT = {'id', 'story_id', 'request_id', 'state', 'created_at', 'request', 'impact'}


def add(repo, story_id, request_id, mode, state, **fields):
    run = Run(id='run-' + request_id, story_id=story_id, request_id=request_id,
              request=RunRequest(story_id=story_id, mode=mode), state=state, tasks=[{'stage': 'x'}], **fields)
    repo.enqueue_run(run)
    return repo.save_run(run)


def fixture(tmp_path):
    repo = Repository(tmp_path / 'data')
    story = repo.create_story(StoryCreate(title='Книга'))
    other = repo.create_story(StoryCreate(title='Інша'))
    ids = [
        add(repo, story.id, 'prep', 'prepare', 'completed', planned_telemetry={'calls': 1}).id,
        add(repo, story.id, 'draft', 'publication_suggest', 'completed', warning='w').id,
        add(repo, story.id, 'bad', 'publication_suggest', 'failed', error='Причина', planned_telemetry={'calls': 2}).id,
        add(repo, story.id, 'review', 'impact', 'needs_review',
            impact={'protocol': 3, 'phase': 'awaiting_author', 'scene_order': ['a'], 'proofs': {'k': 1}}).id,
    ]
    add(repo, other.id, 'foreign', 'prepare', 'completed')
    app = create_app(AppSettings(data_dir=tmp_path / 'data', env_file=tmp_path / 'absent.env'))
    return TestClient(app, base_url='http://127.0.0.1'), story, ids


def test_story_runs_returns_short_form(tmp_path):
    client, story, ids = fixture(tmp_path)
    runs = client.get(f'/api/stories/{story.id}/runs').json()['runs']
    assert [r['id'] for r in runs] == ids
    for r in runs:
        assert set(r) == SHORT
        assert r['impact'] is None or set(r['impact']) <= {'protocol', 'phase'}
    assert runs[-1]['impact'] == {'protocol': 3, 'phase': 'awaiting_author'}
    assert [r['impact'] for r in runs[:3]] == [None, None, None]
    assert runs[0]['request']['mode'] == 'prepare' and runs[2]['state'] == 'failed'
    sessions = [r for r in runs if (r['impact'] or {}).get('protocol') == 3]
    assert [r['id'] for r in sessions] == [ids[3]]


def test_run_detail_stays_full(tmp_path):
    client, story, ids = fixture(tmp_path)
    run = client.get(f'/api/runs/{ids[2]}').json()['run']
    assert run['error'] == 'Причина' and 'tasks' in run and run['planned_telemetry'] == {'calls': 2}
    assert client.get(f'/api/runs/{ids[3]}').json()['run']['impact']['proofs'] == {'k': 1}


def test_run_summary_is_a_subset_of_the_full_run(tmp_path):
    client, story, ids = fixture(tmp_path)
    listed = client.get(f'/api/stories/{story.id}/runs').json()['runs']
    for short in listed:
        full = client.get(f"/api/runs/{short['id']}").json()['run']
        assert {k: full[k] for k in short if k != 'impact'} == {k: v for k, v in short.items() if k != 'impact'}
