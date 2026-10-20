import json
import threading

from ..domain import StageAttempt, new_id
from ..memory.models import MemorySnapshot, MemoryDelta
from ..memory.service import memory_before, validate_memory, merge_memory_delta
from .models import StoryBlueprint, WritersBrief


def execute_stage(repo,scene_id: str | None,stage: str,context,gateway,cancel: threading.Event,on_delta,run_id=None,task_cursor=None) -> StageAttempt:
    id=new_id()
    attempt=StageAttempt(id=id,run_id=run_id,story_id=context.story_id,scene_id=scene_id,stage=stage,context=context.model_dump(),partial_path=f'stories/{context.story_id}/runs/{id}/partial.txt')
    if task_cursor is not None:attempt.context['run_cursor']=task_cursor
    repo.save_attempt(attempt)  # Persist exact inputs before a model can receive anything.
    repo.files.write(attempt.partial_path,b'')
    text=''
    terminal=None
    for event in gateway.stream(context,cancel):
        if event.type=='delta':
            text+=event.text
            repo.files.write(attempt.partial_path,text.encode('utf-8'))
            on_delta(event.text)
        else:
            terminal=event
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
            previous=MemorySnapshot.model_validate_json(context.fragments['previous_memory']) if 'previous_memory' in context.fragments else memory_before(repo,scene_id)
            sources={id:repo.read_text(id) for id in previous.source_prose_ids}
            prose_id=scene.heads['prose']
            # Validate against the exact source passed in this attempt, not a concurrent replacement.
            expected=[id for id in context.input_refs if repo.get_version(id).scene_id==scene_id and repo.get_version(id).kind in {'edited','manual'}]
            if expected!=[prose_id]:
                raise ValueError('Прозу змінено під час оновлення пам’яті')
            sources[prose_id]=repo.read_text(prose_id)
            if context.settings.memory_mode=='evidence_delta':
                snapshot=merge_memory_delta(previous,MemoryDelta.model_validate_json(text),prose_id,sources[prose_id])
                text=snapshot.model_dump_json()
            else:
                snapshot=MemorySnapshot.model_validate_json(text)
            validate_memory(snapshot,sources)
            for field in ('facts','character_states','open_threads','timeline'):
                retained={entry.model_dump_json() for entry in getattr(snapshot,field)}
                if any(entry.model_dump_json() not in retained for entry in getattr(previous,field)):
                    raise ValueError('Нова пам’ять втратила попередні підтверджені записи')
        elif stage=='edit' and context.settings.edit_mode=='patches':
            from .copyediting import CopyEdits, apply_copyedits
            draft_id=context.fragments['copyedit_draft_id']
            text=apply_copyedits(repo.read_text(draft_id),CopyEdits.model_validate_json(text))
        kind={'prepare':'canon','brief':'brief','draft':'draft','edit':'edited','memory':'memory'}[stage]
        ref=repo.save_version(context.story_id,scene_id,kind,text,context.input_refs,run_id)
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
