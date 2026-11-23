import pytest
from storygen.mcp.bridge import scene_state


@pytest.mark.req('VALID-LINKS')
@pytest.mark.parametrize('heads,status,expected', [
    ({}, None, 'not_started'),
    ({'brief': 'b'}, {'validity': 'incomplete'}, 'no_text'),
    ({'brief': 'b', 'draft': 'd'}, {'validity': 'incomplete'}, 'draft'),
    ({'brief': 'b', 'prose': 'p'}, {'validity': 'valid'}, 'prose'),
    ({'brief': 'b', 'prose': 'p'}, {'validity': 'unchecked'}, 'needs_review'),
    ({'brief': 'b', 'prose': 'p'}, {'validity': 'discrepancy'}, 'needs_review'),
    ({'prose': 'p'}, {'validity': 'incomplete', 'prose': 'current'}, 'prose'),
])
def test_scene_state_keeps_client_words_for_validity(heads, status, expected):
    assert scene_state({'heads': heads}, status) == expected


@pytest.mark.req('VALID-LINKS')
def test_get_story_reports_validity_and_links(tmp_path):
    from tests.mcp.test_bridge import obscura, call, text, build_server
    from storygen.domain import StoryCreate, SceneCreate
    from storygen.generation.dependencies import save_manual_prose
    app, http = obscura(tmp_path)
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк'))
    scene = repo.create_scene(story.id, SceneCreate(title='Перша'))
    brief = repo.save_version(story.id, scene.id, 'brief', '{"objective":"Світло","beats":["Маяк"],"constraints":[],"proposed_changes":[]}', [])
    repo.set_head(scene.id, 'brief', brief.id, repo.get_scene(scene.id).revision)
    save_manual_prose(repo, scene.id, 'Світло на воді.', repo.get_scene(scene.id).revision)
    result = call(build_server(http), 'get_story', {'story_id': story.id})
    assert not result.is_error, text(result)
    (row,) = result.structured_content['scenes']
    assert row['state'] == 'needs_review' and row['validity'] == 'unchecked'
    assert row['links'] == {'brief': 'unchecked', 'prose': 'unchecked', 'memory': 'unavailable'}
