"""MEMORY-LOCATIONS-S08 (R-51, spec 2, amendment 2): the author removes a place a model gave a scene in the «Locations»
panel; places from the plan line are changed in the plan."""
import json

import pytest

from storygen.domain import SceneCreate
from tests.storage.test_story_locations import set_model_places
from tests.web.test_locations_api import base, card, lid, setup


def model_book(tmp_path):
    """Scene «Ніч» without a plan place holds three model places: «Маяк», «Пірс» and «Маяк » (the typo card, merged into
    «Маяк»); scenes «Ранок» and «Вечір» have plan places."""
    client, repo, story, first, second = setup(tmp_path)
    night = repo.create_scene(story.id, SceneCreate(title='Ніч', beats='Дії: тиша.', character_ids=[]))
    from storygen.storage import locations as store
    with repo.db.connection() as db:
        store.ensure_locations(db, story.id, [('Маяк',), ('Пірс',), ('Маякк',)])
        store.merge_location(db, story.id, lid(story, 'Маякк'), lid(story, 'Маяк'))
    repo.db.bump_generation()
    set_model_places(repo, night.id, [lid(story, 'Маяк'), lid(story, 'Пірс'), lid(story, 'Маякк')])
    return client, repo, repo.get_story(story.id), first, repo.get_scene(night.id)


def stored(repo, story):
    """Every stored scene and version payload of the story: a refusal must leave all of them byte for byte."""
    with repo.db.connection() as db:
        return {table: dict(db.execute(f'SELECT id, payload FROM {table} WHERE story_id=?', (story.id,)).fetchall())
                for table in ('scenes', 'versions')}


def remove(client, story, location, scene, revision):
    return client.post(f'{base(story)}/{location}/remove-from-scene', json={'scene_id': scene, 'expected_revision': revision})


@pytest.mark.req('MEMORY-LOCATIONS')
def test_the_view_says_where_a_scene_place_comes_from(tmp_path):
    client, repo, story, first, night = model_book(tmp_path)
    data = client.get(base(story)).json()
    assert card(data, lid(story, 'Маяк'))['scenes'] == [{'id': night.id, 'position': 2, 'title': 'Ніч', 'source': 'model'}]
    assert card(data, lid(story, 'Квартира Джорджа', 'вітальня'))['scenes'] == [
        {'id': first.id, 'position': 0, 'title': 'Ранок', 'source': 'plan'}]


@pytest.mark.req('MEMORY-LOCATIONS')
def test_removing_a_model_place_drops_every_id_of_that_card(tmp_path):
    client, repo, story, first, night = model_book(tmp_path)
    response = remove(client, story, lid(story, 'Маяк'), night.id, story.revision)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['story_revision'] == story.revision + 1
    assert card(data, lid(story, 'Маяк'))['scenes'] == []
    scene = repo.get_scene(night.id)
    assert scene.location_ids == [lid(story, 'Пірс')]  # the merged typo card went with its target
    assert scene.location_source == 'model' and scene.revision == night.revision + 1


@pytest.mark.req('MEMORY-LOCATIONS')
def test_removing_the_last_place_returns_the_scene_to_the_plan_source(tmp_path):
    client, repo, story, first, night = model_book(tmp_path)
    rev = remove(client, story, lid(story, 'Маяк'), night.id, story.revision).json()['story_revision']
    assert remove(client, story, lid(story, 'Пірс'), night.id, rev).status_code == 200
    scene = repo.get_scene(night.id)
    assert scene.location_ids == [] and scene.location_source == 'plan'
    with repo.db.connection() as db:  # an older build reads the scene again
        assert 'location_source' not in json.loads(db.execute('SELECT payload FROM scenes WHERE id=?', (night.id,)).fetchone()[0])


@pytest.mark.req('MEMORY-LOCATIONS')
@pytest.mark.parametrize('case,message', [
    ('plan', 'Місце сцени з плану: змініть рядок «Локація:»'),
    ('not_held', 'Сцена не має цього місця'),
    ('unknown_card', 'Невідома локація'),
    ('unknown_scene', 'Невідома сцена'),
    ('trashed', 'Невідома сцена'),
])
def test_refusals_change_nothing(tmp_path, case, message):
    client, repo, story, first, night = model_book(tmp_path)
    location, scene = lid(story, 'Маяк'), night.id
    if case == 'plan':
        location, scene = lid(story, 'Квартира Джорджа', 'вітальня'), first.id
    elif case == 'not_held':
        location = lid(story, 'двір')
    elif case == 'unknown_card':
        location = 'loc_0000000000000000'
    elif case == 'unknown_scene':
        scene = 'missing'
    else:
        repo.set_scene_trashed(story.id, night.id, night.revision, False)
    story = repo.get_story(story.id)
    before = stored(repo, story)
    response = remove(client, story, location, scene, story.revision)
    assert response.status_code == 400 and message in response.text
    assert repo.get_story(story.id).revision == story.revision and stored(repo, story) == before


@pytest.mark.req('MEMORY-LOCATIONS')
def test_removal_stales_the_scene_material_and_names_the_scene_as_dependent(tmp_path):
    """As accepting places: material built before snapshots goes stale; the scene with a brief
    is offered to the author for the link decision (VALID-LINKS, rule (г))."""
    client, repo, story, first, night = model_book(tmp_path)
    brief = repo.save_version(story.id, night.id, 'brief', '{}', [])
    repo.set_head(night.id, 'brief', brief.id, repo.get_scene(night.id).revision)
    story = repo.get_story(story.id)
    data = remove(client, story, lid(story, 'Маяк'), night.id, story.revision).json()
    assert data['dependent_scene_ids'] == [night.id]
    with repo.db.connection() as db:  # the stored flag; a head's shown mark comes from its link (VALID-LINKS)
        assert json.loads(db.execute('SELECT payload FROM versions WHERE id=?', (brief.id,)).fetchone()[0])['stale'] is True


@pytest.mark.req('MEMORY-LOCATIONS')
def test_a_stale_revision_is_a_conflict(tmp_path):
    client, repo, story, first, night = model_book(tmp_path)
    before = stored(repo, story)
    assert remove(client, story, lid(story, 'Маяк'), night.id, story.revision - 1).status_code == 409
    assert stored(repo, story) == before
