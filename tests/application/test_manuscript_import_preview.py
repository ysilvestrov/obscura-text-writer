"""MANUSCRIPT-IMPORT: the preview service, the kept temp file, the memory-fit estimate and the edition limits."""
import json
import os
import time
from datetime import datetime, timedelta, timezone

import pytest

from storygen.application import manuscript_import as service
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.publication.manuscript_read import ManuscriptError
from storygen.publication.manuscript_structure import ParseSettings
from storygen.storage.backup import create_backup
from storygen.storage.integrity import check_integrity
from storygen.storage.repository import Repository

BOOK = '\n\n'.join(['# Книга', 'Частина перша', '## Глава перша', 'Тексту досить для першої сцени. ' * 5,
                    '## Глава друга', 'Другий текст, теж не короткий. ' * 5]).encode()
SETTINGS = ParseSettings()


def repo_for(tmp_path):
    return Repository(tmp_path / 'data')


def kept(tmp_path, import_id):
    return sorted((tmp_path / 'data' / 'manuscript-import').glob(f'{import_id}.*'))


def test_preview_keeps_temp_file_and_fingerprint(tmp_path):
    repo = repo_for(tmp_path)
    first = service.preview(repo, BOOK, 'book.md', SETTINGS)
    assert (tmp_path / 'data' / 'manuscript-import' / f'{first.import_id}.md').read_bytes() == BOOK
    assert len(first.fingerprint) == 64 and first.file_name == 'book.md'
    assert [scene.title for scene in first.scenes] == ['Глава перша', 'Глава друга']
    assert first.edition == {'parts_allowed': True, 'series_allowed': True}
    assert first.parts and first.parts[0]['title']
    again = service.preview(repo, b'', '', SETTINGS, first.import_id)  # the kept file is parsed, content is ignored
    assert again.import_id == first.import_id and again.fingerprint == first.fingerprint and again.file_name == 'book.md'
    assert service.load(repo, first.import_id) == (BOOK, 'book.md')


def test_repreview_with_markers_changes_fingerprint(tmp_path):
    repo = repo_for(tmp_path)
    first = service.preview(repo, BOOK, 'book.md', SETTINGS)
    other = service.preview(repo, b'', '', ParseSettings(chapter_markers=('Сцена',)), first.import_id)
    assert other.import_id == first.import_id and other.fingerprint != first.fingerprint


def test_unreadable_file_is_not_kept(tmp_path):
    repo = repo_for(tmp_path)
    with pytest.raises(ManuscriptError):
        service.preview(repo, 'Привіт'.encode('cp1251'), 'old.txt', SETTINGS)
    with pytest.raises(ManuscriptError):
        service.preview(repo, b'x', 'book.pdf', SETTINGS)
    folder = tmp_path / 'data' / 'manuscript-import'
    assert not folder.exists() or not list(folder.iterdir())


def test_too_large_for_every_format(tmp_path, monkeypatch):
    repo = repo_for(tmp_path)
    monkeypatch.setattr(service, 'MAX_FILE', 1000)
    with pytest.raises(service.ManuscriptTooLarge):
        service.preview(repo, b'a' * 1001, 'big.txt', SETTINGS)


@pytest.mark.parametrize('bad', ['x', 'A' * 32, '../' + 'a' * 29, None])
def test_unknown_import_id_is_missing(tmp_path, bad):
    repo = repo_for(tmp_path)
    for call in (lambda: service.load(repo, bad), lambda: service.paragraphs(repo, bad, 0, 1), lambda: service.discard(repo, bad)):
        with pytest.raises(KeyError):
            call()
    with pytest.raises(KeyError):
        service.load(repo, 'a' * 32)


def test_paragraphs_range_and_cap(tmp_path):
    repo = repo_for(tmp_path)
    text = '\n\n'.join(f'Абзац {number} ' + 'слово ' * 40 for number in range(2500)).encode()
    import_id = service.preview(repo, text, 'long.txt', SETTINGS).import_id
    rows = service.paragraphs(repo, import_id, 2, 4)
    assert [row['index'] for row in rows] == [2, 3, 4]
    assert set(rows[0]) == {'index', 'text_head', 'words', 'heading_level', 'after_break', 'role', 'boundary_allowed'}
    assert len(rows[0]['text_head']) <= 160 and rows[0]['words'] == 42
    assert len(service.paragraphs(repo, import_id, 0, 100000)) == 2000
    assert service.paragraphs(repo, import_id, 2490, 100000)[-1]['index'] == 2499
    with pytest.raises(ValueError):
        service.paragraphs(repo, import_id, 5, 2)


def test_sweep_removes_old_files(tmp_path):
    repo = repo_for(tmp_path)
    old = service.preview(repo, BOOK, 'book.md', SETTINGS).import_id
    fresh = service.preview(repo, BOOK, 'book.md', SETTINGS).import_id
    stamp = time.time() - 25 * 3600
    for path in kept(tmp_path, old):
        os.utime(path, (stamp, stamp))
    assert service.sweep_temp(repo, now=datetime.now(timezone.utc)) == 1
    assert kept(tmp_path, old) == [] and kept(tmp_path, fresh)
    assert service.sweep_temp(repo, now=datetime.now(timezone.utc) + timedelta(hours=25)) == 1
    assert kept(tmp_path, fresh) == []


