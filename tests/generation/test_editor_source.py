import pytest
from pydantic import ValidationError

from storygen.run_models import RunRequest
from storygen.generation.editor_loop import source
from tests.generation.test_editor_loop import seeded


def explicit(tmp_path, head='draft'):
    repo, scene, draft, worker, old, calls = seeded(tmp_path, ['{"edits":[]}'])
    prose = repo.save_version(scene.story_id, scene.id, 'manual', 'Поточна проза.', [])
    repo.set_head(scene.id, 'prose', prose.id, repo.get_scene(scene.id).revision)
    old.state = 'cancelled'
    repo.save_run(old)
    ref = draft if head == 'draft' else prose
    request = RunRequest(story_id=scene.story_id, scene_id=scene.id, mode='edit_loop',
                         editor_source_head=head, editor_source_version_id=ref.id)
    return repo, scene, draft, prose, worker, request, calls


@pytest.mark.parametrize('head', ['draft', 'prose'])
def test_explicit_editor_source_is_used_when_both_materials_exist(tmp_path, head):
    repo, scene, draft, prose, worker, request, calls = explicit(tmp_path, head)
    run = worker.enqueue(request, 'explicit')
    worker._execute(run.id)
    current = worker.get_run(run.id)
    expected = draft if head == 'draft' else prose
    assert current.editor_loop['source_version_id'] == expected.id
    assert len(calls) == 1 and repo.read_text(expected.id) in calls[0].user_text


def test_changed_source_after_enqueue_never_switches_or_calls_model(tmp_path):
    repo, scene, _, _, worker, request, calls = explicit(tmp_path)
    run = worker.enqueue(request, 'explicit')
    other = repo.save_version(scene.story_id, scene.id, 'draft', 'Інша чернетка.', [])
    repo.set_head(scene.id, 'draft', other.id, repo.get_scene(scene.id).revision)
    worker._execute(run.id)
    assert not calls
    assert worker.get_run(run.id).state == 'failed'


def test_explicit_source_rejects_wrong_head_or_scene(tmp_path):
    repo, scene, _, prose, worker, request, calls = explicit(tmp_path)
    request.editor_source_version_id = prose.id
    with pytest.raises(ValueError):
        worker.enqueue(request, 'wrong')
    assert not calls


@pytest.mark.parametrize('fields', [
    dict(editor_source_head='draft'), dict(editor_source_version_id='v'),
    dict(editor_source_head='plan', editor_source_version_id='v'),
    dict(mode='scene', editor_source_head='draft', editor_source_version_id='v'),
])
def test_explicit_source_contract_rejects_invalid_pairs_or_modes(fields):
    with pytest.raises(ValidationError):
        RunRequest(**dict(story_id='s', scene_id='c', mode='edit_loop') | fields)


def test_source_readiness_reports_captured_version(tmp_path):
    repo, scene, draft, _, worker, request, _ = explicit(tmp_path)
    result = worker.readiness(scene.story_id, scene.id, 'draft', draft.id)['operations']['edit_loop']
    assert result['ready'] and result['editor_source_version_id'] == draft.id
    assert source(repo, scene.id)[1].id == repo.get_scene(scene.id).heads['prose']


def test_statistics_uses_the_same_explicit_source_as_enqueue(tmp_path):
    from storygen.application.statistics import scene_statistics
    repo, scene, draft, prose, worker, request, calls = explicit(tmp_path)
    stats=scene_statistics(repo,scene.id,'edit','draft',draft.id)
    assert stats['context']['available']
    assert stats['context']['editor_source_version_id']==draft.id
    assert scene_statistics(repo,scene.id,'edit','prose',prose.id)['context']['editor_source_version_id']==prose.id
    assert not calls


def test_incomplete_explicit_source_is_not_enqueued(tmp_path):
    repo, scene, draft, _, worker, request, calls = explicit(tmp_path)
    with repo.db.connection() as db:
        draft.complete=False
        db.execute('UPDATE versions SET payload=? WHERE id=?',(draft.model_dump_json(),draft.id))
    with pytest.raises(ValueError):worker.enqueue(request,'incomplete')
    assert not calls
