"""MCP-BRIDGE stdio server: twenty-three tools mapped onto the loopback HTTP API of a running Obscura.

The bridge holds no data, keys or prompts of its own. Every tool is one HTTP request; Obscura's own checks
(revision, context fingerprint, language lock, import limits) decide, and their messages reach the chat as tool errors.
"""
import argparse
import copy
import hashlib
import json
import os
import re
import stat
import uuid
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from ..publication_models import PublicationData

DEFAULT_URL = 'http://127.0.0.1:8765'
LOOPBACK = {'127.0.0.1', 'localhost', '::1'}
FALLBACK_CLIENT = 'MCP client'
TOOLS = ('list_stories', 'get_story', 'get_scene_context', 'get_scene_text', 'import_plan_and_characters', 'save_draft', 'next_steps',
         'create_story', 'get_templates', 'update_story', 'add_scene', 'update_scene', 'open_ghost_mode',
         'get_publication', 'update_publication', 'add_signature', 'upload_cover', 'export_book',
         'get_settings', 'update_settings', 'apply_role_preset', 'get_stage_task', 'save_stage_result', 'start_run', 'get_run')
MATERIALS = ('plan', 'brief', 'draft', 'prose', 'memory')
STAGES = ('brief', 'edit', 'memory')
RUN_ACTIONS = ('brief', 'draft', 'edit', 'memory', 'publication_suggest')
CHAT_WRITES = 'Твір у режимі «пише чат»: напишіть текст самі (get_stage_task, save_draft)'
MEMORY_APPROVAL = 'Попередня пам’ять потребує вашого підтвердження в Obscura: відкрийте сцену й підтвердьте використання пам’яті'
LANGUAGES = ('uk', 'en')
PUBLICATION_FIELDS = tuple(PublicationData.model_fields)
EXPORT_FORMATS = ('fb2', 'epub', 'pdf', 'md', 'txt')
COVER_EXTENSIONS = ('.png', '.jpg', '.jpeg')
COVER_MAX_BYTES = 10 * 1024 * 1024
DRIVE_REMOTE = 4
ROLES = ('planner', 'writer', 'editor', 'memory')
SETTINGS_SECTIONS = ('writing',) + ROLES
WRITING_FIELDS = ('target_words', 'ending_goal', 'genre', 'tone', 'point_of_view', 'tense', 'rules', 'previous_tail_chars')
PROVIDER_FIELDS = ('provider', 'model', 'base_url', 'timeout', 'response_mode', 'include_usage', 'local_disable_thinking',
                   'venice_include_system_prompt', 'venice_disable_thinking', 'venice_reasoning_effort')
ROLE_FIELDS = ('context_tokens', 'max_output_tokens', 'max_input_chars', 'temperature', 'future_plan_mode', 'future_plan_count', 'stop_sequences')
EDITOR_FIELDS = ('edit_mode', 'edit_review')
DEFAULT_KEYS = ('OPENROUTER_API_KEY', 'VENICE_API_KEY')
MODELS_LIMIT = 200
# update_scene: null is a real plan_version_id (the scene has no plan version yet), so "not given" needs its own value.
NOT_GIVEN = ''
# WRITING-MODE: the server limits only requests that carry this header; the bridge sends it on every request.
BRIDGE_HEADERS = {'X-Obscura-Client': 'mcp'}
STORY_STEPS = (('title', 'PATCH', ''), ('language', 'PUT', '/language'), ('content_rating', 'PUT', '/content-rating'))
INSTRUCTIONS = ('Obscura — локальний редактор історій. Прочитайте контекст сцени (get_scene_context) і поточну чернетку '
                '(get_scene_text з material=draft), напишіть чернетку мовою сцени й збережіть її через save_draft з revision і '
                'context_fingerprint з контексту та draft_version_id з прочитаної чернетки. Переписуючи чернетку, беріть саме '
                'прочитаний текст: у ньому можуть бути правки автора. Конфлікт 409 означає, що сцена чи чернетка змінилася: '
                'прочитайте їх знову. Новий твір: create_story → get_templates → import_plan_and_characters (план і персонажі за шаблоном) '
                '→ get_story. План сцени переписуйте лише поверх прочитаного: plan_version_id з get_scene_text(material=plan). '
                'Публікація: get_publication → update_publication (лише змінені поля, revision з прочитаного) → export_book. '
                'Налаштування: get_settings → update_settings (один розділ, fingerprint з прочитаного). '
                'Етапи brief, edit і memory: get_stage_task (інструкції й матеріал, як для моделі Obscura) → відповідь у форматі '
                'result_format → save_stage_result з task_fingerprint; інструкції чернетки — поле instructions у get_scene_context. '
                'Режим твору (writing_mode у get_story): «chat» — тексти пише чат; «obscura» — тексти пишуть моделі Obscura, '
                'і save_draft та етапи з чату відхиляються, а етап чи пропозицію картки запускає start_run (спершу перегляд без confirm, '
                'запуск — лише після згоди автора; стан — get_run). Режим змінює лише автор у налаштуваннях твору.')


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


