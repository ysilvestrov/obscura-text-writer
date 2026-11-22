"""EXPORT-DOCX-S03: the RTF manuscript."""
import pytest

from storygen.publication.book import capture
from storygen.publication import rtf
from tests.authoring.test_docx_exports import INVALID_XML, flat_book
from tests.authoring.test_ebook_exports import seeded


def rendered(repo, story, allow_incomplete=False):
    return rtf.render(capture(repo, story.id, 'rtf', allow_incomplete)).decode('ascii')


def test_rtf_header_and_page(tmp_path):
    repo, story = seeded(tmp_path, count=2)
    text = rendered(repo, story)
    assert text.startswith('{\\rtf1\\ansi')
    for token in ['\\paperw11906', '\\paperh16838', '\\margl1417', '\\fs24', 'heading 1;', 'heading 2;', '{\\footer', '\\chpgn']:
        assert token in text
    assert text.rstrip().endswith('}')


def test_rtf_escaping(tmp_path):
    repo, story = flat_book(tmp_path, 'a\\b{c} Ї 😀\n')
    text = rendered(repo, story)
    assert 'a\\\\b\\{c\\}' in text
    assert '\\u1031?' in text
    assert '\\u-10179?\\u-8704?' in text


def test_rtf_runs_and_scene_order(tmp_path):
    repo, story = flat_book(tmp_path, 'Слово *курсив* і **жирний**.\n', content_format='markdown')
    text = rendered(repo, story)
    assert '{\\i ' in text and '{\\b ' in text
    repo, story = flat_book(tmp_path / 'plain', 'ліва\tправа\n')
    assert '\\tab ' in rendered(repo, story)
    repo, story = seeded(tmp_path / 'order', count=3)
    trashed = repo.list_scenes(story.id)[1]
    repo.set_scene_trashed(story.id, trashed.id, repo.get_scene(trashed.id).revision, False)
    text = rendered(repo, story, allow_incomplete=True)
    first, third = text.index(rtf.encode('Сцена 1: <Двері>')), text.index(rtf.encode('Сцена 3: <Двері>'))
    assert first < third and rtf.encode('Сцена 2: <Двері>') not in text
    assert text.count('\\pagebb') == 2


def test_rtf_language(tmp_path):
    repo, story = flat_book(tmp_path, 'Текст.\n', card_language='uk-UA')
    assert '\\deflang1058' in rendered(repo, story)
    repo, story = flat_book(tmp_path / 'fr', 'Texte.\n', card_language='fr')
    assert '\\deflang' not in rendered(repo, story)
    repo, story = flat_book(tmp_path / 'scene', 'Text.\n', language='uk', scene_language='en')
    assert '\\lang1033' in rendered(repo, story)


def test_rtf_line_breaks_in_markdown(tmp_path):
    repo, story = flat_book(tmp_path, 'Рядок один  \nрядок два.\n', content_format='markdown')
    assert '\\line ' in rendered(repo, story)


def test_rtf_invalid_xml_character_raises(tmp_path):
    repo, story = flat_book(tmp_path, 'Погано\x01.\n')
    with pytest.raises(ValueError, match=INVALID_XML):
        rendered(repo, story)


def test_rtf_document_language_reaches_the_text(tmp_path):
    # Word applies \deflang only as a default; without \lang the text takes the system language (seen: 1045).
    repo, story = flat_book(tmp_path, 'Текст.\n', card_language='uk-UA')
    assert '\\f0\\fs24\\lang1058' in rendered(repo, story)
    repo, story = flat_book(tmp_path / 'fr', 'Texte.\n', card_language='fr')
    assert '\\f0\\fs24\n' in rendered(repo, story)
