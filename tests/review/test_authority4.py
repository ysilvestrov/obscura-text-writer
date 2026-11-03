import pytest
from tests.review.test_store import setup,report_for
from storygen.review.store import publish_scene


def api():
    from storygen.storage import repository
    assert hasattr(repository,'review_authority'), 'Збереження авторських пріоритетів ще не реалізовано'
    return repository.review_authority


def sources(repo,scene_id,material='prose'):
    from storygen.review.capture import capture
    from storygen.review.planning4 import registry_for
    from storygen.review.evidence import statement
    view=repo.context_view(repo.get_scene(scene_id).story_id)
    target=capture(view,view.get_scene(scene_id).heads[material],'current_consistency')
    reg=registry_for([target.model_dump()]);rows=[(id,r) for id,r in reg.items() if r['kind']=='source' and r['side']=='new' and r['text']]
    return [statement(reg,dict(ref=id,start=0,end=len(r['text']),quote=r['text'])) for id,r in rows[:2]]


def test_priority_is_append_only_idempotent_and_invalidates_legacy(tmp_path):
    a=api();repo,story,first,second,ref,run,target=setup(tmp_path)
    publish_scene(repo,run.id,report_for(repo,run,target),'author_rejected','legacy-accept')
    assert not repo.get_version(ref.id).stale
    preferred,superseded=sources(repo,second.id)
    kwargs=dict(story_id=story.id,scene_id=second.id,material='prose',expected_revision=0,operation_id='choose',preferred=preferred,superseded=superseded)
    saved=repo.review('priority_decide',**kwargs)
    assert saved['revision']==1
    assert repo.review('priority_decide',**kwargs)==saved
    assert repo.get_version(ref.id).stale
    assert repo.get_scene(second.id).needs_review
    with pytest.raises(ValueError):repo.review('priority_decide',**{**kwargs,'expected_revision':1})
    revoked=repo.review('priority_decide',story_id=story.id,scene_id=second.id,material='prose',expected_revision=1,operation_id='revoke',revoke_id=saved['decision_id'])
    assert revoked['revision']==2 and repo.get_version(ref.id).stale
    assert a.snapshot(repo,story.id,second.id)['priorities']==[]


def test_foreign_hash_and_stale_revision_do_not_create_priority(tmp_path):
    api();repo,story,first,second,ref,run,target=setup(tmp_path)
    preferred,superseded=sources(repo,second.id)
    kw=dict(story_id=story.id,scene_id=second.id,material='prose',expected_revision=0,operation_id='bad',preferred={**preferred,'document_hash':'bad'},superseded=superseded)
    with pytest.raises(ValueError):repo.review('priority_decide',**kw)
    with pytest.raises(ValueError):repo.review('priority_decide',**{**kw,'preferred':preferred,'expected_revision':5})


def test_old_contract_cannot_bypass_new_authority_revision(tmp_path):
    api();repo,story,first,second,ref,run,target=setup(tmp_path)
    preferred,superseded=sources(repo,second.id)
    repo.review('priority_decide',story_id=story.id,scene_id=second.id,material='prose',expected_revision=0,operation_id='choose',preferred=preferred,superseded=superseded)
    with pytest.raises(ValueError):publish_scene(repo,run.id,report_for(repo,run,target),'author_rejected','legacy-bypass')


def test_priority_history_detects_derived_state_tampering(tmp_path):
    import json
    api();repo,story,first,second,ref,run,target=setup(tmp_path)
    preferred,superseded=sources(repo,second.id)
    repo.review('priority_decide',story_id=story.id,scene_id=second.id,material='prose',expected_revision=0,operation_id='choose',preferred=preferred,superseded=superseded)
    with repo.db.connection() as db:
        key='review-authority:'+story.id+':choose'
        data=json.loads(db.execute('SELECT payload FROM app_settings WHERE key=?',(key,)).fetchone()[0]);data['decisions']=[]
        db.execute('UPDATE app_settings SET payload=? WHERE key=?',(json.dumps(data),key))
    with pytest.raises(ValueError):repo.context_view(story.id)


def test_priority_replacement_is_atomic(tmp_path):
    api();repo,story,first,second,ref,run,target=setup(tmp_path)
    preferred,superseded=sources(repo,second.id)
    kw=dict(story_id=story.id,scene_id=second.id,material='prose')
    first=repo.review('priority_decide',**kw,expected_revision=0,operation_id='choose',preferred=preferred,superseded=superseded)
    result=repo.review('priority_decide',**kw,expected_revision=1,operation_id='replace',preferred=superseded,superseded=preferred,replace_id=first['decision_id'])
    policy=repo.review('priorities',story_id=story.id,scene_id=second.id)
    assert result['revision']==2 and len(policy['priorities'])==1
    assert policy['priorities'][0]['preferred_statement_id']==superseded['id']


def test_priority_invalidates_fresh_native_baseline(tmp_path):
    api()
    from tests.impact.test_planning import seeded
    repo,story,first,second,ref=seeded(tmp_path)
    assert not repo.get_version(ref.id).stale
    preferred,superseded=sources(repo,second.id)
    repo.review('priority_decide',story_id=story.id,scene_id=second.id,material='prose',expected_revision=0,operation_id='native',preferred=preferred,superseded=superseded)
    assert repo.get_version(ref.id).stale and repo.get_scene(second.id).needs_review
