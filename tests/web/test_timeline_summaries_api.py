"""MEMORY-SUMMARY API: block list with states and recommendation, readiness, author correction with CAS."""
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.memory.summary_blocks import summary_blocks
from storygen.storage.timeline_summaries import publish_summary, save_summary_version
from storygen.web.app import create_app
from tests.memory.summary_helpers import long_story


def setup(tmp_path, count=25, memory_until=21, publish=True):
    long_story(tmp_path / 'data', count, memory_until)
    app = create_app(AppSettings(data_dir=tmp_path / 'data', env_file=tmp_path / 'absent.env'))
    repo = app.state.repo
    story = repo.list_stories()[0]
    if publish:
        scenes = repo.list_scenes(story.id)
        block = summary_blocks(story, scenes)[0]
        ref = save_summary_version(repo, story.id, block, [s.heads['memory'] for s in scenes[:10]], 'Підсумок першого блоку.', 'model', 'uk')
        publish_summary(repo, story.id, block.key, ref.id, story.revision)
    return TestClient(app, base_url='http://127.0.0.1'), repo, repo.get_story(story.id)


def test_list_shows_states_and_recommendation(tmp_path):
    client, repo, story = setup(tmp_path)
    data = client.get(f'/api/stories/{story.id}/timeline-summaries').json()
    assert data['story_revision'] == story.revision
    first, second = data['blocks']
    assert (first['key'], first['state'], first['recommended'], first['text'], first['origin']) == (
        'range:1-10', 'fresh', False, 'Підсумок першого блоку.', 'model')
    assert first['version_id'] == story.timeline_summary_heads['range:1-10'] and first['ready']
    assert (second['key'], second['state'], second['recommended'], second['ready']) == ('range:11-20', 'none', False, True)


def test_block_without_summary_is_recommended_once_part_of_it_left_the_window(tmp_path):
    client, repo, story = setup(tmp_path, publish=False)
    first = client.get(f'/api/stories/{story.id}/timeline-summaries').json()['blocks'][0]
    assert (first['state'], first['recommended'], first['version_id']) == ('none', True, None)
    client, repo, story = setup(tmp_path / 'early', memory_until=20, publish=False)
    assert not client.get(f'/api/stories/{story.id}/timeline-summaries').json()['blocks'][0]['recommended']


def test_not_ready_block_names_the_scene(tmp_path):
    client, repo, story = setup(tmp_path, memory_until=15, publish=False)
    second = client.get(f'/api/stories/{story.id}/timeline-summaries').json()['blocks'][1]
    assert not second['ready'] and 'Сцена 16' in second['ready_reason'] and not second['recommended']


def test_readiness_route(tmp_path):
    client, repo, story = setup(tmp_path, publish=False)
    result = client.get(f'/api/stories/{story.id}/timeline-summaries/readiness', params={'block_key': 'range:1-10'}).json()
    assert not result['ready'] and 'Пам’ять' in result['reason']  # no memory role configured


def test_author_correction_with_cas(tmp_path):
    client, repo, story = setup(tmp_path)
    head = story.timeline_summary_heads['range:1-10']
    url = f'/api/stories/{story.id}/timeline-summaries/range:1-10'
    stale = client.put(url, json={'text': 'Виправлено.', 'expected_version_id': head, 'expected_revision': story.revision - 1})
    assert stale.status_code == 409
    long = client.put(url, json={'text': 'а' * 1201, 'expected_version_id': head, 'expected_revision': story.revision})
    assert long.status_code == 400
    saved = client.put(url, json={'text': 'Виправлено автором.', 'expected_version_id': head, 'expected_revision': story.revision})
    assert saved.status_code == 200, saved.text
    block = client.get(f'/api/stories/{story.id}/timeline-summaries').json()['blocks'][0]
    assert block['text'] == 'Виправлено автором.' and block['origin'] == 'author' and block['state'] == 'fresh'
