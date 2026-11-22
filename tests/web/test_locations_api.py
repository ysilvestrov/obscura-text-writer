"""MEMORY-LOCATIONS-S07: the locations API — cards with scenes and suggestions, merge, split, dismiss and description with CAS."""
import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import SceneCreate, StoryCreate
from storygen.locations import location_id, normalize
from storygen.web.app import create_app


def setup(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path / 'data', env_file=tmp_path / 'absent.env'))
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Пристань'))
    first = repo.create_scene(story.id, SceneCreate(title='Ранок', beats='Локація: Квартира Джорджа / вітальня', character_ids=[]))
    second = repo.create_scene(story.id, SceneCreate(title='Вечір', beats='Локація: Квартира Джоржа, двір', character_ids=[]))
    return TestClient(app, base_url='http://127.0.0.1'), repo, repo.get_story(story.id), first, second


def lid(story, *parts):
    return location_id(story.id, normalize(parts))


def base(story):
    return f'/api/stories/{story.id}/locations'


def card(data, id):
    return next(c for c in data['locations'] if c['id'] == id)


@pytest.mark.req('MEMORY-LOCATIONS')
def test_list_has_cards_with_their_scenes_and_suggestions(tmp_path):
    client, repo, story, first, second = setup(tmp_path)
    data = client.get(base(story)).json()
    assert data['story_revision'] == story.revision
    assert [c['path'] for c in data['locations']] == ['Квартира Джорджа', 'Квартира Джорджа / вітальня', 'Квартира Джоржа', 'двір']
    room = card(data, lid(story, 'Квартира Джорджа', 'вітальня'))
    assert room['parent_id'] == lid(story, 'Квартира Джорджа') and room['description'] == '' and room['merged_into'] is None
    assert room['scenes'] == [{'id': first.id, 'position': 0, 'title': 'Ранок'}]
    assert card(data, lid(story, 'Квартира Джорджа'))['scenes'] == []  # only scenes that name the card itself
    assert data['suggestions'] == [{'a': lid(story, 'Квартира Джорджа'), 'b': lid(story, 'Квартира Джоржа'),
                                    'a_path': 'Квартира Джорджа', 'b_path': 'Квартира Джоржа'}]


@pytest.mark.req('MEMORY-LOCATIONS')
def test_story_without_locations_has_an_empty_list(tmp_path):
    client, repo, story, *_ = setup(tmp_path)
    other = repo.create_story(StoryCreate(title='Без місць'))
    assert client.get(base(other)).json() == {'story_revision': other.revision, 'locations': [], 'suggestions': []}


@pytest.mark.req('MEMORY-LOCATIONS')
def test_merge_redirects_scenes_and_split_returns_them(tmp_path):
    client, repo, story, first, second = setup(tmp_path)
    typo, right = lid(story, 'Квартира Джоржа'), lid(story, 'Квартира Джорджа')
    data = client.post(f'{base(story)}/{typo}/merge', json={'into': right, 'expected_revision': story.revision}).json()
    assert data['story_revision'] == story.revision + 1
    merged = card(data, typo)
    assert (merged['merged_into'], merged['target_path']) == (right, 'Квартира Джорджа')
    assert card(data, right)['scenes'] == [{'id': second.id, 'position': 1, 'title': 'Вечір'}]
    assert data['suggestions'] == []
    assert repo.get_scene(second.id).beats == 'Локація: Квартира Джоржа, двір'  # the plan text stays
    data = client.post(f'{base(story)}/{typo}/split', json={'expected_revision': data['story_revision']}).json()
    assert card(data, typo)['merged_into'] is None and card(data, right)['scenes'] == []


@pytest.mark.req('MEMORY-LOCATIONS')
def test_merge_into_a_merged_card_shows_the_final_target(tmp_path):
    client, repo, story, first, second = setup(tmp_path)
    typo, right, yard = lid(story, 'Квартира Джоржа'), lid(story, 'Квартира Джорджа'), lid(story, 'двір')
    rev = client.post(f'{base(story)}/{right}/merge', json={'into': yard, 'expected_revision': story.revision}).json()['story_revision']
    data = client.post(f'{base(story)}/{typo}/merge', json={'into': right, 'expected_revision': rev}).json()
    assert card(data, typo)['target_path'] == 'двір'
    data = client.post(f'{base(story)}/{right}/split', json={'expected_revision': data['story_revision']}).json()
    assert card(data, typo)['merged_into'] == right and card(data, typo)['target_path'] == 'Квартира Джорджа'


@pytest.mark.req('MEMORY-LOCATIONS')
def test_dismissed_pair_is_not_suggested_again(tmp_path):
    client, repo, story, *_ = setup(tmp_path)
    pair = {'a': lid(story, 'Квартира Джоржа'), 'b': lid(story, 'Квартира Джорджа'), 'expected_revision': story.revision}
    data = client.post(f'{base(story)}/dismiss', json=pair).json()
    assert data['suggestions'] == [] and data['story_revision'] == story.revision + 1


