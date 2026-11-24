from storygen.application.editor_import_match import match_scenes
from storygen.publication.docx_import import DocxManuscript, DocxParagraph, Run


def para(text, style=None, bookmark=None):
    runs = (Run(text),)
    return DocxParagraph(style, (f'_os{bookmark}',) if bookmark else (), runs, runs, False)


def doc(*paragraphs):
    return DocxManuscript(None, None, tuple(paragraphs), (), ())


ORDER = [('A', 'Перша'), ('B', 'Друга'), ('C', 'Третя')]


def test_bookmarks():
    fragments, warnings = match_scenes(doc(
        para('Книга', 'Title'), para('Частина', 'Heading1'),
        para('Перша', 'Heading2', 'A'), para('a1'), para('a2'),
        para('Інша', 'Heading2', 'B'), para('b1'),
        para('Розділ', 'Heading1'),
        para('Третя', 'Heading2', 'C'), para('c1')), ORDER)
    assert [(f.scene_id, f.how, f.first, f.last) for f in fragments] == [
        ('A', 'bookmark', 3, 5), ('B', 'bookmark', 6, 7), ('C', 'bookmark', 9, 10)]
    assert warnings == []


def test_title_fallback():
    fragments, _ = match_scenes(doc(
        para('Перша', 'Heading2'), para('a'), para('Друга', 'Heading2'), para('b'), para('Третя', 'Heading2')), ORDER)
    assert [(f.scene_id, f.how) for f in fragments] == [('A', 'title'), ('B', 'title'), ('C', 'title')]


def test_title_fallback_keeps_relative_order():
    fragments, _ = match_scenes(doc(para('Друга', 'Heading2'), para('Перша', 'Heading2', 'A')), ORDER)
    assert fragments[0].scene_id is None


def test_position_fallback():
    fragments, warnings = match_scenes(doc(
        para('Перша', 'Heading2', 'A'), para('a'), para('Зовсім нова назва', 'Heading2'), para('b'),
        para('Третя', 'Heading2', 'C')), ORDER)
    assert [(f.scene_id, f.how) for f in fragments] == [('A', 'bookmark'), ('B', 'position'), ('C', 'bookmark')]
    assert any('назву змінено редактором' in w.lower() and 'Зовсім нова назва' in w for w in warnings)


def test_position_at_edges():
    fragments, _ = match_scenes(doc(
        para('Нова', 'Heading2'), para('Друга', 'Heading2', 'B'), para('Нова2', 'Heading2')), ORDER)
    assert [f.scene_id for f in fragments] == ['A', 'B', 'C']


def test_position_ambiguous():
    order = [('A', 'a'), ('B', 'b'), ('C', 'c'), ('D', 'd')]
    fragments, warnings = match_scenes(doc(
        para('a', 'Heading2', 'A'), para('Х', 'Heading2'), para('Y', 'Heading2'), para('d', 'Heading2', 'D')), order)
    assert [f.scene_id for f in fragments] == ['A', None, None, 'D']
    assert any('«Х»' in w for w in warnings)


def test_duplicate_bookmark_or_unknown_id():
    fragments, _ = match_scenes(doc(para('Перша', 'Heading2', 'A'), para('Перша', 'Heading2', 'A')), ORDER)
    assert [f.scene_id for f in fragments] == [None, None]
    fragments, warnings = match_scenes(doc(para('Невідома', 'Heading2', 'Z')), ORDER)
    assert fragments[0].scene_id is None and fragments[0].how is None
    assert any('Невідома' in w for w in warnings)
