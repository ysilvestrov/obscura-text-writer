"""SERIES-S09: past and future decisions of a prequel's start snapshot (neutral examples)."""
import json

from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.book.series import series_status
from storygen.memory.journal import replay_memory
from storygen.memory.series_start import read_series_start
from storygen.series_models import SeriesStart
from storygen.storage import series as store
from storygen.storage.integrity import check_integrity
from storygen.storage.repository import Repository
from storygen.web.app import create_app
from tests.series.helpers import book, finished_book, into_series
from tests.series.test_series_memory import write_brief, write_scene_memory
from tests.series.test_series_refresh import rewrite_last_memory


def setup(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Сага')
    first, scenes, cloth = finished_book(repo)
    first = into_series(repo, first, item.id, 1)
    prequel, scene = book(repo, 'Приквел', cast=['A'])
    prequel = store.set_story_series(repo, prequel.id, item.id, 2, SeriesStart(offset='Рік -10', anchor=1), prequel.revision)
    return repo, item, first, scenes, prequel, repo.get_scene(scene.id)


def snapshot(repo, story):
    story = repo.get_story(story.id)
    return read_series_start(repo.read_text(story.series_start_version_id), story.series_start_version_id)


def keys(repo, story):
    return {fact['text']: fact['key'] for fact in store.start_facts(repo, story.id)}


def client_for(tmp_path):
    return TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765')


def test_first_prequel_snapshot_is_all_future(tmp_path):
    repo, item, first, scenes, prequel, scene = setup(tmp_path)
    data = snapshot(repo, prequel)
    assert data.journal.events == [] and data.text == ''
    assert sorted(f['text'] for f in data.future) == ['Сусід пішов', 'Халат']
    assert set(data.decisions.values()) == {'future'} and len(data.decisions) == 2
    facts = store.start_facts(repo, prequel.id)
    assert [(f['category'], f['text'], f['story_id'], f['decision']) for f in facts] == [
        ('facts', 'Сусід пішов', first.id, 'future'), ('character_states', 'Халат', first.id, 'future')]
    assert series_status(repo, repo.get_story(prequel.id)).state == 'fresh'
    assert check_integrity(repo.root).ok


def test_saving_past_moves_the_record_chain_into_memory(tmp_path):
    repo, item, first, scenes, prequel, scene = setup(tmp_path)
    memory_id = write_scene_memory(repo, scene)
    brief_id = write_brief(repo, scene)
    clothing = keys(repo, prequel)['Халат']
    before = snapshot(repo, prequel).source
    story = store.save_decisions(repo, prequel.id, {clothing: 'past'}, repo.get_story(prequel.id).revision)
    data = snapshot(repo, story)
    assert [e.text for e in replay_memory(data.journal).values()] == ['Халат']
    assert data.text == 'Анна в халаті.'
    assert [f['text'] for f in data.future] == ['Сусід пішов']
    assert (data.source['sources'], data.source['resolved']) == (before['sources'], before['resolved'])
    assert repo.get_version(memory_id).stale and repo.get_version(brief_id).stale


def test_decisions_need_confirmation_and_known_keys(tmp_path):
    repo, item, first, scenes, prequel, scene = setup(tmp_path)
    clothing = keys(repo, prequel)['Халат']
    revision = repo.get_story(prequel.id).revision
    url = f'/api/stories/{prequel.id}/series/decisions'
    with client_for(tmp_path) as client:
        facts = client.get(f'/api/stories/{prequel.id}/series/facts')
        assert facts.status_code == 200 and [f['text'] for f in facts.json()['facts']] == ['Сусід пішов', 'Халат']
        assert client.put(url, json={'decisions': {clothing: 'past'}, 'expected_revision': revision}).status_code == 422
        unknown = client.put(url, json={'decisions': {'claim:x': 'past'}, 'expected_revision': revision, 'confirm': True})
        assert unknown.status_code == 422
        wrong = client.put(url, json={'decisions': {clothing: 'maybe'}, 'expected_revision': revision, 'confirm': True})
        assert wrong.status_code == 422
        done = client.put(url, json={'decisions': {clothing: 'past'}, 'expected_revision': revision, 'confirm': True})
        assert done.status_code == 200, done.text
        assert client.put(url, json={'decisions': {clothing: 'future'}, 'expected_revision': revision,
                                     'confirm': True}).status_code == 409
        outside = repo.create_story(__import__('storygen.domain', fromlist=['StoryCreate']).StoryCreate(title='Окрема'))
        assert client.get(f'/api/stories/{outside.id}/series/facts').status_code == 404


def test_refresh_carries_decisions_and_defaults_new_keys(tmp_path):
    repo, item, first, scenes, prequel, scene = setup(tmp_path)
    clothing = keys(repo, prequel)['Халат']
    store.save_decisions(repo, prequel.id, {clothing: 'past'}, repo.get_story(prequel.id).revision)
    rewrite_last_memory(repo, first, scenes)  # «Сусід пішов» is gone, «Сусід зачинив двері» is new
    story, _ = store.refresh_snapshot(repo, prequel.id, repo.get_story(prequel.id).revision)
    data = snapshot(repo, story)
    by_text = {f['text']: f['decision'] for f in store.start_facts(repo, prequel.id)}
    assert by_text == {'Халат': 'past', 'Сусід зачинив двері': 'future'}
    assert set(data.decisions) == set(keys(repo, story).values())


def test_series_4a_prequel_snapshot_is_all_past(tmp_path):
    repo, item, first, scenes, prequel, scene = setup(tmp_path)
    story = repo.get_story(prequel.id)
    raw = json.loads(repo.read_text(story.series_start_version_id))
    full = raw.pop('start_memory')
    for name in ('decisions', 'future', 'origins'):
        raw.pop(name)
    raw.update(full)  # a 4a snapshot: the whole summary of the source book in the journal, no decisions
    version = repo.save_version(story.id, None, 'series_start', json.dumps(raw, ensure_ascii=False),
                                [raw['characters_version_id']])
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        current = repo._active_story(db, story.id)
        repo._save_story(db, current.model_copy(update={'series_start_version_id': version.id,
                                                       'revision': current.revision + 1}))
    data = snapshot(repo, story)
    assert sorted(e.text for e in replay_memory(data.journal).values()) == ['Сусід пішов', 'Халат']
    assert data.decisions is None and data.future == []
    assert {f['decision'] for f in store.start_facts(repo, story.id)} == {'past'}
    assert series_status(repo, repo.get_story(story.id)).state == 'prequel_review'


def test_store_refuses_decisions(tmp_path, store_edition):
    repo, item, first, scenes, prequel, scene = setup(tmp_path)
    clothing = keys(repo, prequel)['Халат']
    with client_for(tmp_path) as client:
        refused = client.put(f'/api/stories/{prequel.id}/series/decisions',
                             json={'decisions': {clothing: 'past'}, 'expected_revision': repo.get_story(prequel.id).revision,
                                   'confirm': True})
        assert refused.status_code == 400 and 'довгою прозою' in refused.text
