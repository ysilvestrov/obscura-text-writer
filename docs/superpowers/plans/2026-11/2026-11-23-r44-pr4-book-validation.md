# R-44 PR 4 — валідація книги: план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** запуск `audit` для всієї книги з попереднім переглядом (зв'язки, виклики, верхня межа вартості, відбиток плану), пункт меню «Валідація книги» з лічильником невалідних сцен, дія `audit` у MCP `start_run`, закріплення повноти експорту, SPEC і сайт uk/en.

**Architecture:** `audit_run` отримує область `story`: на кожному кроці worker бере перший невалідний зв'язок у порядку читання по всій книзі (сцени за позицією, у сцені З1 → З2 → З3) і зупиняється в `needs_review` так само, як для сцени. Попередній перегляд — окремий маршрут `POST /api/stories/{id}/audit/preview`, що лише читає й повертає відбиток плану; `POST /api/runs` для `audit` звіряє цей відбиток і відмовляє, якщо план змінився. Вартість — `tariff.price(max_input_chars*4+256, max_output_tokens) × calls` для хмарних провайдерів зі збереженим чинним тарифом.

**Tech Stack:** Python 3.12, Pydantic v2, FastAPI, SQLite, vanilla JS, pytest, node-скрипти JS-тестів, Playwright.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-23-book-validation-design.md` (розділи 9, 12, 13, 14, 15). Чинна архітектура — `SPEC.MD` (VALID-RUN, VALID-AUDITOR, VALID-LINKS, MCP-BRIDGE, WORKSPACE-TOOLS, EXPORT-001, EXPORT-CLEAN).

## Global Constraints

- `RunRequest.audit_scope: Literal['scene','story'] | None`; `mode='audit'` ⇔ `audit_scope` задано; `scene` вимагає `scene_id`, `story` — `scene_id is None`.
- `RunRequest.audit_plan_fingerprint: str | None` (sha256, 64 hex). Для `story` обов'язковий; для `scene` необов'язковий (кнопка сцени з PR 3 лишається сумісною), але якщо заданий — звіряється.
- Відбиток плану = sha256 канонічного JSON `{'scope', 'scene_id', 'links': [[scene_id, link, status, link_fingerprint]…], 'auditor': {provider, model, base_url, max_input_chars, max_output_tokens}}`. Розбіжність під час `POST /api/runs` → 409/ValueError «План перевірки змінився. Перегляньте його ще раз».
- Порядок читання книги: `view.list_scenes(story_id)` без кошика за `position`; у сцені `brief → prose → memory`; `missing` і `valid` пропускаються.
- Виклик рахується лише для `unchecked` і для переповнення Ревізора (`unavailable` з `source='auditor'` і причиною переповнення). Структурне `unavailable` (з `link_state` чи висновок Ревізора не про переповнення) і `discrepancy` — без виклику.
- Верхня межа вартості: `tariff.price(settings.max_input_chars*4+256, settings.max_output_tokens) × calls`; лише хмарні провайдери (`venice`, `openrouter`) з чинним збереженим тарифом (`repo.billing('tariff_get', …)`, `.current()`); інакше `cost_usd: null` і попередження. Локальні — без USD.
- Хмарний запуск вимагає ліміту твору (як інші запуски).
- Попередній перегляд не є верхньою межею, якщо автор змінює компоненти під час запуску — інтерфейс це каже.
- Лічильник меню: кількість сцен із `validity in {'unchecked','discrepancy'}` з `material_status`; 0 → пункт показує «Книга валідна» і неактивний.
- Мова документації — українська; OpenSpec-маркери англійські; кожен Scenario — у `docs/verification/traceability.json`; сайт `docs/site/{uk,en}` парами з `check_site.py --rehash`.
- Гейт: `python scripts/check_docs.py && python -m pytest -q` (venv, `PYTHONUTF8=1 PYTHONPATH=src`, `-p no:cacheprovider --basetemp=C:/tmp/r44p4/<ім'я>`).

## Review Focus

1. Книга, де всі сцени валідні, крім однієї в середині: перегляд показує 1 сцену; запуск робить виклики лише для неї й завершується `completed` — Task 1.
2. Під час зупиненої валідації книги автор затверджує зв'язок у сцені 3, а потім правкою прози робить невалідною сцену 1: продовження бере сцену 1 першою (порядок читання перечитується на кожному кроці) — Task 1.
3. Автор відкрив перегляд, потім змінив модель Ревізора або зв'язок: запуск із давнім відбитком відмовляє «План перевірки змінився», нічого не платячи — Task 1, Task 2.
4. Тариф моделі застарів або провайдер локальний: перегляд показує виклики без USD і пояснення, запуск не падає на ціні — Task 2.
5. MCP-клієнт у творі режиму «chat» запускає `audit`: Ревізор не пише тексту, тож обмеження режиму письма не діє, але попередній перегляд без `confirm` нічого не запускає — Task 4.

