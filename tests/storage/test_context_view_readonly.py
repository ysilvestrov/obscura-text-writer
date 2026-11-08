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
    repo, story, scenes = seeded(tmp_path)
    view = repo.context_view(story.id)
    before = _dumps(view)
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
    view = repo.context_view(story_id)
    outputs['status'] = scene_status(view)
    outputs['effective'] = [view.effective_scene(s.id) for s in view.list_scenes(story_id)]
    view = repo.context_view(story_id)
    outputs['freshness'] = {id: snapshots.freshness(view, id) for id in view.versions}
    outputs['public'] = {id: view.get_version(id) for id in view.versions
                         if not view.versions[id].scene_id or not view.scenes[view.versions[id].scene_id].trashed_at}
    return json.dumps(outputs, sort_keys=True, ensure_ascii=False, default=_default)


def test_peek_path_matches_copying_path(tmp_path, monkeypatch):
    stories = [seeded(tmp_path / 'a')[:2], setup(tmp_path / 'b')[:2]]
    repo, story = stories[0]
    hidden = repo.get_scene(repo.context_view(story.id).list_scenes(story.id)[0].id)
    # A trashed scene and a stale prose keep the comparison on non-trivial branches.
    extra = repo.create_scene(story.id, SceneCreate(title='Кошик'))
    repo.set_scene_trashed(story.id, extra.id, extra.revision, restore=False)
    repo.update_scene_metadata(hidden.id, {'title': 'Змінена', 'character_ids': ['a']}, hidden.revision)
    peeked = [_outputs(r, s.id) for r, s in stories]

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
