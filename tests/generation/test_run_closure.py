"""RUN-ACCEPT-CLOSE: a run that only waits for an author decision does not stay open after that decision or after a newer run of the same stage."""
import json

import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import SceneCreate, StageAttempt, new_id
from storygen.generation.worker import RunCoordinator
from storygen.run_models import Run, RunRequest
from storygen.web.app import create_app
from tests.generation.test_copyedit_review import choose, generate
from tests.generation.test_worker import ready
from tests.link_helpers import approve_links

BRIEF = json.dumps({'objective': 'Мета', 'beats': ['Подія'], 'constraints': [], 'proposed_changes': ['Змінити план']}, ensure_ascii=False)


def stopped(repo, story_id, scene_id, tasks, state='needs_review', cursor=0, mode='stage', stage='brief'):
    request = RunRequest(story_id=story_id, scene_id=scene_id, mode=mode, stage=stage if mode == 'stage' else None)
    run = Run(id=new_id(), story_id=story_id, request_id=new_id(), request=request, state=state, cursor=cursor, tasks=tasks)
    repo.enqueue_run(run)
    return run


def waiting_brief(repo, story_id, scene_id, tasks, attempt_state='needs_review'):
    run = stopped(repo, story_id, scene_id, tasks)
    ref = repo.save_version(story_id, scene_id, 'brief', BRIEF, [])
    attempt = StageAttempt(id=new_id(), run_id=run.id, story_id=story_id, scene_id=scene_id, stage='brief', state=attempt_state,
                           context={'run_cursor': 0}, partial_path='partial.txt', result_version_id=ref.id)
    repo.save_attempt(attempt)
    return run, ref, attempt


def client_with_scene(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))
    client = TestClient(app, base_url='http://127.0.0.1:8765')
    client.__enter__()
    story = client.post('/api/stories', json={'title': 'Книга'}).json()
    scene = client.post(f'/api/stories/{story["id"]}/scenes', json={'title': 'Сцена'}).json()
    return client, app.state.repo, story['id'], scene['id']


def test_accepting_the_brief_completes_its_waiting_run(tmp_path):
    client, repo, story_id, scene_id = client_with_scene(tmp_path)
    try:
        run, ref, attempt = waiting_brief(repo, story_id, scene_id, [{'scene_id': scene_id, 'stage': 'brief'}])
        revision = repo.get_scene(scene_id).revision
        accepted = client.post(f'/api/scenes/{scene_id}/accept-brief', json={'version_id': ref.id, 'expected_revision': revision})
        assert accepted.status_code == 200, accepted.text
        closed = repo.get_run(run.id)
        assert closed.state == 'completed' and closed.cursor == 1 and closed.error is None
        events = repo.list_run_events(run.id)
        assert events[-2].type == 'accepted_outside_run' and events[-2].data == {'attempt_id': attempt.id, 'version_id': ref.id}
        assert events[-1].data == {'state': 'completed'}
        # The scene can now go to the trash: nothing is left open.
        trashed = client.post(f'/api/scenes/{scene_id}/trash', json={'story_id': story_id, 'expected_revision': repo.get_scene(scene_id).revision})
        assert trashed.status_code == 200, trashed.text
    finally:
        client.__exit__(None, None, None)


def test_accepting_the_brief_keeps_a_run_with_later_tasks_waiting(tmp_path):
    client, repo, story_id, scene_id = client_with_scene(tmp_path)
    try:
        tasks = [{'scene_id': scene_id, 'stage': 'brief'}, {'scene_id': scene_id, 'stage': 'draft'}]
        run, ref, _ = waiting_brief(repo, story_id, scene_id, tasks)
        revision = repo.get_scene(scene_id).revision
        assert client.post(f'/api/scenes/{scene_id}/accept-brief', json={'version_id': ref.id, 'expected_revision': revision}).status_code == 200
        # Later tasks still need the explicit «continue» decision (continue_after_acceptance).
        assert repo.get_run(run.id).state == 'needs_review' and repo.get_run(run.id).cursor == 0
    finally:
        client.__exit__(None, None, None)


def test_applying_point_edits_completes_a_single_edit_run(tmp_path):
    repo, scene, _, attempt = generate(tmp_path, run_id='edit-run')
    run = repo.get_run('edit-run')
    run.tasks = [{'scene_id': scene.id, 'stage': 'edit'}]
    run.request = RunRequest(story_id=scene.story_id, scene_id=scene.id, mode='stage', stage='edit')
    run.state = 'needs_review'
    repo.save_run(run)
    result = choose(repo, scene, attempt, [0])
    closed = repo.get_run('edit-run')
    assert closed.state == 'completed' and closed.cursor == 1
    assert repo.list_run_events('edit-run')[-2].data['version_id'] == result['version'].id


