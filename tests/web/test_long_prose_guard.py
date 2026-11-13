"""BUILD-EDITION-001-S08: a structured book is read-only in an edition without long prose."""
import re
import sqlite3

import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.book.guard import READ_ONLY
from storygen.domain import SceneCreate, StoryCreate
from storygen.storage.book_structure import put_structure
from storygen.web.app import create_app
from storygen.web.long_prose_guard import ALLOWED, GENERATIVE_GET, routes

PARTS = [{'id': 'p1', 'arcs': [{'id': 'a1'}]}, {'id': 'p2', 'arcs': [{'id': 'b1'}]}]


def setup(tmp_path, structured=True):
    app = create_app(AppSettings(data_dir=tmp_path / 'data', env_file=tmp_path / 'absent.env'))
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Книга'))
    first = repo.create_scene(story.id, SceneCreate(title='Перша'))
    second = repo.create_scene(story.id, SceneCreate(title='Друга'))
    if structured:
        put_structure(repo, story.id, PARTS, {first.id: 'a1', second.id: 'b1'}, repo.get_story(story.id).revision)
    db = sqlite3.connect(tmp_path / 'data' / 'storygen.sqlite3')
    db.execute('INSERT INTO runs VALUES(?,?,?,?,?)', ('run1', story.id, 'req1', 'completed', '{}'))
    db.commit()
    db.close()
    return TestClient(app, base_url='http://127.0.0.1'), app, repo, repo.get_story(story.id), first


def url(path, story, scene):
    values = {'story_id': story.id, 'scene_id': scene.id, 'run_id': 'run1', 'attempt_id': 'x', 'stage': 'brief', 'call_id': 'x',
              'record_id': 'x', 'name': 'x'}
    def value(match):
        name = match[1]
        if name == 'id':
            return {'stories': story.id, 'scenes': scene.id, 'runs': 'run1'}.get(path.split('/')[2], 'x')
        return values[name]
    return re.sub(r'\{(\w+)\}', value, path)


def test_every_write_route_is_guarded_or_allowed_with_a_reason(tmp_path, store_edition):
    client, app, repo, story, scene = setup(tmp_path)
    checked = 0
    for route in routes(app):
        for method in sorted(route.methods - {'HEAD'}):
            if method == 'GET' and route.path not in GENERATIVE_GET:
                continue
            if (method, route.path) in ALLOWED:
                assert ALLOWED[(method, route.path)].strip()
                continue
            body = {'request_id': 'r', 'request': {'story_id': story.id}} if route.path == '/api/runs' else {}
            response = client.request(method, url(route.path, story, scene), json=body)
            assert response.status_code == 400 and READ_ONLY in response.json()['detail_original'], (method, route.path, response.text)
            checked += 1
    assert checked > 50
    assert repo.get_story(story.id).revision == story.revision


def test_allowed_list_names_only_existing_routes(tmp_path):
    client, app, *_ = setup(tmp_path, structured=False)
    existing = {(m, r.path) for r in routes(app) for m in r.methods}
    assert set(ALLOWED) <= existing and GENERATIVE_GET <= {p for _, p in existing}


def test_flat_book_is_writable_in_store(tmp_path, store_edition):
    client, _, repo, story, _ = setup(tmp_path, structured=False)
    response = client.patch(f'/api/stories/{story.id}', json={'title': 'Нова', 'expected_revision': story.revision})
    assert response.status_code == 200, response.text


def test_one_named_part_and_arc_is_writable_in_store(tmp_path, store_edition):
    client, _, repo, story, scene = setup(tmp_path, structured=False)
    put_structure(repo, story.id, [{'id': 'p', 'title': 'Одна', 'arcs': [{'id': 'a', 'title': 'Одна'}]}], {}, story.revision)
    story = repo.get_story(story.id)
    assert client.patch(f'/api/stories/{story.id}', json={'title': 'Нова', 'expected_revision': story.revision}).status_code == 200


def test_structured_book_reads_and_exports_in_store(tmp_path, store_edition):
    from storygen.generation.dependencies import save_manual_prose
    from storygen.publication_models import PublicationData
    client, _, repo, story, _ = setup(tmp_path)
    for scene in repo.list_scenes(story.id):
        save_manual_prose(repo, scene.id, f'Текст сцени {scene.title}.\n', repo.get_scene(scene.id).revision)
    author = repo.publication('create_signature', display_name='Автор')
    repo.publication('save_card', story_id=story.id, data=PublicationData(title='Книга', author_ids=[author.id], genres=['short_story']),
                     expected_revision=0, expected_signature_revisions={author.id: 0})
    assert client.get(f'/api/stories/{story.id}').status_code == 200
    response = client.post(f'/api/stories/{story.id}/export', json={'format': 'md'})
    assert response.status_code == 200, response.text
    download = client.get(response.json()['download_url'])
    assert download.status_code == 200 and 'Текст сцени Перша.' in download.content.decode('utf-8')


def test_structured_book_is_writable_with_long_prose(tmp_path):
    client, _, repo, story, _ = setup(tmp_path)
    assert client.patch(f'/api/stories/{story.id}', json={'title': 'Нова', 'expected_revision': story.revision}).status_code == 200


def test_body_read_by_the_guard_still_reaches_the_route(tmp_path, store_edition):
    client, _, repo, story, scene = setup(tmp_path, structured=False)
    body = {'request_id': 'guard-body', 'request': {'story_id': story.id, 'mode': 'scene', 'scene_id': scene.id}}
    response = client.post('/api/runs', json=body)
    # The route saw the whole body: a run was created (or refused for a model reason), never a validation error.
    assert response.status_code != 422, response.text
    assert READ_ONLY not in response.text
