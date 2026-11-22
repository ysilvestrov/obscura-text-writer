"""EXPORT-DOCX: a Word manuscript for an outside editor, built by hand as OOXML without new dependencies.

Each scene heading carries a hidden bookmark `_os<scene id>` and docProps/custom.xml names the story and
the export: the R-46 import finds scenes by them. All author text is XML-escaped.
"""
import io
import zipfile
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from .book import part_starts
from .markup import chapter_paragraphs

PROFILE={'paper':'A4','width_twips':11906,'height_twips':16838,'margin_twips':1417,'font':'Times New Roman',
    'font_half_points':24,'line_240ths':360,'first_line_twips':709}
BOOKMARK_PREFIX='_os'
INVALID_XML='Текст містить недопустимий символ XML 1.0; його не вилучено автоматично'
SCENE_LANG={'uk':'uk-UA','en':'en-US'}
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PACKAGE_RELS='http://schemas.openxmlformats.org/package/2006/relationships'
CUSTOM_FMTID='{D5CDD505-2E9C-101B-9397-08002B2CF9AE}'
HEAD='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
REQUIRED=('[Content_Types].xml','_rels/.rels','word/document.xml','word/_rels/document.xml.rels','word/styles.xml',
    'word/footer1.xml','docProps/core.xml','docProps/custom.xml')


def valid_text(text):
    """The same rule as book.xml_bytes: a character XML 1.0 cannot carry stops the export, nothing is dropped."""
    if any(not (c in '\t\n\r' or 0x20<=ord(c)<=0xd7ff or 0xe000<=ord(c)<=0xfffd or 0x10000<=ord(c)<=0x10ffff) for c in text):
        raise ValueError(INVALID_XML)
    return text


def primary(tag):return tag.split('-')[0].lower()


def word_language(tag):
    """A bare uk/en card tag gets its region: Word reads a bare tag as a neutral language and may skip proofing."""
    return SCENE_LANG.get(tag.lower(),tag) if '-' not in tag else tag


def _run(text,*,bold=False,italic=False,lang=None):
    properties=('<w:b/>' if bold else '')+('<w:i/>' if italic else '')+(f'<w:lang w:val="{lang}"/>' if lang else '')
    pieces=[]
    for index,line in enumerate(valid_text(text).replace('\r\n','\n').replace('\r','\n').split('\n')):
        if index:pieces.append('<w:br/>')
        for number,chunk in enumerate(line.split('\t')):
            if number:pieces.append('<w:tab/>')
            if chunk:pieces.append(f'<w:t xml:space="preserve">{escape(chunk)}</w:t>')
    return f'<w:r>{"<w:rPr>"+properties+"</w:rPr>" if properties else ""}{"".join(pieces)}</w:r>' if pieces else ''


def _paragraph(content='',*,style=None,centered=False,bookmark=None):
    properties=(f'<w:pStyle w:val="{style}"/>' if style else '')+('<w:jc w:val="center"/><w:ind w:firstLine="0"/>' if centered else '')
    start=f'<w:bookmarkStart w:id="{bookmark[0]}" w:name="{bookmark[1]}"/>' if bookmark else ''
    end=f'<w:bookmarkEnd w:id="{bookmark[0]}"/>' if bookmark else ''
    return f'<w:p>{"<w:pPr>"+properties+"</w:pPr>" if properties else ""}{start}{content}{end}</w:p>'


def _body(book):
    publication=book.snapshot.publication;card=publication.card;story=book.snapshot.story
    document_language=primary(card.language)
    english=story.language=='en'
    words=sum(chapter.entry['word_count'] for chapter in book.chapters)
    out=[_paragraph(_run(book.title),style='Title')]
    for person in publication.authors:out.append(_paragraph(_run(person.display_name),centered=True))
    if card.cycle_title:
        out.append(_paragraph(_run(card.cycle_title+(f' · {card.cycle_number}' if card.cycle_number is not None else '')),centered=True))
    out.append(_paragraph(_run(f'{"Words" if english else "Слів"}: {words}'),centered=True))
    starts=part_starts(book)
    for index,chapter in enumerate(book.chapters):
        if index in starts:out.append(_paragraph(_run(starts[index]),style='Heading1'))
        out.append(_paragraph(_run(chapter.title),style='Heading2',bookmark=(index+1,BOOKMARK_PREFIX+chapter.entry['scene_id'])))
        # A scene in another language than the card gets its own proofing language.
        lang=SCENE_LANG.get(chapter.language) if chapter.language!=document_language else None
        paragraphs=list(chapter_paragraphs(chapter))
        while paragraphs and not paragraphs[-1]:paragraphs.pop()
        for runs in paragraphs:
            out.append(_paragraph(''.join(_run(run.text,bold=run.bold,italic=run.italic,lang=lang) for run in runs)))
    return ''.join(out)


def _document(book):
    p=PROFILE
    section=(f'<w:sectPr><w:footerReference w:type="default" r:id="rIdFooter"/><w:pgSz w:w="{p["width_twips"]}" w:h="{p["height_twips"]}"/>'
        f'<w:pgMar w:top="{p["margin_twips"]}" w:right="{p["margin_twips"]}" w:bottom="{p["margin_twips"]}" w:left="{p["margin_twips"]}" '
        'w:header="709" w:footer="709" w:gutter="0"/></w:sectPr>')
    return f'{HEAD}<w:document xmlns:w="{W}" xmlns:r="{R}"><w:body>{_body(book)}{section}</w:body></w:document>'


