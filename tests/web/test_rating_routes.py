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


def test_story_view_reports_effective_ratings(tmp_path):
    client, repo, story, scene = make(tmp_path)
    other = repo.create_scene(story.id, SceneCreate(title="Друга"))
    assert client.put(f"/api/stories/{story.id}/content-rating", json={"content_rating": {"sexual": 1, "violence": 0, "themes": 0}, "expected_revision": repo.get_story(story.id).revision}).status_code == 200
    own = {"sexual": 0, "violence": 2, "themes": 0}
    put = client.put(f"/api/scenes/{scene.id}/content-rating", json={"story_id": story.id, "content_rating": own, "expected_revision": scene.revision})
    assert put.status_code == 200, put.text
    view = client.get(f"/api/stories/{story.id}").json()
    assert view["scene_ratings"][scene.id] == {"effective": own, "source": "scene"}
    assert view["scene_ratings"][other.id] == {"effective": {"sexual": 1, "violence": 0, "themes": 0}, "source": "story"}
    stale = client.put(f"/api/scenes/{scene.id}/content-rating", json={"story_id": story.id, "content_rating": None, "expected_revision": scene.revision})
    assert stale.status_code == 409


def test_story_view_unrated_story_has_no_effective_rating(tmp_path):
    client, repo, story, scene = make(tmp_path)
    view = client.get(f"/api/stories/{story.id}").json()
    assert view["scene_ratings"] == {scene.id: {"effective": None, "source": None}}


def test_store_edition_put_level_two_is_400_with_translation(tmp_path, store_edition):
    client, repo, story, _ = make(tmp_path)
    body = {"content_rating": {"sexual": 2, "violence": 0, "themes": 0}, "expected_revision": story.revision}
    response = client.put(f"/api/stories/{story.id}/content-rating", json=body)
    assert response.status_code == 400
    assert response.json()["detail"] == "Некоректні дані: У цьому виданні Obscura рівень 2 для осі «сексуальний зміст» недоступний: найвищий дозволений — 1."
    english = client.put(f"/api/stories/{story.id}/content-rating", json=body, headers={"accept-language": "en"})
    assert english.json()["detail"] == "Invalid data: In this edition of Obscura, level 2 is not available for “sexual content”: the highest allowed is 1."
    assert repo.get_story(story.id).content_rating is None


def test_store_edition_put_scene_level_two_is_400(tmp_path, store_edition):
    client, repo, story, scene = make(tmp_path)
    story = client.put(f"/api/stories/{story.id}/content-rating", json={"content_rating": {"sexual": 0, "violence": 0, "themes": 0}, "expected_revision": story.revision}).json()
    scene = repo.get_scene(scene.id)
    body = {"story_id": story["id"], "content_rating": {"sexual": 2, "violence": 0, "themes": 0}, "expected_revision": scene.revision}
    response = client.put(f"/api/scenes/{scene.id}/content-rating", json=body)
    assert response.status_code == 400 and "найвищий дозволений — 1" in response.json()["detail"]
    assert repo.get_scene(scene.id).content_rating is None
    inherit = client.put(f"/api/scenes/{scene.id}/content-rating", json={**body, "content_rating": None})
    assert inherit.status_code == 200, inherit.text
