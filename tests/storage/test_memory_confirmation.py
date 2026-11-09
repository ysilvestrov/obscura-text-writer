import pytest
from storygen.domain import RevisionConflict
from storygen.memory.reuse import MemoryApprovalRequired
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage.snapshots import build_dependency_snapshot, compare_snapshot, resolve_freshness
from tests.memory.test_author_reuse import workspace
from tests.storage.test_memory_core_selectors import memory_version, setup



def test_confirm_sets_field_without_touching_bytes(tmp_path):
    repo, first, second, old, new, memory, role = workspace(tmp_path)
    scene = repo.get_scene(first.id)
    before = repo.get_version(memory.id)
    assert before.memory_confirmation is None
    text = repo.read_text(memory.id)
    got = repo.confirm_memory(first.id, memory.id, scene.revision)
    after = repo.get_version(memory.id)
    assert got.memory_confirmation.by == 'author' and after.memory_confirmation.by == 'author'
    assert after.memory_confirmation.confirmed_at
    assert after.sha256 == before.sha256 and repo.read_text(memory.id) == text
    assert repo.get_scene(first.id).revision == scene.revision


def test_post_conflict_when_head_changed(tmp_path):
    repo, first, second, old, new, memory, role = workspace(tmp_path)
    scene = repo.get_scene(first.id)
    other = repo.save_version(first.story_id, first.id, 'memory', '{}', [])
    with pytest.raises(RevisionConflict):
        repo.confirm_memory(first.id, other.id, scene.revision)
    with pytest.raises(RevisionConflict):
        repo.confirm_memory(first.id, memory.id, scene.revision - 1)
    repo.set_head(first.id, 'memory', other.id, scene.revision)
    with pytest.raises(RevisionConflict):
        repo.confirm_memory(first.id, memory.id, repo.get_scene(first.id).revision)
    assert repo.get_version(memory.id).memory_confirmation is None
    assert repo.get_version(other.id).memory_confirmation is None


def test_confirmation_does_not_stale_next_scene(tmp_path):
    repo, story, (s1, s2) = setup(tmp_path)
    role = RoleSettings(provider=ProviderSettings(model='fake'))
    m1, _ = memory_version(repo, story, s1)
    repo.set_head(s1.id, 'memory', m1.id, repo.get_scene(s1.id).revision)
    snap = build_dependency_snapshot(repo.context_view(story.id), s2.id, 'memory', role, [m1.id])
    m2 = repo.save_version(story.id, s2.id, 'memory', '{}', [m1.id], dependency_snapshot=snap)

    def state():
        view = repo.context_view(story.id)
        return resolve_freshness(view, m2.id).stale, compare_snapshot(view, repo.get_version(m2.id).dependency_snapshot)

    assert state() == (False, [])
    repo.confirm_memory(s1.id, m1.id, repo.get_scene(s1.id).revision)
    assert state() == (False, [])


def test_new_head_is_unconfirmed(tmp_path):
    repo, first, second, old, new, memory, role = workspace(tmp_path)
    repo.confirm_memory(first.id, memory.id, repo.get_scene(first.id).revision)
    fresh = repo.save_version(first.story_id, first.id, 'memory', '{}', [])
    repo.set_head(first.id, 'memory', fresh.id, repo.get_scene(first.id).revision)
    assert repo.get_version(fresh.id).memory_confirmation is None
    assert repo.get_version(memory.id).memory_confirmation is not None


def test_confirmation_not_in_reuse_fingerprint(tmp_path):
    from storygen.memory.reuse import memory_for_update
    repo, first, second, old, new, memory, role = workspace(tmp_path, changed=True)

    def fingerprint():
        with pytest.raises(MemoryApprovalRequired) as caught:
            memory_for_update(repo.context_view(second.story_id), second.id)
        return caught.value.review['fingerprint']

    before = fingerprint()
    repo.confirm_memory(first.id, memory.id, repo.get_scene(first.id).revision)
    assert fingerprint() == before
