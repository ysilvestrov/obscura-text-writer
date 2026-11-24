import pytest

from storygen.publication.docx_import import Run
from storygen.publication.docx_text import normalized, roundtrip_ok, serialize


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
    assert scene.text == 'x*y*\nz'
    assert (scene.position(0, 1), scene.position(0, 2), scene.position(1, 0), scene.position(1, 1)) == (2, 4, 5, 6)


def test_plain_keeps_lines():
    prose = '\n'.join(f'рядок {n}' for n in range(44))
    scene = normalized(prose, 'plain')
    assert scene.text.count('\n') == 43 and scene.text == prose and roundtrip_ok(prose, 'plain')
    assert serialize([[Run('a', italic=True, bold=True)]], 'plain').text == 'a'


@pytest.mark.parametrize('prose', ['мі*с*це', '***жирний курсив***', 'a \\* b', '\\# не заголовок', '# заголовок', '- пункт', '1. пункт',
                                   'a < b', '[x] і [y](z)', '  відступ', '&amp; і &#x20;', 'a\\\nb'])
def test_roundtrip_idempotent(prose):
    once = normalized(prose, 'markdown').text
    assert normalized(once, 'markdown').text == once
    assert roundtrip_ok(prose, 'markdown') in (True, False)


def test_leading_markers_survive():
    for prose in ['\\# не заголовок', '\\- x', '1\\. x', '\\+ x', '\\= x']:
        assert roundtrip_ok(prose, 'markdown')


def test_hard_break_is_kept_not_split():
    scene = serialize([[Run('a\nb')]], 'markdown')
    assert scene.text == 'a\nb' and scene.position(0, 3) == 3
