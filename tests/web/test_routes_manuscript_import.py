"""MANUSCRIPT-IMPORT: HTTP API of the manuscript preview, the paragraph descriptions and the cancel."""
from fastapi.testclient import TestClient

from storygen.application import manuscript_import
from storygen.application.settings import AppSettings
from storygen.web.app import create_app

BOOK = '\n\n'.join(['# Книга', '## Глава перша', 'Текст першої глави. ' * 5, '## Глава друга', 'Текст другої глави. ' * 5]).encode()


def client_for(tmp_path):
    return TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765')


def fields(**values):
    return {name: (None, value) for name, value in values.items()}  # multipart form fields without a file


def upload(client, content=BOOK, name='book.md', **fields):
    return client.post('/api/manuscript-import/preview', files={'file': (name, content, 'application/octet-stream')}, data=fields)


def test_preview_paragraphs_and_cancel(tmp_path):
    with client_for(tmp_path) as client:
        response = upload(client)
        assert response.status_code == 200, response.text
        preview = response.json()
        assert [scene['title'] for scene in preview['scenes']] == ['Глава перша', 'Глава друга']
        assert preview['edition'] == {'parts_allowed': True, 'series_allowed': True, 'trial': {'state': 'none', 'kind': None, 'id': None, 'title': None}}
        assert (tmp_path / 'manuscript-import' / f'{preview["import_id"]}.md').is_file()
        rows = client.get(f'/api/manuscript-import/{preview["import_id"]}/paragraphs', params={'start': 0, 'end': 2}).json()
        assert [row['index'] for row in rows] == [0, 1, 2] and rows[1]['heading_level'] == 1
        again = client.post('/api/manuscript-import/preview', files=fields(import_id=preview['import_id'], chapter_markers='Розділ'))
        assert again.status_code == 200 and again.json()['fingerprint'] != preview['fingerprint']
        assert client.delete(f'/api/manuscript-import/{preview["import_id"]}').status_code == 204
        assert list((tmp_path / 'manuscript-import').glob('*')) == []
        assert client.get(f'/api/manuscript-import/{preview["import_id"]}/paragraphs', params={'start': 0, 'end': 1}).status_code == 404


def test_language_sets_prologue_title(tmp_path):
    chapter = '\n\n## Глава {}\n\n' + 'Текст. ' * 20
    text = ('Дуже довгий вступ. ' * 20 + chapter.format('перша') + chapter.format('друга')).encode()
    with client_for(tmp_path) as client:
        uk = upload(client, text).json()
        en = upload(client, text, language='en').json()
    assert [scene['title'] for scene in uk['scenes']][0] == 'Пролог'
    assert [scene['title'] for scene in en['scenes']][0] == 'Prologue'


def test_too_large_413_for_any_format(tmp_path, monkeypatch):
    monkeypatch.setattr(manuscript_import, 'MAX_FILE', 3 * 1024 * 1024)
    with client_for(tmp_path) as client:
        response = upload(client, b'x' * (3 * 1024 * 1024 + 1), 'big.txt')
        assert response.status_code == 413 and '3 MiB' in response.text
    assert list(tmp_path.glob('manuscript-import/*')) == []


def test_cp1251_txt_is_400(tmp_path):
    with client_for(tmp_path) as client:
        response = upload(client, 'Привіт, світе'.encode('cp1251'), 'old.txt')
        assert response.status_code == 400 and 'UTF-8' in response.json()['detail_original']
        assert upload(client, b'x', 'book.pdf').status_code == 400
    assert list(tmp_path.glob('manuscript-import/*')) == []


def test_unknown_or_foreign_import_id_is_404(tmp_path):
    with client_for(tmp_path) as client:
        for import_id in ('a' * 32, 'not-an-id', 'A' * 32):
            assert client.get(f'/api/manuscript-import/{import_id}/paragraphs', params={'start': 0, 'end': 1}).status_code == 404
            # a cancel of a well-formed unknown id is idempotent (204), a malformed id is 404
            assert client.delete(f'/api/manuscript-import/{import_id}').status_code == (204 if import_id == 'a' * 32 else 404)
            assert client.post('/api/manuscript-import/preview', files=fields(import_id=import_id)).status_code == 404


def test_bad_request_is_400(tmp_path):
    with client_for(tmp_path) as client:
        assert client.post('/api/manuscript-import/preview', files=fields(chapter_markers='Глава')).status_code == 400  # no file
        assert upload(client, chapter_source='7').status_code == 400
        assert upload(client, chapter_markers='я' * 41).status_code == 400


def test_json_body_is_400(tmp_path):
    with client_for(tmp_path) as client:
        assert client.post('/api/manuscript-import/preview', json={}).status_code == 400


def test_startup_sweeps_old_files(tmp_path):
    import os
    import time
    folder = tmp_path / 'manuscript-import'
    folder.mkdir(parents=True)
    old = folder / ('a' * 32 + '.txt')
    old.write_bytes(b'x')
    stamp = time.time() - 25 * 3600
    os.utime(old, (stamp, stamp))
    with client_for(tmp_path):
        assert not old.exists()


