"""Append-only author decisions and head publication share one transaction."""
import hashlib
import json
from dataclasses import dataclass

from ..dependency_models import AcceptancePreview, AcceptanceRecord
from ..domain import RevisionConflict, Scene, VersionRef, new_id, now
from .context_view import ContextView
from .snapshots import build_author_baseline, resolve_freshness
from .invalidation import invalidate_in_transaction


@dataclass
class AcceptanceResult:
    scene: Scene
    version: VersionRef
    acceptance: AcceptanceRecord


def _preview(view, scene_id, version_id):
    scene=view.get_scene(scene_id)
    ref=view.get_version(version_id)
    if ref.scene_id!=scene.id or ref.story_id!=scene.story_id or ref.kind not in {'draft','edited','manual'} or not ref.complete:
        raise ValueError('Приймати можна лише завершену чернетку або прозу цієї сцени')
    text=view.read_text(version_id)
    baseline=build_author_baseline(view,scene.id)
    freshness=resolve_freshness(view,version_id)
    payload={'scene_id':scene.id,'version_id':ref.id,'sha256':ref.sha256,'expected_revision':scene.revision,
        'baseline':baseline.model_dump(),'previous_baseline_id':freshness.baseline_id,'changes':[c.model_dump() for c in freshness.reasons]}
    fingerprint=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    return AcceptancePreview(version_id=ref.id,expected_revision=scene.revision,changes=freshness.reasons,
        baseline=baseline,preview_fingerprint=fingerprint,text=text)


def preview_acceptance(repo, scene_id, version_id):
    scene=repo.get_scene(scene_id)
    return _preview(repo.context_view(scene.story_id),scene_id,version_id)


def list_acceptances(repo, story_id, version_id=None):
    repo.get_story(story_id)
    with repo.db.connection() as db:
        records=[AcceptanceRecord.model_validate_json(r[0]) for r in db.execute(
            'SELECT payload FROM app_settings WHERE key LIKE ? ORDER BY rowid',('acceptance:'+story_id+':%',))]
        return [r for r in records if version_id is None or r.version_id==version_id]


def accept_version(repo, scene_id, version_id, expected_revision, preview_fingerprint, note=None):
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        scene=repo._active_scene(db,scene_id)
        if scene.revision!=expected_revision:
            raise RevisionConflict('Сцену змінено після перегляду. Перегляньте прийняття заново')
        view=ContextView(repo,db,scene.story_id)
        preview=_preview(view,scene_id,version_id)
        if preview.preview_fingerprint!=preview_fingerprint:
            raise RevisionConflict('Джерела змінено після перегляду. Потрібен новий перегляд')
        return _accept_in_transaction(repo,db,view,scene,preview,note)


# Mass acceptance from the story menu (DATA-010-S02): the prose counted as waiting, in reading order.


def _waiting_prose(view):
    rows=[]
    for scene in view.list_scenes(view.story.id):
        id=scene.heads.get('prose')
        if id and (view.is_stale(id) or view.effective_scene(scene.id).needs_review):rows.append((scene,id))
    return rows


def _bulk_preview(view):
    """The prose waiting now and a fingerprint of the whole book: the waiting previews plus the prose head and revision
    of every active scene, so an unlisted scene the acceptance cascade reaches cannot change unseen either."""
    rows=[(scene,_preview(view,scene.id,id)) for scene,id in _waiting_prose(view)]
    book=[[scene.id,scene.heads.get('prose'),scene.revision] for scene in view.list_scenes(view.story.id)]
    fingerprint=hashlib.sha256(json.dumps([[p.preview_fingerprint for _,p in rows],book]).encode()).hexdigest()
    return rows,fingerprint


def _scene_rows(rows):
    return [dict(scene_id=scene.id,title=scene.title,position=scene.position,version_id=preview.version_id) for scene,preview in rows]


def preview_prose_acceptance(repo, story_id):
    repo.get_story(story_id)
    rows,fingerprint=_bulk_preview(repo.context_view(story_id))
    return dict(scenes=_scene_rows(rows),fingerprint=fingerprint)


def _accept_cascade(repo, db, story_id):
    """Accept waiting prose one scene at a time, the first waiting scene in reading order, until none waits.

    A scene's author baseline records the acceptance ID of every earlier scene's prose, so accepting one scene makes
    later scenes that were current a moment ago wait (`source_baseline_changed`, or `needs_review` from the dependency
    edges). The list is therefore read again after every acceptance instead of being fixed up front (DATA-010-S02;
    the defect of 22.11.2026 left such scenes stale after the click)."""
    accepted=[]
    while True:
        view=ContextView(repo,db,story_id)
        rows=_waiting_prose(view)
        if not rows:
            return accepted
        scene,version_id=rows[0]
        if any(a['scene_id']==scene.id for a in accepted):
            # An author decision does not clear every reason (e.g. a changed review authority): stop, change nothing.
            reasons=', '.join(sorted({r.reason for r in resolve_freshness(view,version_id).reasons})) or 'needs_review'
            raise ValueError(f'Прозу сцени «{scene.title}» не можна прийняти масово: вона застаріла й після прийняття ({reasons})')
        preview=_preview(view,scene.id,version_id)
        record=_record_acceptance(repo,db,view,repo._active_scene(db,scene.id),preview,None)
        accepted.append(dict(scene_id=scene.id,title=scene.title,version_id=record.version_id,acceptance_id=record.id))


def accept_all_prose(repo, story_id, fingerprint):
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        repo._active_story(db,story_id)
        _,current=_bulk_preview(ContextView(repo,db,story_id))
        if current!=fingerprint:
            raise RevisionConflict('Прозу книги змінено після перегляду. Перегляньте прийняття заново')
        return dict(accepted=_accept_cascade(repo,db,story_id))


def _accept_in_transaction(repo, db, view, scene, preview, note):
        record=_record_acceptance(repo,db,view,scene,preview,note)
        current=ContextView(repo,db,scene.story_id)
        return AcceptanceResult(scene=current.effective_scene(scene.id),version=current.get_version(record.version_id),acceptance=record)


def _record_acceptance(repo, db, view, scene, preview, note):
        version_id=preview.version_id
        ref=view.get_version(version_id)
        record=AcceptanceRecord(id=new_id(),story_id=scene.story_id,scene_id=scene.id,version_id=ref.id,created_at=now(),
            action='accept_draft' if ref.kind=='draft' else 'accept_prose',note=note,baseline=preview.baseline,
            previous_baseline_id=resolve_freshness(view,version_id).baseline_id)
        db.execute('INSERT INTO app_settings VALUES(?,?)',('acceptance:'+scene.story_id+':'+record.id,record.model_dump_json()))
        head='draft' if ref.kind=='draft' else 'prose'
        previous=scene.heads.get(head)
        scene.heads[head]=ref.id
        scene.head_revisions[head]=scene.head_revisions.get(head,0)+1
        scene.revision+=1
        repo._save_scene(db,scene)
        invalidate_in_transaction(repo,db,list(dict.fromkeys([ref.id]+([previous] if previous and previous!=ref.id else []))),exclude=[ref.id])
        if head=='prose':
            scene=repo._get(db,'scenes',scene.id,Scene)
            scene.needs_review=False
            repo._save_scene(db,scene)
        repo._touch_story(db,scene.story_id)
        return record
