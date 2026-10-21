import json
import threading

from ..domain import StageAttempt, new_id
from ..memory.journal import load_memory, parse_memory_result
from ..memory.service import journal_before, validate_memory_journal
from .models import StoryBlueprint, WritersBrief
from .stream_buffer import StreamBuffer


def execute_stage(repo,scene_id: str | None,stage: str,context,gateway,cancel: threading.Event,on_delta,run_id=None,task_cursor=None) -> StageAttempt:
    id=new_id()
    attempt=StageAttempt(id=id,run_id=run_id,story_id=context.story_id,scene_id=scene_id,stage=stage,context=context.model_dump(),partial_path=f'stories/{context.story_id}/runs/{id}/partial.txt')
    if task_cursor is not None:attempt.context['run_cursor']=task_cursor
    repo.save_attempt(attempt)  # Persist exact inputs before a model can receive anything.
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
        repo.save_attempt(attempt)
        raise
    text=''.join(parts)
    if terminal:
        attempt.usage=terminal.usage
        attempt.finish_reason=terminal.finish_reason
    if cancel.is_set() or (terminal and terminal.type=='cancelled'):
        attempt.state='cancelled'
    elif terminal is None or terminal.type!='terminal' or terminal.finish_reason!='stop' or not text.strip():
        attempt.state='failed'
        attempt.error=terminal.message if terminal else 'Потік не має підтвердженого завершення'
    if attempt.state!='running':
        return repo.save_attempt(attempt)
    try:
        proposed=False
        if stage=='brief':
            brief=WritersBrief.model_validate_json(text)
            proposed=bool(brief.proposed_changes)
        elif stage=='prepare':
            StoryBlueprint.model_validate_json(text)
        elif stage=='memory':
            scene=repo.get_scene(scene_id)
            previous=load_memory(context.fragments['previous_memory']) if 'previous_memory' in context.fragments else journal_before(repo,scene_id)
            sources={id:repo.read_text(id) for id in previous.source_prose_ids}
            # Validate against the exact source passed in this attempt, not a concurrent replacement.
            expected=[id for id in context.input_refs if repo.get_version(id).scene_id==scene_id and repo.get_version(id).kind in {'edited','manual'}]
            if len(expected)!=1:
                raise ValueError('Немає єдиного зафіксованого джерела прози')
            prose_id=expected[0]
            sources[prose_id]=repo.read_text(prose_id)
            snapshot=parse_memory_result(text,previous,prose_id,sources[prose_id],context.settings.memory_mode,
                json.loads(context.fragments.get('memory_allowed_character_ids','[]')))
            validate_memory_journal(snapshot,sources,previous)
            text=snapshot.model_dump_json()
        elif stage=='edit' and context.settings.edit_mode=='patches':
            from .copyediting import CopyEdits, apply_copyedits
            draft_id=context.fragments['copyedit_draft_id']
            text=apply_copyedits(repo.read_text(draft_id),CopyEdits.model_validate_json(text))
        kind={'prepare':'canon','brief':'brief','draft':'draft','edit':'edited','memory':'memory'}[stage]
        ref=repo.save_version(context.story_id,scene_id,kind,text,context.input_refs,run_id,dependency_snapshot=context.dependency_snapshot)
        attempt.result_version_id=ref.id
        if proposed:
            attempt.state='needs_review'
            attempt.error='Суттєві зміни потребують рішення автора'
            return repo.save_attempt(attempt)
        repo.save_attempt(attempt)
        return repo.commit_stage_result(attempt.id,ref,context.scene_revision)
    except ValueError:
        attempt.state='failed'
        attempt.error='Результат не відповідає схемі, джерелам або правилам збереження пам’яті. Перегляньте частковий текст.'
        return repo.save_attempt(attempt)
