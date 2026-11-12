"""MCP-BRIDGE stdio server: twelve tools mapped onto the loopback HTTP API of a running Obscura.

The bridge holds no data, keys or prompts of its own. Every tool is one HTTP request; Obscura's own checks
(revision, context fingerprint, language lock, import limits) decide, and their messages reach the chat as tool errors.
"""
import argparse
import json
import re
from typing import Any
from urllib.parse import urlsplit

import httpx
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError

DEFAULT_URL = 'http://127.0.0.1:8765'
LOOPBACK = {'127.0.0.1', 'localhost', '::1'}
FALLBACK_CLIENT = 'MCP client'
TOOLS = ('list_stories', 'get_story', 'get_scene_context', 'get_scene_text', 'import_plan_and_characters', 'save_draft', 'next_steps',
         'create_story', 'get_templates', 'update_story', 'add_scene', 'update_scene')
MATERIALS = ('plan', 'brief', 'draft', 'prose', 'memory')
LANGUAGES = ('uk', 'en')
# update_scene: null is a real plan_version_id (the scene has no plan version yet), so "not given" needs its own value.
NOT_GIVEN = ''
STORY_STEPS = (('title', 'PATCH', ''), ('language', 'PUT', '/language'), ('content_rating', 'PUT', '/content-rating'))
INSTRUCTIONS = ('Obscura — локальний редактор історій. Прочитайте контекст сцени (get_scene_context) і поточну чернетку '
                '(get_scene_text з material=draft), напишіть чернетку мовою сцени й збережіть її через save_draft з revision і '
                'context_fingerprint з контексту та draft_version_id з прочитаної чернетки. Переписуючи чернетку, беріть саме '
                'прочитаний текст: у ньому можуть бути правки автора. Конфлікт 409 означає, що сцена чи чернетка змінилася: '
                'прочитайте їх знову. Новий твір: create_story → get_templates → import_plan_and_characters (план і персонажі за шаблоном) '
                '→ get_story. План сцени переписуйте лише поверх прочитаного: plan_version_id з get_scene_text(material=plan).')


def check_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme != 'http' or parts.hostname not in LOOPBACK:
        raise SystemExit(f'storygen-mcp працює лише з локальною Obscura (http://127.0.0.1, localhost або [::1]), а не {url}')
    return url


def client_label(name: str | None) -> str:
    cleaned = re.sub(r'[^A-Za-z0-9 ._-]', '', name or '').strip()[:64].strip()
    return cleaned or FALLBACK_CLIENT


def scene_state(scene: dict, impact: str | None) -> str:
    """Port of sceneStatusKey in web/static/workspace-status.js: the same words the scene list shows."""
    heads = scene.get('heads') or {}
    if not heads.get('prose') and not heads.get('draft'):
        return 'no_text' if heads.get('brief') else 'not_started'
    if impact == 'changes_required':
        return 'impact_changes'
    if impact == 'no_impact':
        return 'impact_current'
    if scene.get('needs_review'):
        return 'impact_pending' if impact == 'pending' else 'needs_review'
    return 'prose' if heads.get('prose') else 'draft'


IDENTIFIER = re.compile(r'[A-Za-z0-9_-]{1,64}')


def identifier(value: str) -> str:
    """IDs go into URL paths: only the repository's ID alphabet, so `..`, `/` or `?` cannot reach another endpoint."""
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ToolError(f'Недопустимий ідентифікатор: {str(value)[:80]!r}')
    return value


def _detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:2000]
    if isinstance(body, dict) and 'detail' in body:
        detail = body['detail']
        return detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False)
    return json.dumps(body, ensure_ascii=False)[:4000]


