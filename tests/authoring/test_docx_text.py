import pytest

from storygen.publication.docx_import import Run
from storygen.publication.docx_text import _paragraphs, normalized, roundtrip_ok, serialize, visible


def test_markdown_canonical():
    assert normalized('_так_ і __це__', 'markdown').text == '*так* і **це**'


def test_blank_lines_are_empty_paragraphs():
    assert normalized('а\n\nб', 'markdown').text == 'а\n\nб'
    assert serialize([[Run('а')], [], [Run('б')]], 'markdown').text == 'а\n\nб'


def test_escaping_and_offsets():
    scene = serialize([[Run('a*b')]], 'markdown')
    assert scene.text == 'a\\*b'
    assert scene.position(0, 2) == 3
    assert scene.position(0, 3) == 4


def test_offsets_with_marks_and_second_paragraph():
    scene = serialize([[Run('x'), Run('y', italic=True)], [Run('z')]], 'markdown')
    assert scene.text == 'x*y*\n\nz'
    assert (scene.position(0, 1), scene.position(0, 2), scene.position(1, 0), scene.position(1, 1)) == (2, 4, 6, 7)


def test_plain_keeps_lines():
    prose = '\n'.join(f'рядок {n}' for n in range(44))
    scene = normalized(prose, 'plain')
    assert scene.text.count('\n') == 43 and scene.text == prose and roundtrip_ok(prose, 'plain')
    assert serialize([[Run('a', italic=True, bold=True)]], 'plain').text == 'a'


@pytest.mark.parametrize('prose, expected', [
    ('мі*с*це', True), ('***жирний курсив***', True), ('a \\* b', True), ('\\# не заголовок', True), ('a < b', True),
    ('  відступ', True), ('&amp; і &#x20;', True), ('a\\\nb', True),
    # A single-line block (heading, list item, link paragraph) would come back as an escaped plain paragraph.
    ('# заголовок', False), ('- пункт', False), ('1. пункт', False), ('[x] і [y](z)', False)])
def test_roundtrip_idempotent(prose, expected):
    once = normalized(prose, 'markdown').text
    assert normalized(once, 'markdown').text == once
    assert roundtrip_ok(prose, 'markdown') is expected


def test_leading_markers_survive():
    for prose in ['\\# не заголовок', '\\- x', '1\\. x', '\\+ x', '\\= x']:
        assert roundtrip_ok(prose, 'markdown')


def test_hard_break_is_kept_not_split():
    scene = serialize([[Run('a\nb')]], 'markdown')
    assert scene.text == 'a\nb' and scene.position(0, 3) == 3


@pytest.mark.parametrize('prose', ['Текст\n\n- a *b*\n- c\n\n> цитата\n> два', '- a *b*\n- c', '> цитата\n> два'])
def test_opaque_blocks_roundtrip(prose):
    once = normalized(prose, 'markdown').text
    assert roundtrip_ok(prose, 'markdown')
    assert normalized(once, 'markdown').text == once


@pytest.mark.parametrize('prose', ['**жирний *курсив***', '*слово**друге*', '***a*** b', '*a* *b*', '**a *b* c**', '*a **b***',
                                   '***a** b*', 'x **y**, *z*.'])
def test_emphasis_across_runs_roundtrips(prose):
    once = normalized(prose, 'markdown')
    assert roundtrip_ok(prose, 'markdown')
    assert normalized(once.text, 'markdown').text == once.text
    assert visible(_paragraphs(once.text, 'markdown')) == visible(_paragraphs(prose, 'markdown'))


def test_adjacent_runs_with_shared_flags():
    scene = serialize([[Run('жирний ', bold=True), Run('курсив', bold=True, italic=True)]], 'markdown')
    assert scene.text == '**жирний *курсив***'
    assert serialize([[Run('слово', italic=True), Run('друге', italic=True)]], 'markdown').text == '*словодруге*'
    assert [scene.text[scene.position(0, i)] for i in range(len('жирний курсив'))] == list('жирний курсив')


def test_formatted_edge_space_moves_outside_the_mark():
    runs = [Run('жирний ', bold=True), Run('далі'), Run(' курсив ', italic=True), Run('кінець')]
    scene = serialize([runs], 'markdown')
    assert scene.text == '**жирний** далі *курсив* кінець'
    assert visible(_paragraphs(scene.text, 'markdown')) == visible([runs])
    assert [scene.text[scene.position(0, i)] for i in range(len('жирний далі курсив кінець'))] == list('жирний далі курсив кінець')


def test_single_line_blocks_do_not_roundtrip():
    for prose in ['> цитата', 'Текст\n\n- пункт', '\\- a\\' + '\n' + '\\- b', '\\*\\*\\*']:
        assert not roundtrip_ok(prose, 'markdown'), prose


@pytest.mark.parametrize('prose', ['***', '---', 'Текст.\n\n* * *\n\nДалі.', '  ___'])
def test_scene_break_line_stays_a_scene_break(prose):
    # The export writes a thematic break as its literal text; the same line in DOCX comes back as the same break.
    once = normalized(prose, 'markdown').text
    assert roundtrip_ok(prose, 'markdown') and normalized(once, 'markdown').text == once
    assert serialize([[Run('Текст.')], [Run('***')], [Run('Далі.')]], 'markdown').text == 'Текст.\n\n***\n\nДалі.'
    assert serialize([[Run('***', bold=True)]], 'markdown').text == '**\\*\\*\\***'


def test_word_paragraphs_stay_paragraphs():
    scene = serialize([[Run('перший')], [Run('другий')], [], [Run('третій')]], 'markdown')
    assert scene.text == 'перший\n\nдругий\n\nтретій'
    assert len(scene.offsets) == 4 and scene.position(1, 0) == 8 and scene.position(3, 0) == 16
    assert [len(p) for p in _paragraphs(scene.text, 'markdown') if p] == [1, 1, 1]
    # A raw block (with a line break) keeps its own line endings; no blank line is added next to it.
    assert serialize([[Run('a\nb')], [Run('c')]], 'markdown').text == 'a\nb\nc'
    for prose in ['x\n- a\n- b', 'x\n 1. y\n 2. z', 'Заголовок\n---\nТекст']:
        assert roundtrip_ok(prose, 'markdown'), prose
