"""EXPORT-DOCX: the Word manuscript with scene bookmarks for the R-46 import."""
import re
import zipfile
import io
from xml.etree import ElementTree as ET

import pytest

from storygen.domain import StoryCreate, SceneCreate
from storygen.generation.dependencies import save_manual_prose
from storygen.publication.book import capture
from storygen.publication import docx
from storygen.publication_models import PublicationData
from storygen.storage.book_structure import put_structure
from storygen.storage.repository import Repository
from tests.authoring.test_ebook_exports import seeded

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
PARTS = {'[Content_Types].xml', '_rels/.rels', 'word/document.xml', 'word/_rels/document.xml.rels', 'word/styles.xml',
         'word/footer1.xml', 'word/settings.xml', 'docProps/core.xml', 'docProps/custom.xml'}
INVALID_XML = 'Текст містить недопустимий символ XML 1.0; його не вилучено автоматично'


def rendered(repo, story, allow_incomplete=False):
    book = capture(repo, story.id, 'docx', allow_incomplete)
    return book, docx.render(book)


def part(content, name):
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        return archive.read(name).decode('utf-8')


def paragraphs(content):
    """(style, text) for each body paragraph."""
    root = ET.fromstring(part(content, 'word/document.xml'))
    result = []
    for p in root.iter(W + 'p'):
        style = p.find(f'{W}pPr/{W}pStyle')
        result.append((style.get(W + 'val') if style is not None else None, ''.join(t.text or '' for t in p.iter(W + 't'))))
    return result


def bookmarks(content):
    return re.findall(r'w:bookmarkStart [^>]*w:name="([^"]+)"', part(content, 'word/document.xml'))


def flat_book(root, prose, *, language='uk', card_language=None, scene_language=None, content_format=None):
    repo = Repository(root)
    story = repo.create_story(StoryCreate(title='Книга', language=language))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена <1> & "друга"', prose_language=scene_language))
    save_manual_prose(repo, scene.id, prose, 0, content_format)
    author = repo.publication('create_signature', display_name='Автор')
    data = PublicationData(title='Книга', author_ids=[author.id], genres=['short_story'], **({'language': card_language} if card_language else {}))
    repo.publication('save_card', story_id=story.id, data=data, expected_revision=0, expected_signature_revisions={author.id: 0})
    return repo, story


def test_docx_parts_and_styles(tmp_path):
    repo, story = seeded(tmp_path, count=3)
    book, content = rendered(repo, story)
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        assert set(archive.namelist()) == PARTS
    found = paragraphs(content)
    assert found[0] == ('Title', 'Публічна назва')
    assert [text for style, text in found if style == 'Heading2'] == [f'Сцена {i}: <Двері>' for i in range(1, 4)]
    styles = part(content, 'word/styles.xml')
    for style in ['Heading1', 'Heading2']:
        block = re.search(rf'w:styleId="{style}".*?</w:style>', styles, re.S).group(0)
        assert '<w:pageBreakBefore/>' in block
    assert 'w:w="11906"' in part(content, 'word/document.xml')


def test_docx_scene_bookmarks_and_custom_properties(tmp_path):
    repo, story = seeded(tmp_path, count=3)
    book, content = rendered(repo, story)
    assert bookmarks(content) == ['_os' + chapter.entry['scene_id'] for chapter in book.chapters]
    custom = part(content, 'docProps/custom.xml')
    assert f'name="ObscuraStoryId"><vt:lpwstr>{story.id}<' in custom
    assert f'name="ObscuraExportId"><vt:lpwstr>{book.export_id}<' in custom
    assert 'name="ObscuraManuscript"><vt:lpwstr>1<' in custom


def test_docx_trash_scene_absent(tmp_path):
    repo, story = seeded(tmp_path, count=3)
    trashed = repo.list_scenes(story.id)[1]
    repo.set_scene_trashed(story.id, trashed.id, repo.get_scene(trashed.id).revision, False)
    # Trashing a scene makes the next one stale; that is not what this test checks.
    book, content = rendered(repo, story, allow_incomplete=True)
    assert '_os' + trashed.id not in bookmarks(content)
    assert [text for style, text in paragraphs(content) if style == 'Heading2'] == ['Сцена 1: <Двері>', 'Сцена 3: <Двері>']


