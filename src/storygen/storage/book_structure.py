"""BOOK-STRUCTURE storage: parts, arcs and scene bindings in the story payload, under the story revision (CAS).

Never touches versions, dependency edges or scene revisions: the structure is not part of any context.
"""
from ..book.structure import arc_before, arc_order, check_sequential, validate_shape
from ..domain import Arc, BookStructure, Part, RevisionConflict, Scene, new_id

CONFLICT = 'Твір уже змінено. Оновіть сторінку; структуру книги не збережено.'
MAX_ID = 64


def _scenes(db, story_id):
    return [Scene.model_validate_json(r[0]) for r in db.execute('SELECT payload FROM scenes WHERE story_id=? ORDER BY position,id', (story_id,))]


def _id(value):
    if value is None:
        return new_id()
    if not isinstance(value, str) or not value or len(value) > MAX_ID:
        raise ValueError('Некоректний ID частини чи арки')
    return value


def build_structure(parts: list[dict]) -> BookStructure:
    """Parts from the request; a null id gets a new one. A client may name ids itself to bind scenes to new arcs."""
    try:
        structure = BookStructure(parts=[Part(id=_id(p.get('id')), title=p.get('title') or '',
                                              arcs=[Arc(id=_id(a.get('id')), title=a.get('title') or '') for a in p.get('arcs') or []])
                                         for p in parts])
    except (AttributeError, TypeError) as exc:
        raise ValueError('Некоректна структура книги') from exc
    validate_shape(structure)
    return structure


def _require_sequence(structure, scene_arcs, active):
    problems = check_sequential(structure, scene_arcs, active)
    if problems:
        raise ValueError('; '.join(problems[:10]) + (f' (і ще {len(problems) - 10})' if len(problems) > 10 else ''))


def _begin(repo, db, story_id, expected_revision):
    db.execute('BEGIN IMMEDIATE')
    story = repo._active_story(db, story_id)
    if story.revision != expected_revision:
        raise RevisionConflict(CONFLICT)
    return story


def _save(repo, db, story, **update):
    story = story.model_copy(update={**update, 'revision': story.revision + 1})
    repo._save_story(db, story)
    return story


def put_structure(repo, story_id: str, parts: list[dict], scene_arcs: dict, expected_revision: int):
    structure = build_structure(parts)
    known = arc_order(structure)
    with repo.db.connection() as db:
        story = _begin(repo, db, story_id, expected_revision)
        scenes = _scenes(db, story_id)
        active = [s for s in scenes if not s.trashed_at]
        ids = {s.id for s in scenes}
        if any(key not in ids for key in scene_arcs):
            raise ValueError('Прив’язка до сцени, якої немає у творі')
        bindings = {s.id: story.scene_arcs[s.id] for s in scenes if s.trashed_at and story.scene_arcs.get(s.id) in known}
        bindings.update({key: value for key, value in scene_arcs.items() if key in {s.id for s in active}})
        if len(known) == 1:
            # One arc for the whole book: unbound scenes can only belong to it.
            only = next(iter(known))
            bindings.update({s.id: only for s in active if s.id not in bindings})
        _require_sequence(structure, bindings, active)
        return _save(repo, db, story, book_structure=structure, scene_arcs=bindings)


def assign_scene(repo, story_id: str, scene_id: str, arc_id: str, expected_revision: int):
    with repo.db.connection() as db:
        story = _begin(repo, db, story_id, expected_revision)
        if story.book_structure is None:
            raise ValueError('У книги немає структури: спершу створіть частини й арки')
        scenes = _scenes(db, story_id)
        active = [s for s in scenes if not s.trashed_at]
        if scene_id not in {s.id for s in active}:
            raise KeyError('Сцену не знайдено')
        if arc_id not in arc_order(story.book_structure):
            raise ValueError('Такої арки немає в структурі книги')
        bindings = {**story.scene_arcs, scene_id: arc_id}
        _require_sequence(story.book_structure, bindings, active)
        return _save(repo, db, story, scene_arcs=bindings)


def clear_structure(repo, story_id: str, expected_revision: int):
    with repo.db.connection() as db:
        story = _begin(repo, db, story_id, expected_revision)
        return _save(repo, db, story, book_structure=None, scene_arcs={})


def bind_new_scene(story, active: list[Scene], scene: Scene, position: int):
    """create_scene hook: in an explicit structure the new scene joins the arc of the scene before it."""
    if story.book_structure is None:
        return story
    others = [s for s in active if s.id != scene.id]
    arc = arc_before(story.book_structure, story.scene_arcs, [s.model_copy(update={'position': i}) for i, s in enumerate(others)], position)
    return story.model_copy(update={'scene_arcs': {**story.scene_arcs, scene.id: arc}})


def require_order(story, ordered_active: list[Scene]):
    """reorder hook: an explicit structure refuses an order that mixes arcs or parts, before anything is written."""
    if story.book_structure is None:
        return
    _require_sequence(story.book_structure, story.scene_arcs, [s.model_copy(update={'position': i}) for i, s in enumerate(ordered_active)])


def bind_restored_scene(story, ordered_active: list[Scene], scene: Scene):
    """restore hook: keeps the scene's arc when it still exists and fits; otherwise the arc of the scene before it.
    Never refuses: a restore must always succeed."""
    if story.book_structure is None:
        return story
    placed = [s.model_copy(update={'position': i}) for i, s in enumerate(ordered_active)]
    current = story.scene_arcs.get(scene.id)
    if current in arc_order(story.book_structure) and not check_sequential(story.book_structure, story.scene_arcs, placed):
        return story
    position = next(i for i, s in enumerate(ordered_active) if s.id == scene.id)
    arc = arc_before(story.book_structure, story.scene_arcs, [s for s in placed if s.id != scene.id], position)
    return story.model_copy(update={'scene_arcs': {**story.scene_arcs, scene.id: arc}})
