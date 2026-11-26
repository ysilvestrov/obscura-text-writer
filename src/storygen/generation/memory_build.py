"""The memory-build preview (R-48 PR 2, design §5): where `rebuild_memory` starts in a book whose scenes have prose and
no memory, an upper bound on its cost in USD, the scenes whose memory request will not fit, the plan fingerprint the run
compares, and whether a series book should first refresh its start memory from the previous book.

Read-only: priced from the stored tariff only (as `audit_cost`), never refusing the run on an unknown price."""
import hashlib
import json
import threading

from .audit_cost import CHARS_TO_TOKENS, CLOUD, INPUT_OVERHEAD, NO_PRICE, current_tariff, usd

# The previous memory is bounded by the same share of the role's input that `memory_fits` reserves for it.
MEMORY_PLAN_CHANGED = 'План побудови пам’яті змінився. Перегляньте його ще раз'
MEMORY_BUILD_RUNNING = 'Побудова пам’яті цього твору вже в черзі або виконується: дочекайтеся її чи скасуйте в панелі запусків'
MEMORY_BUILD_RESUME_BLOCKED = 'Інша побудова пам’яті цього твору вже в черзі або виконується: дочекайтеся її чи скасуйте, перш ніж продовжувати цю'


def memory_build_target(view, proposal=None) -> tuple[str | None, int]:
    """The first active scene, by position, without valid memory (design §5, §5.1), and the number of scenes from it to the
    end of the book — the scenes `rebuild_memory` from it covers. Memory is not valid when there is no memory head, when
    the head is stale (the stored flag), when the cast recorded in its dependency snapshot differs from the scene's cast
    (the stage's memory: `stale_scene_material` leaves snapshot versions to their selectors) or when the proposed cast
    (`scene_cast.propose_cast`, computed when not given; an unreadable cards file proposes nothing) changes the scene's
    cast. (None, 0) when every scene has valid memory. A scene without finished prose is still the target: the readiness
    of the run then names what is missing."""
    if proposal is None:
        from ..storage.scene_cast import propose_cast, view_cards
        try:
            proposal = propose_cast(view, view_cards(view))
        except (ValueError, KeyError, OSError):  # as readiness: unreadable cards give no proposal, not a failed preview
            proposal = {}
    scenes = sorted((s for s in view.list_scenes(view.story.id) if not s.trashed_at), key=lambda s: s.position)
    for index, scene in enumerate(scenes):
        memory_id = scene.heads.get('memory')
        if not memory_id or not _memory_valid(view, memory_id, scene) \
                or proposal.get(scene.id, scene.character_ids) != scene.character_ids:
            return scene.id, len(scenes) - index
    return None, 0


def finished_prose(view, scene) -> bool:
    """The scene has the prose a memory call reads: a complete prose head of kind `edited` or `manual` (as readiness of
    `rebuild_memory` requires for every target scene)."""
    prose_id = scene.heads.get('prose')
    prose = view.peek_version(prose_id) if prose_id else None
    return bool(prose and prose.complete and prose.kind in {'edited', 'manual'})


def memory_build_buildable(view, count: int) -> bool:
    """Whether the build of the last `count` active scenes can start as far as prose goes: every one of them has finished
    prose (owner, 25.11.2026: the menu item stays hidden until then). False when there is nothing to build."""
    scenes = sorted((s for s in view.list_scenes(view.story.id) if not s.trashed_at), key=lambda s: s.position)
    return count > 0 and all(finished_prose(view, scene) for scene in scenes[len(scenes) - count:])


def _memory_valid(view, memory_id, scene) -> bool:
    """The memory head was built for the scene as it is: not flagged stale and, with a snapshot, over the same cast.
    Freshness (inputs changed, link verdicts) is not consulted (coordinator, 25.11.2026: review M-3 reverted); such
    memory is rebuilt per scene."""
    ref = view.peek_version(memory_id)
    if ref.stale:
        return False
    snapshot = ref.dependency_snapshot
    return snapshot is None or all(
        selector.expected == scene.character_ids for selector in snapshot.selectors
        if selector.kind == 'scene' and selector.owner_id == scene.id and selector.field == 'character_ids')


# A placeholder of a version ID's length: the request names the prose version in its fragments label.
PROSE_ID_PLACEHOLDER = '0' * 32


