"""Capture one publication and resolve immutable blobs; renderers receive data only."""
from dataclasses import dataclass
from uuid import UUID,uuid5
from ..domain import new_id,now
from ..publication_models import PublicationSnapshot
from ..rating.levels import age_label
import re

RATING_UNSET_EXPORT='Віковий рейтинг твору не задано; позначку не додано'
EDITION_NAMESPACE=UUID('f194517a-40c4-52c1-8d82-74d6c82bb54b')
EXPORTER={'name':'Obscura Text Writer','version':'0.1.0','protocol':4}


@dataclass(frozen=True)
class Chapter:
    title: str
    text: str
    entry: dict
    content_format: str = 'plain'
    # BOOK-STRUCTURE-S05: index into Book.parts; None for a flat book.
    part_index: int | None = None


@dataclass(frozen=True)
class Book:
    snapshot: PublicationSnapshot
    chapters: tuple[Chapter,...]
    warnings: tuple[str,...]
    cover: bytes | None
    export_id: str
    edition_id: str
    created_at: str
    age_rating: str | None = None
    # Effective part titles of a structured book (an untitled part is «Частина N» / «Part N»); () for a flat book.
    parts: tuple[str,...] = ()

    @property
    def title(self):return self.snapshot.publication.effective_title


def series_cycle(repo,snapshot):
    """SERIES-S06: an empty cycle of the card takes the series title, and an empty cycle number the book's number."""
    story=snapshot.story;card=snapshot.publication.card
    if not story.series_id or card.cycle_title:return snapshot
    from ..storage.series import get_series
    try:title=get_series(repo,story.series_id).title
    except KeyError:return snapshot
    card=card.model_copy(update={'cycle_title':title,'cycle_number':card.cycle_number if card.cycle_number is not None else story.series_number})
    return snapshot.model_copy(update={'publication':snapshot.publication.model_copy(update={'card':card})})


def capture(repo,story_id,format,allow_incomplete):
    snapshot=series_cycle(repo,repo.publication_snapshot(story_id))
    publication=snapshot.publication
    if format=='fb2':
        if not publication.authors:raise ValueError('FB2: оберіть автора в картці публікації')
        if not publication.card.genres:raise ValueError('FB2: оберіть жанр у картці публікації')
    chapters=[];warnings=[]
    if not snapshot.scenes:warnings.append('Немає сцен')
    for scene,ref in snapshot.scenes:
        content_format=ref.content_format if ref else 'plain'
        entry={'scene_id':scene.id,'title':scene.title,'position':scene.position,'version_id':ref.id if ref else None,'content_format':content_format,'warnings':[]}
        text=''
        if ref:
            if ref.stale or not ref.complete or scene.needs_review:entry['warnings'].append('Сцена застаріла або потребує перегляду')
            text=repo.files.read(ref.relative_path,ref.sha256).decode('utf-8');entry['sha256']=ref.sha256
        else:entry['warnings'].append('Немає завершеної вибраної прози')
        from ..markdown_document import to_plain_text
        entry['word_count']=len(re.findall(r"\b[\w’'-]+\b",to_plain_text(text,content_format)))
        warnings.extend(entry['warnings']);chapters.append(Chapter(scene.title,text,entry,content_format))
    if warnings and not allow_incomplete:raise ValueError('Експорт зупинено: є відсутні або застарілі сцени. Явно дозвольте неповний експорт.')
    cover=None
    if publication.cover:
        asset=publication.cover
        cover=repo.files.read(asset.relative_path,asset.sha256)
        if format in {'fb2','epub','pdf'}:
            from .covers import image_info
            if image_info(cover)!=(asset.mime_type,asset.width,asset.height):raise ValueError('Обкладинка не відповідає збереженим метаданим')
    parts,chapters=book_parts(snapshot.story,[scene for scene,_ in snapshot.scenes],chapters)
    return Book(snapshot,tuple(chapters),tuple(warnings),cover,new_id(),str(uuid5(EDITION_NAMESPACE,story_id)),now(),
        age_label(snapshot.story,[scene for scene,_ in snapshot.scenes]),parts)


def book_parts(story,scenes,chapters):
    """Part titles and chapters bound to parts; a flat book keeps its chapters exactly as they were."""
    from dataclasses import replace
    from ..book.structure import effective_structure
    structure=effective_structure(story,scenes)
    if structure.kind=='flat':return (),chapters
    word='Part' if story.language=='en' else 'Частина'
    titles=tuple(part.title or f'{word} {number}' for number,part in enumerate(structure.parts,1))
    index={part.id:number for number,part in enumerate(structure.parts)}
    bound=[replace(chapter,part_index=index.get(structure.part_of_arc.get(structure.arc_of.get(chapter.entry['scene_id'])))) for chapter in chapters]
    return titles,bound


def part_starts(book):
    """Chapter index -> part title for the first chapter of each part (empty for a flat book)."""
    starts={};previous=None
    for number,chapter in enumerate(book.chapters):
        if chapter.part_index is not None and chapter.part_index!=previous:starts[number]=book.parts[chapter.part_index]
        previous=chapter.part_index
    return starts


def lines(text):return text.replace('\r\n','\n').replace('\r','\n').split('\n')


def chapter_lines(chapter):
    yield from lines(chapter.text)


def xml_bytes(root):
    from xml.etree import ElementTree as ET
    for element in root.iter():
        for text in [element.text,element.tail,*element.attrib.values()]:
            if text and any(not (c in '\t\n\r' or 0x20<=ord(c)<=0xd7ff or 0xe000<=ord(c)<=0xfffd or 0x10000<=ord(c)<=0x10ffff) for c in text):
                raise ValueError('Текст містить недопустимий символ XML 1.0; його не вилучено автоматично')
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)
