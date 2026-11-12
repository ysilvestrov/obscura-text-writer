"""BOOK-STRUCTURE-S05: parts as a higher heading level in every export format; arcs are not exported."""
import io
import zipfile
from xml.etree import ElementTree as ET

import pytest

from storygen.application.exports import export_story
from storygen.domain import StoryCreate, SceneCreate
from storygen.generation.dependencies import save_manual_prose
from storygen.publication_models import PublicationData
from storygen.storage.book_structure import put_structure
from storygen.storage.repository import Repository

FB = {'f': 'http://www.gribuser.ru/xml/fictionbook/2.0'}
XHTML = '{http://www.w3.org/1999/xhtml}'


def book(root, language='uk', structured=True):
    repo = Repository(root)
    story = repo.create_story(StoryCreate(title='Книга', language=language))
    scenes = []
    for title in ['Ранок', 'Обід', 'Вечір']:
        scene = repo.create_scene(story.id, SceneCreate(title=title))
        save_manual_prose(repo, scene.id, f'Текст сцени {title}.\n', 0)
        scenes.append(scene)
    author = repo.publication('create_signature', display_name='Автор')
    repo.publication('save_card', story_id=story.id, data=PublicationData(title='Книга', author_ids=[author.id], genres=['short_story']),
                     expected_revision=0, expected_signature_revisions={author.id: 0})
    if structured:
        parts = [{'id': 'p1', 'title': 'Дім', 'arcs': [{'id': 'a1', 'title': 'Таємна арка'}]}, {'id': 'p2', 'title': '', 'arcs': [{'id': 'b1'}]}]
        put_structure(repo, story.id, parts, {scenes[0].id: 'a1', scenes[1].id: 'a1', scenes[2].id: 'b1'}, repo.get_story(story.id).revision)
    return repo, story


def test_markdown_has_part_headings(tmp_path):
    repo, story = book(tmp_path)
    text = export_story(repo, story.id, 'md').read_text(encoding='utf-8')
    assert text.startswith('# Книга\n\n## Дім\n\n### Ранок\n\nТекст сцени Ранок.')
    assert '\n\n## Частина 2\n\n### Вечір\n' in text
    assert 'Таємна арка' not in text


def test_markdown_part_without_title_in_english(tmp_path):
    repo, story = book(tmp_path, language='en')
    assert '\n## Part 2\n' in export_story(repo, story.id, 'md').read_text(encoding='utf-8')


def test_flat_markdown_is_unchanged(tmp_path):
    repo, story = book(tmp_path, structured=False)
    text = export_story(repo, story.id, 'md').read_text(encoding='utf-8')
    assert text.startswith('# Книга\n\n## Ранок\n\n') and '###' not in text


def test_txt_has_part_paragraphs(tmp_path):
    repo, story = book(tmp_path)
    text = export_story(repo, story.id, 'txt').read_text(encoding='utf-8')
    assert text.startswith('Книга\n\nДім\n\nРанок\n\nТекст сцени Ранок.')
    assert '\n\nЧастина 2\n\nВечір\n' in text


def test_fb2_nests_scene_sections_in_parts(tmp_path):
    pytest.importorskip('lxml')
    repo, story = book(tmp_path)
    root = ET.fromstring(export_story(repo, story.id, 'fb2').read_bytes())
    parts = root.findall('f:body/f:section', FB)
    assert [p.find('f:title/f:p', FB).text for p in parts] == ['Дім', 'Частина 2']
    assert [s.find('f:title/f:p', FB).text for s in parts[0].findall('f:section', FB)] == ['Ранок', 'Обід']


def test_epub_has_part_pages_and_nested_toc(tmp_path):
    repo, story = book(tmp_path)
    with zipfile.ZipFile(export_story(repo, story.id, 'epub')) as archive:
        nav = ET.fromstring(archive.read('EPUB/nav.xhtml'))
        part = ET.fromstring(archive.read('EPUB/part-1.xhtml'))
        opf = archive.read('EPUB/package.opf').decode('utf-8')
    toc = nav.find(f'.//{XHTML}nav/{XHTML}ol')
    items = toc.findall(f'{XHTML}li')
    assert [li.find(f'{XHTML}a').text for li in items] == ['Дім', 'Частина 2']
    assert [a.text for a in items[0].findall(f'{XHTML}ol/{XHTML}li/{XHTML}a')] == ['Ранок', 'Обід']
    assert part.find(f'.//{XHTML}h1').text == 'Дім'
    assert opf.index('part-1') < opf.index('chapter-1') < opf.index('part-2') < opf.index('chapter-3')


def test_pdf_renders_with_parts(tmp_path):
    pytest.importorskip('reportlab')
    repo, story = book(tmp_path)
    from pypdf import PdfReader
    reader = PdfReader(export_story(repo, story.id, 'pdf'))
    outline = reader.outline
    titles = [item.title for item in outline if not isinstance(item, list)]
    assert titles == ['Дім', 'Частина 2']
    assert [item.title for item in outline[1]] == ['Ранок', 'Обід']
    text = ' '.join(page.extract_text() for page in reader.pages)
    assert 'Таємна арка' not in text
