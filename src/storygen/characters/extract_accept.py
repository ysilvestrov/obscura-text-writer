"""CHARACTER-EXTRACT (R-51): the current proposal of a book and its acceptance item by item (spec 4.2, 4.3).

Plan amendment: the proposal lives in `Run.checkpoint['proposal']` of the finished `character_extract` run and is named by
`run_id`; the accept marks it with `Run.checkpoint['accepted_at']`. One write transaction holds the new version of the
cards (`save_cards_in_transaction`, CAS on the story revision read in it), the casts (`apply_cast_in_transaction`, mode
`add`) and the mark, so an accept is all or nothing. A dry run is the same transaction rolled back."""
from pydantic import Field

from ..domain import DomainModel, RevisionConflict, now
from ..scene_description import name_key
from .extract_plan import PROPOSAL_SUPERSEDED, _has_author_protagonist

STAGE = 'character_extract'
FINISHED = frozenset({'completed', 'cancelled'})

PROPOSAL_NOT_FOUND = 'Пропозицію персонажів не знайдено'
PROPOSAL_NOT_READY = 'Пропозиція персонажів ще не готова'
PROPOSAL_ACCEPTED = 'Пропозицію персонажів уже прийнято'
PROPOSAL_CHANGED = 'Пропозиція змінилася; перегляньте її знову'
NO_PROPOSAL = 'Немає неприйнятої пропозиції персонажів'

SKIP_NAME_TAKEN = 'картка з таким іменем уже є'
SKIP_NAME_OTHER_CARD = "ім'я вже має інша картка"
SKIP_CARD_GONE = 'картки вже немає'
SKIP_NO_NEW_NAMES = 'картка вже має ці імена'
SKIP_PROTAGONIST_MARKED = 'позначку героя вже має картка'
SKIP_PROTAGONIST_NOT_ACCEPTED = 'картку героя не прийнято'
SKIP_SCENE_TRASHED = 'сцену вилучено'
SKIP_PROSE_CHANGED = 'проза сцени змінилася'
SKIP_PLANNED = 'план сцени називає учасників'
SKIP_NOT_AUTHOR_PROSE = 'проза сцени не авторська'
SKIP_NOTHING_TO_ADD = 'немає кого додати до складу'

# The marker lines the readers of cards recognise (characters.acquaintance.PROTAGONIST, characters.names.OTHER_NAMES).
MARKERS = {'uk': {'quote': '«{}»', 'other_names': "Інше ім'я: {}", 'protagonist': 'Головний герой'},
           'en': {'quote': '“{}”', 'other_names': 'Other names: {}', 'protagonist': 'Main character'}}


class CardChoice(DomainModel):
    key: str = Field(min_length=1)
    names: list[str] = Field(default_factory=list)


class NameUpdateChoice(DomainModel):
    card_id: str = Field(min_length=1)
    names: list[str] = Field(default_factory=list)


class AcceptRequest(DomainModel):
    run_id: str = Field(min_length=1)
    fingerprint: str = Field(min_length=1)
    cards: list[CardChoice] = Field(default_factory=list)
    name_updates: list[NameUpdateChoice] = Field(default_factory=list)
    protagonist: bool = False
    casts: list[str] = Field(default_factory=list)
    dry_run: bool = False


def _current_run(runs):
    """The latest `character_extract` run of the book while its proposal can be accepted: finished (completed or
    cancelled), phase `done`, not accepted. Any newer `character_extract` run, in any state, supersedes it."""
    runs = [run for run in runs if run.request.mode == STAGE]
    if not runs:
        return None
    run, checkpoint = runs[-1], runs[-1].checkpoint or {}
    ready = checkpoint.get('phase') == 'done' and isinstance(checkpoint.get('proposal'), dict)
    return run if run.state in FINISHED and ready and not checkpoint.get('accepted_at') else None


