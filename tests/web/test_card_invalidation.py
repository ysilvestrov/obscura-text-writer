"""Card and location changes report the dependent scenes; only the author's POST /links/invalidate unchecks their links."""
import pytest
from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.domain import SceneCreate
from storygen.locations import location_id, normalize
from storygen.web.app import create_app
from tests.storage.test_links import book, save_manual_brief


def client_for(tmp_path):
    return TestClient(create_app(AppSettings(data_dir=tmp_path, env_file=tmp_path / 'absent.env')), base_url='http://127.0.0.1:8765')


def save_cards(client, story_id, cards):
    revision = client.get(f'/api/stories/{story_id}/characters').json()['revision']
    response = client.put(f'/api/stories/{story_id}/characters', json={'cards': cards, 'expected_revision': revision})
    assert response.status_code == 200, response.text
    return response.json()


def card(name, text):
    return {'id': None, 'schema_version': 2, 'name': name,
            'entries': [{'id': None, 'text': text, 'availability': 'timeless', 'available_from_scene_id': None,
                         'origin': 'author', 'sources': []}]}


def material_status(client, story_id, scene_id):
    return client.get(f'/api/stories/{story_id}').json()['material_status'][scene_id]


def cast(repo, scene_id, **changes):
    repo.update_scene_metadata(scene_id, changes, repo.get_scene(scene_id).revision)


@pytest.mark.req('VALID-CARDS')
def test_character_save_reports_changed_and_dependent(tmp_path):
    repo, story, scenes = book(tmp_path, 3)
    with client_for(tmp_path) as client:
        first = save_cards(client, story.id, [card('Олена', 'Бібліотекарка.'), card('Марко', 'Сторож.')])
        assert len(first['changed_character_ids']) == 2 and first['dependent_scene_ids'] == []
        olena, marko = (c['id'] for c in first['cards'])
        cast(repo, scenes[0].id, character_ids=[olena])
        cast(repo, scenes[2].id, character_ids=[marko], narrator={'person': 'first', 'character_id': olena})
        cards = first['cards']
        unchanged = save_cards(client, story.id, cards)
        assert unchanged['changed_character_ids'] == [] and unchanged['dependent_scene_ids'] == []
        cards[0]['entries'][0]['text'] = 'Бібліотекарка з міста.'
        changed = save_cards(client, story.id, cards)
        assert changed['changed_character_ids'] == [olena]
        assert changed['dependent_scene_ids'] == [scenes[0].id, scenes[2].id]
        no_brief = repo.create_scene(story.id, SceneCreate(title='Без завдання', beats='Ніч'))
        cast(repo, no_brief.id, character_ids=[olena])
        cards = changed['cards']
        cards[0]['entries'][0]['text'] = 'Бібліотекарка з села.'
        changed = save_cards(client, story.id, cards)
        assert changed['dependent_scene_ids'] == [scenes[0].id, scenes[2].id]  # no brief: nothing to uncheck
        removed = save_cards(client, story.id, [c for c in changed['cards'] if c['id'] == olena])
        assert removed['changed_character_ids'] == [marko] and removed['dependent_scene_ids'] == [scenes[2].id]
        assert 'changed_character_ids' not in client.get(f'/api/stories/{story.id}/characters').json()