@pytest.mark.req('MEMORY-LOCATIONS')
def test_description_is_saved_trimmed_and_limited(tmp_path):
    client, repo, story, *_ = setup(tmp_path)
    yard = lid(story, 'двір')
    data = client.put(f'{base(story)}/{yard}', json={'description': '  Тісний, з липою.  ', 'expected_revision': story.revision}).json()
    assert card(data, yard)['description'] == 'Тісний, з липою.'
    response = client.put(f'{base(story)}/{yard}', json={'description': 'х' * 2001, 'expected_revision': data['story_revision']})
    assert response.status_code == 422
    assert card(client.get(base(story)).json(), yard)['description'] == 'Тісний, з липою.'


@pytest.mark.req('MEMORY-LOCATIONS')
def test_stale_revision_is_a_conflict_and_changes_nothing(tmp_path):
    client, repo, story, *_ = setup(tmp_path)
    yard = lid(story, 'двір')
    response = client.put(f'{base(story)}/{yard}', json={'description': 'Тісний.', 'expected_revision': story.revision - 1})
    assert response.status_code == 409
    data = client.get(base(story)).json()
    assert card(data, yard)['description'] == '' and data['story_revision'] == story.revision


@pytest.mark.req('MEMORY-LOCATIONS')
def test_unknown_card_self_merge_and_cycle_are_refused(tmp_path):
    client, repo, story, *_ = setup(tmp_path)
    typo, right = lid(story, 'Квартира Джоржа'), lid(story, 'Квартира Джорджа')
    rev = story.revision
    assert client.post(f'{base(story)}/loc_0000000000000000/split', json={'expected_revision': rev}).status_code == 400
    assert client.post(f'{base(story)}/{typo}/merge', json={'into': typo, 'expected_revision': rev}).status_code == 400
    rev = client.post(f'{base(story)}/{typo}/merge', json={'into': right, 'expected_revision': rev}).json()['story_revision']
    assert client.post(f'{base(story)}/{right}/merge', json={'into': typo, 'expected_revision': rev}).status_code == 400
    assert client.get(base(story)).json()['story_revision'] == rev


@pytest.mark.req('MEMORY-LOCATIONS')
def test_a_trashed_scene_is_not_listed(tmp_path):
    client, repo, story, first, second = setup(tmp_path)
    repo.set_scene_trashed(story.id, first.id, repo.get_scene(first.id).revision, False)
    room = card(client.get(base(story)).json(), lid(story, 'Квартира Джорджа', 'вітальня'))
    assert room['scenes'] == []


@pytest.mark.req('MEMORY-LOCATIONS')
def test_writes_through_the_api_make_shown_versions_stale(tmp_path):
    """No manual cache bump: what the author reads after an API write is recomputed."""
    from storygen.storage.snapshots import build_dependency_snapshot
    from storygen.providers.models import ProviderSettings, RoleSettings
    client, repo, story, first, second = setup(tmp_path)
    role = RoleSettings(provider=ProviderSettings(model='fake'), context_tokens=262144)
    snap = build_dependency_snapshot(repo.context_view(story.id), first.id, 'brief', role, [])
    brief = repo.save_version(story.id, first.id, 'brief', '{}', [], dependency_snapshot=snap)
    assert client.get(f'/api/versions/{brief.id}').json()['version']['stale'] is False
    data = client.put(f'{base(story)}/{lid(story, "Квартира Джорджа")}', json={'description': 'Старий дім.', 'expected_revision': story.revision}).json()
    assert client.get(f'/api/versions/{brief.id}').json()['version']['stale'] is True
    snap = build_dependency_snapshot(repo.context_view(story.id), first.id, 'memory', role, [])
    memory = repo.save_version(story.id, first.id, 'memory', '{}', [], dependency_snapshot=snap)
    client.post(f'{base(story)}/{lid(story, "Квартира Джоржа")}/merge',
                json={'into': lid(story, 'Квартира Джорджа', 'вітальня'), 'expected_revision': data['story_revision']})
    assert client.get(f'/api/versions/{memory.id}').json()['version']['stale'] is True


@pytest.mark.req('MEMORY-LOCATIONS')
def test_no_suggestion_between_a_card_and_its_ancestor_through_a_merge(tmp_path):
    client, repo, story, *_ = setup(tmp_path)
    repo.create_scene(story.id, SceneCreate(title='Сад', beats='Локація: Маєток', character_ids=[]))
    repo.create_scene(story.id, SceneCreate(title='Зала', beats='Локація: Старий маєток / вітальня', character_ids=[]))
    story = repo.get_story(story.id)
    old, manor, room = lid(story, 'Старий маєток'), lid(story, 'Маєток'), lid(story, 'Старий маєток', 'вітальня')
    data = client.post(f'{base(story)}/{old}/merge', json={'into': manor, 'expected_revision': story.revision}).json()
    pairs = {frozenset((s['a'], s['b'])) for s in data['suggestions']}
    assert frozenset((manor, room)) not in pairs
