"""CAS for author memory-kind marks (#60, MEMORY-SELECT-S08); no journal, prose or scene writes."""
from ..domain import RevisionConflict, Story
from .context_view import ContextView

MAX_MARKS=10000


def update_memory_kind(repo,story_id: str,claim_id: str,kind: str | None,expected_revision: int) -> Story:
    from ..memory.kinds import KINDS, find_claim, is_core_slot, tracked_ids
    if kind is not None and kind not in KINDS:raise ValueError('Невідомий тип запису пам’яті')
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        story=repo._active_story(db,story_id)
        if story.revision!=expected_revision:
            raise RevisionConflict('Твір уже змінено. Оновіть таблицю; тип запису не збережено.')
        marks=dict(story.memory_kind_overrides)
        if marks.get(claim_id)==kind:return story
        if kind is not None:
            view=ContextView(repo,db,story_id)
            event=find_claim(view,story_id,claim_id)
            if event is None:raise ValueError('Запису немає в пам’яті твору')
            if is_core_slot(event,tracked_ids(view,view.story)):raise ValueError('Слот ядра завжди показується; тип не змінюється')
            if claim_id not in marks and len(marks)>=MAX_MARKS:raise ValueError('Забагато позначок типу запису')
            marks[claim_id]=kind
        else:marks.pop(claim_id,None)
        story=story.model_copy(update={'memory_kind_overrides':marks,'revision':story.revision+1})
        repo._save_story(db,story)
        return story
