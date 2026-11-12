"""MCP-BRIDGE package 3: chat stage tasks and results through the real app (S40-S45). Neutral texts, no provider."""
import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import ContentRating, SceneCreate, StoryCreate
from storygen.generation.context import build_context
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.web.app import create_app

ORIGIN = {'client': 'claude-ai', 'model': 'test-model'}
PROSE = ('Марта піднялася на маяк о шостій вечора, коли туман уже ліг на затоку. На ній був вовняний светр, у руці — ліхтар.\n\n'
         'Нагорі вона виявила, що лінза тріснула, а механізм обертання зупинився.\n\n'
         'Внизу чекав Остап. Він сказав, що його човен не повернувся з моря, і попросив запалити сигнальний вогонь.\n\n'
         'Марта пообіцяла полагодити механізм до ранку й лишилася на маяку сама.')
SLOT = lambda status, text='', ev=(), reason='': {'status': status, 'text': text, 'evidence_ids': list(ev), 'reason': reason}
MEMORY = {'schema_version': 4,
          'core': {'marta': {'clothing': SLOT('changed', 'вовняний светр', ['f000001']), 'carried': SLOT('changed', 'ліхтар', ['f000001']),
                             'location': SLOT('changed', 'на маяку', ['f000001', 'f000004']), 'body': SLOT('unchanged'),
                             'company': SLOT('changed', 'сама', ['f000004'])}},
          'threads': {}, 'facts': {'add': []},
          'timeline': {'add': [{'text': 'Марта виявила тріснуту лінзу й зупинений механізм маяка.', 'evidence_ids': ['f000002']}]},
          'character_states': {'add': [{'text': 'Маяк не світить.', 'character_ids': [], 'evidence_ids': ['f000002']}], 'update': [], 'retire': []},
          'open_threads': {'add': [{'text': 'Марта пообіцяла полагодити механізм до ранку.', 'evidence_ids': ['f000004']}]}}
BRIEF = {'objective': 'Марта лагодить маяк', 'beats': ['Марта шукає шестерню'], 'constraints': [], 'proposed_changes': [], 'introduced': []}


def app_with_scene(tmp_path, prose=True, draft=False):
    app = create_app(AppSettings(data_dir=tmp_path))
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк', content_rating=ContentRating(sexual=0, violence=0, themes=0)))
    scene = repo.create_scene(story.id, SceneCreate(title='Туман', beats='Марта виявляє зламаний маяк.', character_ids=['marta']))
    if draft:
        brief = repo.save_version(story.id, scene.id, 'brief', json.dumps(BRIEF, ensure_ascii=False), [])
        repo.set_head(scene.id, 'brief', brief.id, repo.get_scene(scene.id).revision)
        version = repo.save_version(story.id, scene.id, 'draft', PROSE, [brief.id])
        repo.set_head(scene.id, 'draft', version.id, repo.get_scene(scene.id).revision)
    if prose:
        version = repo.save_version(story.id, scene.id, 'manual', PROSE, [])
        repo.set_head(scene.id, 'prose', version.id, repo.get_scene(scene.id).revision)
    return app, repo, story, repo.get_scene(scene.id), TestClient(app, base_url='http://127.0.0.1:8765')


def task(client, scene_id, stage, **params):
    response = client.get(f'/api/scenes/{scene_id}/chat-task/{stage}', params=params)
    assert response.status_code == 200, response.text
    return response.json()


def save(client, scene_id, stage, fingerprint, text):
    return client.post(f'/api/scenes/{scene_id}/chat-result/{stage}', json={'task_fingerprint': fingerprint, 'text': text, 'external_origin': ORIGIN})


def dump(value):
    return json.dumps(value, ensure_ascii=False)


@pytest.mark.req('MCP-BRIDGE')
def test_memory_task_matches_pipeline_context(tmp_path):
    """MCP-BRIDGE-S40."""
    app, repo, story, scene, client = app_with_scene(tmp_path)
    first = task(client, scene.id, 'memory', max_chars=1000)
    from storygen.application.chat_stages import chat_role_settings
    bundle = build_context(repo, scene.id, 'memory', chat_role_settings(repo, story.id, 'memory'))
    parts, offset = [first['material']], first['next_offset']
    while offset is not None:
        part = task(client, scene.id, 'memory', offset=offset, max_chars=1000)
        assert part['content_sha256'] == first['content_sha256'] and part['task_fingerprint'] == first['task_fingerprint']
        parts.append(part['material']); offset = part['next_offset']
    assert len(parts) > 1 and ''.join(parts) == bundle.user_text and first['instructions'] == bundle.system_text
    assert first['content_sha256'] == hashlib.sha256(bundle.user_text.encode('utf-8')).hexdigest()
    assert first['result_format'] == 'json' and first['revision'] == scene.revision and '[f000004]' in bundle.user_text


