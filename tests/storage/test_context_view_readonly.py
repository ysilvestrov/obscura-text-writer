"""Internal peek_* reads and snapshots.freshness share state without copies; public reads still copy."""
import json

import pytest

from storygen.domain import SceneCreate
from storygen.impact.presentation import scene_status
from storygen.storage import snapshots
from storygen.storage.context_view import ContextView
from storygen.storage.snapshots import compare_snapshot, resolve_freshness
from tests.memory.test_forwarding import seeded
from tests.storage.test_freshness import setup


def _dumps(view):
    return (view.story.model_dump(), {k: v.model_dump() for k, v in view.scenes.items()},
            {k: v.model_dump() for k, v in view.versions.items()})


CONTEXT_STAGES = ('brief', 'draft', 'edit', 'memory')


def _configure(repo, story_id):
    """Save local bench roles, so readiness passes the role check and reaches build_context."""
    from storygen.application.workspace_bench import configure_roles
    configure_roles(repo, story_id)


def _contexts(repo, story_id, scene_id, view):
    """Build every stage context for one scene from one captured view, as readiness does."""
    from storygen.authoring.blueprints import get_role_settings
    from storygen.generation.context import build_context
    from storygen.generation.pipeline import STAGE_ROLES
    roles = get_role_settings(repo, story_id)
    built = {}
    for stage in CONTEXT_STAGES:
        try:
            built[stage] = build_context(repo, scene_id, stage, roles[STAGE_ROLES[stage]], view=view)
        except (ValueError, KeyError) as exc:
            built[stage] = f'{type(exc).__name__}: {exc}'
    return built


def _prose_snapshots(view):
    return [v.dependency_snapshot for v in view.versions.values() if v.kind in {'edited', 'manual'} and v.dependency_snapshot]


def test_peek_methods_raise_like_public_ones_for_trashed_scene(tmp_path):
    repo, story, scene, draft, prose = setup(tmp_path)
    second = repo.create_scene(story.id, SceneCreate(title='Друга'))
    view = repo.context_view(story.id)
    snapshot = next(v.dependency_snapshot for v in view.versions.values() if v.id == prose.id)
    selector = snapshot.selectors[0]
    assert selector.owner_id == scene.id
    scene = repo.get_scene(scene.id)
    repo.set_scene_trashed(story.id, scene.id, scene.revision, restore=False)
    view = repo.context_view(story.id)
    with pytest.raises(KeyError):
        view.peek_scene(scene.id)
    with pytest.raises(KeyError):
        view.get_scene(scene.id)
    with pytest.raises(KeyError):
        view.peek_version(prose.id)
    with pytest.raises(KeyError):
        view.get_version(prose.id)
    with pytest.raises(KeyError):
        view.peek_story('missing')
    with pytest.raises(KeyError):
        view.peek_scenes('missing')
    assert [s.id for s in view.peek_scenes(story.id)] == [s.id for s in view.list_scenes(story.id)] == [second.id]
    changes = compare_snapshot(view, snapshot)
    assert any(c.selector == selector and c.reason == 'selector_unavailable' for c in changes)


def test_readiness_and_status_do_not_mutate_view_models(tmp_path):
    from storygen.characters.context import character_material
    repo, story, scenes = seeded(tmp_path)
    _configure(repo, story.id)
    view = repo.context_view(story.id)
    before = _dumps(view)
    # Readiness work on the captured view: every stage context and the character material.
    built = [_contexts(repo, story.id, s.id, view) for s in view.list_scenes(story.id)]
    assert sum(not isinstance(c, str) for item in built for c in item.values()) >= len(scenes)
    for s in view.list_scenes(story.id):
        character_material(view, view.get_story(story.id), view.get_scene(s.id))
    assert _dumps(view) == before
    scene_status(view)
    [view.effective_scene(s.id) for s in view.list_scenes(story.id)]
    changes = [c for snapshot in _prose_snapshots(view) for c in compare_snapshot(view, snapshot)]
    for version_id in view.versions:
        snapshots.freshness(view, version_id)
    assert _dumps(view) == before
    # Changed cast and order make compare_snapshot return list values taken from the view's scenes.
    repo.update_scene_metadata(scenes[0].id, {'character_ids': ['a']}, repo.get_scene(scenes[0].id).revision)
    repo.reorder_scenes(story.id, [s.id for s in reversed(scenes)], repo.get_story(story.id).revision)
    view = repo.context_view(story.id)
    before = _dumps(view)
    changes = [c for snapshot in _prose_snapshots(view) for c in compare_snapshot(view, snapshot)]
    listed = [c for c in changes if isinstance(c.current, list)]
    assert {c.selector.kind for c in listed} >= {'scene', 'order'}
    for change in listed:
        change.current.append('x')
    for scene in view.scenes.values():
        for field in ['character_ids', 'beats']:
            selector = snapshots.DependencySelector(kind='scene', owner_id=scene.id, field=field, expected=None)
            value = snapshots.selector_value(view, selector)
            if isinstance(value, list):
                value.append('x')
    assert _dumps(view) == before


