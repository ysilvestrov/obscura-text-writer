import json

import pytest

from storygen.domain import StoryCreate
from storygen.publication.genres import genre_catalog
from storygen.role_profiles import capture_profile, export_profile, parse_profile, preview_profile
from storygen.storage.repository import Repository
from tests.authoring.test_role_profiles import seeded


@pytest.mark.req('STORY-LANGUAGE')
def test_english_genre_labels_cover_every_code():
    uk, en = dict(genre_catalog('uk')), dict(genre_catalog('en'))
    assert list(uk) == list(en)
    assert all(label.isascii() and label for label in en.values())
    assert dict(genre_catalog()) == uk and en['sf_fantasy'] == 'Fantasy'


@pytest.mark.req('STORY-LANGUAGE')
def test_english_metadata_request_uses_english_genre_labels():
    from storygen.generation.publication_metadata import catalog_for
    assert catalog_for('en')['sf_fantasy'] == 'Fantasy'
    assert catalog_for('uk')['sf_fantasy'] == 'Фентезі'


@pytest.mark.req('STORY-LANGUAGE')
def test_unsaved_card_defaults_to_story_language(tmp_path):
    repo = Repository(tmp_path)
    english = repo.create_story(StoryCreate(title='Pier', language='en'))
    ukrainian = repo.create_story(StoryCreate(title='Маяк'))
    assert repo.publication('get_card', story_id=english.id).card.language == 'en'
    assert repo.publication('get_card', story_id=ukrainian.id).card.language == 'uk'


@pytest.mark.req('STORY-LANGUAGE')
def test_profile_carries_story_language_and_warns_on_mismatch(tmp_path):
    repo, source, _ = seeded(tmp_path)
    saved = capture_profile(repo, source.id, 'Local', source.revision)
    assert json.loads(export_profile(repo, saved['id'], 1))['language'] == 'uk'
    target = repo.create_story(StoryCreate(title='Pier', language='en'))
    warnings = preview_profile(repo, target.id, saved['id'], 1, target.revision)['warnings']
    assert any('uk' in w and 'en' in w for w in warnings)
    same = repo.create_story(StoryCreate(title='Маяк'))
    assert preview_profile(repo, same.id, saved['id'], 1, same.revision)['warnings'] == []


@pytest.mark.req('STORY-LANGUAGE')
def test_old_profile_without_language_imports_without_warning(tmp_path):
    repo, source, _ = seeded(tmp_path)
    saved = capture_profile(repo, source.id, 'Local', source.revision)
    document = json.loads(export_profile(repo, saved['id'], 1))
    del document['language']
    assert parse_profile(json.dumps(document)).language is None


@pytest.mark.req('R24-MESSAGES')
def test_profile_language_warning_is_localized():
    from storygen.web.localization import diagnostic
    text = 'Комплект зроблено для твору мовою uk, а цей твір має мову en; власні промпти не перекладаються.'
    assert diagnostic(text, 'en') == 'The profile was made for a story in uk, but this story is in en; custom prompts are not translated.'
