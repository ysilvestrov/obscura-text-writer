import json
import sys

import pytest

from storygen.storage.backup import create_backup, restore_backup
from storygen.storage.integrity import check_integrity
from storygen.storage.locking import AppInstanceLock
from storygen.storage.repository import Repository
from storygen.domain import StoryCreate, SceneCreate
from storygen.generation.dependencies import save_manual_prose


def sample(root):
    repo = Repository(root)
    story = repo.create_story(StoryCreate(title='Книга'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена'))
    ref = save_manual_prose(repo, scene.id, 'Збережений текст.', 0)
    repo.files.write(f'stories/{story.id}/runs/test/partial.txt', b'partial')
    return repo, story, scene, ref


def test_backup_restore_round_trip(tmp_path):
    repo, story, scene, ref = sample(tmp_path / 'source')
    backup = create_backup(repo.root, tmp_path / 'backup')
    manifest = json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['status'] == 'complete' and manifest['format_version'] == 1
    assert not (backup / 'data' / 'worker.lock').exists()
    assert not any(item['path'].startswith('storygen.sqlite3-') for item in manifest['files'])
    restored = restore_backup(backup, tmp_path / 'restored')
    assert check_integrity(restored).ok
    copy = Repository(restored)
    assert copy.get_scene(scene.id).heads['prose'] == ref.id
    assert copy.get_story(story.id).revision == repo.get_story(story.id).revision
    assert copy.read_text(ref.id) == 'Збережений текст.'
    assert (restored / f'stories/{story.id}/runs/test/partial.txt').read_bytes() == b'partial'
    assert not (restored / '.restore-incomplete.json').exists()


def test_backup_refuses_busy_source_without_destination(tmp_path):
    repo, *_ = sample(tmp_path / 'source')
    with AppInstanceLock(repo.root):
        with pytest.raises(RuntimeError):
            create_backup(repo.root, tmp_path / 'backup')
    assert not (tmp_path / 'backup').exists()


@pytest.mark.parametrize('destination', ['source', 'source/nested', 'existing'])
def test_backup_refuses_existing_or_nested_destination(tmp_path, destination):
    repo, *_ = sample(tmp_path / 'source')
    (tmp_path / 'existing').mkdir()
    with pytest.raises(ValueError):
        create_backup(repo.root, tmp_path / destination)


@pytest.mark.parametrize('damage', ['modify', 'extra', 'root_extra', 'missing', 'incomplete', 'escape'])
def test_restore_rejects_invalid_backup_before_destination(tmp_path, damage):
    repo, _, _, ref = sample(tmp_path / 'source')
    backup = create_backup(repo.root, tmp_path / 'backup')
    manifest_path = backup / 'manifest.json'
    if damage == 'modify':
        (backup / 'data' / ref.relative_path).write_bytes(b'bad')
    elif damage == 'extra':
        (backup / 'data' / 'extra.txt').write_bytes(b'extra')
    elif damage == 'root_extra':
        (backup / 'extra.txt').write_bytes(b'extra')
    elif damage == 'missing':
        (backup / 'data' / ref.relative_path).unlink()
    else:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if damage == 'incomplete':
            manifest['status'] = 'incomplete'
        else:
            manifest['files'][0]['path'] = '../outside.txt'
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError):
        restore_backup(backup, tmp_path / 'restored')
    assert not (tmp_path / 'restored').exists()


def test_failed_copy_keeps_backup_incomplete(tmp_path, monkeypatch):
    import storygen.storage.backup as module
    repo, *_ = sample(tmp_path / 'source')
    def fail(*args, **kwargs):
        raise OSError('simulated disk failure')
    monkeypatch.setattr(module.shutil, 'copy2', fail)
    with pytest.raises(OSError):
        create_backup(repo.root, tmp_path / 'backup')
    manifest = json.loads((tmp_path / 'backup/manifest.json').read_text(encoding='utf-8'))
    assert manifest['status'] == 'incomplete'


def test_restore_never_overwrites_existing_destination(tmp_path):
    repo, *_ = sample(tmp_path / 'source')
    backup = create_backup(repo.root, tmp_path / 'backup')
    destination = tmp_path / 'existing'
    destination.mkdir()
    (destination / 'keep.txt').write_text('keep')
    with pytest.raises(ValueError):
        restore_backup(backup, destination)
    assert (destination / 'keep.txt').read_text() == 'keep'


def test_failed_restore_keeps_incomplete_marker(tmp_path, monkeypatch):
    import storygen.storage.backup as module
    repo, *_ = sample(tmp_path / 'source')
    backup = create_backup(repo.root, tmp_path / 'backup')
    def fail(*args, **kwargs):
        raise OSError('simulated disk failure')
    monkeypatch.setattr(module.shutil, 'copy2', fail)
    with pytest.raises(OSError):
        restore_backup(backup, tmp_path / 'restored')
    assert (tmp_path / 'restored/.restore-incomplete.json').is_file()


def test_application_refuses_incomplete_restore_before_database_creation(tmp_path):
    root = tmp_path / 'incomplete'
    root.mkdir()
    (root / '.restore-incomplete.json').write_text('{"status":"incomplete"}')
    with pytest.raises(ValueError):
        Repository(root)
    assert not (root / 'storygen.sqlite3').exists()


def test_incomplete_restore_is_not_a_backup_source(tmp_path):
    repo, *_ = sample(tmp_path / 'source')
    (repo.root / '.restore-incomplete.json').write_text('{"status":"incomplete"}')
    with pytest.raises(ValueError):
        create_backup(repo.root, tmp_path / 'backup')
    assert not (tmp_path / 'backup').exists()


def test_backup_refuses_corrupt_source_before_destination(tmp_path):
    repo, _, _, ref = sample(tmp_path / 'source')
    repo.files.resolve(ref.relative_path).unlink()
    with pytest.raises(ValueError):
        create_backup(repo.root, tmp_path / 'backup')
    assert not (tmp_path / 'backup').exists()


def test_backup_rejects_symlink_before_lock_is_opened(tmp_path):
    repo, *_ = sample(tmp_path / 'source')
    outside = tmp_path / 'outside.txt'
    outside.write_bytes(b'')
    try:
        (repo.root / 'worker.lock').symlink_to(outside)
    except OSError:
        pytest.skip('OS does not allow symlink creation')
    with pytest.raises(ValueError):
        create_backup(repo.root, tmp_path / 'backup')
    assert outside.read_bytes() == b''


def test_backup_closes_sqlite_output_before_validation(tmp_path, monkeypatch):
    import storygen.storage.backup as module
    repo, *_ = sample(tmp_path / 'source')
    original = module.require_integrity
    def verify(root):
        if root.name == 'data':
            path = root / 'storygen.sqlite3'
            moved = root / 'closed.sqlite3'
            path.rename(moved)
            moved.rename(path)
        return original(root)
    monkeypatch.setattr(module, 'require_integrity', verify)
    create_backup(repo.root, tmp_path / 'backup')


def test_backup_skips_env_files_at_any_depth(tmp_path):
    repo, story, _, _ = sample(tmp_path / 'source')
    (repo.root / '.env').write_text('VENICE_API_KEY=secret', encoding='utf-8')
    (repo.root / 'stories' / story.id / '.env').write_text('X=1', encoding='utf-8')
    (repo.root / 'stories' / story.id / 'notes.env.txt').write_text('kept', encoding='utf-8')
    backup = create_backup(repo.root, tmp_path / 'backup')
    copied = [path.name for path in (backup / 'data').rglob('*') if path.is_file()]
    assert '.env' not in copied
    assert 'notes.env.txt' in copied
    manifest = json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))
    assert not [item for item in manifest['files'] if item['path'].rsplit('/', 1)[-1] == '.env']


