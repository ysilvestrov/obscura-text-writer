"""MCP-BRIDGE: reading one scene material with its current version (#108)."""
import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import ContentRating, SceneCreate, StoryCreate
from storygen.web.app import create_app

from tests.web.test_writing_context import BRIEF, story_with_memory


def client_for(app):
    return TestClient(app, base_url='http://127.0.0.1:8765')


def read(client, scene_id, material, **params):
    return client.get(f'/api/scenes/{scene_id}/text/{material}', params=params)


def plain_scene(tmp_path, beats='Анна знаходить лист.'):
    app = create_app(AppSettings(data_dir=tmp_path))
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк'))
    scene = repo.create_scene(story.id, SceneCreate(title='Лист', beats=beats))
    return app, repo, story, scene


def put_head(repo, story, scene_id, kind, head, text):
    ref = repo.save_version(story.id, scene_id, kind, text, [])
    repo.set_head(scene_id, head, ref.id, repo.get_scene(scene_id).revision)
    return ref


@pytest.mark.req('MCP-BRIDGE')
def test_each_material_returns_text_and_current_version(tmp_path):
    app, repo, story, second = story_with_memory(tmp_path)
    first = repo.list_scenes(story.id)[0]
    with client_for(app) as client:
        assert client.patch(f'/api/scenes/{first.id}', json={'story_id': story.id, 'expected_revision': repo.get_scene(first.id).revision,
                                                            'beats': 'Анна вдома.'}).status_code == 200
        put_head(repo, story, first.id, 'brief', 'brief', BRIEF)
        put_head(repo, story, first.id, 'draft', 'draft', 'Анна вдома, чернетка.')
        scene = repo.get_scene(first.id)
        for material in ['plan', 'brief', 'draft', 'prose', 'memory']:
            response = read(client, first.id, material)
            assert response.status_code == 200, (material, response.text)
            data = response.json()
            assert data['version_id'] == scene.heads[material], material
            assert data['revision'] == scene.revision and data['material'] == material and data['story_id'] == story.id
            if material == 'memory':
                rows = json.loads(data['text'])
                assert rows and {'claim_id', 'category', 'text', 'source_scene', 'quote', 'forward', 'closed'} <= set(rows[0])
                assert 'scene' not in rows[0] and 'kind' not in rows[0]
            else:
                assert data['text'] == repo.read_text(scene.heads[material])


@pytest.mark.req('MCP-BRIDGE')
def test_missing_material_is_empty_not_404(tmp_path):
    app, repo, story, scene = plain_scene(tmp_path)
    with client_for(app) as client:
        data = read(client, scene.id, 'draft').json()
    assert data['version_id'] is None and data['text'] == '' and data['total_chars'] == 0 and data['next_offset'] is None


@pytest.mark.req('MCP-BRIDGE')
def test_plan_without_head_falls_back_to_beats(tmp_path):
    app, repo, story, scene = plain_scene(tmp_path, beats='Анна знаходить лист у скриньці.')
    with client_for(app) as client:
        data = read(client, scene.id, 'plan').json()
    assert data['text'] == repo.get_scene(scene.id).beats and data['version_id'] is None


@pytest.mark.req('MCP-BRIDGE')
def test_long_text_comes_in_parts_with_one_hash(tmp_path):
    app, repo, story, scene = plain_scene(tmp_path)
    full = ('Анна відчинила скриньку 🙂 ' * 120)[:2500]
    ref = put_head(repo, story, scene.id, 'draft', 'draft', full)
    parts, offset = [], 0
    with client_for(app) as client:
        while offset is not None:
            data = read(client, scene.id, 'draft', offset=offset, max_chars=1000).json()
            parts.append(data)
            offset = data['next_offset']
    assert [p['offset'] for p in parts] == [0, 1000, 2000] and parts[-1]['next_offset'] is None
    assert ''.join(p['text'] for p in parts) == full
    assert {p['content_sha256'] for p in parts} == {hashlib.sha256(full.encode('utf-8')).hexdigest()}
    assert {p['version_id'] for p in parts} == {ref.id} and parts[0]['total_chars'] == 2500


