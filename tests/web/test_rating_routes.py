import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import SceneCreate, StoryCreate
from storygen.web.app import create_app

pytestmark = pytest.mark.unrated_stories

R = {"sexual": 1, "violence": 0, "themes": 2}


def make(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path / "data", env_file=tmp_path / "absent.env"))
    client = TestClient(app, base_url="http://127.0.0.1")
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title="Твір"))
    scene = repo.create_scene(story.id, SceneCreate(title="Сцена"))
    return client, repo, repo.get_story(story.id), scene


def test_put_story_rating_roundtrip(tmp_path):
    client, repo, story, _ = make(tmp_path)
    assert story.content_rating is None
    response = client.put(f"/api/stories/{story.id}/content-rating", json={"content_rating": R, "expected_revision": story.revision})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["content_rating"] == R and body["initial_content_rating"] == R
    assert body["revision"] == story.revision + 1
    again = client.put(f"/api/stories/{story.id}/content-rating", json={"content_rating": {"sexual": 0, "violence": 0, "themes": 0}, "expected_revision": body["revision"]}).json()
    assert again["content_rating"]["sexual"] == 0 and again["initial_content_rating"] == R


def test_put_story_rating_null_rejected(tmp_path):
    client, repo, story, _ = make(tmp_path)
    for payload in ({"content_rating": None, "expected_revision": story.revision}, {"expected_revision": story.revision},
                    {"content_rating": {"sexual": 3, "violence": 0, "themes": 0}, "expected_revision": story.revision}):
        assert client.put(f"/api/stories/{story.id}/content-rating", json=payload).status_code == 422
    assert repo.get_story(story.id).content_rating is None


def test_put_scene_rating_and_reset(tmp_path):
    client, repo, story, scene = make(tmp_path)
    url = f"/api/scenes/{scene.id}/content-rating"
    response = client.put(url, json={"story_id": story.id, "content_rating": R, "expected_revision": scene.revision})
    assert response.status_code == 200, response.text
    assert response.json()["content_rating"] == R
    revision = response.json()["revision"]
    reset = client.put(url, json={"story_id": story.id, "content_rating": None, "expected_revision": revision})
    assert reset.status_code == 200, reset.text
    assert reset.json()["content_rating"] is None


def test_scene_rating_wrong_story_rejected(tmp_path):
    client, repo, story, scene = make(tmp_path)
    other = repo.create_story(StoryCreate(title="Інший"))
    response = client.put(f"/api/scenes/{scene.id}/content-rating", json={"story_id": other.id, "content_rating": R, "expected_revision": scene.revision})
    assert response.status_code == 400
    assert repo.get_scene(scene.id).content_rating is None
    assert client.put("/api/scenes/missing/content-rating", json={"story_id": story.id, "content_rating": R, "expected_revision": 0}).status_code == 404


def test_rating_conflict_returns_409(tmp_path):
    client, repo, story, scene = make(tmp_path)
    assert client.put(f"/api/stories/{story.id}/content-rating", json={"content_rating": R, "expected_revision": story.revision + 5}).status_code == 409
    assert client.put(f"/api/scenes/{scene.id}/content-rating", json={"story_id": story.id, "content_rating": R, "expected_revision": scene.revision + 5}).status_code == 409
