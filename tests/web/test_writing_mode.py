"""WRITING-MODE: the story writing mode and the checks for requests from the MCP bridge. Neutral texts, no provider."""
import json

from storygen.generation.dependencies import writing_fingerprint
from storygen.web.bridge_marker import MODE_OWNER_ONLY, OBSCURA_WRITES
from tests.web.test_chat_stage_routes import ORIGIN, PROSE, app_with_scene, task

BRIDGE = {'X-Obscura-Client': 'mcp'}


def set_mode(client, story, mode, headers=None):
    return client.put(f'/api/stories/{story.id}/writing-mode', json={'writing_mode': mode, 'expected_revision': story.revision}, headers=headers or {})


def draft(client, scene, headers=None, origin=True):
    body = {'text': PROSE, 'expected_revision': scene.revision}
    if origin:
        repo = client.app.state.repo
        body.update(external_origin=ORIGIN, expected_context_fingerprint=writing_fingerprint(repo, repo.get_scene(scene.id)),
                    expected_draft_version_id=scene.heads.get('draft'))
    return client.post(f'/api/scenes/{scene.id}/draft', json=body, headers=headers or {})


def test_story_mode_defaults_to_chat_and_is_set_at_creation(tmp_path):
    app, repo, story, scene, client = app_with_scene(tmp_path, prose=False)
    story = repo.get_story(story.id)
    assert story.writing_mode == 'chat'
    created = client.post('/api/stories', json={'title': 'Сад', 'writing_mode': 'obscura'})
    assert created.status_code == 200, created.text
    assert created.json()['writing_mode'] == 'obscura'
    assert client.post('/api/stories', json={'title': 'Сад', 'writing_mode': 'both'}).status_code == 422


def test_stored_story_without_the_field_reads_as_chat(tmp_path):
    app, repo, story, scene, client = app_with_scene(tmp_path, prose=False)
    story = repo.get_story(story.id)
    payload = json.loads(story.model_dump_json())
    payload.pop('writing_mode')
    with repo.db.connection() as db:
        db.execute('UPDATE stories SET payload=? WHERE id=?', (json.dumps(payload), story.id))
    assert repo.get_story(story.id).writing_mode == 'chat'


def test_author_changes_mode_with_revision(tmp_path):
    app, repo, story, scene, client = app_with_scene(tmp_path, prose=False)
    story = repo.get_story(story.id)
    changed = set_mode(client, story, 'obscura')
    assert changed.status_code == 200, changed.text
    assert changed.json()['writing_mode'] == 'obscura' and changed.json()['revision'] == story.revision + 1
    stale = set_mode(client, story, 'chat')
    assert stale.status_code == 409
    assert repo.get_story(story.id).writing_mode == 'obscura'
    current = repo.get_story(story.id)
    same = set_mode(client, current, 'obscura')
    assert same.status_code == 200 and same.json()['revision'] == current.revision


def test_bridge_cannot_change_mode(tmp_path):
    app, repo, story, scene, client = app_with_scene(tmp_path, prose=False)
    story = repo.get_story(story.id)
    refused = set_mode(client, story, 'obscura', BRIDGE)
    assert refused.status_code == 403
    assert refused.json()['detail'] == MODE_OWNER_ONLY
    assert repo.get_story(story.id).writing_mode == 'chat'


def test_obscura_mode_refuses_bridge_texts_but_not_the_author(tmp_path):
    app, repo, story, scene, client = app_with_scene(tmp_path, prose=True)
    story = repo.get_story(story.id)
    set_mode(client, story, 'obscura')
    scene = repo.get_scene(scene.id)
    refused = draft(client, scene, BRIDGE)
    assert refused.status_code == 409 and OBSCURA_WRITES in refused.text
    task_refused = client.get(f'/api/scenes/{scene.id}/chat-task/memory', headers=BRIDGE)
    assert task_refused.status_code == 409 and OBSCURA_WRITES in task_refused.text
    result_refused = client.post(f'/api/scenes/{scene.id}/chat-result/memory', headers=BRIDGE,
                                 json={'task_fingerprint': '0' * 64, 'text': '{}', 'external_origin': ORIGIN})
    assert result_refused.status_code == 409 and OBSCURA_WRITES in result_refused.text
    assert len(repo.list_versions(story.id, scene.id)) == 1
    context = client.get(f'/api/scenes/{scene.id}/writing-context', headers=BRIDGE)
    assert context.status_code == 200
    author = draft(client, scene, origin=False)
    assert author.status_code == 200, author.text


def test_chat_mode_keeps_bridge_writes(tmp_path):
    app, repo, story, scene, client = app_with_scene(tmp_path, prose=True)
    story = repo.get_story(story.id)
    assert draft(client, scene, BRIDGE).status_code == 200
    data = client.get(f'/api/scenes/{scene.id}/chat-task/memory', headers=BRIDGE)
    assert data.status_code == 200, data.text


def test_refusals_are_translated_for_english_locale(tmp_path):
    app, repo, story, scene, client = app_with_scene(tmp_path, prose=True)
    story = repo.get_story(story.id)
    refused = set_mode(client, story, 'obscura', {**BRIDGE, 'Accept-Language': 'en'})
    assert refused.json()['detail'] != MODE_OWNER_ONLY
