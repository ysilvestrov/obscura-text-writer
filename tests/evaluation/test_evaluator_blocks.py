import json

import pytest

from storygen.domain import StoryCreate, SceneCreate
from storygen.storage.repository import Repository
from storygen.generation.dependencies import save_manual_prose
from storygen.generation.worker import RunCoordinator, RunRequest
from storygen.evaluation.gateway import GatewayFailure
from storygen.evaluation.models import EvaluatorConfig, GatewayResult
from storygen.evaluation.story_adapter import EvaluationSettings, save_evaluation_settings, build_evaluation_case


def prepared(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Без повторних відмов'))
    scenes = []
    for number in range(2):
        scene = repo.create_scene(story.id, SceneCreate(title=str(number), beats='Ранок'))
        save_manual_prose(repo, scene.id, 'Доросла фотографка приготувала бібліотеку.', scene.revision)
        scenes.append(scene)
    settings = EvaluationSettings(config=EvaluatorConfig(provider='local', model='judge', max_input_chars=100000), context_tokens=128000)
    save_evaluation_settings(repo, story.id, settings)
    return repo, story, scenes, settings


def run_now(worker, run):
    run.state = 'running'
    worker._save(run)
    worker._execute(run.id)
    return worker.get_run(run.id)


@pytest.mark.parametrize('refusal', ['Не можу оцінити цей контент.', 'Не можу оцінити.'])
def test_refusal_blocks_later_windows_queued_runs_and_restart(tmp_path, monkeypatch, refusal):
    repo, story, scenes, settings = prepared(tmp_path)
    cases = [build_evaluation_case(repo, story.id, s.id, 'scene') for s in scenes]
    monkeypatch.setattr('storygen.evaluation.story_adapter.plan_evaluation_windows', lambda *a: cases)
    calls = []
    class Gateway:
        def complete(self, request):
            calls.append(request)
            return GatewayResult(text='', refusal=refusal, finish_reason='stop')
    worker = RunCoordinator(repo, evaluator_factory=lambda _: Gateway())
    first = worker.enqueue(RunRequest(story_id=story.id, mode='evaluate', evaluation_mode='story'), 'first')
    queued = worker.enqueue(RunRequest(story_id=story.id, scene_id=scenes[1].id, mode='evaluate'), 'already-queued')
    assert run_now(worker, first).state == 'completed'
    assert len(calls) == 1
    assert worker.enqueue(first.request, 'first').id == first.id
    assert run_now(worker, queued).state == 'completed'
    assert any(e.type == 'evaluation_skipped' for e in worker.list_events(queued.id))
    from storygen.evaluation.blocks import get_block
    assert get_block(repo, story.id, settings.config)['failure']['category'].startswith('refusal_')
    reopened = RunCoordinator(Repository(tmp_path), evaluator_factory=lambda _: pytest.fail('blocked factory called'))
    settings.config.temperature = .2
    save_evaluation_settings(repo, story.id, settings)
    with pytest.raises(ValueError, match='заблоковано'):
        reopened.enqueue(RunRequest(story_id=story.id, scene_id=scenes[0].id, mode='evaluate'), 'restart')
    with pytest.raises(ValueError):  # Completed runs cannot resume at all.
        reopened.resume(first.id, repeat_interrupted=True)
    assert len(calls) == 1


def test_technical_error_does_not_block_and_report_checks_next_window(tmp_path, monkeypatch):
    repo, story, scenes, settings = prepared(tmp_path)
    monkeypatch.setattr('storygen.evaluation.story_adapter.plan_evaluation_windows', lambda *a: [build_evaluation_case(repo, story.id, s.id, 'scene') for s in scenes])
    calls = []
    class Gateway:
        def complete(self, request):
            calls.append(request)
            raise GatewayFailure('timeout: оцінювач не відповів')
    worker = RunCoordinator(repo, evaluator_factory=lambda _: Gateway())
    run = worker.enqueue(RunRequest(story_id=story.id, mode='evaluate', evaluation_mode='story'), 'technical')
    completed = run_now(worker, run)
    assert completed.state == 'completed'
    assert completed.warning
    assert len(calls) == 2
    from storygen.evaluation.blocks import get_block
    assert get_block(repo, story.id, settings.config) is None
    assert len(repo.list_versions(story.id, kind='evaluation')) == 2


def test_block_does_not_follow_other_model_or_other_story(tmp_path):
    repo, story, scenes, settings = prepared(tmp_path)
    from storygen.evaluation.blocks import get_block, block_evaluator
    from storygen.evaluation.models import FailureDetail
    block_evaluator(repo, story.id, settings.config, FailureDetail(category='refusal_unknown', message='Невідома причина'), 'run', 'attempt')
    assert get_block(repo, story.id, settings.config)
    assert get_block(repo, story.id, settings.config.model_copy(update={'base_url': 'http://127.0.0.1:1235/v1/'}))

    assert get_block(repo, story.id, settings.config.model_copy(update={'model': 'another-judge'})) is None
    other = repo.create_story(StoryCreate(title='Інший твір'))
    assert get_block(repo, other.id, settings.config) is None
    settings.policy = 'off'
    save_evaluation_settings(repo, story.id, settings)
    settings.policy = 'report'
    save_evaluation_settings(repo, story.id, settings)
    assert get_block(repo, story.id, settings.config)


def test_refusal_block_survives_report_write_failure(tmp_path, monkeypatch):
    repo, story, scenes, settings = prepared(tmp_path)
    class Gateway:
        def complete(self, request):
            return GatewayResult(text='', refusal='Не можу оцінити.', finish_reason='stop')
    worker = RunCoordinator(repo, evaluator_factory=lambda _: Gateway())
    run = worker.enqueue(RunRequest(story_id=story.id, scene_id=scenes[0].id, mode='evaluate'), 'disk-error')
    def fail_report(*args):
        raise OSError('disk full')
    monkeypatch.setattr('storygen.evaluation.runner.write_reports', fail_report)
    with pytest.raises(OSError):
        run_now(worker, run)
    from storygen.evaluation.blocks import get_block
    assert get_block(Repository(tmp_path), story.id, settings.config)


def test_pause_policy_blocks_resume_until_model_changed_or_off(tmp_path):
    from storygen.evaluation.models import ScoringProfile
    from storygen.evaluation.runner import evaluator_fingerprint
    from storygen.evaluation.prompting import load_rubric
    repo, story, scenes, settings = prepared(tmp_path)
    settings.profile = ScoringProfile(version='fixture', calibrated=True, calibration_fingerprint='fixture-registration',
        evaluator_fingerprint=evaluator_fingerprint(settings.config, load_rubric()))
    with repo.db.connection() as db:
        db.execute('INSERT INTO app_settings VALUES(?,?)', ('calibration:fixture-registration', json.dumps({'profile': settings.profile.model_dump()})))
    settings.policy = 'pause_on_failure'
    save_evaluation_settings(repo, story.id, settings)
    calls = []
    class Gateway:
        def complete(self, request):
            calls.append(request)
            return GatewayResult(text='', refusal='Не можу оцінити.', finish_reason='stop')
    worker = RunCoordinator(repo, evaluator_factory=lambda _: Gateway())
    run = worker.enqueue(RunRequest(story_id=story.id, scene_id=scenes[0].id, mode='evaluate'), 'pause-refusal')
    paused = run_now(worker, run)
    assert paused.state == 'paused' and paused.cursor == 0
    with pytest.raises(ValueError, match='заблоковано'):
        worker.resume(run.id, repeat_interrupted=True)
    settings.policy = 'off'
    save_evaluation_settings(repo, story.id, settings)
    resumed = worker.resume(run.id)
    assert run_now(worker, resumed).state == 'completed'
    assert len(calls) == 1


def test_changed_config_cannot_keep_registered_calibration_and_can_turn_off(tmp_path):
    from storygen.evaluation.models import ScoringProfile
    from storygen.evaluation.runner import evaluator_fingerprint
    from storygen.evaluation.prompting import load_rubric
    from storygen.evaluation.story_adapter import get_evaluation_settings
    repo, story, scenes, settings = prepared(tmp_path)
    settings.profile = ScoringProfile(version='fixture', calibrated=True, calibration_fingerprint='registered',
        evaluator_fingerprint=evaluator_fingerprint(settings.config, load_rubric()))
    with repo.db.connection() as db:
        db.execute('INSERT INTO app_settings VALUES(?,?)', ('calibration:registered', json.dumps({'profile': settings.profile.model_dump()})))
    save_evaluation_settings(repo, story.id, settings)
    settings.config.temperature = .4
    save_evaluation_settings(repo, story.id, settings)
    loaded = get_evaluation_settings(repo, story.id)
    assert loaded.profile.calibrated is False
    loaded.policy = 'off'
    save_evaluation_settings(repo, story.id, loaded)
    assert get_evaluation_settings(repo, story.id).policy == 'off'


@pytest.mark.parametrize('kind', ['api', 'text', 'structured'])
def test_refusal_is_blocked_before_partial_write(tmp_path, monkeypatch, kind):
    repo, story, scenes, settings = prepared(tmp_path)
    class Gateway:
        def complete(self, request):
            # The initial empty partial already exists; simulate failure writing the response.
            original = repo.files.write
            def fail_response(path, content):
                if path.endswith('partial.txt') and content:
                    raise OSError('partial storage failed')
                return original(path, content)
            monkeypatch.setattr(repo.files, 'write', fail_response)
            if kind == 'api':
                return GatewayResult(text='', refusal='Не можу оцінити.', finish_reason='stop')
            text = 'Не можу оцінити цей контент.' if kind == 'text' else json.dumps({'refusal': 'Не оцінюю оголеність.', 'assessments': [], 'findings': [], 'checked_document_ids': [], 'limitations': []})
            return GatewayResult(text=text, finish_reason='stop')
    worker = RunCoordinator(repo, evaluator_factory=lambda _: Gateway())
    run = worker.enqueue(RunRequest(story_id=story.id, scene_id=scenes[0].id, mode='evaluate'), 'partial-error')
    with pytest.raises(OSError):
        run_now(worker, run)
    from storygen.evaluation.blocks import get_block
    assert get_block(Repository(tmp_path), story.id, settings.config)


def test_codex_block_ignores_inactive_endpoint(tmp_path):
    from storygen.evaluation.blocks import block_evaluator, get_block
    from storygen.evaluation.models import FailureDetail
    repo, story, scenes, settings = prepared(tmp_path)
    config = EvaluatorConfig(provider='codex_cli', model='judge', max_input_chars=30000)
    block_evaluator(repo, story.id, config, FailureDetail(category='refusal_unknown', message='Невідомо'), 'run', 'attempt')
    assert get_block(repo, story.id, config.model_copy(update={'base_url': 'https://unused.example/v1'}))
