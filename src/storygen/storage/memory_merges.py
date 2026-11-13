"""MEMORY-MERGE storage: merge points, `memory_merge` versions and their heads, CAS on the story revision.

A merge is a story version (`scene_id=None`, kind `memory_merge`, JSON) whose input_refs are the selected memory of its
heads; Story.memory_merge_heads maps a merge key to the current version. A merge is usable while its version is fresh and
its head memory IDs are still the selected memory of the head scenes."""
import json
from dataclasses import dataclass

from ..domain import RevisionConflict, Story

SCHEMA_VERSION = 1
MAX_HEADS = 10000
CHANGED = 'Пам’ять арок або твір уже змінилися; перегляньте злиття заново. Ваш вибір не збережено.'


@dataclass(frozen=True)
class MergePoint:
    key: str
    heads: tuple[str, ...]  # reading order
    target_scene_ids: tuple[str, ...]  # scenes that start from this point; empty for the end of the book
    book_end: bool = False


def merge_point(story, scenes, *, scene_id=None, book_end=False) -> MergePoint | None:
    from ..book.lineage import book_end_heads, lineage_map, merge_key
    items = lineage_map(story, scenes)
    if book_end:
        heads = book_end_heads(story, scenes)
        if len(heads) < 2:
            return None
    else:
        item = items.get(scene_id)
        if item is None or not item.needs_merge:
            return None
        heads = item.heads
    key = merge_key(heads)
    targets = tuple(id for id, item in items.items() if item.needs_merge and merge_key(item.heads) == key)
    return MergePoint(key, tuple(heads), targets, bool(book_end))


def point_by_key(story, scenes, key: str) -> MergePoint | None:
    from ..book.lineage import lineage_map, merge_key
    for scene_id, item in lineage_map(story, scenes).items():
        if item.needs_merge and merge_key(item.heads) == key:
            return merge_point(story, scenes, scene_id=scene_id)
    end = merge_point(story, scenes, book_end=True)
    return end if end and end.key == key else None


def read_merge(view, version_id: str) -> dict:
    ref = view.get_version(version_id)
    if ref.kind != 'memory_merge':
        raise ValueError('Це не версія злиття пам’яті')
    return json.loads(view.read_text(version_id))


def merge_journal(view, version_id: str):
    from ..memory.journal import MemoryJournal
    return MemoryJournal.model_validate(read_merge(view, version_id)['journal'])


def _label(scene) -> str:
    return f'сцена {scene.position + 1} «{scene.title}»'


def head_inputs(view, scenes, point):
    """(journals by head, head memory ids, blocked reason or None)."""
    from ..memory.journal import load_memory
    by_id = {s.id: s for s in scenes}
    journals, memory_ids = {}, []
    for head in point.heads:
        scene = by_id[head]
        memory_id = scene.heads.get('memory')
        if not memory_id:
            return {}, [], f'{_label(scene)[0].upper()}{_label(scene)[1:]} ще не має пам’яті'
        ref = view.get_version(memory_id)
        if ref.stale or not ref.complete:
            return {}, [], f'Пам’ять: {_label(scene)} застаріла; оновіть її'
        journals[head] = load_memory(view.read_text(memory_id))
        memory_ids.append(memory_id)
    return journals, memory_ids, None


def merged_sources(view, scenes, journals: dict) -> list[str]:
    """Prose sources of every head journal, in reading order of the scenes they belong to."""
    position = {s.id: s.position for s in scenes}
    ids = list(dict.fromkeys(source for journal in journals.values() for source in journal.source_prose_ids))
    return sorted(ids, key=lambda id: position.get(view.get_version(id).scene_id, -1))


def compute(view, story, scenes, point):
    """(plan, journals, head memory ids, sources, author source) for a point whose heads all have fresh memory."""
    from ..memory.merge import plan_merge
    journals, memory_ids, reason = head_inputs(view, scenes, point)
    if reason:
        raise ValueError(reason)
    plan = plan_merge(journals, list(point.heads))
    sources = merged_sources(view, scenes, journals)
    return plan, journals, memory_ids, sources, journals[point.heads[-1]].source_prose_ids[-1]


def usable_merge(view, story, scenes, point) -> str | None:
    version_id = story.memory_merge_heads.get(point.key)
    if not version_id:
        return None
    try:
        ref = view.get_version(version_id)
        payload = read_merge(view, version_id)
    except (KeyError, ValueError, OSError):
        return None
    by_id = {s.id: s for s in scenes}
    current = [by_id[h].heads.get('memory') if h in by_id else None for h in point.heads]
    if ref.stale or payload.get('head_memory_ids') != current:
        return None
    return version_id


def _previous(view, story, point) -> dict | None:
    """Payload of the merge whose decisions carry: the head of the key, else the latest merge sharing a head scene."""
    version_id = story.memory_merge_heads.get(point.key)
    if version_id:
        try:
            return read_merge(view, version_id)
        except (KeyError, ValueError, OSError):
            return None
    for version_id in reversed(list(story.memory_merge_heads.values())):
        try:
            payload = read_merge(view, version_id)
        except (KeyError, ValueError, OSError):
            continue
        if set(payload.get('heads', ())) & set(point.heads):
            return payload
    return None


