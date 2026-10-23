"""Local EPUB 3 package; ordinary author text is never interpreted as markup."""
import io
import posixpath
import zipfile
from datetime import datetime
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET
from .book import INCOMPLETE,chapter_lines,xml_bytes

XHTML='http://www.w3.org/1999/xhtml'
OPF='http://www.idpf.org/2007/opf'
EPUB='http://www.idpf.org/2007/ops'
OCF='urn:oasis:names:tc:opendocument:xmlns:container'
DC='http://purl.org/dc/elements/1.1/'
VOCAB='https://github.com/ysilvestrov/obscura-text-writer/metadata#'
CSS=b'body { font-family: serif; } p { white-space: pre-wrap; } img { max-width: 100%; height: auto; }'


def add(parent,tag,text=None,**attrs):
    element=ET.SubElement(parent,tag,attrs);element.text=text;return element


def page(title,language):
    root=ET.Element('html',{'xmlns':XHTML,'xmlns:epub':EPUB,'lang':language,'xml:lang':language})
    head=add(root,'head');add(head,'title',title)
    add(head,'link',rel='stylesheet',type='text/css',href='style.css')
    return root,add(root,'body')


def render(book):
    card=book.snapshot.publication.card
    root=ET.Element('package',{'xmlns':OPF,'xmlns:dc':DC,'version':'3.0','unique-identifier':'edition','prefix':'obscura: '+VOCAB})
    metadata=add(root,'metadata')
    add(metadata,'dc:identifier','urn:uuid:'+book.edition_id,id='edition')
    add(metadata,'dc:title',book.title);add(metadata,'dc:language',card.language)
    modified=datetime.fromisoformat(book.created_at).strftime('%Y-%m-%dT%H:%M:%SZ')
    add(metadata,'meta',modified,property='dcterms:modified')
    for role,tag,people in [('aut','creator',book.snapshot.publication.authors),('trl','contributor',book.snapshot.publication.translators)]:
        for index,person in enumerate(people,1):
            id=f'{tag}-{index}';add(metadata,'dc:'+tag,person.display_name,id=id)
            add(metadata,'meta',role,refines='#'+id,property='role',scheme='marc:relators')
    for field,tag in [('annotation','description'),('rights','rights'),('publisher','publisher'),('publication_date','date')]:
        if getattr(card,field):add(metadata,'dc:'+tag,getattr(card,field))
    if card.isbn:add(metadata,'dc:identifier','urn:isbn:'+card.isbn)
    if card.source_language:add(metadata,'meta',card.source_language,property='obscura:source-language')
    for kind,values in [('fb2-genre',card.genres),('keyword',card.keywords)]:
        for index,value in enumerate(values,1):
            id=f'{kind}-{index}';add(metadata,'dc:subject',value,id=id)
            add(metadata,'meta',kind,refines='#'+id,property='obscura:subject-kind')
    if card.cycle_title:
        add(metadata,'meta',card.cycle_title,id='series',property='belongs-to-collection')
        add(metadata,'meta','series',refines='#series',property='collection-type')
        if card.cycle_number is not None:add(metadata,'meta',str(card.cycle_number),refines='#series',property='group-position')
    if book.warnings:add(metadata,'meta',INCOMPLETE,property='obscura:export-status')
    manifest=add(root,'manifest');spine=add(root,'spine')
    resources={}
    def resource(id,name,mime,data,properties=None,reading=False):
        attrs={'id':id,'href':name,'media-type':mime}
        if properties:attrs['properties']=properties
        add(manifest,'item',**attrs);resources['EPUB/'+name]=data
        if reading:add(spine,'itemref',idref=id)
    resource('css','style.css','text/css',CSS)
    if book.cover:
        asset=book.snapshot.publication.cover;name='cover.'+('png' if asset.mime_type=='image/png' else 'jpg')
        resource('cover-image',name,asset.mime_type,book.cover,'cover-image')
        cover,body=page('Обкладинка',card.language);add(body,'img',src=name,alt='Обкладинка: '+book.title)
        resource('cover-page','cover.xhtml','application/xhtml+xml',xml_bytes(cover),reading=True)
    nav,nav_body=page('Зміст — '+book.title,card.language)
    nav_element=add(nav_body,'nav',**{'epub:type':'toc','id':'toc'});add(nav_element,'h1','Зміст');toc=add(nav_element,'ol')
    chapters=book.chapters
    if not chapters:
        blank,body=page(book.title,card.language);add(body,'h1',book.title);add(body,'p',INCOMPLETE)
        resource('incomplete','incomplete.xhtml','application/xhtml+xml',xml_bytes(blank),reading=True)
        add(add(toc,'li'),'a','Незавершений твір',href='incomplete.xhtml')
    for index,chapter in enumerate(chapters,1):
        name=f'chapter-{index}.xhtml';document,body=page(chapter.title,card.language);add(body,'h1',chapter.title)
        if book.warnings and index==1:add(body,'aside',INCOMPLETE)
        for line in chapter_lines(chapter):
            paragraph=add(body,'p',line or None)
            if not line:add(paragraph,'br')
        resource(f'chapter-{index}',name,'application/xhtml+xml',xml_bytes(document),reading=True)
        add(add(toc,'li'),'a',chapter.title,href=name)
    resource('nav','nav.xhtml','application/xhtml+xml',xml_bytes(nav),'nav')
    resources['EPUB/package.opf']=xml_bytes(root)
    container=ET.Element('container',{'xmlns':OCF,'version':'1.0'})
    add(add(container,'rootfiles'),'rootfile',**{'full-path':'EPUB/package.opf','media-type':'application/oebps-package+xml'})
    resources['META-INF/container.xml']=xml_bytes(container)
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        archive.writestr('mimetype',b'application/epub+zip',compress_type=zipfile.ZIP_STORED)
        for name,content in resources.items():archive.writestr(name,content)
    data=output.getvalue();validate(data);return data


