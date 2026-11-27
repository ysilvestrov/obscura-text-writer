"""MEMORY-LOCATIONS-S10: the glue and unglue API of the «Locations» panel."""
import json

import pytest

from storygen.domain import SceneCreate
from tests.web.test_locations_api import base, lid, setup

PHRASE = 'бар, в якому пахне кавою'


def cafe_book(tmp_path):
    """The usual two scenes plus «Кава» with «Локація: Бар, в якому пахне кавою, вулиця» and a brief head."""
    client, repo, story, first, second = setup(tmp_path)
    cafe = repo.create_scene(story.id, SceneCreate(title='Кава', beats='Локація: Бар, в якому пахне кавою, вулиця', character_ids=[]))
    brief = repo.save_version(story.id, cafe.id, 'brief', 'завдання', [])
    with repo.db.connection() as db:
        row = json.loads(db.execute('SELECT payload FROM scenes WHERE id=?', (cafe.id,)).fetchone()[0])
        row['heads']['brief'] = brief.id
        db.execute('UPDATE scenes SET payload=? WHERE id=?', (json.dumps(row, ensure_ascii=False), cafe.id))
    repo.db.bump_generation()
    return client, repo, repo.get_story(story.id), repo.get_scene(cafe.id)


def stored(repo, story):
    with repo.db.connection() as db:
        return {'stories': db.execute('SELECT payload FROM stories WHERE id=?', (story.id,)).fetchone()[0],
                'scenes': dict(db.execute('SELECT id, payload FROM scenes WHERE story_id=?', (story.id,)).fetchall())}


@pytest.mark.req('MEMORY-LOCATIONS')
def test_glue_api_returns_view_and_dependent_scenes(tmp_path):
    client, repo, story, cafe = cafe_book(tmp_path)
    response = client.post(f'{base(story)}/glue', json={'phrase': PHRASE, 'expected_revision': story.revision})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['glues'] == [{'key': PHRASE, 'phrase': PHRASE}]
    assert data['story_revision'] == story.revision + 1
    assert cafe.id in data['dependent_scene_ids']
    assert repo.get_scene(cafe.id).location_ids[0] == lid(story, 'Бар, в якому пахне кавою')


@pytest.mark.req('MEMORY-LOCATIONS')
def test_glue_api_conflict_changes_nothing(tmp_path):
    client, repo, story, cafe = cafe_book(tmp_path)
    before = stored(repo, story)
    response = client.post(f'{base(story)}/glue', json={'phrase': PHRASE, 'expected_revision': story.revision - 1})
    assert response.status_code == 409
    assert stored(repo, story) == before


@pytest.mark.req('MEMORY-LOCATIONS')
def test_glue_api_validation(tmp_path):
    client, repo, story, cafe = cafe_book(tmp_path)
    before = stored(repo, story)
    response = client.post(f'{base(story)}/glue', json={'phrase': 'Місто / бар, кава', 'expected_revision': story.revision})
    assert response.status_code == 400 and 'без «/»' in response.text
    assert client.post(f'{base(story)}/glue', json={'expected_revision': story.revision}).status_code == 422
    assert client.post(f'{base(story)}/glue', json={'phrase': 'х' * 401, 'expected_revision': story.revision}).status_code == 422
    assert stored(repo, story) == before


@pytest.mark.req('MEMORY-LOCATIONS')
def test_unglue_api(tmp_path):
    client, repo, story, cafe = cafe_book(tmp_path)
    revision = client.post(f'{base(story)}/glue', json={'phrase': PHRASE, 'expected_revision': story.revision}).json()['story_revision']
    assert client.post(f'{base(story)}/unglue', json={'key': 'нема', 'expected_revision': revision}).status_code == 400
    response = client.post(f'{base(story)}/unglue', json={'key': PHRASE, 'expected_revision': revision})
    assert response.status_code == 200 and response.json()['glues'] == []
    assert repo.get_scene(cafe.id).location_ids[0] == lid(story, 'Бар')
