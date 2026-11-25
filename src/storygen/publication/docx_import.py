"""IMPORT-DOCX: a safe reader of an editor's Word file, built on zipfile and ElementTree without new dependencies.

It reads only word/document.xml, word/comments.xml, word/styles.xml (optional, for heading levels and the Title
style), docProps/custom.xml and [Content_Types].xml. Every paragraph
carries two views: the editor's (w:ins kept, w:del dropped) and the original (w:del kept, w:ins dropped);
comment ranges are measured in the original view.
"""
import io
import re
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from .docx import W

MAX_FILE = 20 * 1024 * 1024
MAX_UNPACKED = 100 * 1024 * 1024
CHUNK = 64 * 1024
OLE_MAGIC = b'\xd0\xcf\x11\xe0'
PARTS = ('[Content_Types].xml', 'word/document.xml', 'word/comments.xml', 'word/styles.xml', 'docProps/custom.xml')
_DOCTYPE = re.compile(rb'<!doctype', re.I)
_OFF = {'0', 'false', 'off', 'none'}
# Nesting of tracked changes: text inserted and then deleted never was in the original and is not in the result.
_COMBINE = {('both', 'ins'): 'ins', ('both', 'del'): 'del', ('ins', 'ins'): 'ins', ('del', 'del'): 'del',
            ('ins', 'del'): 'none', ('del', 'ins'): 'none', ('none', 'ins'): 'none', ('none', 'del'): 'none'}
_TRANSPARENT = ('hyperlink', 'smartTag', 'sdt', 'sdtContent', 'fldSimple', 'customXml')


@dataclass(frozen=True)
class Run:
    text: str
    bold: bool = False
    italic: bool = False


@dataclass(frozen=True)
class DocxParagraph:
    style: str | None
    bookmarks: tuple[str, ...]
    editor: tuple[Run, ...]
    original: tuple[Run, ...]
    changed: bool
    # Paragraph-mark revisions (w:pPr/w:rPr/w:ins|del): an inserted mark joins this paragraph with the next one in
    # the original view, a deleted mark joins them in the editor's view.
    mark_inserted: bool = False
    mark_deleted: bool = False
    heading_level: int | None = None  # 0-based: outlineLvl of the paragraph or its style chain, else 'heading N' -> N-1


@dataclass(frozen=True)
class DocxComment:
    id: str
    author: str
    text: str
    start: tuple[int, int] | None
    end: tuple[int, int] | None


@dataclass(frozen=True)
class DocxWarning:
    paragraph: int | None  # 0-based index into DocxManuscript.paragraphs; None for the document as a whole
    text: str


@dataclass(frozen=True)
class DocxManuscript:
    story_id: str | None
    export_id: str | None
    paragraphs: tuple[DocxParagraph, ...]
    comments: tuple[DocxComment, ...]
    warnings: tuple[DocxWarning, ...]
    title_paragraphs: tuple[int, ...] = ()  # indexes of paragraphs whose style is named 'title'


def _q(name):
    return f'{{{W}}}{name}'


def _read_parts(content):
    if len(content) > MAX_FILE:
        raise ValueError('DOCX: файл завеликий для імпорту')
    if content[:4] == OLE_MAGIC:
        raise ValueError('DOCX: файл зашифровано або це старий формат Word; збережіть його як звичайний .docx без пароля')
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise ValueError('DOCX: файл не є пакетом DOCX (ZIP)') from exc
    with archive:
        infos = {}
        for info in archive.infolist():
            infos.setdefault(info.filename, info)
        if 'word/document.xml' not in infos:
            raise ValueError('DOCX: у файлі немає word/document.xml')
        if sum(infos[name].file_size for name in PARTS if name in infos) > MAX_UNPACKED:
            raise ValueError('DOCX: вміст файлу завеликий після розпаковування')
        total = 0
        result = {}
        for name in PARTS:
            if name not in infos:
                continue
            chunks = []
            try:
                with archive.open(infos[name]) as stream:
                    while True:
                        chunk = stream.read(CHUNK)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > MAX_UNPACKED:
                            raise ValueError('DOCX: вміст файлу завеликий після розпаковування')
                        chunks.append(chunk)
            except (zipfile.BadZipFile, NotImplementedError, RuntimeError, EOFError) as exc:
                raise ValueError('DOCX: файл пошкоджено') from exc
            data = b''.join(chunks)
            if _DOCTYPE.search(data.replace(b'\x00', b'')):
                raise ValueError('DOCX: файл містить DOCTYPE; такий XML не читається')
            result[name] = data
    return result


