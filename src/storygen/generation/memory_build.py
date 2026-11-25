"""The memory-build preview (R-48 PR 2, design §5): where `rebuild_memory` starts in a book whose scenes have prose and
no memory, an upper bound on its cost in USD, the scenes whose memory request will not fit, the plan fingerprint the run
compares, and whether a series book should first refresh its start memory from the previous book.

Read-only: priced from the stored tariff only (as `audit_cost`), never refusing the run on an unknown price."""
import hashlib
import json

from .audit_cost import CHARS_TO_TOKENS, CLOUD, INPUT_OVERHEAD, NO_PRICE, current_tariff, usd

PROSE_KINDS = frozenset({'manual', 'edited'})
# The previous memory is bounded by the same share of the role's input that `memory_fits` reserves for it.
PREVIOUS_MEMORY_SHARE = 8
MEMORY_PLAN_CHANGED = 'План побудови пам’яті змінився. Перегляньте його ще раз'


def _has_finished_prose(view, scene) -> bool:
    prose_id = scene.heads.get('prose')
    if not prose_id:
        return False
    prose = view.peek_version(prose_id)
    return bool(prose.complete) and prose.kind in PROSE_KINDS


def memory_build_target(view) -> tuple[str | None, int]:
    """The first scene, by position, with finished author prose (`manual`/`edited`) and no memory head, and the number of
    scenes from it to the end of the book — the scenes `rebuild_memory` from it covers. (None, 0) when there is none."""
    scenes = sorted(view.list_scenes(view.story.id), key=lambda s: s.position)
    for index, scene in enumerate(scenes):
        if not scene.heads.get('memory') and _has_finished_prose(view, scene):
            return scene.id, len(scenes) - index
    return None, 0


def input_tokens(settings, chars: int) -> int:
    """Input tokens of one memory request: the prose plus the previous memory bound, capped by the role's input limit."""
    return min(settings.max_input_chars, chars + settings.max_input_chars // PREVIOUS_MEMORY_SHARE) * CHARS_TO_TOKENS \
        + INPUT_OVERHEAD


def memory_cost(repo, settings, prose_chars: list[int]) -> dict:
    """Upper bound in USD of one memory call per scene (`prose_chars` — the prose length of each), rounded up.
    No USD for a local model; an unknown or stale cloud price leaves the totals None with the reason."""
    result = {'per_call_usd': None, 'total_usd': None, 'calls': len(prose_chars), 'reason': None}
    if settings is None or settings.provider.provider not in CLOUD:
        return result
    if not prose_chars:
        result['total_usd'] = usd(0)
        return result
    tariff, reason = current_tariff(repo, settings)
    if tariff is None:
        result['reason'] = reason
        return result
    try:
        prices = [tariff.price(input_tokens(settings, chars), settings.max_output_tokens) for chars in prose_chars]
    except Exception:  # a broken stored row is an unknown price, not a refused preview
        result['reason'] = NO_PRICE
        return result
    result.update(per_call_usd=usd(max(prices)), total_usd=usd(sum(prices)))
    return result


def unfit_scenes(repo, view, settings, scene_ids) -> list[str]:
    """The scenes whose memory request would exceed the memory role's limits (`memory_fits`: characters and tokens);
    the run stops on them with the existing «Текст не обрізається» refusal. Scenes without prose are not listed."""
    from ..application.manuscript_import import memory_fits
    fits = memory_fits(repo, settings)
    unfit = []
    for scene_id in scene_ids:
        prose_id = view.peek_scene(scene_id).heads.get('prose')
        if prose_id and not fits(view.read_text(prose_id)):
            unfit.append(scene_id)
    return unfit


def plan_fingerprint(scene_id, targets, settings) -> str:
    """sha256 of the plan the author saw: the start scene, each target scene with its prose head, and the memory model."""
    provider = settings.provider
    payload = {'scene_id': scene_id, 'scenes': [[scene.id, scene.heads.get('prose')] for scene in targets],
               'memory': {'provider': provider.provider, 'model': provider.model, 'base_url': provider.base_url}}
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def series_refresh(repo, story) -> bool:
    """A series book without a start snapshot whose previous book is finished: offer «Оновити з попередньої книги» first."""
    if not story.series_id or story.series_start_version_id:
        return False
    from ..book.series import series_status
    try:
        status = series_status(repo, story)
    except (ValueError, KeyError, OSError):  # an unreadable source is no hint, not a refused preview
        return False
    return status is not None and status.state == 'source_finished'
