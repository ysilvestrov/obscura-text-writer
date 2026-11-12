"""MODEL-001: the writer's optional model for scenes 0–1, chosen per scene by one routing function."""
import json
import threading
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.authoring.blueprints import save_role_settings
from storygen.domain import ContentRating, SceneCreate, StoryCreate
from storygen.generation.context import build_context
from storygen.generation.pipeline import generate_scene
from storygen.generation.role_routing import VARIANT_WRITER_ONLY, WRITER_STAGES, settings_for, uses_low_rating_variant
from storygen.generation.stages import execute_stage
from storygen.providers.models import ProviderSettings, RoleSettings, RoleVariant
from storygen.providers.policy import ModelPolicyBlocked, endpoint
from storygen.storage.repository import Repository
from storygen.web.app import create_app
from tests.generation.test_model_policy_stages import ADULTS, BRIEF, FakeGateway
from tests.generation.test_scene_pipeline import FakeGateway as PipelineGateway

pytestmark = pytest.mark.req('MODEL-001')


def R(s, v, t):
    return ContentRating(sexual=s, violence=v, themes=t)


def story(*rating):
    return SimpleNamespace(content_rating=R(*rating) if rating else None)


def scene(rating):
    return SimpleNamespace(content_rating=R(*rating) if rating else None)


def provider(spec):
    kind, model = spec.split('/', 1)
    return ProviderSettings(provider='local', model=spec) if kind == 'local' else ProviderSettings(provider=kind, model=spec)


def variant(low='openrouter/x', **extra):
    return RoleVariant(provider=provider(low), context_tokens=16384, max_output_tokens=1024, max_input_chars=50000,
        temperature=0.3, **extra)


def writer_with_variant(main='venice/unc', low='openrouter/x', **extra):
    return RoleSettings(provider=provider(main), low_rating_variant=variant(low, **extra))


def writer_without_variant(main='venice/unc'):
    return RoleSettings(provider=provider(main))


def test_writer_scene_without_level_two_goes_to_variant():  # MODEL-001-S02
    s = writer_with_variant(main='venice/unc', low='openrouter/x')
    assert settings_for(s, 'writer', story(0, 1, 1), scene(None)).provider.model == 'openrouter/x'
    assert settings_for(s, 'writer', story(0, 0, 0), scene((0, 2, 0))).provider.model == 'venice/unc'
    assert settings_for(s, 'writer', story(2, 0, 0), scene((0, 1, 0))).provider.model == 'openrouter/x'  # Scene rating wins.
    assert settings_for(writer_without_variant(), 'writer', story(0, 1, 1), scene(None)).provider.model == 'venice/unc'


def test_unset_rating_uses_main_model():
    s = writer_with_variant()
    assert not uses_low_rating_variant(s, story(), scene(None))
    assert settings_for(s, 'writer', story(), scene(None)) is s


def test_routed_settings_take_variant_limits_and_timeout():
    s = writer_with_variant(timeout=42)
    routed = settings_for(s, 'writer', story(0, 0, 0), scene(None))
    assert (routed.context_tokens, routed.max_output_tokens, routed.max_input_chars, routed.temperature) == (16384, 1024, 50000, 0.3)
    assert routed.provider.timeout == 42 and routed.provider.provider == 'openrouter'
    assert settings_for(writer_with_variant(), 'writer', story(0, 0, 0), scene(None)).provider.timeout == 180  # Provider default.
    assert routed.prompt_version_id == s.prompt_version_id  # The prompt is shared.


def test_routing_is_idempotent_and_only_for_writer():
    s = writer_with_variant()
    routed = settings_for(s, 'writer', story(0, 0, 0), scene(None))
    assert routed.low_rating_variant is None and settings_for(routed, 'writer', story(0, 0, 0), scene(None)) == routed
    assert settings_for(s, 'editor', story(0, 0, 0), scene(None)) is s
    assert WRITER_STAGES == frozenset({'draft', 'rewrite'})


def test_variant_limits_are_validated():
    with pytest.raises(ValueError):
        RoleVariant(provider=provider('openrouter/x'), context_tokens=1024, max_output_tokens=1024)
    with pytest.raises(ValueError):
        RoleVariant(provider=provider('openrouter/x'), timeout=0)
    assert RoleSettings.model_validate({'provider': {'model': 'm'}}).low_rating_variant is None  # Stored settings unchanged.


