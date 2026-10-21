import json
import pytest
from storygen.domain import StoryCreate, SceneCreate, RevisionConflict
from storygen.storage.repository import Repository
from storygen.storage.integrity import check_integrity
from storygen.providers.models import RoleSettings, ProviderSettings
from storygen.generation.context import build_context


def setup(tmp_path, kind='edited'):
    repo=Repository(tmp_path)
    story=repo.create_story(StoryCreate(title='Прийняття'))
    scene=repo.create_scene(story.id,SceneCreate(title='Сцена',beats='Початок'))
    draft=repo.save_version(story.id,scene.id,'draft','Чернетка A',[])
    scene=repo.set_head(scene.id,'draft',draft.id,0)
    context=build_context(repo,scene.id,'edit',RoleSettings(provider=ProviderSettings(model='fake'),edit_mode='patches'))
    ref=repo.save_version(story.id,scene.id,kind,'Текст для рішення',[draft.id],dependency_snapshot=context.dependency_snapshot)
    replacement=repo.save_version(story.id,scene.id,'draft','Чернетка B',[])
    repo.set_head(scene.id,'draft',replacement.id,scene.revision)
    assert repo.get_version(ref.id).stale
    return repo,story,scene,ref


def accept(repo,scene,ref):
    preview=repo.preview_acceptance(scene.id,ref.id)
    return repo.accept_version(scene.id,ref.id,preview.expected_revision,preview.preview_fingerprint)


def test_accept_stale_prose_preserves_text_and_model_provenance(tmp_path):
    repo,story,scene,ref=setup(tmp_path)
    before=repo.get_version(ref.id)
    result=accept(repo,scene,ref)
    assert result.scene.heads['prose']==ref.id
    assert not result.version.stale
    assert repo.read_text(ref.id)=='Текст для рішення'
    assert result.version.input_refs==before.input_refs
    assert result.version.sha256==before.sha256
    assert result.version.dependency_snapshot==before.dependency_snapshot
    assert result.acceptance.previous_baseline_id==ref.id
    assert check_integrity(repo.root).ok


def test_accept_draft_creates_new_baseline(tmp_path):
    repo,story,scene,ref=setup(tmp_path,'draft')
    result=accept(repo,scene,ref)
    assert result.scene.heads['draft']==ref.id
    assert result.acceptance.baseline.scope=='author_text'
    assert result.acceptance.baseline.refs!=dict.fromkeys(ref.input_refs)
    again=accept(repo,result.scene,ref)
    assert again.acceptance.id!=result.acceptance.id
    assert again.acceptance.previous_baseline_id==result.acceptance.id
    assert len(repo.list_acceptances(story.id,ref.id))==2


def test_acceptance_does_not_refresh_memory_or_evaluation(tmp_path):
    repo,story,scene,ref=setup(tmp_path)
    # Both derived snapshots predate acceptance, reference exactly this prose ID.
    from storygen.dependency_models import DependencySnapshot
    snapshot=DependencySnapshot(scope='memory',selectors=[],refs={ref.id:ref.sha256},scene_order=[],accepted_stale_prose_ids=[ref.id])
    memory=repo.save_version(story.id,scene.id,'memory','{}',[ref.id],dependency_snapshot=snapshot)
    evaluation=repo.save_version(story.id,scene.id,'evaluation','{}',[ref.id],dependency_snapshot=snapshot)
    accept(repo,scene,ref)
    assert repo.get_version(memory.id).stale
    assert repo.get_version(evaluation.id).stale


def test_preview_race_rolls_back_head_and_ledger(tmp_path):
    repo,story,scene,ref=setup(tmp_path)
    preview=repo.preview_acceptance(scene.id,ref.id)
    repo.update_scene_plan(scene.id,'План змінено',preview.expected_revision)
    before=repo.get_scene(scene.id)
    with pytest.raises(RevisionConflict):
        repo.accept_version(scene.id,ref.id,preview.expected_revision,preview.preview_fingerprint)
    assert repo.get_scene(scene.id)==before
    assert repo.list_acceptances(story.id,ref.id)==[]


@pytest.mark.parametrize('damage',['foreign','incomplete','corrupt','missing','memory','evaluation','brief'])
def test_acceptance_rejects_invalid_version(tmp_path,damage):
    repo,story,scene,ref=setup(tmp_path)
    if damage=='foreign':
        other=repo.create_story(StoryCreate(title='Інший'))
        second=repo.create_scene(other.id,SceneCreate(title='Чужа'))
        ref=repo.save_version(other.id,second.id,'manual','Чужий',[])
    elif damage=='incomplete':
        with repo.db.connection() as db:
            raw=ref.model_dump();raw['complete']=False
            db.execute('UPDATE versions SET payload=? WHERE id=?',(json.dumps(raw),ref.id))
    elif damage in {'corrupt','missing'}:
        path=repo.root/ref.relative_path
        if damage=='missing':path.unlink()
        else:path.write_bytes(b'broken')
    else:
        ref=repo.save_version(story.id,scene.id,damage,'{}',[])
    with pytest.raises((ValueError,KeyError,OSError)):
        repo.preview_acceptance(scene.id,ref.id)
    assert repo.list_acceptances(story.id)==[]


def test_fsck_detects_invalid_acceptance_owner(tmp_path):
    repo,story,scene,ref=setup(tmp_path)
    result=accept(repo,scene,ref)
    with repo.db.connection() as db:
        raw=result.acceptance.model_dump();raw['scene_id']='foreign-scene'
        db.execute('UPDATE app_settings SET payload=? WHERE key=?',(json.dumps(raw),'acceptance:'+story.id+':'+result.acceptance.id))
    assert any(i.code=='invalid_acceptance' for i in check_integrity(repo.root).issues)


@pytest.mark.parametrize('damage',['ref_baseline','duplicate_order'])
def test_fsck_detects_corrupt_acceptance_baseline(tmp_path,damage):
    repo,story,scene,ref=setup(tmp_path)
    current=repo.get_scene(scene.id)
    repo.update_scene_plan(scene.id,'План для авторського рішення',current.revision)
    result=accept(repo,scene,ref)
    assert check_integrity(repo.root).ok
    raw=result.acceptance.model_dump()
    if damage=='ref_baseline':
        plan=repo.get_scene(scene.id).heads['plan']
        raw['baseline']['ref_baselines'][plan]='nonexistent-decision'
    else:raw['baseline']['scene_order'].append(scene.id)
    with repo.db.connection() as db:
        db.execute('UPDATE app_settings SET payload=? WHERE key=?',(json.dumps(raw),'acceptance:'+story.id+':'+result.acceptance.id))
    assert any(i.code=='invalid_acceptance' for i in check_integrity(repo.root).issues)


def test_backup_restore_preserves_acceptance_ledger(tmp_path):
    from storygen.storage.backup import create_backup,restore_backup
    repo,story,scene,ref=setup(tmp_path/'source')
    result=accept(repo,scene,ref)
    backup=create_backup(repo.root,tmp_path/'backup')
    restored=Repository(restore_backup(backup,tmp_path/'restored'))
    assert check_integrity(restored.root).ok
    assert restored.list_acceptances(story.id)==[result.acceptance]
    assert restored.get_scene(scene.id).heads['prose']==ref.id
    assert not restored.get_version(ref.id).stale
    assert restored.get_version(ref.id).sha256==ref.sha256
