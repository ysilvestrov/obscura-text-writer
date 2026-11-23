"""Context of one link check by the auditor role (VALID-LINKS, R-44 PR 3).

Built apart from build_context and tolerant of stale heads: the auditor checks exactly the material the author is asked
about, so a stale brief, prose or previous memory is read as it is. Structural problems (no previous memory where it is
required, a merge without its merged memory, foreign sources) and an input over the auditor's limits give
AuditUnavailable, never a call; the text is never truncated."""
import hashlib
import json
from dataclasses import dataclass, field

from ..storage.link_records import LinkName
from .audit_output import LINK_STAGE
from .context import ContextBundle

NOT_CONFIGURED = 'Роль не налаштовано: Ревізор'
MISSING_LINK = 'Зв’язок сцени ще не має обох компонентів'
FOREIGN_PREVIOUS = 'Пам’ять попередньої сцени незавершена або належить іншій сцені чи твору'
FOREIGN_SOURCE = 'Пам’ять попередньої сцени містить невідоме або стороннє джерело'
UNREADABLE = 'Матеріал перевірки не прочитано'
CUSTOM_PROMPT = 'Промпт ролі потребує оновлення: Ревізор'
OVERFLOW_CHARS = 'Вхід перевірки перевищує ліміт Ревізора: {chars} символів із {limit}'
OVERFLOW_TOKENS = 'Вхід перевірки перевищує ліміт Ревізора: приблизно {tokens} токенів із {limit}'
# Fields of a memory event that name versions (event_id is derived from them): left out, as in links.memory_digest.
VERSION_FIELDS = {'event_id', 'source_version_id', 'evidence_version_id'}


@dataclass(frozen=True)
class AuditUnavailable:
    """No call for this link: `reason` is the link_state reason (no_previous_memory, carry_pending, carry_failed,
    no_memory) or an explanation; `inputs` and `fingerprint` are those of the link at build time."""
    reason: str
    inputs: dict = field(default_factory=dict)
    fingerprint: str | None = None