def _styles(book):
    p=PROFILE;font=p['font'];lang=escape(word_language(book.snapshot.publication.card.language),{'"':'&quot;'})
    heading=lambda id,name,level,size:(f'<w:style w:type="paragraph" w:styleId="{id}"><w:name w:val="{name}"/><w:basedOn w:val="Normal"/>'
        f'<w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:pageBreakBefore/><w:spacing w:after="240"/><w:ind w:firstLine="0"/>'
        f'<w:outlineLvl w:val="{level}"/></w:pPr><w:rPr><w:b/><w:sz w:val="{size}"/></w:rPr></w:style>')
    return (f'{HEAD}<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr>'
        f'<w:rFonts w:ascii="{font}" w:hAnsi="{font}" w:cs="{font}" w:eastAsia="{font}"/><w:sz w:val="{p["font_half_points"]}"/>'
        f'<w:szCs w:val="{p["font_half_points"]}"/><w:lang w:val="{lang}"/></w:rPr></w:rPrDefault>'
        f'<w:pPrDefault><w:pPr><w:spacing w:after="0" w:line="{p["line_240ths"]}" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
        f'<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/>'
        f'<w:pPr><w:ind w:firstLine="{p["first_line_twips"]}"/></w:pPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>'
        '<w:pPr><w:jc w:val="center"/><w:spacing w:before="2400" w:after="480"/><w:ind w:firstLine="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="36"/></w:rPr></w:style>'
        +heading('Heading1','heading 1',0,32)+heading('Heading2','heading 2',1,28)+'</w:styles>')


def _footer():
    return (f'{HEAD}<w:ftr xmlns:w="{W}"><w:p><w:pPr><w:jc w:val="center"/><w:ind w:firstLine="0"/></w:pPr>'
        '<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
        '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p></w:ftr>')


def _core(book):
    publication=book.snapshot.publication
    creator='; '.join(person.display_name for person in publication.authors)
    return (f'{HEAD}<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f'<dc:title>{escape(valid_text(book.title))}</dc:title><dc:creator>{escape(valid_text(creator))}</dc:creator>'
        f'<dc:language>{escape(publication.card.language)}</dc:language></cp:coreProperties>')


def _custom(book):
    values=[('ObscuraStoryId',book.snapshot.story.id),('ObscuraExportId',book.export_id),('ObscuraManuscript','1')]
    properties=''.join(f'<property fmtid="{CUSTOM_FMTID}" pid="{pid}" name="{name}"><vt:lpwstr>{escape(value)}</vt:lpwstr></property>'
        for pid,(name,value) in enumerate(values,2))
    return (f'{HEAD}<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties" '
        f'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">{properties}</Properties>')


CONTENT_TYPES=(f'{HEAD}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
    '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
    '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
    '<Override PartName="/docProps/custom.xml" ContentType="application/vnd.openxmlformats-officedocument.custom-properties+xml"/></Types>')
ROOT_RELS=(f'{HEAD}<Relationships xmlns="{PACKAGE_RELS}">'
    f'<Relationship Id="rId1" Type="{R}/officeDocument" Target="word/document.xml"/>'
    '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
    f'<Relationship Id="rId3" Type="{R}/custom-properties" Target="docProps/custom.xml"/></Relationships>')
DOCUMENT_RELS=(f'{HEAD}<Relationships xmlns="{PACKAGE_RELS}">'
    f'<Relationship Id="rIdStyles" Type="{R}/styles" Target="styles.xml"/>'
    f'<Relationship Id="rIdFooter" Type="{R}/footer" Target="footer1.xml"/></Relationships>')


def render(book):
    parts=[('[Content_Types].xml',CONTENT_TYPES),('_rels/.rels',ROOT_RELS),('word/document.xml',_document(book)),
        ('word/_rels/document.xml.rels',DOCUMENT_RELS),('word/styles.xml',_styles(book)),('word/footer1.xml',_footer()),
        ('docProps/core.xml',_core(book)),('docProps/custom.xml',_custom(book))]
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,text in parts:archive.writestr(name,text.encode('utf-8'))
    content=output.getvalue()
    validate(content,book)
    return content


def validate(content,book):
    """EXPORT-DOCX-S02: the package reads back, and its scene bookmarks and identities are those of this captured book."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names=set(archive.namelist())
            if any(name not in names for name in REQUIRED):raise ValueError('missing part')
            xml={name:archive.read(name) for name in REQUIRED}
        for data in xml.values():ET.fromstring(data)
        document=ET.fromstring(xml['word/document.xml'])
        found=[e.get(f'{{{W}}}name') for e in document.iter(f'{{{W}}}bookmarkStart') if (e.get(f'{{{W}}}name') or '').startswith(BOOKMARK_PREFIX)]
        if found!=[BOOKMARK_PREFIX+chapter.entry['scene_id'] for chapter in book.chapters]:raise ValueError('scene bookmarks')
        custom=ET.fromstring(xml['docProps/custom.xml'])
        values={e.get('name'):''.join(e.itertext()) for e in custom}
        if values.get('ObscuraStoryId')!=book.snapshot.story.id or values.get('ObscuraExportId')!=book.export_id:raise ValueError('identity')
    except (ValueError,KeyError,ET.ParseError,zipfile.BadZipFile) as exc:
        raise ValueError('DOCX: файл не пройшов перевірку структури; не опубліковано') from exc
