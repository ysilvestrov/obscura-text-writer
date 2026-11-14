"""BUILD-EDITION-001-S08: an edition without long prose opens a structured book for reading and export only.

One check in the HTTP middleware covers every write route and every GET route that builds a model context. The story is
found from the route's path parameters (story, scene or run) or from `story_id` in the JSON body. Routes that never
change a book, or that the spec lets through, are listed in ALLOWED with the reason; a test walks the route table and
fails on any route that is neither guarded nor listed.
"""
import json

from starlette.routing import Match

from .. import build_edition

ALLOWED = {
    ('POST', '/api/stories'): 'новий твір ще не має структури',
    ('POST', '/api/stories/{id}/trash'): 'специфікація дозволяє прибрати твір у кошик',
    ('POST', '/api/stories/{id}/restore'): 'специфікація дозволяє відновити твір',
    ('POST', '/api/stories/{id}/export'): 'експорт дозволено',
    ('POST', '/api/series'): 'маршрути серії відмовляють у будь-якому виданні без довгої прози власною перевіркою',
    ('PATCH', '/api/series/{series_id}'): 'маршрути серії відмовляють у будь-якому виданні без довгої прози власною перевіркою',
    ('POST', '/api/stories/{story_id}/series/refresh'): 'маршрути серії відмовляють у будь-якому виданні без довгої прози власною перевіркою',
    ('POST', '/api/series/{series_id}/books'): 'маршрути серії відмовляють у будь-якому виданні без довгої прози власною перевіркою',
    ('DELETE', '/api/series/{series_id}'): 'маршрути серії відмовляють у будь-якому виданні без довгої прози власною перевіркою',
    ('PUT', '/api/stories/{story_id}/structure'): 'маршрути структури відмовляють у будь-якій книзі власною перевіркою',
    ('DELETE', '/api/stories/{story_id}/structure'): 'маршрути структури відмовляють у будь-якій книзі власною перевіркою',
    ('PUT', '/api/stories/{story_id}/scenes/{scene_id}/arc'): 'маршрути структури відмовляють у будь-якій книзі власною перевіркою',
    ('PUT', '/api/stories/{story_id}/memory-merges/{merge_key}'): 'злиття пам’яті відмовляє в будь-якій книзі власною перевіркою',
    ('POST', '/api/runs/{id}/pause'): 'зупинка запуску нічого не створює',
    ('POST', '/api/runs/{id}/cancel'): 'скасування запуску нічого не створює',
    ('POST', '/api/runs/cancel-request'): 'скасування запуску нічого не створює',
    ('POST', '/api/providers/discover'): 'налаштування застосунку, не твору',
    ('PUT', '/api/provider-keys/{name}'): 'налаштування застосунку, не твору',
    ('DELETE', '/api/provider-keys/{name}'): 'налаштування застосунку, не твору',
    ('POST', '/api/role-profiles/import'): 'профілі ролей застосунку, не твору',
    ('POST', '/api/publication-signatures'): 'підписи автора спільні для всіх творів',
    ('PATCH', '/api/publication-signatures/{id}'): 'підписи автора спільні для всіх творів',
    ('PUT', '/api/model-policy/consent'): 'згода застосунку, не твору',
    ('DELETE', '/api/model-policy/consent'): 'згода застосунку, не твору',
    ('DELETE', '/api/model-policy/refusal'): 'згода застосунку, не твору',
}
GENERATIVE_GET = {'/api/scenes/{scene_id}/writing-context', '/api/scenes/{scene_id}/chat-task/{stage}'}


def routes(app):
    """Every APIRoute of the application, through included routers."""
    from fastapi.routing import APIRoute
    def walk(items):
        for item in items:
            if isinstance(item, APIRoute):
                yield item
            elif hasattr(item, 'original_router'):
                yield from walk(item.original_router.routes)
    return list(walk(app.routes))


def _route(app, scope):
    for route in routes(app):
        match, child = route.matches(scope)
        if match == Match.FULL:
            return route, child.get('path_params', {})
    return None, {}


def _target(path, params, body):
    """Keyword arguments naming the story: a story, scene or run id from the path, else story_id from the JSON body."""
    if 'story_id' in params:
        return {'story_id': params['story_id']}
    if 'scene_id' in params or path.startswith('/api/scenes/{id}'):
        return {'scene_id': params.get('scene_id') or params.get('id')}
    if path.startswith('/api/stories/{id}'):
        return {'story_id': params.get('id')}
    if path.startswith('/api/runs/{id}'):
        return {'run_id': params.get('id')}
    if isinstance(body, dict):
        nested = body.get('request')
        story_id = body.get('story_id') or (nested.get('story_id') if isinstance(nested, dict) else None)
        return {'story_id': story_id} if isinstance(story_id, str) else {}
    return {}


async def blocked(app, request) -> str | None:
    """The refusal text for a write to a structured book in an edition without long prose; None otherwise."""
    if build_edition.current().long_prose or request.method in {'HEAD', 'OPTIONS'}:
        return None
    route, params = _route(app, request.scope)
    if route is None or (request.method, route.path) in ALLOWED:
        return None
    if request.method == 'GET' and route.path not in GENERATIVE_GET:
        return None
    body = None
    if not params and 'json' in request.headers.get('content-type', ''):
        try:
            body = json.loads(await request.body() or b'null')
        except ValueError:
            body = None
    target = _target(route.path, params, body)
    if not target:
        return None
    from ..book.guard import READ_ONLY
    from ..book.structure import structure_kind
    from ..storage.book_structure import structured_story
    found = structured_story(app.state.repo, **target)
    return READ_ONLY if found and structure_kind(*found) == 'structured' else None
