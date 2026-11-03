"""Optional scene-memory evidence for review; never modifies journals or forwarding."""
import json
from ..memory.journal import load_memory,validate_memory_journal


def validated_journal(view,id,scene):
    ref=view.versions[id]
    if ref.story_id!=scene.story_id or ref.scene_id!=scene.id or ref.kind!='memory' or not ref.complete:
        raise ValueError('Пам’ять має неправильного власника або незавершене джерело')
    raw=view.read_blob(ref.relative_path,ref.sha256).decode('utf-8');journal=load_memory(raw)
    prefix=[s for s in view.list_scenes(scene.story_id) if s.position<=scene.position]
    if len(journal.source_prose_ids)!=len(prefix):raise ValueError('Пам’ять не відповідає повному префіксу сцен')
    sources={};hashes={}
    for item,source in zip(prefix,journal.source_prose_ids):
        v=view.versions[source]
        if v.scene_id!=item.id or v.story_id!=scene.story_id or v.kind not in {'manual','edited'} or not v.complete:
            raise ValueError('Джерело пам’яті не відповідає префіксу сцен')
        sources[source]=view.read_blob(v.relative_path,v.sha256).decode('utf-8');hashes[source]=v.sha256
    validate_memory_journal(journal,sources)
    return journal,hashes,prefix


def capture_memory(view,scene):
    id=scene.heads.get('memory')
    result=dict(memory_id=id,memory_sha256=None,memory_text='',memory_source_hashes={},memory_evidence_status='missing' if not id else 'invalid')
    if not id:return result
    try:
        journal,hashes,prefix=validated_journal(view,id,scene)
        result.update(memory_sha256=view.versions[id].sha256,memory_text=journal.model_dump_json(),memory_source_hashes=hashes,
            memory_evidence_status='current' if journal.source_prose_ids==[s.heads.get('prose') for s in prefix] else 'historical')
    except (KeyError,ValueError,OSError):pass
    return result
