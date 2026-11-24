r"""IMPORT-DOCX: scene text serialization and normalization with a visible-character offset map.

Markdown rule: one paragraph is one line, paragraphs are joined by '\n', an empty paragraph is an empty line; two
non-empty single-line paragraphs in a row get a blank line between them (one '\n' would merge them into one).
A paragraph whose visible text contains '\n' is an opaque block (list, quote) that the Markdown parser keeps as one
paragraph with raw source text; it is emitted verbatim (no escaping, no marks), offsets map 1:1. A Word hard break
lands in the same path: kept as is, never silently altered; if it does not round-trip, `roundtrip_ok` is False.
A scene-break line (`***`, `---`) is emitted verbatim too. Bold and italic open and close on flag transitions.
"""
import re
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Literal, Sequence

from ..markdown_document import _ENTITY, parse_markdown
from .markup import chapter_paragraphs

_SPECIAL = frozenset('\\`*_[]<>')


@dataclass(frozen=True)
class SceneText:
    text: str
    offsets: tuple[tuple[int, ...], ...]

    def position(self, paragraph: int, offset: int) -> int:
        return self.offsets[paragraph][offset]


def _escapes(chars):
    """Per visible character: the text that stands for it in Markdown."""
    result = []
    for index, char in enumerate(chars):
        result.append('\\' + char if char in _SPECIAL else char)
    text = ''.join(chars)
    for match in _ENTITY.finditer(text):
        result[match.start()] = '\\&'
    lead = len(text) - len(text.lstrip(' \t'))
    trail = len(text) - len(text.rstrip(' 	'))
    for index in [*range(lead), *range(len(text) - trail, len(text))]:
        result[index] = '&#x20;' if chars[index] == ' ' else '&#x9;'
    if lead < len(text) and text[lead] in '#+-=':
        result[lead] = '\\' + text[lead]
    number = re.match(r'(\d{1,9})([.)])(?=\s)', text[lead:]) if lead == 0 else None
    if number:
        position = len(number[1])
        result[position] = '\\' + text[position]
    return result


def _flags(runs):
    """Per visible character: (char, bold, italic), with emphasis dropped from whitespace at the edge of a mark.

    A Markdown mark cannot touch whitespace on its inside, and emphasis of a space is not visible; a whitespace stretch
    keeps a flag only when the characters on both sides of it have that flag too (a paragraph edge has none)."""
    chars = [(char, bool(run.bold), bool(run.italic)) for run in runs for char in run.text]
    index = 0
    while index < len(chars):
        if not chars[index][0].isspace():
            index += 1
            continue
        end = index
        while end < len(chars) and chars[end][0].isspace():
            end += 1
        left = chars[index - 1][1:] if index else (False, False)
        right = chars[end][1:] if end < len(chars) else (False, False)
        for at in range(index, end):
            char, bold, italic = chars[at]
            chars[at] = (char, bold and left[0] and right[0], italic and left[1] and right[1])
        index = end
    return chars


def _segments(runs):
    """Runs as (text, bold, italic), adjacent equal formatting merged, edge whitespace without emphasis."""
    merged = []
    for char, bold, italic in _flags(runs):
        if merged and merged[-1][1:] == (bold, italic):
            merged[-1] = (merged[-1][0] + char, bold, italic)
        else:
            merged.append((char, bold, italic))
    return merged


_MARKS = {'bold': '**', 'italic': '*'}
# A CommonMark thematic break on one line: three or more of the same `*`, `-` or `_`, spaces between them allowed.
_BREAK = re.compile(r' {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*')


def _scene_break(runs, chars):
    return bool(_BREAK.fullmatch(chars)) and not any(run.bold or run.italic for run in runs)