def _remote_drive(path: str) -> bool:
    if os.name != 'nt':
        return False
    import ctypes
    drive = os.path.splitdrive(path)[0]
    return ctypes.windll.kernel32.GetDriveTypeW(drive + '\\') == DRIVE_REMOTE


def local_cover_path(file_path: str) -> str:
    """MCP-BRIDGE-S29: a cover is read only from a local disk; network and device paths are refused before any file access."""
    raw = file_path if isinstance(file_path, str) else ''
    network = ToolError('Обкладинка має лежати на локальному диску: мережеві шляхи й шляхи пристроїв не приймаються')
    if raw.replace('/', '\\').startswith('\\\\'):
        raise network
    if not os.path.splitext(raw)[1].lower() in COVER_EXTENSIONS:
        raise ToolError('Обкладинка — файл .png, .jpg або .jpeg')
    absolute = re.match(r'[A-Za-z]:[\\/]', raw) if os.name == 'nt' else os.path.isabs(raw)
    if not absolute:
        raise ToolError('Вкажіть повний шлях до файла обкладинки' + (' з літерою диска' if os.name == 'nt' else ''))
    real = os.path.realpath(raw)
    if real.replace('/', '\\').startswith('\\\\') or _remote_drive(real):
        raise network
    try:
        info = os.stat(real)
    except OSError as error:
        raise ToolError(f'Файл обкладинки не знайдено: {raw}') from error
    if not stat.S_ISREG(info.st_mode):
        raise ToolError(f'Обкладинка має бути звичайним файлом: {raw}')
    if info.st_size > COVER_MAX_BYTES:
        raise ToolError('Обкладинка має бути до 10 MiB')
    return real


def _detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:2000]
    if isinstance(body, dict) and 'detail' in body:
        detail = body['detail']
        return detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False)
    return json.dumps(body, ensure_ascii=False)[:4000]