def test_shared_freshness_cache_survives_public_copy_mutation_and_cycle_stays_stale(tmp_path):
    repo, story, scene, draft, prose = setup(tmp_path)
    other = repo.save_version(story.id, scene.id, 'draft', 'B', [])
    repo.set_head(scene.id, 'draft', other.id, repo.get_scene(scene.id).revision)
    view = repo.context_view(story.id)
    public = resolve_freshness(view, prose.id)
    assert public.reasons
    shared = snapshots.freshness(view, prose.id)
    assert snapshots.freshness(view, prose.id) is shared
    count = len(shared.reasons)
    public.reasons.clear()
    resolve_freshness(view, prose.id).reasons.clear()
    assert len(snapshots.freshness(view, prose.id).reasons) == count and shared.stale

    with repo.db.connection() as db:
        raw = json.loads(db.execute('SELECT payload FROM versions WHERE id=?', (prose.id,)).fetchone()[0])
        raw['dependency_snapshot']['refs'] = {prose.id: prose.sha256}
        db.execute('UPDATE versions SET payload=? WHERE id=?', (json.dumps(raw), prose.id))
    view = repo.context_view(story.id)
    assert snapshots.freshness(view, prose.id).stale is True
    assert view.is_stale(prose.id) is True
    assert view.get_version(prose.id).stale is True


def _outputs(repo, story_id):
    from storygen.application.workspace_bench import OPERATIONS, _default, _request
    from storygen.generation.readiness import preview
    scenes = repo.context_view(story_id).list_scenes(story_id)
    outputs = {}
    for scene in scenes:
        for name in OPERATIONS:
            outputs[f'{scene.id}:{name}'] = preview(repo, _request(story_id, scene.id, name))
        # build_context(view=...) output itself (prompt texts, refs, snapshot), not only readiness flags.
        view = repo.context_view(story_id)
        for stage, built in _contexts(repo, story_id, scene.id, view).items():
            outputs[f'{scene.id}:context:{stage}'] = built
    view = repo.context_view(story_id)
    outputs['status'] = scene_status(view)
    outputs['effective'] = [view.effective_scene(s.id) for s in view.list_scenes(story_id)]
    view = repo.context_view(story_id)
    outputs['freshness'] = {id: snapshots.freshness(view, id) for id in view.versions}
    outputs['public'] = {id: view.get_version(id) for id in view.versions
                         if not view.versions[id].scene_id or not view.scenes[view.versions[id].scene_id].trashed_at}
    return json.dumps(outputs, sort_keys=True, ensure_ascii=False, default=_default)


def _accepted_stale_prose(repo, story, scene, prose):
    """Make `prose` stale, accept it, then add a second prose whose snapshot refs form a cycle."""
    other = repo.save_version(story.id, scene.id, 'draft', 'B', [])
    repo.set_head(scene.id, 'draft', other.id, repo.get_scene(scene.id).revision)
    assert repo.get_version(prose.id).stale
    preview = repo.preview_acceptance(scene.id, prose.id)
    repo.accept_version(scene.id, prose.id, preview.expected_revision, preview.preview_fingerprint)
    assert not repo.get_version(prose.id).stale
    cyclic = repo.save_version(story.id, scene.id, 'edited', 'Цикл', [other.id],
                               dependency_snapshot=repo.get_version(prose.id).dependency_snapshot)
    with repo.db.connection() as db:
        raw = json.loads(db.execute('SELECT payload FROM versions WHERE id=?', (cyclic.id,)).fetchone()[0])
        raw['dependency_snapshot']['refs'] = {cyclic.id: cyclic.sha256}
        db.execute('UPDATE versions SET payload=? WHERE id=?', (json.dumps(raw), cyclic.id))
    assert repo.context_view(story.id).is_stale(cyclic.id)


