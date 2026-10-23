import pytest
from storygen.storage.repository import Repository
from storygen.token_budget.service import record_usage, token_estimate, build, activate
from storygen.token_budget.core import measure


def request(text='Проза'):
    return {'model': 'm', 'messages': [{'role': 'user', 'content': text}], 'max_tokens': 30}


def test_usage_missing_dedup_and_revision_free(tmp_path):
    repo = Repository(tmp_path)
    assert record_usage(repo, 'local', 'http://localhost:1235/v1', request(), {}, 'a') is None
    record_usage(repo, 'local', 'http://localhost:1235/v1', request(), {'prompt_tokens': 9}, 'a')
    record_usage(repo, 'local', 'http://localhost:1235/v1', request(), {'prompt_tokens': 9}, 'a')
    assert len(repo.token_records('observation')) == 1
    item = measure('local', 'http://localhost:1235/v1', request())
    assert not build(repo, item['identity'])['eligible']
    with pytest.raises(ValueError): activate(repo, item['identity'])
    assert token_estimate(repo, 'local', 'http://localhost:1235/v1', request())['confidence'] == 'heuristic'


def test_manual_activation_reopen_and_drift(tmp_path):
    repo = Repository(tmp_path)
    texts = [('Слово ' * (i * 20 + 1)) if i % 3 == 0 else ('english ' * (i * 20 + 1)) if i % 3 == 1
        else '{"text":"' + ('value ' * (i * 20 + 1)) + '"}' for i in range(90)]
    for i, text in enumerate(texts):
        record_usage(repo, 'local', 'http://localhost:1235/v1', request(text), {'prompt_tokens': 100 + i * 30}, str(i))
    identity = measure('local', 'http://localhost:1235/v1', request())['identity']
    profile = build(repo, identity)
    assert profile['eligible'] and not profile['active']
    assert token_estimate(repo, 'local', 'http://localhost:1235/v1', request(texts[45]))['confidence'] == 'heuristic'
    activate(repo, identity)
    reopened = Repository(tmp_path)
    assert token_estimate(reopened, 'local', 'http://localhost:1235/v1', request(texts[45]))['confidence'] == 'empirical_holdout'
    record_usage(repo, 'local', 'http://localhost:1235/v1', request(texts[45]), {'prompt_tokens': 10**8}, 'drift')
    assert not reopened.token_records('profile')[0]['active']
    assert token_estimate(reopened, 'local', 'http://localhost:1235/v1', request(texts[45]))['confidence'] == 'heuristic'


def test_telemetry_storage_failure_preserves_finished_prose(tmp_path, monkeypatch):
    import threading
    from storygen.domain import StoryCreate, SceneCreate
    from storygen.providers.models import RoleSettings, ProviderSettings
    from storygen.generation.context import make_context
    from storygen.generation.stages import execute_stage
    from storygen.providers.streaming import GenerationEvent
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Тест'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена'))
    role = RoleSettings(provider=ProviderSettings(model='test'))
    context = make_context(repo, story, scene, 'draft', role, ['Текст'], [])
    class Gateway:
        def stream(self, *_):
            yield GenerationEvent(type='delta', text='Завершена проза.')
            yield GenerationEvent(type='terminal', finish_reason='stop', usage={'prompt_tokens': 20})
    def broken(*_): raise OSError('telemetry storage unavailable')
    monkeypatch.setattr(repo, 'record_token_observation', broken)
    attempt = execute_stage(repo, scene.id, 'draft', context, Gateway(), threading.Event(), lambda *_: None)
    assert attempt.state == 'completed'
    assert repo.read_text(attempt.result_version_id) == 'Завершена проза.'
    assert 'token_observation_warning' in attempt.context
