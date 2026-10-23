"""Capture one publication and resolve immutable blobs; renderers receive data only."""
from dataclasses import dataclass
from uuid import UUID,uuid5
from ..domain import new_id,now
from ..publication_models import PublicationSnapshot
import re

EDITION_NAMESPACE=UUID('f194517a-40c4-52c1-8d82-74d6c82bb54b')
EXPORTER={'name':'Obscura Text Writer','version':'0.1.0','protocol':2}
INCOMPLETE='НЕЗАВЕРШЕНО — див. попередження у сценах і manifest'


@dataclass(frozen=True)
class Chapter:
    title: str
    text: str
    entry: dict


@dataclass(frozen=True)
class Book:
    snapshot: PublicationSnapshot
    chapters: tuple[Chapter,...]
    warnings: tuple[str,...]
    cover: bytes | None
    export_id: str
    edition_id: str
    created_at: str

    @property
    def title(self):return self.snapshot.publication.effective_title


def capture(repo,story_id,format,allow_incomplete):
    snapshot=repo.publication_snapshot(story_id)
    publication=snapshot.publication
    if format=='fb2':
        if not publication.authors:raise ValueError('FB2: оберіть автора в картці публікації')
        if not publication.card.genres:raise ValueError('FB2: оберіть жанр у картці публікації')
    chapters=[];warnings=[]
    if not snapshot.scenes:warnings.append('Немає сцен')
    for scene,ref in snapshot.scenes:
        entry={'scene_id':scene.id,'title':scene.title,'position':scene.position,'version_id':ref.id if ref else None,'warnings':[]}
        text=''
        if ref:
            if ref.stale or not ref.complete or scene.needs_review:entry['warnings'].append('Сцена застаріла або потребує перегляду')
            text=repo.files.read(ref.relative_path,ref.sha256).decode('utf-8');entry['sha256']=ref.sha256
        else:entry['warnings'].append('Немає завершеної вибраної прози')
        entry['word_count']=len(re.findall(r"\b[\w’'-]+\b",text))
        warnings.extend(entry['warnings']);chapters.append(Chapter(scene.title,text,entry))
    if warnings and not allow_incomplete:raise ValueError('Експорт зупинено: є відсутні або застарілі сцени. Явно дозвольте неповний експорт.')
    cover=None
    if publication.cover:
        asset=publication.cover
        cover=repo.files.read(asset.relative_path,asset.sha256)
        if format in {'fb2','epub','pdf'}:
            from .covers import image_info
            if image_info(cover)!=(asset.mime_type,asset.width,asset.height):raise ValueError('Обкладинка не відповідає збереженим метаданим')
    return Book(snapshot,tuple(chapters),tuple(warnings),cover,new_id(),str(uuid5(EDITION_NAMESPACE,story_id)),now())


def lines(text):return text.replace('\r\n','\n').replace('\r','\n').split('\n')


def chapter_lines(chapter):
    if chapter.entry['warnings']:yield '[НЕЗАВЕРШЕНО: '+'; '.join(chapter.entry['warnings'])+']'
    yield from lines(chapter.text)


def xml_bytes(root):
    from xml.etree import ElementTree as ET
    for element in root.iter():
        for text in [element.text,element.tail,*element.attrib.values()]:
            if text and any(not (c in '\t\n\r' or 0x20<=ord(c)<=0xd7ff or 0xe000<=ord(c)<=0xfffd or 0x10000<=ord(c)<=0x10ffff) for c in text):
                raise ValueError('Текст містить недопустимий символ XML 1.0; його не вилучено автоматично')
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)
