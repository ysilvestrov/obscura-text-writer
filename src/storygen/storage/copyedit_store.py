"""Atomic publication of a chosen subset against the original editor inputs."""
from ..domain import RevisionConflict, StageAttempt, VersionRef


def commit_copyedit_selection(
    repo,
    attempt_id: str,
    result_ref: VersionRef,
    indices: list[int],
    expected_revision: int,
    fingerprint: str,
    warnings,
) -> dict:
    from .context_view import ContextView
    from .invalidation import invalidate_in_transaction
    from .snapshots import compare_snapshot
    from ..dependency_models import DependencySnapshot
    from ..copyediting import proposal_data, ensure_selectable, validate_indices, record_decision
    from ..copyediting import apply_proposal
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        attempt = repo._get(db, 'stage_attempts', attempt_id, StageAttempt)
        view = ContextView(repo, db, attempt.story_id)
        scene, original, proposal, _, actual_fingerprint = proposal_data(view, attempt)
        if scene.revision != expected_revision or fingerprint != actual_fingerprint:
            raise RevisionConflict('Сцену або пропозицію змінено; відкрийте перегляд знову')
        ensure_selectable(
            view,
            attempt,
            compare_snapshot(view, DependencySnapshot.model_validate(attempt.context["dependency_snapshot"]))
        )
        loop_run=None
        if attempt.context.get('edit_loop_summary'):
            from ..run_models import Run
            loop_run=repo._get(db,'runs',attempt.run_id,Run)
            key=attempt.context['edit_loop_summary'].get('task_cursor','')
            standalone=loop_run.request.mode=='edit_loop'
            checkpoint=loop_run.editor_loop if standalone else loop_run.editor_loops.get(key)
            task=loop_run.tasks[int(key)] if key.isdecimal() and int(key)<len(loop_run.tasks) else {}
            valid_scope = loop_run.request.scene_id == scene.id if standalone else (
                loop_run.request.mode in {'scene', 'remaining'}
                and task.get('editor_loop')
                and task.get('scene_id') == scene.id
                and (loop_run.state != 'needs_review' or str(loop_run.cursor) == key)
            )
            if (
                not valid_scope
                or not checkpoint
                or checkpoint.get('proposal_attempt_id') != attempt.id
                or loop_run.state not in {'needs_review', 'completed', 'cancelled'}
            ):
                raise RevisionConflict('Підсумковий результат циклу ще не готовий до прийняття')
        indices = validate_indices(indices, len(proposal.edits))
        from ..sentence_groups import validate_group_selection
        validate_group_selection(original,proposal,indices)
        ref = repo._get(db, 'versions', result_ref.id, VersionRef)
        snapshot = DependencySnapshot.model_validate(attempt.context['dependency_snapshot'])
        if (
            ref.story_id != scene.story_id
            or ref.scene_id != scene.id
            or ref.kind != 'edited'
            or ref.input_refs != attempt.context['input_refs']
            or ref.dependency_snapshot != snapshot
            or view.read_text(ref.id) != apply_proposal(original, proposal, indices)
        ):
            raise ValueError('Результат не відповідає вибраним правкам')
        previous = scene.heads.get('prose')
        scene.heads['prose'] = ref.id
        scene.head_revisions['prose'] = scene.head_revisions.get('prose', 0) + 1
        scene.revision += 1
        scene.needs_review = False
        repo._save_scene(db, scene)
        if previous and previous != ref.id:
            invalidate_in_transaction(repo, db, [previous], exclude=[ref.id])
        repo._touch_story(db, scene.story_id)
        record_decision(attempt, scene, indices, ref.id, 'manual', warnings)
        if attempt.context['copyedit_proposal']['protocol_version']==2:
            from ..rewrite_diff import rewrite_warnings
            attempt.context['copyedit_decisions'][-1]['rewrite_warnings']=rewrite_warnings(original,view.read_text(ref.id),[proposal.edits[i] for i in indices])
        attempt.result_version_id = ref.id
        if attempt.state in {'needs_review', 'alternative'}:
            attempt.state = 'completed'
            attempt.error = None
        db.execute(
            'UPDATE stage_attempts SET state=?,payload=? WHERE id=?',
            (attempt.state, attempt.model_dump_json(), attempt.id)
        )
        if loop_run and loop_run.state=='needs_review':
            if standalone:
                loop_run.state='completed'
                loop_run.cursor=len(loop_run.tasks)
            loop_run.error=None
            loop_run.warning='Підсумкові правки прийнято.'+(' Пам’ять і оцінювання оновлюються окремо.' if standalone else '')
            db.execute(
                'UPDATE runs SET state=?,payload=? WHERE id=?',
                (loop_run.state,loop_run.model_dump_json(),loop_run.id)
            )
            from ..run_models import RunEvent
            seq=db.execute('SELECT COALESCE(MAX(seq),0)+1 FROM run_events WHERE run_id=?',(loop_run.id,)).fetchone()[0]
            for offset, (type, data) in enumerate(
                [
                    ('edit_loop_accepted', {'version_id': ref.id, 'attempt_id': attempt.id}),
                    ('state', {'state': loop_run.state, 'warning': loop_run.warning}),
                ]
            ):
                event=RunEvent(run_id=loop_run.id,seq=seq+offset,type=type,data=data)
                db.execute(
                    'INSERT INTO run_events VALUES(?,?,?,?)',
                    (loop_run.id,event.seq,type,event.model_dump_json())
                )
    result={'scene': scene, 'version': ref, 'attempt': attempt}
    if loop_run:
        result['run']=loop_run
    return result