@pytest.mark.req('VALID-CARDS')
def test_saving_cards_alone_changes_no_link(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    with client_for(tmp_path) as client:
        saved = save_cards(client, story.id, [card('Олена', 'Бібліотекарка.')])
        cast(repo, scene.id, character_ids=[saved['cards'][0]['id']])
        cards = saved['cards']
        cards[0]['entries'][0]['text'] = 'Інша.'
        assert save_cards(client, story.id, cards)['dependent_scene_ids'] == [scene.id]
        assert material_status(client, story.id, scene.id)['validity'] == 'valid'  # the author said «Ні»


@pytest.mark.req('VALID-CARDS')
def test_invalidate_route_unchecks_scenes(tmp_path):
    repo, story, scenes = book(tmp_path, 2)
    with client_for(tmp_path) as client:
        response = client.post(f'/api/stories/{story.id}/links/invalidate',
                               json={'scene_ids': [scenes[1].id], 'reason': {'kind': 'character', 'ids': ['c1']}})
        assert response.status_code == 200, response.text
        assert response.json()['scene_ids'] == [scenes[1].id]
        status = material_status(client, story.id, scenes[1].id)
        assert status['validity'] == 'unchecked'
        assert status['links']['brief']['status'] == status['links']['prose']['status'] == 'unchecked'
        assert material_status(client, story.id, scenes[0].id)['validity'] == 'valid'


@pytest.mark.req('VALID-CARDS')
def test_invalidate_route_refuses_foreign_or_unknown_scenes(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    from storygen.domain import StoryCreate
    foreign_story = repo.create_story(StoryCreate(title='Інший'))
    foreign = repo.create_scene(foreign_story.id, SceneCreate(title='Чужа', beats='x'))
    url = f'/api/stories/{story.id}/links/invalidate'
    reason = {'kind': 'location', 'ids': ['l1']}
    with client_for(tmp_path) as client:
        for ids in ([foreign.id], ['missing'], [scene.id, foreign.id]):
            assert client.post(url, json={'scene_ids': ids, 'reason': reason}).status_code == 404, ids
        assert client.post(url, json={'scene_ids': [], 'reason': reason}).status_code == 422
        assert client.post(url, json={'scene_ids': [scene.id], 'reason': {'kind': 'style', 'ids': ['x']}}).status_code == 422
        assert client.post(f'/api/stories/missing/links/invalidate', json={'scene_ids': [scene.id], 'reason': reason}).status_code == 404
        assert material_status(client, story.id, scene.id)['validity'] == 'valid'  # nothing was written


@pytest.mark.req('VALID-CARDS')
def test_location_change_reports_dependent(tmp_path):
    repo, story, _ = book(tmp_path, 0)
    room = repo.create_scene(story.id, SceneCreate(title='Ранок', beats='Локація: Квартира Джорджа / вітальня'))
    yard = repo.create_scene(story.id, SceneCreate(title='Вечір', beats='Локація: Квартира Джоржа, двір'))
    garden = repo.create_scene(story.id, SceneCreate(title='Сад', beats='Локація: Сад'))
    for scene in (room, yard):
        save_manual_brief(repo, scene)  # a scene without a brief has no card links to uncheck
    lid = lambda *parts: location_id(story.id, normalize(parts))
    base = f'/api/stories/{story.id}/locations'
    with client_for(tmp_path) as client:
        def change(method, path, **body):
            revision = client.get(base).json()['story_revision']
            response = client.request(method, base + path, json={**body, 'expected_revision': revision})
            assert response.status_code == 200, response.text
            return response.json()['dependent_scene_ids']
        assert change('PUT', '/' + lid('двір'), description='Тісний двір') == [yard.id]
        assert change('PUT', '/' + lid('двір'), description='Тісний двір ') == []  # same text after strip
        # A parent card is shown to the scenes of the places inside it.
        assert change('PUT', '/' + lid('Квартира Джорджа'), description='Третій поверх') == [room.id]
        # The merged card's scene shows another path; the target's scenes see its memory as nearby (neighbourhood).
        assert change('POST', f'/{lid("Квартира Джоржа")}/merge', into=lid('Квартира Джорджа')) == [room.id, yard.id]
        assert change('POST', f'/{lid("Квартира Джоржа")}/split') == [room.id, yard.id]
        assert change('POST', '/dismiss', a=lid('Квартира Джорджа'), b=lid('Квартира Джоржа')) == []
        assert change('PUT', '/' + lid('Сад'), description='Яблуні') == []  # the garden scene has no brief yet
        assert 'dependent_scene_ids' not in client.get(base).json()
