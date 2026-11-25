"""CHARACTER-EXTRACT (R-51): the run preview — groups, calls bound, cost and the plan fingerprint (spec 3.1, 3.6).

Read-only: nothing is written and no model is called. The same plan is the readiness of a `character_extract` run."""
import hashlib
import json

from ..authoring.blueprints import get_role_settings
from ..storage.link_records import PROSE_KINDS
from .acquaintance import is_protagonist_line
from .extract import ExtractState, SceneProse, plan_groups, short_ids

DEFAULT_GROUP_WORDS = 5000
CATALOGUE_RESERVE_CAP = 4000  # chars; catalogue_reserve = min(5 % of max_input_chars, 4000)
EXTRACT_PLAN_CHANGED = 'План змінився; перегляньте знову'
EXTRACT_RUNNING = 'Пошук персонажів уже виконується'
NO_PROSE = 'Немає сцен із завершеною прозою: пошуку персонажів нічого читати'
NO_BUDGET_LIMIT = 'Спершу задайте явний ліміт бюджету в налаштуваннях'
PENDING_PROPOSAL = 'Є неприйнята пропозиція персонажів: новий пошук зробить її неприйнятною'
NO_FINISHED_PROSE = 'немає завершеної прози'
UNREADABLE_PROSE = 'не вдалося прочитати прозу сцени'


def _pending_proposal(repo, story_id: str) -> bool:
    """The latest `character_extract` run of the book left a proposal (Task 5 checkpoint) that is not accepted yet."""
    runs = [run for run in repo.list_runs(story_id) if run.request.mode == 'character_extract']
    if not runs:
        return False
    checkpoint = runs[-1].checkpoint or {}
    return checkpoint.get('phase') == 'done' and not checkpoint.get('accepted_at')


def _tariff(repo, settings):
    from ..generation.audit_cost import CLOUD, current_tariff
    if settings.provider.provider not in CLOUD:
        return None
    tariff, reason = current_tariff(repo, settings)
    if tariff is None:
        return reason
    return {'input_per_million': str(tariff.input_per_million), 'output_per_million': str(tariff.output_per_million),
            'request_usd': str(tariff.request_usd), 'kind': tariff.kind, 'source': tariff.source}


def _has_author_protagonist(cards) -> bool:
    return any(is_protagonist_line(line) for card in cards for entry in card.entries for line in entry.text.splitlines())


def extract_plan(repo, story_id: str, group_words: int = DEFAULT_GROUP_WORDS, view=None) -> dict:
    from ..generation.audit_cost import CLOUD, upper_bound
    from ..generation.extract_context import NO_MEMORY_ROLE, build_extract_context, resolve_extractor
    from ..storage.scene_cast import view_cards
    story = repo.get_story(story_id)
    view = view if view is not None else repo.context_view(story_id)
    settings = get_role_settings(repo, story_id)
    extractor = resolve_extractor(settings)
    result = {'ready': False, 'reason': None, 'groups': [], 'scenes_count': 0, 'skipped': [], 'calls_bound': 0,
              'cost': {'per_call_usd': None, 'total_usd': None, 'reason': None}, 'cards_count': 0,
              'has_protagonist': False, 'pending_proposal': _pending_proposal(repo, story_id), 'plan_fingerprint': None}
    if extractor is None:
        result['reason'] = NO_MEMORY_ROLE
        return result
    try:
        cards = view_cards(view)
    except (ValueError, KeyError, OSError):  # unreadable cards: no catalogue, the run itself names the problem
        cards = []
    result.update(cards_count=len(cards), has_protagonist=_has_author_protagonist(cards))
    scenes = sorted((s for s in view.list_scenes(story_id) if not s.trashed_at), key=lambda s: s.position)
    prose, skipped = [], []
    for scene in scenes:
        prose_id = scene.heads.get('prose')
        ref = view.peek_version(prose_id) if prose_id else None
        if ref is None or not ref.complete or ref.kind not in PROSE_KINDS:
            skipped.append((scene.id, NO_FINISHED_PROSE))  # spec 3.1: the preview lists scenes without prose
            continue
        try:
            prose.append(SceneProse(scene.id, ref.id, view.read_text(ref.id)))
        except (ValueError, KeyError, OSError):
            skipped.append((scene.id, UNREADABLE_PROSE))
    by_id = {item.scene_id: item for item in prose}
    state = ExtractState(scene_order=[item.scene_id for item in prose])
    reserve = min(int(0.05 * extractor.max_input_chars), CATALOGUE_RESERVE_CAP)

    why = {}  # a single scene that does not fit: input limit or context, as build_extract_context names it

    def fits(ids: list[str]) -> bool:
        group = [by_id[scene_id] for scene_id in ids]
        card_numbers, scene_numbers = short_ids(state, ids)
        built = build_extract_context(repo, story_id, extractor, state, group, scene_numbers, card_numbers, reserve_chars=reserve)
        if isinstance(built, str) and len(ids) == 1:
            why[ids[0]] = built
        return not isinstance(built, str)

    groups, unfit = plan_groups([(item.scene_id, len(item.text.split()), len(item.text)) for item in prose],
                                group_words, fits)
    unfit = [(scene_id, why.get(scene_id, reason)) for scene_id, reason in unfit]
    skipped += unfit
    reading = sum(len(group) for group in groups)
    result.update(groups=groups, scenes_count=reading,
                  skipped=[{'scene_id': scene_id, 'reason': reason} for scene_id, reason in skipped],
                  calls_bound=2 * len(groups) + 2)
    result['cost'] = upper_bound(repo, extractor, result['calls_bound']) if groups else result['cost']
    limit = repo.billing('summary', scope='story:' + story.id)['limit_nanos']
    if not groups:
        result['reason'] = unfit[0][1] if unfit else NO_PROSE
    elif extractor.provider.provider in CLOUD and limit is None:
        result['reason'] = NO_BUDGET_LIMIT
    result['ready'] = result['reason'] is None
    payload = {'group_words': group_words, 'groups': groups, 'skipped': result['skipped'],
               'prose': {item.scene_id: view.peek_version(item.version_id).sha256 for item in prose},
               'cards': view.get_story(story_id).characters_version_id,
               'executor': {'provider': extractor.provider.provider, 'model': extractor.provider.model,
                            'base_url': extractor.provider.base_url, 'max_input_chars': extractor.max_input_chars,
                            'max_output_tokens': extractor.max_output_tokens, 'context_tokens': extractor.context_tokens},
               'tariff': _tariff(repo, extractor), 'budget_limit_nanos': limit, 'calls_bound': result['calls_bound'],
               'cost': result['cost']}
    result['plan_fingerprint'] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'), default=str).encode('utf-8')).hexdigest()
    return result


def readiness(repo, request, view=None) -> dict:
    """The readiness shape of the queue (`generation.readiness.preview`) over the extraction plan."""
    plan = extract_plan(repo, request.story_id, request.group_words or DEFAULT_GROUP_WORDS, view)
    role = get_role_settings(repo, request.story_id).get('memory')
    roles = {'memory': role.provider.model_dump(include={'provider', 'model'})} if role is not None else {}
    warnings = [PENDING_PROPOSAL] if plan['pending_proposal'] else []
    return {**plan, 'roles': roles, 'calls': plan['calls_bound'], 'evaluator': None, 'warnings': warnings}
