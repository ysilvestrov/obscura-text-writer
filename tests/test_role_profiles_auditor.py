"""MODEL-001: role presets and the auditor (schema version 3)."""
import json

import pytest

from storygen.domain import StoryCreate
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.role_profiles import apply_profile, capture_profile, export_profile, parse_profile, preview_profile
from tests.authoring.test_role_profiles import seeded

BASE_ROLES = ('planner', 'writer', 'editor', 'memory')


def with_auditor(repo, story, model='audit-model'):
    rows = repo.read_role_settings(story.id)
    rows['auditor'] = RoleSettings(provider=ProviderSettings(model=model), temperature=0.1).model_dump()
    repo.write_role_settings(story.id, rows, story.revision)
    return repo.get_story(story.id)


def document(repo, profile):
    return json.loads(export_profile(repo, profile['id'], profile['version']))


@pytest.mark.req('MODEL-001')
def test_capture_without_auditor_keeps_version_1_and_has_no_auditor(tmp_path):  # MODEL-001-S03
    repo, source, _ = seeded(tmp_path)
    saved = capture_profile(repo, source.id, 'Без Ревізора', source.revision)
    data = document(repo, saved)
    assert data['schema_version'] == 1 and set(data['roles']) == set(BASE_ROLES)


@pytest.mark.req('MODEL-001')
def test_capture_with_auditor_writes_version_3_and_apply_copies_its_settings(tmp_path):  # MODEL-001-S03
    repo, source, _ = seeded(tmp_path)
    source = with_auditor(repo, source)
    saved = capture_profile(repo, source.id, 'З Ревізором', source.revision)
    data = document(repo, saved)
    assert data['schema_version'] == 3 and set(data['roles']) == set(BASE_ROLES) | {'auditor'}
    assert data['roles']['auditor']['settings']['provider']['model'] == 'audit-model'
    target = repo.create_story(StoryCreate(title='Ціль'))
    preview = preview_profile(repo, target.id, saved['id'], 1, target.revision)
    assert set(preview['roles']) == set(BASE_ROLES) | {'auditor'}
    apply_profile(repo, target.id, saved['id'], 1, target.revision)
    rows = repo.read_role_settings(target.id)
    assert rows['auditor']['provider']['model'] == 'audit-model' and rows['auditor']['temperature'] == 0.1


@pytest.mark.req('MODEL-001')
def test_capture_with_auditor_and_variant_writes_version_3(tmp_path):  # MODEL-001-S03
    from storygen.providers.models import RoleVariant
    repo, source, _ = seeded(tmp_path)
    rows = repo.read_role_settings(source.id)
    rows['writer']['low_rating_variant'] = RoleVariant(provider=ProviderSettings(model='low')).model_dump()
    repo.write_role_settings(source.id, rows, source.revision)
    source = with_auditor(repo, repo.get_story(source.id))
    data = document(repo, capture_profile(repo, source.id, 'Обидва', source.revision))
    assert data['schema_version'] == 3 and data['roles']['writer']['settings']['low_rating_variant']


@pytest.mark.req('MODEL-001')
def test_older_presets_leave_the_existing_auditor_row_unchanged(tmp_path):  # MODEL-001-S03
    repo, source, _ = seeded(tmp_path)
    saved = capture_profile(repo, source.id, 'Старий', source.revision)
    target = repo.create_story(StoryCreate(title='Ціль'))
    target = with_auditor(repo, target, 'own-auditor')
    before = repo.read_role_settings(target.id)['auditor']
    apply_profile(repo, target.id, saved['id'], 1, target.revision)
    rows = repo.read_role_settings(target.id)
    assert rows['auditor'] == before and set(rows) == set(BASE_ROLES) | {'auditor'}


@pytest.mark.req('MODEL-001')
def test_schema_version_and_auditor_must_agree(tmp_path):  # MODEL-001-S03
    repo, source, _ = seeded(tmp_path)
    source = with_auditor(repo, source)
    v3 = document(repo, capture_profile(repo, source.id, 'З Ревізором', source.revision))
    parse_profile(json.dumps(v3))
    without = {**v3, 'roles': {key: value for key, value in v3['roles'].items() if key != 'auditor'}}
    for bad in [without, {**v3, 'schema_version': 1}, {**v3, 'schema_version': 2}]:
        with pytest.raises(ValueError):
            parse_profile(json.dumps(bad))
    v1 = {**without, 'schema_version': 1}
    assert set(parse_profile(json.dumps(v1)).roles) == set(BASE_ROLES)


@pytest.mark.req('MODEL-001')
def test_auditor_prompt_uuids_are_not_portable(tmp_path):  # MODEL-001-S03
    repo, source, _ = seeded(tmp_path)
    source = with_auditor(repo, source)
    data = document(repo, capture_profile(repo, source.id, 'З Ревізором', source.revision))
    data['roles']['auditor']['settings']['stage_prompt_version_ids'] = {'audit_brief': 'foreign'}
    with pytest.raises(ValueError):
        parse_profile(json.dumps(data))


@pytest.mark.req('MODEL-001')
def test_apply_rejects_a_role_set_that_is_neither_five_nor_four(tmp_path):  # MODEL-001-S03
    repo, source, _ = seeded(tmp_path)
    saved = capture_profile(repo, source.id, 'Профіль', source.revision)
    target = repo.create_story(StoryCreate(title='Ціль'))
    role = RoleSettings(provider=ProviderSettings(model='x')).model_dump()
    with pytest.raises(ValueError):
        repo.role_profiles('apply', story_id=target.id, profile_id=saved['id'], version=1, expected_revision=target.revision,
                           roles={key: role for key in ('planner', 'writer', 'editor')}, evaluator=None)
    assert repo.read_role_settings(target.id) == {}