def prose_memory_request(settings, prose: str, *, language: str = 'uk', system: str | None = None):
    """(system, user, fragments) of the memory request of a first scene with this prose and no tracked characters or places,
    composed from the pieces `context.build_context` uses for the memory stage (a test compares the two). `system`: the
    book's memory prompt (`stage_system_text`); the default prompt of the role otherwise."""
    from ..evidence import render_fragments
    from ..memory.journal import MemoryJournal
    from ..memory.projection import memory_catalog_v4
    from ..memory.wire_v4 import schema_bounds_v4
    from .context_labels import label
    from .prompts import role_prompt
    if system is None:
        system = role_prompt('memory', settings, language)
    past = MemoryJournal()
    parts = json.loads(memory_catalog_v4(past, [], {}, all_tracked=[]))
    dump = lambda value: json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    sections = [label('memory_core', language) + '\n' + dump({'names': parts['names'], 'core': parts['core']}),
                label('memory_threads', language) + '\n' + dump(parts['threads']),
                label('memory_claims', language) + '\n' + dump({'mutable': parts['mutable'], 'immutable': parts['immutable']}),
                label('allowed_ids', language) + '\n' + json.dumps([], ensure_ascii=False),
                label('prose_fragments', language, id=PROSE_ID_PLACEHOLDER) + '\n' + render_fragments(prose)]
    bounds = schema_bounds_v4(past, prose, [], [], {}, flashback=False)
    fragments = {'previous_memory': past.model_dump_json(), 'expected_source_prose_ids': json.dumps([PROSE_ID_PLACEHOLDER]),
                 'memory_allowed_character_ids': json.dumps([]), 'memory_wire_version': '4',
                 'memory_schema_bounds': json.dumps(bounds, ensure_ascii=False), 'memory_tracked': json.dumps([], ensure_ascii=False)}
    return system, '\n\n'.join(sections), fragments


def input_tokens(settings) -> int:
    """Input tokens priced for one memory request: the role's input limit (`max_input_chars · 4 + 256`, as the audit bound).
    The request carries the memory prompt (the book's own one included), the catalog of the previous memory and the prose;
    the prompt and the catalog have no smaller bound, and a request above `max_input_chars` is refused before any call
    (`ContextOverflow`), so this is the honest upper bound (cross-review P2: prose plus a reserve could price less)."""
    return settings.max_input_chars * CHARS_TO_TOKENS + INPUT_OVERHEAD


