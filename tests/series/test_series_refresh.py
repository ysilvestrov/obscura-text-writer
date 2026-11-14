"""SERIES-S04: snapshot status (computed on read) and the explicit refresh (neutral examples)."""
import json

import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.book.series import series_status
from storygen.characters.models import load_characters
from storygen.domain import SceneCreate
from storygen.memory.journal import MemoryJournal, _add_event, load_memory
from storygen.storage import series as store
from storygen.storage.repository import Repository
from storygen.web.app import create_app
from tests.series.helpers import book, card, finished_book, into_series, memory, prose, publish_cards
from tests.series.test_series_memory import write_scene_memory


def setup(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Серія')
    first, scenes, cloth = finished_book(repo)
    first = into_series(repo, first, item.id, 1)
    second, scene = book(repo, 'Книга 2', cast=['A'])
    second = into_series(repo, second, item.id, 2)
    return repo, item, repo.get_story(first.id), scenes, repo.get_story(second.id), repo.get_scene(scene.id)


def cards_of(repo, story):
    return load_characters(repo.read_text(repo.get_story(story.id).characters_version_id))


def rewrite_last_memory(repo, first, scenes):
    """A new memory of book 1's last scene: one more fact on top of the same journal."""
    last = repo.get_scene(scenes[1].id)
    journal = load_memory(repo.read_text(last.heads['memory']))
    previous = MemoryJournal(schema_version=3, source_prose_ids=journal.source_prose_ids[:-1],
                             events=[e for e in journal.events if e.source_version_id != last.heads['prose']])
    memory(repo, last, previous, [_add_event('facts', 'Сусід зачинив двері', last.heads['prose'], 'Сусід пішов додому.', 0)])


def test_first_book_and_fresh_status(tmp_path):
    repo, item, first, scenes, second, scene = setup(tmp_path)
    assert series_status(repo, first).state == 'first'
    status = series_status(repo, second)
    assert (status.state, status.source_story_id, status.changed_cards) == ('fresh', first.id, [])
    assert series_status(repo, repo.create_story(__import__('storygen.domain', fromlist=['StoryCreate']).StoryCreate(title='Окрема'))) is None


def test_new_memory_of_book_1_warns_without_staling_book_2(tmp_path):
    repo, item, first, scenes, second, scene = setup(tmp_path)
    memory_id = write_scene_memory(repo, scene)
    rewrite_last_memory(repo, first, scenes)
    assert series_status(repo, repo.get_story(second.id)).state == 'source_changed'
    assert not repo.get_version(memory_id).stale


def test_card_change_in_source_is_listed_but_own_edits_are_not(tmp_path):
    repo, item, first, scenes, second, scene = setup(tmp_path)
    own = [json.loads(c.model_dump_json()) for c in cards_of(repo, second)]
    own[0]['name'] = 'Анна Коваль'
    publish_cards(repo, second, own)
    assert series_status(repo, repo.get_story(second.id)).changed_cards == []
    source = [json.loads(c.model_dump_json()) for c in cards_of(repo, first)]
    source[0]['entries'][0]['text'] = 'Хірургиня'
    publish_cards(repo, first, source)
    status = series_status(repo, repo.get_story(second.id))
    assert (status.state, status.changed_cards) == ('source_changed', ['A'])


def test_source_finished_later_warns_and_refresh_takes_the_first_snapshot(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Серія')
    first, scenes, cloth = finished_book(repo)
    into_series(repo, first, item.id, 1)
    extra = repo.create_scene(first.id, SceneCreate(title='Сцена 3', beats='Пізніше.'))
    second, scene = book(repo, 'Книга 2')
    second = into_series(repo, second, item.id, 2)
    assert series_status(repo, second).state == 'no_summary'
    repo.set_scene_trashed(first.id, extra.id, repo.get_scene(extra.id).revision, False)
    assert series_status(repo, repo.get_story(second.id)).state == 'source_finished'
    assert repo.get_story(second.id).series_start_version_id is None
    story, warnings = store.refresh_snapshot(repo, second.id, repo.get_story(second.id).revision)
    assert story.series_start_version_id and warnings == []
    assert series_status(repo, story).state == 'fresh'


def test_trashed_or_renumbered_source_warns(tmp_path):
    repo, item, first, scenes, second, scene = setup(tmp_path)
    store.set_story_series(repo, second.id, item.id, 3, None, second.revision)
    middle, _ = book(repo, 'Книга 2')
    into_series(repo, middle, item.id, 2)
    assert series_status(repo, repo.get_story(second.id)).state == 'source_changed'
    repo2, item2, first2, _, second2, _ = setup(tmp_path / 'other')
    repo2.set_story_trashed(first2.id, first2.revision, False)
    status = series_status(repo2, repo2.get_story(second2.id))
    assert (status.state, status.source_story_id) == ('source_changed', None)


def test_refresh_adds_new_cards_and_skips_same_name(tmp_path):
    repo, item, first, scenes, second, scene = setup(tmp_path)
    source = [json.loads(c.model_dump_json()) for c in cards_of(repo, first)]
    publish_cards(repo, first, source + [card('B', 'Борис'), card('C', 'Віра')])
    own = [json.loads(c.model_dump_json()) for c in cards_of(repo, second)]
    publish_cards(repo, second, own + [card('own-c', ' віра ')])
    story, warnings = store.refresh_snapshot(repo, second.id, repo.get_story(second.id).revision)
    assert sorted(c.id for c in cards_of(repo, story)) == ['A', 'B', 'own-c']
    assert any('Віра' in w for w in warnings)


def test_refresh_names_cards_changed_in_the_source_and_keeps_the_book_copy(tmp_path):
    repo, item, first, scenes, second, scene = setup(tmp_path)
    before = [c.model_dump() for c in cards_of(repo, second)]
    source = [json.loads(c.model_dump_json()) for c in cards_of(repo, first)]
    source[0]['entries'][0]['text'] = 'Хірургиня'
    publish_cards(repo, first, source)
    story, warnings = store.refresh_snapshot(repo, second.id, repo.get_story(second.id).revision)
    assert warnings == [store.CARD_CHANGED.format(names=cards_of(repo, first)[0].name)]
    assert [c.model_dump() for c in cards_of(repo, story)] == before


def test_refresh_stales_scene_1_memory(tmp_path):
    repo, item, first, scenes, second, scene = setup(tmp_path)
    memory_id = write_scene_memory(repo, scene)
    rewrite_last_memory(repo, first, scenes)
    story, _ = store.refresh_snapshot(repo, second.id, repo.get_story(second.id).revision)
    assert story.series_start_version_id != second.series_start_version_id
    assert repo.get_version(memory_id).stale
    assert series_status(repo, story).state == 'fresh'


def test_refresh_endpoint_requires_confirmation_and_story_view_has_series(tmp_path):
    repo, item, first, scenes, second, scene = setup(tmp_path)
    rewrite_last_memory(repo, first, scenes)
    with TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765') as client:
        view = client.get(f'/api/stories/{second.id}').json()
        assert view['series']['number'] == 2 and view['series']['title'] == 'Серія'
        assert view['series']['status']['state'] == 'source_changed'
        revision = view['story']['revision']
        refused = client.post(f'/api/stories/{second.id}/series/refresh', json={'expected_revision': revision})
        assert refused.status_code == 422
        done = client.post(f'/api/stories/{second.id}/series/refresh', json={'expected_revision': revision, 'confirm': True})
        assert done.status_code == 200, done.text
        assert done.json()['story']['series_start_version_id'] != second.series_start_version_id
        assert 'series' not in client.get(f'/api/stories/{repo.create_story(__import__("storygen.domain", fromlist=["StoryCreate"]).StoryCreate(title="Окрема")).id}').json()
