"""Offline A5 book layout. All author text is escaped before Platypus parsing."""
import hashlib
import io
import json
import threading
from importlib.resources import files
from xml.sax.saxutils import escape
from .book import INCOMPLETE,chapter_lines

_FONT_LOCK=threading.Lock()
PROFILE={'name':'A5','width_mm':148,'height_mm':210,'margin_mm':17,'bottom_mm':18,'font_size':11,'leading':15}


def format_details():
    try:import reportlab
    except ImportError:raise ValueError('Для PDF потрібен ReportLab: встановіть додаткові залежності publication') from None
    manifest=json.loads(files('storygen.publication').joinpath('resources/fonts/manifest.json').read_text(encoding='utf-8'))
    return {'library':'ReportLab '+reportlab.Version,'profile':PROFILE,'fonts':manifest}


def render(book):
    details=format_details()
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import BaseDocTemplate,Frame,PageTemplate,Paragraph,Spacer,PageBreak,NextPageTemplate,Image
    from reportlab.platypus.tableofcontents import TableOfContents
    resources=files('storygen.publication').joinpath('resources/fonts')
    blobs={name:resources.joinpath(name).read_bytes() for name in details['fonts']['files']}
    if any(hashlib.sha256(data).hexdigest()!=details['fonts']['files'][name] for name,data in blobs.items()):
        raise ValueError('Пошкоджено комплектні шрифти PDF або їхню ліцензію')
    with _FONT_LOCK:
        for style in ['Regular','Italic','Bold','BoldItalic']:
            name='ObscuraNotoSerif-'+style
            if name not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont(name,io.BytesIO(blobs['NotoSerif-'+style+'.ttf'])))
        pdfmetrics.registerFontFamily('ObscuraNotoSerif-Regular',normal='ObscuraNotoSerif-Regular',bold='ObscuraNotoSerif-Bold',italic='ObscuraNotoSerif-Italic',boldItalic='ObscuraNotoSerif-BoldItalic')
    regular='ObscuraNotoSerif-Regular';bold='ObscuraNotoSerif-Bold'
    publication=book.snapshot.publication;card=publication.card
    visible=[book.title,card.cycle_title,card.publisher,card.publication_date,INCOMPLETE,'Зміст',
        *[p.display_name for p in publication.authors],*[c.title+'\n'+c.text for c in book.chapters]]
    for font in [regular,bold]:
        glyphs=pdfmetrics.getFont(font).face.charToGlyph
        missing=next((c for text in visible for c in text if c not in '\n\r\t' and not glyphs.get(ord(c))),None)
        if missing is not None:raise ValueError(f'PDF: Noto Serif не підтримує символ U+{ord(missing):04X}; текст не замінено')
    body=ParagraphStyle('Body',fontName=regular,fontSize=11,leading=15,firstLineIndent=4*mm,
        spaceAfter=3,allowWidows=0,allowOrphans=0,splitLongWords=1)
    heading=ParagraphStyle('Chapter',parent=body,fontName=bold,fontSize=17,leading=22,firstLineIndent=0,spaceAfter=16,keepWithNext=True)
    title_style=ParagraphStyle('Title',parent=heading,fontSize=24,leading=31,spaceAfter=20,keepWithNext=False)
    front=ParagraphStyle('Front',parent=body,firstLineIndent=0,spaceAfter=10)
    toc_style=ParagraphStyle('TOC',parent=front,fontSize=11,leading=15,rightIndent=20,spaceBefore=8)
    width,height=148*mm,210*mm;available_width=width-34*mm;available_height=height-35*mm
    output=io.BytesIO()
    class BookDoc(BaseDocTemplate):
        def afterFlowable(self,flowable):
            if hasattr(flowable,'chapter_key'):
                key=flowable.chapter_key;self.canv.bookmarkPage(key)
                self.notify('TOCEntry',(0,escape(flowable.getPlainText()),self.page,key))
                self.canv.addOutlineEntry(flowable.getPlainText(),key,0,False)
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont(regular,9);canvas.drawCentredString(width/2,9*mm,str(doc.page));canvas.restoreState()
    def frame():return Frame(17*mm,18*mm,available_width,available_height,leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
    doc=BookDoc(output,pagesize=(width,height),leftMargin=17*mm,rightMargin=17*mm,topMargin=17*mm,bottomMargin=18*mm,
        title=book.title,author=', '.join(p.display_name for p in publication.authors),pageCompression=1)
    doc.addPageTemplates([PageTemplate('Front',frames=[frame()]),PageTemplate('Body',frames=[frame()],onPage=footer)])
    flow=[]
    if book.cover:
        asset=publication.cover;scale=min(available_width/asset.width,(available_height-1)/asset.height)
        image=Image(io.BytesIO(book.cover),width=asset.width*scale,height=asset.height*scale);image.hAlign='CENTER'
        flow.extend([image,PageBreak()])
    flow.append(Paragraph(escape(book.title),title_style))
    for person in publication.authors:flow.append(Paragraph(escape(person.display_name),front))
    if card.cycle_title:
        cycle=card.cycle_title+(f' · {card.cycle_number}' if card.cycle_number is not None else '')
        flow.append(Paragraph(escape(cycle),front))
    for text in [card.publisher,card.publication_date]:
        if text:flow.append(Paragraph(escape(text),front))
    if book.warnings:flow.append(Paragraph(escape(INCOMPLETE),front))
    flow.extend([NextPageTemplate('Body'),PageBreak(),Paragraph('Зміст',heading)])
    if book.chapters:
        toc=TableOfContents();toc.levelStyles=[toc_style];flow.append(toc)
    else:flow.append(Paragraph('Немає сцен',front))
    for index,chapter in enumerate(book.chapters,1):
        flow.append(PageBreak());h=Paragraph(escape(chapter.title),heading);h.chapter_key=f'chapter-{index}';flow.append(h)
        paragraph_lines=list(chapter_lines(chapter))
        while paragraph_lines and not paragraph_lines[-1]:paragraph_lines.pop()
        for line in paragraph_lines:flow.append(Paragraph(escape(line),body) if line else Spacer(1,7.5))
    if not book.chapters:flow.extend([PageBreak(),Paragraph(escape(INCOMPLETE),front)])
    try:doc.multiBuild(flow,maxPasses=10)
    except Exception as exc:
        from reportlab.platypus.doctemplate import LayoutError
        if isinstance(exc,(LayoutError,IndexError)):raise ValueError('PDF: не вдалося розмістити текст або узгодити зміст; файл не опубліковано') from exc
        raise
    return output.getvalue()