def test_backup_skips_env_files_in_any_letter_case(tmp_path):
    repo, story, _, _ = sample(tmp_path / 'source')
    (repo.root / 'stories' / story.id / '.ENV').write_text('VENICE_API_KEY=secret', encoding='utf-8')
    backup = create_backup(repo.root, tmp_path / 'backup')
    assert not [path for path in (backup / 'data').rglob('*') if path.name.lower() == '.env']


@pytest.mark.req('DESKTOP-001')
def test_backup_skips_only_the_window_profile_at_the_root(tmp_path):
    repo, story, _, _ = sample(tmp_path / 'source')
    (repo.root / '.window' / 'Default').mkdir(parents=True)
    (repo.root / '.window' / 'Default' / 'Cookies').write_bytes(b'edge profile')
    nested = repo.root / 'stories' / story.id / '.window'
    nested.mkdir()
    (nested / 'note.txt').write_text('kept', encoding='utf-8')
    backup = create_backup(repo.root, tmp_path / 'backup')
    copied = [item['path'] for item in json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))['files']]
    assert not any(path.startswith('.window/') for path in copied)
    assert f'stories/{story.id}/.window/note.txt' in copied


@pytest.mark.req('DESKTOP-001')
@pytest.mark.skipif(sys.platform != 'win32', reason='a junction is a Windows reparse point')
def test_integrity_check_ignores_what_edge_keeps_in_the_window_profile(tmp_path):
    import _winapi
    repo, _, _, _ = sample(tmp_path / 'source')
    profile = repo.root / '.window'
    profile.mkdir()
    (tmp_path / 'elsewhere').mkdir()
    _winapi.CreateJunction(str(tmp_path / 'elsewhere'), str(profile / 'junction'))
    assert check_integrity(repo.root).ok
    assert create_backup(repo.root, tmp_path / 'backup').is_dir()


def test_backup_skips_kept_editor_import_files(tmp_path):
    repo, story, _, _ = sample(tmp_path / 'source')
    repo.files.write('editor-import/' + 'a' * 32 + '.docx', b'preview kept until save')
    assert check_integrity(repo.root).ok
    backup = create_backup(repo.root, tmp_path / 'backup')
    copied = [item['path'] for item in json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))['files']]
    assert not any(path.startswith('editor-import/') for path in copied)
    assert not (backup / 'data' / 'editor-import').exists()
    assert (repo.root / 'editor-import' / ('a' * 32 + '.docx')).is_file()
