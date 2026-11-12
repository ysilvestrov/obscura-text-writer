"""MODEL-003/MODEL-004: execute_stage is the single consent check and refusal record point."""
import json
import threading

import pytest

from storygen.authoring.blueprints import save_role_settings
from storygen.domain import ContentRating, ExternalOrigin, SceneCreate, StoryCreate
from storygen.generation.context import build_context
from storygen.generation.stages import execute_stage
from storygen.memory.journal import MemoryJournal
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.providers.policy import ModelPolicyBlocked, endpoint
from storygen.providers.streaming import GenerationEvent
from storygen.storage.repository import Repository

BRIEF = '{"objective":"Подія","beats":["Подія"]}'
ADULTS = {'schema_version': 2, 'id': 'A', 'name': 'Анна', 'entries': [{'id': 'A0', 'text': 'Вік: 30',
    'availability': 'timeless', 'available_from_scene_id': None, 'origin': 'author', 'sources': []}]}


def R(s, v, t):
    return ContentRating(sexual=s, violence=v, themes=t)


class FakeGateway:
    def __init__(self, text='Чернетка сцени.', finish_reason='stop', type='terminal', refusal=False):
        self.text, self.finish_reason, self.type, self.refusal = text, finish_reason, type, refusal
        self.calls = []

    def stream(self, context, cancel):
        self.calls.append(context)
        if self.text:
            yield GenerationEvent(type='delta', text=self.text)
        yield GenerationEvent(type=self.type, finish_reason=self.finish_reason, refusal=self.refusal,
            message='Модель відмовилася' if self.type == 'error' else '')


def noop(_):
    pass


def setup(tmp_path, story_rating=R(0, 0, 0), scene_ratings=(None,), model='x/y'):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Нейтральний твір'))
    cards = repo.save_version(story.id, None, 'character_cards', json.dumps([ADULTS], ensure_ascii=False), [])
    repo.publish_story_material(story.id, 'characters_version_id', cards.id, repo.get_story(story.id).revision)
    repo.update_story_rating(story.id, story_rating, repo.get_story(story.id).revision)
    scenes = []
    for index, rating in enumerate(scene_ratings):
        scene = repo.create_scene(story.id, SceneCreate(title=f'Сцена {index + 1}', beats='Прогулянка', character_ids=['A']))
        if rating is not None:
            repo.update_scene_rating(scene.id, rating, repo.get_scene(scene.id).revision)
        ref = repo.save_version(story.id, scene.id, 'brief', BRIEF, [])
        repo.set_head(scene.id, 'brief', ref.id, repo.get_scene(scene.id).revision)
        scenes.append(repo.get_scene(scene.id))
    role = writer_role(model)
    save_role_settings(repo, story.id, 'writer', role, repo.get_story(story.id).revision)
    return repo, scenes


def writer_role(model='x/y'):
    return RoleSettings(provider=ProviderSettings(provider='openrouter', model=model))


def draft(repo, scene, gateway, model='x/y'):
    context = build_context(repo, scene.id, 'draft', writer_role(model))
    return execute_stage(repo, scene.id, 'draft', context, gateway, threading.Event(), noop)


def consent(repo, role='writer', model='x/y'):
    s = ProviderSettings(provider='openrouter', model=model)
    repo.model_policy('set_consent', role=role, provider='openrouter', base_url=endpoint(s), model=model)


def refusal(repo, role='writer', model='x/y'):
    s = ProviderSettings(provider='openrouter', model=model)
    return repo.model_policy('get_refusal', role=role, provider='openrouter', base_url=endpoint(s), model=model)


@pytest.mark.req('MODEL-003')
def test_draft_without_consent_is_blocked_with_author_text(tmp_path):  # MODEL-003-S02
    repo, [scene] = setup(tmp_path, R(1, 0, 0))
    gateway = FakeGateway()
    with pytest.raises(ModelPolicyBlocked) as e:
        draft(repo, scene, gateway)
    assert 'не має позначки Uncensored' in str(e.value) and '1/0/0' in str(e.value)
    assert e.value.kind == 'consent'
    assert gateway.calls == []
    assert repo.list_attempts(scene.story_id) == []  # Blocked before an attempt exists.


