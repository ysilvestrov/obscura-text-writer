import pytest

from storygen.publication.docx_import import Run
from storygen.publication.manuscript_read import ManuscriptError, read_manuscript
from storygen.publication.docx_text import serialize
from storygen.publication.manuscript_structure import ParseSettings, detect
from tests.publication.manuscript_fixtures import T, comments, docx, markdown, para, style, tracked_del, tracked_ins, txt


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


def test_txt_one_line_per_paragraph_with_scene_breaks():
    result = read_manuscript(txt('— Привіт.\n— Здоров!\n— Як справи?\n\n— Добре.\n— Чудово.'), 'b.txt')
    assert [(p.text, p.after_break) for p in result.paragraphs] == [
        ('— Привіт.', False), ('— Здоров!', False), ('— Як справи?', False), ('— Добре.', True), ('— Чудово.', False)]


def test_txt_hard_wrapped_blocks_joined():
    result = read_manuscript(txt('Це довге речення, яке\nпереносять посеред\nдумки.\n\nДругий абзац теж\nпереноситься.'), 'b.txt')
    assert [p.text for p in result.paragraphs] == [
        'Це довге речення, яке переносять посеред думки.', 'Другий абзац теж переноситься.']


def test_docx_deleted_mark_on_last_paragraph_keeps_text():
    body = ('<w:p><w:r><w:t>Перший</w:t></w:r></w:p>'
            '<w:p><w:pPr><w:rPr><w:del w:id="5" w:author="Р"/></w:rPr></w:pPr><w:r><w:t>Останній</w:t></w:r></w:p>')
    result = read_manuscript(docx(body), 'b.docx')
    assert [p.text for p in result.paragraphs] == ['Перший', 'Останній']


def test_docx_outline_level_9_overrides_heading_style():
    content = docx(para('Звичайний', '1', outline=9) + para('Стиль-тіло', 'Body') + para('Глава', '1'),
                   [style('1', 'heading 1'), style('Body', 'Body', outline=9, based_on='1')])
    assert [p.heading_level for p in read_manuscript(content, 'b.docx').paragraphs] == [None, None, 0]


def test_docx_soft_line_break_splits_paragraph():
    poem = f'<w:p><w:r><w:rPr><w:i/></w:rPr>{T}Рядок вірша один</w:t><w:br/>{T}Рядок вірша два</w:t></w:r></w:p>'
    heading = f'<w:p><w:pPr><w:pStyle w:val="H"/></w:pPr><w:r>{T}Глава 1</w:t><w:br/>{T}Підзаголовок</w:t></w:r></w:p>'
    content = docx(heading + para('Перший абзац.') + para() + poem + para('Останній абзац.'), [style('H', 'heading 1')])
    result = read_manuscript(content, 'b.docx').paragraphs
    assert [(p.index, p.text, p.heading_level, p.after_break) for p in result] == [
        (0, 'Глава 1', 0, False), (1, 'Підзаголовок', None, False), (2, 'Перший абзац.', None, False),
        (3, 'Рядок вірша один', None, True), (4, 'Рядок вірша два', None, False), (5, 'Останній абзац.', None, False)]
    assert not any('\n' in p.text for p in result)
    assert result[3].runs == (Run('Рядок вірша один', False, True),) and result[4].runs == (Run('Рядок вірша два', False, True),)
    text = serialize([p.runs for p in result[2:]], 'markdown').text
    assert text == 'Перший абзац.\n\n*Рядок вірша один*\n\n*Рядок вірша два*\n\nОстанній абзац.'


def test_docx_edge_tabs_and_nbsp_trimmed():
    body = (f'<w:p><w:r><w:tab/>{T}\u00a0Абзац з відступом.\u00a0</w:t><w:tab/></w:r></w:p>'
            f'<w:p><w:r><w:rPr><w:i/></w:rPr><w:tab/></w:r><w:r>{T}Другий.</w:t></w:r></w:p>')
    result = read_manuscript(docx(body), 'b.docx').paragraphs
    assert [p.text for p in result] == ['Абзац з відступом.', 'Другий.']
    assert result[0].runs == (Run('Абзац з відступом.'),) and result[1].runs == (Run('Другий.'),)
    assert '&#x9;' not in serialize([p.runs for p in result], 'markdown').text


def test_markdown_backslash_escapes_decoded():
    text = '\- Привіт, — сказав він.\n\nЗ \*зірочкою\* і *курсивом \* теж*.\n\n\# Не заголовок \_так\_\.'
    result = read_manuscript(markdown(text), 'b.md').paragraphs
    assert [p.text for p in result] == ['- Привіт, — сказав він.', 'З *зірочкою* і курсивом * теж.', '# Не заголовок _так_.']
    assert result[1].runs == (Run('З *зірочкою* і '), Run('курсивом * теж', False, True), Run('.'))
    assert result[2].heading_level is None
    # Obscura's own Markdown export escapes a leading dash; the import keeps it as the same text, not `\-`.
    assert serialize([result[0].runs], 'markdown').text == '\- Привіт, — сказав він.'


def test_markdown_thematic_breaks_are_scene_separators():
    text = 'А.\n\n---\n\nБ.\n\n* * *\n\nВ.\n\n___\n\nГ.\n\n# # #\n\nД.\n\n- - -\n\nЕ.'
    result = read_manuscript(markdown(text), 'b.md').paragraphs
    assert all(p.heading_level is None for p in result)
    assert all(not (run.bold or run.italic) for p in result for run in p.runs)
    structure = detect(result, ParseSettings())
    assert [structure.prose_indices] == [(0, 2, 4, 6, 8, 10)]
    assert [(s.start, s.end) for s in structure.scenes] == [(0, 0), (2, 2), (4, 4), (6, 6), (8, 8), (10, 10)]


def test_docx_comments_warning():
    content = docx(para('Текст.'), parts=comments('Перша примітка', 'Друга'))
    assert 'Коментарі Word не імпортуються: 2' in read_manuscript(content, 'b.docx').warnings
    assert not any('Коментарі' in w for w in read_manuscript(docx(para('Текст.')), 'b.docx').warnings)