def _parse(data, name):
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError(f'DOCX: {name} не є коректним XML') from exc


def _flag(rpr, tag):
    if rpr is None:
        return False
    element = rpr.find(_q(tag))
    return element is not None and (element.get(_q('val')) or '').lower() not in _OFF


def _merge(runs):
    out = []
    for run in runs:
        if not run.text:
            continue
        if out and out[-1].bold == run.bold and out[-1].italic == run.italic:
            out[-1] = Run(out[-1].text + run.text, run.bold, run.italic)
        else:
            out.append(run)
    return tuple(out)


_HEADING_NAME = re.compile(r'heading\s*([1-9])', re.I)


def _styles(data):
    """styleId -> (name, outlineLvl, basedOn) from word/styles.xml."""
    result = {}
    if data is None:
        return result
    for style in _parse(data, 'word/styles.xml').iter(_q('style')):
        key = style.get(_q('styleId'))
        if not key:
            continue
        name = style.find(_q('name'))
        outline = style.find(f'{_q("pPr")}/{_q("outlineLvl")}')
        based = style.find(_q('basedOn'))
        result[key] = ((name.get(_q('val')) or '') if name is not None else '', _outline(outline),
                       based.get(_q('val')) if based is not None else None)
    return result


def _outline(element):
    """outlineLvl 0..8 is a heading level; 9 means body text."""
    try:
        value = int(element.get(_q('val'))) if element is not None else None
    except (TypeError, ValueError):
        return None
    return value if value is not None and 0 <= value <= 8 else None


def _chain(styles, style_id):
    seen = set()
    while style_id and style_id in styles and style_id not in seen:
        seen.add(style_id)
        yield styles[style_id]
        style_id = styles[style_id][2]


def _heading_level(styles, style_id, direct):
    if direct is not None:
        return direct
    chain = list(_chain(styles, style_id))
    for _, outline, _ in chain:
        if outline is not None:
            return outline
    for name, _, _ in chain:
        match = _HEADING_NAME.fullmatch(name.strip())
        if match:
            return int(match.group(1)) - 1
    if not chain and style_id:  # no styles part or an unknown style: fall back to the conventional style id
        match = _HEADING_NAME.fullmatch(style_id.strip())
        return int(match.group(1)) - 1 if match else None
    return None


def _is_title(styles, style_id):
    chain = list(_chain(styles, style_id))
    if not chain:
        return (style_id or '').strip().lower() == 'title'
    return any(name.strip().lower() == 'title' for name, _, _ in chain)


