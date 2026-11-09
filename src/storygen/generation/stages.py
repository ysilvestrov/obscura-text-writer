import json
import threading

from ..domain import StageAttempt, new_id
from ..memory.journal import load_memory, parse_memory_result
from ..memory.service import journal_before, validate_memory_journal
from .stream_buffer import StreamBuffer


def execute_stage(
    repo,
    scene_id: str | None,
    stage: str,
    context,
    gateway,
    cancel: threading.Event,
    on_delta,
    run_id: str | None = None,
    task_cursor: int | None = None,
) -> StageAttempt:
    id=new_id()
    attempt=StageAttempt(
        id=id,
        run_id=run_id,
        story_id=context.story_id,
        scene_id=scene_id,
        stage=stage,
        context=context.model_dump(),
        partial_path=f'stories/{context.story_id}/runs/{id}/partial.txt'
    )
    if stage=='review_part':
        attempt.context['review_spec']=json.loads(context.fragments['review_spec'])
        attempt.context['review_plan_id']=json.loads(context.fragments['review_plan'])['id']
    if stage=='impact_part':
        attempt.context['impact_chunk_manifest']=context.fragments['impact_chunk_manifest']
        attempt.context['impact_chunk_task']=json.loads(context.fragments['impact_chunk_task'])
    if stage=='classify':
        from .edit_classification import identity
        attempt.context.update({key:context.fragments[key] for key in ['classification_proposal_id','classification_fingerprint']})
        attempt.context['classification_identity']=identity(context.settings.provider)
    if task_cursor is not None:
        attempt.context['run_cursor']=task_cursor
    repo.save_attempt(attempt)  # Persist exact inputs before a model can receive anything.
    if hasattr(gateway,'bind_accounting'):
        from ..providers.accounting import CallAccounting
        run=repo.get_run(run_id) if run_id else None
        gateway.bind_accounting(
            CallAccounting(
                repo,
                'story:' + context.story_id,
                run_id or attempt.id,
                attempt.id,
                attempt.id,
                run.request.budget_limit_usd if run else None,
            )
        )
    parts=[]
    terminal=None
    try:
        with StreamBuffer(repo.files.open_partial(attempt.partial_path), on_delta) as buffer:
            for event in gateway.stream(context,cancel):
                if event.type=='delta':
                    parts.append(event.text)
                    buffer.append(event.text)
                else:
                    terminal=event
    except Exception:
        attempt.state='cancelled' if cancel.is_set() else 'failed'
        attempt.error='Потік або збереження checkpoint перервано. Автоматичного повтору немає.'
        if stage=='publication_suggest':
            attempt.context['publication_failure']={'category':attempt.state if cancel.is_set() else 'technical','message':attempt.error}
        repo.save_attempt(attempt)
        raise
    text=''.join(parts)
    accounting=getattr(gateway,'accounting',None)
    if accounting:
        attempt.context['accounting']=accounting.result
        if accounting.warning:
            attempt.context['accounting_warning']=accounting.warning
    if terminal:
        if terminal.type=='error' and terminal.failure:attempt.context['generation_failure']=terminal.failure
        attempt.usage=terminal.usage
        attempt.finish_reason=terminal.finish_reason
        if stage=='classify' and terminal.refusal:
            attempt.context['classification_refusal']=True
        if stage=='classify' and terminal.type=='error':
            if terminal.finish_reason=='content_filter':
                terminal.message='Класифікатор відмовився через контент; автоматичного повтору немає.'
            failure = (
                {'category': 'refusal_content', 'message': terminal.message}
                if terminal.finish_reason == 'content_filter'
                else terminal.failure or {
                    'category': (
                        'refusal_unknown'
                        if terminal.refusal
                        else 'output_limit' if terminal.finish_reason == 'length' else 'technical'
                    ),
                    'message': terminal.message,
                }
            )
            attempt.context['classification_failure']=failure
            if failure['category'].startswith('refusal_'):
                attempt.context['classification_refusal']=True
        if context.api_request:
            try:
                from ..token_budget.service import record_usage
                record_usage(repo,context.settings.provider.provider,context.settings.provider.base_url,
                    context.api_request,attempt.usage,attempt.id)
            except Exception:
                attempt.context['token_observation_warning']='Не вдалося зберегти token usage; первинні дані лишилися у спробі.'
    if cancel.is_set() or (terminal and terminal.type=='cancelled'):
        attempt.state='cancelled'
    elif terminal is None or terminal.type!='terminal' or terminal.finish_reason!='stop' or not text.strip() or (stage in {'rewrite','impact_delta','impact_check','impact_part','review_part'} and terminal.refusal):
        attempt.state='failed'
        if (stage=='edit' and terminal and terminal.finish_reason=='stop' and not text.strip()
                and (terminal.type=='terminal' or terminal.failure.get('category')=='empty_output')):
            attempt.context['editor_failure']={'category':'empty_output','message':'Редактор повернув порожню відповідь'}
            attempt.error=(terminal.message or 'Редактор повернув порожню відповідь. Автоматичного повтору немає.')+' Прийняття недоступне; поточний текст не змінено.'
        else:
            attempt.error=terminal.message if terminal else 'Потік не має підтвердженого завершення'
    if attempt.state!='running':
        if stage in {'impact_delta','impact_check','impact_part','review_part'}:
            category=('cancelled' if attempt.state=='cancelled' else 'refusal_content' if attempt.finish_reason=='content_filter' else 'refusal_unknown' if terminal and terminal.refusal else 'output_limit' if attempt.finish_reason=='length' else 'empty_output' if attempt.finish_reason=='stop' and not text.strip() else (terminal.failure.get('category','technical') if terminal else 'incomplete'))
            if category=='empty_output':
                from ..providers.streaming import empty_output_message
                attempt.error=empty_output_message(context,attempt.usage)
            attempt.error=attempt.error or 'Перевірка впливу не отримала повної відповіді; автоматичного повтору немає'
            attempt.context['impact_failure']={**(terminal.failure if terminal else {}),'category':category,'message':attempt.error}

        if stage=='rewrite':
            category=('cancelled' if attempt.state=='cancelled' else
                'refusal_content' if attempt.finish_reason=='content_filter' else
                'refusal_unknown' if terminal and terminal.refusal else
                'output_limit' if attempt.finish_reason=='length' else
                'empty_output' if terminal and terminal.finish_reason=='stop' and not text.strip() else
                terminal.failure.get('category','technical') if terminal else 'incomplete')
            if category=='empty_output':
                from ..providers.streaming import empty_output_message
                attempt.error=empty_output_message(context,attempt.usage)
            elif category.startswith('refusal_'):
                attempt.error=attempt.error or 'Письменник відмовився; автоматичного повтору немає'
            attempt.error=attempt.error or 'Переписування не завершено; автоматичного повтору немає'
            attempt.context['rewrite_failure']={'category':category,'message':attempt.error}
        if stage=='edit' and attempt.state=='failed' and context.fragments.get('edit_loop_run_id'):
            attempt.context['edit_loop_failure_origin']='model_response'
        if stage=='publication_suggest':
            category=('cancelled' if attempt.state=='cancelled' else
                'output_limit' if attempt.finish_reason=='length' else
                'refusal_content' if attempt.finish_reason=='content_filter' else
                'refusal_unknown' if terminal and terminal.refusal else
                'empty_output' if terminal and terminal.finish_reason=='stop' and not text.strip() else
                (terminal.failure.get('category','technical') if terminal else 'incomplete'))
            attempt.error=attempt.error or {'empty_output':'Планувальник повернув порожню відповідь','output_limit':'Вичерпано ліміт відповіді'}.get(category,'Пропозицію не завершено')
            attempt.context['publication_failure']={**(terminal.failure if terminal else {}),'category':category,'message':attempt.error}
        if stage=='classify' and attempt.state=='failed' and not attempt.context.get('classification_failure'):
            attempt.context['classification_failure']={'category':'output_limit' if attempt.finish_reason=='length' else 'incomplete','message':attempt.error}
        return repo.save_attempt(attempt)
    try:
        if stage=='review_part':
            from ..review.wire import validate_part
            from ..impact.validation import decode_response
            attempt.context['review_result']=validate_part(decode_response(text),json.loads(context.fragments['review_plan']),attempt.context['review_spec'],json.loads(context.fragments['review_results']))
            attempt.state='completed'
            return repo.save_attempt(attempt)
        if stage=='impact_part':
            from ..impact.chunk_models import ChunkManifest
            from ..impact.chunk_validation import validate_part
            from ..impact.validation import decode_response
            run=repo.get_run(run_id);manifest=ChunkManifest.model_validate(run.impact['manifest'])
            task=attempt.context['impact_chunk_task']
            results={key:repo.get_attempt(value).context['impact_result'] for key,value in run.impact['proofs'].items()}
            parsed=validate_part(decode_response(text),manifest,task,results)
            attempt.context['impact_result']=parsed.model_dump();attempt.state='completed'
            return repo.save_attempt(attempt)
        if stage in {'impact_delta','impact_check'}:
            from ..impact.models import ImpactTarget
            from ..impact.validation import validate_delta,validate_check,decode_response
            target=ImpactTarget.model_validate_json(context.fragments['impact_target'])
            attempt.context['impact_target']=target.model_dump()
            result=(validate_delta if stage=='impact_delta' else validate_check)(decode_response(text),target)
            if stage=='impact_check' and result.memory_semantic_impact!='unchecked' and context.fragments.get('impact_memory_included')!='true':
                raise ValueError('Пам’ять не була передана для перевірки')
            attempt.context['impact_result']=result.model_dump()
            attempt.state='completed'
            return repo.save_attempt(attempt)
        if stage=='rewrite':
            from .assisted_writing import save_rewrite_result
            return save_rewrite_result(repo,attempt,context,text)
        proposed=False
        if stage=='publication_suggest':
            from ..publication_suggestions import parse_suggestions, fingerprint
            proposal={'source_stamp':json.loads(context.fragments['publication_sources']),
                'eligible_fields':json.loads(context.fragments['publication_eligible'])}
            attempt.context['publication_warnings']=[]
            proposal['suggestions']=parse_suggestions(text,proposal['eligible_fields'],attempt.context['publication_warnings'])
            proposal['fingerprint']=fingerprint(proposal)
            attempt.context['publication_proposal']=proposal
            attempt.state='completed'
            return repo.save_attempt(attempt)
        elif stage=='classify':
            from .edit_classification import parse_classification,text_refusal
            try:
                result=parse_classification(text,int(context.fragments['classification_count']))
            except ValueError:
                if text_refusal(text):
                    attempt.context['classification_refusal']=True
                    raise ValueError('Класифікатор відмовився; ця модель більше не використовуватиметься для класифікації цього оповідання')
                raise
            attempt.context['classification_result']=result.model_dump()
            attempt.state='completed'
            return repo.save_attempt(attempt)
        elif stage=='brief':
            from .planner_output import parse_planner_output
            attempt.context['planner_warnings']=[]
            brief,text=parse_planner_output(text,stage,attempt.context['planner_warnings'])
            proposed=bool(brief.proposed_changes)
            if brief.introduced:
                try:
                    from ..characters.acquaintance import protagonist,unexpected_introduced
                    from ..characters.models import load_characters
                    view=repo.context_view(context.story_id) if hasattr(repo,'context_view') else repo
                    scene=view.get_scene(scene_id)
                    story=view.get_story(context.story_id)
                    cards=load_characters(view.read_text(story.characters_version_id)) if story.characters_version_id else []
                    hero=protagonist(cards,view.list_scenes(story.id))[0] if cards else None
                    if unexpected_introduced(scene,hero,brief.introduced):
                        attempt.context['planner_warnings'].append('Планувальник: introduced містить ID поза складом сцени або головного героя; їх не враховано.')
                except Exception:
                    pass  # попередження допоміжне: збій не має провалювати оплачений brief
        elif stage=='prepare':
            from .planner_output import parse_planner_output
            attempt.context['planner_warnings']=[]
            _,text=parse_planner_output(text,stage,attempt.context['planner_warnings'])
        elif stage=='memory':
            scene=repo.get_scene(scene_id)
            previous = (
                load_memory(context.fragments['previous_memory'])
                if 'previous_memory' in context.fragments
                else journal_before(repo, scene_id)
            )
            sources={id:repo.read_text(id) for id in previous.source_prose_ids}
            # Validate against the exact source passed in this attempt, not a concurrent replacement.
            expected = [
                id for id in context.input_refs
                if repo.get_version(id).scene_id == scene_id
                and repo.get_version(id).kind in {'edited', 'manual'}
            ]
            if len(expected)!=1:
                raise ValueError('Немає єдиного зафіксованого джерела прози')
            prose_id=expected[0]
            sources[prose_id]=repo.read_text(prose_id)
            memory_warnings=[]
            attempt.context['memory_warnings']=memory_warnings
            snapshot=parse_memory_result(text,previous,prose_id,sources[prose_id],context.settings.memory_mode,
                json.loads(context.fragments.get('memory_allowed_character_ids','[]')),warnings=memory_warnings,
                # Attempts captured before wire v3 have no key and keep the v2 parser.
                wire_version=int(context.fragments.get('memory_wire_version','2')))
            validate_memory_journal(snapshot,sources,previous)
            text=snapshot.model_dump_json()
        elif stage=='edit' and context.settings.edit_mode=='prose' and context.fragments.get('edit_loop_run_id'):
            from ..rewrite_diff import build_rewrite_diff
            from .editor_loop import save_pass_result
            original=repo.read_text(context.fragments['copyedit_draft_id'])
            build_rewrite_diff(original,text)
            return save_pass_result(repo,attempt,context,original,text)
        elif stage=='edit' and context.settings.edit_mode=='diff':
            from ..rewrite_diff import build_rewrite_diff, rewrite_warnings
            draft_id=context.fragments['copyedit_draft_id']
            original=repo.read_text(draft_id)
            proposal=build_rewrite_diff(original,text)
            if context.fragments.get('edit_loop_run_id'):
                from .editor_loop import save_pass_result
                return save_pass_result(repo,attempt,context,original,text)
            from ..copyediting import require_editor_changes
            require_editor_changes(original,text)
            attempt.context['copyedit_proposal']={'protocol_version':2,'draft_id':draft_id,'proposal':proposal.model_dump()}
            attempt.context['editor_warnings']=rewrite_warnings(original,text,proposal.edits)
            attempt.state='needs_review'
            attempt.error='Перегляньте зміни редактора та явно прийміть вибір. Поточну прозу не змінено.'
            return repo.save_attempt(attempt)
        elif stage=='edit' and context.settings.edit_mode=='patches':
            from .copyediting import apply_copyedits
            draft_id=context.fragments['copyedit_draft_id']
            from .editor_output import parse_editor_output
            editor_warnings=[]
            attempt.context['editor_warnings']=editor_warnings
            proposal,_=parse_editor_output(text,editor_warnings)
            original=repo.read_text(draft_id)
            text=apply_copyedits(original,proposal)
            if context.fragments.get('edit_loop_run_id'):
                from .editor_loop import save_pass_result
                return save_pass_result(repo,attempt,context,original,text)
            from ..copyediting import require_editor_changes
            require_editor_changes(original,text)
            attempt.context['copyedit_proposal']={'protocol_version':1,'draft_id':draft_id,'proposal':proposal.model_dump()}
            from .language import language_warnings
            attempt.context['language_warnings']=language_warnings(text)
            if context.settings.edit_review=='review':
                attempt.state='needs_review'
                attempt.error='Оберіть точкові правки в панелі «Правки редактора» та застосуйте вибір. Поточну прозу не змінено.'
                return repo.save_attempt(attempt)
        if stage=='edit' and 'language_warnings' not in attempt.context:
            from .language import language_warnings
            attempt.context['language_warnings']=language_warnings(text)
        kind={'prepare':'canon','brief':'brief','draft':'draft','edit':'edited','memory':'memory'}[stage]
        ref=repo.save_version(
            context.story_id,
            scene_id,
            kind,
            text,
            context.input_refs,
            run_id,
            dependency_snapshot=context.dependency_snapshot,
            content_format=context.fragments.get('output_content_format','plain') if stage in {'draft','edit'} else 'plain'
        )
        attempt.result_version_id=ref.id
        if proposed:
            attempt.state='needs_review'
            attempt.error='Суттєві зміни потребують рішення автора'
            return repo.save_attempt(attempt)
        repo.save_attempt(attempt)
        return repo.commit_stage_result(attempt.id,ref,context.scene_revision)
    except ValueError as exc:
        attempt.state='failed'
        if stage in {'impact_delta','impact_check','impact_part','review_part'}:
            from ..impact.validation import refusal_body
            from pydantic import ValidationError
            detail=str(exc) if stage in {'impact_part','review_part'} and not isinstance(exc,ValidationError) else 'Результат перевірки впливу не відповідає схемі, покриттю або дослівним цитатам'
            failure=refusal_body(text) or {'category':'protocol','message':detail}
            attempt.error=failure['message'];attempt.context['impact_failure']=failure
        elif stage=='rewrite':
            attempt.error=str(exc)
            attempt.context['rewrite_failure']={'category':'protocol','message':str(exc)}
        elif stage=='publication_suggest':
            from ..publication_suggestions import text_refusal
            failure=text_refusal(text) or {'category':'protocol','message':str(exc)}
            attempt.error=failure['message']
            attempt.context['publication_failure']=failure
        elif stage=='classify':
            attempt.error=str(exc) # Only trusted parse_classification messages reach this branch.
            attempt.context['classification_failure']={'category':'refusal_unknown' if attempt.context.get('classification_refusal') else 'protocol','message':attempt.error}
        elif stage=='memory':
            from ..memory.diagnostics import memory_error
            from ..memory.violations import MemoryViolations
            if isinstance(exc,MemoryViolations):attempt.context['memory_violations']=exc.payload()
            attempt.error='Помилка пам’яті: '+memory_error(exc)+'. Оригінальну відповідь збережено; автоматичного повтору немає.'
        elif stage=='edit':
            from .editor_output import editor_failure
            failure=editor_failure(exc)
            attempt.context['editor_failure']=failure
            if context.fragments.get('edit_loop_run_id') and failure['category']!='publication':
                attempt.context['edit_loop_failure_origin']='model_response'
            attempt.error='Помилка редактора: '+failure['message']+'. Оригінальну відповідь збережено; автоматичного повтору немає.'
        elif stage in {'brief','prepare'}:
            from .planner_output import planner_failure
            failure=planner_failure(exc)
            attempt.context['planner_failure']=failure
            attempt.error='Помилка планувальника: '+failure['message']+'. Оригінальну відповідь збережено; автоматичного повтору немає.'
        else:
            attempt.error='Результат не відповідає схемі або правилам збереження. Перегляньте частковий текст.'
        return repo.save_attempt(attempt)
