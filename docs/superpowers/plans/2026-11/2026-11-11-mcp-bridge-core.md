# MCP-міст: ядро (#84, R-32, PR 1) — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** `storygen-mcp`: stdio-клієнт до запущеного сервера Obscura із шістьма інструментами. Чернетку з чату позначено `external_origin` і прив’язано до прочитаного контексту.

**Architecture:** Сервер отримує поле версії `external_origin`, відбиток контексту письма й два GET-ендпоінти. Пакет `storygen.mcp` (SDK `mcp` 2.x, `MCPServer`) перекладає виклики інструментів у HTTP-запити до `127.0.0.1` через `httpx.Client`. До сховища клієнт не звертається.

**Tech Stack:** FastAPI, pydantic, `mcp==2.3.0` (extra `[mcp]`), httpx.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-10-mcp-server-design.md` (PR 1).

## Global Constraints

- Інструменти рівно: `list_stories`, `get_story`, `get_scene_context`, `import_plan_and_characters`, `save_draft`, `next_steps`. Немає видалення, публікації, запуску, налаштувань і ключів.
- `--url` типово `http://127.0.0.1:8765`; хост поза {127.0.0.1, localhost, ::1} → вихід із помилкою на старті. HTTP без заголовка `Origin`, таймаут 30 с.
- Недоступний сервер → помилка інструмента «Obscura не запущено за адресою <url>». Відповіді 4xx повертаються як помилка інструмента з текстом сервера. Автоматичних повторів немає.
- `ExternalOrigin(client: 1..64 символи [A-Za-z0-9 ._-], model: str|None ≤128)`; старі версії без поля → `None`.
- 409 «Контекст сцени змінився — прочитайте його знову»; для `external_origin` відбиток обов’язковий (400). Чернетка з `external_origin` завжди створює нову версію.
- Фіксація мови: `source_run_id IS NOT NULL OR external_origin IS NOT NULL`.

## Review Focus

1. Відбиток має змінюватися від усього, що повертає `writing-context`: картки, план, бриф, пам’ять попередніх сцен, прапорці передавання, склад сцени.
2. `writing-context` для сцени B без власної пам’яті показує ту саму проєкцію пам’яті, що контекст етапу `draft` (S09).
3. Клієнт ніколи не відкриває каталог даних і не надсилає `Origin`; не-loopback URL зупиняє старт.
4. 409/400 сервера доходять до чат-клієнта текстом, а не загальним «Error executing tool».
5. Імпорт через MCP не повторюється автоматично (безномерні сцени додалися б удруге).

---

### Task 1: Походження й відбиток чернетки

**Files:** Modify `src/storygen/domain.py` (`ExternalOrigin`, поле `VersionRef.external_origin`); `src/storygen/storage/repository.py` (`save_version(..., external_origin=None)`); `src/storygen/generation/dependencies.py` (`writing_fingerprint(repo, scene) -> str`; `save_manual_draft(..., external_origin=None, expected_context_fingerprint=None)`); `src/storygen/web/routes_versions.py` (`DraftChange.external_origin`, `expected_context_fingerprint`); `src/storygen/storage/authoring.py` (`model_material_exists`). Test `tests/web/test_external_draft.py`.

- `writing_fingerprint` = SHA-256 канонічного JSON `{snapshot: _manual_snapshot(repo,scene,'draft').model_dump(mode='json'), brief: scene.heads.get('brief')}`.
- Тести: S03 застаріла ревізія → 409, чернетка не змінена; S04 нова поточна версія з `external_origin`, попередня в історії, однаковий текст однаково дає нову версію; S08 картки змінено після читання → 409; без відбитка з `external_origin` → 400; мову твору зафіксовано після такої чернетки.

### Task 2: Ендпоінти читання

**Files:** Modify `src/storygen/generation/context.py` (виділити `memory_projection(repo, story, scene, scenes, language)` з `build_context` без зміни поведінки); Create `src/storygen/application/writing_context.py` (`writing_context(repo, scene_id) -> dict`); Modify `src/storygen/web/routes_stories.py` (`GET /api/stories`), `src/storygen/web/routes_versions.py` (`GET /api/scenes/{id}/writing-context`). Test `tests/web/test_writing_context.py`.

- `GET /api/stories` → `[{id,title,language,rating,scene_count}]`, без кошика.
- `writing-context` → `{story_id, scene_id, title, position, plan, brief, characters, memory, rating, language, target_words, revision, context_fingerprint}`; `characters` — `character_material`, `memory` — текст проєкції, обидва ті самі, що в контексті `draft`.
- Тести: S09 (сцена B без пам’яті → проєкція A дорівнює секції пам’яті `build_context(...,'draft',...)`); список без кошика; відбиток збігається з тим, що приймає запис.

### Task 3: Клієнт `storygen-mcp`

**Files:** Create `src/storygen/mcp/__init__.py`, `src/storygen/mcp/bridge.py` (`build_server(http, client_name=None) -> MCPServer`, `check_url(url)`, `main(argv=None)`); Modify `pyproject.toml` (extra `mcp = ["mcp==2.3.0"]`, script `storygen-mcp = "storygen.mcp.bridge:main"`), `requirements-lock.txt`. Test `tests/mcp/test_bridge.py` (in-process `mcp.Client(server)`, HTTP через `TestClient(app, base_url='http://127.0.0.1:8765')`).

- `get_story` повертає сцени зі станом `not_started|no_text|draft|needs_review|prose` за правилами UI-FEEDBACK-S01 (мовно-нейтральні ключі `sceneStatusKey` без статусу впливу).
- Тести: S06 рівно шість інструментів; S01 недоступний сервер → помилка з адресою, каталог даних не створено; S02 імпорт той самий, що форма; S05 не-loopback URL → `SystemExit`; `save_draft` → версія з `external_origin.client`, 409 → `is_error` із текстом сервера.

### Task 4: Специфікація

**Files:** Modify `SPEC.MD` (Requirement MCP-BRIDGE, S01–S09; STORY-LANGUAGE — фіксація зважає на `external_origin`; походження версій), `docs/verification/traceability.json` (S07 — ручна процедура `docs/verification/manual.md#mcp-real-client`), `docs/verification/manual.md`; журнал, беклог R-32.
- [ ] `python scripts/check_docs.py`, повний pytest, verify.py.
