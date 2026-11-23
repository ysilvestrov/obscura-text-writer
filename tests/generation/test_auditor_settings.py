"""The auditor role (MODEL-001): derived settings, stage prompts and policy keys."""
import pytest

from storygen.domain import StoryCreate
from storygen.generation.auditor_settings import is_derived, prompt_version_for, resolve_auditor
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.providers.policy import CONSENT_REQUIRED, MULTI_SCENE_STAGES, REFUSAL_BLOCKED, STAGE_POLICY_ROLE, ModelPolicyBlocked, check_consent
from storygen.storage.repository import Repository

AUDIT_STAGES = ('audit_brief', 'audit_prose', 'audit_memory')


def base_roles():
    return {'editor': RoleSettings(provider=ProviderSettings(provider='venice', model='m-ed'), max_input_chars=80000),
            'planner': RoleSettings(provider=ProviderSettings(provider='local', model='p'), context_tokens=200000,
                                    max_input_chars=400000, max_output_tokens=8000)}


@pytest.mark.req('MODEL-001')
def test_auditor_without_row_takes_editor_provider_and_planner_limits():  # MODEL-001-S03
    roles = base_roles()
    derived = resolve_auditor(roles)
    assert derived.provider == roles['editor'].provider
    assert (derived.max_input_chars, derived.max_output_tokens, derived.context_tokens) == (400000, 8000, 200000)
    assert derived.temperature == 0.2
    assert is_derived(roles) and resolve_auditor({}) is None
    own = RoleSettings(provider=ProviderSettings(provider='local', model='a'))
    assert resolve_auditor({**roles, 'auditor': own}) == own and not is_derived({**roles, 'auditor': own})


@pytest.mark.req('MODEL-001')
def test_derived_auditor_needs_the_editor_and_falls_back_to_defaults_without_planner():  # MODEL-001-S03
    assert resolve_auditor({'planner': base_roles()['planner']}) is None
    only_editor = resolve_auditor({'editor': base_roles()['editor']})
    assert only_editor.provider.model == 'm-ed' and only_editor.temperature == 0.2
    assert only_editor.max_output_tokens == RoleSettings.model_fields['max_output_tokens'].default


@pytest.mark.req('MODEL-001')
def test_prompt_version_for_picks_the_stage_prompt():  # MODEL-001-S03
    item = RoleSettings(provider=ProviderSettings(model='a'), prompt_version_id='p-prose',
                        stage_prompt_version_ids={'audit_brief': 'p-brief'})
    assert prompt_version_for(item, 'audit_prose') == 'p-prose'
    assert prompt_version_for(item, 'audit_brief') == 'p-brief'
    assert prompt_version_for(item, 'audit_memory') is None
    with pytest.raises(ValueError):
        prompt_version_for(item, 'edit')


@pytest.mark.req('MODEL-001')
def test_stage_prompts_only_for_auditor_audit_brief_and_memory(tmp_path):  # MODEL-001-S03
    from storygen.authoring.blueprints import save_role_settings
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Ревізор'))
    base = RoleSettings(provider=ProviderSettings(model='a'))
    for role, keys in [('auditor', {'audit_prose': 'x'}), ('auditor', {'edit': 'x'}), ('editor', {'audit_brief': 'x'}),
                       ('writer', {'audit_memory': 'x'})]:
        with pytest.raises(ValueError):
            save_role_settings(repo, story.id, role, base.model_copy(update={'stage_prompt_version_ids': keys}), repo.get_story(story.id).revision)
    assert repo.read_role_settings(story.id) == {}
    updated = save_role_settings(repo, story.id, 'auditor', base, repo.get_story(story.id).revision)
    assert 'auditor' in repo.read_role_settings(story.id) and updated.config_revision == 1
    assert RoleSettings.model_validate({'provider': {'model': 'a'}}).stage_prompt_version_ids == {}


@pytest.mark.req('MODEL-001')
def test_stage_prompt_of_another_story_is_rejected(tmp_path):  # MODEL-001-S03
    from storygen.authoring.blueprints import save_role_settings
    repo = Repository(tmp_path)
    story, other = repo.create_story(StoryCreate(title='А')), repo.create_story(StoryCreate(title='Б'))
    foreign = repo.save_version(other.id, None, 'prompt', 'чужий', [])
    item = RoleSettings(provider=ProviderSettings(model='a'), stage_prompt_version_ids={'audit_brief': foreign.id})
    with pytest.raises(ValueError):
        save_role_settings(repo, story.id, 'auditor', item, repo.get_story(story.id).revision)


@pytest.mark.req('MODEL-003')
def test_audit_stages_use_the_auditor_consent_key_per_scene(tmp_path):  # MODEL-003-S03
    repo = Repository(tmp_path)
    assert {STAGE_POLICY_ROLE[s] for s in AUDIT_STAGES} == {'auditor'}
    assert not MULTI_SCENE_STAGES & set(AUDIT_STAGES)
    s = ProviderSettings(provider='openrouter', model='x/y')
    with pytest.raises(ModelPolicyBlocked) as blocked:
        check_consent(repo, STAGE_POLICY_ROLE['audit_prose'], s, (2, 0, 0), None)
    assert blocked.value.kind == 'consent' and 'Ревізор' in str(blocked.value)
    repo.model_policy('set_consent', role='auditor', provider='openrouter', base_url=s.base_url, model='x/y')
    check_consent(repo, 'auditor', s, (2, 0, 0), None)
    with pytest.raises(ModelPolicyBlocked):
        check_consent(repo, 'editor', s, (2, 0, 0), None)


