"""BOOK-STRUCTURE storage: parts, arcs and scene bindings in the story payload, under the story revision (CAS).

Never touches versions, dependency edges or scene revisions: the structure is not part of any context.
"""
from ..book.structure import arc_before, arc_order, canonical_arcs, check_order, scene_arc_list, validate_shape
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


def _protagonist(value):
    if value is None or isinstance(value, str) and value and len(value) <= MAX_ID:
        return value
    raise ValueError('Некоректний ID протагоніста арки')


def _require_cards(repo, db, story, structure):
    """BOOK-LINEAGE-S04: an explicit protagonist names a card of the current character set."""
    wanted = {arc.protagonist_id for part in structure.parts for arc in part.arcs if arc.protagonist_id}
    if not wanted:
        return
    from .context_view import ContextView
    from .snapshots import core_cards
    if wanted - {card.id for card in core_cards(ContextView(repo, db, story.id), story)}:
        raise ValueError('Протагоніст арки — картка, якої немає серед персонажів')


def build_structure(parts: list[dict]) -> BookStructure:
    """Parts from the request; a null id gets a new one. A client may name ids itself to bind scenes to new arcs."""
    try:
        structure = BookStructure(parts=[Part(id=_id(p.get('id')), title=p.get('title') or '',
                                              arcs=[Arc(id=_id(a.get('id')), title=a.get('title') or '',
                                                        protagonist_id=_protagonist(a.get('protagonist_id'))) for a in p.get('arcs') or []])
                                         for p in parts])
    except (AttributeError, TypeError) as exc:
        raise ValueError('Некоректна структура книги') from exc
    validate_shape(structure)
    return structure


def _binding(value):
    """A request binding: an arc id or a list of arc ids (a meeting scene); stored in canonical form."""
    arcs = [value] if isinstance(value, str) else value
    if not isinstance(arcs, list) or not arcs or len(arcs) > 20 or any(not isinstance(a, str) or not a or len(a) > MAX_ID for a in arcs):
        raise ValueError('Некоректна прив’язка сцени до арки')
    return canonical_arcs(arcs)


def _known(scene_arcs, scene_id, known):
    arcs = scene_arc_list(scene_arcs, scene_id)
    return bool(arcs) and all(a in known for a in arcs)


def _require_sequence(structure, scene_arcs, active):
    problems = check_order(structure, scene_arcs, active)
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
        _require_cards(repo, db, story, structure)
        scenes = _scenes(db, story_id)
        active = [s for s in scenes if not s.trashed_at]
        ids = {s.id for s in scenes}
        if any(key not in ids for key in scene_arcs):
            raise ValueError('Прив’язка до сцени, якої немає у творі')
        bindings = {s.id: story.scene_arcs[s.id] for s in scenes if s.trashed_at and _known(story.scene_arcs, s.id, known)}
        bindings.update({key: _binding(value) for key, value in scene_arcs.items() if key in {s.id for s in active}})
        if len(known) == 1:
            # One arc for the whole book: unbound scenes can only belong to it.
            only = next(iter(known))
            bindings.update({s.id: only for s in active if s.id not in bindings})
        _require_sequence(structure, bindings, active)
        return _save(repo, db, story, book_structure=structure, scene_arcs=bindings)


def assign_scene(repo, story_id: str, scene_id: str, arc_ids: list[str] | str, expected_revision: int):
    with repo.db.connection() as db:
        story = _begin(repo, db, story_id, expected_revision)
        if story.book_structure is None:
            raise ValueError('У книги немає структури: спершу створіть частини й арки')
        scenes = _scenes(db, story_id)
        active = [s for s in scenes if not s.trashed_at]
        if scene_id not in {s.id for s in active}:
            raise KeyError('Сцену не знайдено')
        binding = _binding(arc_ids)
        if any(arc not in arc_order(story.book_structure) for arc in scene_arc_list({scene_id: binding}, scene_id)):
            raise ValueError('Такої арки немає в структурі книги')
        bindings = {**story.scene_arcs, scene_id: binding}
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
    if _known(story.scene_arcs, scene.id, arc_order(story.book_structure)) and not check_order(story.book_structure, story.scene_arcs, placed):
        return story
    position = next(i for i, s in enumerate(ordered_active) if s.id == scene.id)
    arc = arc_before(story.book_structure, story.scene_arcs, [s for s in placed if s.id != scene.id], position)
    return story.model_copy(update={'scene_arcs': {**story.scene_arcs, scene.id: arc}})


PROTAGONIST_TAKEN = 'Арка вже має протагоніста; рядок «Протагоніст: {name}» пропущено.'
PROTAGONIST_UNKNOWN = 'Протагоніст «{name}» не знайдений серед карток; протагоніста арки не задано.'


def _card_by_name(cards):
    from ..scene_description import name_key
    return {name_key(card.name): card.id for card in cards}


