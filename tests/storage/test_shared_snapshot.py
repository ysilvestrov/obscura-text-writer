"""PERF-001-S06: a story snapshot shared by the reads of one data generation (#39, part 2)."""
import itertools
import json
import threading

import pytest

from storygen.storage.material_status import material_status
from storygen.storage import snapshots
from storygen.storage.context_view import ContextView
from tests.storage.test_freshness import setup



def private_view(repo, story_id):
    with repo.db.connection() as db:
        db.execute('BEGIN')
        return ContextView(repo, db, story_id)


def dumped(result):
    return result.model_dump(mode='json')


def test_reads_of_one_generation_share_state(tmp_path):
    repo, story, scene, draft, prose = setup(tmp_path)
    a = repo.context_view(story.id)
    b = repo.context_view(story.id)
    assert a.scenes is b.scenes and a.versions is b.versions
    a.is_stale(prose.id)
    assert prose.id in b.freshness_cache
    assert a.resolving is not b.resolving


def test_repository_reads_share_the_snapshot(tmp_path):
    repo, story, scene, draft, prose = setup(tmp_path)
    view = repo.context_view(story.id)
    view.is_stale(prose.id)
    assert repo.scene_view(scene.id).versions is view.versions
    calls = []
    original = snapshots._compute_freshness
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(snapshots, '_compute_freshness', lambda v, i: (calls.append(i), original(v, i))[1])
        repo.get_scene(scene.id)
        repo.get_version(prose.id)
    assert prose.id not in calls


def test_write_starts_a_new_generation(tmp_path):
    # VALID-LINKS: a draft change no longer marks the prose head; the generation is observed on a non-head version
    repo, story, scene, draft, prose = setup(tmp_path, head=False)
    before = repo.context_view(story.id)
    assert before.is_stale(prose.id) is False
    other = repo.save_version(story.id, scene.id, 'draft', 'B', [])
    repo.set_head(scene.id, 'draft', other.id, repo.get_scene(scene.id).revision)
    after = repo.context_view(story.id)
    assert after.versions is not before.versions
    assert after.is_stale(prose.id) is True
    assert repo.get_version(prose.id).stale is True


def test_commit_between_open_and_capture_keeps_view_private(tmp_path, monkeypatch):
    repo, story, scene, draft, prose = setup(tmp_path)
    original = ContextView.__init__
    fired = []

    def init(self, *args):
        if not fired:  # another connection commits while this one is capturing
            fired.append(1)
            with repo.db.connection() as db:
                db.execute("INSERT INTO app_settings(key,payload) VALUES('probe','{}')")
        original(self, *args)
    monkeypatch.setattr(ContextView, '__init__', init)
    first = repo.context_view(story.id)
    second = repo.context_view(story.id)
    assert first.versions is not second.versions
    assert repo.context_view(story.id).versions is second.versions


def test_older_generation_never_replaces_newer(tmp_path):
    from storygen.storage.shared_snapshot import SnapshotStore
    store = SnapshotStore()
    assert store.publish('s', 4, 'new') == 'new'
    assert store.publish('s', 2, 'old') is None
    assert store.get('s', 4) == 'new' and store.get('s', 2) is None


def test_store_keeps_a_bounded_number_of_stories(tmp_path):
    from storygen.storage.shared_snapshot import SnapshotStore
    store = SnapshotStore(limit=2)
    for name in 'abc':
        store.publish(name, 2, name)
    assert store.get('a', 2) is None and store.get('c', 2) == 'c'


def test_write_transaction_view_is_private(tmp_path):
    repo, story, scene, draft, prose = setup(tmp_path)
    shared = repo.context_view(story.id)
    with pytest.raises(RuntimeError), repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        view = ContextView(repo, db, story.id)
        assert view.scenes is not shared.scenes
        view.scenes[scene.id].title = 'Зіпсовано'  # a buggy write into a model, then the transaction fails
        raise RuntimeError
    assert repo.context_view(story.id).peek_scene(scene.id).title == 'Сцена'


