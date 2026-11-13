"""Model policy: consent for non-uncensored cloud models and the refusal block (MODEL-003, MODEL-004)."""
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlsplit
from .models import ProviderSettings
from ..rating.levels import AXES, effective_rating

POLICY_ROLES = ('planner', 'writer', 'editor', 'memory')
STAGE_POLICY_ROLE = {'prepare': 'planner', 'brief': 'planner', 'impact_delta': 'planner', 'impact_check': 'planner',
    'impact_part': 'planner', 'review_part': 'planner', 'publication_suggest': 'planner', 'timeline_summary': 'memory', 'draft': 'writer',
    'rewrite': 'writer', 'edit': 'editor', 'classify': 'editor', 'memory': 'memory'}
# Stages whose material spans several scenes: the request rating also counts the scenes behind `input_refs`.
MULTI_SCENE_STAGES = frozenset({'impact_delta', 'impact_check', 'impact_part', 'review_part', 'publication_suggest', 'timeline_summary'})
ROLE_LABELS = {'planner': 'Планувальник', 'writer': 'Письменник', 'editor': 'Редактор', 'memory': 'Пам’ять'}

CONSENT_REQUIRED = ('Модель «{model}» не має позначки Uncensored, а рейтинг цього запиту {rating}. '
    'Підтвердьте в налаштуваннях ролі «{role}», що погоджуєтеся на виклики цієї моделі для дорослого змісту, або виберіть іншу модель.')
REFUSAL_BLOCKED = ('Модель «{model}» уже відмовила ролі «{role}» через зміст на запиті з рейтингом {seen}. '
    'Виклики з рейтингом {rating} заблоковано: зніміть позначку в налаштуваннях ролі або виберіть іншу модель.')


class ModelPolicyBlocked(ValueError):
    def __init__(self, message: str, kind: Literal['consent', 'refusal']):
        super().__init__(message)
        self.kind = kind


def normalize_endpoint(base_url: str) -> str:
    parts = urlsplit(base_url)
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}{parts.path.rstrip('/')}"


def endpoint(settings: ProviderSettings) -> str:
    return normalize_endpoint(settings.base_url)


def is_local(settings: ProviderSettings) -> bool:
    return settings.provider == 'local' and urlsplit(settings.base_url or '').hostname in {'localhost', '127.0.0.1', '::1'}


def _max_rating(ratings) -> tuple[int, int, int]:
    return tuple(max([getattr(r, a) for r in ratings if r is not None], default=0) for a in AXES)


def request_rating(view, story, scene_ids: Iterable[str]) -> tuple[int, int, int]:
    ratings = [story.content_rating]
    for scene_id in scene_ids:
        try:
            scene = view.get_scene(scene_id)
        except KeyError:
            continue
        ratings.append(effective_rating(story, scene))
    return _max_rating(ratings)


def context_rating(repo, context) -> tuple[int, int, int]:
    """A scene stage rates the story and its own scene; a multi-scene stage also rates the scenes of `input_refs`."""
    story = repo.get_story(context.story_id)
    scene_ids = [context.scene_id] if context.scene_id else []
    refs = context.input_refs if getattr(context, 'stage', None) in MULTI_SCENE_STAGES else []
    for ref in refs:
        try:
            version = repo.get_version(ref)
        except KeyError:
            continue
        if version.scene_id:
            scene_ids.append(version.scene_id)

    class _View:
        @staticmethod
        def get_scene(scene_id):
            return repo.get_scene(scene_id)
    return request_rating(_View, story, scene_ids)


def needs_consent(settings: ProviderSettings, uncensored: bool | None, rating) -> bool:
    return not is_local(settings) and uncensored is not True and any(rating)


def blocking_refusal(refusals: list[dict], rating) -> dict | None:
    for entry in refusals:
        if all(a <= b for a, b in zip(entry['rating'], rating)):
            return entry
    return None


def _fmt(rating) -> str:
    return '/'.join(str(x) for x in rating)


def _args(role, settings):
    return dict(role=role, provider=settings.provider, base_url=endpoint(settings), model=settings.model)


def check_refusal(repo, role, settings, rating) -> None:
    stored = repo.model_policy('get_refusal', **_args(role, settings))
    entry = blocking_refusal(stored['refusals'], rating) if stored else None
    if entry:
        raise ModelPolicyBlocked(REFUSAL_BLOCKED.format(model=settings.model, role=ROLE_LABELS[role],
            seen=_fmt(entry['rating']), rating=_fmt(rating)), 'refusal')


def check_consent(repo, role, settings, rating, uncensored: bool | None) -> None:
    if not needs_consent(settings, uncensored, rating):
        return
    if repo.model_policy('get_consent', **_args(role, settings)) is None:
        raise ModelPolicyBlocked(CONSENT_REQUIRED.format(model=settings.model, rating=_fmt(rating),
            role=ROLE_LABELS[role]), 'consent')


def record_refusal(repo, role, settings, rating, *, story_id, scene_id, attempt_id, category) -> None:
    entry = {'rating': list(rating), 'at': datetime.now(timezone.utc).isoformat(), 'story_id': story_id,
        'scene_id': scene_id, 'attempt_id': attempt_id, 'category': category}
    repo.model_policy('add_refusal', entry=entry, **_args(role, settings))