def test_discard_removes_file_and_name(tmp_path):
    repo = repo_for(tmp_path)
    import_id = service.preview(repo, BOOK, 'book.md', SETTINGS).import_id
    service.discard(repo, import_id)
    assert kept(tmp_path, import_id) == []
    service.discard(repo, import_id)  # a second cancel is harmless


def test_temp_dir_outside_backup_and_fsck(tmp_path):
    repo = repo_for(tmp_path)
    import_id = service.preview(repo, BOOK, 'book.md', SETTINGS).import_id
    assert check_integrity(repo.root).ok
    backup = create_backup(repo.root, tmp_path / 'backup')
    copied = [item['path'] for item in json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))['files']]
    assert not any(path.startswith('manuscript-import/') for path in copied)
    assert not (backup / 'data' / 'manuscript-import').exists()
    assert kept(tmp_path, import_id)


def test_store_edition_skips_parts_with_warning(tmp_path, store_edition):
    repo = repo_for(tmp_path)
    preview = service.preview(repo, BOOK, 'book.md', SETTINGS)
    assert preview.edition == {'parts_allowed': False, 'series_allowed': False}
    assert preview.parts == [] and any('частини доступні' in warning for warning in preview.warnings)
    assert [scene.title for scene in preview.scenes] == ['Глава перша', 'Глава друга']


def small_memory_role():
    return RoleSettings(provider=ProviderSettings(model='small'), context_tokens=4096, max_output_tokens=1024)


def test_memory_fits_uses_tokens_and_chars(tmp_path):
    repo = repo_for(tmp_path)
    prose = ' '.join(['слово'] * 2000)
    assert service.memory_fits(repo)(prose)  # the default role: 131 072 tokens, 80 000 characters
    assert not service.memory_fits(repo, small_memory_role())(prose)  # tokens: about 3 000 available
    chars_only = RoleSettings(provider=ProviderSettings(model='wide'), context_tokens=2 ** 20, max_output_tokens=1024,
                              max_input_chars=20000)
    assert not service.memory_fits(repo, chars_only)(prose)  # 2 x 12 000 characters plus the reserve
    assert service.memory_fits(repo, chars_only)('коротко')


def test_scene_that_does_not_fit_the_memory_role_is_split(tmp_path):
    repo = repo_for(tmp_path)
    paragraphs = '\n\n'.join(' '.join(['слово'] * 100) + '.' for _ in range(20)).encode()
    plain = service.preview(repo, paragraphs, 'one.txt', SETTINGS)
    chars_only = RoleSettings(provider=ProviderSettings(model='wide'), context_tokens=2 ** 20, max_output_tokens=1024,
                              max_input_chars=20000)
    small = service.preview(repo, paragraphs, 'one.txt', SETTINGS, role=chars_only)
    assert len(plain.scenes) == 1 and len(small.scenes) > 1
    assert not any(scene.warnings for scene in small.scenes)
    # No split fits the 4 096-token role: the word-count baseline stays (one scene up to 2 500 words) with a warning.
    never = service.preview(repo, paragraphs, 'one.txt', SETTINGS, role=small_memory_role())
    assert len(never.scenes) == 1 and never.scenes[0].warnings


ROLES_BOOK = '\n\n'.join(['# Книга', 'Присвята.', 'Частина перша', '## Глава перша', 'Текст першої глави. ' * 5, '***',
                          'Ще текст першої. ' * 5, '## Глава друга', 'Текст другої глави. ' * 5]).encode()


def test_paragraphs_carry_role_and_allowed_boundary(tmp_path):
    repo = repo_for(tmp_path)
    preview = service.preview(repo, ROLES_BOOK, 'book.md', SETTINGS)
    rows = service.paragraphs(repo, preview.import_id, 0, 100)
    assert [row['role'] for row in rows] == ['title', 'front_matter', 'part_heading', 'chapter_heading', 'prose', 'separator',
                                             'prose', 'chapter_heading', 'prose']
    assert [row['index'] for row in rows if row['boundary_allowed']] == [1, 4, 6, 8]
    for start in (5, 7):  # a separator or a chapter heading is never a scene boundary
        scenes = [{'start': 4, 'title': 'А'}, {'start': start, 'title': 'Б'}]
        with pytest.raises(ValueError, match=service.BAD_BOUNDARY):
            service.apply_import(repo, preview.import_id, {'fingerprint': preview.fingerprint, 'title': 'К', 'scenes': scenes})


def test_preview_warns_when_more_scenes_than_one_import_takes(tmp_path, monkeypatch):
    monkeypatch.setattr(service, 'MAX_SCENES', 1)
    preview = service.preview(repo_for(tmp_path), BOOK, 'book.md', SETTINGS)
    assert service.TOO_MANY_PROPOSED.format(count=2, limit=1) in preview.warnings


def test_file_name_with_lone_surrogate_is_kept_without_it(tmp_path):
    repo = repo_for(tmp_path)
    preview = service.preview(repo, BOOK, 'кни\udc80га.md', SETTINGS)
    assert preview.file_name == 'книга.md'
    json.dumps(preview.file_name, ensure_ascii=False).encode('utf-8')
    assert service.load(repo, preview.import_id) == (BOOK, 'книга.md')
    (tmp_path / 'data' / 'manuscript-import' / f'{preview.import_id}.name').write_bytes(b'\xff\xfe')
    assert service.load(repo, preview.import_id)[1] == f'{preview.import_id}.md'