class _Unavailable(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _previous_memory(view, story, scene, scenes):
    """P0 rendered for reading as the writer sees past memory, without freshness or needs_confirmation checks; None for
    a first scene without a series start. (text, memory_id)."""
    from ..memory.previous import previous_memory, read_previous_journal
    from .context import memory_projection
    before = previous_memory(view, scene, peek=True, require=False)
    if before.memory_id is None:
        return None, None  # link_state already reported a required P0 as unavailable
    ref = view.versions.get(before.memory_id)
    kind = 'series_start' if before.series_start else 'memory_merge' if before.merge_key else 'memory'
    if (ref is None or ref.story_id != story.id or ref.kind != kind or not ref.complete
            or (kind == 'memory' and ref.scene_id != before.ancestors[-1].id)):
        raise _Unavailable(FOREIGN_PREVIOUS)
    journal = read_previous_journal(view, before, peek=True)
    for source_id in journal.source_prose_ids:
        source = view.versions.get(source_id)
        if source is None or source.story_id != story.id:
            raise _Unavailable(FOREIGN_SOURCE)
    projection = memory_projection(view, story, scene, scenes, story.language, past=journal)[-1]
    return projection.text, before.memory_id


def _own_records(view, memory_id):
    from ..memory.journal import load_memory
    from ..storage.links import own_events
    journal = load_memory(view.read_text(memory_id))
    return [event.model_dump(mode='json', exclude=VERSION_FIELDS) for event in own_events(journal)]


def _reference(view, story, scene, scenes, refs):
    """Character cards of the scene and the canon, read as they are (no stale refusal, no participant validation)."""
    from ..characters.models import load_characters
    from ..characters.projection import project_characters
    from .context_labels import label
    parts = []
    if story.characters_version_id:
        projection = project_characters(load_characters(view.read_text(story.characters_version_id)), scenes, scene.id, story.language)
        refs.append(story.characters_version_id)
        if projection.text:
            parts.append(label('characters', story.language) + '\n' + projection.text)
    if story.canon_version_id:
        parts.append(label('canon', story.language) + '\n' + view.read_text(story.canon_version_id))
        refs.append(story.canon_version_id)
    return '\n\n'.join(parts)


def _system_text(view, story, settings, link, refs):
    from ..language import load_prompt
    from .auditor_settings import prompt_version_for
    custom = prompt_version_for(settings, LINK_STAGE[link])
    if not custom:
        return load_prompt(f'audit_{link}_v1', story.language)
    ref = view.versions.get(custom)
    if ref is None or ref.story_id != story.id or ref.kind != 'prompt' or not ref.complete:
        raise ValueError(CUSTOM_PROMPT)
    refs.append(custom)
    return view.read_text(custom)


def _inputs(view, story, scene, link, refs):
    heads = scene.heads
    scenes = view.list_scenes(story.id)
    payload = {}
    if link in {'brief', 'prose'}:
        previous_text, previous_id = _previous_memory(view, story, scene, scenes)
        if previous_id:
            refs.append(previous_id)
        if link == 'brief':
            if heads.get('plan'):
                refs.append(heads['plan'])
            payload['plan'] = view.read_text(heads['plan']) if heads.get('plan') else scene.beats
            payload['previous_memory'] = previous_text
            payload['brief'] = view.read_text(heads['brief'])
        else:
            payload['brief'] = view.read_text(heads['brief'])
            payload['previous_memory'] = previous_text
            payload['prose'] = view.read_text(heads['prose'])
        refs.append(heads['brief'])
    else:
        payload['prose'] = view.read_text(heads['prose'])
        payload['own_memory_records'] = _own_records(view, heads['memory'])
        refs.append(heads['memory'])
    if link != 'brief':
        refs.append(heads['prose'])
    payload['reference'] = _reference(view, story, scene, scenes, refs)
    return payload


def _invalidation_marker(view) -> str:
    records = getattr(view, 'link_invalidations', ())
    return str(view.link_order[records[-1].id]) if records else '0'


def build_audit_context(repo, scene_id: str, link: LinkName, *, view=None) -> ContextBundle | AuditUnavailable:
    from ..authoring.blueprints import get_role_settings
    from ..providers.requests import generation_request
    from ..rating.guard import enforce_edition_limit
    from ..storage.links import link_state
    from ..token_budget.service import token_estimate
    from .auditor_settings import resolve_auditor
    if link not in LINK_STAGE:
        raise ValueError('Невідомий зв’язок сцени')
    if view is None:
        view = repo.context_view(repo.get_scene(scene_id).story_id)
    state = link_state(view, scene_id, link)
    if state.status == 'missing':
        raise ValueError(MISSING_LINK)
    if state.status == 'unavailable':
        return AuditUnavailable(state.reason, dict(state.inputs), state.fingerprint)
    marker = _invalidation_marker(view)  # from the same view as the fingerprint
    story = view.get_story(view.story.id)
    scene = view.get_scene(scene_id)
    settings = resolve_auditor(get_role_settings(repo, story.id))
    if settings is None or not settings.provider.model.strip():
        raise ValueError(NOT_CONFIGURED)
    enforce_edition_limit(story, scene)
    stage = LINK_STAGE[link]
    refs = []
    try:
        payload = _inputs(view, story, scene, link, refs)
    except _Unavailable as exc:
        return AuditUnavailable(exc.reason, dict(state.inputs), state.fingerprint)
    except (KeyError, OSError):
        return AuditUnavailable(UNREADABLE, dict(state.inputs), state.fingerprint)
    except ValueError as exc:
        return AuditUnavailable(str(exc) or UNREADABLE, dict(state.inputs), state.fingerprint)
    system = _system_text(view, story, settings, link, refs)
    user = json.dumps(payload, ensure_ascii=False)
    body = generation_request(stage, settings, system, user, {})
    prediction = token_estimate(repo, settings.provider.provider, settings.provider.base_url, body)
    chars = len(json.dumps(body, ensure_ascii=False, separators=(',', ':')))
    budget = settings.context_tokens - settings.max_output_tokens
    if chars > settings.max_input_chars:
        return AuditUnavailable(OVERFLOW_CHARS.format(chars=chars, limit=settings.max_input_chars), dict(state.inputs), state.fingerprint)
    if prediction['input_tokens'] > budget:
        return AuditUnavailable(OVERFLOW_TOKENS.format(tokens=prediction['input_tokens'], limit=budget), dict(state.inputs), state.fingerprint)
    fingerprint = hashlib.sha256(json.dumps({'request': body, 'link': link, 'audit_fingerprint': state.fingerprint,
                                             'invalidation_marker': marker}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return ContextBundle(story_id=story.id, scene_id=scene.id, stage=stage, scene_revision=scene.revision, story_revision=story.revision,
                         settings=settings, system_text=system, user_text=user, input_refs=list(dict.fromkeys(refs)),
                         fingerprint=fingerprint, estimated_tokens=prediction['input_tokens'], estimate_method=prediction['method'],
                         api_request=body, token_estimate=prediction, policy_role='auditor',
                         fragments={'audit_link': link, 'audit_fingerprint': state.fingerprint, 'invalidation_marker': marker})
