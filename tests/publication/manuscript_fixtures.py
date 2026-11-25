"""Builders of manuscript files for the R-48 reader tests: DOCX is zipped from XML by code, no binary files in the repo."""
import io
import zipfile

NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
T = '<w:t xml:space="preserve">'


def style(style_id, name=None, outline=None, based_on=None):
    parts = f'<w:name w:val="{name}"/>' if name else ''
    parts += f'<w:basedOn w:val="{based_on}"/>' if based_on else ''
    parts += f'<w:pPr><w:outlineLvl w:val="{outline}"/></w:pPr>' if outline is not None else ''
    return f'<w:style w:type="paragraph" w:styleId="{style_id}">{parts}</w:style>'


def para(text='', style_id=None, italic=False, bold=False, outline=None):
    ppr = ''
    if style_id or outline is not None:
        ppr = '<w:pPr>' + (f'<w:pStyle w:val="{style_id}"/>' if style_id else '') + \
              (f'<w:outlineLvl w:val="{outline}"/>' if outline is not None else '') + '</w:pPr>'
    rpr = ('<w:rPr>' + ('<w:b/>' if bold else '') + ('<w:i/>' if italic else '') + '</w:rPr>') if italic or bold else ''
    run = f'<w:r>{rpr}{T}{text}</w:t></w:r>' if text else ''
    return f'<w:p>{ppr}{run}</w:p>'


def tracked_ins(text):
    return f'<w:ins w:id="1" w:author="Р"><w:r>{T}{text}</w:t></w:r></w:ins>'


def tracked_del(text):
    return f'<w:del w:id="2" w:author="Р"><w:r><w:delText xml:space="preserve">{text}</w:delText></w:r></w:del>'


def docx(body, styles=(), parts=None):
    """`parts` — extra package parts {name: xml}, e.g. word/comments.xml."""
    document = f'<?xml version="1.0" encoding="UTF-8"?><w:document {NS}><w:body>{body}</w:body></w:document>'
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as archive:
        archive.writestr('word/document.xml', document)
        if styles:
            archive.writestr('word/styles.xml', f'<?xml version="1.0" encoding="UTF-8"?><w:styles {NS}>{"".join(styles)}</w:styles>')
        for name, xml in (parts or {}).items():
            archive.writestr(name, xml)
    return out.getvalue()


def comments(*texts):
    items = ''.join(f'<w:comment w:id="{i}" w:author="Р"><w:p><w:r>{T}{text}</w:t></w:r></w:p></w:comment>'
                    for i, text in enumerate(texts))
    return {'word/comments.xml': f'<?xml version="1.0" encoding="UTF-8"?><w:comments {NS}>{items}</w:comments>'}


def markdown(text, bom=False):
    return (('﻿' if bom else '') + text).encode('utf-8')


def txt(text, encoding='utf-8'):
    return text.encode(encoding)