def test_peek_path_matches_copying_path(tmp_path, monkeypatch):
    """Guards peek path vs public copying path within one view.

    The same ContextView logic is run once with shared peek_* models and freshness results and once with
    deep copies of every peek_* result and of snapshots.freshness. Equal outputs prove the result does not
    depend on object sharing. It does not by itself prove equivalence with the pre-change code or with
    correct data: that comes from the workspace_bench digest and the existing freshness, forwarding,
    acceptance and impact suites. The fixtures cover a trashed scene, stale prose, an accepted version,
    a snapshot cycle, a saved forwarding choice and a no_impact review overlay.
    """
    from tests.impact.test_storage import assessed
    from tests.memory.test_forwarding import apply
    from storygen.memory.forwarding import memory_view
    repo, story, scenes = seeded(tmp_path / 'a')
    claim = memory_view(repo, scenes[1].id)['rows'][0]['claim_id']
    apply(repo, scenes[1], {claim: False})
    repo2, story2, scene2, _, _ = setup(tmp_path / 'b')
    _accepted_stale_prose(repo2, story2, scene2, next(v for v in repo2.list_versions(story2.id) if v.kind == 'edited'))
    repo3, story3, _, _, ref3, record3 = assessed(tmp_path / 'c')
    repo3.impact('save_report', record=record3)
    assert not repo3.get_version(ref3.id).stale
    stories = [(repo, story), (repo2, story2), (repo3, story3)]
    for r, s in stories:
        _configure(r, s.id)
    hidden = repo.get_scene(repo.context_view(story.id).list_scenes(story.id)[0].id)
    # A trashed scene and a stale prose keep the comparison on non-trivial branches.
    extra = repo.create_scene(story.id, SceneCreate(title='Кошик'))
    repo.set_scene_trashed(story.id, extra.id, extra.revision, restore=False)
    repo.update_scene_metadata(hidden.id, {'title': 'Змінена', 'character_ids': ['a']}, hidden.revision)
    peeked = [_outputs(r, s.id) for r, s in stories]
    # Each story reaches the full readiness path: ready results and real contexts, no role errors.
    for text in peeked:
        decoded = json.loads(text)
        assert 'Роль не налаштовано' not in text
        assert any(isinstance(v, dict) and v.get('ready') is True for v in decoded.values())
        assert any(isinstance(v, dict) and v.get('fingerprint') for k, v in decoded.items() if ':context:' in k)

    def copying(name):
        original = getattr(ContextView, name)
        return lambda self, id: (lambda value: [v.model_copy(deep=True) for v in value]
                                 if isinstance(value, list) else value.model_copy(deep=True))(original(self, id))
    for name in ['peek_scene', 'peek_scenes', 'peek_version', 'peek_story']:
        monkeypatch.setattr(ContextView, name, copying(name))
    original_freshness = snapshots.freshness
    monkeypatch.setattr(snapshots, 'freshness', lambda view, id: original_freshness(view, id).model_copy(deep=True))
    copied = [_outputs(r, s.id) for r, s in stories]
    assert peeked == copied


def test_second_request_sees_change_made_between_requests(tmp_path):
    """No state crosses requests: each readiness call and ContextView is built fresh from the database."""
    from storygen.application.workspace_bench import OPERATIONS, _default, _request
    from storygen.generation.readiness import preview
    repo, story, scene, draft, prose = setup(tmp_path)
    _configure(repo, story.id)

    def request():
        view = repo.context_view(story.id)
        return (resolve_freshness(view, prose.id).stale,
                json.dumps(scene_status(view), default=_default, sort_keys=True),
                [json.dumps(preview(repo, _request(story.id, scene.id, name)), default=_default, sort_keys=True)
                 for name in OPERATIONS])
    def ready(result):
        return {name for name, text in zip(OPERATIONS, result[2]) if json.loads(text)['ready']}
    first = request()
    assert first == request()
    # memory and rebuild_memory pass the role check and build_context; brief waits for a scene plan.
    assert ready(first) == {'memory', 'rebuild_memory'}
    other = repo.save_version(story.id, scene.id, 'draft', 'B', [])
    repo.set_head(scene.id, 'draft', other.id, repo.get_scene(scene.id).revision)
    second = request()
    assert first[0] is False and second[0] is True
    assert second[1] != first[1]
    # The stale prose is seen by the second readiness request too (edit_loop reason changes).
    assert second[2] != first[2]
    repo.set_head(scene.id, 'draft', draft.id, repo.get_scene(scene.id).revision)
    assert request() == first
    # A plan saved between requests makes brief ready: build_context runs on a fresh view.
    current = repo.get_scene(scene.id)
    repo.update_scene_plan(scene.id, 'План', current.revision)
    assert 'brief' in ready(request()) and 'brief' not in ready(first)