@pytest.mark.req('MCP-BRIDGE')
def test_memory_result_becomes_head_with_origin(tmp_path):
    """MCP-BRIDGE-S41."""
    app, repo, story, scene, client = app_with_scene(tmp_path)
    data = task(client, scene.id, 'memory')
    response = save(client, scene.id, 'memory', data['task_fingerprint'], dump(MEMORY))
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['state'] == 'completed' and repo.get_scene(scene.id).heads['memory'] == result['version_id']
    version = repo.get_version(result['version_id'])
    assert version.kind == 'memory' and version.external_origin.client == 'claude-ai' and version.external_origin.model == 'test-model'
    review = client.get(f'/api/scenes/{scene.id}/core-review').json()
    assert review['has_wire'] is True and review['memory_version_id'] == result['version_id']


@pytest.mark.req('MCP-BRIDGE')
def test_memory_result_with_violations_saves_nothing(tmp_path):
    """MCP-BRIDGE-S41: no partial memory; every violation comes back."""
    app, repo, story, scene, client = app_with_scene(tmp_path)
    data = task(client, scene.id, 'memory')
    broken = json.loads(dump(MEMORY))
    del broken['core']['marta']['body']
    broken['open_threads']['add'][0]['evidence_ids'] = ['f000009']
    before = [v.id for v in repo.list_versions(story.id) if v.kind == 'memory']
    response = save(client, scene.id, 'memory', data['task_fingerprint'], dump(broken))
    assert response.status_code == 422, response.text
    body = response.json()
    codes = {item['operation'] for item in body['memory_violations']['items']}
    assert 'core.marta.body' in str(body) and body['memory_violations']['total'] == 2 and codes
    assert 'memory' not in repo.get_scene(scene.id).heads
    assert [v.id for v in repo.list_versions(story.id) if v.kind == 'memory'] == before


@pytest.mark.req('MCP-BRIDGE')
def test_fenced_json_is_unwrapped_with_warning(tmp_path):
    """MCP-BRIDGE-S41, review focus 3."""
    app, repo, story, scene, client = app_with_scene(tmp_path)
    data = task(client, scene.id, 'memory')
    response = save(client, scene.id, 'memory', data['task_fingerprint'], '```json\n' + dump(MEMORY) + '\n```')
    assert response.status_code == 200, response.text
    assert any('обгортку' in warning for warning in response.json()['warnings'])


@pytest.mark.req('MCP-BRIDGE')
def test_brief_without_proposed_changes_becomes_head(tmp_path):
    """MCP-BRIDGE-S42."""
    app, repo, story, scene, client = app_with_scene(tmp_path, prose=False)
    data = task(client, scene.id, 'brief')
    response = save(client, scene.id, 'brief', data['task_fingerprint'], dump(BRIEF))
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['state'] == 'completed' and repo.get_scene(scene.id).heads['brief'] == result['version_id']
    assert repo.get_version(result['version_id']).external_origin.client == 'claude-ai'


@pytest.mark.req('MCP-BRIDGE')
def test_brief_with_proposed_changes_needs_review(tmp_path):
    """MCP-BRIDGE-S42."""
    app, repo, story, scene, client = app_with_scene(tmp_path, prose=False)
    data = task(client, scene.id, 'brief')
    response = save(client, scene.id, 'brief', data['task_fingerprint'], dump({**BRIEF, 'proposed_changes': ['Перенести сцену на ранок']}))
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['state'] == 'needs_review' and result['message'] and 'brief' not in repo.get_scene(scene.id).heads


@pytest.mark.req('MCP-BRIDGE')
def test_edit_prose_mode_saves_edited_version(tmp_path):
    """MCP-BRIDGE-S43."""
    app, repo, story, scene, client = app_with_scene(tmp_path, prose=False, draft=True)
    data = task(client, scene.id, 'edit')
    assert data['result_format'] == 'prose'
    response = save(client, scene.id, 'edit', data['task_fingerprint'], PROSE.replace('вовняний светр', 'теплий вовняний светр'))
    assert response.status_code == 200, response.text
    version = repo.get_version(response.json()['version_id'])
    assert version.kind == 'edited' and version.external_origin.client == 'claude-ai'
    assert repo.get_scene(scene.id).heads['prose'] == version.id