def _apply_protagonists(structure, wanted, cards):
    """wanted: [(arc_id, name)] in plan order. Sets the protagonist of arcs without one; returns (pending, warnings)."""
    from ..scene_description import name_key
    by_name = _card_by_name(cards)
    arcs = {arc.id: arc for part in structure.parts for arc in part.arcs}
    pending, warnings = [], []
    for arc_id, name in wanted:
        arc = arcs.get(arc_id)
        if arc is None:
            continue
        found = by_name.get(name_key(name))
        if arc.protagonist_id:
            if found != arc.protagonist_id:
                warnings.append(PROTAGONIST_TAKEN.format(name=name))
        elif found:
            arc.protagonist_id = found
        elif (arc_id, name) not in pending:
            pending.append((arc_id, name))
    return pending, warnings


def bind_pending_protagonists(repo, story_id: str, pending: list[tuple[str, str]]) -> list[str]:
    """End of an import batch: names a later card file of the same batch may have created (as the cast, #103).
    One transaction on the current revision; unknown names become warnings and nothing is written for them."""
    if not pending:
        return []
    from .context_view import ContextView
    from .snapshots import core_cards
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        story = repo._active_story(db, story_id)
        if story.book_structure is None:
            return []
        structure = story.book_structure.model_copy(deep=True)
        left, warnings = _apply_protagonists(structure, pending, core_cards(ContextView(repo, db, story_id), story))
        if structure != story.book_structure:
            _save(repo, db, story, book_structure=structure)
    return warnings + [PROTAGONIST_UNKNOWN.format(name=name) for _, name in left]


def place_imported(story, active: list[Scene], created: list[tuple], structured: bool, cards=()):
    """publish_import hook: parts and arcs from the plan for the new scenes (all at the end of the book).

    Every part heading of the plan starts a new part, except the plan's first heading when its title matches the book's
    last part (a continued import); a scene before any heading (title None) continues the book's last part.
    An arc is found by title in its part; None continues the part's last arc. A flat book that already has scenes keeps
    them in a first part. A sequence violation raises ValueError and the whole publication rolls back.

    BOOK-LINEAGE-S04: a fifth tuple member is the scene's «Протагоніст:» name; it sets the protagonist of the scene's
    arc when the arc has none. Returns (story, pending [(arc_id, name)] not found among `cards`, warnings)."""
    if not created or story.book_structure is None and not structured:
        return story, [], []
    parts = [part.model_copy(deep=True) for part in story.book_structure.parts] if story.book_structure else []
    bindings = dict(story.scene_arcs)
    new = {scene.id for scene, *_ in created}
    earlier = [s for s in active if s.id not in new]
    if story.book_structure is None and earlier:
        parts.append(Part(id=new_id(), arcs=[Arc(id=new_id())]))
        bindings.update({s.id: parts[0].arcs[0].id for s in earlier})
    book_parts = len(parts)
    current = None
    wanted = []
    for scene, part_title, arc_title, part_index, *rest in created:
        if part_index is not None and part_index != current:
            continues = current is None and len(parts) == book_parts and parts and parts[-1].title == (part_title or '')
            if not continues:
                parts.append(Part(id=new_id(), title=part_title or ''))
            current = part_index
        elif not parts:
            parts.append(Part(id=new_id(), title=part_title or ''))
        part = parts[-1]
        meeting = rest[1] if len(rest) > 1 and rest[1] else None
        if meeting:
            # MEMORY-MERGE harness: a meeting scene belongs to every listed arc of its part, in structure order.
            arcs = [_arc_in_part(part, title) for title in meeting]
            order = {a.id: i for i, a in enumerate(part.arcs)}
            bindings[scene.id] = canonical_arcs(sorted({a.id for a in arcs}, key=order.get))
            arc = arcs[0]
        else:
            arc = _arc_in_part(part, arc_title) if arc_title is not None else (part.arcs[-1] if part.arcs else _arc_in_part(part, ''))
            bindings[scene.id] = arc.id
        if rest and rest[0]:
            wanted.append((arc.id, rest[0]))
    structure = BookStructure(parts=parts)
    validate_shape(structure)
    _require_sequence(structure, bindings, [s.model_copy(update={'position': i}) for i, s in enumerate(active)])
    pending, warnings = _apply_protagonists(structure, wanted, cards)
    return story.model_copy(update={'book_structure': structure, 'scene_arcs': bindings}), pending, warnings


def _arc_in_part(part, title: str):
    """The latest arc of the part with this title, created at the end of the part when there is none."""
    arc = next((a for a in reversed(part.arcs) if a.title == title), None)
    if arc is None:
        arc = Arc(id=new_id(), title=title or '')
        part.arcs.append(arc)
    return arc


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
        if story.book_structure is None and story.series_id is None:  # SERIES-S06: a series book is guarded too
            return None
        return story, _scenes(db, story_id)
