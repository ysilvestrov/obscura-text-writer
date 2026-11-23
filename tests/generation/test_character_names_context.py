"""CHARACTER-NAMES-S02 (#215): requests for a scene name a character by the name current there."""
import json

import pytest

from storygen.domain import SceneCreate, SceneNarrator, StoryCreate
from storygen.generation.context import build_context
from storygen.generation.models import StyleProfile
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage.repository import Repository
from tests.link_helpers import approve_links


def role():
    return RoleSettings(provider=ProviderSettings(model='fake'), context_tokens=262144)


def entry(id, text, anchor=None):
    return {'id': id, 'text': text, 'availability': 'from_scene' if anchor else 'timeless',
            'available_from_scene_id': anchor, 'origin': 'author', 'sources': []}


def setup(tmp_path, language='uk'):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Ферма', language=language))
    style = repo.save_version(story.id, None, 'style', StyleProfile().model_dump_json(), [])
    repo.publish_story_material(story.id, 'style_version_id', style.id, repo.get_story(story.id).revision)
    scenes = [repo.create_scene(story.id, SceneCreate(title=title, beats=f'Хто бере участь: Юлія, Хазяїн\n{beat}'))
              for title, beat in (('Ворота', 'Юлія приходить на ферму.'), ('Двір', 'Юлія чує його ім’я.'), ('Кухня', 'Вечеря.'))]
    cards = [
        {'schema_version': 2, 'id': 'j', 'name': 'Юлія', 'entries': [entry('j1', 'Протагоністка')]},
        {'schema_version': 2, 'id': 'h', 'name': 'Хазяїн', 'entries': [
            entry('h1', 'Вік: 40'), entry('h2', 'Інше ім\'я: Бос'), entry('h3', 'Інше ім\'я: Джон', scenes[1].id)]},
    ]
    ref = repo.save_version(story.id, None, 'character_cards', json.dumps(cards, ensure_ascii=False), [])
    repo.publish_story_material(story.id, 'characters_version_id', ref.id, repo.get_story(story.id).revision)
    scenes = [repo.get_scene(scene.id) for scene in scenes]
    for scene in scenes:
        repo.update_scene_metadata(scene.id, {'narrator': SceneNarrator(person='third_limited', character_id='h')}, scene.revision)
    return repo, [repo.get_scene(scene.id) for scene in scenes]


def remember(repo, scenes, upto, events=lambda prose: []):
    """Prose for scenes[0..upto] and the memory of scenes[upto] over them; events(prose ids) gives its journal."""
    from storygen.memory.journal import MemoryJournal
    story_id = scenes[0].story_id
    prose = []
    for scene in scenes[:upto + 1]:
        ref = repo.save_version(story_id, scene.id, 'manual', 'Юлія йде.', [])
        repo.set_head(scene.id, 'prose', ref.id, repo.get_scene(scene.id).revision)
        prose.append(ref.id)
    journal = MemoryJournal(schema_version=3, source_prose_ids=prose, events=events(prose))
    memory = repo.save_version(story_id, scenes[upto].id, 'memory', journal.model_dump_json(), prose)
    repo.set_head(scenes[upto].id, 'memory', memory.id, repo.get_scene(scenes[upto].id).revision)
    approve_links(repo, story_id)
    return [repo.get_scene(scene.id) for scene in scenes]


@pytest.mark.req('CHARACTER-NAMES')
def test_brief_before_and_after_the_rename(tmp_path):
    repo, scenes = setup(tmp_path)
    assert all(scene.character_ids == ['j', 'h'] for scene in scenes)
    early = build_context(repo, scenes[0].id, 'brief', role()).user_text
    assert 'ПЕРСОНАЖ: Хазяїн (також: Бос)\n' in early
    assert 'Джон' not in early
    assert 'Третя особа через героя: Хазяїн' in early
    scenes = remember(repo, scenes, 0)
    later = build_context(repo, scenes[1].id, 'brief', role()).user_text
    assert 'ПЕРСОНАЖ: Джон (також: Хазяїн, Бос)\n' in later
    assert 'Третя особа через героя: Джон' in later
    assert 'ЗНАЙОМСТВА ГОЛОВНОГО ГЕРОЯ — Юлія\nЗнайомі: Джон (зі сцени 1)\n' in later


@pytest.mark.req('CHARACTER-NAMES')
def test_english_story_uses_also(tmp_path):
    repo, scenes = setup(tmp_path, language='en')
    scenes = remember(repo, scenes, 1)
    assert 'CHARACTER: Джон (also: Хазяїн, Бос)\n' in build_context(repo, scenes[2].id, 'brief', role()).user_text


@pytest.mark.req('CHARACTER-NAMES')
def test_cards_without_markers_keep_the_card_name_and_no_also(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Ферма'))
    style = repo.save_version(story.id, None, 'style', StyleProfile().model_dump_json(), [])
    repo.publish_story_material(story.id, 'style_version_id', style.id, repo.get_story(story.id).revision)
    cards = [{'schema_version': 2, 'id': 'h', 'name': 'Хазяїн', 'entries': [entry('h1', 'Вік: 40')]}]
    ref = repo.save_version(story.id, None, 'character_cards', json.dumps(cards, ensure_ascii=False), [])
    repo.publish_story_material(story.id, 'characters_version_id', ref.id, repo.get_story(story.id).revision)
    scene = repo.create_scene(story.id, SceneCreate(title='Ворота', beats='Хто бере участь: Хазяїн\nВорота.'))
    text = build_context(repo, scene.id, 'brief', role()).user_text
    assert 'ПЕРСОНАЖ: Хазяїн\nПОЗАЧАСОВІ ВІДОМОСТІ\n— Вік: 40' in text and 'також' not in text