def current_proposal(repo, story_id: str) -> dict | None:
    run = _current_run(repo.list_runs(story_id))
    return None if run is None else {'run_id': run.id, 'state': run.state, 'proposal': run.checkpoint['proposal']}


def _proposal_run(runs, request):
    """The run of the request, checked inside the accept transaction (spec 4.3: otherwise 409)."""
    run = next((run for run in runs if run.id == request.run_id and run.request.mode == STAGE), None)
    if run is None:
        raise RevisionConflict(PROPOSAL_NOT_FOUND)
    checkpoint = run.checkpoint or {}
    if checkpoint.get('accepted_at'):
        raise RevisionConflict(PROPOSAL_ACCEPTED)
    if run.state not in FINISHED or checkpoint.get('phase') != 'done' or not isinstance(checkpoint.get('proposal'), dict):
        raise RevisionConflict(PROPOSAL_NOT_READY)
    current = _current_run(runs)
    if current is None or current.id != run.id:
        raise RevisionConflict(PROPOSAL_SUPERSEDED)
    if checkpoint['proposal']['fingerprint'] != request.fingerprint:
        raise RevisionConflict(PROPOSAL_CHANGED)
    return run


def _offered(chosen, offered, what):
    names = list(dict.fromkeys(chosen))
    if set(names) - {item['name'] for item in offered}:
        raise ValueError(f'{what}: ім\'я не з пропозиції')
    return names


def _choice(proposal, request) -> tuple[dict, dict, set]:
    """The selected items, each checked against the proposal: an item it does not offer is an invalid request."""
    cards = {card['key']: card for card in proposal['cards']}
    updates = {item['card_id']: item for item in proposal['name_updates']}
    chosen_cards, chosen_updates = {}, {}
    for choice in request.cards:
        if choice.key not in cards or choice.key in chosen_cards:
            raise ValueError('Невідома або повторена картка пропозиції')
        chosen_cards[choice.key] = _offered(choice.names, cards[choice.key]['other_names'], 'Нова картка')
    for choice in request.name_updates:
        if choice.card_id not in updates or choice.card_id in chosen_updates:
            raise ValueError('Невідоме або повторене оновлення імен')
        chosen_updates[choice.card_id] = _offered(choice.names, updates[choice.card_id]['names'], 'Нові імена')
    if request.protagonist and not proposal['protagonist']:
        raise ValueError('Пропозиція не має головного героя')
    casts = set(request.casts)
    if len(casts) != len(request.casts) or casts - {item['scene_id'] for item in proposal['casts']}:
        raise ValueError('Невідома або повторена сцена пропозиції')
    return chosen_cards, chosen_updates, casts


def _item(kind, **key) -> dict:
    return {'kind': kind, **key}


def _entry(text, scene_id=None, sources=()) -> dict:
    return {'text': text, 'availability': 'from_scene' if scene_id else 'timeless', 'available_from_scene_id': scene_id,
            'origin': 'model', 'sources': list(sources)}


class _Outcome:
    def __init__(self):
        self.applied, self.skipped = [], []

    def apply(self, item):
        self.applied.append(item)

    def skip(self, item, reason):
        self.skipped.append({'item': item, 'reason': reason})