def validate(content):
    """Bounded structural checks for generated packages; EPUBCheck is separate dev acceptance."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names=archive.namelist()
            if not names or names[0]!='mimetype' or len(names)!=len(set(names)):raise ValueError()
            if any(n.startswith('/') or '\\' in n or '..' in n.split('/') for n in names):raise ValueError()
            if sum(i.file_size for i in archive.infolist())>64*1024*1024:raise ValueError()
            if archive.getinfo('mimetype').compress_type!=zipfile.ZIP_STORED or archive.read('mimetype')!=b'application/epub+zip':raise ValueError()
            def xml(name):
                data=archive.read(name)
                if b'<!DOCTYPE' in data or b'<!ENTITY' in data:raise ValueError()
                return ET.fromstring(data)
            container=xml('META-INF/container.xml')
            ref=container.find('{'+OCF+'}rootfiles/{'+OCF+'}rootfile')
            if ref is None or ref.get('full-path')!='EPUB/package.opf':raise ValueError()
            package=xml('EPUB/package.opf')
            if package.tag!='{'+OPF+'}package' or package.get('version')!='3.0':raise ValueError()
            metadata=package.find('{'+OPF+'}metadata')
            for tag in ['title','identifier','language']:
                if metadata.find('{'+DC+'}'+tag) is None:raise ValueError()
            if metadata.find("{"+OPF+"}meta[@property='dcterms:modified']") is None:raise ValueError()
            items=package.findall('{'+OPF+'}manifest/{'+OPF+'}item')
            ids={item.get('id'):item for item in items}
            if len(ids)!=len(items) or not any(i.get('properties')=='nav' for i in items):raise ValueError()
            paths={'EPUB/'+i.get('href','') for i in items}
            if set(names)!=paths|{'mimetype','META-INF/container.xml','EPUB/package.opf'}:raise ValueError()
            for ref in package.findall('{'+OPF+'}spine/{'+OPF+'}itemref'):
                if ref.get('idref') not in ids:raise ValueError()
            for item in items:
                if item.get('media-type')!='application/xhtml+xml':continue
                document=xml('EPUB/'+item.get('href'))
                if document.tag!='{'+XHTML+'}html':raise ValueError()
                for element in document.iter():
                    if element.tag.split('}')[-1] in {'script','iframe','object','embed'}:raise ValueError()
                    for attr in ['href','src']:
                        value=element.get(attr)
                        if value:
                            url=urlsplit(value)
                            target=posixpath.normpath(posixpath.join('EPUB',url.path))
                            if url.scheme or url.netloc or target not in paths:raise ValueError()
    except (ValueError,KeyError,ET.ParseError,zipfile.BadZipFile,TypeError,AttributeError) as exc:
        raise ValueError('EPUB не пройшов структурну перевірку; файл не опубліковано') from exc
