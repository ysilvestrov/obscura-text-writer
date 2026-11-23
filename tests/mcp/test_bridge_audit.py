"""R-44 PR 4: start_run(action='audit') checks the links of one scene or of the whole book through the real Obscura app.

The auditor writes no story text, so the story's writing mode does not limit the action; the preview without confirm still
starts nothing, and the launch carries the plan fingerprint the author saw."""
import pytest

pytest.importorskip('mcp')

from fastapi.testclient import TestClient  # noqa: E402

from storygen.application.settings import AppSettings  # noqa: E402
from storygen.billing.service import set_limit  # noqa: E402
from storygen.mcp.bridge import BRIDGE_HEADERS, build_server  # noqa: E402
from storygen.providers.models import ProviderSettings  # noqa: E402
from storygen.web.app import create_app  # noqa: E402

from tests.generation.test_audit_context import auditor  # noqa: E402
from tests.generation.test_audit_cost import tariff  # noqa: E402
from tests.generation.test_audit_run import Answers, DISCREPANCY, drive, four_scenes, start_book  # noqa: E402
from tests.generation.test_audit_verdict import answer, unchecked_scene  # noqa: E402
from tests.mcp.test_bridge import call, text  # noqa: E402
from tests.mcp.test_bridge_settings import ok  # noqa: E402


def bridge(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))
    http = TestClient(app, base_url='http://127.0.0.1:8765')
    http.headers.update(BRIDGE_HEADERS)
    return app, build_server(http)


def setup(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    app, server = bridge(tmp_path)
    return app, story, scene, server


def run_ids(app):
    return {run.id for run in app.state.coordinator.list_runs()}


def test_preview_without_confirm_starts_nothing_in_a_chat_story(tmp_path):
    app, story, scene, server = setup(tmp_path)
    assert app.state.repo.get_story(story.id).writing_mode == 'chat'
    before = run_ids(app)
    data = ok(call(server, 'start_run', {'story_id': story.id, 'action': 'audit'}))
    assert data['started'] is False
    preview = data['preview']
    assert preview['ready'] is True and preview['calls'] == 2 and preview['invalid_scenes'] == 1
    assert preview['roles'] == {'auditor': {'provider': 'local', 'model': 'auditor'}}
    assert [(link['scene_id'], link['link']) for link in preview['links']] == [(scene.id, 'brief'), (scene.id, 'prose')]
    assert len(preview['plan_fingerprint']) == 64
    assert preview['cost'] == {'per_call_usd': None, 'total_usd': None, 'reason': None}
    assert set(preview['budget']) == {'limit_usd', 'spent_usd', 'available_usd', 'default_run_limit_usd'}
    assert run_ids(app) == before


def test_confirm_starts_book_validation_with_the_previewed_fingerprint(tmp_path):
    app, story, scene, server = setup(tmp_path)
    fingerprint = ok(call(server, 'start_run', {'story_id': story.id, 'action': 'audit'}))['preview']['plan_fingerprint']
    data = ok(call(server, 'start_run', {'story_id': story.id, 'action': 'audit', 'confirm': True, 'plan_fingerprint': fingerprint}))
    assert data['started'] is True and data['state'] == 'queued'
    run = app.state.coordinator.get_run(data['run_id'])
    assert run.origin == 'mcp' and run.request.mode == 'audit' and run.request.audit_scope == 'story'
    assert run.request.scene_id is None and run.request.audit_plan_fingerprint == fingerprint
    state = ok(call(server, 'get_run', {'run_id': run.id}))
    assert state['action'] == 'audit' and state['audit_scope'] == 'story' and state['checkpoint'] is None


def test_scene_id_selects_the_scene_scope(tmp_path):
    app, story, scene, server = setup(tmp_path)
    preview = ok(call(server, 'start_run', {'story_id': story.id, 'action': 'audit', 'scene_id': scene.id}))['preview']
    assert preview['calls'] == 2 and [link['link'] for link in preview['links']] == ['brief', 'prose']
    data = ok(call(server, 'start_run', {'story_id': story.id, 'action': 'audit', 'scene_id': scene.id, 'confirm': True,
                                         'plan_fingerprint': preview['plan_fingerprint']}))
    run = app.state.coordinator.get_run(data['run_id'])
    assert run.request.audit_scope == 'scene' and run.request.scene_id == scene.id
    assert run.request.audit_plan_fingerprint == preview['plan_fingerprint']


def test_confirm_needs_the_fingerprint_of_the_shown_preview(tmp_path):
    app, story, scene, server = setup(tmp_path)
    before = run_ids(app)
    missing = call(server, 'start_run', {'story_id': story.id, 'action': 'audit', 'confirm': True})
    assert missing.is_error and 'plan_fingerprint' in text(missing)
    stale = call(server, 'start_run', {'story_id': story.id, 'action': 'audit', 'confirm': True, 'plan_fingerprint': '0' * 64})
    assert stale.is_error and 'План перевірки змінився' in text(stale)
    assert run_ids(app) == before


def test_cloud_preview_carries_the_upper_bound_of_cost(tmp_path):
    app, story, scene, server = setup(tmp_path)
    repo = app.state.repo
    auditor(repo, story, provider=ProviderSettings(provider='openrouter', model='cloud-model'), max_input_chars=1000,
            max_output_tokens=1000)
    tariff(repo)
    set_limit(repo, 'story:' + story.id, '10', 0)
    preview = ok(call(server, 'start_run', {'story_id': story.id, 'action': 'audit'}))['preview']
    assert preview['ready'] is True, preview['reason']
    assert preview['cost'] == {'per_call_usd': '0.0063', 'total_usd': '0.0126', 'reason': None}
    assert preview['budget']['limit_usd'] == '10.0000'


def test_get_run_of_a_stopped_book_validation_names_the_scene(tmp_path):
    repo, story, (s1, s2, s3, s4), _ = four_scenes(tmp_path)
    worker, run = start_book(repo, story, Answers(answer(95), DISCREPANCY))
    assert drive(worker, run.id).state == 'needs_review'
    app, server = bridge(tmp_path)
    state = ok(call(server, 'get_run', {'run_id': run.id}))
    assert state['state'] == 'needs_review' and state['action'] == 'audit' and state['audit_scope'] == 'story'
    assert state['checkpoint']['scene_id'] == s3.id and state['checkpoint']['phase'] == 'awaiting_author'
    assert state['scene_id'] is None
