"""A book with interleaved arcs, prose and memory journals that follow the lineage (neutral text, no private data)."""
from storygen.book.lineage import lineage_map
from storygen.domain import SceneCreate, StoryCreate
from storygen.memory.journal import MemoryJournal, _add_event, _change_event, _extend, load_memory
from storygen.storage.book_structure import put_structure
from storygen.storage.repository import Repository

QUOTE = 'Анна йде містом'


def fact(text, prose_id):
    return _add_event('facts', text, prose_id, QUOTE, 0)


def slot_add(text, prose_id, character='c1', slot='clothing'):
    return _add_event('character_states', text, prose_id, QUOTE, 0, [character], slot=slot)


def slot_update(record, text, prose_id):
    return _change_event('update', record.claim_id, text, 'character_states', record.character_ids, prose_id, QUOTE, slot=record.slot)


def arc_book(root, tokens, parts, events=None, *, repo=None):
    """`tokens`: 'A B A+B' (a '+' marks a meeting scene); `parts`: [[arc ids], ...]. Every scene gets manual prose; a scene
    whose lineage needs no merge gets memory extending its head's journal with `events(n, prose_id, previous)` (default:
    one fact). Returns (repo, story, scenes in reading order)."""
    repo = repo or Repository(root)
    story = repo.create_story(StoryCreate(title='Книга з арками'))
    words = tokens.split()
    scenes = []
    for n, _ in enumerate(words, 1):
        scene = repo.create_scene(story.id, SceneCreate(title=f'Сцена {n}', beats='Анна йде містом.'))
        prose = repo.save_version(story.id, scene.id, 'manual', f'Сцена {n}. Анна йде містом.', [])
        repo.set_head(scene.id, 'prose', prose.id, repo.get_scene(scene.id).revision)
        scenes.append(repo.get_scene(scene.id))
    structure = [{'id': f'p{i}', 'title': f'Частина {i}', 'arcs': [{'id': a, 'title': a} for a in part]} for i, part in enumerate(parts, 1)]
    bindings = {s.id: (w.split('+') if '+' in w else w) for s, w in zip(scenes, words)}
    story = put_structure(repo, story.id, structure, bindings, repo.get_story(story.id).revision)
    write_memory(repo, story.id, events)
    return repo, repo.get_story(story.id), repo.list_scenes(story.id)


def write_memory(repo, story_id, events=None, *, only=None):
    """Memory for every scene (or the scene numbers in `only`) whose lineage has at most one head and no memory yet."""
    story = repo.get_story(story_id)
    scenes = repo.list_scenes(story_id)
    items = lineage_map(story, scenes)
    for n, scene in enumerate(scenes, 1):
        scene = repo.get_scene(scene.id)
        if scene.heads.get('memory') or items[scene.id].needs_merge or (only and n not in only):
            continue
        heads = items[scene.id].heads
        previous = load_memory(repo.read_text(repo.get_scene(heads[0]).heads['memory'])) if heads else MemoryJournal()
        save_scene_journal(repo, scene, previous, (events or (lambda n, p, prev: [fact(f'Подія сцени {n}', p)]))(n, scene.heads['prose'], previous))


def save_scene_journal(repo, scene, previous, new_events, refs=()):
    journal = _extend(previous, scene.heads['prose'], new_events, 3)
    memory = repo.save_version(scene.story_id, scene.id, 'memory', journal.model_dump_json(), list(journal.source_prose_ids) + list(refs))
    repo.set_head(scene.id, 'memory', memory.id, repo.get_scene(scene.id).revision)
    return memory
