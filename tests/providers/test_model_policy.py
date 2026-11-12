from types import SimpleNamespace

import pytest

from storygen.domain import ContentRating, SceneCreate, StoryCreate
from storygen.providers.models import ProviderSettings
from storygen.providers.policy import (ModelPolicyBlocked, blocking_refusal, check_consent, context_rating, is_local,
    needs_consent, record_refusal, request_rating)
from storygen.storage.repository import Repository


@pytest.fixture
def repo(tmp_path):
    return Repository(tmp_path)


@pytest.mark.req('MODEL-003')
def test_cloud_model_without_uncensored_needs_consent_only_above_zero():
    s = ProviderSettings(provider='openrouter', model='x/y')
    assert needs_consent(s, None, (0, 1, 0)) is True
    assert needs_consent(s, None, (0, 0, 0)) is False
    assert needs_consent(ProviderSettings(provider='venice', model='v'), True, (2, 2, 2)) is False


@pytest.mark.req('MODEL-003')
def test_local_model_never_needs_consent():  # MODEL-003-S04
    assert is_local(ProviderSettings(provider='local', model='m')) is True
    assert needs_consent(ProviderSettings(provider='local', model='m'), None, (2, 2, 2)) is False


@pytest.mark.req('MODEL-003')
def test_consent_is_keyed_by_role_endpoint_and_exact_model(repo):  # MODEL-003-S03, S04
    s = ProviderSettings(provider='openrouter', model='x/y')
    repo.model_policy('set_consent', role='writer', provider='openrouter', base_url=s.base_url, model='x/y')
    check_consent(repo, 'writer', s, (2, 0, 0), None)
    with pytest.raises(ModelPolicyBlocked) as e:
        check_consent(repo, 'editor', s, (2, 0, 0), None)
    assert e.value.kind == 'consent'
    with pytest.raises(ModelPolicyBlocked):
        check_consent(repo, 'writer', ProviderSettings(provider='openrouter', model='x/z'), (2, 0, 0), None)
    assert repo.model_policy('get_consent', role='writer', provider='openrouter', base_url='https://other.example/v1', model='x/y') is None
    assert repo.model_policy('get_consent', role='writer', provider='openrouter', base_url='HTTPS://OpenRouter.AI/api/v1/', model='x/y') is not None
    repo.model_policy('delete_consent', role='writer', provider='openrouter', base_url=s.base_url, model='x/y')
    with pytest.raises(ModelPolicyBlocked):
        check_consent(repo, 'writer', s, (2, 0, 0), None)


@pytest.mark.req('MODEL-004')
def test_refusal_vectors_block_per_axis():  # MODEL-004-S02
    refusals = [{'rating': [2, 0, 0]}, {'rating': [0, 2, 0]}]
    assert blocking_refusal(refusals, (1, 1, 0)) is None
    assert blocking_refusal(refusals, (2, 1, 0)) is not None
    assert blocking_refusal(refusals, (0, 2, 2)) is not None
    assert blocking_refusal([{'rating': [0, 0, 0]}], (0, 0, 0)) is not None


@pytest.mark.req('MODEL-004')
def test_new_refusal_keeps_the_set_minimal(repo):
    s = ProviderSettings(provider='openrouter', model='x/y')
    for r in [(2, 2, 0), (2, 0, 0), (2, 1, 0)]:
        record_refusal(repo, 'writer', s, r, story_id='s', scene_id=None, attempt_id=None, category='refusal_content')
    stored = repo.model_policy('get_refusal', role='writer', provider='openrouter', base_url=s.base_url, model='x/y')
    assert [e['rating'] for e in stored['refusals']] == [[2, 0, 0]]
    repo.model_policy('delete_refusal', role='writer', provider='openrouter', base_url=s.base_url, model='x/y')
    assert repo.model_policy('get_refusal', role='writer', provider='openrouter', base_url=s.base_url, model='x/y') is None


@pytest.fixture
def repo_with_story(repo):
    story = repo.create_story(StoryCreate(title='T'))
    a = repo.create_scene(story.id, SceneCreate(title='A'))
    b = repo.create_scene(story.id, SceneCreate(title='B'))
    repo.update_scene_rating(a.id, ContentRating(sexual=2, violence=0, themes=0), repo.get_scene(a.id).revision)
    return repo, repo.get_story(story.id), a, b


@pytest.mark.req('MODEL-003')
def test_unset_story_rating_counts_as_zero(repo_with_story):  # MODEL-003-S05
    repo, story, a, b = repo_with_story
    view = repo
    assert request_rating(view, story, [a.id]) == (2, 0, 0)
    assert request_rating(view, story, [b.id]) == (0, 0, 0)
    assert request_rating(view, story, []) == (0, 0, 0)
    assert request_rating(view, story, ['missing']) == (0, 0, 0)
    ctx = SimpleNamespace(story_id=story.id, scene_id=b.id, input_refs=['unknown-version'])
    assert context_rating(repo, ctx) == (0, 0, 0)
    assert context_rating(repo, SimpleNamespace(story_id=story.id, scene_id=a.id, input_refs=[])) == (2, 0, 0)
