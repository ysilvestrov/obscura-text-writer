import pytest

from storygen.characters.acquaintance import is_protagonist_line, known_names_line
from storygen.domain import StoryCreate
from storygen.memory.story_time import START
from storygen.plan_sections import split_plan
from storygen.scene_description import explicit_scene_number, parse_scene_description


@pytest.mark.req('STORY-LANGUAGE')
def test_english_scene_headings_split_plan_with_author_numbers():
    _, sections = split_plan('Scene 1: Arrival\nAnna arrives.\n\nScene 2: Departure\nAnna leaves.')
    assert [(s.title, s.author_scene_number) for s in sections] == [('Arrival', 1), ('Departure', 2)]


@pytest.mark.req('STORY-LANGUAGE')
def test_scene_number_accepts_both_languages():
    assert explicit_scene_number('## Scene 3. Pier') == 3
    assert explicit_scene_number('**Сцена 4:** Маяк') == 4


@pytest.mark.req('STORY-LANGUAGE')
def test_unheaded_plan_uses_language_default_title():
    assert split_plan('Free plan', default_title='Scene')[1][0].title == 'Scene 1'
    assert split_plan('Довільний план')[1][0].title == 'Сцена 1'


@pytest.mark.req('STORY-LANGUAGE')
def test_english_participants_and_start_line():
    assert parse_scene_description('Scene 1: A\nCharacters: Anna, Bob').participants == ['Anna', 'Bob']
    assert parse_scene_description('Scene 1: A\n- Participants: Anna').participants == ['Anna']
    assert parse_scene_description('Scene 1: Arrival').title == 'Arrival'
    match = START.match('Start: day 2, 23:40')
    assert match and match.group(2) == '2'


@pytest.mark.req('STORY-LANGUAGE')
def test_english_protagonist_and_acquaintance_markers():
    assert is_protagonist_line('Protagonist')
    assert is_protagonist_line('Role: Main character, sailor')
    assert is_protagonist_line('Role in the story: Protagonist')
    assert known_names_line('Knows: Bob, Clara') == ['Bob', 'Clara']
    assert known_names_line('Acquainted with: Bob') == ['Bob']
    assert is_protagonist_line('Протагоністка')
    assert known_names_line('Знайома з: Анна') == ['Анна']
    assert not is_protagonist_line('Role: friend of the protagonist')


@pytest.mark.req('STORY-LANGUAGE')
def test_english_story_import_names_unheaded_scene_in_english(tmp_path):
    from storygen.authoring.imports import SourceFile, import_sources
    from storygen.storage.repository import Repository
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Pier', language='en'))
    import_sources(repo, story.id, [SourceFile(name='plan.md', raw=b'Anna waits at the pier.', kind='source_plan')])
    assert [s.title for s in repo.list_scenes(story.id)] == ['Scene 1']


@pytest.mark.req('STORY-LANGUAGE')
def test_english_templates_import_scenes_cast_and_markers(tmp_path):
    from importlib.resources import files
    from storygen.authoring.imports import SourceFile, import_sources
    from storygen.characters.acquaintance import protagonist
    from storygen.characters.models import load_characters
    from storygen.storage.repository import Repository
    templates = files('storygen.web').joinpath('static', 'templates')
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Pier', language='en'))
    import_sources(repo, story.id, [
        SourceFile(name='characters.md', raw=templates.joinpath('characters-en.md').read_bytes(), kind='source_characters'),
        SourceFile(name='plan.md', raw=templates.joinpath('story-plan-en.md').read_bytes(), kind='source_plan')])
    scenes = repo.list_scenes(story.id)
    assert [(s.title, s.author_scene_number) for s in scenes] == [('The meeting', 1), ('A night conversation', 2)]
    assert all(len(s.character_ids) == 2 for s in scenes)
    story = repo.get_story(story.id)
    cards = load_characters(repo.read_text(story.characters_version_id))
    assert [c.name for c in cards if c.id == protagonist(cards, scenes)[0]] == ['Helen']
    assert known_names_line('Knows at the start: the harbour') is None