def _cycle(repo, story, scene, prose):
    """X -> A -> B -> C -> A: versions whose dependency snapshots refer to each other."""
    with repo.db.connection() as db:
        template = json.loads(db.execute('SELECT payload FROM versions WHERE id=?', (prose.id,)).fetchone()[0])['dependency_snapshot']
    ids = {name: repo.save_version(story.id, scene.id, 'edited', name, [], dependency_snapshot=template) for name in 'XABC'}
    links = {'X': 'A', 'A': 'B', 'B': 'C', 'C': 'A'}
    with repo.db.connection() as db:
        for name, target in links.items():
            row = json.loads(db.execute('SELECT payload FROM versions WHERE id=?', (ids[name].id,)).fetchone()[0])
            row['dependency_snapshot']['refs'] = {ids[target].id: ids[target].sha256}
            row['dependency_snapshot']['ref_baselines'] = {ids[target].id: None}
            db.execute('UPDATE versions SET payload=? WHERE id=?', (json.dumps(row), ids[name].id))
    return [ids[n].id for n in 'XABC']


def test_cycle_results_match_a_private_view_in_every_order(tmp_path):
    repo, story, scene, draft, prose = setup(tmp_path)
    ids = _cycle(repo, story, scene, prose)
    orders = list(itertools.permutations(ids))[:8]
    for first, second in zip(orders, orders[1:]):
        repo.db.bump_generation()
        for order in (first, second):  # two requests of one generation, each in its own order
            shared = repo.context_view(story.id)
            private = private_view(repo, story.id)
            assert [dumped(snapshots.freshness(shared, i)) for i in order] == [dumped(snapshots.freshness(private, i)) for i in order]
    shared = repo.context_view(story.id)
    assert any(r.reason == 'dependency_cycle' for r in snapshots.freshness(shared, ids[1]).reasons)
    assert not any(i in shared.freshness_cache.shared for i in ids)


def test_parallel_requests_compute_top_level_once(tmp_path, monkeypatch):
    repo, story, scene, draft, prose = setup(tmp_path)
    repo.db.bump_generation()
    calls = []
    original = snapshots._compute_freshness

    def counting(view, id):
        if id == prose.id:
            calls.append(id)
        return original(view, id)
    monkeypatch.setattr(snapshots, '_compute_freshness', counting)
    views = [repo.context_view(story.id) for _ in range(4)]
    barrier = threading.Barrier(4)
    threads = [threading.Thread(target=lambda v=v: (barrier.wait(), v.is_stale(prose.id))) for v in views]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert calls == [prose.id]


def _outputs(repo, story_id, view):
    from storygen.application.workspace_bench import OPERATIONS, _default, _request
    from storygen.generation.readiness import preview
    scenes = view.peek_scenes(story_id)
    return json.dumps({
        'status': material_status(view),
        'fresh': {v: dumped(snapshots.freshness(view, v)) for v in sorted(view.versions)},
        'ready': {name: preview(repo, _request(story_id, scenes[-1].id, name), view) for name in OPERATIONS},
    }, default=_default, sort_keys=True)


def test_shared_equals_private_after_writes(tmp_path):
    from tests.storage.test_context_view_readonly import _configure
    repo, story, scene, draft, prose = setup(tmp_path)
    _configure(repo, story.id)

    def compare():
        shared = repo.context_view(story.id)
        reused = repo.context_view(story.id)  # a second read of the generation reuses the published state
        assert reused.shared_lock is shared.shared_lock is not None
        expected = _outputs(repo, story.id, private_view(repo, story.id))
        assert _outputs(repo, story.id, shared) == expected
        assert _outputs(repo, story.id, reused) == expected
    compare()
    other = repo.save_version(story.id, scene.id, 'draft', 'B', [])
    repo.set_head(scene.id, 'draft', other.id, repo.get_scene(scene.id).revision)
    compare()
    repo.set_head(scene.id, 'draft', draft.id, repo.get_scene(scene.id).revision)
    compare()


def test_trashed_story_and_scene_raise_like_private(tmp_path):
    from storygen.domain import SceneCreate
    repo, story, scene, draft, prose = setup(tmp_path)
    extra = repo.create_scene(story.id, SceneCreate(title='Кошик'))
    repo.set_scene_trashed(story.id, extra.id, extra.revision, restore=False)
    repo.context_view(story.id)
    for view in (repo.context_view(story.id), private_view(repo, story.id)):
        with pytest.raises(KeyError):
            view.peek_scene(extra.id)
    with pytest.raises(KeyError):
        repo.get_scene(extra.id)
    repo.set_story_trashed(story.id, repo.get_story(story.id).revision, restore=False)
    with pytest.raises(KeyError):
        repo.context_view(story.id)


def _counting_reads(monkeypatch, repo):
    reads = []
    original = type(repo.files).read

    def read(self, path, sha):
        reads.append(path)
        return original(self, path, sha)
    monkeypatch.setattr(type(repo.files), 'read', read)
    return reads