def memory_cost(repo, settings, prose_chars: list[int]) -> dict:
    """Upper bound in USD of one memory call per scene (`prose_chars` — the prose length of each; only their number decides
    the bound, see `input_tokens`), rounded up.
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
        prices = [tariff.price(input_tokens(settings), settings.max_output_tokens) for _ in prose_chars]
    except Exception:  # a broken stored row is an unknown price, not a refused preview
        result['reason'] = NO_PRICE
        return result
    result.update(per_call_usd=usd(max(prices)), total_usd=usd(sum(prices)))
    return result


# `memory_fits` measures the request of every scene, and the workspace asks readiness of every operation on each refresh:
# an answer is kept per (prose text, role, prompt, token profiles), so only changed scenes are measured again.
_FITS_CACHE: dict = {}
_FITS_CACHE_SIZE = 4096
_FITS_LOCK = threading.Lock()


def _remember(key, fit) -> None:
    with _FITS_LOCK:
        while len(_FITS_CACHE) >= _FITS_CACHE_SIZE:
            _FITS_CACHE.pop(next(iter(_FITS_CACHE)))
        _FITS_CACHE[key] = fit


def unfit_scenes(repo, view, settings, scene_ids) -> list[str]:
    """The scenes whose memory request would exceed the memory role's limits (`memory_fits`: characters and tokens, the
    book's own memory prompt); the run stops on them with the existing «Текст не обрізається» refusal. Scenes without
    prose are not listed."""
    from ..application.manuscript_import import memory_fits
    from .context import stage_system_text
    story = view.get_story(view.story.id)
    system = stage_system_text(repo, story, None, 'memory', settings, {}, [])
    try:
        profiles = json.dumps(repo.token_records('profile'), sort_keys=True, default=str)
    except Exception:  # no stored profiles to key on: measure without the cache
        profiles = None
    common = None if profiles is None else hashlib.sha256(
        json.dumps([settings.model_dump_json(), system, story.language, profiles]).encode('utf-8')).hexdigest()
    fits = None
    unfit = []
    for scene_id in scene_ids:
        prose_id = view.peek_scene(scene_id).heads.get('prose')
        if not prose_id:
            continue
        key = None if common is None else (view.peek_version(prose_id).sha256, common)
        fit = _FITS_CACHE.get(key) if key is not None else None
        if fit is None:
            fits = fits or memory_fits(repo, settings, language=story.language, system=system)
            fit = fits(view.read_text(prose_id))
            if key is not None:
                _remember(key, fit)
        if not fit:
            unfit.append(scene_id)
    return unfit


def plan_fingerprint(scene_id, targets, settings, cast=None, cost=None, repo=None) -> str:
    """sha256 of the plan the author saw: the start scene, each target scene with its prose head, the memory role fields
    that decide what the run costs and which scenes fit (model, endpoint, input, output and context limits), `cast` —
    every scene's cast with the proposal applied, and the cards it comes from (design §5.1) —, the shown `cost` (total, per
    call, reason) and the prices of the role's current tariff (cross-review P1: a price changed after the preview refuses
    the old fingerprint). That cast stays the same once `apply_cast` writes it, so the fingerprint the author saw still
    matches; new cards in between change it."""
    provider = settings.provider
    tariff = None
    if repo is not None and provider.provider in CLOUD:
        current, reason = current_tariff(repo, settings)
        tariff = reason if current is None else {
            'input_per_million': str(current.input_per_million), 'output_per_million': str(current.output_per_million),
            'request_usd': str(current.request_usd), 'kind': current.kind, 'source': current.source}
    shown = None if cost is None else {key: cost.get(key) for key in ('per_call_usd', 'total_usd', 'reason')}
    payload = {'scene_id': scene_id, 'scenes': [[scene.id, scene.heads.get('prose')] for scene in targets],
               'memory': {'provider': provider.provider, 'model': provider.model, 'base_url': provider.base_url,
                          'max_input_chars': settings.max_input_chars, 'max_output_tokens': settings.max_output_tokens,
                          'context_tokens': settings.context_tokens},
               'cast': cast, 'cost': shown, 'tariff': tariff}
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'), default=str)
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


# R-49 (MANUSCRIPT-IMPORT-S16): what the memory model receives, named by the sections of its request. A new labelled section of
# the memory request without a category here fails test_sends_cover_every_section_of_the_memory_request.
SECTION_CATEGORIES = {
    'current_prose': 'prose', 'prose_fragments': 'prose',
    'memory_core': 'memory_catalog', 'memory_threads': 'memory_catalog', 'memory_claims': 'memory_catalog',
    'day_changed': 'memory_catalog', 'allowed_ids': 'memory_catalog',
    'allowed_location_ids': 'places', 'bible_facts': 'series_facts',
}
_SEND_ORDER = ('memory_catalog', 'places', 'series_facts')


def request_sections(context) -> set[str]:
    """The label keys whose heading starts a paragraph of the request text (headings are in either language)."""
    from .context_labels import LABELS
    paragraphs = [part.lstrip() for part in (context.user_text or '').split('\n\n')]
    found = set()
    for key, texts in LABELS.items():
        for text in texts.values():
            head = text.split('{')[0].strip()
            if head and any(part.startswith(head) for part in paragraphs):
                found.add(key)
    # «ПОТОЧНА ПРОЗА» is also the start of the fragments heading: one prose section, not two.
    if 'prose_fragments' in found:
        found.discard('current_prose')
    return found


def is_local_provider(provider) -> bool:
    """Obscura sends the text only to an address on this computer; where that server sends it next is not Obscura's claim."""
    from urllib.parse import urlsplit
    return urlsplit(provider.base_url or '').hostname in {'localhost', '127.0.0.1', '::1'}


def memory_sends(repo, provider, targets, context) -> dict:
    found = {SECTION_CATEGORIES[key] for key in request_sections(context) if key in SECTION_CATEGORIES}
    words = sum(len(repo.read_text(target.heads['prose']).split()) for target in targets if target.heads.get('prose'))
    items = [{'key': 'prose', 'scenes': len(targets), 'words': words}] + [{'key': key} for key in _SEND_ORDER if key in found]
    return {'items': items, 'local': is_local_provider(provider)}