def test_server_messages_have_english_text(tmp_path, monkeypatch):
    from storygen.publication.manuscript_structure import DOES_NOT_FIT, LONG_PARAGRAPH, NO_HEADINGS, PARTS_NOT_ALLOWED
    from storygen.web.localization import diagnostic
    english = {'Accept-Language': 'en'}
    for text in (PARTS_NOT_ALLOWED, LONG_PARAGRAPH, NO_HEADINGS, DOES_NOT_FIT, 'Глава «A» без тексту: сцену не створено',
                 'У файлі є невирішені виправлення Word (3); їх прийнято: імпортовано погляд редактора',
                 'Файл має бути до 20 MiB'):
        assert not any('А' <= char <= 'я' for char in diagnostic(text, 'en')), text
    with client_for(tmp_path) as client:
        response = client.post('/api/manuscript-import/preview', headers=english,
                               files={'file': ('old.txt', 'Привіт'.encode('cp1251'), 'text/plain')})
        assert response.status_code == 400 and 'UTF-8' in response.json()['detail'] and 'Файл' not in response.json()['detail']
        assert client.get('/api/manuscript-import/' + 'a' * 32 + '/paragraphs', params={'start': 0, 'end': 1}).status_code == 404


def test_apply_creates_book_and_maps_errors(tmp_path):
    english = {'Accept-Language': 'en'}
    with client_for(tmp_path) as client:
        preview = upload(client).json()
        scenes = [{'start': scene['start'], 'title': scene['title']} for scene in preview['scenes']]
        body = {'fingerprint': preview['fingerprint'], 'title': 'Книга', 'language': 'uk', 'scenes': scenes, 'parts': []}
        url = f'/api/manuscript-import/{preview["import_id"]}'
        stale = client.post(url, json={**body, 'fingerprint': '0' * 64}, headers=english)
        assert stale.status_code == 409 and 'out of date' in stale.json()['detail']
        unsorted = client.post(url, json={**body, 'scenes': scenes[::-1]}, headers=english)
        assert unsorted.status_code == 400 and 'ascending' in unsorted.json()['detail']
        assert client.get('/api/stories').json() == []
        created = client.post(url, json=body)
        assert created.status_code == 200, created.text
        result = created.json()
        assert len(result['scene_ids']) == 2 and result['warnings'] == []
        assert [story['id'] for story in client.get('/api/stories').json()] == [result['story_id']]
        assert list((tmp_path / 'manuscript-import').glob('*')) == []
        assert client.post(url, json=body).status_code == 404


def test_scene_warnings_and_new_messages_have_english_text():
    from storygen.publication.manuscript_read import COMMENTS
    from storygen.web.localization import diagnostic
    assert diagnostic('Розділ 3 (2): довгий абзац без меж', 'en') == 'Розділ 3 (2): a long paragraph with no breaks'
    assert diagnostic("Глава: вступ: Частина сцени не вміститься в ліміти пам'яті навіть після поділу", 'en') == \
        'Глава: вступ: A part of the scene will not fit the memory limits even after splitting'
    assert diagnostic('Розділ 3: щось інше', 'en') == 'Розділ 3: щось інше'  # only the known scene warnings
    for text in (COMMENTS.format(count=3), manuscript_import.TOO_MANY_PROPOSED.format(count=600, limit=500)):
        assert not any('А' <= char <= 'я' for char in diagnostic(text, 'en')), text


def test_language_sets_single_chapter_title(tmp_path):
    text = ('Просто текст без заголовків. ' * 20).encode()
    with client_for(tmp_path) as client:
        uk = upload(client, text, 'a.txt').json()
        en = upload(client, text, 'a.txt', language='en').json()
    assert [scene['title'] for scene in uk['scenes']] == ['Рукопис']
    assert [scene['title'] for scene in en['scenes']] == ['Manuscript']


def test_too_large_series_number_is_a_validation_error(tmp_path):
    with client_for(tmp_path) as client:
        preview = upload(client).json()
        scenes = [{'start': scene['start'], 'title': scene['title']} for scene in preview['scenes']]
        body = {'fingerprint': preview['fingerprint'], 'title': 'Книга', 'scenes': scenes,
                'series': {'series_id': 'a' * 32, 'number': 1000001}}
        response = client.post(f'/api/manuscript-import/{preview["import_id"]}', json=body)
        assert response.status_code == 422, response.text  # the app's answer to any invalid request body
        assert client.get('/api/stories').json() == []


def test_js_diagnostic_translates_scene_warnings():
    import subprocess
    from pathlib import Path
    result = subprocess.run(['node', str(Path(__file__).parent / 'js' / 'manuscript_import_diagnostic.mjs')],
                            capture_output=True, encoding='utf8', timeout=20)
    assert result.returncode == 0, result.stderr
