import json

import pytest

from storygen.domain import StoryCreate, RevisionConflict
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage.repository import Repository
from storygen.role_profiles import capture_profile, preview_profile, apply_profile, parse_profile, export_profile


def seeded(tmp_path):
    repo=Repository(tmp_path)
    source=repo.create_story(StoryCreate(title='Джерело'))
    from storygen.prompt_contracts import expected_contract
    role=RoleSettings(provider=ProviderSettings(model='local-test'))
    prompt=repo.save_version(source.id,None,'prompt','Пиши природною українською.',[],prompt_contract=expected_contract('draft',role))
    updates={key:role.model_dump() for key in ('planner','writer','editor','memory')}
    updates['writer']={**role.model_dump(),'prompt_version_id':prompt.id}
    repo.write_role_settings(source.id,updates,source.revision)
    return repo,repo.get_story(source.id),prompt


def test_capture_apply_copies_prompts_and_versions_do_not_update_stories(tmp_path):
    repo,source,prompt=seeded(tmp_path)
    saved=capture_profile(repo,source.id,'Локальний',source.revision)
    target=repo.create_story(StoryCreate(title='Ціль'))
    preview=preview_profile(repo,target.id,saved['id'],1,target.revision)
    assert preview['roles']['writer']['provider']['model']=='local-test'
    updated=apply_profile(repo,target.id,saved['id'],1,target.revision)
    assert updated.config_revision==1 and updated.revision==1
    roles=repo.read_role_settings(target.id)
    local=repo.get_version(roles['writer']['prompt_version_id'])
    assert local.story_id==target.id and local.id!=prompt.id
    assert repo.read_text(local.id)==repo.read_text(prompt.id)
    assert local.input_refs==[]
    raw=export_profile(repo,saved['id'],1)
    assert prompt.id not in raw and source.id not in raw
    assert parse_profile(raw).name=='Локальний'
    v2=capture_profile(repo,source.id,'Новий заголовок',source.revision,profile_id=saved['id'],expected_version=1)
    assert v2['version']==2
    assert repo.role_profiles('read',profile_id=saved['id'],version=1)['document']['name']=='Локальний'
    assert repo.read_role_settings(target.id)==roles


def test_profile_and_story_cas_prevent_partial_apply(tmp_path):
    repo,source,_=seeded(tmp_path)
    saved=capture_profile(repo,source.id,'Профіль',source.revision)
    with pytest.raises(RevisionConflict):
        capture_profile(repo,source.id,'Зміна',source.revision,profile_id=saved['id'],expected_version=0)
    target=repo.create_story(StoryCreate(title='Ціль'))
    with pytest.raises(RevisionConflict):
        apply_profile(repo,target.id,saved['id'],1,99)
    assert repo.read_role_settings(target.id)=={}


@pytest.mark.parametrize('change', ['missing_role','foreign_prompt','wrong_contract','secret','calibrated','command'])
def test_import_rejects_unsafe_or_incompatible_document(tmp_path,change):
    repo,source,_=seeded(tmp_path)
    saved=capture_profile(repo,source.id,'Профіль',source.revision)
    data=json.loads(export_profile(repo,saved['id'],1))
    if change=='missing_role':del data['roles']['writer']
    elif change=='foreign_prompt':data['roles']['writer']['settings']['prompt_version_id']='foreign'
    elif change=='wrong_contract':data['roles']['writer']['prompt']['contract']['stage']='edit'
    elif change=='secret':data['roles']['writer']['settings']['provider']['api_key']='private-secret'
    else:
        from storygen.evaluation.story_adapter import EvaluationSettings
        from storygen.evaluation.models import EvaluatorConfig
        data['evaluator']=EvaluationSettings(config=EvaluatorConfig(provider='codex_cli',max_input_chars=1000)).model_dump()
        if change=='calibrated':data['evaluator']['profile']['calibrated']=True
        else:data['evaluator']['config']['codex_command']='malicious.exe'
    with pytest.raises(ValueError) as exc:parse_profile(json.dumps(data))
    assert 'private-secret' not in str(exc.value) and 'malicious.exe' not in str(exc.value)


