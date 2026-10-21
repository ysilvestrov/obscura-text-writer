import json
import sqlite3

import pytest

from storygen.domain import SceneCreate, StoryCreate
from storygen.generation.dependencies import save_manual_prose
from storygen.storage.repository import Repository
from storygen.storage.integrity import check_integrity


def sample(root):
    repo = Repository(root)
    story = repo.create_story(StoryCreate(title='Книга'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена'))
    ref = save_manual_prose(repo, scene.id, 'Збережена проза.', 0)
    return repo, story, scene, ref


def test_fsck_is_read_only_and_checks_archived_materials(tmp_path):
    from storygen.authoring.trash import trash_story
    repo, story, _, _ = sample(tmp_path)
    trash_story(repo, story.id, repo.get_story(story.id).revision)
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    result = check_integrity(tmp_path)
    assert result.ok and result.versions_checked == 1
    assert before == {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}


def test_fsck_missing_database_does_not_create_directory(tmp_path):
    root = tmp_path / 'missing'
    report = check_integrity(root)
    assert not report.ok and 'database_missing' in {i.code for i in report.issues}
    assert not root.exists()


@pytest.mark.parametrize('damage,code', [
    ('missing', 'file_missing'), ('hash', 'hash_mismatch'), ('orphan', 'orphan_blob'),
    ('unknown_suffix', 'orphan_blob'),
    ('head', 'invalid_head'), ('edge', 'dependency_mismatch'), ('column', 'payload_mismatch'),
])
def test_fsck_reports_corruption_without_repair(tmp_path, damage, code):
    repo, story, scene, ref = sample(tmp_path)
    if damage == 'missing':
        repo.files.resolve(ref.relative_path).unlink()
    elif damage == 'hash':
        repo.files.resolve(ref.relative_path).write_bytes(b'changed')
    elif damage == 'orphan':
        repo.files.write(f'stories/{story.id}/versions/orphan.txt', b'orphan')
    elif damage == 'unknown_suffix':
        repo.files.write(f'stories/{story.id}/versions/orphan.other', b'orphan')
    else:
        with repo.db.connection() as db:
            if damage == 'head':
                value = repo.get_scene(scene.id).model_dump()
                value['heads']['prose'] = 'missing'
                db.execute('UPDATE scenes SET payload=? WHERE id=?', (json.dumps(value), scene.id))
            elif damage == 'edge':
                child = repo.save_version(story.id, scene.id, 'draft', 'Чернетка.', [ref.id])
                db.execute('DELETE FROM dependency_edges WHERE target_id=?', (child.id,))
            else:
                db.execute("UPDATE versions SET kind='draft' WHERE id=?", (ref.id,))
    report = check_integrity(tmp_path)
    assert not report.ok and code in {i.code for i in report.issues}
    assert not check_integrity(tmp_path).ok


def test_fsck_rejects_foreign_head(tmp_path):
    repo, story, scene, ref = sample(tmp_path)
    other = repo.create_scene(story.id, SceneCreate(title='Інша'))
    value = other.model_copy(update={'heads': {'prose': ref.id}})
    with repo.db.connection() as db:
        db.execute('UPDATE scenes SET payload=? WHERE id=?', (value.model_dump_json(), other.id))
    assert 'invalid_head' in {i.code for i in check_integrity(tmp_path).issues}


def test_fsck_checks_source_bytes_and_classifies_partial(tmp_path):
    from storygen.authoring.imports import SourceFile, import_sources
    repo, story, _, _ = sample(tmp_path)
    imported = import_sources(repo, story.id, [SourceFile(name='plan.txt', raw='План.'.encode())])
    repo.files.write(f'stories/{story.id}/runs/test/partial.txt', b'partial')
    report = check_integrity(tmp_path)
    assert report.ok and report.sources_checked == 1 and report.auxiliary_files >= 1
    repo.files.resolve(imported.sources[0]['relative_path']).write_bytes(b'bad')
    assert 'hash_mismatch' in {i.code for i in check_integrity(tmp_path).issues}


def test_fsck_does_not_migrate_old_database(tmp_path):
    path = tmp_path / 'storygen.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('PRAGMA user_version=1')
    before = path.read_bytes()
    report = check_integrity(tmp_path)
    assert not report.ok and 'unsupported_schema' in {i.code for i in report.issues}
    assert path.read_bytes() == before


def test_fsck_rejects_path_escape(tmp_path):
    repo, _, _, ref = sample(tmp_path)
    value = ref.model_copy(update={'relative_path': '../outside.txt'})
    with repo.db.connection() as db:
        db.execute('UPDATE versions SET payload=? WHERE id=?', (value.model_dump_json(), ref.id))
    assert 'unsafe_path' in {i.code for i in check_integrity(tmp_path).issues}


def test_fsck_reads_committed_wal_instead_of_stale_database(tmp_path):
    repo, _, _, ref = sample(tmp_path)
    with sqlite3.connect(tmp_path / 'storygen.sqlite3') as writer:
        value = ref.model_copy(update={'sha256': '0' * 64})
        writer.execute('UPDATE versions SET payload=? WHERE id=?', (value.model_dump_json(), ref.id))
        writer.commit()
        assert (tmp_path / 'storygen.sqlite3-wal').stat().st_size > 0
        assert 'hash_mismatch' in {i.code for i in check_integrity(tmp_path).issues}
    writer.close()
