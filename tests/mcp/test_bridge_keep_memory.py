"""VALID-MEMORY-S09: the chat keeps the memory of a scene after a prose change through MCP keep_scene_memory."""
import pytest

pytest.importorskip('mcp')

import httpx  # noqa: E402

from storygen.domain import StoryCreate  # noqa: E402
from storygen.generation.dependencies import save_manual_prose  # noqa: E402
from storygen.mcp.bridge import build_server  # noqa: E402
from storygen.storage.links import link_state  # noqa: E402

from tests.mcp.test_bridge import call, text  # noqa: E402
from tests.mcp.test_bridge_audit import bridge  # noqa: E402
from tests.mcp.test_bridge_settings import ok  # noqa: E402
from tests.storage.test_links import book  # noqa: E402


def changed_prose(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    old = repo.get_scene(scene.id).heads['prose']
    save_manual_prose(repo, scene.id, repo.read_text(old) + '\n\nЗа вікном стемніло.', repo.get_scene(scene.id).revision)
    app, server = bridge(tmp_path)
    return app.state.repo, story, repo.get_scene(scene.id), server


@pytest.mark.req('VALID-MEMORY')
def test_keep_scene_memory_records_the_author_decision_and_equivalence(tmp_path):
    repo, story, scene, server = changed_prose(tmp_path)
    assert link_state(repo.context_view(story.id), scene.id, 'memory').status == 'unchecked'
    data = ok(call(server, 'keep_scene_memory', {'story_id': story.id, 'scene_id': scene.id,
        'prose_version_id': scene.heads['prose'], 'memory_version_id': scene.heads['memory']}))
    assert data['memory'] == 'valid'
    view = repo.context_view(story.id)
    state = link_state(view, scene.id, 'memory')
    assert (state.status, state.source) == ('valid', 'author')
    assert [(e.scene_id, e.new_prose_id) for e in view.prose_equivalences] == [(scene.id, scene.heads['prose'])]
    assert repo.get_scene(scene.id).heads['memory'] == scene.heads['memory']


@pytest.mark.req('VALID-MEMORY')
def test_keep_scene_memory_refuses_a_prose_read_before_a_change(tmp_path):
    repo, story, scene, server = changed_prose(tmp_path)
    stale = [v.id for v in repo.list_versions(story.id, scene.id) if v.kind == 'edited'][0]
    result = call(server, 'keep_scene_memory', {'story_id': story.id, 'scene_id': scene.id,
        'prose_version_id': stale, 'memory_version_id': scene.heads['memory']})
    assert result.is_error and 'прочитайте їх знову' in text(result)
    view = repo.context_view(story.id)
    assert link_state(view, scene.id, 'memory').status == 'unchecked' and not view.prose_equivalences


@pytest.mark.req('VALID-MEMORY')
def test_keep_scene_memory_leaves_an_auditor_discrepancy_to_the_author(tmp_path):
    from storygen.storage.link_decisions import write_auditor_verdict
    repo, story, scene, server = changed_prose(tmp_path)
    state = link_state(repo.context_view(story.id), scene.id, 'memory')
    assert write_auditor_verdict(repo, story.id, scene.id, 'memory', fingerprint=state.fingerprint, marker=None,
                                 outcome='discrepancy', confidence=40, reason='Місто не те')[0] == 'written'
    result = call(server, 'keep_scene_memory', {'story_id': story.id, 'scene_id': scene.id,
        'prose_version_id': scene.heads['prose'], 'memory_version_id': scene.heads['memory']})
    assert result.is_error and 'рішення ухвалює автор' in text(result)
    view = repo.context_view(story.id)
    assert link_state(view, scene.id, 'memory').status == 'discrepancy' and not view.prose_equivalences


@pytest.mark.req('VALID-MEMORY')
def test_keep_scene_memory_twice_and_for_another_story(tmp_path):
    repo, story, scene, server = changed_prose(tmp_path)
    arguments = {'story_id': story.id, 'scene_id': scene.id, 'prose_version_id': scene.heads['prose'],
                 'memory_version_id': scene.heads['memory']}
    assert ok(call(server, 'keep_scene_memory', arguments))['memory'] == 'valid'
    verdicts = dict(repo.context_view(story.id).link_verdicts)
    assert ok(call(server, 'keep_scene_memory', arguments))['memory'] == 'valid'
    assert dict(repo.context_view(story.id).link_verdicts) == verdicts
    other = repo.create_story(StoryCreate(title='Інший'))
    result = call(server, 'keep_scene_memory', {**arguments, 'story_id': other.id})
    assert result.is_error and 'Сцени немає в цьому творі' in text(result)


@pytest.mark.req('VALID-MEMORY')
@pytest.mark.parametrize('link, message', [
    ({'status': 'unavailable', 'reason': 'carry_pending', 'fingerprint': None}, 'дочекайтеся завершення переносу'),
    ({'status': 'unavailable', 'reason': 'carry_failed', 'fingerprint': None}, 'створіть нову пам’ять цієї сцени'),
    ({'status': 'unavailable', 'reason': 'no_memory', 'fingerprint': None}, 'спершу створіть пам’ять сцени'),
])
def test_keep_scene_memory_explains_a_link_it_cannot_keep(link, message):
    posts = []

    def serve(request):
        if request.method == 'POST':
            posts.append(request.url.path)
        return httpx.Response(200, json={'scenes': [{'id': 's1', 'heads': {'prose': 'p1', 'memory': 'm1'}}],
                                         'material_status': {'s1': {'links': {'memory': link}, 'validity': 'unchecked'}}})
    server = build_server(httpx.Client(base_url='http://127.0.0.1:8765', transport=httpx.MockTransport(serve)))
    result = call(server, 'keep_scene_memory', {'story_id': 'st1', 'scene_id': 's1', 'prose_version_id': 'p1',
                                                'memory_version_id': 'm1'})
    assert result.is_error and message in text(result) and posts == []
