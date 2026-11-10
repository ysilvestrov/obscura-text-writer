import pytest

from storygen.copyediting import protected_negations
from storygen.domain import SceneCreate, StoryCreate
from storygen.generation.language import language_warnings
from storygen.web.localization import diagnostic


@pytest.mark.req('LANGUAGE-WARNINGS')
def test_english_prose_gets_only_language_neutral_hints():
    codes = {w['code'] for w in language_warnings('- Hello the the world ыы', 'en')}
    assert codes == {'repeated_word'}


@pytest.mark.req('LANGUAGE-WARNINGS')
def test_ukrainian_default_unchanged():
    text = '- Привіт привіт ы'
    assert language_warnings(text) == language_warnings(text, 'uk')
    assert {'dialogue_dash', 'non_ukrainian_letters', 'repeated_word'} <= {w['code'] for w in language_warnings(text)}


@pytest.mark.req('LANGUAGE-WARNINGS')
def test_version_language_check_follows_scene_prose_language(tmp_path):
    from fastapi.testclient import TestClient
    from storygen.application.settings import AppSettings
    from storygen.web.app import create_app
    app = create_app(AppSettings(data_dir=tmp_path))
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк'))
    scene = repo.create_scene(story.id, SceneCreate(title='Pier', beats='x'))
    scene = repo.update_scene_metadata(scene.id, {'prose_language': 'en'}, scene.revision)
    ref = repo.save_version(story.id, scene.id, 'manual', '- Hello there.', [])
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        warnings = client.get(f'/api/versions/{ref.id}/language-warnings').json()['warnings']
    assert repo.get_scene(scene.id).prose_language == 'en'
    assert 'dialogue_dash' not in {w['code'] for w in warnings}


@pytest.mark.req('STORY-LANGUAGE')
def test_cannot_is_protected_negation():
    assert 'cannot' in protected_negations('She cannot go.')


@pytest.mark.req('R24-MESSAGES')
def test_story_changed_conflicts_are_localized():
    assert diagnostic('Твір уже змінено', 'en') != 'Твір уже змінено'
    assert diagnostic('Твір уже змінено. Оновіть таблицю; тип запису не збережено.', 'en').isascii()
