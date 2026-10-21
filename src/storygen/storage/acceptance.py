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
        current=ContextView(repo,db,scene.story_id)
        return AcceptanceResult(scene=current.effective_scene(scene.id),version=current.get_version(ref.id),acceptance=record)
