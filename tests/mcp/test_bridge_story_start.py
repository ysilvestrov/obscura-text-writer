"""MCP-BRIDGE package 2: starting and configuring a story from the chat, through the real Obscura app."""
import json
from pathlib import Path

import httpx
import pytest

pytest.importorskip('mcp')

from storygen.domain import SceneCreate, StoryCreate  # noqa: E402
from storygen.mcp.bridge import build_server  # noqa: E402

from tests.mcp.test_bridge import CHARACTERS, PLAN, _recording_server, call, fresh_save, obscura, read_text, text  # noqa: E402

TEMPLATES = Path(__file__).resolve().parents[2] / 'src' / 'storygen' / 'web' / 'static' / 'templates'
RATING = {'sexual': 0, 'violence': 1, 'themes': 0}


def ok(result):
    assert not result.is_error, text(result)
    return result.structured_content


def error_payload(result):
    assert result.is_error
    message = text(result)
    return json.loads(message[message.index('{'):message.rindex('}') + 1])


def imported_story(app, http):
    story = app.state.repo.create_story(StoryCreate(title='Маяк'))
    form = http.post(f'/api/stories/{story.id}/sources', files=[('plan', ('plan.md', PLAN.encode(), 'text/markdown')),
                                                               ('characters', ('characters.md', CHARACTERS.encode(), 'text/markdown'))])
    assert form.status_code == 200, form.text
    return story


@pytest.mark.req('MCP-BRIDGE')
@pytest.mark.unrated_stories
def test_create_story_returns_id_revision_language_rating(tmp_path):
    app, http = obscura(tmp_path)
    data = ok(call(build_server(http), 'create_story', {'title': 'Острів', 'language': 'en', 'content_rating': RATING}))
    story = app.state.repo.get_story(data['id'])
    assert data == {'id': story.id, 'title': 'Острів', 'revision': story.revision, 'language': 'en', 'content_rating': RATING,
                    'target_words': 7000}
    assert story.initial_content_rating.model_dump() == RATING


@pytest.mark.req('MCP-BRIDGE')
@pytest.mark.unrated_stories
def test_create_story_over_store_limit_is_error_and_nothing_created(tmp_path, store_edition):
    app, http = obscura(tmp_path)
    result = call(build_server(http), 'create_story', {'title': 'Острів', 'content_rating': {'sexual': 2, 'violence': 0, 'themes': 0}})
    assert result.is_error and '400' in text(result)
    assert http.get('/api/stories').json() == []


@pytest.mark.req('MCP-BRIDGE')
@pytest.mark.parametrize('language,suffix', [('uk', ''), ('en', '-en')])
def test_templates_match_static_files(tmp_path, language, suffix):
    app, http = obscura(tmp_path)
    data = ok(call(build_server(http), 'get_templates', {'language': language}))
    assert data['plan_markdown'] == (TEMPLATES / f'story-plan{suffix}.md').read_text(encoding='utf-8')
    assert data['characters_markdown'] == (TEMPLATES / f'characters{suffix}.md').read_text(encoding='utf-8')
    assert 'import_plan_and_characters' in data['hint']


@pytest.mark.req('MCP-BRIDGE')
def test_templates_unknown_language_is_refused_without_request():
    seen = []
    result = call(_recording_server(seen), 'get_templates', {'language': '../de'})
    assert result.is_error and seen == []


@pytest.mark.req('MCP-BRIDGE')
def test_get_story_has_revision_rating_target_and_characters(tmp_path):
    app, http = obscura(tmp_path)
    story = imported_story(app, http)
    data = ok(call(build_server(http), 'get_story', {'story_id': story.id}))
    current = app.state.repo.get_story(story.id)
    assert data['revision'] == current.revision and data['target_words'] == 7000
    assert data['content_rating'] == current.content_rating.model_dump()
    assert [c['name'] for c in data['characters']] == ['Анна'] and data['characters'][0]['id']
    assert [s['title'] for s in data['scenes']] == ['Лист']


@pytest.mark.req('MCP-BRIDGE')
def test_update_story_applies_title_language_rating_in_order(tmp_path):
    app, http = obscura(tmp_path)
    story = app.state.repo.create_story(StoryCreate(title='Маяк'))
    data = ok(call(build_server(http), 'update_story', {'story_id': story.id, 'expected_revision': story.revision,
                                                        'title': 'Острів', 'language': 'en', 'content_rating': RATING}))
    current = app.state.repo.get_story(story.id)
    assert data == {'revision': current.revision, 'applied': ['title', 'language', 'content_rating']}
    assert (current.title, current.language, current.content_rating.model_dump()) == ('Острів', 'en', RATING)


@pytest.mark.req('MCP-BRIDGE')
def test_update_story_stops_on_locked_language(tmp_path):
    app, http = obscura(tmp_path)
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк'))
    scene = repo.create_scene(story.id, SceneCreate(title='Лист', beats='Анна знаходить лист.'))
    server = build_server(http, client_name='Codex')
    assert not fresh_save(server, http, scene.id, 'Чернетка з чату.', None).is_error
    payload = error_payload(call(server, 'update_story', {'story_id': story.id, 'expected_revision': repo.get_story(story.id).revision,
                                                          'title': 'Острів', 'language': 'en', 'content_rating': RATING}))
    assert payload['applied'] == ['title'] and payload['rejected'] == 'language' and payload['not_attempted'] == ['content_rating']
    assert '409' in payload['error']
    current = repo.get_story(story.id)
    assert (current.title, current.language) == ('Острів', 'uk') and payload['revision'] == current.revision