def _conflict_label(conflict, base_active, names) -> str:
    if conflict.key.startswith('slot:'):
        _, character, slot = conflict.key.split(':', 2)
        return f'{names.get(character, character)} — {slot}'
    record = base_active.get(conflict.key[len('claim:'):])
    return record.text if record else next(iter(conflict.values.values())) or conflict.key


def merge_state(view, story, scenes, point) -> dict:
    from ..book.structure import arc_order, scene_arc_list
    from ..memory.journal import replay_memory
    from ..memory.merge import carry_decisions
    from .snapshots import core_cards
    by_id = {s.id: s for s in scenes}
    titles = {}
    if story.book_structure:
        for number, (arc_id, _) in enumerate(arc_order(story.book_structure).items(), 1):
            arc = next(a for p in story.book_structure.parts for a in p.arcs if a.id == arc_id)
            titles[arc_id] = arc.title or f'Арка {number}'
    heads = [{'scene_id': h, 'number': by_id[h].position + 1, 'title': by_id[h].title, 'memory_id': by_id[h].heads.get('memory'),
              'arc_titles': [titles.get(a, a) for a in scene_arc_list(story.scene_arcs, h)]} for h in point.heads]
    result = {'key': point.key, 'book_end': point.book_end, 'target_scene_ids': list(point.target_scene_ids), 'heads': heads,
              'state': 'none', 'reason': None, 'conflicts': [], 'carried': {}, 'head_version_id': story.memory_merge_heads.get(point.key),
              'story_revision': story.revision}
    try:
        plan, _, _, _, _ = compute(view, story, scenes, point)
    except ValueError as exc:
        return {**result, 'state': 'blocked', 'reason': str(exc)}
    names = {card.id: card.name for card in core_cards(view, story)}
    base_active = replay_memory(plan.base)
    result['conflicts'] = [{'key': c.key, 'label': _conflict_label(c, base_active, names), 'values': c.values} for c in plan.conflicts]
    usable = usable_merge(view, story, scenes, point)
    previous = _previous(view, story, point)
    if usable:
        result['state'] = 'fresh'
        result['carried'] = previous.get('decisions', {}) if previous else {}
    else:
        result['state'] = 'stale' if result['head_version_id'] else 'none'
        if previous:
            result['carried'] = carry_decisions(previous.get('conflicts', []), previous.get('decisions', {}), plan.conflicts)
    return result


def save_merge(repo, story_id: str, key: str, decisions: dict, expected_revision: int, expected_head_memory_ids: list[str]):
    """Builds, validates and publishes the merge of `key`; returns (story, version id)."""
    from ..memory.journal import validate_memory_journal
    from ..memory.merge import build_merged_journal
    view = repo.context_view(story_id)
    story = view.get_story(story_id)
    scenes = view.list_scenes(story_id)
    if story.revision != expected_revision:
        raise RevisionConflict(CHANGED)
    point = point_by_key(story, scenes, key)
    if point is None:
        raise ValueError('Такої точки злиття немає; оновіть сторінку')
    plan, journals, memory_ids, sources, author_source = compute(view, story, scenes, point)
    if memory_ids != list(expected_head_memory_ids):
        raise RevisionConflict(CHANGED)
    journal = build_merged_journal(plan, decisions, sources, author_source)
    validate_memory_journal(journal, {id: view.read_text(id) for id in sources})
    payload = json.dumps({'schema_version': SCHEMA_VERSION, 'merge_key': key, 'heads': list(point.heads),
                          'head_memory_ids': memory_ids, 'base_source_prose_ids': plan.base.source_prose_ids,
                          'conflicts': [{'key': c.key, 'values': c.values} for c in plan.conflicts],
                          'decisions': {c.key: decisions[c.key] for c in plan.conflicts},
                          'journal': json.loads(journal.model_dump_json())}, ensure_ascii=False)
    ref = repo.save_version(story_id, None, 'memory_merge', payload, memory_ids)
    return publish_merge(repo, story_id, key, ref.id, point.heads, memory_ids, expected_revision), ref.id


def publish_merge(repo, story_id: str, key: str, version_id: str, heads, memory_ids, expected_revision: int) -> Story:
    from .invalidation import invalidate_in_transaction
    from .book_structure import _scenes
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        story = repo._active_story(db, story_id)
        if story.revision != expected_revision:
            raise RevisionConflict(CHANGED)
        by_id = {s.id: s for s in _scenes(db, story_id)}
        if [by_id[h].heads.get('memory') if h in by_id else None for h in heads] != list(memory_ids):
            raise RevisionConflict(CHANGED)
        merge_heads = dict(story.memory_merge_heads)
        previous = merge_heads.get(key)
        if previous is None and len(merge_heads) >= MAX_HEADS:
            raise ValueError('Забагато злиттів пам’яті')
        merge_heads[key] = version_id
        story = story.model_copy(update={'memory_merge_heads': merge_heads, 'revision': story.revision + 1})
        repo._save_story(db, story)
        if previous and previous != version_id:
            invalidate_in_transaction(repo, db, [previous], exclude={version_id})
        return story
