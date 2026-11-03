"""Independent review reproductions: all faults fail closed before inference."""
import pytest
from storygen.domain import Story,Scene,SceneCreate
from storygen.memory.models import MemorySnapshot,MemoryEntry
from storygen.impact.planning import capture_target,plan_impact
from storygen.generation.dependencies import save_manual_prose
from storygen.run_models import RunRequest
from tests.impact.test_storage import assessed
from tests.impact.test_runner import runner


@pytest.mark.parametrize('field,value_kind',[('canon','missing'),('canon','wrong_kind'),('prose','missing')])
def test_missing_or_wrong_kind_version_selector_blocks_analysis(tmp_path,field,value_kind):
    repo,story,first,second,ref,record=assessed(tmp_path)
    with repo.db.connection() as db:
        if field=='canon':
            item=repo._get(db,'stories',story.id,Story);item.canon_version_id='missing-source' if value_kind=='missing' else ref.id;repo._save_story(db,item)
        else:
            item=repo._get(db,'scenes',first.id,Scene);item.heads['prose']='missing-source';repo._save_scene(db,item)
    target=capture_target(repo.context_view(story.id),ref.id)
    assert target.blockers
    assert repo.get_version(ref.id).stale


@pytest.mark.parametrize('historical',[False,True])
def test_dependency_memory_requires_exact_historical_quotes(tmp_path,historical):
    repo,story,first,second,ref,record=assessed(tmp_path)
    prose=repo.get_scene(first.id).heads['prose']
    bad=MemorySnapshot(source_prose_ids=[prose],facts=[MemoryEntry(text='Подія.',source_version_id=prose,quote='THIS QUOTE DOES NOT EXIST')])
    memory=repo.save_version(story.id,first.id,'memory',bad.model_dump_json(),[])
    repo.set_head(first.id,'memory',memory.id,repo.get_scene(first.id).revision)
    if historical:
        # Freeze a target with the bad historical journal, then publish a valid current one.
        current=save_manual_prose(repo,second.id,'Авторська згадка.',repo.get_scene(second.id).revision)
        bad.facts[0].quote=repo.read_text(prose)
        good=repo.save_version(story.id,first.id,'memory',bad.model_dump_json(),[])
        repo.set_head(first.id,'memory',good.id,repo.get_scene(first.id).revision)
        ref=current
    target=capture_target(repo.context_view(story.id),ref.id)
    assert target.blockers


def test_future_append_does_not_revoke_prefix_only_assessment(tmp_path):
    repo,story,first,second,ref,worker,old,calls=runner(tmp_path)
    worker.cancel(old.id)
    original=next(id for id in ref.dependency_snapshot.refs if repo.get_version(id).scene_id==first.id)
    repo.set_head(first.id,'prose',original,repo.get_scene(first.id).revision)
    manual=save_manual_prose(repo,second.id,'Авторська згадка про лист.',repo.get_scene(second.id).revision)
    save_manual_prose(repo,first.id,'Марія знає про лист. Вечір настав.',repo.get_scene(first.id).revision)
    plan=plan_impact(repo.context_view(story.id))
    run=worker.enqueue(RunRequest(story_id=story.id,mode='impact',impact_plan_fingerprint=plan.fingerprint),'prefix-checked')
    worker._execute(run.id)
    assert worker.get_run(run.id).state=='completed'
    assert not repo.get_version(manual.id).stale
    repo.create_scene(story.id,SceneCreate(title='Майбутній епілог'))
    assert not repo.get_version(manual.id).stale