def _card_payload(view, proposal, chosen_cards, chosen_updates, protagonist, markers, current, outcome):
    """(the cards payload, the new cards by key) — the current cards with the selected additions; None when nothing
    changes. Author entries are kept as they are; new cards and entries get their IDs from the save."""
    from .names import card_names
    payload = [card.model_dump() for card in current]
    by_id = {card['id']: card for card in payload}
    # Who has each name: the current cards, then the cards and names accepted so far in this request. A name is never
    # given to a second card.
    owners = {}
    for card in current:
        for name in card_names(card):
            owners.setdefault(name_key(name), set()).add(card.id)

    def kept_names(owner, names, item):
        """The names free of any other card, now owned by `owner`; a name of another card is skipped."""
        kept, dropped = [], False
        for name in names:
            others = owners.get(name_key(name), set()) - {owner}
            if others:
                outcome.skip(item(name), SKIP_NAME_OTHER_CARD)
                dropped = True
            elif owner not in owners.get(name_key(name), set()):
                owners.setdefault(name_key(name), set()).add(owner)
                kept.append(name)
        return kept, dropped
    new = {}
    for card in proposal['cards']:
        if card['key'] not in chosen_cards:
            continue
        key = card['key']
        if name_key(card['name']) in owners:
            outcome.skip(_item('card', key=key), SKIP_NAME_TAKEN)
            continue
        owners[name_key(card['name'])] = {key}
        chosen, _ = kept_names(key, chosen_cards[key], lambda name, key=key: _item('name', key=key, name=name))
        entries = []
        for quote in card['quotes']:  # spec 4.3: one entry per quote, available from the scene of that quote
            scene = view.scenes.get(quote['scene_id'])
            if scene is None or scene.trashed_at:
                outcome.skip(_item('quote', key=key, scene_id=quote['scene_id']), SKIP_SCENE_TRASHED)
                continue
            entries.append(_entry(markers['quote'].format(quote['quote']), scene.id,
                                  [{'version_id': quote['version_id'], 'quote': quote['quote']}]))
        if chosen:
            entries.append(_entry(markers['other_names'].format(', '.join(chosen))))
        new[key] = {'name': card['name'], 'entries': entries}
        payload.append(new[key])
        outcome.apply(_item('card', key=key))
    for update in proposal['name_updates']:
        card_id = update['card_id']
        if card_id not in chosen_updates:
            continue
        if card_id not in by_id:
            outcome.skip(_item('name_update', card_id=card_id), SKIP_CARD_GONE)
            continue
        added, dropped = kept_names(card_id, chosen_updates[card_id],
                                    lambda name, card_id=card_id: _item('name', card_id=card_id, name=name))
        if not added:
            if not dropped:  # a name of another card is skipped item by item above
                outcome.skip(_item('name_update', card_id=card_id), SKIP_NO_NEW_NAMES)
            continue
        by_id[card_id]['entries'].append(_entry(markers['other_names'].format(', '.join(added))))
        outcome.apply(_item('name_update', card_id=card_id))
    if protagonist:
        ref = proposal['protagonist']['ref']
        item = _item('protagonist', ref=ref)
        target = new.get(ref) or by_id.get(ref)
        if _has_author_protagonist(current):
            outcome.skip(item, SKIP_PROTAGONIST_MARKED)
        elif target is None:
            proposed = {card['key'] for card in proposal['cards']}
            outcome.skip(item, SKIP_PROTAGONIST_NOT_ACCEPTED if ref in proposed else SKIP_CARD_GONE)
        else:
            target['entries'].append(_entry(markers['protagonist']))
            outcome.apply(item)
    changed = bool(new) or len(outcome.applied) > len(new)
    return (payload if changed else None), new


def _valid_memory_scenes(view) -> list[str]:
    """Active scenes, in book order, whose memory head is valid (`memory_build._memory_valid`)."""
    from ..generation.memory_build import _memory_valid
    scenes = sorted((s for s in view.scenes.values() if not s.trashed_at), key=lambda s: s.position)
    return [s.id for s in scenes if s.heads.get('memory') and _memory_valid(view, s.heads['memory'], s)]


