"""CAS for author forwarding choices; no journal or prose writes."""
from ..domain import RevisionConflict
from .context_view import ContextView
from ..memory.forwarding import memory_view_from_view


def save_forwarding(repo,scene_id,body):
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        scene=repo._active_scene(db,scene_id)
        view=ContextView(repo,db,scene.story_id)
        current=memory_view_from_view(view,scene_id)
        if scene.revision!=body.expected_revision or current['fingerprint']!=body.fingerprint:
            raise RevisionConflict('Пам’ять або вибір попередніх сцен змінилися. Оновіть таблицю; ваш вибір не збережено.')
        if not current['can_save']:raise ValueError(current['reason'])
        if set(body.choices)-{row['claim_id'] for row in current['rows']}:
            raise ValueError('Вибір містить записи поза поточною пам’яттю сцени')
        updated={**scene.memory_forwarding,**body.choices}
        if updated!=scene.memory_forwarding:
            scene.memory_forwarding=updated;scene.revision+=1
            repo._save_scene(db,scene);repo._touch_story(db,scene.story_id)
        return memory_view_from_view(ContextView(repo,db,scene.story_id),scene_id)
