import pytest
from fastapi.testclient import TestClient
from storygen.web.app import create_app
from storygen.application.settings import AppSettings
from tests.storage.test_links import book, save_manual_brief
from storygen.generation.dependencies import save_manual_prose



def client_for(tmp_path):
    return TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765')


def links(client, story_id, scene_id):
    view = client.get(f'/api/stories/{story_id}').json()
    return view['material_status'][scene_id]


def setup(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    return repo, story, scene


def decide(client, scene_id, link, fingerprint, action='approve'):
    return client.post(f'/api/scenes/{scene_id}/links/{link}/decision', json={'action': action, 'fingerprint': fingerprint})


@pytest.mark.req('VALID-LINKS')
def test_story_view_reports_links_and_validity(tmp_path):
    repo, story, scene = setup(tmp_path)
    with client_for(tmp_path) as client:
        status = links(client, story.id, scene.id)
    assert status['validity'] == 'valid'
    assert {k: v['status'] for k, v in status['links'].items()} == {'brief': 'valid', 'prose': 'valid', 'memory': 'valid'}
    assert status['links']['brief']['source'] == 'construction'


@pytest.mark.req('VALID-LINKS')
def test_author_approves_manual_brief(tmp_path):
    repo, story, scene = setup(tmp_path)
    save_manual_brief(repo, scene)
    with client_for(tmp_path) as client:
        state = links(client, story.id, scene.id)['links']['brief']
        assert state['status'] == 'unchecked'
        response = decide(client, scene.id, 'brief', state['fingerprint'])
        assert response.status_code == 200, response.text
        assert response.json()['link'] == {**state, 'status': 'valid', 'source': 'author'}
        assert links(client, story.id, scene.id)['links']['brief']['source'] == 'author'


@pytest.mark.req('VALID-LINKS')
def test_author_approves_prose_without_accepting_it(tmp_path):
    repo, story, scene = setup(tmp_path)
    save_manual_prose(repo, scene.id, 'Олена увійшла до старої бібліотеки.', repo.get_scene(scene.id).revision)
    with client_for(tmp_path) as client:
        state = links(client, story.id, scene.id)['links']['prose']
        response = decide(client, scene.id, 'prose', state['fingerprint'])
        assert response.status_code == 200 and response.json()['link']['status'] == 'valid'
    assert repo.list_acceptances(story.id) == []  # DATA-010 is not called


@pytest.mark.req('VALID-LINKS')
def test_stale_fingerprint_is_409_and_writes_nothing(tmp_path):
    repo, story, scene = setup(tmp_path)
    save_manual_brief(repo, scene)
    with client_for(tmp_path) as client:
        old = links(client, story.id, scene.id)['links']['brief']['fingerprint']
        save_manual_brief(repo, scene)
        assert decide(client, scene.id, 'brief', old).status_code == 409
        assert repo.context_view(story.id).link_verdicts == {}


@pytest.mark.req('VALID-LINKS')
def test_author_keeps_memory_through_the_api(tmp_path):
    repo, story, scene = setup(tmp_path)
    save_manual_prose(repo, scene.id, 'Інша проза.', repo.get_scene(scene.id).revision)
    with client_for(tmp_path) as client:
        state = links(client, story.id, scene.id)['links']['memory']
        assert state['status'] == 'unchecked'
        response = decide(client, scene.id, 'memory', state['fingerprint'])
        assert response.status_code == 200, response.text
        assert response.json()['link'] == {**state, 'status': 'valid', 'source': 'author'}
    assert len(repo.context_view(story.id).prose_equivalences) == 1


@pytest.mark.req('VALID-LINKS')
def test_missing_link_cannot_be_approved(tmp_path):
    from storygen.domain import StoryCreate, SceneCreate
    from storygen.storage.repository import Repository
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Твір'))
    scene = repo.create_scene(story.id, SceneCreate(title='Порожня', beats='x'))
    with client_for(tmp_path) as client:
        assert decide(client, scene.id, 'brief', '0' * 64).status_code == 409


@pytest.mark.req('VALID-LINKS')
def test_unknown_action_or_link_is_422(tmp_path):
    repo, story, scene = setup(tmp_path)
    with client_for(tmp_path) as client:
        assert decide(client, scene.id, 'plan', '0' * 64).status_code == 422
        assert decide(client, scene.id, 'brief', '0' * 64, action='reject').status_code == 422


@pytest.mark.req('VALID-LINKS')
def test_approving_a_valid_link_writes_nothing(tmp_path):
    repo, story, scene = setup(tmp_path)
    with client_for(tmp_path) as client:
        state = links(client, story.id, scene.id)['links']['brief']
        response = decide(client, scene.id, 'brief', state['fingerprint'])
        assert response.status_code == 200 and response.json()['link']['source'] == 'construction'
    assert repo.context_view(story.id).link_verdicts == {}