@pytest.mark.req('MCP-BRIDGE')
def test_edit_patches_review_goes_to_editor_proposals(tmp_path):
    """MCP-BRIDGE-S43, review focus 2."""
    app, repo, story, scene, client = app_with_scene(tmp_path, prose=False, draft=True)
    editor = RoleSettings(provider=ProviderSettings(model='test'), edit_mode='patches', edit_review='review', context_tokens=131072, max_output_tokens=8192)
    repo.write_role_settings(story.id, {'editor': editor.model_dump()}, repo.get_story(story.id).revision)
    data = task(client, scene.id, 'edit')
    assert data['result_format'] == 'patches'
    edits = {'edits': [{'fragment_id': 'f000001', 'original': 'вовняний', 'replacement': 'теплий', 'category': 'wording'}]}
    response = save(client, scene.id, 'edit', data['task_fingerprint'], dump(edits))
    assert response.status_code == 200, response.text
    assert response.json()['state'] == 'needs_review' and 'prose' not in repo.get_scene(scene.id).heads
    proposals = client.get(f'/api/scenes/{scene.id}/copyedits').json()['attempts']
    assert len(proposals) == 1 and proposals[0]['state'] == 'needs_review'


@pytest.mark.req('MCP-BRIDGE')
def test_stale_task_is_rejected(tmp_path):
    """MCP-BRIDGE-S44: a role settings change after the task."""
    app, repo, story, scene, client = app_with_scene(tmp_path, prose=False)
    data = task(client, scene.id, 'brief')
    planner = RoleSettings(provider=ProviderSettings(model='test'), temperature=0.1, context_tokens=131072, max_output_tokens=8192)
    repo.write_role_settings(story.id, {'planner': planner.model_dump()}, repo.get_story(story.id).revision)
    response = save(client, scene.id, 'brief', data['task_fingerprint'], dump(BRIEF))
    assert response.status_code == 409 and 'Завдання застаріло' in response.text
    assert not [v for v in repo.list_versions(story.id) if v.kind == 'brief']


@pytest.mark.req('MCP-BRIDGE')
def test_same_fingerprint_twice_is_rejected(tmp_path):
    """MCP-BRIDGE-S44, review focus 4."""
    app, repo, story, scene, client = app_with_scene(tmp_path)
    data = task(client, scene.id, 'memory')
    assert save(client, scene.id, 'memory', data['task_fingerprint'], dump(MEMORY)).status_code == 200
    again = save(client, scene.id, 'memory', data['task_fingerprint'], dump(MEMORY))
    assert again.status_code == 409, again.text
    assert len([v for v in repo.list_versions(story.id) if v.kind == 'memory']) == 1


@pytest.mark.req('MCP-BRIDGE')
def test_memory_reuse_approval_is_required(tmp_path):
    """MCP-BRIDGE-S45: the previous scene's prose changed after its memory; the author confirms reuse in Obscura."""
    app, repo, story, first, client = app_with_scene(tmp_path)
    data = task(client, first.id, 'memory')
    assert save(client, first.id, 'memory', data['task_fingerprint'], dump(MEMORY)).status_code == 200
    second = repo.create_scene(story.id, SceneCreate(title='Ранок', beats='Світанок.', character_ids=['marta']))
    prose = repo.save_version(story.id, second.id, 'manual', 'До світанку Марта полагодила механізм.', [])
    repo.set_head(second.id, 'prose', prose.id, repo.get_scene(second.id).revision)
    edited = client.post(f'/api/scenes/{first.id}/prose', json={'text': PROSE + '\n\nВітер ущух.', 'expected_revision': repo.get_scene(first.id).revision})
    assert edited.status_code == 200, edited.text
    response = client.get(f'/api/scenes/{second.id}/chat-task/memory')
    assert response.status_code == 409, response.text
    assert 'потребує вашого підтвердження в Obscura' in response.json()['detail_original']


@pytest.mark.req('MCP-BRIDGE')
def test_missing_previous_stage_is_400(tmp_path):
    """Review focus 5."""
    app, repo, story, scene, client = app_with_scene(tmp_path, prose=False)
    for stage in ('memory', 'edit'):
        response = client.get(f'/api/scenes/{scene.id}/chat-task/{stage}')
        assert response.status_code == 400 and 'Спершу' in response.json()['detail_original'], response.text


@pytest.mark.req('MCP-BRIDGE')
def test_no_provider_call_and_no_token_observation(tmp_path, monkeypatch):
    from storygen.application.chat_stages import ExternalTextGateway
    import storygen.token_budget.service as budget
    calls = []
    monkeypatch.setattr(budget, 'record_usage', lambda *args, **kwargs: calls.append(args))
    monkeypatch.setattr('storygen.providers.client.ProviderClient', None, raising=False)
    app, repo, story, scene, client = app_with_scene(tmp_path)
    data = task(client, scene.id, 'memory')
    assert save(client, scene.id, 'memory', data['task_fingerprint'], dump(MEMORY)).status_code == 200
    assert calls == [] and not hasattr(ExternalTextGateway('x'), 'bind_accounting')
    attempt = [a for a in repo.list_attempts(story.id) if a.stage == 'memory'][-1]
    assert attempt.context['external_origin']['client'] == 'claude-ai' and 'accounting' not in attempt.context