@pytest.mark.req('MODEL-003')
def test_consent_lets_any_story_through_and_model_change_resets_it(tmp_path):  # MODEL-003-S03
    repo, [scene] = setup(tmp_path, R(2, 2, 2))
    consent(repo)
    gateway = FakeGateway()
    attempt = draft(repo, scene, gateway)
    assert attempt.state == 'completed'
    sent = gateway.calls[0]
    assert sent.policy_role == 'writer' and tuple(sent.policy_rating) == (2, 2, 2)
    with pytest.raises(ModelPolicyBlocked):
        draft(repo, repo.get_scene(scene.id), FakeGateway(), model='x/z')


def accept_scene(repo, scene, prose_ids):
    """Selected prose and memory for a finished scene, so the next scene's real draft context can be built."""
    prose = repo.save_version(scene.story_id, scene.id, 'manual', f'Проза сцени {scene.title}.', [])
    repo.set_head(scene.id, 'prose', prose.id, repo.get_scene(scene.id).revision)
    prose_ids.append(prose.id)
    journal = MemoryJournal(schema_version=3, source_prose_ids=list(prose_ids), events=[])
    memory = repo.save_version(scene.story_id, scene.id, 'memory', journal.model_dump_json(), [prose.id])
    repo.set_head(scene.id, 'memory', memory.id, repo.get_scene(scene.id).revision)


@pytest.mark.req('MODEL-003')
def test_scene_rated_above_zero_story_needs_consent_only_for_that_scene(tmp_path):  # MODEL-003-S05
    repo, [first, rated, third] = setup(tmp_path, R(0, 0, 0), (None, R(2, 0, 0), None))
    prose_ids = []
    assert draft(repo, first, FakeGateway()).state == 'completed'
    accept_scene(repo, repo.get_scene(first.id), prose_ids)
    gateway = FakeGateway()
    with pytest.raises(ModelPolicyBlocked) as e:
        draft(repo, repo.get_scene(rated.id), gateway)
    assert '2/0/0' in str(e.value) and gateway.calls == []
    accept_scene(repo, repo.get_scene(rated.id), prose_ids)  # The author wrote the rated scene by hand.
    context = build_context(repo, third.id, 'draft', writer_role())
    assert rated.id in {repo.get_version(ref).scene_id for ref in context.input_refs}  # Its prose is memory input.
    gateway = FakeGateway()
    assert execute_stage(repo, third.id, 'draft', context, gateway, threading.Event(), noop).state == 'completed'
    assert tuple(gateway.calls[0].policy_rating) == (0, 0, 0)


@pytest.mark.req('MODEL-004')
def test_refusal_on_rated_scene_does_not_block_the_next_plain_scene(tmp_path):  # MODEL-004-S01
    repo, [first, rated, third] = setup(tmp_path, R(0, 0, 0), (None, R(2, 0, 0), None))
    consent(repo)
    prose_ids = []
    accept_scene(repo, first, prose_ids)
    attempt = draft(repo, repo.get_scene(rated.id), FakeGateway(text='', type='error', finish_reason='content_filter'))
    assert attempt.state == 'failed'
    assert [e['rating'] for e in refusal(repo)['refusals']] == [[2, 0, 0]]
    accept_scene(repo, repo.get_scene(rated.id), prose_ids)
    gateway = FakeGateway()
    assert draft(repo, repo.get_scene(third.id), gateway).state == 'completed'
    assert tuple(gateway.calls[0].policy_rating) == (0, 0, 0)