def make_repo(tmp_path, story_rating, scene_rating=None):
    repo = Repository(tmp_path)
    created = repo.create_story(StoryCreate(title='Нейтральний твір'))
    cards = repo.save_version(created.id, None, 'character_cards', json.dumps([ADULTS], ensure_ascii=False), [])
    repo.publish_story_material(created.id, 'characters_version_id', cards.id, repo.get_story(created.id).revision)
    repo.update_story_rating(created.id, story_rating, repo.get_story(created.id).revision)
    item = repo.create_scene(created.id, SceneCreate(title='Сцена 1', beats='Прогулянка', character_ids=['A']))
    if scene_rating is not None:
        repo.update_scene_rating(item.id, scene_rating, repo.get_scene(item.id).revision)
    ref = repo.save_version(created.id, item.id, 'brief', BRIEF, [])
    repo.set_head(item.id, 'brief', ref.id, repo.get_scene(item.id).revision)
    return repo, repo.get_scene(item.id)


def test_draft_context_uses_variant_limits_and_changes_fingerprint(tmp_path):
    repo, item = make_repo(tmp_path, R(0, 1, 1))
    role = writer_with_variant(main='local/main', low='local/low')
    low = build_context(repo, item.id, 'draft', role)
    assert low.settings.context_tokens == 16384 and low.settings.provider.model == 'local/low'
    assert low.settings.low_rating_variant is None
    assert build_context(repo, item.id, 'brief', role).settings.provider.model == 'local/main'  # Planner stage: not routed.
    repo.update_story_rating(item.story_id, R(0, 2, 0), repo.get_story(item.story_id).revision)
    high = build_context(repo, item.id, 'draft', role)
    assert high.settings.provider.model == 'local/main' and high.settings.context_tokens == 8192
    assert high.fingerprint != low.fingerprint


def run_pipeline(tmp_path, rating):
    repo = Repository(tmp_path)
    created = repo.create_story(StoryCreate(title='Твір'))
    repo.update_story_rating(created.id, rating, repo.get_story(created.id).revision)
    item = repo.create_scene(created.id, SceneCreate(title='Ранок', beats='Студія'))
    gateway = PipelineGateway(repo, item.id)
    roles = {role: RoleSettings(provider=ProviderSettings(model=role)) for role in ['planner', 'editor', 'memory']}
    roles['writer'] = writer_with_variant(main='local/main', low='local/low')
    providers = []

    def factory(p):
        providers.append(p.model)
        return gateway
    generate_scene(repo, item.id, roles, factory, threading.Event(), lambda *_: None)
    return providers, [c.stage for c in gateway.contexts]


def test_pipeline_calls_variant_model_for_low_scene(tmp_path):
    providers, stages = run_pipeline(tmp_path / 'low', R(0, 1, 0))
    assert providers[stages.index('draft')] == 'local/low'
    assert providers[stages.index('brief')] == 'planner'
    providers, stages = run_pipeline(tmp_path / 'high', R(0, 2, 0))
    assert providers[stages.index('draft')] == 'local/main'


def test_variant_model_needs_its_own_consent(tmp_path):
    repo, item = make_repo(tmp_path, R(0, 1, 0))
    role = writer_with_variant(main='local/main', low='openrouter/x')
    save_role_settings(repo, item.story_id, 'writer', role, repo.get_story(item.story_id).revision)
    gateway = FakeGateway()
    with pytest.raises(ModelPolicyBlocked) as e:
        execute_stage(repo, item.id, 'draft', build_context(repo, item.id, 'draft', role), gateway, threading.Event(), lambda _: None)
    assert '«openrouter/x»' in str(e.value) and gateway.calls == []
    s = provider('openrouter/x')
    repo.model_policy('set_consent', role='writer', provider='openrouter', base_url=endpoint(s), model='openrouter/x')
    attempt = execute_stage(repo, item.id, 'draft', build_context(repo, item.id, 'draft', role), gateway, threading.Event(), lambda _: None)
    assert attempt.state == 'completed'


def test_variant_is_rejected_for_other_roles(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app, base_url='http://127.0.0.1:8765') as c:
        sid = c.post('/api/stories', json={'title': 'Варіант'}).json()['id']
        revision = c.get(f'/api/stories/{sid}/settings').json()['story']['revision']
        body = {'expected_revision': revision, 'settings': {'provider': {'model': 'main'},
            'low_rating_variant': {'provider': {'model': 'low'}}}}
        response = c.put(f'/api/stories/{sid}/settings', json={**body, 'role': 'editor'})
        assert response.status_code == 400 and VARIANT_WRITER_ONLY in response.text
        saved = c.put(f'/api/stories/{sid}/settings', json={**body, 'role': 'writer'})
        assert saved.status_code == 200
        roles = c.get(f'/api/stories/{sid}/settings').json()['roles']
        assert roles['writer']['low_rating_variant']['provider']['model'] == 'low'