def build_server(http: httpx.Client, client_name: str | None = None) -> MCPServer:
    base = str(http.base_url).rstrip('/')
    server = MCPServer('Obscura', instructions=INSTRUCTIONS)

    def send(method: str, path: str, **kwargs) -> httpx.Response:
        try:
            return http.request(method, path, **kwargs)
        except httpx.TransportError as error:
            raise ToolError(f'Obscura не запущено за адресою {base}: запустіть її і повторіть ({type(error).__name__})') from error

    def request(method: str, path: str, **kwargs):
        response = send(method, path, **kwargs)
        if response.status_code >= 400:
            raise ToolError(f'Obscura відповіла {response.status_code}: {_detail(response)}')
        return response.json()

    def origin_client(ctx: Context | None) -> str:
        if client_name:
            return client_label(client_name)
        try:
            return client_label(ctx.request_context.session.client_params.client_info.name)
        except (AttributeError, ValueError, LookupError):
            return FALLBACK_CLIENT

    @server.tool()
    def list_stories() -> list[dict[str, Any]]:
        """Історії в Obscura (без кошика): id, назва, мова, рейтинг, кількість сцен."""
        return request('GET', '/api/stories')

    @server.tool()
    def get_story(story_id: str) -> dict[str, Any]:
        """Сцени історії по порядку: id, позиція, назва, revision і стан (тими самими словами, що в списку сцен)."""
        data = request('GET', f'/api/stories/{identifier(story_id)}')
        impact = data.get('impact_status') or {}
        story = data['story']
        scenes = [{'id': s['id'], 'position': s['position'], 'title': s['title'], 'revision': s['revision'],
                   'state': scene_state(s, (impact.get(s['id']) or {}).get('prose'))} for s in data['scenes']]
        names = data.get('character_names') or {}
        return {'id': story['id'], 'title': story['title'], 'language': story.get('language'),
                'language_locked': data.get('language_locked'), 'revision': story.get('revision'),
                'content_rating': story.get('content_rating'), 'target_words': story.get('target_words'),
                'characters': [{'id': key, 'name': value} for key, value in names.items()], 'scenes': scenes}

    @server.tool()
    def get_scene_context(scene_id: str) -> dict[str, Any]:
        """Усе потрібне для чернетки сцени: план, бриф, картки персонажів, пам’ять попередніх сцен, рейтинг, мова,
        цільова довжина, revision і context_fingerprint (обидва передайте в save_draft)."""
        return request('GET', f'/api/scenes/{identifier(scene_id)}/writing-context')

    @server.tool()
    def get_scene_text(scene_id: str, material: str, offset: int = 0, max_chars: int = 20000) -> dict[str, Any]:
        """Поточний текст одного матеріалу сцени: plan, brief, draft, prose або memory (таблиця тверджень пам’яті в JSON).
        Нічого не змінює й не коштує грошей. Повертає version_id поточної версії (null, якщо матеріалу немає) — для draft
        передайте його в save_draft як draft_version_id. Довгий текст приходить частинами: читайте далі з next_offset, доки
        він не стане null; якщо content_sha256 частин різний, матеріал змінився — прочитайте його знову з offset=0."""
        if material not in MATERIALS:
            raise ToolError(f'Невідомий матеріал {str(material)[:40]!r}: оберіть один із {", ".join(MATERIALS)}')
        return request('GET', f'/api/scenes/{identifier(scene_id)}/text/{material}', params={'offset': offset, 'max_chars': max_chars})

    @server.tool()
    def import_plan_and_characters(story_id: str, plan_markdown: str | None = None, characters_markdown: str | None = None) -> dict[str, Any]:
        """Імпортувати план і/або персонажів у Markdown — так само, як форма «Імпорт» в Obscura. Повтор не робиться автоматично."""
        files = []
        if plan_markdown and plan_markdown.strip():
            files.append(('plan', ('plan.md', plan_markdown.encode('utf-8'), 'text/markdown')))
        if characters_markdown and characters_markdown.strip():
            files.append(('characters', ('characters.md', characters_markdown.encode('utf-8'), 'text/markdown')))
        if not files:
            raise ToolError('Передайте план або персонажів')
        return request('POST', f'/api/stories/{identifier(story_id)}/sources', files=files)

    @server.tool()
    def save_draft(scene_id: str, text: str, expected_revision: int, context_fingerprint: str, draft_version_id: str | None,
                   content_format: str = 'markdown', model: str | None = None, ctx: Context | None = None) -> dict[str, Any]:
        """Зберегти чернетку сцени як нову поточну версію з позначкою зовнішнього клієнта; попередня лишається в історії.
        Грошей не коштує. expected_revision і context_fingerprint беруться з get_scene_context, draft_version_id — з
        get_scene_text(material='draft') (null, якщо чернетки ще немає). Якщо сцену чи чернетку змінено після читання,
        Obscura відповість 409."""
        if draft_version_id:
            identifier(draft_version_id)
        origin = {'client': origin_client(ctx), 'model': (model or '')[:128] or None}
        body = {'text': text, 'expected_revision': expected_revision, 'content_format': content_format,
                'external_origin': origin, 'expected_context_fingerprint': context_fingerprint,
                'expected_draft_version_id': draft_version_id or None}
        result = request('POST', f'/api/scenes/{identifier(scene_id)}/draft', json=body)
        version, scene = result.get('version') or {}, result.get('scene') or {}
        return {'version_id': version.get('id'), 'revision': scene.get('revision'), 'external_origin': version.get('external_origin')}

    @server.tool()
    def create_story(title: str, language: str = 'uk', target_words: int = 7000, content_rating: dict[str, int] | None = None) -> dict[str, Any]:
        """Створити новий твір в Obscura. Грошей не коштує; видалити твір можна лише в Obscura. language — uk або en
        (мову можна змінити до першого тексту від моделі чи чату); content_rating — {sexual, violence, themes} з рівнями 0–2.
        Якщо рейтинг перевищує межу цього видання Obscura, твір не створюється."""
        body: dict[str, Any] = {'title': title, 'language': language, 'target_words': target_words}
        if content_rating is not None:
            body['content_rating'] = content_rating
        story = request('POST', '/api/stories', json=body)
        return {key: story.get(key) for key in ('id', 'title', 'revision', 'language', 'content_rating', 'target_words')}

    @server.tool()
    def get_templates(language: str) -> dict[str, str]:
        """Шаблони плану й персонажів (uk або en) — ті самі файли, що дає сторінка твору. Нічого не змінює."""
        if language not in LANGUAGES:
            raise ToolError(f'Невідома мова {str(language)[:20]!r}: оберіть uk або en')
        suffix = '' if language == 'uk' else '-en'
        files = {}
        for key, name in (('plan_markdown', 'story-plan'), ('characters_markdown', 'characters')):
            response = send('GET', f'/static/templates/{name}{suffix}.md')
            if response.status_code >= 400:
                raise ToolError(f'Obscura відповіла {response.status_code}: шаблон {name}{suffix}.md недоступний')
            files[key] = response.content.decode('utf-8')
        return {**files, 'hint': 'Заповніть шаблони й передайте їх у import_plan_and_characters: імпорт приймає саме цей формат.'}

    @server.tool()
    def update_story(story_id: str, expected_revision: int, title: str | None = None, language: str | None = None,
                     content_rating: dict[str, int] | None = None) -> dict[str, Any]:
        """Змінити назву, мову й/або рейтинг твору. Грошей не коштує. Зміни виконуються по черзі (назва, мова, рейтинг);
        помилка зупиняє решту й повідомляє applied (застосовано), rejected (відхилено, нічого не змінило), unknown (відповіді
        немає — перечитайте get_story) і not_attempted. Зниження рейтингу робить застарілими тексти вищого рейтингу."""
        values = {'title': title, 'language': language, 'content_rating': content_rating}
        steps = [step for step in STORY_STEPS if values[step[0]] is not None]
        if not steps:
            raise ToolError('Передайте title, language або content_rating')
        path = f'/api/stories/{identifier(story_id)}'
        revision, applied = expected_revision, []
        for index, (field, method, suffix) in enumerate(steps):
            rest = [name for name, *_ in steps[index + 1:]]
            try:
                response = http.request(method, path + suffix, json={field: values[field], 'expected_revision': revision})
            except httpx.TransportError as error:
                raise ToolError('Невідомо, чи застосовано крок: перечитайте твір (get_story) перед повтором. ' + json.dumps(
                    {'applied': applied, 'unknown': field, 'not_attempted': rest, 'error': type(error).__name__}, ensure_ascii=False)) from error
            if response.status_code >= 400:
                raise ToolError('Зміну твору зупинено. ' + json.dumps(
                    {'applied': applied, 'rejected': field, 'not_attempted': rest, 'revision': revision,
                     'error': f'Obscura відповіла {response.status_code}: {_detail(response)}'}, ensure_ascii=False))
            revision = response.json()['revision']
            applied.append(field)
        return {'revision': revision, 'applied': applied}

    @server.tool()
    def add_scene(story_id: str, title: str, plan_markdown: str | None = None, position: int | None = None,
                  target_words: int = 1000, character_ids: list[str] | None = None) -> dict[str, Any]:
        """Додати сцену до твору (position — місце від 0; без нього — у кінець). Грошей не коштує. Без плану Obscura
        підставить план за зразком попередньої сцени. character_ids — id персонажів із get_story."""
        body: dict[str, Any] = {'title': title, 'beats': plan_markdown or '', 'target_words': target_words,
                                'character_ids': [identifier(value) for value in character_ids or []]}
        if position is not None:
            body['position'] = position
        scene = request('POST', f'/api/stories/{identifier(story_id)}/scenes', json=body)
        return {key: scene.get(key) for key in ('id', 'title', 'position', 'revision')}

    @server.tool()
    def update_scene(story_id: str, scene_id: str, expected_revision: int, plan_markdown: str | None = None,
                     plan_version_id: str | None = NOT_GIVEN, title: str | None = None, target_words: int | None = None,
                     character_ids: list[str] | None = None, prose_language: str | None = None) -> dict[str, Any]:
        """Змінити план і/або властивості сцени. Грошей не коштує; попередній план лишається в історії версій. План
        переписуйте поверх прочитаного: plan_version_id з get_scene_text(material='plan') обов’язковий разом із планом
        (null, якщо версії плану ще немає). Якщо план змінено після читання, Obscura відповість 409. prose_language — uk, en
        або story (мова твору)."""
        body: dict[str, Any] = {'story_id': identifier(story_id), 'expected_revision': expected_revision}
        given = plan_version_id != NOT_GIVEN
        if plan_markdown is not None:
            if not given:
                raise ToolError('Разом із планом передайте plan_version_id з get_scene_text(material=plan) (null, якщо версії плану немає)')
            if plan_version_id is not None:
                identifier(plan_version_id)
            body['beats'] = plan_markdown
            body['expected_plan_version_id'] = plan_version_id
        elif given:
            raise ToolError('plan_version_id передається лише разом із plan_markdown')
        for key, value in (('title', title), ('target_words', target_words), ('prose_language', prose_language)):
            if value is not None:
                body[key] = value
        if character_ids is not None:
            body['character_ids'] = [identifier(value) for value in character_ids]
        if len(body) == 2:
            raise ToolError('Передайте план або властивість сцени')
        response = send('PATCH', f'/api/scenes/{identifier(scene_id)}', json=body)
        if response.status_code >= 400:
            try:
                applied = response.json().get('plan_applied') is True
            except ValueError:
                applied = False
            note = ' План записано, властивості — ні: перечитайте сцену (get_scene_text, get_story).' if applied else ''
            raise ToolError(f'Obscura відповіла {response.status_code}: {_detail(response)}{note}')
        scene = response.json()
        result = {'id': scene['id'], 'revision': scene['revision'], 'title': scene['title']}
        if plan_markdown is not None:
            # Only the plan the chat itself wrote: a metadata-only update must not hand out the id of an unread plan.
            result['plan_version_id'] = (scene.get('heads') or {}).get('plan')
        return result

    @server.tool()
    def next_steps(scene_id: str) -> str:
        """Що робити далі в Obscura після збереження чернетки."""
        context = request('GET', f'/api/scenes/{identifier(scene_id)}/writing-context')
        url = f"{base}/stories/{identifier(context['story_id'])}?scene={scene_id}&material=draft"
        return (f'Відкрийте сцену в Obscura: {url}\n'
                '0. Щоб доопрацювати чернетку з чату, спершу прочитайте її (get_scene_text) і пишіть поверх прочитаного.\n'
                '1. Перегляньте чернетку в редакторі; попередня версія лишається в історії версій.\n'
                '2. За потреби доопрацюйте текст у режимі Ghost Mode.\n'
                '3. Коли текст готовий, затвердіть прозу й оновіть пам’ять сцени, щоб наступні сцени її бачили.')

    return server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog='storygen-mcp', description='MCP-сервер (stdio) для локальної Obscura')
    parser.add_argument('--url', default=DEFAULT_URL, help=f'адреса запущеної Obscura (типово {DEFAULT_URL})')
    parser.add_argument('--client-name', default=None, help='назва клієнта для позначки версій (типово з clientInfo)')
    args = parser.parse_args(argv)
    url = check_url(args.url)
    with httpx.Client(base_url=url, timeout=30) as http:
        build_server(http, args.client_name).run('stdio')


if __name__ == '__main__':
    main()