def _marked(segments, pieces, base):
    """One Markdown paragraph line: marks open and close on flag transitions, the outer mark stays open across runs."""
    line, row, stack, cursor = '', [], [], 0
    for index, (text, bold, italic) in enumerate(segments):
        wanted = {name for name, on in (('bold', bold), ('italic', italic)) if on}
        while any(name not in wanted for name in stack):
            line += _MARKS[stack.pop()]

        def lasting(name):
            count = 0
            for _, *flags in segments[index:]:
                if not flags[0 if name == 'bold' else 1]:
                    break
                count += 1
            return count
        # The longer-lasting mark opens first, so it is the outer one; on a tie bold is outer.
        for name in sorted(wanted - set(stack), key=lambda name: (-lasting(name), name != 'bold')):
            stack.append(name)
            line += _MARKS[name]
        for _ in text:
            row.append(base + len(line))
            line += pieces[cursor]
            cursor += 1
    while stack:
        line += _MARKS[stack.pop()]
    return line, row


def serialize(paragraphs: Sequence[Sequence], content_format: Literal['plain', 'markdown']) -> SceneText:
    lines, offsets, base, prior = [], [], 0, ''
    for runs in paragraphs:
        chars = ''.join(run.text for run in runs)
        row, line = [], ''
        if content_format == 'markdown' and prior and chars and chr(10) not in prior + chars:
            # Two single-line Word paragraphs in a row: a blank line keeps them two Markdown paragraphs; a single line
            # break would join them into one. A raw block (with a line break) keeps its own line endings as is.
            lines.append('')
            base += 1
        if content_format == 'markdown' and (chr(10) in chars or _scene_break(runs, chars)):
            # An opaque block (list, quote) from the export: its single run is raw source, so it is emitted verbatim.
            # So is a scene-break line (`***`, `---`): the export writes it as literal text, it comes back as a break.
            for char in chars:
                row.append(base + len(line))
                line += char
        elif content_format == 'markdown':
            line, row = _marked(_segments(runs), _escapes(chars), base)
        else:
            for char in chars:
                row.append(base + len(line))
                line += char
        row.append(base + len(line))
        lines.append(line)
        offsets.append(tuple(row))
        base += len(line) + 1
        prior = chars
    return SceneText('\n'.join(lines), tuple(offsets))


def visible(paragraphs) -> list[list[tuple[str, bool, bool]]]:
    """Visible content: per paragraph, runs as (text, bold, italic), merged across equal formatting; emphasis of
    whitespace at the edge of a mark is not visible and not kept (see `_flags`)."""
    return [_segments(runs) for runs in paragraphs]


def _paragraphs(prose, content_format):
    return list(chapter_paragraphs(SimpleNamespace(text=prose, content_format=content_format)))


def normalized(prose: str, content_format) -> SceneText:
    return serialize(_paragraphs(prose, content_format), content_format)


def _blocks(text):
    """Block structure of Markdown: per paragraph, whether it is an opaque block (list, quote, heading, link...)."""
    return [paragraph.opaque for paragraph in parse_markdown(text).paragraphs]


def roundtrip_ok(prose: str, content_format) -> bool:
    """True when the scene goes through DOCX unchanged: the same visible text, formatting and Markdown blocks.
    A single-line block (`- пункт`, `> цитата`, `# заголовок`) reaches DOCX as plain text and would come back as
    an escaped paragraph; its scene is not imported (`unsupported_markup`)."""
    first = _paragraphs(prose, content_format)
    text = serialize(first, content_format).text
    if visible(first) != visible(_paragraphs(text, content_format)):
        return False
    return content_format != 'markdown' or _blocks(prose) == _blocks(text)


def carries(paragraphs, text: str, content_format) -> bool:
    """Whether `text` (serialized from `paragraphs`) reads back with the same visible text and formatting.
    False for a transition Markdown cannot express (e.g. italic ending in punctuation right before a letter)."""
    if content_format != 'markdown':
        return True
    return [p for p in visible(paragraphs) if p] == [p for p in visible(_paragraphs(text, content_format)) if p]
