import json
import pytest
from storygen.domain import StoryCreate, SceneCreate
from storygen.storage.repository import Repository
from storygen.providers.models import RoleSettings, ProviderSettings
from storygen.generation.context import build_context
from storygen.storage.snapshots import resolve_freshness, compare_snapshot
from storygen.storage.integrity import check_integrity
from storygen.application.exports import export_story


def setup(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Актуальність'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена'))
    draft = repo.save_version(story.id, scene.id, 'draft', 'A', [])
    scene = repo.set_head(scene.id, 'draft', draft.id, 0)
    context = build_context(repo, scene.id, 'edit', RoleSettings(provider=ProviderSettings(model='fake'), edit_mode='patches'))
    prose = repo.save_version(story.id, scene.id, 'edited', 'Результат', [draft.id], dependency_snapshot=context.dependency_snapshot)
    scene = repo.set_head(scene.id, 'prose', prose.id, scene.revision)
    return repo, story, scene, draft, prose


def test_new_version_recovers_after_dependency_a_b_a(tmp_path):
    repo, story, scene, draft, prose = setup(tmp_path)
    other = repo.save_version(story.id, scene.id, 'draft', 'B', [])
    scene = repo.set_head(scene.id, 'draft', other.id, scene.revision)
    assert repo.get_version(prose.id).stale
    reasons = resolve_freshness(repo.context_view(story.id), prose.id).reasons
    assert any(c.selector and c.selector.field == 'draft' and c.current == other.id for c in reasons)
    repo.set_head(scene.id, 'draft', draft.id, scene.revision)
    assert not repo.get_version(prose.id).stale
    assert not repo.get_scene(scene.id).needs_review
    assert not next(v for v in repo.list_versions(story.id) if v.id == prose.id).stale


def test_legacy_stale_never_recovers_without_acceptance(tmp_path):
    repo, story, scene, draft, _ = setup(tmp_path)
    legacy = repo.save_version(story.id, scene.id, 'edited', 'Старий', [draft.id])
    other = repo.save_version(story.id, scene.id, 'draft', 'B', [])
    scene = repo.set_head(scene.id, 'draft', other.id, scene.revision)
    repo.set_head(scene.id, 'draft', draft.id, scene.revision)
    assert repo.get_version(legacy.id).stale
    assert any(c.reason == 'legacy_stale' for c in resolve_freshness(repo.context_view(story.id), legacy.id).reasons)


def test_adding_or_trashing_scene_changes_relevant_order(tmp_path):
    repo, story, scene, draft, prose = setup(tmp_path)
    role = RoleSettings(provider=ProviderSettings(model='fake'))
    context = build_context(repo, scene.id, 'brief', role)
    new = repo.create_scene(story.id, SceneCreate(title='Друга'))
    assert any(c.selector and c.selector.kind == 'order' for c in compare_snapshot(repo.context_view(story.id), context.dependency_snapshot))
    repo.set_scene_trashed(story.id, new.id, new.revision, restore=False)
    assert not compare_snapshot(repo.context_view(story.id), context.dependency_snapshot)


def test_export_and_context_agree_on_freshness(tmp_path):
    repo, story, scene, draft, prose = setup(tmp_path)
    other = repo.save_version(story.id, scene.id, 'draft', 'B', [])
    scene = repo.set_head(scene.id, 'draft', other.id, scene.revision)
    with pytest.raises(ValueError):export_story(repo, story.id, 'txt')
    repo.set_head(scene.id, 'draft', draft.id, scene.revision)
    assert not repo.context_view(story.id).get_version(prose.id).stale
    assert not repo.export_snapshot(story.id)[1][0][1].stale
    assert export_story(repo, story.id, 'txt').is_file()


def test_snapshot_refs_corruption_is_reported_by_fsck(tmp_path):
    repo, story, scene, draft, prose = setup(tmp_path)
    with repo.db.connection() as db:
        raw = json.loads(db.execute('SELECT payload FROM versions WHERE id=?', (prose.id,)).fetchone()[0])
        raw['dependency_snapshot']['refs'][draft.id] = '0' * 64
        db.execute('UPDATE versions SET payload=? WHERE id=?', (json.dumps(raw), prose.id))
    report = check_integrity(repo.root)
    assert any(i.code == 'invalid_snapshot' for i in report.issues)
    assert repo.get_version(prose.id).stale


@pytest.mark.parametrize('legacy', [False, True])
def test_backup_restore_preserves_heads_hashes_and_freshness(tmp_path, legacy):
    from storygen.storage.backup import create_backup, restore_backup
    repo, story, scene, draft, prose = setup(tmp_path / 'source')
    if legacy:
        with repo.db.connection() as db:
            for table in ['stories','scenes','versions']:
                for row in db.execute('SELECT id,payload FROM '+table).fetchall():
                    raw=json.loads(row[1])
                    for key in ['config_revision','head_revisions','dependency_snapshot']:raw.pop(key,None)
                    db.execute('UPDATE '+table+' SET payload=? WHERE id=?',(json.dumps(raw),row[0]))
    before=repo.get_version(prose.id)
    backup=create_backup(repo.root,tmp_path/'backup')
    restored=Repository(restore_backup(backup,tmp_path/'restored'))
    assert check_integrity(restored.root).ok
    assert restored.get_scene(scene.id).heads==repo.get_scene(scene.id).heads
    assert restored.get_version(prose.id)==before
    assert restored.read_text(prose.id)=='Результат'


def test_cycle_never_counts_as_fresh(tmp_path):
    repo, story, scene, draft, prose = setup(tmp_path)
    with repo.db.connection() as db:
        raw=json.loads(db.execute('SELECT payload FROM versions WHERE id=?',(prose.id,)).fetchone()[0])
        raw['dependency_snapshot']['refs']={prose.id:prose.sha256}
        db.execute('UPDATE versions SET payload=? WHERE id=?',(json.dumps(raw),prose.id))
    assert repo.get_version(prose.id).stale