def test_blob_reused_across_generations_only_with_same_stat(tmp_path, monkeypatch):
    import os
    repo, story, scene, draft, prose = setup(tmp_path)
    repo.context_view(story.id).is_stale(prose.id)
    reads = _counting_reads(monkeypatch, repo)
    repo.db.bump_generation()
    repo.context_view(story.id).is_stale(prose.id)
    assert prose.relative_path not in reads
    path = repo.files.resolve(prose.relative_path)
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    repo.db.bump_generation()
    repo.context_view(story.id).is_stale(prose.id)
    assert prose.relative_path in reads


@pytest.mark.parametrize('damage', ['delete', 'replace'])
def test_damaged_file_gives_integrity_error_next_generation(tmp_path, damage):
    repo, story, scene, draft, prose = setup(tmp_path)
    assert repo.context_view(story.id).is_stale(prose.id) is False
    path = repo.files.resolve(prose.relative_path)
    if damage == 'delete':
        path.unlink()
    else:
        path.write_bytes('Інший текст іншої довжини'.encode())
    repo.db.bump_generation()
    reasons = snapshots.freshness(repo.context_view(story.id), prose.id).reasons
    assert any(r.reason == 'integrity_error' for r in reasons)


def test_cards_and_journals_parsed_once_across_a_write(tmp_path, monkeypatch):
    import storygen.characters.models as character_models
    import storygen.memory.journal as journal
    from storygen.application.workspace_bench import build_story
    from storygen.storage.repository import Repository
    repo = Repository(tmp_path)
    story_id = build_story(repo, 3, cast=True)
    material_status(repo.context_view(story_id))
    calls = []
    for module, name in [(character_models, 'load_characters'), (journal, 'load_memory')]:
        original = getattr(module, name)
        monkeypatch.setattr(module, name, lambda *a, _o=original, _n=name, **k: (calls.append(_n), _o(*a, **k))[1])
    repo.db.bump_generation()
    view = repo.context_view(story_id)
    material_status(view)
    assert calls == []


def test_scene_values_start_again_in_a_new_generation(tmp_path):
    from storygen.application.workspace_bench import build_story
    from storygen.storage.repository import Repository
    repo = Repository(tmp_path)
    story_id = build_story(repo, 3, cast=True)
    view = repo.context_view(story_id)
    material_status(view)
    # VALID-LINKS: heads are marked by their links, so material_status computes the scene's links ('links' memo), not
    # the snapshot comparison that memoised 'tracked'
    assert any(key[0] == 'links' for key in view.memo_cache)
    repo.db.bump_generation()
    fresh = repo.context_view(story_id)
    assert fresh.memo_cache is not view.memo_cache
    # Only parses of one version's file carry over (ImmutableStore); scene values are computed again.
    assert not any(key[0][0] in {'names', 'policy', 'tracked', 'links'} for key in repo.immutable.parses)
    material_status(fresh)
    assert any(key[0] == 'links' for key in fresh.memo_cache)


def test_second_capture_of_a_generation_adopts_the_published_state(tmp_path, monkeypatch):
    from storygen.storage.shared_snapshot import read_view
    repo, story, scene, draft, prose = setup(tmp_path)
    with repo.db.connection() as a, repo.db.connection() as b:
        first = read_view(repo, a, story.id)
        # b missed the store before a published (both captured in parallel).
        monkeypatch.setattr(repo.snapshots, 'get', lambda *args: None)
        second = read_view(repo, b, story.id)
    assert first.shared_lock is not None
    assert second.shared_lock is first.shared_lock
    assert second.versions is first.versions


def test_peek_journal_parse_carries_over_generations(tmp_path, monkeypatch):
    import storygen.memory.journal as journal
    from storygen.application.workspace_bench import build_story
    from storygen.memory.previous import previous_memory, read_previous_journal
    from storygen.storage.repository import Repository
    repo = Repository(tmp_path)
    story_id = build_story(repo, 3, cast=True)
    view = repo.context_view(story_id)
    scene = view.list_scenes(story_id)[-1]
    previous = previous_memory(view, scene, peek=True)
    assert previous.memory_id
    read_previous_journal(view, previous, peek=True)
    calls = []
    original = journal.load_memory
    monkeypatch.setattr(journal, 'load_memory', lambda *a, **k: (calls.append(1), original(*a, **k))[1])
    repo.db.bump_generation()
    read_previous_journal(repo.context_view(story_id), previous, peek=True)
    assert calls == []