def test_docx_markdown_runs_and_controls(tmp_path):
    repo, story = flat_book(tmp_path, 'Слово *курсив* і **жирний**.\n', content_format='markdown')
    _, content = rendered(repo, story)
    document = part(content, 'word/document.xml')
    assert re.search(r'<w:i/>.*?<w:t xml:space="preserve">курсив</w:t>', document)
    assert re.search(r'<w:b/>.*?<w:t xml:space="preserve">жирний</w:t>', document)
    assert ('Heading2', 'Сцена <1> & "друга"') in paragraphs(content)
    repo, story = flat_book(tmp_path / 'plain', '\nліва\tправа <&>\nрядок\n\n')
    _, content = rendered(repo, story)
    document = part(content, 'word/document.xml')
    assert '<w:tab/>' in document
    texts = [text for style, text in paragraphs(content) if style is None]
    assert texts[-3:] == ['', 'ліваправа <&>', 'рядок']  # leading empty kept, trailing empty dropped


def test_docx_language_document_and_scene(tmp_path):
    repo, story = flat_book(tmp_path, 'Текст.\n', language='uk', card_language='en')
    _, content = rendered(repo, story)
    assert re.search(r'<w:rPrDefault>.*?<w:lang w:val="en-US"', part(content, 'word/styles.xml'), re.S)
    assert '<w:lang w:val="uk-UA"/>' in part(content, 'word/document.xml')
    repo, story = flat_book(tmp_path / 'same', 'Text.\n', language='uk', card_language='en-GB', scene_language='en')
    _, content = rendered(repo, story)
    assert '<w:lang ' not in part(content, 'word/document.xml')


