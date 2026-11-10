"""STORY-LANGUAGE-S01: story language is fixed after the first model output; scene prose language is free (#32)."""
import json

import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import RevisionConflict, SceneCreate, StoryCreate
from storygen.language import prose_language
from storygen.web.app import create_app


def setup(tmp_path):
    client = TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765')
    repo = client.app.state.repo
    story = repo.create_story(StoryCreate(title='Tide'))
    scene = repo.create_scene(story.id, SceneCreate(title='Arrival', beats='They arrive.'))
    return client, repo, story, scene


@pytest.mark.req('STORY-LANGUAGE')
def test_story_defaults_to_ukrainian(tmp_path):
    _, repo, story, _ = setup(tmp_path)
    assert story.language == 'uk'
    with repo.db.connection() as db:
        payload = json.loads(db.execute('SELECT payload FROM stories WHERE id=?', (story.id,)).fetchone()[0])
        payload.pop('language', None)
        db.execute('UPDATE stories SET payload=? WHERE id=?', (json.dumps(payload), story.id))
    assert repo.get_story(story.id).language == 'uk'


@pytest.mark.req('STORY-LANGUAGE')
def test_language_changes_before_generation(tmp_path):
    client, repo, story, _ = setup(tmp_path)
    story = repo.get_story(story.id)
    response = client.put(f'/api/stories/{story.id}/language', json={'language': 'en', 'expected_revision': story.revision})
    assert response.status_code == 200
    changed = repo.get_story(story.id)
    assert changed.language == 'en' and changed.revision == story.revision + 1


@pytest.mark.req('STORY-LANGUAGE')
def test_language_locked_after_model_version(tmp_path):
    client, repo, story, scene = setup(tmp_path)
    repo.save_version(story.id, scene.id, 'brief', 'Brief', [], source_run_id='run-1')
    story = repo.get_story(story.id)
    with pytest.raises(RevisionConflict):
        repo.update_story_language(story.id, 'en', story.revision)
    response = client.put(f'/api/stories/{story.id}/language', json={'language': 'en', 'expected_revision': story.revision})
    assert response.status_code == 409
    assert repo.get_story(story.id).language == 'uk'
    client.cookies.set('obscura_locale', 'en')
    english = client.put(f'/api/stories/{story.id}/language', json={'language': 'en', 'expected_revision': story.revision})
    assert 'story language is fixed' in english.text


@pytest.mark.req('STORY-LANGUAGE')
def test_author_material_does_not_lock_language(tmp_path):
    _, repo, story, scene = setup(tmp_path)
    repo.save_version(story.id, scene.id, 'manual', 'Author text', [])
    assert repo.update_story_language(story.id, 'en', repo.get_story(story.id).revision).language == 'en'


@pytest.mark.req('STORY-LANGUAGE')
def test_same_language_is_idempotent_when_locked(tmp_path):
    _, repo, story, scene = setup(tmp_path)
    repo.save_version(story.id, scene.id, 'brief', 'Brief', [], source_run_id='run-1')
    story = repo.get_story(story.id)
    assert repo.update_story_language(story.id, 'uk', story.revision).revision == story.revision


@pytest.mark.req('STORY-LANGUAGE')
def test_scene_prose_language_patch(tmp_path):
    client, repo, story, scene = setup(tmp_path)
    brief = repo.save_version(story.id, scene.id, 'brief', 'Brief', [], source_run_id='run-1')
    repo.set_head(scene.id, 'brief', brief.id, repo.get_scene(scene.id).revision)

    def patch(**fields):
        current = repo.get_scene(scene.id)
        response = client.patch(f'/api/scenes/{scene.id}', json={'story_id': story.id, 'expected_revision': current.revision, **fields})
        assert response.status_code == 200, response.text
        return repo.get_scene(scene.id)

    assert patch(prose_language='en').prose_language == 'en'
    assert not repo.get_version(brief.id).stale
    assert patch(title='Arrival again').prose_language == 'en'
    assert patch(prose_language='story').prose_language is None


@pytest.mark.req('STORY-LANGUAGE')
def test_prose_language_helper(tmp_path):
    _, repo, story, scene = setup(tmp_path)
    english = story.model_copy(update={'language': 'en'})
    assert prose_language(english, scene) == 'en'
    assert prose_language(story, scene.model_copy(update={'prose_language': 'en'})) == 'en'
    assert prose_language(story, None) == 'uk'