---

### Task 1: область `story` у запуску `audit`

**Files:**
- Modify: `src/storygen/run_models.py` (`audit_scope`, `audit_plan_fingerprint`, валідатори), `src/storygen/generation/audit_run.py` (`book_pending`, `plan_fingerprint`, `readiness`, `execute`, `_called`), `src/storygen/generation/worker.py` (`enqueue`: звірка відбитка; `_supersede`: нова валідація книги замінює зупинені `audit` того самого твору в `needs_review`; `readiness(..., operation='audit_story')`), `src/storygen/web/routes_runs.py` (Literal `audit_story`; `_refuse_carry`/`guard_bridge_run` терплять `scene_id=None`)
- Test: `tests/generation/test_audit_run.py`, `tests/web/test_runs.py`

**Interfaces:**
- Produces: `audit_run.book_pending(view) -> list[tuple[str, LinkName]]`; `audit_run.plan_fingerprint(scope, scene_id, entries, settings) -> str`; `audit_run.readiness(repo, request, view=None, resume=False)` для `story` повертає ключі сцени плюс `links: [{'scene_id','link','status','reason'}]`, `invalid_scenes: int`, `plan_fingerprint`; checkpoint зупинки як у PR 3 (`scene_id` — сцена зупинки).

- [ ] **Step 1: тести** (RED):
  - `book_pending` на книзі з 4 сцен (1 валідна, 2 `unchecked` З2, 3 `discrepancy` З1 + `unchecked` З2, 4 `missing`) → `[(s2,'prose'),(s3,'brief'),(s3,'prose')]`;
  - перегляд `story`: `calls == 2` (`discrepancy` без виклику), `invalid_scenes == 2`, `plan_fingerprint` стабільний між двома викликами й змінюється після зміни моделі Ревізора;
  - виконання: шлюз повертає `valid` для s2 → наступний крок s3 `discrepancy` → `needs_review`, `checkpoint.scene_id == s3`, `phase == 'awaiting_author'`;
  - продовження після «Затвердити» в s3 і ручної правки прози s1 → наступний виклик для s1 (Review Focus 2);
  - книга без невалідних сцен → `ready=False`, «Книга вже валідна»;
  - `POST /api/runs` з давнім `audit_plan_fingerprint` → відмова «План перевірки змінився. Перегляньте його ще раз», шлюз не викликано; без відбитка для `story` → 422;
  - нова валідація книги переводить зупинену `audit` того самого твору в `superseded`;
  - структурне `unavailable` не за переповненням з висновком Ревізора не додає виклику (відкладена дрібниця PR 3).
