"""EDITOR-IMPORT: HTTP API of the editor DOCX import and the startup sweep of the kept files."""
import os
import time

import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.generation.dependencies import save_manual_prose
from storygen.web.app import create_app
from tests.publication.test_editor_import import book, edit

DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'


def client_for(tmp_path):
    return TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765')


def upload(client, story_id, content):
    return client.post(f'/api/stories/{story_id}/editor-import/preview', files={'file': ('book.docx', content, DOCX)})


def test_preview_and_apply_roundtrip(tmp_path):
    repo, story, scenes, content = book(tmp_path)
    with client_for(tmp_path) as client:
        response = upload(client, story.id, edit(content, lambda xml: xml.replace('пішов', 'побіг')))
        assert response.status_code == 200, response.text
        preview = response.json()
        assert [item['status'] for item in preview['scenes']] == ['unchanged', 'changed', 'unchanged']
        assert preview['choice_required'] is False
        assert (tmp_path / 'editor-import' / f'{preview["import_id"]}.docx').is_file()
        response = client.post(f'/api/stories/{story.id}/editor-import/{preview["import_id"]}',
                               json={'fingerprint': preview['fingerprint'], 'changed_scenes': None})
        assert response.status_code == 200, response.text
        assert response.json()['imported'] == [scenes[1].id]
        assert not (tmp_path / 'editor-import' / f'{preview["import_id"]}.docx').exists()
        response = client.get(f'/api/scenes/{scenes[1].id}/copyedits')
        assert response.status_code == 200 and len(response.json()) == 1

        second = upload(client, story.id, content).json()
        assert client.delete(f'/api/stories/{story.id}/editor-import/{second["import_id"]}').status_code == 204
        assert not (tmp_path / 'editor-import' / f'{second["import_id"]}.docx').exists()


def test_preview_too_large_413(tmp_path, monkeypatch):
    from storygen.publication import docx_import
    repo, story, _, content = book(tmp_path)
    monkeypatch.setattr(docx_import, 'MAX_FILE', 3 * 1024 * 1024)
    with client_for(tmp_path) as client:
        response = upload(client, story.id, content + b'x' * (3 * 1024 * 1024))
        assert response.status_code == 413
        assert '3 MiB' in response.text  # the message follows MAX_FILE
    assert list(tmp_path.glob('editor-import/*.docx')) == []


def test_two_files_400(tmp_path):
    repo, story, _, content = book(tmp_path)
    with client_for(tmp_path) as client:
        response = client.post(f'/api/stories/{story.id}/editor-import/preview',
                               files=[('file', ('a.docx', content, DOCX)), ('file', ('b.docx', content, DOCX))])
        assert response.status_code == 400
        response = client.post(f'/api/stories/{story.id}/editor-import/preview', data={'note': 'x'},
                               files={'file': ('a.docx', content, DOCX)})
        assert response.status_code == 400
        assert client.post(f'/api/stories/{story.id}/editor-import/preview', content=content,
                           headers={'content-type': DOCX}).status_code == 400


def test_apply_conflict_409(tmp_path):
    repo, story, scenes, content = book(tmp_path)
    with client_for(tmp_path) as client:
        preview = upload(client, story.id, edit(content, lambda xml: xml.replace('пішов', 'побіг'))).json()
        save_manual_prose(repo, scenes[0].id, 'Новий початок.', scenes[0].revision, content_format='markdown')
        response = client.post(f'/api/stories/{story.id}/editor-import/{preview["import_id"]}',
                               json={'fingerprint': preview['fingerprint'], 'changed_scenes': None})
        assert response.status_code == 409
        assert 'Твір змінився після зведення' in response.json()['detail_original']
        assert repo.list_attempts(story.id) == []


@pytest.mark.parametrize('import_id', ['not-an-id', '0' * 31 + 'G', 'A' * 32])
def test_bad_import_id_404(tmp_path, import_id):
    repo, story, _, _ = book(tmp_path)
    with client_for(tmp_path) as client:
        response = client.post(f'/api/stories/{story.id}/editor-import/{import_id}',
                               json={'fingerprint': 'x', 'changed_scenes': None})
        assert response.status_code == 404
        assert client.delete(f'/api/stories/{story.id}/editor-import/{import_id}').status_code == 404
        # A well-formed id whose file is gone (imported, cancelled or swept): saving is 404, cancelling is idempotent.
        assert client.delete(f'/api/stories/{story.id}/editor-import/{"f" * 32}').status_code == 204
        assert client.post(f'/api/stories/{story.id}/editor-import/{"f" * 32}',
                           json={'fingerprint': 'x', 'changed_scenes': None}).status_code == 404


def test_startup_sweeps_old_temp(tmp_path):
    folder = tmp_path / 'editor-import'
    folder.mkdir()
    old, fresh = folder / ('a' * 32 + '.docx'), folder / ('b' * 32 + '.docx')
    old.write_bytes(b'old')
    fresh.write_bytes(b'fresh')
    stamp = time.time() - 25 * 3600
    os.utime(old, (stamp, stamp))
    app = create_app(AppSettings(data_dir=tmp_path))
    assert old.exists()
    with TestClient(app, base_url='http://127.0.0.1:8765'):
        assert not old.exists() and fresh.exists()


def test_startup_sweep_failure_is_logged_not_raised(tmp_path, monkeypatch, caplog):
    from storygen.application import editor_import

    def broken(repo, **_):
        raise OSError('disk')
    monkeypatch.setattr(editor_import, 'sweep_temp', broken)
    with TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765') as client:
        assert client.get('/api/stories').status_code == 200
    assert any('editor-import' in record.getMessage() for record in caplog.records)
