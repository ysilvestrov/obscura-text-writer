"""R-49: the «Пишу сам» story mode (`writing_mode='author'`): models never write or apply prose. Neutral texts, no provider."""
from typing import get_args

import pytest

from storygen.run_models import RunRequest
from storygen.writing_mode import RUN_MODE_WRITES, writes_prose
from tests.web.test_chat_stage_routes import app_with_scene


@pytest.mark.req('WRITING-MODE')
def test_every_run_mode_has_a_prose_decision():
    assert set(RUN_MODE_WRITES) == set(get_args(RunRequest.model_fields['mode'].annotation))


WRITING = [('stage', 'draft'), ('stage', 'edit'), ('scene', None), ('remaining', None), ('edit_loop', None), ('rewrite', None)]
NOT_WRITING = [('stage', 'brief'), ('stage', 'memory'), ('prepare', None), ('rebuild_memory', None), ('memory_carry', None),
               ('evaluate', None), ('audit', None), ('character_extract', None), ('classify', None),
               ('publication_suggest', None), ('timeline_summary', None)]


@pytest.mark.req('WRITING-MODE')
def test_writes_prose_by_mode_and_stage():
    for mode, stage in WRITING:
        assert writes_prose(RunRequest.model_construct(story_id='s', mode=mode, stage=stage)), (mode, stage)
    for mode, stage in NOT_WRITING:
        assert not writes_prose(RunRequest.model_construct(story_id='s', mode=mode, stage=stage)), (mode, stage)


@pytest.mark.req('WRITING-MODE')
def test_author_mode_is_accepted_at_creation_and_switch(tmp_path):
    app, repo, story, scene, client = app_with_scene(tmp_path, prose=False)
    created = client.post('/api/stories', json={'title': 'Сад', 'writing_mode': 'author'})
    assert created.status_code == 200, created.text
    assert created.json()['writing_mode'] == 'author'
    story = repo.get_story(story.id)
    changed = client.put(f'/api/stories/{story.id}/writing-mode', json={'writing_mode': 'author', 'expected_revision': story.revision})
    assert changed.status_code == 200, changed.text
    assert repo.get_story(story.id).writing_mode == 'author' and repo.get_story(story.id).revision == story.revision + 1


from storygen.writing_mode import AUTHOR_WRITES  # noqa: E402
from tests.web.test_bridge_run_routes import ready, scene_app  # noqa: E402,F401


def run(client, request, request_id='r1'):
    return client.post('/api/runs', json={'request_id': request_id, 'request': request})


def prose_requests(story, scene):
    base = {'story_id': story.id, 'scene_id': scene.id}
    return [{**base, 'mode': 'stage', 'stage': 'draft'}, {**base, 'mode': 'stage', 'stage': 'edit'}, {**base, 'mode': 'scene'},
            {**base, 'mode': 'remaining'}, {**base, 'mode': 'edit_loop'},
            {**base, 'mode': 'rewrite', 'source_version_id': 'v', 'comment_set_id': 'c', 'comment_fingerprint': 'f' * 64}]


@pytest.mark.req('WRITING-MODE')
def test_author_mode_refuses_prose_runs_before_the_queue(tmp_path, ready):
    app, repo, story, scene, client = scene_app(tmp_path, 'author')
    for index, request in enumerate(prose_requests(story, scene)):
        refused = run(client, request, f'r{index}')
        assert refused.status_code == 409 and AUTHOR_WRITES in refused.text, (request, refused.text)
    assert app.state.coordinator.list_runs() == []


@pytest.mark.req('WRITING-MODE')
def test_author_mode_allows_memory_brief_and_audit_runs(tmp_path, ready):
    app, repo, story, scene, client = scene_app(tmp_path, 'author')
    base = {'story_id': story.id, 'scene_id': scene.id}
    for index, request in enumerate(({**base, 'mode': 'stage', 'stage': 'brief'}, {**base, 'mode': 'stage', 'stage': 'memory'},
                                     {**base, 'mode': 'audit', 'audit_scope': 'scene'})):
        response = run(client, request, f'a{index}')
        assert AUTHOR_WRITES not in response.text, (request, response.text)


@pytest.mark.req('WRITING-MODE')
def test_same_request_id_after_switch_returns_the_existing_run(tmp_path, ready):
    app, repo, story, scene, client = scene_app(tmp_path, 'obscura')
    request = prose_requests(story, scene)[0]
    first = run(client, request)
    assert first.status_code == 200, first.text
    story = repo.get_story(story.id)
    client.put(f'/api/stories/{story.id}/writing-mode', json={'writing_mode': 'author', 'expected_revision': story.revision})
    again = run(client, request)
    assert again.status_code == 200 and again.json()['id'] == first.json()['id']