@pytest.mark.req('MCP-BRIDGE')
def test_update_story_timeout_is_unknown(tmp_path):
    app, http = obscura(tmp_path)
    story = app.state.repo.create_story(StoryCreate(title='Маяк'))

    def forward(request):
        if request.url.path.endswith('/language'):
            raise httpx.ReadTimeout('timed out', request=request)
        response = http.request(request.method, request.url.path, content=request.content, headers=dict(request.headers))
        return httpx.Response(response.status_code, content=response.content, headers=response.headers)
    server = build_server(httpx.Client(base_url='http://127.0.0.1:8765', transport=httpx.MockTransport(forward)))
    payload = error_payload(call(server, 'update_story', {'story_id': story.id, 'expected_revision': story.revision,
                                                          'title': 'Острів', 'language': 'en', 'content_rating': RATING}))
    assert payload['applied'] == ['title'] and payload['unknown'] == 'language' and payload['not_attempted'] == ['content_rating']
    assert 'get_story' in text(call(server, 'update_story', {'story_id': story.id, 'expected_revision': 0, 'language': 'en'}))


@pytest.mark.req('MCP-BRIDGE')
def test_update_story_needs_a_field():
    seen = []
    result = call(_recording_server(seen), 'update_story', {'story_id': 'S1', 'expected_revision': 1})
    assert result.is_error and seen == []


@pytest.mark.req('MCP-BRIDGE')
def test_add_scene_without_plan_gets_previous_plan_and_characters(tmp_path):
    app, http = obscura(tmp_path)
    story = imported_story(app, http)
    first = app.state.repo.list_scenes(story.id)[0]
    anna = next(iter(http.get(f'/api/stories/{story.id}').json()['character_names']))
    data = ok(call(build_server(http), 'add_scene', {'story_id': story.id, 'title': 'Маяк уночі', 'position': 1, 'character_ids': [anna]}))
    scene = app.state.repo.get_scene(data['id'])
    assert data == {'id': scene.id, 'position': 1, 'revision': scene.revision, 'title': 'Маяк уночі'}
    assert scene.character_ids == [anna]
    assert scene.beats.strip(), 'SCENE-PLAN-TEMPLATE: a scene added without a plan starts from the previous plan'


@pytest.mark.req('MCP-BRIDGE')
@pytest.mark.parametrize('arguments', [{'plan_markdown': 'План.'}, {'plan_version_id': 'abc', 'title': 'Нова'}])
def test_update_scene_plan_needs_version_id_and_vice_versa(arguments):
    seen = []
    result = call(_recording_server(seen), 'update_scene', {'story_id': 'S1', 'scene_id': 'C1', 'expected_revision': 1, **arguments})
    assert result.is_error and seen == []


@pytest.mark.req('MCP-BRIDGE')
def test_update_scene_stale_plan_is_error(tmp_path):
    app, http = obscura(tmp_path)
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк'))
    scene = repo.create_scene(story.id, SceneCreate(title='Лист'))
    server = build_server(http)
    seen = read_text(server, scene.id, 'plan')
    author = http.patch(f'/api/scenes/{scene.id}', json={'story_id': story.id, 'expected_revision': repo.get_scene(scene.id).revision,
                                                         'beats': 'План автора.'})
    assert author.status_code == 200, author.text
    result = call(server, 'update_scene', {'story_id': story.id, 'scene_id': scene.id, 'expected_revision': repo.get_scene(scene.id).revision,
                                           'plan_markdown': 'План із чату.', 'plan_version_id': seen['version_id']})
    assert result.is_error and '409' in text(result) and 'get_scene_text' in text(result)
    assert repo.get_scene(scene.id).beats == 'План автора.'


@pytest.mark.req('MCP-BRIDGE')
def test_update_scene_plan_and_title(tmp_path):
    app, http = obscura(tmp_path)
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк'))
    scene = repo.create_scene(story.id, SceneCreate(title='Лист'))
    server = build_server(http)
    seen = read_text(server, scene.id, 'plan')
    data = ok(call(server, 'update_scene', {'story_id': story.id, 'scene_id': scene.id, 'expected_revision': scene.revision,
                                            'plan_markdown': 'План із чату.', 'plan_version_id': seen['version_id'],
                                            'title': 'Лист у шухляді', 'target_words': 1500, 'prose_language': 'en'}))
    current = repo.get_scene(scene.id)
    assert data == {'id': scene.id, 'revision': current.revision, 'title': 'Лист у шухляді', 'plan_version_id': current.heads['plan']}
    assert (current.beats, current.target_words, current.prose_language) == ('План із чату.', 1500, 'en')


@pytest.mark.req('MCP-BRIDGE')
def test_update_scene_bad_character_id_is_refused():
    seen = []
    result = call(_recording_server(seen), 'update_scene', {'story_id': 'S1', 'scene_id': 'C1', 'expected_revision': 1, 'character_ids': ['../x']})
    assert result.is_error and 'ідентифікатор' in text(result) and seen == []


@pytest.mark.req('MCP-BRIDGE')
def test_plan_from_chat_keeps_language_unlocked(tmp_path):
    app, http = obscura(tmp_path)
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк'))
    scene = repo.create_scene(story.id, SceneCreate(title='Лист'))
    server = build_server(http)
    ok(call(server, 'update_scene', {'story_id': story.id, 'scene_id': scene.id, 'expected_revision': scene.revision,
                                     'plan_markdown': 'План із чату.', 'plan_version_id': None}))
    assert ok(call(server, 'get_story', {'story_id': story.id}))['language_locked'] is False
    ok(call(server, 'update_story', {'story_id': story.id, 'expected_revision': repo.get_story(story.id).revision, 'language': 'en'}))
    assert repo.get_story(story.id).language == 'en'
