"""Shared rewrite proposal and source guards; independent of generation services."""
import hashlib
import json
from .authoring.comments import CommentSet,comment_fingerprint
from .copyediting import apply_proposal
from .dependency_models import DependencySnapshot,TargetCAS
from .domain import RevisionConflict
from .rewrite_diff import RewriteDiff
from .storage.snapshots import compare_snapshot


def classify_location(start,end,ranges):
    overlaps=[r for r in ranges if (r['start']<=start<=r['end'] if start==end else start<r['end'] and end>r['start'])]
    inside=any(r['start']<start<r['end'] if start==end else r['start']<=start and end<=r['end'] for r in overlaps)
    return dict(location='inside' if inside else 'cross_boundary' if overlaps else 'outside',comment_ids=[r['id'] for r in overlaps])


def proposal_data(view,attempt):
    raw=attempt.context.get('rewrite_proposal')
    if attempt.stage!='rewrite' or not raw or raw.get('protocol_version')!=2 or attempt.state not in {'needs_review','alternative','completed'}:
        raise ValueError('Спроба не має пропозиції письменника')
    scene=view.get_scene(attempt.scene_id)
    source=view.get_version(raw['source_id'])
    if source.kind!='draft' or source.scene_id!=scene.id or scene.story_id!=attempt.story_id or not source.complete:
        raise ValueError('Неприпустиме джерело пропозиції')
    original=view.read_text(source.id)
    proposal=RewriteDiff.model_validate(raw['proposal'])
    candidate=apply_proposal(original,proposal)
    fingerprint=hashlib.sha256(json.dumps(raw,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    notes=CommentSet.model_validate_json(attempt.context['fragments']['rewrite_notes'])
    if notes.scene_id!=scene.id or notes.story_id!=scene.story_id or comment_fingerprint(notes,source)!=attempt.context['fragments']['rewrite_comment_fingerprint']:
        raise ValueError('Неприпустимі коментарі пропозиції')
    return scene,source,original,proposal,candidate,fingerprint,notes


def ensure_current(view,attempt,scene,source,notes,latest):
    if attempt.context.get('rewrite_decisions'):raise ValueError('Цю пропозицію вже розглянуто')
    target=TargetCAS.model_validate(attempt.context['target_cas'])
    if target.scene_id!=scene.id or target.head!='draft' or target.version_id!=source.id or scene.heads.get('draft')!=source.id or scene.head_revisions.get('draft',0)!=target.head_revision:
        raise RevisionConflict('Чернетку змінено; результат доступний лише як альтернатива')
    if not latest or latest.id!=notes.id or latest.revision!=notes.revision or comment_fingerprint(latest,source)!=attempt.context['fragments']['rewrite_comment_fingerprint']:
        raise RevisionConflict('Коментарі змінено; результат не може їх перезаписати')
    snapshot=DependencySnapshot.model_validate(attempt.context['dependency_snapshot'])
    if snapshot.scope!='author_rewrite' or snapshot.frozen_author_source_id!=source.id or set(snapshot.refs)!=set(attempt.context['input_refs']):
        raise ValueError('Некоректна база залежностей переписування')
    if compare_snapshot(view,snapshot):raise RevisionConflict('Контекст змінився; перегляньте джерела пропозиції')


