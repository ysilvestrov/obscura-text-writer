"""CHARACTER-EXTRACT (R-51): executor settings, context bundle and the `character_extract` stage."""
import json
import threading

import pytest

from storygen.authoring.blueprints import get_role_settings, save_role_settings
from storygen.characters.extract import (
    CatalogueCard, ExtractState, SKIP_CONTEXT_LIMIT, SKIP_INPUT_LIMIT, SceneProse, catalogue_text, short_ids)
from storygen.domain import SceneCreate, StoryCreate
from storygen.generation.extract_context import NO_MEMORY_ROLE, build_extract_context, resolve_extractor
from storygen.generation.stages import execute_stage
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.providers.streaming import GenerationEvent
from storygen.storage.repository import Repository

PROSE = ['Іванка йшла лісом. Анничка сміялася: «Ходімо додому, мамо!»', 'Мирон приніс воду з колодязя.']


class Gateway:
    def __init__(self, text, finish_reason='stop'):
        self.text, self.finish_reason = text, finish_reason

    def stream(self, *_):
        if self.text:
            yield GenerationEvent(type='delta', text=self.text)
        yield GenerationEvent(type='terminal', finish_reason=self.finish_reason)


def memory_role(**limits):
    return RoleSettings(provider=ProviderSettings(provider='local', model='fake'), temperature=0.9,
                        context_tokens=limits.pop('context_tokens', 32768), **limits)


def case(tmp_path, role=None, language='uk'):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Ліс', language=language))
    group = []
    for index, text in enumerate(PROSE, 1):
        scene = repo.create_scene(story.id, SceneCreate(title=str(index)))
        ref = repo.save_version(story.id, scene.id, 'manual', text, [])
        repo.set_head(scene.id, 'prose', ref.id, repo.get_scene(scene.id).revision)
        group.append(SceneProse(scene.id, ref.id, text))
    if role is not None:
        save_role_settings(repo, story.id, 'memory', role, repo.get_story(story.id).revision)
    state = ExtractState(catalogue=[CatalogueCard(ref='card-1', name='Анна', names=['Анна', 'Анничка'], existing=True)],
                         scene_order=[scene.scene_id for scene in group])
    cards, scenes = short_ids(state, [scene.scene_id for scene in group])
    return repo, story, group, state, scenes, cards


def build(case_, settings=None, **kwargs):
    repo, story, group, state, scenes, cards = case_
    settings = settings or resolve_extractor(get_role_settings(repo, story.id))
    return build_extract_context(repo, story.id, settings, state, group, scenes, cards, **kwargs)


@pytest.mark.req('CHARACTER-EXTRACT')
def test_extractor_borrows_memory_role():
    role = memory_role(max_output_tokens=2048, max_input_chars=50000)
    roles = {'memory': role, 'writer': memory_role()}
    extractor = resolve_extractor(roles)
    assert extractor.provider == role.provider
    assert (extractor.context_tokens, extractor.max_input_chars) == (32768, 50000)
    assert extractor.temperature == 0.2 and extractor.max_output_tokens == 16000
    assert roles['memory'].temperature == 0.9 and roles['memory'].max_output_tokens == 2048  # the role is not changed
    assert resolve_extractor({'memory': memory_role(max_output_tokens=20000, context_tokens=60000)}).max_output_tokens == 20000


@pytest.mark.req('CHARACTER-EXTRACT')
def test_no_memory_role_is_none():
    assert resolve_extractor({'writer': memory_role()}) is None
    assert resolve_extractor({'memory': RoleSettings(provider=ProviderSettings(model=' '))}) is None
    assert 'Пам\'ять' in NO_MEMORY_ROLE and 'читає прозу' in NO_MEMORY_ROLE


@pytest.mark.req('CHARACTER-EXTRACT')
def test_bundle_carries_prompt_catalogue_and_prose(tmp_path):
    c = case(tmp_path, memory_role())
    bundle = build(c)
    repo, story, group, state, scenes, cards = c
    assert bundle.stage == 'character_extract' and bundle.policy_role == 'memory'
    assert bundle.scene_id == group[0].scene_id and bundle.story_id == story.id
    assert bundle.input_refs == [scene.version_id for scene in group]
    assert catalogue_text(state, 'uk') in bundle.user_text and 'c1: Анна' in bundle.user_text
    for short, scene_id in scenes.items():
        text = next(scene.text for scene in group if scene.scene_id == scene_id)
        assert short in bundle.user_text and text in bundle.user_text
    assert 'ДОСЛІВН' in bundle.system_text and bundle.api_request['messages'][1]['content'] == bundle.user_text
    assert bundle.estimated_tokens > 0 and bundle.token_estimate['input_tokens'] == bundle.estimated_tokens


