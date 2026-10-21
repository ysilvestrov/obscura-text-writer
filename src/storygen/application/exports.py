import json
import re
from pathlib import Path
from typing import Literal

from ..domain import new_id, now


def export_story(repo,story_id: str,format: Literal['md','txt'],allow_incomplete: bool = False) -> Path:
    if format not in {'md','txt'}:raise ValueError('Доступні MD і TXT')
    entries=[];warnings=[];parts=[]
    story, snapshot = repo.export_snapshot(story_id)
    if not snapshot:warnings.append('Немає сцен')
    for scene, ref in snapshot:
        entry={'scene_id':scene.id,'title':scene.title,'position':scene.position,'version_id':ref.id if ref else None,'warnings':[]}
        text=''
        if ref:
            if ref.stale or not ref.complete or scene.needs_review:entry['warnings'].append('Сцена застаріла або потребує перегляду')
            text=repo.files.read(ref.relative_path,ref.sha256).decode('utf-8')
            entry['sha256']=ref.sha256
        else:entry['warnings'].append('Немає завершеної вибраної прози')
        warnings.extend(entry['warnings'])
        entry['word_count']=len(re.findall(r"\b[\w’'-]+\b",text))
        entries.append(entry)
        heading=('## ' if format=='md' else '')+scene.title
        marker='\n[НЕЗАВЕРШЕНО: '+ '; '.join(entry['warnings'])+']\n' if entry['warnings'] else ''
        parts.append(heading+'\n'+marker+'\n'+text)
    if warnings and not allow_incomplete:
        raise ValueError('Експорт зупинено: є відсутні або застарілі сцени. Явно дозвольте неповний експорт.')
    id=new_id()
    relative=f'stories/{story_id}/exports/{id}.{format}'
    title=('# ' if format=='md' else '')+story.title
    if warnings:title+='\n\n[НЕЗАВЕРШЕНО — див. попередження у сценах і manifest]'
    manifest={'story_id':story_id,'revision':story.revision,'created_at':now(),'format':format,'complete':not warnings,'warnings':warnings,'scenes':entries,'word_count':sum(e['word_count'] for e in entries)}
    repo.files.write(f'stories/{story_id}/exports/{id}.manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8'))
    repo.files.write(relative,(title+'\n\n'+'\n\n'.join(parts)+'\n').encode('utf-8'))
    return repo.files.resolve(relative)
