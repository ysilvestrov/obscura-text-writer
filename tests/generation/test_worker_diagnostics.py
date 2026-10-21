import pytest
from storygen.domain import StoryCreate,SceneCreate,StageAttempt
from storygen.storage.repository import Repository
from storygen.generation.worker import RunCoordinator
from storygen.run_models import Run,RunRequest
from storygen.evaluation.story_adapter import EvaluationSettings,save_evaluation_settings
from storygen.evaluation.models import EvaluatorConfig


def setup_run(tmp_path):
    repo=Repository(tmp_path)
    story=repo.create_story(StoryCreate(title='Діагностика'))
    scene=repo.create_scene(story.id,SceneCreate(title='Перша'))
    request=RunRequest(story_id=story.id,scene_id=scene.id,mode='evaluate')
    run=Run(id='run',story_id=story.id,request_id='request',request=request,
        tasks=[{'stage':'evaluate','scene_id':scene.id}],state='running')
    repo.enqueue_run(run)
    return repo,run,scene,RunCoordinator(repo)


@pytest.mark.parametrize('private',[
    'Це приватний вигаданий уривок для перевірки відлуння документа.',
    'Короткий таємний текст',
])
def test_unexpected_evaluator_error_hides_document_text_and_marks_attempt_failed(tmp_path,private):
    repo,run,scene,worker=setup_run(tmp_path)
    attempt=StageAttempt(id='attempt',run_id=run.id,story_id=run.story_id,scene_id=scene.id,
        stage='evaluate',context={'case':{'documents':[{'text':private}]},'run_cursor':0},partial_path='partial.txt')
    repo.save_attempt(attempt)
    message=worker._failure_message(run,ValueError('provider echo: '+private))
    assert private not in message
    assert 'відлуння' in message and 'ValueError' in message
    stored=repo.get_attempt(attempt.id)
    assert stored.state=='failed' and stored.error==message


@pytest.mark.parametrize('prefix',['','x'*490,' '*1990])
def test_diagnostic_hides_both_frozen_and_current_keys(tmp_path,monkeypatch,prefix):
    repo,run,scene,worker=setup_run(tmp_path)
    monkeypatch.setenv('OLD_EVALUATOR_TEST_KEY','old-private-test-credential')
    monkeypatch.setenv('NEW_EVALUATOR_TEST_KEY','new-private-test-credential')
    save_evaluation_settings(repo,run.story_id,EvaluationSettings(config=EvaluatorConfig(
        provider='venice',model='test-model',api_key_env='NEW_EVALUATOR_TEST_KEY',max_input_chars=10000)))
    repo.save_attempt(StageAttempt(id='attempt',run_id=run.id,story_id=run.story_id,scene_id=scene.id,
        stage='evaluate',context={'config':{'provider':'venice','api_key_env':'OLD_EVALUATOR_TEST_KEY'}},partial_path='partial.txt'))
    message=worker._failure_message(run,RuntimeError(prefix+'old-private-test-credential new-private-test-credential'))
    assert 'old-privat' not in message and 'new-privat' not in message
    assert 'RuntimeError' in message


def test_diagnostic_keeps_real_preflight_reason_without_attempt(tmp_path):
    _,run,_,worker=setup_run(tmp_path)
    message=worker._failure_message(run,ValueError('Оцінювачеві бракує контексту'))
    assert 'ValueError' in message and 'бракує контексту' in message
    assert 'повтору немає' in message


def test_non_evaluator_exception_remains_generic(tmp_path):
    _,run,_,worker=setup_run(tmp_path)
    run.tasks[0]['stage']='draft'
    message=worker._failure_message(run,RuntimeError('private prompt fragment'))
    assert 'private prompt fragment' not in message
    assert 'Етап зупинено' in message
