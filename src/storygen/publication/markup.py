"""Allowlisted book markup: author text never becomes arbitrary XML/HTML."""
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
import re

from ..markdown_document import InlineRun, parse_markdown
from .book import lines


def _plain(text):return (InlineRun(text,0,len(text)),) if text else ()


def chapter_paragraphs(chapter):
    if chapter.content_format=='plain':
        yield from (_plain(line) for line in lines(chapter.text));return
    projection=parse_markdown(chapter.text);cursor=0
    for index,paragraph in enumerate(projection.paragraphs):
        gap=chapter.text[cursor:paragraph.start]
        breaks=len(re.findall(r'\r\n|[\r\n]',gap))
        for _ in range(max(0,breaks-(1 if index else 0))):yield ()
        yield paragraph.runs;cursor=paragraph.end
    tail=chapter.text[cursor:]
    if tail.strip():yield _plain(tail)
    else:
        for _ in range(max(0,len(re.findall(r'\r\n|[\r\n]',tail))-1)):yield ()


def append_xml_runs(parent,runs,*,bold='strong',italic='em'):
    for run in runs:
        target=parent
        if run.bold:target=ET.SubElement(target,bold)
        if run.italic:target=ET.SubElement(target,italic)
        if target is not parent:target.text=run.text
        elif len(parent):parent[-1].tail=(parent[-1].tail or '')+run.text
        else:parent.text=(parent.text or '')+run.text
    return parent


def reportlab_runs(runs):
    pieces=[]
    for run in runs:
        value=escape(run.text).replace('\r\n','\n').replace('\r','\n').replace('\n','<br/>')
        if run.italic:value='<i>'+value+'</i>'
        if run.bold:value='<b>'+value+'</b>'
        pieces.append(value)
    return ''.join(pieces)
