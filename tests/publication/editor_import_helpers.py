"""DOCX edit helpers shared by the editor-import tests and the browser fixture server (no pytest imports)."""
import io
import zipfile

T = '<w:t xml:space="preserve">'


def run(text):
    return f'<w:r>{T}{text}</w:t></w:r>'


def tracked(old, new):
    return (f'<w:del w:id="90" w:author="Р"><w:r><w:delText xml:space="preserve">{old}</w:delText></w:r></w:del>'
            f'<w:ins w:id="91" w:author="Р">{run(new)}</w:ins>')


def ranged(cid, inner):
    return f'<w:commentRangeStart w:id="{cid}"/>{inner}<w:commentRangeEnd w:id="{cid}"/>'


def split(xml, phrase, middle):
    """Put run-level XML in place of a phrase that sits inside one plain run."""
    assert xml.count(phrase) == 1
    return xml.replace(phrase, f'</w:t></w:r>{middle}<w:r>{T}')


def edit(content, change=lambda xml: xml, comments=(), custom=None):
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(content)) as source, zipfile.ZipFile(output, 'w') as target:
        for name in source.namelist():
            data = source.read(name)
            if name == 'word/document.xml':
                data = change(data.decode('utf-8')).encode('utf-8')
            elif name == 'docProps/custom.xml' and custom:
                data = custom(data.decode('utf-8')).encode('utf-8')
            target.writestr(name, data)
        if comments:
            body = ''.join(f'<w:comment w:id="{cid}" w:author="{author}"><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:comment>'
                           for cid, author, text in comments)
            target.writestr('word/comments.xml',
                '<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">' + body + '</w:comments>')
    return output.getvalue()
