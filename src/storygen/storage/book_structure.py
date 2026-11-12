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


def place_imported(story, active: list[Scene], created: list[tuple[Scene, str | None, str | None]], structured: bool):
    """publish_import hook: parts and arcs from the plan for the new scenes (all at the end of the book).

    A part continues the book's last part when the titles match (or the title is None); otherwise a new part follows.
    An arc is found by title in its part; None continues the part's last arc. A flat book that already has scenes keeps
    them in a first part. A sequence violation raises ValueError and the whole publication rolls back."""
    if not created or story.book_structure is None and not structured:
        return story
    parts = [part.model_copy(deep=True) for part in story.book_structure.parts] if story.book_structure else []
    bindings = dict(story.scene_arcs)
    new = {scene.id for scene, _, _ in created}
    earlier = [s for s in active if s.id not in new]
    if story.book_structure is None and earlier:
        parts.append(Part(id=new_id(), arcs=[Arc(id=new_id())]))
        bindings.update({s.id: parts[0].arcs[0].id for s in earlier})
    for scene, part_title, arc_title in created:
        if not parts or part_title is not None and parts[-1].title != part_title:
            parts.append(Part(id=new_id(), title=part_title or ''))
        part = parts[-1]
        arc = next((a for a in reversed(part.arcs) if a.title == arc_title), None) if arc_title is not None else (part.arcs[-1] if part.arcs else None)
        if arc is None:
            arc = Arc(id=new_id(), title=arc_title or '')
            part.arcs.append(arc)
        bindings[scene.id] = arc.id
    structure = BookStructure(parts=parts)
    validate_shape(structure)
    _require_sequence(structure, bindings, [s.model_copy(update={'position': i}) for i, s in enumerate(active)])
    return story.model_copy(update={'book_structure': structure, 'scene_arcs': bindings})


def structured_story(repo, *, story_id=None, scene_id=None, run_id=None):
    """BUILD-EDITION-001-S08 guard lookup: (story, scenes) of the story named by a story, scene or run id, or None when
    there is no such story or it has no explicit structure. One read transaction; never raises for unknown ids."""
    from ..domain import Story
    with repo.db.connection() as db:
        if story_id is None and scene_id is not None:
            row = db.execute('SELECT story_id FROM scenes WHERE id=?', (scene_id,)).fetchone()
            story_id = row[0] if row else None
        if story_id is None and run_id is not None:
            row = db.execute('SELECT story_id FROM runs WHERE id=?', (run_id,)).fetchone()
            story_id = row[0] if row else None
        if not story_id:
            return None
        row = db.execute('SELECT payload FROM stories WHERE id=?', (story_id,)).fetchone()
        if row is None:
            return None
        story = Story.model_validate_json(row[0])
        if story.book_structure is None:
            return None
        return story, _scenes(db, story_id)
