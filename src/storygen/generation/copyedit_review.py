"""Editor proposal read/selection service, using public repository methods."""
from ..sentence_groups import sentence_context,sentence_groups,validate_group_selection

from ..copyediting import proposal_data, ensure_selectable, validate_indices, apply_proposal
from ..dependency_models import DependencySnapshot
from ..storage.snapshots import compare_snapshot


def copyedit_preview(repo, scene_id, attempt_id):
    attempt = repo.get_attempt(attempt_id)
    if attempt.scene_id != scene_id:
        raise ValueError('Пропозиція належить іншій сцені')
    view = repo.context_view(attempt.story_id)
    scene, original, proposal, text, fingerprint = proposal_data(view, attempt)
    reason = None
    try:
        ensure_selectable(view, attempt, compare_snapshot(view, DependencySnapshot.model_validate(attempt.context["dependency_snapshot"])))
    except ValueError as exc:
        reason = str(exc)
    raw=attempt.context['copyedit_proposal']
    edits=[e.model_dump() for e in proposal.edits]
    from ..evidence import fragment_text
    fragments = {f.id: f for f in fragment_text(original)} if raw['protocol_version']==1 else {}
    for edit in edits:
        if raw['protocol_version']==2:
            start, end = edit['start'], edit['end']
            edit.update(category='unclassified')
        else:
            fragment = fragments[edit['fragment_id']]
            start = fragment.start + fragment.text.index(edit['original'])
            end = start + len(edit['original'])
        edit.update(sentence_context(original, start, end))
    from .edit_classification import classification_state
    advice=classification_state(repo,attempt,fingerprint) if raw['protocol_version']==2 else dict(classification=None,classification_history=[],can_classify=False,classification_reason='Доступно для редактури з diff')
    if text==original:
        advice.update(can_classify=False,classification_reason='Немає змін для класифікації')
    return dict(**advice,attempt_id=attempt.id, has_changes=text!=original,protocol_version=raw['protocol_version'],default_selected_indices=[] if raw['protocol_version']==2 else list(range(len(edits))),original=original, edits=edits,groups=sentence_groups(original,proposal),grouping_version=1,
                warnings=attempt.context.get('editor_warnings',[]),
                preview=text, proposal_fingerprint=fingerprint, expected_revision=scene.revision,
                decisions=attempt.context.get('copyedit_decisions', []), can_apply=reason is None, reason=reason)


def select_copyedits(repo, scene_id, attempt_id, selected_indices, expected_revision, proposal_fingerprint):
    attempt = repo.get_attempt(attempt_id)
    if attempt.scene_id != scene_id:
        raise ValueError('Пропозиція належить іншій сцені')
    view = repo.context_view(attempt.story_id)
    _, original, proposal, _, fingerprint = proposal_data(view, attempt)
    if fingerprint != proposal_fingerprint:
        raise ValueError('Пропозиція змінилася; відкрийте її знову')
    indices = validate_indices(selected_indices, len(proposal.edits))
    validate_group_selection(original,proposal,indices)
    ensure_selectable(view, attempt, compare_snapshot(view, DependencySnapshot.model_validate(attempt.context["dependency_snapshot"])))
    text = apply_proposal(original,proposal,indices)
    snapshot = DependencySnapshot.model_validate(attempt.context['dependency_snapshot'])
    ref = repo.save_version(attempt.story_id, scene_id, 'edited', text, attempt.context['input_refs'],
                            attempt.run_id, dependency_snapshot=snapshot)
    from .language import language_warnings
    return repo.commit_copyedit_selection(attempt_id, ref, indices, expected_revision, fingerprint, language_warnings(text))


def selection_preview(repo,scene_id,attempt_id,indices,expected_revision,fingerprint):
    preview=copyedit_preview(repo,scene_id,attempt_id)
    if preview['expected_revision']!=expected_revision or preview['proposal_fingerprint']!=fingerprint:
        from ..domain import RevisionConflict
        raise RevisionConflict('Сцену або пропозицію змінено; відкрийте перегляд знову')
    if not preview['can_apply']:
        raise ValueError(preview['reason'])
    attempt=repo.get_attempt(attempt_id)
    _,original,proposal,_,_=proposal_data(repo.context_view(attempt.story_id),attempt)
    indices=validate_indices(indices,len(proposal.edits))
    validate_group_selection(original,proposal,indices)
    text=apply_proposal(original,proposal,indices)
    from ..rewrite_diff import rewrite_warnings
    return dict(text=text,selected_indices=indices,proposal_fingerprint=fingerprint,warnings=rewrite_warnings(original,text,[proposal.edits[i] for i in indices]) if preview['protocol_version']==2 else [])