@pytest.mark.req('MODEL-003')
def test_auditor_policy_texts_are_in_both_catalogs():  # MODEL-003-S03
    from storygen.web.localization import translate
    assert translate('policy.block.consent.auditor', 'uk', p0='m', p1='2/0/0') == CONSENT_REQUIRED.format(model='m', rating='2/0/0', role='Ревізор')
    assert translate('policy.block.refusal.auditor', 'uk', p0='m', p1='1/0/0', p2='2/0/0') == REFUSAL_BLOCKED.format(model='m', seen='1/0/0', rating='2/0/0', role='Ревізор')
    for kind in ('consent', 'refusal'):
        assert 'Auditor' in translate(f'policy.block.{kind}.auditor', 'en', p0='m', p1='1', p2='2')


@pytest.mark.req('MODEL-001')
def test_shared_provider_writes_the_auditor_only_when_it_has_a_row(tmp_path):  # MODEL-001-S01
    from storygen.authoring.blueprints import get_role_settings, save_role_settings, save_shared_provider
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Спільний'))
    for role in ('planner', 'writer', 'editor', 'memory'):
        save_role_settings(repo, story.id, role, RoleSettings(provider=ProviderSettings(model='old')), repo.get_story(story.id).revision)
    shared = ProviderSettings(provider='venice', model='shared')
    save_shared_provider(repo, story.id, shared, repo.get_story(story.id).revision)
    rows = get_role_settings(repo, story.id)
    assert 'auditor' not in rows and {r.provider.model for r in rows.values()} == {'shared'}
    assert resolve_auditor(rows).provider.model == 'shared'
    save_role_settings(repo, story.id, 'auditor', RoleSettings(provider=ProviderSettings(model='own')), repo.get_story(story.id).revision)
    save_shared_provider(repo, story.id, ProviderSettings(provider='venice', model='next'), repo.get_story(story.id).revision)
    assert {r.provider.model for r in get_role_settings(repo, story.id).values()} == {'next'}


@pytest.mark.req('MODEL-001')
def test_settings_api_reads_a_story_without_and_with_an_auditor_row(tmp_path):  # MODEL-001-S03
    from fastapi.testclient import TestClient
    from storygen.application.settings import AppSettings
    from storygen.web.app import create_app
    with TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765') as client:
        story = client.post('/api/stories', json={'title': 'Ревізор'}).json()
        before = client.get(f"/api/stories/{story['id']}/settings").json()
        assert 'auditor' not in before['roles'] and 'auditor' not in before['prompts']
        saved = client.put(f"/api/stories/{story['id']}/settings", json={'expected_revision': before['story']['revision'], 'role': 'auditor',
            'settings': {'provider': {'provider': 'local', 'model': 'm1'}}})
        assert saved.status_code == 200, saved.text
        after = client.get(f"/api/stories/{story['id']}/settings").json()
        assert after['roles']['auditor']['provider']['model'] == 'm1' and 'auditor' in after['prompts']
        assert after['prompt_contracts']['auditor'] == {'stage': 'audit_prose', 'mode': 'json', 'schema_version': 1}


@pytest.mark.req('MODEL-001')
def test_settings_api_stores_a_custom_auditor_main_prompt_with_its_stage_contract(tmp_path):  # MODEL-001-S03
    from fastapi.testclient import TestClient
    from storygen.application.settings import AppSettings
    from storygen.generation.prompts import default_prompt
    from storygen.web.app import create_app
    with TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765') as client:
        story = client.post('/api/stories', json={'title': 'Ревізор'}).json()
        revision = client.get(f"/api/stories/{story['id']}/settings").json()['story']['revision']
        body = {'expected_revision': revision, 'role': 'auditor', 'settings': {'provider': {'provider': 'local', 'model': 'm1'}}}
        assert client.put(f"/api/stories/{story['id']}/settings", json={**body, 'prompt_text': 'Власна перевірка.'}).status_code == 200
        after = client.get(f"/api/stories/{story['id']}/settings").json()
        assert after['prompts']['auditor'] == 'Власна перевірка.'
        assert after['prompt_contracts']['auditor'] == {'stage': 'audit_prose', 'mode': 'json', 'schema_version': 1}
        # The standard text returns the built-in prompt.
        reset = {**body, 'expected_revision': after['story']['revision'], 'settings': after['roles']['auditor'],
                 'prompt_text': default_prompt('audit_prose', 'uk')}
        assert client.put(f"/api/stories/{story['id']}/settings", json=reset).status_code == 200
        assert client.get(f"/api/stories/{story['id']}/settings").json()['roles']['auditor']['prompt_version_id'] is None

