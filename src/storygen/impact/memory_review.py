"""Optional scene-memory evidence for review; never modifies journals or forwarding."""
import json
from ..memory.journal import load_memory,validate_memory_journal


def validated_journal(view,id,scene):
    # One request validates the same journal for many review targets; the view (one SQL snapshot) keeps the first
    # successful result. Callers only read the journal; the hashes and the prefix list are handed out as new containers.
    key=(id,scene.id,scene.story_id,scene.position)
    if key not in view.journal_cache:view.journal_cache[key]=_validated_journal(view,id,scene)
    journal,hashes,prefix=view.journal_cache[key]
    return journal,dict(hashes),list(prefix)


def prose_sources(journal,count):
    """The prose sources of a journal: all of them, or all but the leading start snapshot of a series book (scene 0)."""
    ids=journal.source_prose_ids
    return ids[1:] if len(ids)==count+1 else ids


def _validated_journal(view,id,scene):
    ref=view.versions[id]
    if ref.story_id!=scene.story_id or ref.scene_id!=scene.id or ref.kind!='memory' or not ref.complete:
        raise ValueError('Пам’ять має неправильного власника або незавершене джерело')
    raw=view.read_blob(ref.relative_path,ref.sha256).decode('utf-8');journal=load_memory(raw)
    prefix=[s for s in view.peek_scenes(scene.story_id) if s.position<=scene.position]
    sources={};hashes={}
    ids=prose_sources(journal,len(prefix))
    if len(ids)<len(journal.source_prose_ids):
        # SERIES: scene 0 — the book's start snapshot heads the journal of a series book.
        start=view.versions[journal.source_prose_ids[0]]
        if start.kind!='series_start' or start.story_id!=scene.story_id or not start.complete:
            raise ValueError('Джерело пам’яті не відповідає префіксу сцен')
        from ..memory.series_start import read_series_start
        sources[start.id]=read_series_start(view.read_blob(start.relative_path,start.sha256).decode('utf-8'),start.id).text
        hashes[start.id]=start.sha256
    if len(ids)!=len(prefix):raise ValueError('Пам’ять не відповідає повному префіксу сцен')
    for item,source in zip(prefix,ids):
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
            memory_evidence_status='current' if prose_sources(journal,len(prefix))==[s.heads.get('prose') for s in prefix] else 'historical')
    except (KeyError,ValueError,OSError):pass
    return result
