"""A long story with prose and cumulative memory journals for timeline summary tests (neutral text, no private data)."""
from storygen.domain import SceneCreate, StoryCreate
from storygen.memory.journal import MemoryJournal, _add_event
from storygen.storage.repository import Repository


def long_story(root, count, memory_until=None, *, timeline_text=None, language='uk'):
    """`count` scenes with manual prose; scenes 1..memory_until (default: all) get memory whose journal holds one timeline
    entry per scene so far. `timeline_text(n)` sets the entry of scene n."""
    repo = Repository(root)
    story = repo.create_story(StoryCreate(title='Довга книга', language=language))
    prose_ids, events, previous = [], [], None
    for n in range(1, count + 1):
        scene = repo.create_scene(story.id, SceneCreate(title=f'Сцена {n}', beats='Анна йде містом.'))
        prose = repo.save_version(story.id, scene.id, 'manual', f'Сцена {n}. Анна йде містом.', [])
        repo.set_head(scene.id, 'prose', prose.id, repo.get_scene(scene.id).revision)
        prose_ids.append(prose.id)
        if n > (count if memory_until is None else memory_until):
            continue
        text = timeline_text(n) if timeline_text else f'Подія сцени {n}: Анна пройшла вулицю номер {n}'
        events = events + [_add_event('timeline', text, prose.id, 'Анна йде містом', 0)]
        journal = MemoryJournal(schema_version=3, source_prose_ids=list(prose_ids), events=events)
        refs = list(prose_ids) + ([previous] if previous else [])
        memory = repo.save_version(story.id, scene.id, 'memory', journal.model_dump_json(), refs)
        repo.set_head(scene.id, 'memory', memory.id, repo.get_scene(scene.id).revision)
        previous = memory.id
    return repo, repo.get_story(story.id)