@pytest.mark.req('MCP-BRIDGE')
def test_memory_hash_changes_with_forwarding_choice(tmp_path):
    app, repo, story, second = story_with_memory(tmp_path)
    first = repo.list_scenes(story.id)[0]
    with client_for(app) as client:
        before = read(client, first.id, 'memory').json()
        table = client.get(f'/api/scenes/{first.id}/memory-view').json()
        claim = next(row['claim_id'] for row in table['rows'] if not row['slot'])
        changed = client.put(f'/api/scenes/{first.id}/memory-view',
                             json={'expected_revision': table['expected_revision'], 'fingerprint': table['fingerprint'], 'choices': {claim: False}})
        assert changed.status_code == 200, changed.text
        after = read(client, first.id, 'memory').json()
    assert after['version_id'] == before['version_id']
    assert after['content_sha256'] != before['content_sha256']


@pytest.mark.req('MCP-BRIDGE')
@pytest.mark.parametrize('params,status', [({'offset': 99}, 400), ({'offset': -1}, 400), ({'max_chars': 999}, 422), ({'max_chars': 50001}, 422)])
def test_bad_offset_or_size_is_refused(tmp_path, params, status):
    app, repo, story, scene = plain_scene(tmp_path)
    put_head(repo, story, scene.id, 'draft', 'draft', 'Коротко.')
    with client_for(app) as client:
        response = read(client, scene.id, 'draft', **params)
        unknown = read(client, scene.id, 'notes')
    assert response.status_code == status, response.text
    assert unknown.status_code == 422


@pytest.mark.req('MCP-BRIDGE')
def test_memory_rows_match_the_memory_table(tmp_path):
    app, repo, story, second = story_with_memory(tmp_path)
    first = repo.list_scenes(story.id)[0]
    fields = ['claim_id', 'category', 'text', 'source_scene', 'source_title', 'quote', 'supporting_quotes', 'forward', 'closed']
    with client_for(app) as client:
        table = client.get(f'/api/scenes/{first.id}/memory-view').json()['rows']
        rows = json.loads(read(client, first.id, 'memory').json()['text'])
    assert len(rows) == len(table) == 2
    assert all(set(row) == set(fields) for row in rows)
    assert sorted(rows, key=lambda r: r['claim_id']) == sorted(({k: t[k] for k in fields} for t in table), key=lambda r: r['claim_id'])
    assert {row['text'] for row in rows} == {'Синій халат', 'Маяк стоїть на старій карті'}


@pytest.mark.req('MCP-BRIDGE')
def test_existing_empty_memory_is_an_empty_json_array(tmp_path):
    from storygen.memory.journal import MemoryJournal
    app, repo, story, scene = plain_scene(tmp_path)
    prose = put_head(repo, story, scene.id, 'manual', 'prose', 'Анна вдома.')
    memory = put_head(repo, story, scene.id, 'memory', 'memory', MemoryJournal(schema_version=3, source_prose_ids=[prose.id], events=[]).model_dump_json())
    with client_for(app) as client:
        data = read(client, scene.id, 'memory').json()
    assert data['version_id'] == memory.id and json.loads(data['text']) == []


@pytest.mark.req('MCP-BRIDGE')
def test_store_edition_blocks_text_above_limit(tmp_path, monkeypatch):
    app, repo, story, scene = plain_scene(tmp_path)
    put_head(repo, story, scene.id, 'draft', 'draft', 'Текст.')
    repo.update_story_rating(story.id, ContentRating(sexual=2, violence=0, themes=0), repo.get_story(story.id).revision)
    from storygen import build_edition
    edition = build_edition.BuildEdition(edition='store', report_url='https://example.test/report')
    monkeypatch.setattr(build_edition, 'current', lambda: edition)
    with client_for(app) as client:
        for material in ['draft', 'memory', 'plan']:
            response = read(client, scene.id, material)
            assert response.status_code == 400 and 'найвищий дозволений рівень — 1' in response.text, (material, response.text)


@pytest.mark.req('MCP-BRIDGE')
def test_response_has_no_paths_or_snapshots(tmp_path):
    app, repo, story, scene = plain_scene(tmp_path)
    put_head(repo, story, scene.id, 'draft', 'draft', 'Текст.')
    with client_for(app) as client:
        body = read(client, scene.id, 'draft').text
    for field in ['relative_path', 'dependency_snapshot', 'prompt_contract', 'input_refs']:
        assert field not in body
