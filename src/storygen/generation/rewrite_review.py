"""Draft-only review service over shared domain guards."""
from ..copyediting import validate_indices,apply_proposal
from ..domain import RevisionConflict
from ..sentence_groups import sentence_groups,validate_group_selection,sentence_context
from ..rewriting import classify_location,proposal_data,ensure_current


def rewrite_preview(repo,scene_id,attempt_id):
    attempt=repo.get_attempt(attempt_id)
    if attempt.scene_id!=scene_id:raise ValueError('Пропозиція належить іншій сцені')
    view=repo.context_view(attempt.story_id)
    scene,source,original,proposal,candidate,fingerprint,notes=proposal_data(view,attempt)
    latest=repo.get_comment_set(scene.id);reason=None
    try:ensure_current(view,attempt,scene,source,notes,latest)
    except ValueError as exc:reason=str(exc)
    ranges=[dict(id=c.id,start=c.anchor.start,end=c.anchor.end) for c in notes.comments]
    edits=[]
    for edit in proposal.edits:
        item=edit.model_dump();item.update(category='unclassified',**sentence_context(original,edit.start,edit.end),**classify_location(edit.start,edit.end,ranges));edits.append(item)
    groups=sentence_groups(original,proposal,source.content_format)
    for group in groups:
        locations={edits[i]['location'] for i in group['indices']}
        ids=sorted({id for i in group['indices'] for id in edits[i]['comment_ids']})
        group.update(location=next(iter(locations)) if len(locations)==1 and not (locations=={'inside'} and len(ids)>1) else 'cross_boundary',comment_ids=ids)
    return dict(attempt_id=attempt.id,protocol_version=2,original=original,preview=candidate,edits=edits,groups=groups,
        has_changes=bool(edits),default_selected_indices=[],proposal_fingerprint=fingerprint,expected_revision=scene.revision,
        expected_comments_revision=notes.revision,decisions=attempt.context.get('rewrite_decisions',[]),comments=notes.model_dump(),
        can_apply=reason is None,reason=reason,warnings=[],classification_history=[],can_classify=False)


def selection_preview(repo,scene_id,attempt_id,indices,expected_revision,fingerprint,expected_comments_revision):
    p=rewrite_preview(repo,scene_id,attempt_id)
    if p['expected_revision']!=expected_revision or p['proposal_fingerprint']!=fingerprint or p['expected_comments_revision']!=expected_comments_revision:
        raise RevisionConflict('Сцену, коментарі або пропозицію змінено')
    if not p['can_apply']:raise RevisionConflict(p['reason'])
    attempt=repo.get_attempt(attempt_id)
    _,source,original,proposal,_,_,_=proposal_data(repo.context_view(attempt.story_id),attempt)
    indices=validate_indices(indices,len(proposal.edits));validate_group_selection(original,proposal,indices,source.content_format)
    return dict(text=apply_proposal(original,proposal,indices),selected_indices=indices,proposal_fingerprint=fingerprint,warnings=[])


def apply_selection(repo,scene_id,attempt_id,indices,expected_revision,fingerprint,expected_comments_revision):
    selection_preview(repo,scene_id,attempt_id,indices,expected_revision,fingerprint,expected_comments_revision)
    from ..storage.rewrite_store import publish_rewrite_selection
    return publish_rewrite_selection(repo,scene_id,attempt_id,indices,expected_revision,fingerprint,expected_comments_revision)
