"""Publication facade: capture once, validate, publish bytes, then commit manifest."""
import hashlib
import json
import re
from pathlib import Path
from typing import Literal
from ..publication.book import capture,EXPORTER,INCOMPLETE
from ..storage.files import StorageCorruption

FORMATS={'md','txt','fb2','epub','pdf'}


def export_story(repo,story_id: str,format: Literal['md','txt','fb2','epub','pdf'],allow_incomplete: bool = False) -> Path:
    if format not in FORMATS:raise ValueError('Доступні MD, TXT, FB2, EPUB і PDF')
    book=capture(repo,story_id,format,allow_incomplete)
    if format in {'fb2','epub','pdf'}:
        if format=='fb2':from ..publication.fb2 import render
        elif format=='pdf':from ..publication.pdf import render
        else:from ..publication.epub import render
        content=render(book)
    else:
        parts=[]
        for chapter in book.chapters:
            heading=('## ' if format=='md' else '')+chapter.title
            marker='\n[НЕЗАВЕРШЕНО: '+'; '.join(chapter.entry['warnings'])+']\n' if chapter.entry['warnings'] else ''
            parts.append(heading+'\n'+marker+'\n'+chapter.text)
        title=('# ' if format=='md' else '')+book.title
        if book.warnings:title+='\n\n['+INCOMPLETE+']'
        content=(title+'\n\n'+'\n\n'.join(parts)+'\n').encode('utf-8')
    name=f'{book.export_id}.{format}'
    relative=f'stories/{story_id}/exports/{name}'
    manifest={'schema_version':2,'export_id':book.export_id,'edition_id':book.edition_id,
        'story_id':story_id,'revision':book.snapshot.story.revision,'created_at':book.created_at,
        'format':format,'complete':not book.warnings,'warnings':list(book.warnings),
        'scenes':[c.entry for c in book.chapters],'word_count':sum(c.entry['word_count'] for c in book.chapters),
        'metadata':book.snapshot.publication.model_dump(mode='json'),'exporter':EXPORTER,
        'validation':{'fb2':'bundled XSD','epub':'local structure','md':'plain text','txt':'plain text','pdf':'Platypus layout + font coverage'}[format],
        'output_file':name,'output_sha256':hashlib.sha256(content).hexdigest()}
    if format=='pdf':
        from ..publication.pdf import format_details
        manifest['format_details']=format_details()
    repo.files.write(relative,content)
    repo.files.write(f'stories/{story_id}/exports/{book.export_id}.manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8'))
    return repo.files.resolve(relative)


def download_export(repo,story_id,name):
    """Read verified immutable bytes; an orphan output is never downloadable."""
    repo.get_story(story_id)
    match=re.fullmatch(r'([0-9a-f]{32})\.(md|txt|fb2|epub|pdf|manifest\.json)',name)
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
    return raw if extension=='manifest.json' else content
