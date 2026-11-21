"""EXPORT-001-S07: the download name of a book export is built from its manifest (authors, title, export date)."""
from datetime import timedelta, timezone
from urllib.parse import quote, unquote

from fastapi.testclient import TestClient

from storygen.application.exports import download_name
from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from tests.authoring.test_ebook_exports import seeded

ID = '0123456789abcdef0123456789abcdef'
PLUS_TWO = timezone(timedelta(hours=2))


def manifest(title='Назва', authors=('Автор',), language='uk', created='2026-11-20T23:30:00+00:00'):
    return {'schema_version': 2, 'created_at': created,
            'metadata': {'effective_title': title, 'authors': [{'display_name': a} for a in authors],
                         'card': {'language': language}}}


def test_name_is_authors_title_and_local_date():
    assert download_name(manifest(), ID, 'epub', tz=PLUS_TWO) == 'Автор — Назва — 2026-11-21.epub'
    assert download_name(manifest(), ID, 'epub', tz=timezone.utc) == 'Автор — Назва — 2026-11-20.epub'


def test_commas_dots_and_windows_characters_become_spaces():
    name = download_name(manifest(title='Ніч, день. Ранок: "так"/ні?*<>|\\', authors=('Т. Шевченко',)), ID, 'pdf', tz=PLUS_TWO)
    assert name == 'Т Шевченко — Ніч день Ранок так ні — 2026-11-21.pdf'


def test_several_authors_joined_in_card_language():
    assert download_name(manifest(authors=('Анна', 'Борис')), ID, 'md', tz=PLUS_TWO) == 'Анна та Борис — Назва — 2026-11-21.md'
    assert download_name(manifest(authors=('Ann', 'Bob'), language='en'), ID, 'md', tz=PLUS_TWO) == 'Ann and Bob — Назва — 2026-11-21.md'


def test_long_author_list_keeps_first_and_others_within_sixty():
    authors = download_name(manifest(authors=('А' * 40, 'Б' * 40)), ID, 'txt', tz=PLUS_TWO).split(' — ')[0]
    assert authors == 'А' * 40 + ' та інші'
    first = ('Слово ' * 12).strip()  # 71 characters, a space falls at the cut
    authors = download_name(manifest(authors=(first, 'Б')), ID, 'txt', tz=PLUS_TWO).split(' — ')[0]
    assert len(authors) <= 60 and authors.endswith(' та інші') and '  ' not in authors
    english = download_name(manifest(authors=('A' * 58, 'B'), language='en'), ID, 'txt', tz=PLUS_TWO).split(' — ')[0]
    assert len(english) <= 60 and english.endswith(' and others')


def test_one_long_author_is_cut_without_suffix():
    authors = download_name(manifest(authors=('Ж' * 65,)), ID, 'txt', tz=PLUS_TWO).split(' — ')[0]
    assert authors == 'Ж' * 60


def test_long_title_is_cut_to_the_limit_without_a_trailing_space():
    name = download_name(manifest(title=('Дуже довга назва ' * 20).strip()), ID, 'epub', tz=PLUS_TWO)
    base = name[:-len('.epub')]
    assert len(base) <= 150 and base.endswith(' — 2026-11-21') and base.startswith('Автор — Дуже')
    assert ' —' in base and '  ' not in base


def test_missing_parts_are_skipped():
    assert download_name(manifest(authors=()), ID, 'fb2', tz=PLUS_TWO) == 'Назва — 2026-11-21.fb2'
    assert download_name(manifest(authors=(' . ', 'Анна')), ID, 'fb2', tz=PLUS_TWO) == 'Анна — Назва — 2026-11-21.fb2'
    assert download_name(manifest(title='...'), ID, 'fb2', tz=PLUS_TWO) == 'Автор — 2026-11-21.fb2'
    assert download_name(manifest(created='not a date'), ID, 'fb2', tz=PLUS_TWO) == 'Автор — Назва.fb2'


def test_technical_name_without_metadata_or_title_and_authors():
    assert download_name({'format': 'md'}, ID, 'md') == f'{ID}.md'
    assert download_name(manifest(title='...', authors=()), ID, 'md', tz=PLUS_TWO) == f'{ID}.md'
    assert download_name({'metadata': {'effective_title': 5, 'authors': 'x'}}, ID, 'md') == f'{ID}.md'


def _filename_star(header):
    return unquote(header.split("filename*=UTF-8''", 1)[1])


def test_download_header_has_readable_name_and_technical_fallback(tmp_path):
    repo, story = seeded(tmp_path, count=1, cover=False)
    with TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765') as client:
        urls = client.post(f'/api/stories/{story.id}/export', json={'format': 'epub'}).json()
        file_name = urls['download_url'].rsplit('/', 1)[-1]
        header = client.get(urls['download_url']).headers['content-disposition']
        assert header.startswith(f'attachment; filename="{file_name}"; filename*=UTF-8\'\'')
        readable = _filename_star(header)
        assert readable.startswith('Псевдонім & Їжак — Публічна назва — 20') and readable.endswith('.epub')
        assert quote(readable) in header
        assert client.get(urls['manifest_url']).headers['content-disposition'] == \
            f'attachment; filename="{urls["manifest_url"].rsplit("/", 1)[-1]}"'
        # Storage keeps the export id.
        assert repo.files.resolve(f'stories/{story.id}/exports/{file_name}').is_file()


def test_legacy_export_downloads_under_technical_name(tmp_path):
    import json
    repo, story = seeded(tmp_path, count=1, cover=False)
    base = f'stories/{story.id}/exports/'
    repo.files.write(base + ID + '.md', b'legacy')
    repo.files.write(base + ID + '.manifest.json', json.dumps({'story_id': story.id, 'format': 'md'}).encode())
    with TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765') as client:
        response = client.get(f'/api/stories/{story.id}/exports/{ID}.md')
    assert response.content == b'legacy'
    assert _filename_star(response.headers['content-disposition']) == f'{ID}.md'