- [ ] **Step 2: реалізувати → PASS.** Лічильник `stale` скидається, коли змінюється пара (сцена, зв'язок).
- [ ] **Step 3: коміт** `feat: валідація книги — запуск audit для всього твору`.

### Task 2: маршрут попереднього перегляду й вартість

**Files:**
- Create: `src/storygen/generation/audit_cost.py` (`upper_bound(repo, settings, calls) -> dict`)
- Modify: `src/storygen/web/routes_runs.py` або новий `routes_audit.py` (`POST /api/stories/{id}/audit/preview`, тіло `{scope:'scene'|'story', scene_id?}`), `src/storygen/generation/audit_run.py` (`readiness` додає `cost`)
- Test: `tests/generation/test_audit_cost.py`, `tests/web/test_audit_preview_api.py`

**Interfaces:**
- Consumes: `audit_run.readiness` (Task 1), `billing.models.Tariff.price`, `repo.billing('tariff_get', provider=, model=, base_url=)`.
- Produces: `upper_bound(...) -> {'per_call_usd': str|None, 'total_usd': str|None, 'reason': str|None}`; відповідь маршруту = результат `readiness` + `cost`; маршрут лише читає (жодних записів у БД — тест через лічильник рядків `app_settings`/`runs`).

- [ ] **Step 1: тести** (RED): хмарний провайдер із чинним тарифом → `total_usd == price(max_input_chars*4+256, max_output_tokens) × calls`; тариф прострочений → `total_usd is None`, `reason` «Ціна моделі застаріла; оновіть ціни в налаштуваннях»; локальний провайдер → `None` без попередження про ціну; `calls == 0` → `0`; маршрут для `scene` і `story`; маршрут не змінює БД.
- [ ] **Step 2: реалізувати → PASS.**
- [ ] **Step 3: коміт** `feat: попередній перегляд перевірки з верхньою межею вартості`.

### Task 3: меню «Валідація книги» й інтерфейс запуску

**Files:**
- Modify: `src/storygen/web/templates/story.html` (`#story-menu-validate` з лічильником), `src/storygen/web/static/story-menu.js` або новий `book-validation.js` (лічильник з `material_status`, діалог перегляду: сцени, виклики, сума чи «без суми» з причиною, застереження про зміни під час запуску; згода → `POST /api/runs {mode:'audit', audit_scope:'story', audit_plan_fingerprint}`), `src/storygen/web/static/link-decision.js` (кнопка сцени бере перегляд із маршруту Task 2 і показує суму), `src/storygen/web/static/run-summary.js` (зупинена валідація: «Перейти до сцени N» за `checkpoint.scene_id`), `src/storygen/web/static/i18n.json`
- Test: `tests/web/js/book_validation.mjs` (або розширення `run_readiness.mjs`), `tests/web/test_workspace_layout_ui.py`, `tests/web/browser/book-validation.spec.mjs`

- [ ] **Step 1: тести** (RED): лічильник = кількість `unchecked`+`discrepancy`, 0 → «Книга валідна» (неактивний); діалог показує кількість сцен, виклики й суму / причину без суми; без згоди запуску немає; Playwright із фейковим шлюзом: дві невалідні сцени, перша `discrepancy` → зупинка, підсумок запуску веде до сцени, після «Затвердити» й «Продовжити» друга сцена перевіряється й лічильник стає 0.
- [ ] **Step 2: реалізувати → PASS.** Відновити `docs/images` після Playwright.
- [ ] **Step 3: коміт** `feat: пункт меню «Валідація книги» з лічильником і переглядом`.

### Task 4: MCP і повнота експорту

**Files:**
- Modify: `src/storygen/mcp/bridge.py` (`RUN_ACTIONS` += `audit`; `start_run(action='audit', scene_id?)` → область `scene` або `story`, перегляд через маршрут Task 2 з `cost`, запуск із `audit_plan_fingerprint` лише з `confirm`; обмеження режиму письма для `audit` не діє; `get_run` повертає `audit_scope` і `checkpoint`)
- Test: `tests/mcp/test_bridge_audit.py`, `tests/mcp/test_bridge_settings.py` (перелік дій), `tests/publication/test_book_capture*.py` або найближчий тест `publication/book.py::capture`

- [ ] **Step 1: тести** (RED): `start_run('audit')` без `confirm` повертає перегляд і нічого не ставить у чергу; з `confirm` — запуск `story` з відбитком; зі `scene_id` — `scene`; твір у режимі `chat` — дозволено; `get_run` для зупиненої валідації має `checkpoint.scene_id`. Експорт: проза сцени з `unchecked` З2 (не прийнята) дає попередження «Сцена застаріла або потребує перегляду» і без `allow_incomplete` блокує експорт; прийнята проза — без попередження; сцена з `missing` З1 (проза без завдання) — без попередження (закріплення чинної поведінки PR 2).
- [ ] **Step 2: реалізувати → PASS.**
- [ ] **Step 3: коміт** `feat: дія audit у MCP і закріплення повноти експорту`.

### Task 5: SPEC, traceability, сайт

- [ ] **SPEC.MD:** нова вимога VALID-UI (меню «Валідація книги» з лічильником, кнопка сцени, панель розбіжностей, опитування; Scenario); VALID-RUN — область `story`, маршрут перегляду, відбиток плану, вартість (нові Scenario), прибрати обмеження «прийде в PR 4»; VALID-LINKS — прибрати «валідації книги ще немає»; WORKSPACE-TOOLS-S01 — «Валідація книги» замість «пункту немає»; MCP-BRIDGE — дія `audit`; EXPORT-001 / EXPORT-CLEAN — повнота за валідністю; відомі обмеження (оцінка токенів завищена — сума консервативна; формула `max_input_chars*4+256`).
- [ ] **traceability.json:** кожен новий Scenario → тести Task 1–4 (Playwright — `manual` у `docs/verification/manual.md#book-validation-browser`).
- [ ] **Сайт uk/en:** `workspace` (меню «Валідація книги», зупинка й продовження), `revision` (валідація книги замість давньої перевірки), `mcp` (`start_run` з `audit`), `troubleshooting` («План перевірки змінився», сума без USD); `check_site.py --rehash` для кожної пари; знімок меню — `scripts/capture_screenshots.py`.
- [ ] `python scripts/check_docs.py` — OK; коміт `docs: валідація книги в SPEC, traceability й на сайті`.
