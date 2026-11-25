import pytest

from storygen.publication.docx_import import Run
from storygen.publication.manuscript_read import ManuscriptError, read_manuscript
from tests.publication.manuscript_fixtures import docx, markdown, para, style, tracked_del, tracked_ins, txt


def test_docx_heading_by_name_when_style_id_localized():
    content = docx(para('Частина 1', '1') + para('Текст'), [style('1', 'heading 1')])
    result = read_manuscript(content, 'book.docx')
    assert [p.heading_level for p in result.paragraphs] == [0, None]
    assert result.paragraphs[0].text == 'Частина 1'


def test_docx_heading_by_outline_level():
    content = docx(para('Глава', 'Custom') + para('Текст'), [style('Custom', 'Мій стиль', outline=1)])
    assert read_manuscript(content, 'b.docx').paragraphs[0].heading_level == 1


def test_docx_heading_by_outline_level_through_based_on():
    content = docx(para('Глава', 'Child'), [style('Base', 'Base', outline=2), style('Child', 'Child', based_on='Base')])
    assert read_manuscript(content, 'b.docx').paragraphs[0].heading_level == 2


def test_docx_paragraph_outline_level_wins_over_style():
    content = docx(para('Глава', '1', outline=3), [style('1', 'heading 1')])
    assert read_manuscript(content, 'b.docx').paragraphs[0].heading_level == 3


def test_docx_title_style():
    content = docx(para('Назва книги', 'Title') + para('Текст'), [style('Title', 'Title')])
    result = read_manuscript(content, 'b.docx')
    assert [p.is_title for p in result.paragraphs] == [True, False]


def test_docx_tracked_changes_counted():
    body = (f'<w:p>{tracked_ins("Вставлене")}{tracked_del("видалене")}</w:p>'
            f'<w:p>{tracked_del("Зникло")}<w:r><w:t>Лишилось</w:t></w:r></w:p>' + para('Чисто'))
    result = read_manuscript(docx(body), 'b.docx')
    assert result.tracked_changes == 2
    assert [p.text for p in result.paragraphs] == ['Вставлене', 'Лишилось', 'Чисто']


def test_docx_empty_paragraphs_become_after_break_and_reindexed():
    content = docx(para('Один') + para() + para('Два') + para('Три'))
    result = read_manuscript(content, 'b.docx')
    assert [(p.index, p.text, p.after_break) for p in result.paragraphs] == [(0, 'Один', False), (1, 'Два', True), (2, 'Три', False)]


def test_docx_runs_keep_italic():
    result = read_manuscript(docx(para('слово', italic=True)), 'b.docx')
    assert result.paragraphs[0].runs == (Run('слово', False, True),)


def test_docx_broken_file_is_manuscript_error():
    with pytest.raises(ManuscriptError) as error:
        read_manuscript(b'not a zip', 'b.docx')
    assert 'DOCX' in str(error.value)


def test_markdown_headings_and_emphasis():
    result = read_manuscript(markdown('# Частина 1\n\n## Глава 1\n\nТекст *курсив* і **жирний**.'), 'b.md')
    assert [p.heading_level for p in result.paragraphs] == [0, 1, None]
    assert result.paragraphs[2].text == 'Текст курсив і жирний.'
    assert Run('курсив', False, True) in result.paragraphs[2].runs
    assert Run('жирний', True, False) in result.paragraphs[2].runs


def test_markdown_heading_without_blank_line_splits_paragraph():
    result = read_manuscript(markdown('Текст\n# Глава\nДалі'), 'b.md')
    assert [(p.text, p.heading_level) for p in result.paragraphs] == [('Текст', None), ('Глава', 0), ('Далі', None)]


def test_txt_paragraphs_by_blank_lines():
    result = read_manuscript(txt('Перший\nрядок\n\nДругий\n'), 'b.txt')
    assert [p.text for p in result.paragraphs] == ['Перший рядок', 'Другий']
    assert all(p.heading_level is None for p in result.paragraphs)


def test_txt_lines_when_no_blank_lines():
    result = read_manuscript(txt('Один\nДва\nТри'), 'b.txt')
    assert [p.text for p in result.paragraphs] == ['Один', 'Два', 'Три']


def test_after_break_marks_blank_line():
    result = read_manuscript(txt('А\n\nБ\n\n\nВ'), 'b.txt')
    assert [p.after_break for p in result.paragraphs] == [False, True, True]
    result = read_manuscript(txt('А\nБ'), 'b.txt')
    assert [p.after_break for p in result.paragraphs] == [False, False]


def test_bom_accepted_and_non_utf8_rejected():
    assert read_manuscript(markdown('Привіт', bom=True), 'b.md').paragraphs[0].text == 'Привіт'
    assert read_manuscript(txt('Привіт', 'utf-8-sig'), 'b.txt').paragraphs[0].text == 'Привіт'
    with pytest.raises(ManuscriptError) as error:
        read_manuscript(txt('Привіт', 'cp1251'), 'b.txt')
    assert 'UTF-8' in str(error.value)


def test_unknown_extension_rejected():
    with pytest.raises(ManuscriptError):
        read_manuscript(b'x', 'b.rtf')


def test_extension_is_case_insensitive():
    assert read_manuscript(txt('Один'), 'B.TXT').paragraphs[0].text == 'Один'
