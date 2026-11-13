"""Read-only, scene-scoped author consent for using historical memory evidence."""
import hashlib
import json
from .journal import MemoryJournal, load_memory, validate_memory_journal


class MemoryApprovalRequired(ValueError):
    def __init__(self,review):
        super().__init__('Попередня пам’ять потребує авторського підтвердження')
        self.review=review


def _candidate(view,scene_id):
    scene=view.get_scene(scene_id)
    from .previous import previous_memory, read_previous_journal
    before=previous_memory(view,scene)  # MergeRequired (a ValueError) when a merge point has no usable merge
    previous=before.ancestors
    if not previous:return MemoryJournal(),None,[],False
    memory_id=before.memory_id
    if not memory_id:raise ValueError('Спершу оновіть пам’ять попередньої сцени')
    ref=view.get_version(memory_id)
    owner_ok=ref.kind=='memory_merge' and ref.scene_id is None if before.merge_key else ref.kind=='memory' and ref.scene_id==previous[-1].id
    if not owner_ok or ref.story_id!=scene.story_id or not ref.complete:
        raise ValueError('Попередня пам’ять незавершена або належить іншій сцені')
    journal=read_previous_journal(view,before)
    if len(journal.source_prose_ids)!=len(previous):
        raise ValueError('Попередня пам’ять не відповідає порядку попередніх сцен')
    # Only kind/scene_id/story_id/complete/sha256 are read below; a Repository (execute_stage) has no peek_version.
    peek=getattr(view,'peek_version',view.get_version)
    sources={};current=[];changed_text=changed_versions=0
    for item,old_id in zip(previous,journal.source_prose_ids):
        try:old=peek(old_id)
        except KeyError:raise ValueError('Попередня пам’ять містить невідоме або стороннє джерело') from None
        current_id=item.heads.get('prose')
        if not current_id:raise ValueError('Потрібні актуальна проза й пам’ять попередніх сцен')
        selected=peek(current_id)
        for source in [old,selected]:
            if source.story_id!=scene.story_id or source.scene_id!=item.id or source.kind not in {'manual','edited'} or not source.complete:
                raise ValueError('Попередня пам’ять містить джерело іншої або майбутньої сцени')
        sources[old_id]=view.read_text(old_id)
        view.read_text(current_id)
        current.append(current_id)
        changed_versions+=old_id!=current_id
        changed_text+=old.sha256!=selected.sha256
    validate_memory_journal(journal,sources)
    provenance=list(ref.dependency_snapshot.memory_provenance) if ref.dependency_snapshot else []
    pairs=approved_source_pairs(provenance)
    needs_confirmation=ref.stale or any(old!=selected and (old,selected) not in pairs for old,selected in zip(journal.source_prose_ids,current))
    baseline={'scene_id':scene.id,'revision':scene.revision,'heads':scene.heads,'characters':scene.character_ids,
              'prefix':[(s.id,s.heads.get('prose')) for s in previous],
              'memory_id':ref.id,'memory_sha256':ref.sha256,'stale':ref.stale,
              'source_hashes':[(id,peek(id).sha256) for id in sources]}
    fingerprint=hashlib.sha256(json.dumps(baseline,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    review={'fingerprint':fingerprint,'scene_id':scene.id,'memory_id':ref.id,'memory_scene_number':previous[-1].position+1,
            'source_prose_ids':journal.source_prose_ids,'current_source_prose_ids':current,
            'changed_version_count':changed_versions,'changed_text_count':changed_text,'risk':bool(changed_text)}
    return journal,review,provenance,needs_confirmation


def memory_for_update(view,scene_id,approval=None):
    journal,review,provenance,needs_confirmation=_candidate(view,scene_id)
    if approval is not None and (not needs_confirmation or review['fingerprint']!=approval):
        raise ValueError('Дані змінилися після підтвердження пам’яті; перегляньте їх заново')
    if needs_confirmation:
        if approval is None:raise MemoryApprovalRequired(review)
        provenance=[*provenance,review]
        return journal,review,provenance
    return journal,None,provenance


def journal_for_read(view,scene_id):
    journal,review,provenance,needs_confirmation=_candidate(view,scene_id)
    if needs_confirmation:
        raise ValueError('Спершу оновіть пам’ять попередньої сцени')
    return journal


def provenance_warnings(provenance):
    if not provenance:return []
    if any(p.risk if hasattr(p,'risk') else p['risk'] for p in provenance):
        return ['Пам’ять використовує історичні факти після авторського підтвердження; попередню прозу змінено, факти можуть потребувати перегляду.']
    return ['Автор підтвердив використання попередньої пам’яті; історичні джерела й цитати збережено.']


def approved_source_pairs(provenance):
    return {(old,current) for approval in provenance
            for old,current in zip(approval.source_prose_ids,approval.current_source_prose_ids)}


def provenance_before(view,scene_id):
    scene=view.get_scene(scene_id)
    from .previous import previous_memory
    before=previous_memory(view,scene,require=False)
    if not before.memory_id:return []
    ref=view.get_version(before.memory_id)
    return list(ref.dependency_snapshot.memory_provenance) if ref.dependency_snapshot else []


def memory_for_manual_edit(view,scene_id):
    """A current output's consent may support its manual edits, never a new model call."""
    journal,review,provenance,needs_confirmation=_candidate(view,scene_id)
    if not needs_confirmation:return journal,provenance,[]
    scene=view.get_scene(scene_id)
    current_id=scene.heads.get('memory')
    ref=view.get_version(current_id) if current_id else None
    snapshot=ref.dependency_snapshot if ref else None
    if ref and ref.kind=='memory' and ref.scene_id==scene_id and ref.complete and not ref.stale and snapshot:
        for approval in snapshot.memory_provenance:
            if (approval.scene_id==scene_id and approval.memory_id==review['memory_id']
                    and approval.memory_id in snapshot.accepted_stale_memory_ids
                    and approval.source_prose_ids==review['source_prose_ids']
                    and approval.current_source_prose_ids==review['current_source_prose_ids']):
                view.read_text(current_id)
                return journal,list(snapshot.memory_provenance),[approval.memory_id]
    raise ValueError('Спершу оновіть пам’ять попередньої сцени')
