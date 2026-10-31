from tests.review.test_runner import fixture
from storygen.storage.integrity import check_integrity as fsck


def test_review_proofs_are_checked_offline(tmp_path):
    repo,story,first,second,ref,worker,run,calls=fixture(tmp_path)
    worker._execute(run.id)
    report=fsck(repo.root)
    assert report.ok,report.issues
    with repo.db.connection() as db:
        row=db.execute("SELECT key,payload FROM app_settings WHERE key LIKE 'review3:%:report:%'").fetchone()
        import json
        raw=json.loads(row[1]);raw['proofs']={}
        db.execute('UPDATE app_settings SET payload=? WHERE key=?',(json.dumps(raw),row[0]))
    report=fsck(repo.root)
    assert any(i.code=='invalid_review' for i in report.issues)


def test_review_survives_cold_backup_and_restore(tmp_path):
    from storygen.storage.backup import create_backup,restore_backup
    from storygen.storage.repository import Repository
    repo,story,first,second,ref,worker,run,calls=fixture(tmp_path/'data')
    worker._execute(run.id)
    backup=create_backup(repo.root,tmp_path/'backup')
    restored=restore_backup(backup,tmp_path/'restored')
    assert fsck(restored).ok
    assert not Repository(restored).get_version(ref.id).stale

