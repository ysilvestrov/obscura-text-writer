"""Safe author-text projection. Raw source remains authoritative for evidence."""
from dataclasses import dataclass
from html import unescape
import re

from markdown_it import MarkdownIt


@dataclass(frozen=True)
class InlineRun:
    text: str
    source_start: int
    source_end: int
    bold: bool = False
    italic: bool = False


@dataclass(frozen=True)
class FormatSpan:
    open_start: int
    open_end: int
    close_start: int
    close_end: int


@dataclass(frozen=True)
class Paragraph:
    start: int
    end: int
    runs: tuple[InlineRun, ...]
    opaque: bool = False
    formats: tuple[FormatSpan, ...] = ()
    source_units: tuple[InlineRun, ...] = ()

    @property
    def text(self):return ''.join(run.text for run in self.runs)


@dataclass(frozen=True)
class DocumentProjection:
    source: str
    paragraphs: tuple[Paragraph, ...]

    @property
    def format_spans(self):return tuple(span for paragraph in self.paragraphs for span in paragraph.formats)

    @property
    def text(self):
        parts=[];cursor=0
        for paragraph in self.paragraphs:
            parts.extend((self.source[cursor:paragraph.start],paragraph.text));cursor=paragraph.end
        parts.append(self.source[cursor:])
        return ''.join(parts)


_PUNCTUATION=re.compile(r'[!"#$%&\'()*+,\-./:;<=>?@[\\\]^_`{|}~]')
_ENTITY=re.compile(r'(?:&#[0-9]{1,7};|&#x[0-9a-fA-F]{1,6};|&[A-Za-z][A-Za-z0-9]+;)')
_RAW_HTML=re.compile(r'<(?:/?[A-Za-z][^>]*|!--[\s\S]*?--|[!?][^>]*)>')


def _has_raw_html(source):
    for match in _RAW_HTML.finditer(source):
        before=source[:match.start()]
        slashes=len(before)-len(before.rstrip('\\'))
        if slashes%2==0:return True
    return False


def _unit(source,cursor):
    start=cursor
    if source[cursor]=='\\' and cursor+1<len(source) and _PUNCTUATION.fullmatch(source[cursor+1]):
        return source[cursor+1],cursor+2
    if source[cursor]=='&' and (match:=_ENTITY.match(source,cursor)):
        return unescape(match[0]),match.end()
    if source[cursor]=='\r':return '\n',cursor+(2 if source[cursor:cursor+2]=='\r\n' else 1)
    return source[start],cursor+1


def _inline(source,start,end,tokens):
    # CommonMark strips at most three initial spaces before an ordinary paragraph.
    cursor=start+len(re.match(r' {0,3}',source[start:end])[0]);bold=italic=0;runs=[];stack=[];formats=[]
    for token in tokens:
        if token.type in {'strong_open','strong_close','em_open','em_close'}:
            if not source.startswith(token.markup,cursor):raise ValueError('Unmapped Markdown delimiter')
            if token.nesting==1:stack.append((cursor,cursor+len(token.markup)))
            else:
                opening=stack.pop();formats.append(FormatSpan(*opening,cursor,cursor+len(token.markup)))
            cursor+=len(token.markup)
            amount=1 if token.nesting==1 else -1
            if token.type.startswith('strong'):bold+=amount
            else:italic+=amount
        elif token.type=='text':
            visible=token.content.replace('\r\n','\n').replace('\r','\n');consumed=0
            while consumed<len(visible):
                if cursor>=end:raise ValueError('Unmapped Markdown text')
                value,after=_unit(source,cursor)
                if not visible.startswith(value,consumed):raise ValueError('Unmapped Markdown text')
                runs.append(InlineRun(value,cursor,after,bool(bold),bool(italic)));cursor=after;consumed+=len(value)
        elif token.type in {'softbreak','hardbreak'}:
            pattern=r'(?: {2,}|\\)(?:\r\n|[\r\n])[ \t]*' if token.type=='hardbreak' else r'[ \t]*(?:\r\n|[\r\n])[ \t]*'
            match=re.match(pattern,source[cursor:end])
            if not match:raise ValueError('Unmapped Markdown break')
            after=cursor+len(match[0]);runs.append(InlineRun('\n',cursor,after,bool(bold),bool(italic)));cursor=after
        else:raise ValueError('Unsupported Markdown inline')
    if bold or italic or source[cursor:end].strip():raise ValueError('Unmapped Markdown remainder')
    # Coalesce only adjacent runs whose source boundaries are equally adjacent.
    merged=[]
    for run in runs:
        if merged and (prior:=merged[-1]).source_end==run.source_start and (prior.bold,prior.italic)==(run.bold,run.italic):
            merged[-1]=InlineRun(prior.text+run.text,prior.source_start,run.source_end,run.bold,run.italic)
        else:merged.append(run)
    return tuple(merged),tuple(formats),tuple(runs)


def _source_lines(source):
    # CommonMark recognizes CR/LF, not Python's broader Unicode splitlines set.
    return re.split(r'(?<=\n)|(?<=\r)(?!\n)',source)