def test_a_new_run_of_the_same_stage_cancels_the_stopped_one(tmp_path):
    repo, story, scene = ready(tmp_path)
    other = repo.create_scene(story.id, SceneCreate(title='Інша', beats='Вечір'))
    same = stopped(repo, story.id, scene.id, [{'scene_id': scene.id, 'stage': 'brief'}])
    paused_scene = stopped(repo, story.id, scene.id, [{'scene_id': scene.id, 'stage': 'brief'}, {'scene_id': scene.id, 'stage': 'draft'}],
                           state='paused', mode='scene')
    other_stage = stopped(repo, story.id, scene.id, [{'scene_id': scene.id, 'stage': 'draft'}], stage='draft')
    other_scene = stopped(repo, story.id, other.id, [{'scene_id': other.id, 'stage': 'brief'}])
    spanning = stopped(repo, story.id, scene.id, [{'scene_id': scene.id, 'stage': 'brief'}, {'scene_id': other.id, 'stage': 'brief'}],
                       state='paused', mode='remaining')
    worker = RunCoordinator(repo)
    new = worker.enqueue(RunRequest(story_id=story.id, scene_id=scene.id, mode='stage', stage='brief'), 'fresh')
    for superseded in (same, paused_scene):
        assert repo.get_run(superseded.id).state == 'cancelled'
        events = repo.list_run_events(superseded.id)
        assert events[-2].type == 'superseded' and events[-2].data == {'run_id': new.id}
    assert repo.get_run(other_stage.id).state == 'needs_review'
    assert repo.get_run(other_scene.id).state == 'needs_review'
    assert repo.get_run(spanning.id).state == 'paused', 'a run that still has other scenes keeps waiting'
    # Repeating the same request id creates nothing and cancels nothing more.
    assert worker.enqueue(RunRequest(story_id=story.id, scene_id=scene.id, mode='stage', stage='brief'), 'fresh').id == new.id


def test_startup_completes_runs_whose_result_was_already_accepted(tmp_path):
    repo, story, scene = ready(tmp_path)
    accepted, ref, attempt = waiting_brief(repo, story.id, scene.id, [{'scene_id': scene.id, 'stage': 'brief'}], attempt_state='completed')
    waiting, _, _ = waiting_brief(repo, story.id, scene.id, [{'scene_id': scene.id, 'stage': 'brief'}])
    RunCoordinator(repo).recover_interrupted()
    assert repo.get_run(accepted.id).state == 'completed' and repo.get_run(accepted.id).cursor == 1
    assert repo.list_run_events(accepted.id)[-2].data == {'attempt_id': attempt.id, 'version_id': ref.id}
    assert repo.get_run(waiting.id).state == 'needs_review', 'an undecided result keeps waiting for the author'


@pytest.mark.parametrize('mode', ['stage', 'edit_loop'])
def test_a_new_edit_run_cancels_an_editor_loop_waiting_for_its_summary(tmp_path, mode):
    repo, story, scene = ready(tmp_path)
    brief = repo.save_version(story.id, scene.id, 'brief', json.dumps({'objective': 'Мета', 'beats': ['Подія'], 'constraints': [], 'proposed_changes': []}), [])
    repo.set_head(scene.id, 'brief', brief.id, repo.get_scene(scene.id).revision)
    draft = repo.save_version(story.id, scene.id, 'draft', 'Ранок у бібліотеці. ' * 20, [brief.id])
    repo.set_head(scene.id, 'draft', draft.id, repo.get_scene(scene.id).revision)
    approve_links(repo, story.id)
    tasks = [{'scene_id': scene.id, 'stage': 'edit'}] * 2
    loop = stopped(repo, story.id, scene.id, tasks, cursor=len(tasks), mode='edit_loop')  # summary waits past the last pass
    request = RunRequest(story_id=story.id, scene_id=scene.id, mode=mode, stage='edit' if mode == 'stage' else None)
    new = RunCoordinator(repo).enqueue(request, 'edit-' + mode)
    assert repo.get_run(loop.id).state == 'cancelled'
    assert repo.list_run_events(loop.id)[-2].data == {'run_id': new.id}
