"""VALID-MEMORY-S09: the chat keeps the memory of a scene after a prose change through MCP keep_scene_memory."""
import pytest

pytest.importorskip('mcp')

from storygen.generation.dependencies import save_manual_prose  # noqa: E402
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