@pytest.mark.req('CHARACTER-EXTRACT')
def test_prompt_follows_story_language(tmp_path):
    bundle = build(case(tmp_path, memory_role(), language='en'))
    assert 'VERBATIM' in bundle.system_text and 'ДОСЛІВН' not in bundle.system_text
    assert 'other names: Анничка' in bundle.user_text and 'інші імена' not in bundle.user_text


@pytest.mark.req('CHARACTER-EXTRACT')
def test_output_limit_capped_by_context(tmp_path):
    bundle = build(case(tmp_path, memory_role(context_tokens=16500, max_output_tokens=2048)))
    expected = 16500 - bundle.token_estimate['input_tokens']
    assert 2048 <= expected < 16000
    assert bundle.settings.max_output_tokens == expected == bundle.api_request['max_tokens']
    assert build(case(tmp_path / 'roomy', memory_role())).settings.max_output_tokens == 16000


@pytest.mark.req('CHARACTER-EXTRACT')
def test_unfit_input_returns_reason(tmp_path):
    assert build(case(tmp_path, memory_role(max_input_chars=1000))) == SKIP_INPUT_LIMIT
    assert build(case(tmp_path / 'ctx', memory_role(context_tokens=2600, max_output_tokens=2048))) == SKIP_CONTEXT_LIMIT


@pytest.mark.req('CHARACTER-EXTRACT')
def test_reserve_chars_replaces_the_catalogue(tmp_path):
    c = case(tmp_path, memory_role())
    real, reserved = build(c), build(c, reserve_chars=500)
    assert catalogue_text(c[3], 'uk') not in reserved.user_text
    assert len(reserved.user_text) - len(real.user_text) == 500 - len(catalogue_text(c[3], 'uk'))
    assert build(case(tmp_path / 'over', memory_role(max_input_chars=3000)), reserve_chars=5000) == SKIP_INPUT_LIMIT


def run_stage(tmp_path, text, finish_reason='stop'):
    c = case(tmp_path, memory_role())
    bundle = build(c)
    return execute_stage(c[0], c[2][0].scene_id, 'character_extract', bundle, Gateway(text, finish_reason),
                         threading.Event(), lambda _: None)


@pytest.mark.req('CHARACTER-EXTRACT')
def test_stage_parses_response_into_attempt(tmp_path):
    answer = {'new_cards': [{'key': 'n1', 'name': 'Мирон', 'other_names': [], 'quotes': ['Мирон приніс воду']}],
              'card_updates': [], 'scenes': [{'scene': 's2', 'participants': ['n1']}], 'protagonist_candidates': []}
    attempt = run_stage(tmp_path, json.dumps(answer, ensure_ascii=False))
    assert attempt.state == 'completed', attempt.error
    assert attempt.result_version_id is None
    saved = attempt.context['extract_response']
    assert saved['new_cards'][0]['name'] == 'Мирон' and saved['scenes'][0]['participants'] == ['n1']


@pytest.mark.req('CHARACTER-EXTRACT')
def test_unparseable_response_fails_attempt(tmp_path):
    attempt = run_stage(tmp_path, 'Ось ваші персонажі: Іванка.')
    assert attempt.state == 'failed' and 'JSON' in attempt.error
    assert attempt.context['extract_failure']['category'] == 'protocol'
    assert 'extract_response' not in attempt.context


@pytest.mark.req('CHARACTER-EXTRACT')
def test_empty_stop_fails_attempt(tmp_path):
    attempt = run_stage(tmp_path, '')
    assert attempt.state == 'failed' and attempt.error
    assert attempt.context['extract_failure']['category'] == 'empty_output'


@pytest.mark.req('CHARACTER-EXTRACT')
def test_truncated_output_fails_attempt(tmp_path):
    attempt = run_stage(tmp_path, '{"new_cards": [', finish_reason='length')
    assert attempt.state == 'failed' and attempt.context['extract_failure']['category'] == 'output_limit'