def _cast_plan(view, proposal, chosen_casts, refs, outcome):
    """{scene id: card IDs to add}. A participant that is a new card not accepted or a card that no longer exists is
    left out before `apply_cast` (which refuses unknown IDs)."""
    from ..storage.scene_cast import AUTHOR_PROSE, _planned
    source = proposal['source']['scenes']
    plan = {}
    for item in proposal['casts']:
        scene_id = item['scene_id']
        if scene_id not in chosen_casts:
            continue
        scene = view.scenes.get(scene_id)
        prose_id = scene.heads.get('prose') if scene is not None else None
        reason, missing = None, []
        if scene is None or scene.trashed_at:
            reason = SKIP_SCENE_TRASHED
        elif not prose_id or prose_id != (source.get(scene_id) or {}).get('version_id'):
            reason = SKIP_PROSE_CHANGED
        elif _planned(scene):
            reason = SKIP_PLANNED
        elif view.peek_version(prose_id).kind != AUTHOR_PROSE:
            reason = SKIP_NOT_AUTHOR_PROSE
        else:
            ids = [refs[ref] for ref in item['participants'] if ref in refs]
            missing = [id for id in dict.fromkeys(ids) if id not in scene.character_ids]  # set on a cast → add
            if not missing:
                reason = SKIP_NOTHING_TO_ADD
        if reason:
            outcome.skip(_item('cast', scene_id=scene_id), reason)
            continue
        plan[scene_id] = missing
        outcome.apply(_item('cast', scene_id=scene_id))
    return plan


def _accept(repo, db, story_id, request, written):
    from ..storage.scene_cast import apply_cast_in_transaction, view_cards
    from .service import changed_character_ids, save_cards_in_transaction
    story = repo.story_in_transaction(db, story_id)
    run = _proposal_run(repo.story_runs_in_transaction(db, story_id), request)
    proposal = run.checkpoint['proposal']
    chosen_cards, chosen_updates, chosen_casts = _choice(proposal, request)
    view = repo.view_in_transaction(db, story_id)
    current = view_cards(view)
    valid_memory = _valid_memory_scenes(view)
    outcome = _Outcome()
    payload, new = _card_payload(view, proposal, chosen_cards, chosen_updates, request.protagonist,
                                 MARKERS[story.language], current, outcome)
    saved = current
    if payload is not None:
        written.append(save_cards_in_transaction(repo, db, story_id, payload, story.revision))
        saved = view_cards(repo.view_in_transaction(db, story_id))
    before = {card.id for card in current}
    created = [card.id for card in saved if card.id not in before]  # new cards keep their order in the payload
    refs = {card.id: card.id for card in saved} | dict(zip(new, created))
    cast_outcome = _Outcome()
    plan = _cast_plan(view, proposal, chosen_casts, refs, cast_outcome)
    changed_scenes = apply_cast_in_transaction(repo, db, story_id, plan, 'add') if plan else []
    # Measured, not predicted: the new cards version (the first one of a book stales all its material), a changed cast
    # and everything downstream of the invalidation, read back from the transaction.
    still_valid = set(_valid_memory_scenes(repo.view_in_transaction(db, story_id)))
    run.checkpoint = {**run.checkpoint, 'accepted_at': now()}
    repo.save_run_in_transaction(db, run)
    return {'applied': outcome.applied + cast_outcome.applied, 'skipped': outcome.skipped + cast_outcome.skipped,
            'changed_card_ids': changed_character_ids(current, saved), 'changed_scene_ids': changed_scenes,
            'stale_memory_scenes': [scene_id for scene_id in valid_memory if scene_id not in still_valid]}


class _DryRun(Exception):
    def __init__(self, result):
        super().__init__('dry run')
        self.result = result


def accept_proposal(repo, story_id: str, request: AcceptRequest) -> dict:
    """{applied, skipped [{item, reason}], changed_card_ids, changed_scene_ids, stale_memory_scenes}. A dry run answers
    the same and rolls the transaction back; the cards file it wrote is removed (an unlisted file fails fsck)."""
    written = []
    try:
        with repo.write_transaction() as db:
            result = _accept(repo, db, story_id, request, written)
            if request.dry_run:
                raise _DryRun(result)
    except _DryRun as dry:
        for version in written:
            repo.discard_unregistered_version(version)
        return dry.result
    except BaseException:
        for version in written:
            repo.discard_unregistered_version(version)
        raise
    return result
