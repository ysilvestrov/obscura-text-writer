"""MCP-BRIDGE stdio server: six tools mapped onto the loopback HTTP API of a running Obscura.

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
TOOLS = ('list_stories', 'get_story', 'get_scene_context', 'import_plan_and_characters', 'save_draft', 'next_steps')
INSTRUCTIONS = ('Obscura — локальний редактор історій. Прочитайте контекст сцени (get_scene_context), напишіть чернетку '
                'мовою сцени й збережіть її через save_draft з revision і context_fingerprint з того самого контексту. '
                'Конфлікт 409 означає, що сцена змінилася: прочитайте контекст знову.')


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

    def request(method: str, path: str, **kwargs):
        try:
            response = http.request(method, path, **kwargs)
        except httpx.TransportError as error:
            raise ToolError(f'Obscura не запущено за адресою {base}: запустіть її і повторіть ({type(error).__name__})') from error
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
        return {'id': story['id'], 'title': story['title'], 'language': story.get('language'),
                'language_locked': data.get('language_locked'), 'scenes': scenes}

    @server.tool()
    def get_scene_context(scene_id: str) -> dict[str, Any]:
        """Усе потрібне для чернетки сцени: план, бриф, картки персонажів, пам’ять попередніх сцен, рейтинг, мова,
        цільова довжина, revision і context_fingerprint (обидва передайте в save_draft)."""
        return request('GET', f'/api/scenes/{identifier(scene_id)}/writing-context')

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
    def save_draft(scene_id: str, text: str, expected_revision: int, context_fingerprint: str,
                   content_format: str = 'markdown', model: str | None = None, ctx: Context | None = None) -> dict[str, Any]:
        """Зберегти чернетку сцени як нову версію з позначкою зовнішнього клієнта. expected_revision і
        context_fingerprint беруться з get_scene_context; якщо сцена змінилася, Obscura відповість 409."""
        origin = {'client': origin_client(ctx), 'model': (model or '')[:128] or None}
        body = {'text': text, 'expected_revision': expected_revision, 'content_format': content_format,
                'external_origin': origin, 'expected_context_fingerprint': context_fingerprint}
        result = request('POST', f'/api/scenes/{identifier(scene_id)}/draft', json=body)
        version, scene = result.get('version') or {}, result.get('scene') or {}
        return {'version_id': version.get('id'), 'revision': scene.get('revision'), 'external_origin': version.get('external_origin')}

    @server.tool()
    def next_steps(scene_id: str) -> str:
        """Що робити далі в Obscura після збереження чернетки."""
        context = request('GET', f'/api/scenes/{identifier(scene_id)}/writing-context')
        url = f"{base}/stories/{identifier(context['story_id'])}?scene={scene_id}&material=draft"
        return (f'Відкрийте сцену в Obscura: {url}\n'
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
