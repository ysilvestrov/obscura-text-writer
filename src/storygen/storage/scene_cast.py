"""R-48 PR 2 (design §5.1, amendment 1): the cast of scenes from the names mentioned in their prose, without a model.

Before the memory build each active scene with author prose (a `manual` prose head: imported or written by the author)
whose plan has no participants line gets as its cast the character cards whose name available in that scene
(`characters/names.py::scene_match_names`) its prose mentions under the stem rule of memory selection, in order of first
mention. Scenes whose plan names participants and scenes whose prose a model derived (`edited`) are never changed, so the
cast write never stales model prose (review M-2)."""
import threading
from typing import Literal

from ..characters.acquaintance import protagonist
from ..characters.models import load_characters
from ..characters.names import scene_match_names
from ..domain import RevisionConflict, Scene
from ..memory.selection import MentionIndex, name_stems
from ..scene_description import parse_scene_description

NO_CARDS_WARNING = 'Немає карток персонажів: пам\'ять не матиме стану героя'
CAST_CONFLICT = 'Твір уже змінено. Оновіть сторінку; учасників сцен не записано.'


def view_cards(view):
    story = view.get_story(view.story.id)
    return load_characters(view.read_text(story.characters_version_id)) if story.characters_version_id else []


def _planned(scene) -> bool:
    return parse_scene_description(scene.beats or '').participants is not None


AUTHOR_PROSE = 'manual'


def propose_cast(view, cards) -> dict[str, list[str]]:
    """{scene id: card IDs in order of first mention} for every active scene with an author (`manual`) prose head whose plan
    has no participants line (or no plan) and whose cast is empty; scenes with that line or a cast the author set are absent
    and never changed. A tie (one word for two cards) keeps card order."""
    scenes = sorted((s for s in view.list_scenes(view.story.id) if not s.trashed_at), key=lambda s: s.position)
    result = {}
    for scene in scenes:
        prose_id = scene.heads.get('prose')
        if not prose_id or _planned(scene) or scene.character_ids or view.peek_version(prose_id).kind != AUTHOR_PROSE:
            continue
        if not cards:
            result[scene.id] = []
            continue
        names = scene_match_names(cards, scenes, scene)
        key = (view.peek_version(prose_id).sha256, tuple((card.id, names.get(card.id, '')) for card in cards))
        cast = _CAST_CACHE.get(key)
        if cast is None:
            index = MentionIndex(view.read_text(prose_id))
            found = []
            for order, card in enumerate(cards):
                at = index.first(name_stems(names.get(card.id, '')))
                if at is not None:
                    found.append((at, order, card.id))
            cast = tuple(dict.fromkeys(id for _, _, id in sorted(found)))
            _remember(key, cast)
        result[scene.id] = list(cast)
    return result


# Readiness of `rebuild_memory` is asked on every workspace refresh: the cast of a scene is kept per (prose text, the card
# names available in it), so only changed scenes are searched again.
_CAST_CACHE: dict = {}
_CAST_CACHE_SIZE = 4096
_CAST_LOCK = threading.Lock()


def _remember(key, cast) -> None:
    with _CAST_LOCK:
        while len(_CAST_CACHE) >= _CAST_CACHE_SIZE:
            _CAST_CACHE.pop(next(iter(_CAST_CACHE)), None)
        _CAST_CACHE[key] = cast


def cast_preview(view):
    """(the readiness `cast` entry, the proposal): the number of cards, the hero's name the build will see once the
    proposal is applied (the protagonist marker, else the first participant of the first scene), how many scenes the
    proposal changes, and the no-cards warning, which never blocks the run."""
    cards = view_cards(view)
    proposal = propose_cast(view, cards)
    scenes = [s for s in view.list_scenes(view.story.id) if not s.trashed_at]
    cast = [s.model_copy(update={'character_ids': proposal[s.id]}) if s.id in proposal else s for s in scenes]
    hero, _ = protagonist(cards, cast) if cards else (None, [])
    names = {card.id: card.name for card in cards}
    entry = {'cards': len(cards), 'protagonist': names.get(hero),
             'scenes_to_fill': sum(1 for s in scenes if s.id in proposal and proposal[s.id] != s.character_ids),
             'warning': None if cards else NO_CARDS_WARNING}
    return entry, proposal


def apply_cast(repo, story_id, proposal, expected_revision, mode: Literal['set', 'add'] = 'set') -> list[str]:
    """Writes the proposed casts in one transaction under CAS on the story revision; returns the IDs of the scenes whose
    cast changed (`apply_cast_in_transaction`)."""
    with repo.write_transaction() as db:
        if repo.story_in_transaction(db, story_id).revision != expected_revision:
            raise RevisionConflict(CAST_CONFLICT)
        return apply_cast_in_transaction(repo, db, story_id, proposal, mode)


def apply_cast_in_transaction(repo, db, story_id, proposal, mode: Literal['set', 'add'] = 'set') -> list[str]:
    """The casts of `proposal` ({scene id: card IDs}) on the caller's open write transaction; returns the IDs of the scenes
    whose cast changed. A scene whose plan now names participants, whose prose head is not author text (`manual`), a
    trashed scene or one of another story is skipped. `set` fills only an empty cast (a cast already set is skipped);
    `add` (CHARACTER-EXTRACT) appends the participants missing from the cast at its end, so a cast never loses anyone.
    A changed cast stales the scene's material as a changed participants line does (`stale_scene_material`); nothing
    changes → nothing is written and the story revision stays."""
    from ..domain import VersionRef
    from .scene_metadata import stale_scene_material, story_cards
    if mode not in ('set', 'add'):
        raise ValueError('Невідомий режим складу сцени')
    repo._active_story(db, story_id)
    known = {card.id for card in story_cards(repo, db, story_id)}
    changed = []
    for scene_id, ids in proposal.items():
        if set(ids) - known:
            raise ValueError('Учасник сцени не має картки персонажа')
        # Read inside the transaction: the invalidation of an earlier scene may have marked this one for review.
        row = db.execute('SELECT payload FROM scenes WHERE id=? AND story_id=?', (scene_id, story_id)).fetchone()
        if row is None:
            continue
        scene = Scene.model_validate_json(row[0])
        if not ids or scene.trashed_at or _planned(scene) or not scene.heads.get('prose'):
            continue
        if mode == 'set' and scene.character_ids:
            continue
        if repo._get(db, 'versions', scene.heads['prose'], VersionRef).kind != AUTHOR_PROSE:
            continue
        cast = list(dict.fromkeys([*scene.character_ids, *ids]))
        if cast == scene.character_ids:
            continue
        scene.character_ids = cast
        stale_scene_material(repo, db, scene)
        scene.revision += 1
        repo._save_scene(db, scene)
        changed.append(scene.id)
    if changed:
        repo._touch_story(db, story_id)
    return changed
