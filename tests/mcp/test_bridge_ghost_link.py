"""MCP-BRIDGE package 7: open_ghost_mode hands out a link only for the scene's current draft (S25)."""
import pytest

pytest.importorskip('mcp')

from storygen.domain import ContentRating, SceneCreate, StoryCreate  # noqa: E402
from storygen.mcp.bridge import build_server  # noqa: E402

from tests.mcp.test_bridge import _recording_server, call, fresh_save, obscura, text  # noqa: E402

BASE = 'http://127.0.0.1:8765'


def drafted(tmp_path, **story):
    app, http = obscura(tmp_path)
    repo = app.state.repo
    created = repo.create_story(StoryCreate(title='Маяк'))
    if story:
        created = repo.update_story_rating(created.id, ContentRating(**story), created.revision)
    scene = repo.create_scene(created.id, SceneCreate(title='Лист', beats='Анна знаходить лист.'))
    server = build_server(http, client_name='Codex')
    assert not fresh_save(server, http, scene.id, 'Чернетка з чату.', None).is_error
    return app, http, server, created, repo.get_scene(scene.id)


@pytest.mark.req('MCP-BRIDGE')
@pytest.mark.parametrize('with_id', [True, False])
def test_link_for_the_current_draft(tmp_path, with_id):
    app, http, server, story, scene = drafted(tmp_path)
    head = scene.heads['draft']
    arguments = {'story_id': story.id, 'scene_id': scene.id, **({'draft_version_id': head} if with_id else {})}
    result = call(server, 'open_ghost_mode', arguments)
    assert not result.is_error, text(result)
    suffix = f'&draft={head}' if with_id else ''
    assert result.structured_content == {'url': f'{BASE}/stories/{story.id}?scene={scene.id}&material=draft&ghost=1{suffix}', 'draft_version_id': head}
    assert app.state.repo.get_scene(scene.id) == scene


@pytest.mark.req('MCP-BRIDGE')
def test_scene_without_draft_gets_no_link(tmp_path):
    app, http = obscura(tmp_path)
    story = app.state.repo.create_story(StoryCreate(title='Маяк'))
    scene = app.state.repo.create_scene(story.id, SceneCreate(title='Лист'))
    result = call(build_server(http), 'open_ghost_mode', {'story_id': story.id, 'scene_id': scene.id})
    assert result.is_error and 'чернетки' in text(result) and 'ghost=1' not in text(result)


@pytest.mark.req('MCP-BRIDGE')
def test_stale_draft_id_gets_no_link(tmp_path):
    app, http, server, story, scene = drafted(tmp_path)
    old = scene.heads['draft']
    author = http.post(f'/api/scenes/{scene.id}/draft', json={'text': 'Правка автора.', 'expected_revision': scene.revision})
    assert author.status_code == 200, author.text
    result = call(server, 'open_ghost_mode', {'story_id': story.id, 'scene_id': scene.id, 'draft_version_id': old})
    assert result.is_error and 'get_scene_text' in text(result) and 'ghost=1' not in text(result)


@pytest.mark.req('MCP-BRIDGE')
def test_scene_of_another_story_gets_no_link(tmp_path):
    app, http, server, story, scene = drafted(tmp_path)
    other = app.state.repo.create_story(StoryCreate(title='Інший'))
    result = call(server, 'open_ghost_mode', {'story_id': other.id, 'scene_id': scene.id})
    assert result.is_error and 'ghost=1' not in text(result)


@pytest.mark.req('MCP-BRIDGE')
def test_store_edition_still_gets_a_link(tmp_path, store_edition):
    # The mode itself is not limited by the edition rating, so the tool does not use writing-context.
    app, http = obscura(tmp_path)
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк'))
    scene = repo.create_scene(story.id, SceneCreate(title='Лист'))
    draft = repo.save_version(story.id, scene.id, 'draft', 'Чернетка.', [])
    repo.set_head(scene.id, 'draft', draft.id, scene.revision)
    with repo.db.connection() as db:
        current = repo.get_story(story.id).model_copy(update={'content_rating': ContentRating(sexual=2, violence=0, themes=0)})
        db.execute('UPDATE stories SET payload=? WHERE id=?', (current.model_dump_json(), story.id))
    result = call(build_server(http), 'open_ghost_mode', {'story_id': story.id, 'scene_id': scene.id})
    assert not result.is_error, text(result)
    assert result.structured_content['draft_version_id'] == draft.id


@pytest.mark.req('MCP-BRIDGE')
@pytest.mark.parametrize('arguments', [{'story_id': '..', 'scene_id': 'S1'}, {'story_id': 'S1', 'scene_id': 'a/b'},
                                       {'story_id': 'S1', 'scene_id': 'C1', 'draft_version_id': '../x'}])
def test_identifiers_are_checked_before_the_request(arguments):
    seen = []
    result = call(_recording_server(seen), 'open_ghost_mode', arguments)
    assert result.is_error and 'ідентифікатор' in text(result) and seen == []


@pytest.mark.req('MCP-BRIDGE')
def test_next_steps_suggests_open_ghost_mode(tmp_path):
    app, http, server, story, scene = drafted(tmp_path)
    assert 'open_ghost_mode' in text(call(server, 'next_steps', {'scene_id': scene.id}))
