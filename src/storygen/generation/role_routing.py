"""MODEL-001: the single place that picks the writer's main model or its model for scenes rated 0–1."""
from ..providers.models import RoleSettings
from ..rating.levels import AXES, effective_rating

WRITER_STAGES = frozenset({'draft', 'rewrite'})
VARIANT_WRITER_ONLY = 'Окрема модель для сцен 0–1 доступна лише письменнику.'


def uses_low_rating_variant(settings: RoleSettings, story, scene) -> bool:
    """True when a variant is set and no axis of the scene's effective rating is 2; an unset rating keeps the main model (defensive: enforce_rating blocks generation before the story has a rating)."""
    if settings.low_rating_variant is None or scene is None:
        return False
    rating = effective_rating(story, scene)
    return rating is not None and all(getattr(rating, axis) < 2 for axis in AXES)


def settings_for(role_settings: RoleSettings, role: str, story, scene) -> RoleSettings:
    """The writer's settings for this scene. Routed settings carry no variant, so routing them again changes nothing."""
    if role != 'writer' or not uses_low_rating_variant(role_settings, story, scene):
        return role_settings
    variant = role_settings.low_rating_variant
    provider = variant.provider if variant.timeout is None else variant.provider.model_copy(update={'timeout': variant.timeout})
    return role_settings.model_copy(update={'provider': provider, 'context_tokens': variant.context_tokens,
        'max_output_tokens': variant.max_output_tokens, 'max_input_chars': variant.max_input_chars,
        'temperature': variant.temperature, 'low_rating_variant': None})
