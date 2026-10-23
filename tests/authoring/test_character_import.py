import pytest
from storygen.authoring.imports import SourceFile,import_sources
from storygen.domain import StoryCreate
from storygen.storage.repository import Repository
from storygen.characters.models import load_characters

TEXT="""## Персонажі

## Олена
Фотографка. Точний опис.

### Звички
Любить ранкову каву.

## Наталя:
Сестра Олени.
"""
PLAN='Сцена 1: Дзвінок\nХто бере участь: Олена, Наталя.'


@pytest.mark.parametrize('characters_first',[False,True])
def test_character_import_creates_proven_cards_and_fills_scene_cast(tmp_path,characters_first):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Твір'))
    files=[SourceFile(name='plan.md',raw=PLAN.encode()),SourceFile(name='characters.md',raw=TEXT.encode(),kind='source_characters')]
    if characters_first:files.reverse()
    result=import_sources(repo,story.id,files)
    actual=repo.get_story(story.id)
    assert actual.characters_version_id is not None
    cards=load_characters(repo.read_text(actual.characters_version_id))
    assert [c.name for c in cards]==['Олена','Наталя']
    assert '### Звички' in cards[0].entries[0].text
    for card in cards:
        entry=card.entries[0]
        assert entry.availability=='unclassified' and entry.origin=='imported'
        assert entry.text==entry.sources[0].quote
        assert entry.text in repo.read_text(entry.sources[0].version_id)
    assert repo.list_scenes(story.id)[0].character_ids==[c.id for c in cards]
    assert result.created_character_cards==2


def test_existing_cards_never_overwritten_on_reimport(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Твір'))
    import_sources(repo,story.id,[SourceFile(name='chars.md',raw=TEXT.encode(),kind='source_characters')])
    original=repo.get_story(story.id).characters_version_id
    result=import_sources(repo,story.id,[SourceFile(name='changed.md',raw='## Інший\nНовий опис.'.encode(),kind='source_characters')])
    assert repo.get_story(story.id).characters_version_id==original
    assert result.created_character_cards==0 and any('не перезаписано' in w for w in result.warnings)


def test_unstructured_source_kept_with_actionable_warning(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Твір'))
    result=import_sources(repo,story.id,[SourceFile(name='chars.txt',raw='Просто опис без заголовків.'.encode(),kind='source_characters')])
    assert repo.get_story(story.id).characters_version_id is None
    assert any('заголовк' in w for w in result.warnings)


def test_mixed_alphabet_warning_does_not_guess_name():
    from storygen.characters.importing import cards_from_markdown
    cards,warnings=cards_from_markdown('## Cлужанки:\nТочний опис.','source')
    assert cards[0]['name']=='Cлужанки'
    assert any('латин' in warning and 'кирил' in warning for warning in warnings)
