"""Deterministic plan selection, shared by prompts and dependency selectors."""

HORIZON_LIMIT_WARNING=('Горизонт обмежує окремі плани сцен. Канон, стиль, власні промпти та вже створений бриф/чернетка можуть містити події поза горизонтом; їхні тексти й залежності не змінюються приховано.')
MISSING_ENDING_WARNING='Авторський орієнтир фіналу не задано: доступний лише план поточної сцени.'


def horizon_future_count(settings):
    if settings.future_plan_mode=='all':
        return None
    return settings.future_plan_count if settings.future_plan_mode=='next_n' else 0


def selected_plan_scenes(scenes,scene,settings):
    future=[item for item in scenes if item.position>=scene.position and not item.trashed_at]
    count=horizon_future_count(settings)
    return future if count is None else future[:count+1]


def horizon_instructions(scene,total,language='uk'):
    from .generation.context_labels import label
    boundary=label('horizon_last' if scene.position==total-1 else 'horizon_not_last',language)
    return label('horizon',language)+boundary
