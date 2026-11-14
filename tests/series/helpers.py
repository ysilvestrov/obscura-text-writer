"""Neutral two-book fixtures for SERIES tests."""
import json

from storygen.domain import SceneCreate, StoryCreate
from storygen.memory.journal import MemoryJournal, _add_event
from storygen.storage import series as store

CARD_SOURCE = '# Анна\nАнна — лікарка.'


def publish_cards(repo, story, cards, source_text=None):
    refs = []
    if source_text:
        refs.append(repo.save_version(story.id, None, 'source_characters', source_text, []).id)
    saved = repo.save_version(story.id, None, 'character_cards', json.dumps(cards, ensure_ascii=False), refs)
    repo.publish_story_material(story.id, 'characters_version_id', saved.id, repo.get_story(story.id).revision)
    return refs[0] if refs else None


def card(id, name, entries=()):
    return {'id': id, 'schema_version': 2, 'name': name, 'entries': list(entries)}


def prose(repo, scene, text):
    version = repo.save_version(scene.story_id, scene.id, 'manual', text, [])
    repo.set_head(scene.id, 'prose', version.id, repo.get_scene(scene.id).revision)
    return version


def memory(repo, scene, previous, events):
    scene = repo.get_scene(scene.id)
    journal = MemoryJournal(schema_version=3, source_prose_ids=previous.source_prose_ids + [scene.heads['prose']],
                            events=previous.events + events)
    saved = repo.save_version(scene.story_id, scene.id, 'memory', journal.model_dump_json(), journal.source_prose_ids)
    repo.set_head(scene.id, 'memory', saved.id, repo.get_scene(scene.id).revision)
    return journal


def finished_book(repo, title='Книга 1'):
    """Two scenes with prose and memory: Anna's clothing (scene 1) and a fact (scene 2); card A with an entry available
    from scene 2, cited from a source_characters version."""
    story = repo.create_story(StoryCreate(title=title))
    s1, s2 = (repo.create_scene(story.id, SceneCreate(title=f'Сцена {n}', beats='Анна.', character_ids=[])) for n in (1, 2))
    source = repo.save_version(story.id, None, 'source_characters', CARD_SOURCE, [])
    entry = {'id': 'e1', 'text': 'Лікарка', 'availability': 'from_scene', 'available_from_scene_id': s2.id, 'origin': 'imported',
             'sources': [{'version_id': source.id, 'quote': 'Анна — лікарка.'}]}
    publish_cards(repo, story, [card('A', 'Анна', [entry])])
    p1 = prose(repo, s1, 'Анна в халаті. Вона мовчить.')
    cloth = _add_event('character_states', 'Халат', p1.id, 'Анна в халаті.', 0, ['A'], slot='clothing')
    first = memory(repo, s1, MemoryJournal(schema_version=3), [cloth])
    p2 = prose(repo, s2, 'Сусід пішов додому.')
    memory(repo, s2, first, [_add_event('facts', 'Сусід пішов', p2.id, 'Сусід пішов додому.', 0)])
    return repo.get_story(story.id), [repo.get_scene(s.id) for s in (s1, s2)], cloth


def book(repo, title, *, written=True):
    story = repo.create_story(StoryCreate(title=title))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена 1', beats='Анна.'))
    if written:
        prose(repo, scene, 'Анна вийшла.')
    return repo.get_story(story.id), repo.get_scene(scene.id)


def into_series(repo, story, series_id, number):
    return store.set_story_series(repo, story.id, series_id, number, None, repo.get_story(story.id).revision)
