from storygen.generation.assisted_writing import build_rewrite_context
from storygen.storage.snapshots import compare_snapshot

def test_frozen_source_is_not_a_live_head_selector(rewrite_case):
    repo,scene,source,notes,role,request=rewrite_case
    ctx=build_rewrite_context(repo,request)
    assert not any(s.kind=='head' and s.field=='draft' for s in ctx.dependency_snapshot.selectors)
    assert source.id in ctx.dependency_snapshot.refs
    new=repo.save_version(scene.story_id,scene.id,'draft','Інша чернетка.',[])
    repo.set_head(scene.id,'draft',new.id,repo.get_scene(scene.id).revision)
    assert compare_snapshot(repo.context_view(scene.story_id),ctx.dependency_snapshot)==[]


def test_external_plan_dependency_still_invalidates(rewrite_case):
    repo,scene,source,notes,role,request=rewrite_case
    ctx=build_rewrite_context(repo,request)
    plan=repo.save_version(scene.story_id,scene.id,'scene_plan','Новий план.',[])
    repo.set_head(scene.id,'plan',plan.id,repo.get_scene(scene.id).revision)
    assert any(c.reason=='selector_changed' for c in compare_snapshot(repo.context_view(scene.story_id),ctx.dependency_snapshot))


def test_frozen_source_still_checks_exact_hash(rewrite_case):
    repo,scene,source,notes,role,request=rewrite_case
    ctx=build_rewrite_context(repo,request)
    repo.files.resolve(source.relative_path).write_text('Пошкодження',encoding='utf-8')
    assert any(c.reason=='source_unavailable' for c in compare_snapshot(repo.context_view(scene.story_id),ctx.dependency_snapshot))
