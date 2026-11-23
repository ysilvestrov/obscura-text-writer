"""MODEL-001: prompts, contracts and requests of the audit stages."""
import re

import pytest

from storygen.domain import PromptContract, StoryCreate
from storygen.generation.audit_output import AUDIT_STAGES, AuditResponse
from storygen.generation.prompts import default_prompt, role_prompt
from storygen.language import PROMPTS, load_prompt
from storygen.prompt_contracts import expected_contract, validate_role_prompt
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.providers.requests import generation_request, streams, strict_schema
from storygen.storage.repository import Repository

CYRILLIC = re.compile('[Ѐ-ӿ]')
KEYS = {'audit_brief': {'plan', 'previous_memory', 'brief', 'reference'},
        'audit_prose': {'brief', 'previous_memory', 'prose', 'reference'},
        'audit_memory': {'prose', 'own_memory_records', 'reference'}}


def role(provider='local', response_mode='json_schema', **extra):
    return RoleSettings(provider=ProviderSettings(provider=provider, model='m', response_mode=response_mode), **extra)


@pytest.mark.req('MODEL-001')
@pytest.mark.parametrize('stage', AUDIT_STAGES)
@pytest.mark.parametrize('language', ['uk', 'en'])
def test_default_prompt_reads_the_stage_file(stage, language):  # MODEL-001-S03
    text = default_prompt(stage, language)
    assert text == load_prompt(f'{stage}_v1', language) == role_prompt(stage, role(), language)
    assert 15 <= len(text.splitlines()) <= 60
    for key in KEYS[stage]:
        assert key in text
    assert 'confidence' in text and 'discrepancies' in text and 'summary' in text
    assert bool(CYRILLIC.search(text)) == (language == 'uk')
    assert PROMPTS[f'{stage}_v1'][1] == stage


@pytest.mark.req('MODEL-001')
@pytest.mark.parametrize('stage', AUDIT_STAGES)
def test_expected_contract_is_json_v1(stage):  # MODEL-001-S03
    assert expected_contract(stage, role()) == PromptContract(stage=stage, mode='json', schema_version=1)


@pytest.mark.req('MODEL-001')
@pytest.mark.parametrize('stage', AUDIT_STAGES)
def test_json_schema_request_uses_the_answer_model(stage):  # MODEL-001-S03
    body = generation_request(stage, role(), 's', 'u', {})
    format_ = body['response_format']['json_schema']
    assert format_['name'] == stage and format_['strict'] is True
    assert format_['schema'] == strict_schema(AuditResponse)
    assert 'response_format' not in generation_request(stage, role(response_mode='prompt_json'), 's', 'u', {})


@pytest.mark.req('MODEL-001')
@pytest.mark.parametrize('stage', AUDIT_STAGES)
def test_venice_audit_request_does_not_stream(stage):  # MODEL-001-S03
    venice = role(provider='venice')
    assert generation_request(stage, venice, 's', 'u', {})['stream'] is False
    assert generation_request(stage, role(), 's', 'u', {})['stream'] is True
    assert streams(stage, venice) is False and streams(stage, role()) is True


def story_with_prompts(tmp_path):
    repo = Repository(tmp_path)
    return repo, repo.create_story(StoryCreate(title='Ревізор'))


def save_prompt(repo, story, stage, mode='json', version=1):
    return repo.save_version(story.id, None, 'prompt', 'Власний промпт ревізора.', [],
                             prompt_contract=PromptContract(stage=stage, mode=mode, schema_version=version))


@pytest.mark.req('MODEL-001')
def test_custom_auditor_prompts_validate_against_their_own_stage(tmp_path):  # MODEL-001-S03
    repo, story = story_with_prompts(tmp_path)
    ids = {stage: save_prompt(repo, story, stage).id for stage in AUDIT_STAGES}
    base = role()
    # audit_prose is the main prompt; audit_brief and audit_memory are stage prompts.
    for stage in AUDIT_STAGES:
        assert validate_role_prompt(repo, story.id, stage, base.model_copy(update={'prompt_version_id': ids[stage]})).id == ids[stage]
    rows = {'auditor': base.model_copy(update={'prompt_version_id': ids['audit_prose'],
            'stage_prompt_version_ids': {'audit_brief': ids['audit_brief'], 'audit_memory': ids['audit_memory']}}).model_dump()}
    repo.write_role_settings(story.id, rows, story.revision)
    assert repo.read_role_settings(story.id)['auditor']['stage_prompt_version_ids']['audit_memory'] == ids['audit_memory']


@pytest.mark.req('MODEL-001')
def test_auditor_prompt_with_another_stage_contract_is_rejected(tmp_path):  # MODEL-001-S03
    repo, story = story_with_prompts(tmp_path)
    wrong = save_prompt(repo, story, 'audit_brief')
    memory = save_prompt(repo, story, 'memory', 'evidence_delta', 4)
    base = role()
    with pytest.raises(ValueError, match='Несумісний'):
        validate_role_prompt(repo, story.id, 'audit_prose', base.model_copy(update={'prompt_version_id': wrong.id}))
    with pytest.raises(ValueError, match='Несумісний'):
        validate_role_prompt(repo, story.id, 'audit_memory', base.model_copy(update={'prompt_version_id': memory.id}))
    for rows in ({'prompt_version_id': wrong.id}, {'stage_prompt_version_ids': {'audit_memory': wrong.id}}):
        with pytest.raises(ValueError):
            repo.write_role_settings(story.id, {'auditor': base.model_copy(update=rows).model_dump()}, story.revision)
    assert repo.read_role_settings(story.id) == {}
