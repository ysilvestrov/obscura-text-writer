"""MODEL-RETIREMENT: when the provider says it will remove a model, read straight from its catalog row."""
from datetime import date, datetime

from .models import ModelRetirement


def _day(value) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).date() if 'T' in value else date.fromisoformat(value)
    except ValueError:
        return None


def retirement_from(provider: str, row: dict) -> ModelRetirement | None:
    """Venice: model_spec.deprecation (removesAt, else date; replacementModelId). OpenRouter: expiration_date, no replacement."""
    if provider == 'venice':
        spec = row.get('model_spec')
        notice = spec.get('deprecation') if isinstance(spec, dict) else None
        if not isinstance(notice, dict):
            return None
        day = _day(notice.get('removesAt')) or _day(notice.get('date'))
        replacement = notice.get('replacementModelId')
        return ModelRetirement(date=day, replacement=replacement if isinstance(replacement, str) and replacement else None) if day else None
    if provider == 'openrouter':
        day = _day(row.get('expiration_date'))
        return ModelRetirement(date=day, replacement=None) if day else None
    return None


def retirement_warning(model: str, retirement: ModelRetirement) -> str:
    when = retirement.date.strftime('%d.%m.%Y')
    instead = f'; заміна: «{retirement.replacement}»' if retirement.replacement else ''
    return f'Провайдер прибирає модель «{model}» {when}{instead}. Змініть модель у налаштуваннях ролі.'
