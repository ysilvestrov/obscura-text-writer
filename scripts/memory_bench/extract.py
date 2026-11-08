"""Read-only extraction of per-scene memory snapshots through the product's own read functions."""
from collections import Counter

from storygen.memory.forwarding import hidden_before
from storygen.memory.journal import MemoryJournal, load_memory, replay_memory
from storygen.memory.reuse import journal_for_read

from .model import Record, SceneInput

NEEDS_CONFIRMATION = 'Спершу оновіть пам’ять попередньої сцени'
SKIP_CODES = ('skipped_needs_confirmation', 'skipped_no_memory')


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


def name_stems(name: str) -> tuple[str, ...]:
    stems = []
    for word in name.lower().replace('’', "'").replace('ʼ', "'").split():
        stem = word[:-1] if len(word) > 4 else word
        if len(stem) >= 3:
            stems.append(stem)
    return tuple(stems)


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
    hero = protagonist or _protagonist(scenes)
    skipped = dict.fromkeys(SKIP_CODES, 0)
    numbers_by_scene = {s.id: s.position + 1 for s in scenes}
    result, seen = [], set()
    for scene in scenes:
        cast = tuple(scene.character_ids)
        first = sum(1 for id in cast if id not in seen)
        seen.update(cast)
        try:
            past = journal_for_read(repo, scene.id)
        except ValueError as error:
            skipped['skipped_needs_confirmation' if str(error) == NEEDS_CONFIRMATION else 'skipped_no_memory'] += 1
            continue
        except Exception:
            skipped['skipped_no_memory'] += 1
            continue
        numbers = {id: numbers_by_scene.get(repo.get_version(id).scene_id) for id in past.source_prose_ids}
        records, timeline = records_from_journal(past, numbers, hidden_before(repo, scene.id))
        targets = frozenset()
        if scene.heads.get('memory'):
            known = {e.event_id for e in past.events}
            own = load_memory(repo.read_text(scene.heads['memory']))
            targets = frozenset(e.claim_id for e in own.events if e.event_id not in known and e.operation in {'update', 'retire'})
        result.append(SceneInput(scene.id, scene.position + 1, cast, _text(repo, scene.heads.get('plan')) or scene.beats,
                                 _text(repo, scene.heads.get('prose')), records, timeline, hero, names, targets, first))
    return result, skipped
