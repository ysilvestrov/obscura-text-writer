"""Executor and context of the `character_extract` stage (CHARACTER-EXTRACT, R-51).

The stage reads a group of scenes with the role «Пам'ять» of the book: its provider, input limit and context size, the
fixed temperature of an extractor and an output limit of at least EXTRACT_MIN_OUTPUT_TOKENS, narrowed to what the context
leaves after the real request. A group that does not fit gives the reason to skip it, never a truncated request."""
import hashlib
import json
from collections.abc import Mapping

from ..characters.extract import SKIP_CONTEXT_LIMIT, SKIP_INPUT_LIMIT, ExtractState, SceneProse, catalogue_text
from ..providers.models import RoleSettings
from .context import ContextBundle

EXTRACT_TEMPERATURE = 0.2
EXTRACT_MIN_OUTPUT_TOKENS = 16000
NO_MEMORY_ROLE = "Налаштуйте роль «Пам'ять»: пошук персонажів читає прозу її моделлю"
RESERVE_FILLERS = {'uk': 'а', 'en': 'a'}  # the catalogue is in the language of the book: the estimator counts bytes
LABELS = {'uk': ('Каталог персонажів:', 'Сцени:'), 'en': ('Character catalogue:', 'Scenes:')}


def resolve_extractor(roles: Mapping[str, RoleSettings]) -> RoleSettings | None:
    """The memory role as an extractor; None while the book has no usable memory role."""
    role = roles.get('memory')
    if role is None or not role.provider.model.strip():
        return None
    # model_copy skips the role's output/context check: a small context is reported per group, not by an exception here.
    return role.model_copy(update={'temperature': EXTRACT_TEMPERATURE,
                                   'max_output_tokens': max(role.max_output_tokens, EXTRACT_MIN_OUTPUT_TOKENS)})


def _user_text(language: str, catalogue: str, group: list[SceneProse], short_by_scene: Mapping[str, str]) -> str:
    head, scenes = LABELS[language]
    parts = [head, catalogue, '', scenes]
    for scene in group:
        parts += [f'[{short_by_scene[scene.scene_id]}]', scene.text, '']
    return '\n'.join(parts).rstrip('\n')


def build_extract_context(repo, story_id: str, settings: RoleSettings, state: ExtractState, group: list[SceneProse],
                          scene_numbers: Mapping[str, str], card_numbers: Mapping[str, str],
                          reserve_chars: int | None = None) -> ContextBundle | str:
    """The request for one group, or the reason it does not fit the role's input limit or context.

    `scene_numbers` maps `s<N>` to scene ids and `card_numbers` maps `c<N>` to card refs (see `characters.extract.short_ids`;
    the catalogue text shows the same `c<N>`). With `reserve_chars` the catalogue is replaced by that many filler
    characters: the preview measures the fit with the catalogue reserve instead of a real catalogue."""
    from ..authoring.blueprints import get_role_settings
    from ..language import load_prompt
    from ..providers.requests import generation_request
    from ..token_budget.service import token_estimate
    story = repo.get_story(story_id)
    short_by_scene = {scene_id: short for short, scene_id in scene_numbers.items()}
    catalogue = RESERVE_FILLERS.get(story.language, 'a') * reserve_chars if reserve_chars is not None else catalogue_text(state, story.language)
    system = load_prompt('character_extract_v1', story.language)
    user = _user_text(story.language, catalogue, group, short_by_scene)
    body = generation_request('character_extract', settings, system, user, {})
    if len(json.dumps(body, ensure_ascii=False, separators=(',', ':'))) > settings.max_input_chars:
        return SKIP_INPUT_LIMIT
    prediction = token_estimate(repo, settings.provider.provider, settings.provider.base_url, body)
    room = settings.context_tokens - prediction['input_tokens']
    memory = get_role_settings(repo, story_id).get('memory')
    if room < (memory.max_output_tokens if memory is not None else settings.max_output_tokens):
        return SKIP_CONTEXT_LIMIT
    narrowed = settings.model_copy(update={'max_output_tokens': min(settings.max_output_tokens, room)})
    body = generation_request('character_extract', narrowed, system, user, {})
    refs = list(dict.fromkeys(scene.version_id for scene in group))
    fingerprint = hashlib.sha256(json.dumps({'request': body, 'refs': refs}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return ContextBundle(story_id=story.id, scene_id=group[0].scene_id, stage='character_extract', scene_revision=None,
                         story_revision=story.revision, settings=narrowed, system_text=system, user_text=user, input_refs=refs,
                         fingerprint=fingerprint, estimated_tokens=prediction['input_tokens'], estimate_method=prediction['method'],
                         api_request=body, token_estimate=prediction, policy_role='memory',
                         fragments={'extract_scene_ids': json.dumps([scene.scene_id for scene in group])})
