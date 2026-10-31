from storygen.storage.integrity import check_integrity
from storygen.storage.backup import create_backup,restore_backup
from storygen.storage.repository import Repository
from tests.impact.test_storage import assessed


def test_impact_report_survives_verified_backup_and_restore(tmp_path):
    repo,story,first,second,ref,record=assessed(tmp_path/'data')
    repo.impact('save_report',record=record)
    report=check_integrity(repo.root)
    assert report.ok,report
    create_backup(repo.root,tmp_path/'backup')
    restore_backup(tmp_path/'backup',tmp_path/'restored')
    reopened=Repository(tmp_path/'restored')
    assert not reopened.get_version(ref.id).stale
    assert reopened.impact('state',story_id=story.id)[0]['current']