def test_evaluator_is_optional_and_import_does_not_transfer_calibration(tmp_path):
    from storygen.evaluation.story_adapter import EvaluationSettings, save_evaluation_settings, get_evaluation_settings
    from storygen.evaluation.models import EvaluatorConfig
    repo,source,_=seeded(tmp_path)
    candidate=EvaluationSettings(config=EvaluatorConfig(provider='codex_cli',max_input_chars=1000),policy='off')
    save_evaluation_settings(repo,source.id,candidate)
    source=repo.get_story(source.id)
    with_eval=capture_profile(repo,source.id,'З оцінювачем',source.revision,True)
    without=capture_profile(repo,source.id,'Без оцінювача',source.revision)
    target=repo.create_story(StoryCreate(title='Ціль'))
    updated=apply_profile(repo,target.id,with_eval['id'],1,target.revision)
    assert get_evaluation_settings(repo,target.id).policy=='off'
    apply_profile(repo,target.id,without['id'],1,updated.revision)
    assert get_evaluation_settings(repo,target.id).model_dump()==candidate.model_dump()


def test_size_and_blank_name_are_rejected(tmp_path):
    with pytest.raises(ValueError):parse_profile(' '* (2*1024*1024+1))
    repo,source,_=seeded(tmp_path)
    with pytest.raises(ValueError):capture_profile(repo,source.id,'   ',source.revision)


def test_transaction_rolls_back_roles_when_evaluator_write_fails(tmp_path,monkeypatch):
    repo,source,_=seeded(tmp_path)
    saved=capture_profile(repo,source.id,'Профіль',source.revision)
    target=repo.create_story(StoryCreate(title='Ціль'))
    import storygen.storage.role_profile_store as store
    def fail(*args):raise ValueError('Збій перед commit')
    monkeypatch.setattr(store,'write_application_record',fail)
    with pytest.raises(ValueError,match='Збій'):apply_profile(repo,target.id,saved['id'],1,target.revision)
    assert repo.read_role_settings(target.id)=={}
    assert repo.get_story(target.id).revision==target.revision


def test_applying_profile_preserves_existing_refusal_block(tmp_path):
    from storygen.evaluation.story_adapter import EvaluationSettings, save_evaluation_settings
    from storygen.evaluation.models import EvaluatorConfig, FailureDetail
    from storygen.evaluation.blocks import block_evaluator, get_block
    repo,source,_=seeded(tmp_path)
    config=EvaluatorConfig(provider='local',model='judge',max_input_chars=1000)
    save_evaluation_settings(repo,source.id,EvaluationSettings(config=config))
    source=repo.get_story(source.id)
    saved=capture_profile(repo,source.id,'З оцінювачем',source.revision,True)
    target=repo.create_story(StoryCreate(title='Ціль'))
    block_evaluator(repo,target.id,config,FailureDetail(category='refusal_unknown',message='Відмова'),None,None)
    preview=preview_profile(repo,target.id,saved['id'],1,target.revision)
    assert any('заблоковано' in warning for warning in preview['warnings'])
    apply_profile(repo,target.id,saved['id'],1,target.revision)
    assert get_block(repo,target.id,config)['failure']['category']=='refusal_unknown'


def test_profile_capture_checks_source_revision_again_before_save(tmp_path,monkeypatch):
    repo,source,_=seeded(tmp_path)
    original=repo.role_profiles
    def concurrent(action,**data):
        if action=='save':
            repo.write_role_settings(source.id,repo.read_role_settings(source.id),source.revision)
        return original(action,**data)
    monkeypatch.setattr(repo,'role_profiles',concurrent)
    with pytest.raises(RevisionConflict):capture_profile(repo,source.id,'Конфлікт',source.revision)
    assert original('list')==[]


def test_imported_pause_without_calibration_cannot_partially_apply(tmp_path):
    repo,source,_=seeded(tmp_path)
    saved=capture_profile(repo,source.id,'Профіль',source.revision)
    data=json.loads(export_profile(repo,saved['id'],1))
    from storygen.evaluation.story_adapter import EvaluationSettings
    from storygen.evaluation.models import EvaluatorConfig
    data['evaluator']=EvaluationSettings(config=EvaluatorConfig(provider='local',model='judge',max_input_chars=1000),policy='pause_on_failure').model_dump()
    imported=repo.role_profiles('save',document=parse_profile(json.dumps(data)).model_dump())
    target=repo.create_story(StoryCreate(title='Ціль'))
    with pytest.raises(ValueError,match='калібрування'):apply_profile(repo,target.id,imported['id'],1,target.revision)
    assert repo.read_role_settings(target.id)=={} and repo.read_evaluator_settings(target.id) is None


@pytest.mark.parametrize('raw',['{"name":"one","name":"two"}', '['*2000])
def test_malformed_import_is_safe(raw):
    with pytest.raises(ValueError,match='Некоректний профіль'):parse_profile(raw)
