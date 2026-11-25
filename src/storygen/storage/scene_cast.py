"""R-48 PR 2 (design §5.1, amendment 1): the cast of scenes from the names mentioned in their prose, without a model.

Before the memory build each active scene with prose whose plan has no participants line gets as its cast the character
cards whose name available in that scene (`characters/names.py::scene_match_names`) its prose mentions under the stem
rule of memory selection, in order of first mention. Scenes whose plan names participants are never changed."""
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


def propose_cast(view, cards) -> dict[str, list[str]]:
    """{scene id: card IDs in order of first mention} for every active scene with a prose head whose plan has no
    participants line (or no plan); scenes with that line are absent. A tie (one word for two cards) keeps card order."""
    scenes = sorted((s for s in view.list_scenes(view.story.id) if not s.trashed_at), key=lambda s: s.position)
    result = {}
    for scene in scenes:
        prose_id = scene.heads.get('prose')
        if not prose_id or _planned(scene):
            continue
        found = []
        if cards:
            index = MentionIndex(view.read_text(prose_id))
            names = scene_match_names(cards, scenes, scene)
            for order, card in enumerate(cards):
                at = index.first(name_stems(names.get(card.id, '')))
                if at is not None:
                    found.append((at, order, card.id))
        result[scene.id] = list(dict.fromkeys(id for _, _, id in sorted(found)))
    return result


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


def apply_cast(repo, story_id, proposal, expected_revision) -> list[str]:
    """Writes the proposed casts in one transaction under CAS on the story revision; returns the IDs of the scenes whose
    cast changed. A scene whose plan now names participants, a trashed scene or one of another story is skipped. A changed
    cast stales the scene's material as a changed participants line does (`stale_scene_material`); nothing changes →
    nothing is written and the story revision stays."""
    from .scene_metadata import stale_scene_material, story_cards
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        story = repo._active_story(db, story_id)
        if story.revision != expected_revision:
            raise RevisionConflict(CAST_CONFLICT)
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
            if scene.trashed_at or _planned(scene) or scene.character_ids == list(ids):
                continue
            scene.character_ids = list(ids)
            stale_scene_material(repo, db, scene)
            scene.revision += 1
            repo._save_scene(db, scene)
            changed.append(scene.id)
        if changed:
            repo._touch_story(db, story_id)
    return changed
