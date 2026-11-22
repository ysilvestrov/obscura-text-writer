"""Publication facade: capture once, validate, publish bytes, then commit manifest."""
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Literal
from ..publication.book import capture,EXPORTER,RATING_UNSET_EXPORT
from ..storage.files import StorageCorruption
from ..markdown_document import to_plain_text,escape_plain_markdown

FORMATS={'md','txt','fb2','epub','pdf','docx','rtf'}


def export_story(repo,story_id: str,format: Literal['md','txt','fb2','epub','pdf','docx','rtf'],allow_incomplete: bool = False) -> Path:
    if format not in FORMATS:raise ValueError('Доступні MD, TXT, FB2, EPUB, PDF, DOCX і RTF')
    book=capture(repo,story_id,format,allow_incomplete)
    if format in {'fb2','epub','pdf','docx','rtf'}:
        if format=='fb2':from ..publication.fb2 import render
        elif format=='pdf':from ..publication.pdf import render
        elif format=='docx':from ..publication.docx import render
        elif format=='rtf':from ..publication.rtf import render
        else:from ..publication.epub import render
        content=render(book)
    else:
        parts=[]
        from ..publication.book import part_starts
        starts=part_starts(book);level='###' if book.parts else '##'
        for number,chapter in enumerate(book.chapters):
            if number in starts:
                # BOOK-STRUCTURE-S05: a part heading above its first scene.
                parts.append(('## '+escape_plain_markdown(starts[number])) if format=='md' else starts[number])
            heading=(level+' '+escape_plain_markdown(chapter.title)) if format=='md' else chapter.title
            text=to_plain_text(chapter.text,chapter.content_format) if format=='txt' else chapter.text if chapter.content_format=='markdown' else escape_plain_markdown(chapter.text)
            parts.append(heading+'\n\n'+text)
        title=('# '+escape_plain_markdown(book.title)) if format=='md' else book.title
        content=(title+'\n\n'+'\n\n'.join(parts)+'\n').encode('utf-8')
    name=f'{book.export_id}.{format}'
    relative=f'stories/{story_id}/exports/{name}'
    manifest={'schema_version':2,'export_id':book.export_id,'edition_id':book.edition_id,
        'story_id':story_id,'revision':book.snapshot.story.revision,'created_at':book.created_at,
        'format':format,'complete':not book.warnings,'age_rating':book.age_rating,
        'warnings':list(book.warnings)+([RATING_UNSET_EXPORT] if book.age_rating is None else []),
        'scenes':[c.entry for c in book.chapters],'word_count':sum(c.entry['word_count'] for c in book.chapters),
        'metadata':book.snapshot.publication.model_dump(mode='json'),'exporter':EXPORTER,
        'validation':{'fb2':'bundled XSD','epub':'local structure','md':'plain text','txt':'plain text','pdf':'Platypus layout + font coverage',
            'docx':'OOXML structure + scene bookmarks','rtf':'RTF 1.9 text'}[format],
        'output_file':name,'output_sha256':hashlib.sha256(content).hexdigest()}
    if format=='pdf':
        from ..publication.pdf import format_details
        manifest['format_details']=format_details()
    elif format in {'docx','rtf'}:
        # EXPORT-DOCX: the manuscript layout the file was built with.
        from ..publication.docx import PROFILE
        manifest['format_details']={'profile':PROFILE}
    repo.files.write(relative,content)
    repo.files.write(f'stories/{story_id}/exports/{book.export_id}.manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8'))
    return repo.files.resolve(relative)


def download_export(repo,story_id,name):
    """Read verified immutable bytes; an orphan output is never downloadable."""
    return export_download(repo,story_id,name)[0]


# EXPORT-001-S07: the readable download name of a book export.
_UNSAFE=re.compile(r'[\\/:*?"<>|,.\x00-\x1f]')
AUTHORS_LIMIT=60
NAME_LIMIT=150
SEPARATOR=' — '


def _clean(text):
    return ' '.join(_UNSAFE.sub(' ',text).split()) if isinstance(text,str) else ''


def _cut(text,limit):
    return text[:max(limit,0)].rstrip()


def _authors(names,language):
    names=[n for n in map(_clean,names) if n]
    english=isinstance(language,str) and language.lower().startswith('en')
    joined=(' and ' if english else ' та ').join(names)
    if len(joined)<=AUTHORS_LIMIT:return joined
    if len(names)==1:return _cut(names[0],AUTHORS_LIMIT)
    suffix=' and others' if english else ' та інші'
    return _cut(names[0],AUTHORS_LIMIT-len(suffix))+suffix


def _local_date(created,tz):
    try:return datetime.fromisoformat(created).astimezone(tz).date().isoformat()
    except (TypeError,ValueError):return ''


def download_name(manifest,export_id,format,tz=None):
    """`Автори — Назва — РРРР-ММ-ДД.<format>` from the manifest; parts that are empty after cleaning are skipped.
    The technical `<export_id>.<format>` when the manifest has no usable metadata or neither title nor authors."""
    technical=f'{export_id}.{format}'
    metadata=manifest.get('metadata') if isinstance(manifest,dict) else None
    try:
        people=[a['display_name'] for a in metadata['authors'] if isinstance(a,dict) and 'display_name' in a]
        card=metadata.get('card')
        authors=_authors(people,card.get('language') if isinstance(card,dict) else None)
        title=_clean(metadata['effective_title'])
    except (KeyError,TypeError,AttributeError):
        return technical
    if not title and not authors:return technical
    date=_local_date(manifest.get('created_at'),tz)
    fixed=sum(len(p)+len(SEPARATOR) for p in (authors,date) if p)
    if title:
        title=_cut(title,max(NAME_LIMIT-fixed,1))
        if len(title)+fixed>NAME_LIMIT and authors:
            authors=_cut(authors,len(authors)-(len(title)+fixed-NAME_LIMIT))
    return SEPARATOR.join(p for p in (authors,title,date) if p)+'.'+format


def export_download(repo,story_id,name):
    """(verified bytes, download file name) of an export file or its manifest."""
    repo.get_story(story_id)
    match=re.fullmatch(r'([0-9a-f]{32})\.(md|txt|fb2|epub|pdf|docx|rtf|manifest\.json)',name)
    if not match:raise KeyError('Немає експорту')
    export_id,extension=match.groups();base=f'stories/{story_id}/exports/'
    manifest_path=repo.files.resolve(base+export_id+'.manifest.json')
    if not manifest_path.is_file():raise KeyError('Немає завершеного експорту')
    raw=manifest_path.read_bytes()
    try:
        manifest=json.loads(raw)
        format=manifest['format']
        if manifest['story_id']!=story_id or format not in FORMATS:raise ValueError()
        output=f'{export_id}.{format}'
        if extension!='manifest.json' and name!=output:raise ValueError()
        if 'schema_version' not in manifest:
            if format not in {'md','txt'}:raise ValueError()
            content=repo.files.resolve(base+output).read_bytes()
        else:
            if manifest['schema_version']!=2 or manifest['export_id']!=export_id or manifest['output_file']!=output:raise ValueError()
            digest=manifest['output_sha256']
            if not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError()
            content=repo.files.read(base+output,digest)
    except (KeyError,ValueError,TypeError,OSError) as exc:
        raise StorageCorruption('Експорт або manifest пошкоджено; створіть новий експорт') from exc
    if extension=='manifest.json':return raw,name
    return content,download_name(manifest,export_id,format)
