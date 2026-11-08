"""Classification state reads classify attempts through the SQL context_key filter with the same result as a full scan."""
import pytest

from storygen.domain import StageAttempt, StoryCreate, SceneCreate
from storygen.generation.copyedit_review import copyedit_preview
from storygen.generation.edit_classification import identity, readiness
from storygen.run_models import RunRequest
from storygen.storage.repository import Repository
from tests.generation.test_edit_classification import fixture

PROVIDER = {'provider': 'local', 'model': 'x'}


def _attempt(repo, n, story_id, scene_id, context, state='completed', stage='classify'):
    repo.save_attempt(StageAttempt(id=f'c{n:03d}', story_id=story_id, scene_id=scene_id, stage=stage, state=state,
                                   context={'settings': {'provider': {'model': f'm{n}'}}, **context}, partial_path='p.txt',
                                   error=None if state == 'completed' else f'e{n}', usage={'n': n}))


def _seed(repo, scene, a, fingerprint, *, refusal_identity):
    """History of this proposal, another proposal's classifications, refusals with null/false/other identity, another story."""
    other = repo.create_story(StoryCreate(title='Інший'))
    other_scene = repo.create_scene(other.id, SceneCreate(title='Сцена'))
    result = {'changes': [{'index': 0, 'category': 'grammar', 'assessment': 'neutral', 'explanation': 'Т'}]}
    rows = [
        (scene.story_id, scene.id, {'classification_proposal_id': a.id, 'classification_fingerprint': fingerprint,
                                    'classification_result': result}, 'completed', 'classify'),
        (scene.story_id, scene.id, {'classification_proposal_id': a.id, 'classification_fingerprint': fingerprint,
                                    'classification_failure': {'category': 'timeout'}}, 'failed', 'classify'),
        (scene.story_id, scene.id, {'classification_proposal_id': a.id, 'classification_fingerprint': fingerprint,
                                    'classification_result': {}}, 'completed', 'classify'),
        (scene.story_id, scene.id, {'classification_proposal_id': a.id, 'classification_fingerprint': 'stale'}, 'completed', 'classify'),
        (scene.story_id, scene.id, {'classification_proposal_id': 'another', 'classification_fingerprint': fingerprint,
                                    'classification_result': result}, 'completed', 'classify'),
        (scene.story_id, scene.id, {'classification_proposal_id': a.id, 'classification_fingerprint': fingerprint}, 'completed', 'copyedit'),
        (scene.story_id, scene.id, {'classification_proposal_id': None}, 'completed', 'classify'),
        (scene.story_id, scene.id, {'classification_refusal': None, 'classification_identity': refusal_identity}, 'failed', 'classify'),
        (scene.story_id, scene.id, {'classification_refusal': False, 'classification_identity': refusal_identity}, 'failed', 'classify'),
        (scene.story_id, scene.id, {'classification_refusal': True, 'classification_identity': PROVIDER}, 'failed', 'classify'),
        (other.id, other_scene.id, {'classification_refusal': True, 'classification_identity': refusal_identity}, 'failed', 'classify'),
        (other.id, other_scene.id, {'classification_proposal_id': a.id, 'classification_fingerprint': fingerprint,
                                    'classification_result': result}, 'completed', 'classify'),
    ]
    for n, (story_id, scene_id, context, state, stage) in enumerate(rows):
        _attempt(repo, n, story_id, scene_id, context, state, stage)


def _unfiltered(monkeypatch):
    """The pre-change path: every list_attempts call scans all attempts of the story."""
    original = Repository.list_attempts
    monkeypatch.setattr(Repository, 'list_attempts', lambda self, story_id, run_id=None, **kw: original(
        self, story_id, run_id, **{k: v for k, v in kw.items() if k != 'context_key'}))


@pytest.mark.parametrize('refused', [False, True])
def test_preview_and_readiness_match_unfiltered_scan(tmp_path, monkeypatch, refused):
    repo, scene, a = fixture(tmp_path)
    fingerprint = copyedit_preview(repo, scene.id, a.id)['proposal_fingerprint']
    from storygen.authoring.blueprints import get_role_settings
    own = identity(get_role_settings(repo, scene.story_id)['editor'].classification.provider)
    _seed(repo, scene, a, fingerprint, refusal_identity=own)
    if refused:
        _attempt(repo, 99, scene.story_id, scene.id, {'classification_refusal': True, 'classification_identity': own}, 'failed')
    request = RunRequest(story_id=scene.story_id, scene_id=scene.id, mode='classify', proposal_attempt_id=a.id,
                         proposal_fingerprint=fingerprint)
    fast = (copyedit_preview(repo, scene.id, a.id), readiness(repo, request))
    # Non-trivial branches: three history rows of this proposal and fingerprint, the last completed non-empty result (c000) wins.
    assert [h['attempt_id'] for h in fast[0]['classification_history']] == ['c000', 'c001', 'c002']
    assert fast[0]['classification']['changes'][0]['category'] == 'grammar'
    assert fast[0]['can_classify'] is (not refused) and fast[1]['ready'] is (not refused)
    _unfiltered(monkeypatch)
    assert (copyedit_preview(repo, scene.id, a.id), readiness(repo, request)) == fast


def test_classification_reads_attempts_through_sql_filter(tmp_path, monkeypatch):
    repo, scene, a = fixture(tmp_path)
    fingerprint = copyedit_preview(repo, scene.id, a.id)['proposal_fingerprint']
    calls = []
    original = Repository.list_attempts

    def spy(self, story_id, run_id=None, **kw):
        calls.append((run_id, kw))
        return original(self, story_id, run_id, **kw)
    monkeypatch.setattr(Repository, 'list_attempts', spy)
    copyedit_preview(repo, scene.id, a.id)
    readiness(repo, RunRequest(story_id=scene.story_id, scene_id=scene.id, mode='classify', proposal_attempt_id=a.id,
                               proposal_fingerprint=fingerprint))
    assert calls == [(None, {'context_key': 'classification_proposal_id'}), (None, {'context_key': 'classification_refusal'}),
                     (None, {'context_key': 'classification_refusal'})]


def test_classification_keys_filter_like_python(tmp_path):
    repo, scene, a = fixture(tmp_path)
    variants = [True, False, None, '', 'x', 0, 'missing']
    n = 0
    for key in ['classification_proposal_id', 'classification_refusal']:
        for value in variants:
            _attempt(repo, n, scene.story_id, scene.id, {} if value == 'missing' else {key: value})
            n += 1
    full = repo.list_attempts(scene.story_id)
    for key in ['classification_proposal_id', 'classification_refusal']:
        expected = [x.id for x in full if x.context.get(key) is not None]
        assert [x.id for x in repo.list_attempts(scene.story_id, context_key=key)] == expected
        assert len(expected) == len(variants) - 2