def test_docx_untitled_part_and_title_page(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    scenes = []
    for title in ['Ранок', 'Вечір']:
        scene = repo.create_scene(story.id, SceneCreate(title=title))
        save_manual_prose(repo, scene.id, 'Три слова тут.\n', 0)
        scenes.append(scene)
    parts = [{'id': 'p1', 'title': 'Дім', 'arcs': [{'id': 'a1'}]}, {'id': 'p2', 'title': '', 'arcs': [{'id': 'b1'}]}]
    put_structure(repo, story.id, parts, {scenes[0].id: 'a1', scenes[1].id: 'b1'}, repo.get_story(story.id).revision)
    book, content = rendered(repo, story)
    found = paragraphs(content)
    assert [text for style, text in found if style == 'Heading1'] == ['Дім', 'Частина 2']
    words = sum(chapter.entry['word_count'] for chapter in book.chapters)
    assert (None, f'Слів: {words}') in found


def test_docx_incomplete_without_service_words(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    scene = repo.create_scene(story.id, SceneCreate(title='Порожня'))
    book, content = rendered(repo, story, allow_incomplete=True)
    assert bookmarks(content) == ['_os' + scene.id]
    document = part(content, 'word/document.xml')
    for word in ['застар', 'перегляд', 'Немає завершеної']:
        assert word not in document


def test_docx_invalid_xml_character_raises(tmp_path):
    repo, story = flat_book(tmp_path, 'Погано\x01.\n')
    with pytest.raises(ValueError, match=INVALID_XML):
        rendered(repo, story)


def test_docx_validate_rejects_foreign_ids(tmp_path):
    from dataclasses import replace
    repo, story = seeded(tmp_path, count=2)
    book, content = rendered(repo, story)
    docx.validate(content, book)
    with pytest.raises(ValueError):
        docx.validate(content, replace(book, export_id='f' * 32))
    with pytest.raises(ValueError):
        docx.validate(content, replace(book, chapters=tuple(reversed(book.chapters))))
    with pytest.raises(ValueError):
        docx.validate(b'not a zip', book)


@pytest.mark.parametrize('format,validation', [('docx', 'OOXML structure + scene bookmarks'), ('rtf', 'RTF 1.9 text')])
def test_export_story_docx_and_rtf_manifest(tmp_path, format, validation):
    import hashlib, json
    from storygen.application.exports import export_story
    repo, story = seeded(tmp_path, count=2)
    path = export_story(repo, story.id, format)
    manifest = json.loads(path.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    assert path.suffix == '.' + format and manifest['format'] == format and manifest['validation'] == validation
    assert manifest['format_details'] == {'profile': docx.PROFILE}
    assert manifest['output_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize('format,mime', [('docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
                                         ('rtf', 'application/rtf')])
def test_download_docx_rtf_mime_and_name(tmp_path, format, mime):
    from urllib.parse import unquote
    from fastapi.testclient import TestClient
    from storygen.application.settings import AppSettings
    from storygen.web.app import create_app
    repo, story = seeded(tmp_path, count=1, cover=False)
    with TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765') as client:
        urls = client.post(f'/api/stories/{story.id}/export', json={'format': format}).json()
        response = client.get(urls['download_url'])
        assert response.status_code == 200 and response.headers['content-type'].startswith(mime)
        header = response.headers['content-disposition']
        assert f'filename="{urls["download_url"].rsplit("/", 1)[-1]}"' in header
        readable = unquote(header.split("filename*=UTF-8''", 1)[1])
        assert readable.startswith('Псевдонім & Їжак — Публічна назва — 20') and readable.endswith('.' + format)


def test_export_dialog_offers_docx_and_rtf():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / 'src' / 'storygen' / 'web'
    template = (root / 'templates' / 'story.html').read_text(encoding='utf-8')
    assert '<option value="docx" data-i18n="export.docx_option">' in template
    assert '<option value="rtf" data-i18n="export.rtf_option">' in template
    catalog = json.loads((root / 'static' / 'i18n.json').read_text(encoding='utf-8'))
    texts = [table for table in catalog.values() if isinstance(table, dict) and 'export.docx_option' in table]
    assert len(texts) == 2 and {t['export.docx_option'] for t in texts} == {'Рукопис Word (.docx)', 'Word manuscript (.docx)'}
    assert {t['export.rtf_option'] for t in texts} == {'Рукопис RTF (.rtf)', 'RTF manuscript (.rtf)'}


@pytest.mark.parametrize('card,expected', [('uk', 'uk-UA'), ('en', 'en-US'), ('en-GB', 'en-GB'), ('fr', 'fr')])
def test_docx_bare_language_gets_a_region_for_word(tmp_path, card, expected):
    # Word treats a bare "uk" as a neutral language id (34), not Ukrainian (1058), and proofing may not apply.
    repo, story = flat_book(tmp_path, 'Текст.\n', card_language=card)
    _, content = rendered(repo, story)
    assert re.search(rf'<w:rPrDefault>.*?<w:lang w:val="{expected}"/>', part(content, 'word/styles.xml'), re.S)


P_ORDER = ['pStyle', 'keepNext', 'pageBreakBefore', 'spacing', 'ind', 'jc', 'outlineLvl']


def test_docx_paragraph_properties_follow_schema_order(tmp_path):
    # CT_PPrBase is a sequence: strict consumers repair or reject jc before ind, or ind before spacing.
    repo, story = seeded(tmp_path, count=2)
    _, content = rendered(repo, story)
    for name in ['word/document.xml', 'word/styles.xml', 'word/footer1.xml']:
        for ppr in ET.fromstring(part(content, name)).iter(W + 'pPr'):
            children = [child.tag.removeprefix(W) for child in ppr]
            assert children == sorted(children, key=P_ORDER.index), (name, children)


def test_docx_opens_in_current_word_mode(tmp_path):
    # Without compatibilityMode 15 Word opens the file in Word 2007 compatibility mode (no modern comments).
    repo, story = seeded(tmp_path, count=1)
    _, content = rendered(repo, story)
    settings = part(content, 'word/settings.xml')
    assert 'w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"' in settings
    assert 'Target="settings.xml"' in part(content, 'word/_rels/document.xml.rels')
    assert 'PartName="/word/settings.xml"' in part(content, '[Content_Types].xml')
