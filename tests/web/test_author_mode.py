"""R-49: the «Пишу сам» story mode (`writing_mode='author'`): models never write or apply prose. Neutral texts, no provider."""
from typing import get_args

import pytest

from storygen.run_models import RunRequest
from storygen.writing_mode import RUN_MODE_WRITES, writes_prose
from tests.web.test_chat_stage_routes import ORIGIN, app_with_scene


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


from storygen.domain import StageAttempt  # noqa: E402
from storygen.writing_mode import AUTHOR_CHAT  # noqa: E402
from tests.web.test_writing_mode import BRIDGE, draft  # noqa: E402


def author_scene(tmp_path, prose=True):
    app, repo, story, scene, client = app_with_scene(tmp_path, prose=prose)
    story = repo.get_story(story.id)
    assert client.put(f'/api/stories/{story.id}/writing-mode', json={'writing_mode': 'author', 'expected_revision': story.revision}).status_code == 200
    return app, repo, repo.get_story(story.id), repo.get_scene(scene.id), client


@pytest.mark.req('WRITING-MODE')
def test_author_mode_refuses_external_draft_with_and_without_bridge_header(tmp_path):
    app, repo, story, scene, client = author_scene(tmp_path)
    for headers in (BRIDGE, {}):
        refused = draft(client, repo.get_scene(scene.id), headers)
        assert refused.status_code == 409 and AUTHOR_CHAT in refused.text, refused.text
    assert repo.list_versions(story.id, scene.id, 'draft') == []


@pytest.mark.req('WRITING-MODE')
def test_author_mode_keeps_manual_draft(tmp_path):
    app, repo, story, scene, client = author_scene(tmp_path)
    saved = draft(client, scene, origin=False)
    assert saved.status_code == 200, saved.text


@pytest.mark.req('WRITING-MODE')
def test_author_mode_chat_stages(tmp_path):
    app, repo, story, scene, client = author_scene(tmp_path)
    refused = client.get(f'/api/scenes/{scene.id}/chat-task/edit', headers=BRIDGE)
    assert refused.status_code == 409 and AUTHOR_CHAT in refused.text
    for stage in ('memory', 'brief'):
        assert AUTHOR_CHAT not in client.get(f'/api/scenes/{scene.id}/chat-task/{stage}', headers=BRIDGE).text, stage
    body = {'task_fingerprint': 'a' * 64, 'text': 'Текст', 'external_origin': ORIGIN}
    refused = client.post(f'/api/scenes/{scene.id}/chat-result/edit', json=body)
    assert refused.status_code == 409 and AUTHOR_CHAT in refused.text, refused.text


def model_proposal(repo, story, scene, **context):
    attempt = StageAttempt(id='p1', story_id=story.id, scene_id=scene.id, stage='edit', state='needs_review',
                           context=context, partial_path='p')
    repo.save_attempt(attempt)
    return attempt


@pytest.mark.req('WRITING-MODE')
def test_author_mode_refuses_applying_model_proposals(tmp_path):
    app, repo, story, scene, client = author_scene(tmp_path)
    model_proposal(repo, story, scene)
    body = {'selected_indices': [0], 'expected_revision': scene.revision, 'proposal_fingerprint': 'a' * 64}
    for path, extra in ((f'/api/scenes/{scene.id}/copyedits/p1', {}),
                        (f'/api/scenes/{scene.id}/rewrites/p1/apply', {'expected_comments_revision': 0})):
        refused = client.post(path, json={**body, **extra})
        assert refused.status_code == 409 and AUTHOR_WRITES in refused.text, (path, refused.text)
    assert repo.get_scene(scene.id).revision == scene.revision and repo.get_scene(scene.id).heads == scene.heads


def real_proposal(tmp_path, editor_import=None):
    """A valid editor proposal made before the switch to «Пишу сам» (cross-review: the test must apply a real one)."""
    from fastapi.testclient import TestClient
    from storygen.application.settings import AppSettings
    from storygen.web.app import create_app
    from tests.generation.test_copyedit_review import TEXT, generate
    repo, scene, draft, attempt = generate(tmp_path)
    if editor_import:
        repo.save_attempt(attempt.model_copy(update={'context': {**attempt.context, 'editor_import': editor_import}}))
    story = repo.get_story(scene.story_id)
    repo.update_writing_mode(story.id, 'author', story.revision)
    app = create_app(AppSettings(data_dir=tmp_path))
    return app.state.repo, scene, attempt, TEXT, TestClient(app, base_url='http://127.0.0.1:8765')


@pytest.mark.req('WRITING-MODE')
def test_author_mode_lets_editor_import_proposals_through(tmp_path):
    repo, scene, attempt, text, client = real_proposal(tmp_path, editor_import={'import_id': 'i', 'export_id': 'e', 'scene_index': 0})
    preview = client.get(f'/api/scenes/{scene.id}/copyedits/{attempt.id}').json()
    assert preview['can_apply'] is True and preview['source'] == 'editor_import'
    body = {'selected_indices': [1], 'expected_revision': preview['expected_revision'], 'proposal_fingerprint': preview['proposal_fingerprint']}
    applied = client.post(f'/api/scenes/{scene.id}/copyedits/{attempt.id}', json=body)
    assert applied.status_code == 200, applied.text
    prose = repo.get_scene(scene.id).heads['prose']
    assert repo.read_text(prose) == text.replace('торкалається', 'торкається')


@pytest.mark.req('WRITING-MODE')
def test_author_mode_model_proposal_preview_cannot_be_applied(tmp_path):
    """Cross-review: the review controls are inactive for a model proposal, with the mode named as the reason."""
    repo, scene, attempt, text, client = real_proposal(tmp_path)
    preview = client.get(f'/api/scenes/{scene.id}/copyedits/{attempt.id}').json()
    assert 'can_apply' in preview, preview
    assert preview['can_apply'] is False and preview['reason'] == AUTHOR_WRITES


@pytest.mark.req('WRITING-MODE')
def test_author_mode_refusals_in_english(tmp_path):
    app, repo, story, scene, client = author_scene(tmp_path)
    en = {'Accept-Language': 'en'}
    refused = draft(client, scene, {**BRIDGE, **en})
    assert refused.json()['detail'] == 'The story is in the "I write myself" mode: the author writes the prose'
    refused = client.post('/api/runs', json={'request_id': 'e1', 'request': {'story_id': story.id, 'scene_id': scene.id, 'mode': 'scene'}},
                          headers=en)
    assert refused.json()['detail'] == ('The story is in the "I write myself" mode: models do not write prose. '
                                        'Change the mode in the story settings')


@pytest.mark.req('WRITING-MODE')
def test_every_stage_of_a_stage_run_has_a_prose_decision():
    from storygen.writing_mode import PROSE_STAGES
    stages = set(get_args(get_args(RunRequest.model_fields['stage'].annotation)[0]))
    assert stages - PROSE_STAGES == {'brief', 'memory'} and stages & PROSE_STAGES == {'draft', 'edit'}


@pytest.mark.req('WRITING-MODE')
def test_bridge_run_in_author_mode_names_the_author(tmp_path):
    app, repo, story, scene, client = author_scene(tmp_path)
    request = {'story_id': story.id, 'scene_id': scene.id, 'mode': 'stage', 'stage': 'memory'}
    refused = client.post('/api/runs', json={'request_id': 'b1', 'request': request}, headers=BRIDGE)
    assert refused.status_code == 409 and AUTHOR_CHAT in refused.text, refused.text
