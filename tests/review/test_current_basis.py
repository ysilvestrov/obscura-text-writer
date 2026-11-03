import json
import pytest
from tests.review.test_runner import fixture
from storygen.domain import VersionRef
from storygen.run_models import RunRequest


def legacy(root,concern=False):
    values=fixture(root,concern=concern)
    repo,story,first,second,ref,worker,run,calls=values
    with repo.db.connection() as db:
        raw=repo._get(db,'versions',ref.id,VersionRef)
        raw.dependency_snapshot=None;raw.input_refs=[];raw.stale=True
        db.execute('UPDATE versions SET payload=? WHERE id=?',(raw.model_dump_json(),ref.id))
        db.execute('DELETE FROM dependency_edges WHERE target_id=?',(ref.id,))
    return values


def test_legacy_preview_is_current_consistency_without_backfill(tmp_path):
    from storygen.review.readiness import readiness
    repo,story,first,second,ref,worker,run,calls=legacy(tmp_path)
    p=readiness(repo,RunRequest(story_id=story.id,mode='impact',impact_protocol=3))
    assert p['ready'],p['reason']
    assert p['basis_modes'][ref.id]=='current_consistency'
    assert repo.get_version(ref.id).dependency_snapshot is None
    assert not calls


def test_current_capture_includes_prior_prose_without_future_prose(tmp_path):
    from storygen.review.capture import capture
    from storygen.generation.dependencies import save_manual_prose
    repo,story,first,second,ref,worker,run,calls=legacy(tmp_path)
    third=repo.list_scenes(story.id)[2]
    future=save_manual_prose(repo,third.id,'СЕКРЕТ МАЙБУТНЬОЇ ПРОЗИ.',third.revision)
    target=capture(repo.context_view(story.id),ref.id,'current_consistency')
    assert not target.blockers
    assert any(c.new_ref==repo.get_scene(first.id).heads['prose'] for c in target.changes)
    assert all(not c.changed and c.old_text==c.new_text for c in target.changes)
    assert future.id not in target.source_hashes
    assert 'СЕКРЕТ МАЙБУТНЬОЇ ПРОЗИ' not in target.model_dump_json()


def test_legacy_clean_acceptance_and_later_source_change(tmp_path):
    from storygen.generation.dependencies import save_manual_prose
    repo,story,first,second,ref,worker,run,calls=legacy(tmp_path)
    worker._execute(run.id);current=repo.get_run(run.id)
    assert current.state=='completed',current.error
    assert [json.loads(c.user_text)['phase'] for c in calls if c.stage=='review_part']==['check','synthesis']
    assert not repo.get_version(ref.id).stale
    assert repo.get_version(ref.id).dependency_snapshot is None
    save_manual_prose(repo,first.id,'Передумова знову змінилася.',repo.get_scene(first.id).revision)
    assert repo.get_version(ref.id).stale


def test_current_consistency_findings_use_existing_author_checkpoint(tmp_path):
    from storygen.review.decisions import preview,decide
    repo,story,first,second,ref,worker,run,calls=legacy(tmp_path,concern=True)
    worker._execute(run.id);current=repo.get_run(run.id)
    assert current.state=='needs_review',current.error
    p=preview(repo,story.id,run.id)
    assert p['report']['coverage']['plan']['basis_modes'][ref.id]=='current_consistency'
    decide(worker,story.id,run.id,p['fingerprint'],'legacy-dismiss',{c['id']:'reject' for c in p['report']['concerns']})
    worker._execute(run.id)
    assert repo.get_run(run.id).state=='completed'
    assert not repo.get_version(ref.id).stale


def test_legacy_author_revision_keeps_report_basis_and_future_invalidation(tmp_path):
    from storygen.review.decisions import preview,decide,finish
    from storygen.generation.dependencies import save_manual_prose
    repo,story,first,second,ref,worker,run,calls=legacy(tmp_path,concern=True)
    worker._execute(run.id);p=preview(repo,story.id,run.id)
    decide(worker,story.id,run.id,p['fingerprint'],'legacy-fix',{c['id']:'fix' for c in p['report']['concerns']})
    new=save_manual_prose(repo,second.id,'Марія прочитала лист.',repo.get_scene(second.id).revision)
    p=preview(repo,story.id,run.id)
    finish(worker,story.id,run.id,p['fingerprint'],'legacy-finish')
    worker._execute(run.id)
    assert repo.get_run(run.id).state=='completed'
    assert not repo.get_version(new.id).stale
    save_manual_prose(repo,first.id,'Листа ніколи не було.',repo.get_scene(first.id).revision)
    assert repo.get_version(new.id).stale


def test_current_consistency_cannot_hide_corrupt_source(tmp_path):
    from storygen.review.capture import capture
    repo,story,first,second,ref,worker,run,calls=legacy(tmp_path)
    source=repo.get_version(repo.get_scene(first.id).heads['prose'])
    (repo.root/source.relative_path).write_text('Пошкоджено.',encoding='utf-8')
    assert capture(repo.context_view(story.id),ref.id).blockers
    assert not calls


def test_current_basis_survives_backup_and_rechecks_sources(tmp_path):
    from storygen.storage.integrity import check_integrity
    from storygen.storage.backup import create_backup,restore_backup
    from storygen.storage.repository import Repository
    repo,story,first,second,ref,worker,run,calls=legacy(tmp_path/'data')
    worker._execute(run.id)
    assert check_integrity(repo.root).ok
    backup=create_backup(repo.root,tmp_path/'backup')
    restored=Repository(restore_backup(backup,tmp_path/'restored'))
    assert not restored.get_version(ref.id).stale
    assert restored.get_version(ref.id).dependency_snapshot is None