def parse_markdown(source):
    # Do not inherit Python markdown-it's permissive HTML default.
    parser=MarkdownIt('commonmark', {'html':False,'linkify':False,'typographer':False})
    tokens=parser.parse(source);offsets=[0]
    for line in _source_lines(source):offsets.append(offsets[-1]+len(line))
    paragraphs=[];index=0
    while index<len(tokens):
        token=tokens[index]
        if token.level!=0 or not token.map:index+=1;continue
        start=offsets[token.map[0]];end=offsets[token.map[1]]
        if source[:end].endswith('\r\n'):end-=2
        elif end>start and source[end-1] in '\n\r':end-=1
        closing=index
        if token.nesting==1:
            closing=index+1
            while closing<len(tokens) and not (tokens[closing].level==0 and tokens[closing].nesting==-1):closing+=1
        opaque=token.type!='paragraph_open'
        runs=None;formats=();source_units=()
        if not opaque:
            inline=tokens[index+1]
            allowed={'text','strong_open','strong_close','em_open','em_close','softbreak','hardbreak'}
            opaque=_has_raw_html(source[start:end]) or any(child.type not in allowed for child in inline.children or [])
            if not opaque:runs,formats,source_units=_inline(source,start,end,inline.children or [])
        if opaque:runs=(InlineRun(source[start:end],start,end),)
        paragraphs.append(Paragraph(start,end,runs,opaque,formats,source_units));index=closing+1
    return DocumentProjection(source,tuple(paragraphs))


def to_plain_text(source,content_format='plain'):
    if content_format=='plain':return source
    if content_format!='markdown':raise ValueError('Невідомий формат авторського тексту')
    return parse_markdown(source).text


def source_range_text(source,start,end,content_format='plain'):
    """Validate a raw source selection using the entire document, never quote search."""
    if not 0<=start<end<=len(source):raise ValueError('Некоректні межі коментаря')
    if content_format=='plain':
        if start and source[start-1:start+1]=='\r\n' or source[end-1:end+1]=='\r\n':
            raise ValueError('Межа коментаря розділяє перенос рядка')
        return source[start:end].replace('\r\n','\n').replace('\r','\n')
    if content_format!='markdown':raise ValueError('Невідомий формат авторського тексту')
    document=parse_markdown(source);chosen=[]
    for paragraph in document.paragraphs:
        if start<paragraph.end and end>paragraph.start and paragraph.opaque:
            raise ValueError('Не можна коментувати непрозорий Markdown-блок')
        units=[unit for unit in paragraph.source_units if start<unit.source_end and end>unit.source_start]
        if not units:continue
        if units[0].source_start<start or units[-1].source_end>end:
            raise ValueError('Межа коментаря розділяє escape або entity')
        chosen.append((paragraph,units))
    if not chosen or chosen[0][1][0].source_start!=start or chosen[-1][1][-1].source_end!=end:
        raise ValueError('Коментар не має точного видимого діапазону')
    result=[];prior=None
    for paragraph,units in chosen:
        if prior is not None:
            gap=source[prior.end:paragraph.start]
            count=len(re.findall(r'\r\n|[\r\n]',gap))
            result.append('\n'*max(2,count//2*2))
        result.append(''.join(unit.text for unit in units));prior=paragraph
    return ''.join(result)


def escape_plain_markdown(source):
    """Markdown export of legacy plain must preserve visible punctuation/indent."""
    result=[]
    for line in _source_lines(source):
        prefix=re.match(r'[ \t]*',line)[0]
        literal=''.join('&#x20;' if char==' ' else '&#x9;' for char in prefix)
        rest=re.sub(r'([\\`*_\[\]<>])',lambda match:'\\'+match[0],line[len(prefix):])
        rest=_ENTITY.sub(lambda match:'\\'+match[0],rest)
        rest=re.sub(r'^([#+\-=])',r'\\\1',rest)
        rest=re.sub(r'^(\d{1,9})([.)])(?=\s)',r'\1\\\2',rest)
        result.append(literal+rest)
    return ''.join(result)


def format_dependency_groups(source,candidate,edits):
    """Couple changes to paired delimiters, including pairs added in the candidate."""
    edits=[dict(index=index,start=edit.start,end=edit.end,replacement=edit.replacement) if not isinstance(edit,dict) else edit
           for index,edit in enumerate(edits)]
    def touched(start,end,left,right):
        return left<=start<=right if start==end else start<right and end>left
    translated=[];shift=0
    for edit in sorted(edits,key=lambda value:(value['start'],value['end'])):
        begin=edit['start']+shift
        translated.append({**edit,'start':begin,'end':begin+len(edit['replacement'])})
        shift+=len(edit['replacement'])-(edit['end']-edit['start'])
    groups=[]
    for text,ranges in [(source,edits),(candidate,translated)]:
        for span in parse_markdown(text).format_spans:
            members={edit['index'] for edit in ranges if touched(edit['start'],edit['end'],span.open_start,span.open_end)
                     or touched(edit['start'],edit['end'],span.close_start,span.close_end)}
            if len(members)>1:groups.append(members)
    return groups