@pytest.mark.req('MODEL-004')
def test_content_filter_records_refusal_and_blocks_same_or_higher(tmp_path):  # MODEL-004-S01
    repo, [scene] = setup(tmp_path, R(1, 1, 0))
    consent(repo)
    attempt = draft(repo, scene, FakeGateway(text='', type='error', finish_reason='content_filter'))
    assert attempt.state == 'failed'
    [entry] = refusal(repo)['refusals']
    assert entry['rating'] == [1, 1, 0] and entry['category'] == 'refusal_content'
    assert entry['attempt_id'] == attempt.id and entry['scene_id'] == scene.id and entry['story_id'] == scene.story_id
    for rating, blocked in [((1, 1, 0), True), ((2, 1, 0), True), ((0, 1, 0), False)]:
        repo.update_story_rating(scene.story_id, R(*rating), repo.get_story(scene.story_id).revision)
        gateway = FakeGateway()
        if blocked:
            with pytest.raises(ModelPolicyBlocked) as e:
                draft(repo, repo.get_scene(scene.id), gateway)
            assert e.value.kind == 'refusal' and gateway.calls == []
        else:
            assert draft(repo, repo.get_scene(scene.id), gateway).state == 'completed'
    s = ProviderSettings(provider='openrouter', model='x/y')
    repo.model_policy('delete_refusal', role='writer', provider='openrouter', base_url=endpoint(s), model='x/y')
    repo.update_story_rating(scene.story_id, R(2, 1, 0), repo.get_story(scene.story_id).revision)
    assert draft(repo, repo.get_scene(scene.id), FakeGateway()).state == 'completed'


@pytest.mark.req('MODEL-004')
def test_refusal_flag_on_completed_draft_still_records(tmp_path):
    repo, [scene] = setup(tmp_path, R(0, 0, 0))
    attempt = draft(repo, scene, FakeGateway(text='Вибачте, я не можу.', refusal=True))
    assert attempt.state == 'completed'
    [entry] = refusal(repo)['refusals']
    assert entry['category'] == 'refusal_unknown' and entry['rating'] == [0, 0, 0]


@pytest.mark.req('MODEL-004')
def test_refusal_record_failure_does_not_break_the_attempt(tmp_path, monkeypatch):
    repo, [scene] = setup(tmp_path, R(0, 0, 0))
    original = repo.model_policy

    def failing(action, **kw):
        if action == 'add_refusal':
            raise OSError('disk')
        return original(action, **kw)
    monkeypatch.setattr(repo, 'model_policy', failing)
    attempt = draft(repo, scene, FakeGateway(text='', type='error', finish_reason='content_filter'))
    assert attempt.state == 'failed' and attempt.context['model_policy_warning']


@pytest.mark.req('MODEL-004')
def test_impact_refusal_records_planner_with_max_scene_rating(tmp_path):  # MODEL-004-S03
    repo, [first, second] = setup(tmp_path, R(0, 0, 0), (None, R(0, 2, 0)))
    planner = RoleSettings(provider=ProviderSettings(provider='openrouter', model='x/y'))
    consent(repo, 'planner')
    refs = [first.heads['brief'], second.heads['brief']]
    context = build_context(repo, first.id, 'brief', planner).model_copy(
        update={'stage': 'impact_delta', 'scene_id': None, 'input_refs': refs})
    attempt = execute_stage(repo, None, 'impact_delta', context,
        FakeGateway(text='', type='error', finish_reason='content_filter'), threading.Event(), noop)
    assert attempt.state == 'failed'
    [entry] = refusal(repo, 'planner')['refusals']
    assert entry['rating'] == [0, 2, 0] and entry['category'] == 'refusal_content'
    assert refusal(repo, 'writer') is None


@pytest.mark.req('MODEL-003')
def test_chat_answer_is_never_checked_or_recorded(tmp_path):
    repo, [scene] = setup(tmp_path, R(2, 0, 0))
    context = build_context(repo, scene.id, 'draft', writer_role())
    gateway = FakeGateway(refusal=True)
    attempt = execute_stage(repo, scene.id, 'draft', context, gateway, threading.Event(), noop,
        external_origin=ExternalOrigin(client='Claude'))
    assert attempt.state == 'completed'
    assert gateway.calls[0].policy_role is None
    assert refusal(repo) is None
