"""MODEL-001 in the settings page: the auditor borrows the editor's model until the author saves a row of its own; its
three prompts are the main audit_prose prompt and the stage prompts of audit_brief and audit_memory."""
import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.authoring.blueprints import save_role_settings
from storygen.domain import StoryCreate
from storygen.generation.prompts import default_prompt
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.web.app import create_app


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(AppSettings(data_dir=tmp_path / 'data', env_file=tmp_path / 'absent.env')), base_url='http://127.0.0.1')


def story_with_editor(client, planner=True):
    repo = client.app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк'))
    save_role_settings(repo, story.id, 'editor', RoleSettings(provider=ProviderSettings(model='editor-model')), repo.get_story(story.id).revision)
    if planner:
        save_role_settings(repo, story.id, 'planner', RoleSettings(provider=ProviderSettings(model='planner-model'), context_tokens=65536,
                                                                   max_input_chars=300000, max_output_tokens=4096), repo.get_story(story.id).revision)
    return story


def auditor_row(**changes):
    settings = RoleSettings(provider=ProviderSettings(model='auditor-model'), temperature=0.2, context_tokens=65536,
                            max_input_chars=300000, max_output_tokens=4096)
    return settings.model_copy(update=changes).model_dump(mode='json')


def put(client, story, **body):
    url = f'/api/stories/{story.id}/settings'
    return client.put(url, json={'expected_revision': client.get(url).json()['story']['revision'], 'role': 'auditor', **body})


def test_auditor_without_its_own_row_is_derived_from_the_editor(client):
    story = story_with_editor(client)
    data = client.get(f'/api/stories/{story.id}/settings').json()
    auditor = data['roles']['auditor']
    assert auditor['derived'] is True
    assert auditor['provider']['model'] == 'editor-model' and auditor['temperature'] == 0.2
    assert (auditor['context_tokens'], auditor['max_input_chars'], auditor['max_output_tokens']) == (65536, 300000, 4096)
    assert 'derived' not in data['roles']['editor']
    assert data['prompts']['auditor'] == default_prompt('audit_prose', 'uk')
    assert data['stage_prompts'] == {'auditor': {'audit_brief': default_prompt('audit_brief', 'uk'),
                                                 'audit_memory': default_prompt('audit_memory', 'uk')}}
    assert data['prompt_contracts']['auditor'] == {'stage': 'audit_prose', 'mode': 'json', 'schema_version': 1}
    assert data['stage_prompt_contracts']['auditor']['audit_brief'] == {'stage': 'audit_brief', 'mode': 'json', 'schema_version': 1}


def test_without_an_editor_there_is_no_auditor(client):
    story = client.app.state.repo.create_story(StoryCreate(title='Порожній'))
    data = client.get(f'/api/stories/{story.id}/settings').json()
    assert 'auditor' not in data['roles'] and data['stage_prompts'] == {}


def test_put_saves_the_auditor_row_of_its_own(client):
    story = story_with_editor(client)
    saved = put(client, story, settings=auditor_row())
    assert saved.status_code == 200, saved.text
    auditor = client.get(f'/api/stories/{story.id}/settings').json()['roles']['auditor']
    assert 'derived' not in auditor and auditor['provider']['model'] == 'auditor-model'
    # The marker belongs to the read: echoing it back is not a field of the settings.
    assert put(client, story, settings={**auditor_row(), 'derived': True}).status_code == 422


def test_audit_prose_is_not_a_stage_prompt(client):
    story = story_with_editor(client)
    prompt = client.app.state.repo.save_version(story.id, None, 'prompt', 'Мій промпт', [])
    response = put(client, story, settings=auditor_row(stage_prompt_version_ids={'audit_prose': prompt.id}))
    assert response.status_code == 422, response.text
    assert put(client, story, settings=auditor_row(), stage_prompt_texts={'audit_prose': 'Мій промпт'}).status_code == 422


def test_stage_prompts_are_saved_with_their_own_contract_and_reset_by_a_blank_text(client):
    story = story_with_editor(client)
    saved = put(client, story, settings=auditor_row(), prompt_text='Головний промпт перевірки',
                stage_prompt_texts={'audit_brief': 'Промпт перевірки завдання'})
    assert saved.status_code == 200, saved.text
    data = client.get(f'/api/stories/{story.id}/settings').json()
    auditor = data['roles']['auditor']
    assert set(auditor['stage_prompt_version_ids']) == {'audit_brief'} and auditor['prompt_version_id']
    assert data['prompts']['auditor'] == 'Головний промпт перевірки'
    assert data['stage_prompts']['auditor'] == {'audit_brief': 'Промпт перевірки завдання', 'audit_memory': default_prompt('audit_memory', 'uk')}
    assert data['stage_prompt_contracts']['auditor']['audit_brief'] == {'stage': 'audit_brief', 'mode': 'json', 'schema_version': 1}
    # The standard text or a blank field returns the stage to the standard prompt; the other stage prompt is kept.
    reset = put(client, story, settings=auditor, stage_prompt_texts={'audit_brief': ''})
    assert reset.status_code == 200, reset.text
    data = client.get(f'/api/stories/{story.id}/settings').json()
    assert data['roles']['auditor']['stage_prompt_version_ids'] == {}
    assert data['stage_prompts']['auditor']['audit_brief'] == default_prompt('audit_brief', 'uk')


def test_stage_prompts_belong_only_to_the_auditor(client):
    story = story_with_editor(client)
    url = f'/api/stories/{story.id}/settings'
    response = client.put(url, json={'expected_revision': client.get(url).json()['story']['revision'], 'role': 'editor',
                                     'settings': RoleSettings(provider=ProviderSettings(model='editor-model')).model_dump(mode='json'),
                                     'stage_prompt_texts': {'audit_brief': 'Промпт'}})
    assert response.status_code == 400 and 'Ревізор' in response.json()['detail_original']
