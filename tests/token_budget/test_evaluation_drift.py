import json
from datetime import datetime, timezone
from storygen.domain import StoryCreate, SceneCreate
from storygen.storage.repository import Repository
from storygen.generation.dependencies import save_manual_prose
from storygen.generation.worker import RunCoordinator, RunRequest
from storygen.evaluation import story_adapter
from storygen.evaluation.models import EvaluatorConfig, GatewayResult
from storygen.evaluation.prompting import build_request, load_rubric
from storygen.providers.requests import evaluation_request
from storygen.token_budget.core import measure


def test_next_window_observes_profile_deactivation(tmp_path, monkeypatch):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Вікна'))
    scenes = [repo.create_scene(story.id, SceneCreate(title=str(i))) for i in range(2)]
    for scene in scenes: save_manual_prose(repo, scene.id, 'Текст.', scene.revision)
    config = EvaluatorConfig(provider='local', model='judge', max_input_chars=100000)
    story_adapter.save_evaluation_settings(repo, story.id, story_adapter.EvaluationSettings(config=config, context_tokens=128000))
    cases = [story_adapter.build_evaluation_case(repo, story.id, s.id, 'scene') for s in scenes]
    body = evaluation_request(config, build_request(cases[0], load_rubric(), config))
    identity = measure(config.provider, config.base_url, body)['identity']
    # Trusted pre-existing admitted profile fixture; creation admission is covered separately.
    profile = {'id': 'verified', 'identity': identity, 'eligible': True, 'active': True,
        'created_at': datetime.now(timezone.utc).isoformat(), 'coefficient': 0.1, 'min_bytes': 1, 'max_bytes': 1000000}
    with repo.db.connection() as db:
        db.execute('INSERT INTO app_settings VALUES(?,?)', ('token_profile:' + identity, json.dumps(profile)))
    monkeypatch.setattr(story_adapter, 'plan_evaluation_windows', lambda *_: cases)
    class Gateway:
        def complete(self, request):
            data = json.loads(request.messages[1]['content'])
            report = {'assessments': [{'criterion_id': k, 'status': 'assessed', 'score': 4, 'explanation': 'Перевірено'} for k in data['required_criteria']],
                'findings': [], 'checked_document_ids': [d['id'] for d in data['documents']], 'limitations': []}
            return GatewayResult(text=json.dumps(report), finish_reason='stop', usage={'prompt_tokens': 1000000})
    worker = RunCoordinator(repo, evaluator_factory=lambda _: Gateway())
    run = worker.enqueue(RunRequest(story_id=story.id, mode='evaluate', evaluation_mode='story'), 'drift')
    run.state = 'running'; worker._save(run)
    worker._evaluate(run)
    attempts = repo.list_attempts(story.id, run.id)
    assert [a.context['token_estimate']['method'] for a in attempts] == ['verified_empirical_profile', 'utf8_body_conservative']
    for attempt in attempts:
        outcome = json.loads(repo.read_text(attempt.result_version_id))
        assert outcome['metadata']['token_estimate'] == attempt.context['token_estimate']