def fingerprint(value) -> str:
    """MCP-BRIDGE-S34: the content of one settings section, the same way for reading and for the check before a write."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()


def role_scope(data: dict, role: str) -> dict:
    return {'settings': (data.get('roles') or {}).get(role), 'prompt': (data.get('prompts') or {}).get(role, ''),
            'prepare': data.get('prepare_prompt') if role == 'planner' else None, 'contract': (data.get('prompt_contracts') or {}).get(role)}


def writing_scope(data: dict) -> dict:
    return {'profile': data.get('profile'), 'target_words': (data.get('story') or {}).get('target_words')}


def section_fingerprint(data: dict, section: str) -> str:
    return fingerprint(writing_scope(data) if section == 'writing' else role_scope(data, section))


def preset_fingerprint(data: dict, evaluator: dict | None) -> str:
    """A preset replaces all four roles and, when it carries one, the evaluator: both are in the check."""
    return fingerprint({'roles': {role: role_scope(data, role) for role in ROLES},
                        'evaluator': {key: value for key, value in evaluator.items() if key != 'block'} if evaluator else None})


def role_fields(role: str) -> tuple[str, ...]:
    return PROVIDER_FIELDS + ROLE_FIELDS + (EDITOR_FIELDS if role == 'editor' else ())


def role_view(settings: dict, role: str) -> dict:
    provider = settings.get('provider') or {}
    return {name: provider.get(name) if name in PROVIDER_FIELDS else settings.get(name) for name in role_fields(role)}


def writing_view(data: dict) -> dict:
    return {'target_words': (data.get('story') or {}).get('target_words'), **{name: (data.get('profile') or {}).get(name) for name in WRITING_FIELDS[1:]}}


def preset_keys(settings: dict) -> list[str]:
    keys = [(settings.get('provider') or {}).get('key_env')]
    classification = settings.get('classification') or {}
    keys.append((classification.get('provider') or {}).get('key_env'))
    return [key for key in keys if key]


def story_series(data: dict) -> dict | None:
    """SERIES: the series of a book in get_story — title, number, start and the snapshot state; None outside a series."""
    series = data.get('series')
    if not series:
        return None
    return {'title': series['title'], 'number': series['number'], 'start': series.get('start'),
            'status': (series.get('status') or {}).get('state')}


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
        """Історії в Obscura (без кошика): id, назва, мова, рейтинг, режим твору (writing_mode: chat чи obscura), кількість сцен."""
        return request('GET', '/api/stories')

    @server.tool()
    def get_story(story_id: str) -> dict[str, Any]:
        """Сцени історії по порядку: id, позиція, назва, revision і стан (тими самими словами, що в списку сцен)."""
        data = request('GET', f'/api/stories/{identifier(story_id)}')
        impact = data.get('impact_status') or {}
        story = data['story']
        # BOOK-STRUCTURE: part and arc of each scene (one implicit part and arc for a flat book).
        arcs = {a['id']: (p, a) for p in (data.get('book_structure') or {}).get('parts', []) for a in p['arcs']}
        none = ({'id': None, 'title': ''}, {'id': None, 'title': ''})

        def place(scene):
            part, arc = arcs.get(scene.get('arc_id'), none)
            return {'part_id': part['id'], 'part_title': part['title'], 'arc_id': arc['id'], 'arc_title': arc['title'],
                    'arc_ids': scene.get('arc_ids') or ([arc['id']] if arc['id'] else [])}
        scenes = [{'id': s['id'], 'position': s['position'], 'title': s['title'], 'revision': s['revision'],
                   'state': scene_state(s, (impact.get(s['id']) or {}).get('prose')), **place(s)} for s in data['scenes']]
        names = data.get('character_names') or {}
        return {'id': story['id'], 'title': story['title'], 'language': story.get('language'),
                'language_locked': data.get('language_locked'), 'revision': story.get('revision'),
                'content_rating': story.get('content_rating'), 'target_words': story.get('target_words'),
                'writing_mode': story.get('writing_mode', 'chat'), 'series': story_series(data),
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
        """Імпортувати план і/або персонажів у Markdown — так само, як форма «Імпорт» в Obscura. Повтор не робиться автоматично.
        proposed_scenes[].character_ids — склад, збережений у створених сценах (також із карток цього самого виклику)."""
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
    def create_story(title: str, language: str = 'uk', target_words: int = 7000, content_rating: dict[str, int] | None = None,
                     writing_mode: Literal['chat', 'obscura'] = 'chat') -> dict[str, Any]:
        """Створити новий твір в Obscura. Грошей не коштує; видалити твір можна лише в Obscura. language — uk або en
        (мову можна змінити до першого тексту від моделі чи чату); content_rating — {sexual, violence, themes} з рівнями 0–2.
        Якщо рейтинг перевищує межу цього видання Obscura, твір не створюється. writing_mode — хто пише тексти: chat (типово,
        чат) або obscura (моделі Obscura; тоді чат не зберігає чернеток і етапів)."""
        body: dict[str, Any] = {'title': title, 'language': language, 'target_words': target_words, 'writing_mode': writing_mode}
        if content_rating is not None:
            body['content_rating'] = content_rating
        story = request('POST', '/api/stories', json=body)
        return {key: story.get(key) for key in ('id', 'title', 'revision', 'language', 'content_rating', 'target_words', 'writing_mode')}

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
    def open_ghost_mode(story_id: str, scene_id: str, draft_version_id: str | None = None) -> dict[str, Any]:
        """Посилання, що відкриває в Obscura переписування по пам’яті (Ghost Mode) поточної чернетки сцени. Нічого не
        змінює й не коштує грошей; браузер відкриває автор кліком. draft_version_id (з get_scene_text чи save_draft)
        перевіряється: якщо чернетку вже змінено, посилання не видається, а сторінка й сама не відкриє режим."""
        identifier(story_id), identifier(scene_id)
        if draft_version_id:
            identifier(draft_version_id)
        data = request('GET', f'/api/stories/{story_id}')
        scene = next((item for item in data.get('scenes') or [] if item.get('id') == scene_id), None)
        if scene is None:
            raise ToolError('Сцени немає в цьому творі: перевірте story_id і scene_id (get_story)')
        head = (scene.get('heads') or {}).get('draft')
        if not head:
            raise ToolError('У сцени немає чернетки: спершу збережіть її (save_draft)')
        if draft_version_id and draft_version_id != head:
            raise ToolError('Чернетку змінено після того, як її прочитали — прочитайте її знову (get_scene_text)')
        suffix = f'&draft={draft_version_id}' if draft_version_id else ''
        return {'url': f'{base}/stories/{story_id}?scene={scene_id}&material=draft&ghost=1{suffix}', 'draft_version_id': head}

    def publication_view(card_response: dict, signatures: list[dict]) -> dict[str, Any]:
        card = {name: card_response['card'].get(name) for name in PUBLICATION_FIELDS}
        card['revision'] = card_response['card']['revision']
        cover = card_response.get('cover')
        return {'card': card, 'revision': card['revision'], 'effective_title': card_response.get('effective_title'),
                'cover': {key: cover.get(key) for key in ('id', 'width', 'height', 'mime_type')} if cover else None,
                'signatures': [{'id': item['id'], 'display_name': item['display_name'], 'revision': item['revision'],
                                'archived': bool(item.get('archived_at'))} for item in signatures]}

    def read_publication(story_id: str) -> tuple[dict, list[dict]]:
        card = request('GET', f'/api/stories/{story_id}/publication')
        signatures = request('GET', '/api/publication-signatures', params={'include_archived': 'true'})['signatures']
        return card, signatures

    @server.tool()
    def get_publication(story_id: str, genres_language: str | None = None) -> dict[str, Any]:
        """Картка публікації твору (назва, автори, жанри, анотація, обкладинка…) з її revision і довідник підписів
        (авторів і перекладачів). genres_language (uk чи en) додає каталог жанрів FB2: коди однакові для обох мов."""
        identifier(story_id)
        if genres_language is not None and genres_language not in LANGUAGES:
            raise ToolError(f'genres_language: одне з {", ".join(LANGUAGES)}')
        result = publication_view(*read_publication(story_id))
        if genres_language:
            result['genres'] = request('GET', '/api/publication/genres', params={'language': genres_language})['genres']
        return result

    @server.tool()
    def update_publication(story_id: str, expected_revision: int, fields: dict[str, Any]) -> dict[str, Any]:
        """Змінює лише передані поля картки публікації поверх прочитаної (revision з get_publication); інші поля лишаються.
        Поля: title, author_ids, language, genres, annotation, keywords, cover_id, cycle_title, cycle_number,
        publication_date, publisher, isbn, rights, translator_ids, source_language. author_ids/translator_ids — id з
        довідника підписів (add_signature), cover_id — з upload_cover, genres — коди з get_publication(genres_language)."""
        identifier(story_id)
        unknown = sorted(set(fields) - set(PUBLICATION_FIELDS))
        if not fields or unknown:
            raise ToolError(f'Невідомі поля картки: {", ".join(unknown)}' if unknown else 'Передайте хоча б одне поле картки (fields)')
        for name in ('author_ids', 'translator_ids'):
            if name in fields:
                if not isinstance(fields[name], list):
                    raise ToolError(f'{name}: список id підписів')
                for value in fields[name]:
                    identifier(value)
        if fields.get('cover_id') is not None:
            identifier(fields['cover_id'])
        current, signatures = read_publication(story_id)
        if current['card']['revision'] != expected_revision:
            raise ToolError(f'Obscura відповіла 409: картку публікації змінено (revision {current["card"]["revision"]}, а не '
                            f'{expected_revision}) — прочитайте її знову (get_publication)')
        data = {name: current['card'].get(name) for name in PUBLICATION_FIELDS} | fields
        revisions = {item['id']: item['revision'] for item in signatures}
        people = list(dict.fromkeys([*(data.get('author_ids') or []), *(data.get('translator_ids') or [])]))
        missing = [person for person in people if person not in revisions]
        if missing:
            raise ToolError(f'Немає підписів {", ".join(missing)}: додайте їх (add_signature) або візьміть id з get_publication')
        response = send('PUT', f'/api/stories/{story_id}/publication', json={
            'expected_revision': expected_revision, 'data': data,
            'expected_signature_revisions': {person: revisions[person] for person in people}})
        if response.status_code == 422:
            # The server names no field: point the chat at the vocabularies it can read.
            raise ToolError(f'Obscura відповіла 422: {_detail(response)}. Перевірте значення полів: коди жанрів — з '
                            'get_publication(genres_language), мова — код на кшталт uk чи en, дата — РРРР-ММ-ДД, ключові слова й '
                            'списки без повторів і порожніх значень')
        if response.status_code >= 400:
            raise ToolError(f'Obscura відповіла {response.status_code}: {_detail(response)}')
        return publication_view(response.json(), signatures)

    @server.tool()
    def add_signature(display_name: str) -> dict[str, Any]:
        """Додає підпис (ім'я автора чи перекладача) до спільного довідника; його id ставлять в author_ids/translator_ids."""
        data = request('POST', '/api/publication-signatures', json={'display_name': display_name})
        return {'id': data['id'], 'display_name': data['display_name'], 'revision': data['revision']}

    @server.tool()
    def upload_cover(story_id: str, file_path: str) -> dict[str, Any]:
        """Завантажує обкладинку з локального файла (абсолютний шлях, PNG чи JPEG до 10 MiB). Картку не змінює: щоб
        поставити обкладинку, передайте cover_id в update_publication."""
        identifier(story_id)
        path = local_cover_path(file_path)
        with open(path, 'rb') as handle:
            content = handle.read(COVER_MAX_BYTES + 1)
        if len(content) > COVER_MAX_BYTES:
            raise ToolError('Обкладинка має бути до 10 MiB')
        mime = 'image/png' if path.lower().endswith('.png') else 'image/jpeg'
        data = request('POST', f'/api/stories/{story_id}/publication/cover', files={'file': (os.path.basename(path), content, mime)})
        return {'cover_id': data['id'], 'width': data['width'], 'height': data['height'], 'mime_type': data['mime_type']}

    @server.tool()
    def export_book(story_id: str, format: str, allow_incomplete: bool = False) -> dict[str, Any]:
        """Експортує книгу (fb2, epub, pdf, md чи txt) з картки публікації й затвердженої прози; повертає посилання на файл.
        Незавершений твір (сцени без прози) експортується лише з allow_incomplete=true. FB2 потребує автора й жанру в картці."""
        identifier(story_id)
        if format not in EXPORT_FORMATS:
            raise ToolError(f'format: одне з {", ".join(EXPORT_FORMATS)}')
        links = request('POST', f'/api/stories/{story_id}/export', json={'format': format, 'allow_incomplete': allow_incomplete})
        manifest = request('GET', links['manifest_url'])
        return {'download_url': f'{base}{links["download_url"]}', 'format': manifest['format'], 'complete': manifest['complete'],
                'warnings': manifest['warnings'], 'word_count': manifest['word_count'], 'age_rating': manifest['age_rating']}

    def read_settings(story_id: str) -> dict:
        return request('GET', f'/api/stories/{story_id}/settings')

    def read_evaluator(story_id: str) -> dict | None:
        response = send('GET', f'/api/stories/{story_id}/evaluator')
        if response.status_code == 400:
            return None  # "Оцінювач не налаштовано"
        if response.status_code >= 400:
            raise ToolError(f'Obscura відповіла {response.status_code}: {_detail(response)}')
        return response.json()

    def key_state(name: str | None) -> dict | None:
        if not name:
            return None
        state = request('GET', f'/api/provider-keys/{identifier(name)}')
        return {'name': state['name'], 'source': state['source']}

    def settings_view(data: dict, section: str) -> dict:
        if section == 'writing':
            return {'settings': writing_view(data), 'fingerprint': section_fingerprint(data, 'writing')}
        settings = (data.get('roles') or {}).get(section)
        return {'configured': settings is not None, 'settings': role_view(settings, section) if settings else None,
                'fingerprint': section_fingerprint(data, section)}

    def changed_fields(before: dict | None, after: dict | None) -> dict[str, list]:
        before, after = before or {}, after or {}
        return {name: [before.get(name), after.get(name)] for name in after if before.get(name) != after.get(name)}

    @server.tool()
    def get_settings(story_id: str, include_prompts: bool = False, models_for_role: str | None = None,
                     models_query: str | None = None) -> dict[str, Any]:
        """Налаштування твору: профіль письма й обсяг (writing), чотири ролі (planner, writer, editor, memory) з
        fingerprint кожного розділу для update_settings, стан ключа провайдера (без значення), пресети ролей і
        preset_fingerprint для apply_role_preset. include_prompts додає тексти промптів; models_for_role — список моделей
        провайдера цієї ролі (models_query фільтрує за підрядком). Нічого не змінює й моделі не викликає."""
        identifier(story_id)
        if models_for_role is not None and models_for_role not in ROLES:
            raise ToolError(f'models_for_role: одна з {", ".join(ROLES)}')
        data = read_settings(story_id)
        roles = {}
        for role in ROLES:
            settings = (data.get('roles') or {}).get(role)
            entry = {'configured': settings is not None, 'fingerprint': section_fingerprint(data, role)}
            if settings:
                provider = settings.get('provider') or {}
                entry |= role_view(settings, role)
                entry['key'] = None if provider.get('provider') == 'local' else key_state(provider.get('key_env'))
                entry['custom_prompt'] = bool(settings.get('prompt_version_id'))
            roles[role] = entry
        result = {'writing': {**writing_view(data), 'fingerprint': section_fingerprint(data, 'writing')}, 'roles': roles,
                  'preset_fingerprint': preset_fingerprint(data, read_evaluator(story_id)),
                  'presets': request('GET', '/api/role-profiles')['profiles']}
        if include_prompts:
            result['prompts'] = {role: text for role, text in (data.get('prompts') or {}).items() if role in ROLES}
            if (data.get('roles') or {}).get('planner'):
                result['prepare_prompt'] = data.get('prepare_prompt')
        if models_for_role:
            settings = (data.get('roles') or {}).get(models_for_role)
            if not settings:
                raise ToolError(f'Роль {models_for_role} ще не налаштовано: спершу задайте провайдера й модель (update_settings)')
            models = request('POST', '/api/providers/discover', json=settings['provider'])['models']
            if models_query:
                models = [item for item in models if models_query.lower() in str(item.get('id', '')).lower()]
            models.sort(key=lambda item: str(item.get('id', '')))
            result['models'] = [{key: item.get(key) for key in ('id', 'context_tokens', 'max_output_tokens', 'tariff', 'uncensored')}
                                for item in models[:MODELS_LIMIT]]
            result['models_total'] = len(models)
        return result

    @server.tool()
    def update_settings(story_id: str, section: str, expected_fingerprint: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Змінює лише передані поля одного розділу налаштувань поверх прочитаного (fingerprint розділу з get_settings).
        section: writing (target_words, ending_goal, genre, tone, point_of_view, tense, rules, previous_tail_chars) або
        роль planner/writer/editor/memory (provider, model, base_url лише для local, timeout, response_mode, include_usage,
        local_disable_thinking, venice_include_system_prompt, venice_disable_thinking, venice_reasoning_effort,
        context_tokens, max_output_tokens, max_input_chars, temperature, future_plan_mode, future_plan_count,
        stop_sequences; для editor ще edit_mode, edit_review). Нова роль потребує provider і model. Назву ключа, промпти,
        оцінювача й бюджет змінює лише автор. Моделі не викликає, але від моделі залежить вартість наступних запусків."""
        identifier(story_id)
        if section not in SETTINGS_SECTIONS:
            raise ToolError(f'section: одне з {", ".join(SETTINGS_SECTIONS)}')
        if not isinstance(fields, dict) or not fields:
            raise ToolError('Передайте хоча б одне поле розділу (fields)')
        if 'key_env' in fields:
            raise ToolError('Назву змінної ключа змінює лише автор на сторінці налаштувань')
        allowed = WRITING_FIELDS if section == 'writing' else role_fields(section)
        unknown = sorted(set(fields) - set(allowed))
        if unknown:
            raise ToolError(f'Поля поза розділом {section}: {", ".join(unknown)}. Допустимі: {", ".join(allowed)}')
        data = read_settings(story_id)
        if section_fingerprint(data, section) != expected_fingerprint:
            raise ToolError(f'Obscura відповіла 409: розділ {section} змінено після того, як його прочитали — прочитайте його знову (get_settings)')
        before = settings_view(data, section)['settings']
        revision = data['story']['revision']
        if section == 'writing':
            body = {'expected_revision': revision,
                    'profile': (data.get('profile') or {}) | {name: value for name, value in fields.items() if name != 'target_words'}}
            if 'target_words' in fields:
                body['target_words'] = fields['target_words']
        else:
            current = (data.get('roles') or {}).get(section)
            if current is None and not {'provider', 'model'} <= set(fields):
                raise ToolError(f'Роль {section} ще не налаштовано: передайте provider і model')
            settings = copy.deepcopy(current) if current else {'provider': {}}
            provider = settings.setdefault('provider', {})
            previous = provider.get('provider')
            for name, value in fields.items():
                (provider if name in PROVIDER_FIELDS else settings)[name] = value
            if provider.get('provider') != previous:
                # The new provider's own key and address: the stored ones belong to the old provider (SECURITY-002).
                provider.pop('key_env', None)
                if 'base_url' not in fields:
                    provider.pop('base_url', None)
            if 'base_url' in fields and provider.get('provider') != 'local':
                raise ToolError('base_url задається лише для локального провайдера; хмарні мають офіційну адресу')
            body = {'expected_revision': revision, 'role': section, 'settings': settings}
        response = send('PUT', f'/api/stories/{story_id}/settings', json=body)
        if response.status_code == 422:
            raise ToolError(f'Obscura відповіла 422: {_detail(response)}. Перевірте значення полів: числа в межах форми '
                            '(max_output_tokens менше за context_tokens, temperature 0–2), provider — local, openrouter чи venice')
        if response.status_code >= 400:
            raise ToolError(f'Obscura відповіла {response.status_code}: {_detail(response)}')
        after = settings_view(read_settings(story_id), section)
        return {'section': section, **after, 'changed': changed_fields(before, after['settings'])}

    @server.tool()
    def apply_role_preset(story_id: str, profile_id: str, version: int, expected_fingerprint: str, confirm: bool = False) -> dict[str, Any]:
        """Застосовує збережений пресет ролей (id і version з get_settings.presets). Без confirm лише показує, що
        зміниться; confirm=true застосовує всі чотири ролі й, якщо пресет його містить, оцінювача — як кнопка на сторінці.
        expected_fingerprint — preset_fingerprint з get_settings. Моделі не викликає."""
        identifier(story_id), identifier(profile_id)
        if not isinstance(version, int) or version < 1:
            raise ToolError('version: ціле число від 1')
        data = read_settings(story_id)
        if preset_fingerprint(data, read_evaluator(story_id)) != expected_fingerprint:
            raise ToolError('Obscura відповіла 409: ролі чи оцінювача змінено після того, як їх прочитали — прочитайте знову (get_settings)')
        preview = request('POST', f'/api/stories/{story_id}/role-profiles/preview',
                          json={'profile_id': profile_id, 'version': version, 'expected_revision': data['story']['revision']})
        current = data.get('roles') or {}
        allowed_keys = set(DEFAULT_KEYS) | {key for settings in current.values() if settings for key in preset_keys(settings)}
        roles, foreign = {}, []
        for role, settings in (preview.get('roles') or {}).items():
            keys = preset_keys(settings)
            foreign += [key for key in keys if key not in allowed_keys]
            roles[role] = {'changed': changed_fields(role_view(current[role], role) if current.get(role) else None, role_view(settings, role)),
                           'keys': keys}
        result = {'profile_id': profile_id, 'version': version, 'name': preview.get('name'), 'roles': roles,
                  'evaluator': preview.get('evaluator') is not None, 'applied': False}
        if not confirm:
            return result
        if foreign:
            raise ToolError(f'Пресет ставить назву ключа, якої немає серед ролей твору: {", ".join(sorted(set(foreign)))}. '
                            'Такий пресет застосовує автор на сторінці налаштувань')
        request('POST', f'/api/stories/{story_id}/role-profiles/apply',
                json={'profile_id': profile_id, 'version': version, 'expected_revision': preview['expected_revision']})
        return result | {'applied': True}

    def known_stage(stage: str) -> str:
        if stage not in STAGES:
            raise ToolError(f'Невідомий етап {str(stage)[:40]!r}: оберіть один із {", ".join(STAGES)}')
        return stage

    @server.tool()
    def get_stage_task(scene_id: str, stage: str, offset: int = 0, max_chars: int = 20000) -> dict[str, Any]:
        """Завдання етапу сцени — brief, edit або memory — таким, яким його отримала б модель Obscura: instructions (системний
        текст ролі) і material (матеріал). Нічого не змінює й не коштує грошей. Довгий матеріал приходить частинами: читайте далі з
        next_offset, доки він не стане null; content_sha256 однаковий для всіх частин одного завдання. Відповідайте у форматі
        result_format (json; для edit — prose, patches або diff) і передайте task_fingerprint у save_stage_result."""
        return request('GET', f'/api/scenes/{identifier(scene_id)}/chat-task/{known_stage(stage)}',
                       params={'offset': offset, 'max_chars': max_chars})

    @server.tool()
    def save_stage_result(scene_id: str, stage: str, task_fingerprint: str, result: str | dict[str, Any], model: str | None = None,
                          ctx: Context | None = None) -> dict[str, Any]:
        """Зберегти відповідь чату на завдання етапу (get_stage_task). Obscura розбирає її так само, як відповідь своєї моделі, і
        зберігає новою версією з позначкою зовнішнього клієнта; грошей не коштує. result — JSON-об'єкт або рядок (для edit — у
        форматі result_format). Неправильну відповідь Obscura не зберігає й повертає всі порушення разом: виправте їх і збережіть
        знову з тим самим task_fingerprint. Після трьох відмов поспіль зупиніться й покажіть порушення авторові. 409 — завдання
        застаріло або потрібне підтвердження автора: візьміть завдання знову. state=needs_review — результат чекає рішення автора."""
        known_stage(stage)
        text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        body = {'task_fingerprint': task_fingerprint, 'text': text,
                'external_origin': {'client': origin_client(ctx), 'model': (model or '')[:128] or None}}
        response = send('POST', f'/api/scenes/{identifier(scene_id)}/chat-result/{stage}', json=body)
        if response.status_code == 422:
            try:
                details = response.json()
            except ValueError:
                details = {}
            if isinstance(details, dict) and isinstance(details.get('detail'), str):
                listed = {key: details[key] for key in ('memory_violations', 'editor_failure', 'planner_failure', 'warnings') if details.get(key)}
                raise ToolError(f"Obscura відповіла 422: {details['detail']}\n{json.dumps(listed, ensure_ascii=False)}")
        if response.status_code >= 400:
            raise ToolError(f'Obscura відповіла {response.status_code}: {_detail(response)}')
        return response.json()

    def usd(nanos: Any) -> str | None:
        return None if nanos is None else f'{int(nanos) / 1_000_000_000:.4f}'

    @server.tool()
    def start_run(story_id: str, action: str, scene_id: str | None = None, confirm: bool = False,
                  budget_limit_usd: str | None = None) -> dict[str, Any]:
        """Запустити моделлю Obscura один етап сцени (brief, draft, edit, memory) або пропозицію картки публікації
        (publication_suggest, без scene_id). Лише у творі з режимом «пише Obscura». КОШТУЄ ГРОШЕЙ за тарифами моделей ролей.
        Без confirm нічого не запускає й повертає перегляд: готовність, моделі, кількість викликів, попередження й бюджет твору.
        Покажіть перегляд авторові й дочекайтеся його згоди в чаті; лише тоді викличте з confirm=true. budget_limit_usd — ліміт
        цього запуску в доларах (рядок, напр. "0.50"). Запуск іде у фоні: стан і результат — get_run(run_id); результат
        етапу читайте get_scene_text, пропозиції картки — у get_run. Кожен виклик з confirm=true створює новий запуск."""
        if action not in RUN_ACTIONS:
            raise ToolError('Невідома дія; можливі: ' + ', '.join(RUN_ACTIONS))
        story = identifier(story_id)
        if action == 'publication_suggest':
            if scene_id is not None:
                raise ToolError('publication_suggest стосується твору: не передавайте scene_id')
        elif scene_id is None:
            raise ToolError('Для етапу сцени потрібен scene_id')
        scene = identifier(scene_id) if scene_id is not None else None
        if request('GET', f'/api/stories/{story}')['story'].get('writing_mode', 'chat') != 'obscura':
            raise ToolError(CHAT_WRITES)
        if action == 'publication_suggest':
            ready = request('GET', f'/api/stories/{story}/publication/suggestions/readiness')
        else:
            ready = request('GET', f'/api/stories/{story}/readiness',
                            params={'scene_id': scene, 'operation': action})['operations'][action]
        budget = request('GET', f'/api/stories/{story}/budget')
        policy = budget.get('policy') or {}
        preview = {'ready': ready.get('ready'), 'reason': ready.get('reason'), 'roles': ready.get('roles') or {},
                   'calls': ready.get('calls'), 'warnings': ready.get('warnings') or [],
                   'budget': {'limit_usd': usd(budget.get('limit_nanos')), 'spent_usd': usd(budget.get('exposure_nanos')),
                              'available_usd': usd(budget.get('available_nanos')),
                              'default_run_limit_usd': usd(policy.get('default_run_limit_nanos'))}}
        if not confirm:
            return {'started': False, 'preview': preview,
                    'message': 'Покажіть перегляд авторові; запуск — лише після його згоди, викликом з confirm=true'}
        if not ready.get('ready'):
            raise ToolError(MEMORY_APPROVAL if ready.get('can_confirm') else f"Запуск не готовий: {ready.get('reason')}")
        if action == 'publication_suggest':
            body: dict[str, Any] = {'story_id': story, 'mode': 'publication_suggest'}
        else:
            body = {'story_id': story, 'scene_id': scene, 'mode': 'stage', 'stage': action}
        if budget_limit_usd is not None:
            body['budget_limit_usd'] = budget_limit_usd
        run = request('POST', '/api/runs', json={'request_id': 'mcp-' + uuid.uuid4().hex, 'request': body})
        return {'started': True, 'run_id': run['id'], 'state': run['state'], 'preview': preview}

    @server.tool()
    def get_run(run_id: str, cancel: bool = False) -> dict[str, Any]:
        """Стан запуску Obscura: state (queued, running, completed, failed, cancelled…), помилка, спроби (state, error,
        result_version_id), для publication_suggest — актуальні пропозиції картки. Грошей не коштує. Довгий запуск не чекайте в
        одному виклику: перевіряйте стан повторно. cancel=true спершу скасовує запуск — лише той, що почав чат."""
        run_path = f'/api/runs/{identifier(run_id)}'
        if cancel:
            request('POST', f'{run_path}/cancel', json={})
        data = request('GET', run_path)
        run = data['run']
        mode = run['request'].get('mode')
        result: dict[str, Any] = {
            'run_id': run['id'], 'story_id': run['story_id'], 'state': run['state'], 'error': run.get('error'),
            'warning': run.get('warning'), 'action': run['request'].get('stage') if mode == 'stage' else mode,
            'scene_id': run['request'].get('scene_id'), 'origin': run.get('origin'),
            'attempts': [{'stage': a.get('stage'), 'state': a.get('state'), 'error': a.get('error'),
                          'result_version_id': a.get('result_version_id')} for a in data.get('attempts') or []]}
        if mode == 'publication_suggest':
            suggestions = request('GET', f"/api/stories/{identifier(run['story_id'])}/publication/suggestions")
            result['suggestions'] = {'proposals': suggestions.get('proposals') or [], 'history': suggestions.get('history') or []}
        return result

    @server.tool()
    def next_steps(scene_id: str) -> str:
        """Що робити далі в Obscura після збереження чернетки."""
        context = request('GET', f'/api/scenes/{identifier(scene_id)}/writing-context')
        story_id = identifier(context['story_id'])
        url = f"{base}/stories/{story_id}?scene={scene_id}&material=draft"
        obscura_writes = request('GET', f'/api/stories/{story_id}')['story'].get('writing_mode') == 'obscura'
        stages = ("4. Твір у режимі «пише Obscura»: етапи запускає start_run(action='brief'|'draft'|'edit'|'memory') — спершу "
                  "перегляд без confirm, запуск лише після згоди автора (коштує грошей); стан і результат — get_run.") if obscura_writes else (
                  "4. Етапи можна пройти й з чату: get_stage_task(stage='brief') — завдання, get_stage_task(stage='edit') — редактура "
                  "чернетки, get_stage_task(stage='memory') — пам’ять затвердженої прози; відповідь зберігає save_stage_result.")
        return (f'Відкрийте сцену в Obscura: {url}\n'
                '0. Щоб доопрацювати чернетку з чату, спершу прочитайте її (get_scene_text) і пишіть поверх прочитаного.\n'
                '1. Перегляньте чернетку в редакторі; попередня версія лишається в історії версій.\n'
                '2. За потреби доопрацюйте текст у режимі Ghost Mode: open_ghost_mode дасть посилання, що відкриє його одразу.\n'
                '3. Коли текст готовий, затвердіть прозу й оновіть пам’ять сцени, щоб наступні сцени її бачили.\n' + stages)

    return server


def build_client(url: str) -> httpx.Client:
    return httpx.Client(base_url=url, timeout=30, headers=BRIDGE_HEADERS)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog='storygen-mcp', description='MCP-сервер (stdio) для локальної Obscura')
    parser.add_argument('--url', default=DEFAULT_URL, help=f'адреса запущеної Obscura (типово {DEFAULT_URL})')
    parser.add_argument('--client-name', default=None, help='назва клієнта для позначки версій (типово з clientInfo)')
    args = parser.parse_args(argv)
    url = check_url(args.url)
    with build_client(url) as http:
        build_server(http, args.client_name).run('stdio')


if __name__ == '__main__':
    main()