class _Reader:
    def __init__(self, styles=None):
        self.styles = styles or {}
        self.titles = []
        self.paragraphs = []
        self.lengths = []
        self.starts = {}
        self.ends = {}
        self.warnings = []

    def warn(self, index, text):
        message = DocxWarning(index, text)
        if message not in self.warnings:
            self.warnings.append(message)

    def body(self, parent):
        for child in parent:
            if child.tag == _q('p'):
                self.paragraph(child)
            elif child.tag == _q('tbl'):
                self.warn(len(self.paragraphs) - 1 if self.paragraphs else None, 'таблицю пропущено разом з текстом у ній')
            elif child.tag == _q('commentRangeStart'):
                self.starts.setdefault(child.get(_q('id')), (len(self.paragraphs), 0))
            elif child.tag == _q('commentRangeEnd'):
                last = len(self.paragraphs) - 1
                self.ends.setdefault(child.get(_q('id')), (last, self.lengths[last]) if last >= 0 else None)
            elif child.tag in (_q('ins'), _q('del'), _q('moveTo'), _q('moveFrom')) or child.tag.rsplit('}', 1)[-1] in _TRANSPARENT:
                self.body(child)

    def paragraph(self, element):
        index = len(self.paragraphs)
        style = element.find(f'{_q("pPr")}/{_q("pStyle")}')
        state = {'editor': [], 'original': [], 'length': 0, 'changed': False, 'bookmarks': []}
        self.walk(element, index, state, 'both')
        for tags, text in ((('drawing', 'pict'), 'малюнок або фігуру не імпортовано'), (('object',), 'вбудований об’єкт не імпортовано'),
                           (('footnoteReference', 'endnoteReference'), 'виноску не імпортовано'),
                           (('rPrChange', 'pPrChange'), 'зміну форматування проігноровано (імпортується лише текст)')):
            if any(next(element.iter(_q(tag)), None) is not None for tag in tags):
                self.warn(index, text)
        style_id = style.get(_q('val')) if style is not None else None
        direct = _outline(element.find(f'{_q("pPr")}/{_q("outlineLvl")}'))
        if _is_title(self.styles, style_id):
            self.titles.append(index)
        mark = element.find(f'{_q("pPr")}/{_q("rPr")}')
        # A tracked move is an insertion at its destination (moveTo) and a deletion at its source (moveFrom).
        inserted = mark is not None and any(mark.find(_q(tag)) is not None for tag in ('ins', 'moveTo'))
        deleted = mark is not None and any(mark.find(_q(tag)) is not None for tag in ('del', 'moveFrom'))
        self.paragraphs.append(DocxParagraph(style.get(_q('val')) if style is not None else None, tuple(state['bookmarks']),
            _merge(state['editor']), _merge(state['original']), state['changed'] or inserted or deleted, inserted, deleted,
            _heading_level(self.styles, style_id, direct)))
        self.lengths.append(state['length'])

    def walk(self, parent, index, state, mode):
        for child in parent:
            tag = child.tag
            if tag == _q('r'):
                self.run(child, state, mode)
            elif tag in (_q('ins'), _q('moveTo')):
                state['changed'] = True
                self.walk(child, index, state, _COMBINE[mode, 'ins'])
            elif tag in (_q('del'), _q('moveFrom')):
                state['changed'] = True
                self.walk(child, index, state, _COMBINE[mode, 'del'])
            elif tag == _q('bookmarkStart'):
                if child.get(_q('name')):
                    state['bookmarks'].append(child.get(_q('name')))
            elif tag == _q('commentRangeStart'):
                self.starts.setdefault(child.get(_q('id')), (index, state['length']))
            elif tag == _q('commentRangeEnd'):
                self.ends.setdefault(child.get(_q('id')), (index, state['length']))
            elif tag.rsplit('}', 1)[-1] in _TRANSPARENT:
                self.walk(child, index, state, mode)

    def run(self, element, state, mode):
        rpr = element.find(_q('rPr'))
        pieces = []
        for child in element:
            if child.tag in (_q('t'), _q('delText')):
                pieces.append(child.text or '')
            elif child.tag == _q('br') and child.get(_q('type')) in (None, 'textWrapping'):
                pieces.append('\n')
            elif child.tag == _q('tab'):
                pieces.append('\t')
        text = ''.join(pieces)
        if not text:
            return
        run = Run(text, _flag(rpr, 'b'), _flag(rpr, 'i'))
        if mode in ('both', 'ins'):
            state['editor'].append(run)
        if mode in ('both', 'del'):
            state['original'].append(run)
            state['length'] += len(text)


def _comments(data, reader):
    if data is None:
        return ()
    result = []
    for comment in _parse(data, 'word/comments.xml').iter(_q('comment')):
        key = comment.get(_q('id'))
        text = '\n'.join(''.join(t.text or '' for t in p.iter(_q('t'))) for p in comment.iter(_q('p')))
        result.append(DocxComment(key or '', comment.get(_q('author')) or '', text, reader.starts.get(key), reader.ends.get(key)))
    return tuple(result)


def _identity(data):
    if data is None:
        return None, None
    values = {prop.get('name'): ''.join(prop.itertext()) for prop in _parse(data, 'docProps/custom.xml') if prop.get('name')}
    return values.get('ObscuraStoryId'), values.get('ObscuraExportId')


def read_docx(content: bytes) -> DocxManuscript:
    """Read an editor's DOCX; raise ValueError with a Ukrainian reason when the file must not be imported."""
    try:
        return _read(content)
    except RecursionError as exc:
        raise ValueError('DOCX: структура документа занадто глибоко вкладена') from exc


def _read(content):
    parts = _read_parts(content)
    if '[Content_Types].xml' in parts:
        _parse(parts['[Content_Types].xml'], '[Content_Types].xml')
    body = _parse(parts['word/document.xml'], 'word/document.xml').find(_q('body'))
    if body is None:
        raise ValueError('DOCX: у word/document.xml немає тіла документа')
    reader = _Reader(_styles(parts.get('word/styles.xml')))
    reader.body(body)
    story_id, export_id = _identity(parts.get('docProps/custom.xml'))
    return DocxManuscript(story_id, export_id, tuple(reader.paragraphs), _comments(parts.get('word/comments.xml'), reader),
        tuple(reader.warnings), tuple(reader.titles))
