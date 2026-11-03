"""Task3 RED design prepared outside tracked source during Task2 verification."""
import pytest
from storygen.markdown_document import parse_markdown, to_plain_text, escape_plain_markdown
from storygen.domain import StoryCreate, SceneCreate
from storygen.storage.repository import Repository
from storygen.generation.dependencies import save_manual_prose
from storygen.publication_models import PublicationData
from storygen.application.exports import export_story
from xml.etree import ElementTree as ET
import zipfile
import json
from pathlib import Path


@pytest.mark.parametrize('fixture',json.loads((Path(__file__).parents[1]/'fixtures/markdown-authoring.json').read_text(encoding='utf-8')),ids=lambda item:item['name'])
def test_shared_javascript_python_projection_fixtures(fixture):
    assert to_plain_text(fixture['source'],fixture['format'])==fixture['expected_visible']


def book(root):
    repo=Repository(root);story=repo.create_story(StoryCreate(title='Зорі'))
    scene=repo.create_scene(story.id,SceneCreate(title='Ранок'))
    save_manual_prose(repo,scene.id,'А **зорі** та _місто_ — **_разом_**.\n\n<script>Текст</script>',scene.revision,content_format='markdown')
    author=repo.publication('create_signature',display_name='Автор')
    repo.publication('save_card',story_id=story.id,data=PublicationData(author_ids=[author.id],genres=['short_story']),
                     expected_revision=0,expected_signature_revisions={author.id:0})
    return repo,story


def test_markdown_projection_and_literal_legacy():
    source = 'А **зорі** та _місто_ — **_разом_**.\\n\\n<script>alert(1)</script>'.replace('\\n', '\n')
    plain = to_plain_text(source, 'markdown')
    assert plain == 'А зорі та місто — разом.\n\n<script>alert(1)</script>'
    assert to_plain_text(source, 'plain') == source
    document = parse_markdown(source)
    runs = document.paragraphs[0].runs
    assert any(run.text == 'зорі' and run.bold and not run.italic for run in runs)
    assert any(run.text == 'місто' and run.italic and not run.bold for run in runs)
    assert any(run.text == 'разом' and run.bold and run.italic for run in runs)


@pytest.mark.parametrize('source', [
    '[Посилання](https://example.org)',
    '![Фото](https://example.org/a.png)',
    '- перший\n- другий',
    '```html\n<b>текст</b>\n```',
    'Текст <i>**літерально**</i> поруч.',
])
def test_unsupported_constructs_are_literal(source):
    assert to_plain_text(source, 'markdown') == source


@pytest.mark.parametrize('source', ['Звичайне речення.', '*літерально* &amp;', '# Заголовок', '1. Список', '    **відступ**', '[лінк](url)', '---'])
def test_legacy_markdown_export_preserves_visible_text(source):
    escaped=escape_plain_markdown(source)
    assert to_plain_text(escaped,'markdown')==source
    if source=='Звичайне речення.':assert escaped==source


@pytest.mark.parametrize('format', ['fb2','epub'])
def test_ebooks_render_only_allowed_marks(tmp_path,format):
    repo,story=book(tmp_path)
    path=export_story(repo,story.id,format)
    if format=='fb2':
        doc=ET.fromstring(path.read_bytes());prefix='{http://www.gribuser.ru/xml/fictionbook/2.0}'
        assert doc.find(f'.//{prefix}body//{prefix}strong').text=='зорі'
        assert doc.find(f'.//{prefix}body//{prefix}emphasis').text=='місто'
    else:
        with zipfile.ZipFile(path) as archive:doc=ET.fromstring(archive.read('EPUB/chapter-1.xhtml'))
        prefix='{http://www.w3.org/1999/xhtml}'
        assert doc.find(f'.//{prefix}strong').text=='зорі'
        assert doc.find(f'.//{prefix}em').text=='місто'
    assert not doc.findall(f'.//{prefix}script')
    assert '<script>Текст</script>' in ''.join(doc.itertext())
    manifest=json.loads(path.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    assert manifest['scenes'][0]['content_format']=='markdown'


def test_txt_md_and_pdf_use_correct_representation(tmp_path):
    repo,story=book(tmp_path)
    txt=export_story(repo,story.id,'txt').read_text(encoding='utf-8')
    assert 'А зорі та місто — разом.' in txt and '**зорі**' not in txt
    md=export_story(repo,story.id,'md').read_text(encoding='utf-8')
    assert '**зорі**' in md
    import pdfplumber
    pdf=export_story(repo,story.id,'pdf')
    with pdfplumber.open(pdf) as document:
        chars=[char for page in document.pages for char in page.chars]
        fonts={char['fontname'] for char in chars}
        assert any('Italic' in font for font in fonts)
        assert any('BoldItalic' in font for font in fonts)
        assert '**' not in '\n'.join(page.extract_text() or '' for page in document.pages)
