"""IMPORT-DOCX-S01: the DOCX reader of an editor's file."""
import io
import zipfile

import pytest

from storygen.publication import docx_import
from storygen.publication.docx_import import read_docx
from tests.authoring.test_docx_exports import _rewrite, flat_book, rendered, runs
from tests.authoring.test_ebook_exports import seeded

WNS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def package(document_body, comments=None, extra=None):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('word/document.xml', f'<w:document {WNS}><w:body>{document_body}</w:body></w:document>')
        if comments is not None:
            archive.writestr('word/comments.xml', f'<w:comments {WNS}>{comments}</w:comments>')
        for name, data in (extra or {}).items():
            archive.writestr(name, data)
    return out.getvalue()


def only(manuscript):
    assert len(manuscript.paragraphs) == 1
    return manuscript.paragraphs[0]


def text(paragraph_runs):
    return ''.join(run.text for run in paragraph_runs)


def test_reads_exported_manuscript(tmp_path):
    repo, story = seeded(tmp_path, count=3)
    book, content = rendered(repo, story)
    manuscript = read_docx(content)
    assert manuscript.story_id == story.id and manuscript.export_id == book.export_id
    marked = [(p.style, p.bookmarks) for p in manuscript.paragraphs if p.bookmarks]
    assert marked == [('Heading2', ('_os' + chapter.entry['scene_id'],)) for chapter in book.chapters]
    assert all(p.editor == p.original and p.changed is False for p in manuscript.paragraphs)
    assert manuscript.warnings == ()
    repo, story = flat_book(tmp_path / 'md', 'Слово *курсив* і **жирний**.\n', content_format='markdown')
    _, content = rendered(repo, story)
    found = [(r.text, r.bold, r.italic) for p in read_docx(content).paragraphs for r in p.editor]
    assert set(runs(content)) <= set(found)
    repo, story = flat_book(tmp_path / 'plain', 'ліва\tправа\nрядок\n')
    _, content = rendered(repo, story)
    assert [text(p.editor) for p in read_docx(content).paragraphs][-2:] == ['ліва\tправа', 'рядок']


def test_break_and_tab_elements_read_as_controls():
    paragraph = only(read_docx(package('<w:p><w:r><w:t>а</w:t><w:br/><w:t>б</w:t><w:tab/><w:t>в</w:t></w:r></w:p>')))
    assert text(paragraph.original) == 'а\nб\tв'


def test_tracked_changes_two_views():
    paragraph = only(read_docx(package(
        '<w:p><w:r><w:t>Він </w:t></w:r><w:del><w:r><w:delText>швидко</w:delText></w:r></w:del>'
        '<w:ins><w:r><w:t>повільно</w:t></w:r></w:ins><w:r><w:t> пішов</w:t></w:r></w:p>')))
    assert text(paragraph.editor) == 'Він повільно пішов'
    assert text(paragraph.original) == 'Він швидко пішов'
    assert paragraph.changed is True


def test_runs_with_same_flags_merge():
    paragraph = only(read_docx(package(
        '<w:p><w:r><w:t>а</w:t></w:r><w:r><w:t>б</w:t></w:r><w:r><w:rPr><w:b/></w:rPr><w:t>в</w:t></w:r></w:p>')))
    assert paragraph.editor == (docx_import.Run('аб'), docx_import.Run('в', bold=True))


def test_comment_ranges_in_original_view():
    comments = ('<w:comment w:id="7" w:author="Редактор" w:initials="Р"><w:p><w:r><w:t>Занадто</w:t></w:r></w:p>'
                '<w:p><w:r><w:t>різко</w:t></w:r></w:p></w:comment>')
    content = package(
        '<w:p><w:r><w:t>Він </w:t></w:r><w:commentRangeStart w:id="7"/><w:del><w:r><w:delText>швидко</w:delText></w:r></w:del>'
        '<w:ins><w:r><w:t>повільно</w:t></w:r></w:ins><w:commentRangeEnd w:id="7"/><w:r><w:commentReference w:id="7"/></w:r>'
        '<w:r><w:t> пішов</w:t></w:r></w:p>', comments)
    manuscript = read_docx(content)
    (comment,) = manuscript.comments
    assert (comment.id, comment.author, comment.text) == ('7', 'Редактор', 'Занадто\nрізко')
    assert comment.start == (0, 4)
    assert comment.end == (0, 10)


def test_comment_range_across_paragraphs_and_without_bounds():
    comments = ('<w:comment w:id="1" w:author="А"><w:p><w:r><w:t>x</w:t></w:r></w:p></w:comment>'
                '<w:comment w:id="2" w:author="Б"><w:p><w:r><w:t>y</w:t></w:r></w:p></w:comment>')
    manuscript = read_docx(package(
        '<w:p><w:r><w:t>перший</w:t></w:r><w:commentRangeStart w:id="1"/></w:p>'
        '<w:p><w:r><w:t>другий</w:t></w:r><w:commentRangeEnd w:id="1"/></w:p>', comments))
    first, second = manuscript.comments
    assert first.start == (0, 6) and first.end == (1, 6)
    assert second.start is None and second.end is None


def _bomb():
    return package('<w:p><w:r><w:t>' + 'а' * 5000 + '</w:t></w:r></w:p>')


def test_rejects_not_zip_ole_and_missing_document():
    for bad in (b'not a zip', b'\xd0\xcf\x11\xe0' + b'\x00' * 100):
        with pytest.raises(ValueError):
            read_docx(bad)
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as archive:
        archive.writestr('word/other.xml', '<x/>')
    with pytest.raises(ValueError):
        read_docx(out.getvalue())


