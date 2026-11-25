"""MANUSCRIPT-IMPORT: reads a manuscript file (DOCX, Markdown, TXT) into a flat sequence of paragraphs.

DOCX goes through the R-46 reader and uses the editor's view (insertions accepted, deletions dropped). Empty paragraphs
and blank lines are not emitted; they set `after_break` on the paragraph that follows. Every error text is for the author.
"""
import re
from dataclasses import dataclass

from .docx_import import Run, _merge, read_docx

BAD_EXTENSION = 'Непідтримуваний формат файла: потрібен .docx, .md або .txt'
BAD_ENCODING = 'Файл не в кодуванні UTF-8: збережіть його як UTF-8 і спробуйте ще раз'
_HEADING = re.compile(r'^\s{0,3}(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$')
_EMPHASIS = re.compile(r'\*\*\*(.+?)\*\*\*|\*\*(.+?)\*\*|\*(.+?)\*|(?<!\w)___(.+?)___(?!\w)|(?<!\w)__(.+?)__(?!\w)|(?<!\w)_(.+?)_(?!\w)')
_FLAGS = ((True, True), (True, False), (False, True), (True, True), (True, False), (False, True))


class ManuscriptError(ValueError):
    """The file cannot be read as a manuscript; the message is shown to the author."""


@dataclass(frozen=True)
class ManuscriptParagraph:
    index: int
    text: str
    runs: tuple[Run, ...]
    heading_level: int | None
    after_break: bool
    is_title: bool


@dataclass(frozen=True)
class ReadManuscript:
    paragraphs: tuple[ManuscriptParagraph, ...]
    warnings: tuple[str, ...]
    tracked_changes: int


def read_manuscript(content: bytes, file_name: str) -> ReadManuscript:
    extension = file_name.rsplit('.', 1)[-1].lower() if '.' in file_name else ''
    if extension == 'docx':
        return _read_docx(content)
    if extension in ('md', 'txt'):
        text = _decode(content)
        return ReadManuscript(tuple(_markdown(text) if extension == 'md' else _plain(text)), (), 0)
    raise ManuscriptError(BAD_EXTENSION)


def _decode(content):
    try:
        return content.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ManuscriptError(BAD_ENCODING) from exc


def _read_docx(content):
    try:
        document = read_docx(content)
    except ValueError as exc:
        raise ManuscriptError(str(exc)) from exc
    titles = set(document.title_paragraphs)
    paragraphs, pending, pending_break, first_title, first_level = [], [], False, False, None
    joined = False  # the previous paragraph mark was deleted: the next paragraph continues the current one
    for index, source in enumerate(document.paragraphs):
        if not joined:
            first_title, first_level = index in titles, source.heading_level
        pending.extend(source.editor)
        joined = source.mark_deleted
        if joined:
            continue
        runs = _merge(pending)
        pending = []
        text = ''.join(run.text for run in runs)
        if not text.strip():
            pending_break = True
            continue
        paragraphs.append(ManuscriptParagraph(len(paragraphs), text, runs, first_level, pending_break, first_title))
        pending_break = False
    if pending:  # the last paragraph mark was deleted: nothing follows to join, keep the text
        runs = _merge(pending)
        text = ''.join(run.text for run in runs)
        if text.strip():
            paragraphs.append(ManuscriptParagraph(len(paragraphs), text, runs, first_level, pending_break, first_title))
    changed = sum(1 for source in document.paragraphs if source.changed)
    warnings = [warning.text for warning in document.warnings]
    if changed:
        warnings.append(f'У файлі є невирішені виправлення Word ({changed}); їх прийнято: імпортовано погляд редактора')
    return ReadManuscript(tuple(paragraphs), tuple(dict.fromkeys(warnings)), changed)


def _blocks(text):
    """(lines, after_break) groups of consecutive non-blank lines."""
    block, after_break, seen = [], False, False
    for line in text.splitlines():
        if line.strip():
            if not block:
                after_break = seen
            block.append(line.strip())
        elif block:
            yield block, after_break
            block, seen = [], True
        else:
            seen = True
    if block:
        yield block, after_break


_SENTENCE_END = ('.', '!', '?', '…', '»', '"', '”', ':')


def _hard_wrapped(lines):
    """Most non-final lines stop without sentence-ending punctuation: the block is one wrapped paragraph."""
    open_lines = sum(1 for line in lines[:-1] if not line.endswith(_SENTENCE_END))
    return open_lines * 2 > len(lines) - 1


def _plain(text):
    blocks = list(_blocks(text))
    has_blank = any(not line.strip() for line in text.strip().splitlines())
    result = []
    for lines, after in blocks:
        if len(lines) == 1 or (has_blank and _hard_wrapped(lines)):
            lines = [" ".join(lines)]
        for i, line in enumerate(lines):
            result.append(ManuscriptParagraph(len(result), line, (Run(line),), None, after and i == 0, False))
    return result


def _emphasis(text, bold=False, italic=False):
    runs, position = [], 0
    for match in _EMPHASIS.finditer(text):
        runs.append(Run(text[position:match.start()], bold, italic))
        group = next(i for i, value in enumerate(match.groups()) if value is not None)
        b, i = _FLAGS[group]
        runs.extend(_emphasis(match.group(group + 1), bold or b, italic or i))
        position = match.end()
    runs.append(Run(text[position:], bold, italic))
    return runs


def _markdown(text):
    paragraphs, block, break_before, seen_blank = [], [], False, False

    def flush():
        nonlocal block, break_before
        if block:
            runs = _merge(_emphasis(' '.join(block)))
            paragraphs.append(ManuscriptParagraph(len(paragraphs), ''.join(r.text for r in runs), runs, None, break_before, False))
            block, break_before = [], False

    for line in text.splitlines():
        heading = _HEADING.match(line)
        if not line.strip():
            flush()
            seen_blank = True
        elif heading:
            flush()
            runs = _merge(_emphasis(heading.group(2)))
            if runs:
                paragraphs.append(ManuscriptParagraph(len(paragraphs), ''.join(r.text for r in runs), runs,
                                                      len(heading.group(1)) - 1, seen_blank, False))
            seen_blank = False
        else:
            if not block:
                break_before, seen_blank = seen_blank, False
            block.append(line.strip())
    flush()
    return paragraphs
