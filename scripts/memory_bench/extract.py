"""Read-only extraction of per-scene memory snapshots through the product's own read functions."""
from collections import Counter

from storygen.memory.forwarding import forwarded_before, hidden_before
from storygen.memory.journal import MemoryJournal, load_memory, replay_memory
from storygen.memory.reuse import journal_for_read

from .model import Record, SceneInput

SKIP_CODES = ('skipped_needs_confirmation', 'skipped_no_memory')
TARGET_CODES = ('targets_hidden', 'targets_absent')


def records_from_journal(journal: MemoryJournal, numbers, hidden):
    """Active records and timeline exactly as project_memory selects them (before any cast filter)."""
    last = {}
    for event in journal.events:
        last[event.claim_id] = numbers.get(event.source_version_id)
    records = tuple(Record(e.claim_id, e.category, e.text, tuple(e.character_ids), numbers.get(e.source_version_id),
                           last[e.claim_id]) for e in replay_memory(journal).values() if e.claim_id not in hidden)
    timeline = tuple(Record(e.claim_id, e.category, e.text, tuple(e.character_ids), numbers.get(e.source_version_id),
                            last[e.claim_id], 'timeline' if e.category == 'timeline' else 'retired_thread')
                     for e in journal.events
                     if e.claim_id not in hidden and (e.category == 'timeline' or e.category == 'open_threads' and e.operation == 'retire'))
    return records, timeline


def scene_targets(own: MemoryJournal, past: MemoryJournal, own_prose_ids) -> frozenset:
    """Claims this scene's memory updated or retired: new events whose source is this scene's own prose."""
    known = {e.event_id for e in past.events}
    return frozenset(e.claim_id for e in own.events
                     if e.event_id not in known and e.source_version_id in own_prose_ids and e.operation in {'update', 'retire'})


def name_stems(name: str) -> tuple[str, ...]:
    stems = []
    for word in name.lower().replace('’', "'").replace('ʼ', "'").split():
        stem = word[:-1] if len(word) > 4 else word
        if len(stem) >= 3:
            stems.append(stem)
    return tuple(stems)


def _tracked(repo, story, scenes):
    from storygen.characters.models import load_characters
    from storygen.memory.core import tracked_characters
    cards = load_characters(repo.read_text(story.characters_version_id)) if story.characters_version_id else []
    return tracked_characters(cards, scenes)


def product_input(repo, scenes, scene, past, numbers, tracked, names, query):
    """The product's own selection input (#60): projection lines of build_context and the scene's plan as the query."""
    from storygen.memory.projection import memory_items
    from storygen.memory.selection import SelectionInput
    from storygen.memory.story_time import day_key
    items, _ = memory_items(past, list(scene.character_ids), {k: v for k, v in numbers.items() if v is not None},
                            hidden_claim_ids=hidden_before(repo, scene.id), forwarded_claim_ids=forwarded_before(repo, scene.id),
                            tracked=tracked, names=names)
    return SelectionInput(tuple(items), scene.id, scene.position + 1, tuple(scene.character_ids), tuple(tracked), dict(names),
                          query, {}, day_key(scene), {s.position + 1: day_key(s) for s in scenes if s.position < scene.position})


def _names(repo, story):
    if not story.characters_version_id:
        return {}
    from storygen.characters.models import load_characters
    return {card.id: card.name for card in load_characters(repo.read_text(story.characters_version_id))}


def _protagonist(scenes):
    counts = Counter(id for s in scenes for id in s.character_ids)
    if not counts:
        return ''
    top = max(counts.values())
    return min(id for id, n in counts.items() if n == top)


def _text(repo, version_id):
    return repo.read_text(version_id) if version_id else ''


def extract_story(repo, story_id: str, protagonist: str | None = None):
    repo = repo.context_view(story_id)  # one read-only snapshot for the whole story (hidden_before needs a view)
    story = repo.get_story(story_id)
    scenes = sorted(repo.list_scenes(story_id), key=lambda s: s.position)
    names = _names(repo, story)
    tracked = _tracked(repo, story, scenes)
    hero = protagonist or _protagonist(scenes)
    skipped = dict.fromkeys(SKIP_CODES + TARGET_CODES, 0)
    numbers_by_scene = {s.id: s.position + 1 for s in scenes}
    result, seen = [], set()
    for scene in scenes:
        cast = tuple(scene.character_ids)
        first = sum(1 for id in cast if id not in seen)
        seen.update(cast)
        earlier = [s for s in scenes if s.position < scene.position]
        if earlier and not earlier[-1].heads.get('memory'):
            skipped['skipped_no_memory'] += 1
            continue
        try:
            past = journal_for_read(repo, scene.id)
        except ValueError:
            # The previous scene has memory, so the product refuses only because it awaits confirmation.
            skipped['skipped_needs_confirmation'] += 1
            continue
        numbers = {id: numbers_by_scene.get(repo.get_version(id).scene_id) for id in past.source_prose_ids}
        records, timeline = records_from_journal(past, numbers, hidden_before(repo, scene.id))
        targets = frozenset()
        if scene.heads.get('memory'):
            own = load_memory(repo.read_text(scene.heads['memory']))
            own_prose = {id for id in own.source_prose_ids if repo.get_version(id).scene_id == scene.id}
            targets = scene_targets(own, past, own_prose)
            hidden = hidden_before(repo, scene.id)
            present = {r.claim_id for r in records}
            for claim in targets - present:
                skipped['targets_hidden' if claim in hidden else 'targets_absent'] += 1
        plan = _text(repo, scene.heads.get('plan')) or scene.beats
        result.append(SceneInput(scene.id, scene.position + 1, cast, plan, _text(repo, scene.heads.get('prose')), records, timeline,
                                 hero, names, targets, first, product_input(repo, scenes, scene, past, numbers, tracked, names, plan),
                                 {'journal': past, 'cast': list(cast), 'tracked': list(tracked), 'names': dict(names),
                                  'prose': _text(repo, scene.heads.get('prose')), 'number': scene.position + 1,
                                  'source_numbers': {k: v for k, v in numbers.items() if v is not None}}))
    return result, skipped
