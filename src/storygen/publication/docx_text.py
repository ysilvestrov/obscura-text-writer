r"""IMPORT-DOCX: scene text serialization and normalization with a visible-character offset map.

Markdown rule: one paragraph is one line, paragraphs are joined by '\n', an empty paragraph is an empty line.
A paragraph whose visible text contains '\n' is an opaque block (list, quote) that the Markdown parser keeps as one
paragraph with raw source text; it is emitted verbatim (no escaping, no marks), offsets map 1:1. A Word hard break
lands in the same path: kept as is, never silently altered; if it does not round-trip, `roundtrip_ok` is False.
"""
import re
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Literal, Sequence

from ..markdown_document import _ENTITY
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


def serialize(paragraphs: Sequence[Sequence], content_format: Literal['plain', 'markdown']) -> SceneText:
    lines, offsets, base = [], [], 0
    for runs in paragraphs:
        chars = ''.join(run.text for run in runs)
        row, line = [], ''
        if content_format == 'markdown' and chr(10) in chars:
            # An opaque block (list, quote) from the export: its single run is raw source, so it is emitted verbatim.
            for char in chars:
                row.append(base + len(line))
                line += char
        elif content_format == 'markdown':
            pieces = _escapes(chars)
            cursor = 0
            for run in runs:
                if not run.text:
                    continue
                mark = ('**' if run.bold else '') + ('*' if run.italic else '')
                line += mark
                for _ in run.text:
                    row.append(base + len(line))
                    line += pieces[cursor]
                    cursor += 1
                line += mark[::-1]
        else:
            for char in chars:
                row.append(base + len(line))
                line += char
        row.append(base + len(line))
        lines.append(line)
        offsets.append(tuple(row))
        base += len(line) + 1
    return SceneText('\n'.join(lines), tuple(offsets))


def visible(paragraphs) -> list[list[tuple[str, bool, bool]]]:
    """Visible content: per paragraph, runs as (text, bold, italic), merged across equal formatting."""
    result = []
    for runs in paragraphs:
        merged = []
        for run in runs:
            if not run.text:
                continue
            if merged and merged[-1][1:] == (bool(run.bold), bool(run.italic)):
                merged[-1] = (merged[-1][0] + run.text, merged[-1][1], merged[-1][2])
            else:
                merged.append((run.text, bool(run.bold), bool(run.italic)))
        result.append(merged)
    return result


def _paragraphs(prose, content_format):
    return list(chapter_paragraphs(SimpleNamespace(text=prose, content_format=content_format)))


def normalized(prose: str, content_format) -> SceneText:
    return serialize(_paragraphs(prose, content_format), content_format)


def roundtrip_ok(prose: str, content_format) -> bool:
    first = _paragraphs(prose, content_format)
    again = _paragraphs(serialize(first, content_format).text, content_format)
    return visible(first) == visible(again)
