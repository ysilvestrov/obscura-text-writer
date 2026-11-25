"""MANUSCRIPT-IMPORT: reads a manuscript file (DOCX, Markdown, TXT) into a flat sequence of paragraphs.

DOCX goes through the R-46 reader and uses the editor's view (insertions accepted, deletions dropped). Empty paragraphs
and blank lines are not emitted; they set `after_break` on the paragraph that follows. A DOCX soft line break (`w:br`)
splits a source paragraph into several manuscript paragraphs: no `ManuscriptParagraph.text` contains a line break. Edge
whitespace (spaces, tabs, NBSP) of every paragraph is trimmed. Every error text is for the author.
"""
import re
from dataclasses import dataclass

from .docx_import import Run, _merge, read_docx

BAD_EXTENSION = 'Непідтримуваний формат файла: потрібен .docx, .md або .txt'
BAD_ENCODING = 'Файл не в кодуванні UTF-8: збережіть його як UTF-8 і спробуйте ще раз'
_HEADING = re.compile(r'^\s{0,3}(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$')
_EMPHASIS = re.compile(r'\*\*\*(.+?)\*\*\*|\*\*(.+?)\*\*|\*(.+?)\*|(?<!\w)___(.+?)___(?!\w)|(?<!\w)__(.+?)__(?!\w)|(?<!\w)_(.+?)_(?!\w)')
_FLAGS = ((True, True), (True, False), (False, True), (True, True), (True, False), (False, True))
# A CommonMark thematic break (`---`, `***`, `___`, spaces allowed) or `# # #`: a scene separator, never a heading.
_THEMATIC_BREAK = re.compile(r' {0,3}(?:([-*_])(?:[ \t]*\1){2,}|#(?:[ \t]+#){2,})[ \t]*')
SEPARATOR_TEXT = '***'
# A backslash before ASCII punctuation is a CommonMark escape: masked with a private-use character while emphasis is parsed
# (one absent from the text, so the author's own private-use characters stay as they are).
_ESCAPE = re.compile(r'\\([!-/:-@\[-`{-~])')
_MASK = 0xE000
COMMENTS = 'Коментарі Word не імпортуються: {count}'


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
    skip: str | None = None  # 'toc': a paragraph of Word's automatic table of contents, never imported


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


def _trimmed(runs):
    """Runs without the whitespace (spaces, tabs, NBSP) at the edges of the paragraph."""
    runs = list(runs)
    while runs and not runs[0].text.strip():
        runs.pop(0)
    while runs and not runs[-1].text.strip():
        runs.pop()
    if runs:
        runs[0] = Run(runs[0].text.lstrip(), runs[0].bold, runs[0].italic)
        runs[-1] = Run(runs[-1].text.rstrip(), runs[-1].bold, runs[-1].italic)
    return tuple(runs)


def _lines(runs):
    """A paragraph's runs split at soft line breaks, each line trimmed; empty lines are left out."""
    lines, current = [], []
    for run in runs:
        for number, piece in enumerate(run.text.split('\n')):
            if number:
                lines.append(current)
                current = []
            if piece:
                current.append(Run(piece, run.bold, run.italic))
    lines.append(current)
    return [line for line in (_trimmed(_merge(line)) for line in lines) if line]


def _read_docx(content):
    try:
        document = read_docx(content)
    except ValueError as exc:
        raise ManuscriptError(str(exc)) from exc
    titles, tocs = set(document.title_paragraphs), set(document.toc_paragraphs)
    paragraphs, pending, pending_break, first = [], [], False, (False, None, None)
    joined = False  # the previous paragraph mark was deleted: the next paragraph continues the current one

    def emit(runs):
        nonlocal pending_break
        lines = _lines(runs)
        if not lines:
            pending_break = True
            return
        is_title, level, skip = first
        for number, line in enumerate(lines):  # heading level, title and break belong to the first line only
            paragraphs.append(ManuscriptParagraph(len(paragraphs), ''.join(run.text for run in line), line,
                                                  None if number else level, pending_break and not number,
                                                  is_title and not number, skip))
        pending_break = False

    for index, source in enumerate(document.paragraphs):
        if not joined:
            first = (index in titles, source.heading_level, 'toc' if index in tocs else None)
        pending.extend(source.editor)
        joined = source.mark_deleted
        if joined:
            continue
        emit(pending)
        pending = []
    if pending:  # the last paragraph mark was deleted: nothing follows to join, keep the text
        emit(pending)
    changed = sum(1 for source in document.paragraphs if source.changed)
    warnings = [warning.text for warning in document.warnings]
    if changed:
        warnings.append(f'У файлі є невирішені виправлення Word ({changed}); їх прийнято: імпортовано погляд редактора')
    if document.comments:
        warnings.append(COMMENTS.format(count=len(document.comments)))
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


def _inline(text):
    """Markdown inline text as runs: a backslash escape (before `*`, `-`, ...) is the literal character, never a mark.

    Each escape is masked with one private-use character absent from the text and restored in order after emphasis."""
    if not _ESCAPE.search(text):
        return _merge(_emphasis(text))
    sentinel = next(char for char in map(chr, range(_MASK, 0xF900)) if char not in text)
    escaped = iter(match[1] for match in _ESCAPE.finditer(text))
    runs = _emphasis(_ESCAPE.sub(sentinel, text))
    return _merge(Run(''.join(next(escaped) if char == sentinel else char for char in run.text), run.bold, run.italic)
                  for run in runs)


def _markdown(text):
    paragraphs, block, break_before, seen_blank = [], [], False, False

    def add(runs, level, after):
        runs = _trimmed(runs)
        if runs:
            paragraphs.append(ManuscriptParagraph(len(paragraphs), ''.join(r.text for r in runs), runs, level, after, False))

    def flush():
        nonlocal block, break_before
        if block:
            add(_inline(' '.join(block)), None, break_before)
            block, break_before = [], False

    for line in text.splitlines():
        heading = _HEADING.match(line)
        if not line.strip():
            flush()
            seen_blank = True
        elif _THEMATIC_BREAK.fullmatch(line):
            flush()
            add((Run(SEPARATOR_TEXT),), None, seen_blank)
            seen_blank = False
        elif heading:
            flush()
            add(_inline(heading.group(2)), len(heading.group(1)) - 1, seen_blank)
            seen_blank = False
        else:
            if not block:
                break_before, seen_blank = seen_blank, False
            block.append(line.strip())
    flush()
    return paragraphs