def test_mode_map_rejects_invented_delta_and_invalid_targets(tmp_path):
    from storygen.review.capture import validate_basis
    from storygen.review.planning import prepare_scene
    repo,story,first,second,ref,worker,run,calls=legacy(tmp_path)
    plan=prepare_scene(repo,second.id);validate_basis(plan)
    plan['basis_modes']['foreign']='current_consistency'
    with pytest.raises(ValueError,match='карта'):validate_basis(plan)
    plan['basis_modes'].pop('foreign')
    plan['targets'][0]['changes'][0]['old_text']='Вигадана історія'
    with pytest.raises(ValueError,match='історію'):validate_basis(plan)


@pytest.mark.parametrize('modes',[None,[],{'foreign':[]},'current_consistency'])
def test_malformed_mode_map_is_diagnosed(tmp_path,modes):
    from storygen.review.capture import validate_basis
    with pytest.raises(ValueError,match='карта'):
        validate_basis(dict(targets=[dict(version_id='target')],basis_modes=modes))


def test_frozen_old_plan_has_exact_pre_mode_payload(tmp_path):
    from storygen.review.planning import prepare_scene,check_specs
    from storygen.review.wire import request_for
    repo,story,first,second,ref,worker,run,calls=fixture(tmp_path)
    plan=prepare_scene(repo,second.id);plan.pop('basis_modes')
    spec=check_specs(repo,plan,{})[0]
    payload,body,_=request_for(plan,spec,{})
    assert 'review_basis' not in payload and 'basis_note' not in payload
    expected=dict(phase=spec['phase'],response_character_limit=plan['result_cap'],evidence=payload['evidence'],current_rules=[],children=[],response_schema=payload['response_schema'])
    assert payload==expected
    assert json.loads(body['messages'][1]['content'])==expected


def test_prose_current_basis_tracks_own_brief_and_mixed_modes(tmp_path):
    from storygen.review.planning import prepare_scene
    from storygen.review.capture import capture
    from storygen.storage.snapshots import build_author_baseline
    repo,story,first,second,ref,worker,run,calls=legacy(tmp_path)
    snapshot=build_author_baseline(repo.context_view(story.id),second.id)
    brief=repo.save_version(story.id,second.id,'brief','Марія отримує лист.',list(snapshot.refs),dependency_snapshot=snapshot)
    repo.set_head(second.id,'brief',brief.id,repo.get_scene(second.id).revision)
    with repo.db.connection() as db:
        raw=repo._get(db,'versions',brief.id,VersionRef);raw.stale=True
        # A genuinely changed selector makes the historical target stale.
        next(s for s in raw.dependency_snapshot.selectors if s.kind=='scene' and s.field=='title').expected='Стара назва'
        db.execute('UPDATE versions SET payload=? WHERE id=?',(raw.model_dump_json(),brief.id))
    t=capture(repo.context_view(story.id),ref.id)
    assert not t.blockers and any(c.new_ref==brief.id for c in t.changes)
    plan=prepare_scene(repo,second.id)
    assert plan['basis_modes']=={brief.id:'historical_delta',ref.id:'current_consistency'}


def test_clean_native_legacy_record_is_reinvalidated_after_review(tmp_path):
    from storygen.generation.dependencies import save_manual_prose
    from storygen.review.capture import plan_review
    repo,story,first,second,ref,worker,run,calls=legacy(tmp_path)
    with repo.db.connection() as db:
        raw=repo._get(db,'versions',ref.id,VersionRef);raw.stale=False
        db.execute('UPDATE versions SET payload=? WHERE id=?',(raw.model_dump_json(),ref.id))
        from storygen.domain import Scene
        scene=repo._get(db,'scenes',second.id,Scene);scene.needs_review=True;repo._save_scene(db,scene)
    worker._execute(run.id)
    assert repo.get_run(run.id).state=='completed'
    assert not repo.get_version(ref.id).stale
    save_manual_prose(repo,first.id,'Події передумови змінилися.',repo.get_scene(first.id).revision)
    assert repo.get_version(ref.id).stale
    assert repo.get_scene(second.id).needs_review
    assert any(t.version_id==ref.id for t in plan_review(repo.context_view(story.id)).targets)


def test_author_revised_prose_tracks_review_only_brief_then_explicit_acceptance(tmp_path):
    from storygen.review.decisions import preview,decide,finish
    from storygen.generation.dependencies import save_manual_prose
    from storygen.storage.acceptance import preview_acceptance,accept_version
    repo,story,first,second,ref,worker,run,calls=legacy(tmp_path,concern=True)
    brief=repo.save_version(story.id,second.id,'brief','Марія прочитає лист.',[])
    repo.set_head(second.id,'brief',brief.id,repo.get_scene(second.id).revision)
    worker._execute(run.id);p=preview(repo,story.id,run.id)
    decide(worker,story.id,run.id,p['fingerprint'],'new-fix',{c['id']:'fix' for c in p['report']['concerns']})
    new=save_manual_prose(repo,second.id,'Марія прочитала лист.',repo.get_scene(second.id).revision)
    p=preview(repo,story.id,run.id);finish(worker,story.id,run.id,p['fingerprint'],'new-finish')
    worker._execute(run.id)
    assert repo.get_run(run.id).state=='completed'
    assert not repo.get_version(new.id).stale
    changed=repo.save_version(story.id,second.id,'brief','Марія спалить лист.',[])
    repo.set_head(second.id,'brief',changed.id,repo.get_scene(second.id).revision)
    assert repo.get_version(new.id).stale
    # A later explicit author rebase retains its existing authority.
    p=preview_acceptance(repo,second.id,new.id)
    accept_version(repo,second.id,new.id,p.expected_revision,p.preview_fingerprint)
    assert not repo.get_version(new.id).stale
