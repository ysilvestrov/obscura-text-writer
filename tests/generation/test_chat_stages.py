"""MCP-BRIDGE package 3: stage instructions shared with the pipeline and the chat role settings."""
import pytest

from storygen.domain import PromptContract, SceneCreate, StoryCreate
from storygen.generation.context import build_context, stage_system_text
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage.repository import Repository

BRIEF = '{"objective":"Марта лагодить маяк","beats":["Марта лагодить маяк"],"constraints":[],"proposed_changes":[],"introduced":[]}'
ROLE = RoleSettings(provider=ProviderSettings(model='test'), context_tokens=262144)


def scene_with_draft(tmp_path, content_format='markdown'):
    from storygen.domain import ContentRating
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Маяк', content_rating=ContentRating(sexual=0, violence=0, themes=0)))
    scene = repo.create_scene(story.id, SceneCreate(title='Туман', beats='Марта лагодить маяк.', character_ids=['marta']))
    brief = repo.save_version(story.id, scene.id, 'brief', BRIEF, [])
    repo.set_head(scene.id, 'brief', brief.id, repo.get_scene(scene.id).revision)
    draft = repo.save_version(story.id, scene.id, 'draft', 'Марта піднялася на маяк.', [brief.id], content_format=content_format)
    repo.set_head(scene.id, 'draft', draft.id, repo.get_scene(scene.id).revision)
    return repo, story, repo.get_scene(scene.id)


def system_of(repo, story, scene, stage, role, fragments=None):
    view = repo.context_view(story.id)
    return stage_system_text(view, view.get_story(story.id), view.get_scene(scene.id), stage, role, dict(fragments or {}), [])


@pytest.mark.req('MCP-BRIDGE')
@pytest.mark.parametrize('stage', ['brief', 'draft', 'edit'])
def test_make_context_system_text_is_stage_system_text(tmp_path, stage):
    repo, story, scene = scene_with_draft(tmp_path)
    bundle = build_context(repo, scene.id, stage, ROLE)
    fragments = {'copyedit_draft_id': bundle.fragments['copyedit_draft_id']} if stage == 'edit' else {}
    assert bundle.system_text == system_of(repo, story, scene, stage, ROLE, fragments)


def custom_writer_prompt(repo, story, schema_version=None):
    contract = PromptContract(stage='draft', mode='prose', schema_version=schema_version) if schema_version else None
    return repo.save_version(story.id, None, 'prompt', 'Власний промпт письменника.', [], prompt_contract=contract)


@pytest.mark.req('MCP-BRIDGE')
def test_writing_context_has_draft_instructions(tmp_path):
    """MCP-BRIDGE-S46."""
    from storygen.application.writing_context import writing_context
    from storygen.application.chat_stages import chat_role_settings
    repo, story, scene = scene_with_draft(tmp_path)
    data = writing_context(repo, scene.id)
    assert data['instructions'] == build_context(repo, scene.id, 'draft', chat_role_settings(repo, story.id, 'draft')).system_text
    assert data['instructions_error'] is None and data['instructions'].strip()


@pytest.mark.req('MCP-BRIDGE')
def test_writer_prompt_change_changes_context_fingerprint(tmp_path):
    """MCP-BRIDGE-S46."""
    from storygen.application.writing_context import writing_context
    from storygen.web.routes_settings import SettingsChange, configure_prompts
    repo, story, scene = scene_with_draft(tmp_path)
    before = writing_context(repo, scene.id)
    settings = RoleSettings(provider=ProviderSettings(model='test'))
    change = SettingsChange(expected_revision=repo.get_story(story.id).revision, role='writer', settings=settings, prompt_text='Пиши коротко.')
    configured = configure_prompts(repo, story.id, change, settings)
    repo.write_role_settings(story.id, {'writer': configured.model_dump()}, repo.get_story(story.id).revision)
    after = writing_context(repo, scene.id)
    assert 'Пиши коротко.' in after['instructions'] and after['context_fingerprint'] != before['context_fingerprint']


@pytest.mark.req('MCP-BRIDGE')
def test_incompatible_writer_prompt_does_not_break_writing_context(tmp_path):
    """Review focus 1: a stored writer prompt with another stage's contract, which the pipeline refuses, leaves the materials readable."""
    from storygen.application.writing_context import writing_context
    repo, story, scene = scene_with_draft(tmp_path)
    prompt = repo.save_version(story.id, None, 'prompt', 'Власний промпт планувальника.', [],
                               prompt_contract=PromptContract(stage='brief', mode='brief', schema_version=1))
    role = RoleSettings(provider=ProviderSettings(model='test'), prompt_version_id=prompt.id)
    # The settings store refuses such a prompt now; a stored row from before a contract change is how it reaches a story.
    with repo.db.connection() as db:
        db.execute('INSERT OR REPLACE INTO role_settings VALUES(?,?,?)', (story.id, 'writer', role.model_dump_json()))
    with pytest.raises(ValueError) as refused:
        build_context(repo, scene.id, 'draft', role)
    data = writing_context(repo, scene.id)
    assert data['instructions'] is None and data['instructions_error'] == str(refused.value)
    assert data['plan'] == 'Марта лагодить маяк.'


@pytest.mark.req('MCP-BRIDGE')
def test_chat_role_settings_defaults_and_configured(tmp_path):
    from storygen.application.chat_stages import chat_role_settings
    repo, story, _ = scene_with_draft(tmp_path)
    default = chat_role_settings(repo, story.id, 'edit')
    assert (default.context_tokens, default.max_output_tokens, default.edit_mode) == (131072, 8192, 'prose')
    assert chat_role_settings(repo, story.id, 'memory').memory_mode == 'evidence_delta'
    editor = RoleSettings(provider=ProviderSettings(model='test'), edit_mode='patches')
    repo.write_role_settings(story.id, {'editor': editor.model_dump()}, repo.get_story(story.id).revision)
    configured = chat_role_settings(repo, story.id, 'edit')
    assert configured.edit_mode == 'patches' and configured.context_tokens == editor.context_tokens
    with pytest.raises(ValueError):
        chat_role_settings(repo, story.id, 'prepare')