def test_rejects_doctype(tmp_path):
    repo, story = flat_book(tmp_path, 'Текст.\n')
    _, content = rendered(repo, story)
    bad = _rewrite(content, lambda xml: xml.replace('<w:document', '<!DOCTYPE d [<!ENTITY a "b">]><w:document', 1))
    with pytest.raises(ValueError):
        read_docx(bad)
    with pytest.raises(ValueError):
        read_docx(package('<w:p/>', extra={'docProps/custom.xml': '<!DOCTYPE x><Properties/>'}))


def test_rejects_oversized_file(monkeypatch):
    monkeypatch.setattr(docx_import, 'MAX_FILE', 100)
    with pytest.raises(ValueError):
        read_docx(_bomb())


def test_rejects_unpacked_by_declared_size(monkeypatch):
    monkeypatch.setattr(docx_import, 'MAX_UNPACKED', 1000)
    with pytest.raises(ValueError):
        read_docx(_bomb())


def test_rejects_unpacked_by_actual_reading(monkeypatch):
    """The declared size lies: the stream keeps yielding bytes past the limit, and reading in chunks stops it."""
    class Endless:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, size):
            return b'a' * size

    monkeypatch.setattr(docx_import, 'MAX_UNPACKED', 10_000)
    monkeypatch.setattr(docx_import, 'CHUNK', 1024)
    content = _bomb()
    monkeypatch.setattr(zipfile.ZipFile, 'open', lambda self, info, *a, **k: Endless())
    with pytest.raises(ValueError, match='розпаковування'):
        read_docx(content)


def test_unsupported_content_warns():
    manuscript = read_docx(package(
        '<w:p><w:r><w:t>перший</w:t></w:r><w:r><w:drawing/></w:r></w:p>'
        '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>у таблиці</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
        '<w:p><w:r><w:t>другий</w:t></w:r><w:r><w:footnoteReference w:id="2"/></w:r></w:p>'
        '<w:p><w:r><w:rPr><w:b/><w:rPrChange w:id="1" w:author="A"><w:rPr/></w:rPrChange></w:rPr><w:t>третій</w:t></w:r></w:p>'))
    assert [text(p.editor) for p in manuscript.paragraphs] == ['перший', 'другий', 'третій']
    assert len(manuscript.warnings) == 4
    assert all(w.paragraph in (0, 1, 2) for w in manuscript.warnings)
    # The table sits after paragraph 0 and is reported against it.
    assert sum('таблицю' in w.text for w in manuscript.warnings if w.paragraph == 0) == 1
    assert any('виноску' in w.text for w in manuscript.warnings if w.paragraph == 1)
    assert any('форматування' in w.text for w in manuscript.warnings if w.paragraph == 2)
    assert not any('абзац' in w.text for w in manuscript.warnings)


def test_table_first_has_no_paragraph_index():
    manuscript = read_docx(package('<w:tbl><w:tr><w:tc><w:p/></w:tc></w:tr></w:tbl><w:p><w:r><w:t>а</w:t></w:r></w:p>'))
    assert [w.paragraph for w in manuscript.warnings] == [None]


def test_nested_insert_then_delete_is_in_neither_view():
    comments = '<w:comment w:id="1" w:author="А"><w:p><w:r><w:t>x</w:t></w:r></w:p></w:comment>'
    manuscript = read_docx(package(
        '<w:p><w:r><w:t>а</w:t></w:r><w:ins><w:del><w:r><w:delText>ХХ</w:delText></w:r></w:del></w:ins>'
        '<w:del><w:ins><w:r><w:t>УУ</w:t></w:r></w:ins></w:del><w:commentRangeStart w:id="1"/><w:r><w:t>б</w:t></w:r>'
        '<w:commentRangeEnd w:id="1"/></w:p>', comments))
    paragraph = only(manuscript)
    assert text(paragraph.editor) == 'аб' and text(paragraph.original) == 'аб' and paragraph.changed is True
    assert manuscript.comments[0].start == (0, 1) and manuscript.comments[0].end == (0, 2)


def test_deep_nesting_is_a_value_error():
    depth = 5000
    body = '<w:p>' + '<w:ins>' * depth + '<w:r><w:t>а</w:t></w:r>' + '</w:ins>' * depth + '</w:p>'
    with pytest.raises(ValueError):
        read_docx(package(body))
    with pytest.raises(ValueError):
        read_docx(package('<w:sdt>' * depth + '</w:sdt>' * depth))


def test_paragraph_mark_revisions():
    manuscript = read_docx(package(
        '<w:p><w:pPr><w:rPr><w:ins w:id="1" w:author="Р"/></w:rPr></w:pPr><w:ins w:id="2" w:author="Р">'
        '<w:r><w:t>нове</w:t></w:r></w:ins></w:p>'
        '<w:p><w:pPr><w:rPr><w:del w:id="3" w:author="Р"/></w:rPr></w:pPr><w:r><w:t>злито</w:t></w:r></w:p>'
        '<w:p><w:pPr><w:rPr><w:ins w:id="4" w:author="Р"/><w:del w:id="5" w:author="Р"/></w:rPr></w:pPr></w:p>'
        '<w:p><w:r><w:t>звичайний</w:t></w:r></w:p>'))
    flags = [(p.mark_inserted, p.mark_deleted, p.changed) for p in manuscript.paragraphs]
    assert flags == [(True, False, True), (False, True, True), (True, True, True), (False, False, False)]
