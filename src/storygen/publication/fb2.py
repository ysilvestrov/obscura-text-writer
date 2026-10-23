"""FictionBook 2 XML, validated against the pinned offline schema."""
import base64
import hashlib
import json
from importlib.resources import files
from urllib.parse import urlparse
from pathlib import PurePosixPath
from xml.etree import ElementTree as ET
from .book import EXPORTER,INCOMPLETE,chapter_lines,lines,xml_bytes

NS='http://www.gribuser.ru/xml/fictionbook/2.0'


def validate(content):
    try:from lxml import etree
    except ImportError:raise ValueError('Для FB2 потрібен lxml: встановіть додаткові залежності publication') from None
    resources=files('storygen.publication').joinpath('resources/fb2')
    hashes=json.loads(resources.joinpath('manifest.json').read_text(encoding='utf-8'))['files']
    blobs={name:resources.joinpath(name).read_bytes() for name in hashes}
    if any(hashlib.sha256(blobs[name]).hexdigest()!=sha for name,sha in hashes.items()):raise ValueError('Пошкоджено комплектну XSD FB2')
    class LocalOnly(etree.Resolver):
        def resolve(self,url,public_id,context):
            name=PurePosixPath(urlparse(url).path).name
            if name not in blobs:raise ValueError('XSD запитує невідомий зовнішній ресурс')
            return self.resolve_string(blobs[name],context,base_url=name)
    parser=etree.XMLParser(resolve_entities=False,load_dtd=False,no_network=True)
    parser.resolvers.add(LocalOnly())
    schema=etree.XMLSchema(etree.fromstring(blobs['FictionBook.xsd'],parser,base_url='FictionBook.xsd'))
    if b'<!DOCTYPE' in content or b'<!ENTITY' in content:raise ValueError('DTD та entities у FB2 заборонені')
    try:schema.assertValid(etree.fromstring(content,parser))
    except (etree.DocumentInvalid,etree.XMLSyntaxError) as exc:
        raise ValueError('FB2 не відповідає комплектній XSD; експорт не опубліковано') from exc


def render(book):
    card=book.snapshot.publication.card
    root=ET.Element('FictionBook',{'xmlns':NS,'xmlns:xlink':'http://www.w3.org/1999/xlink'})
    description=ET.SubElement(root,'description');info=ET.SubElement(description,'title-info')
    def add(parent,tag,text=None,**attrs):
        e=ET.SubElement(parent,tag,attrs);e.text=text;return e
    def person(parent,tag,name):add(add(parent,tag),'nickname',name)
    def paragraphs(parent,text):
        for line in lines(text):add(parent,'p',line) if line else add(parent,'empty-line')
    for genre in card.genres:add(info,'genre',genre)
    for author in book.snapshot.publication.authors:person(info,'author',author.display_name)
    add(info,'book-title',book.title)
    if card.annotation:paragraphs(add(info,'annotation'),card.annotation)
    if card.keywords:add(info,'keywords',', '.join(card.keywords))
    if card.publication_date:add(info,'date',card.publication_date,value=card.publication_date)
    if book.cover:add(add(info,'coverpage'),'image',**{'xlink:href':'#cover'})
    add(info,'lang',card.language)
    if card.source_language:add(info,'src-lang',card.source_language)
    for translator in book.snapshot.publication.translators:person(info,'translator',translator.display_name)
    if card.cycle_title:add(info,'sequence',**{'name':card.cycle_title,**({'number':str(card.cycle_number)} if card.cycle_number is not None else {})})
    document=add(description,'document-info');person(document,'author',EXPORTER['name'])
    add(document,'program-used',EXPORTER['name']+' '+EXPORTER['version'])
    add(document,'date',book.created_at[:10],value=book.created_at[:10]);add(document,'id',book.edition_id);add(document,'version','1.0')
    for field in ['publisher','isbn','rights']:
        if getattr(card,field):add(description,'custom-info',getattr(card,field),**{'info-type':'publication-'+field})
    if book.warnings:add(description,'custom-info',INCOMPLETE,**{'info-type':'export-status'})
    body=add(root,'body')
    if book.warnings:add(add(body,'title'),'p',INCOMPLETE)
    for index,chapter in enumerate(book.chapters,1):
        section=add(body,'section',id=f'chapter-{index}');add(add(section,'title'),'p',chapter.title)
        for line in chapter_lines(chapter):add(section,'p',line) if line else add(section,'empty-line')
    if not book.chapters:add(add(body,'section'),'p',INCOMPLETE)
    if book.cover:add(root,'binary',base64.b64encode(book.cover).decode('ascii'),id='cover',**{'content-type':book.snapshot.publication.cover.mime_type})
    result=xml_bytes(root);validate(result);return result
