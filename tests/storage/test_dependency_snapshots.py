import pytest
from pydantic import ValidationError

from storygen.domain import StoryCreate, SceneCreate
from storygen.storage.repository import Repository
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.dependency_models import DependencySnapshot
from storygen.storage.snapshots import build_dependency_snapshot, compare_snapshot
from storygen.generation.context import build_context


def fixture(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Знімки'))
    scenes = [repo.create_scene(story.id, SceneCreate(title=str(i), beats='План')) for i in range(3)]
    return repo, story, scenes


def role(**changes):
    return RoleSettings(provider=ProviderSettings(model='fake'), **changes)


def test_context_view_does_not_mix_heads_from_two_transactions(tmp_path):
    repo, story, scenes = fixture(tmp_path)
    old = repo.save_version(story.id, scenes[0].id, 'draft', 'Старий текст', [])
    repo.set_head(scenes[0].id, 'draft', old.id, 0)
    view = repo.context_view(story.id)
    new = repo.save_version(story.id, scenes[0].id, 'draft', 'Новий текст', [])
    repo.set_head(scenes[0].id, 'draft', new.id, 1)
    assert view.get_scene(scenes[0].id).heads['draft'] == old.id
    assert view.read_text(old.id) == 'Старий текст'
    assert repo.context_view(story.id).get_scene(scenes[0].id).heads['draft'] == new.id
    # Returned domain objects cannot mutate captured metadata.
    view.get_scene(scenes[0].id).heads['draft'] = new.id
    assert view.get_scene(scenes[0].id).heads['draft'] == old.id


def test_snapshot_records_missing_canon(tmp_path):
    repo, story, scenes = fixture(tmp_path)
    context = build_context(repo, scenes[0].id, 'brief', role())
    selectors = context.dependency_snapshot.selectors
    missing = next(s for s in selectors if s.kind == 'story' and s.field == 'canon_version_id')
    assert missing.owner_id == story.id and missing.expected is None
    canon = repo.save_version(story.id, None, 'canon', 'Новий канон', [])
    # Simulate concurrent authoritative material installation.
    with repo.db.connection() as db:
        current = repo._active_story(db, story.id)
        current.canon_version_id = canon.id
        repo._save_story(db, current)
    assert any(c.selector.field == 'canon_version_id' and c.current == canon.id for c in compare_snapshot(repo.context_view(story.id), context.dependency_snapshot))


def test_memory_tracks_only_prefix_order(tmp_path):
    repo, story, scenes = fixture(tmp_path)
    view = repo.context_view(story.id)
    snapshot = build_dependency_snapshot(view, scenes[1].id, 'memory', role(), [])
    assert snapshot.scene_order == [s.id for s in scenes[:2]]
    assert all(s.owner_id != scenes[2].id for s in snapshot.selectors)


def test_patches_ignore_unread_scene_metadata(tmp_path):
    repo, story, scenes = fixture(tmp_path)
    draft = repo.save_version(story.id, scenes[0].id, 'draft', 'Чернетка', [])
    repo.set_head(scenes[0].id, 'draft', draft.id, 0)
    context = build_context(repo, scenes[0].id, 'edit', role(edit_mode='patches'))
    repo.update_scene_metadata(scenes[1].id, {'title': 'Інше'}, 0)
    assert not compare_snapshot(repo.context_view(story.id), context.dependency_snapshot)
    assert context.dependency_snapshot.scene_order == []
    assert context.target_cas.head == 'prose'


def test_unknown_snapshot_version_fails_closed():
    with pytest.raises(ValidationError):
        DependencySnapshot(schema_version=2, scope='memory', selectors=[], refs={}, scene_order=[])


def test_context_view_retains_one_snapshot_during_concurrent_commit(tmp_path,monkeypatch):
    repo,story,scenes=fixture(tmp_path)
    first=repo.save_version(story.id,scenes[0].id,'draft','A',[])
    repo.set_head(scenes[0].id,'draft',first.id,0)
    second=repo.save_version(story.id,scenes[0].id,'draft','B',[])
    original=repo._active_story
    changed=False
    def read_story(db,id):
        nonlocal changed
        captured=original(db,id)
        if not changed:
            changed=True
            # WAL commit on another connection after first SELECT, before heads SELECT.
            Repository(tmp_path).set_head(scenes[0].id,'draft',second.id,1)
        return captured
    monkeypatch.setattr(repo,'_active_story',read_story)
    view=repo.context_view(story.id)
    assert view.get_scene(scenes[0].id).heads['draft']==first.id
    assert Repository(tmp_path).get_scene(scenes[0].id).heads['draft']==second.id
