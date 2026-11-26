# Режим «Пишу сам» — ядро: план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** третій режим твору `author`, у якому сервер не дає моделі писати чи застосовувати прозу, а міст — зберігати текст чату.

**Architecture:** новий модуль `storygen/writing_mode.py` тримає перелік того, що пише прозу, тексти відмов і перевірки. Перевірки стоять у `RunCoordinator.enqueue` (409 до черги), в `execute_stage` (до виклику моделі й перед збереженням результату), у маршрутах застосування пропозицій і в маршрутах зовнішнього тексту (`external_origin`). Міст MCP отримує гілку `author`. Інтерфейс, діалог пам'яті й вітрина — окремий план обв'язки після рев'ю ядра.

**Tech Stack:** Python 3.12, FastAPI, pydantic, pytest; MCP-міст `storygen-mcp`.

**Spec:** [2026-11-26-author-mode-design.md](../../specs/2026-11/2026-11-26-author-mode-design.md) (затверджено 26.11.2026: brief дозволено, коректуру заборонено, типовий режим форми — `obscura`).

## Global Constraints

- Значення режиму — рівно `'author'`; `Literal['chat','obscura','author']` у `domain.py` (`Story`, `StoryCreate`), `web/routes_stories.py` (`StoryWritingModeChange`), `mcp/bridge.py` (`create_story`). Типове значення `Story` лишається `'chat'`.
- Текст відмови запуску (uk): `Твір у режимі «Пишу сам»: модель не пише прозу. Змініть режим у налаштуваннях твору`. Ключ `writing_mode.author_writes`; en: `The story is in the "I write myself" mode: models do not write prose. Change the mode in the story settings`.
- Текст відмови мосту (uk): `Твір у режимі «Пишу сам»: прозу пише автор`. Ключ `writing_mode.author_chat`; en: `The story is in the "I write myself" mode: the author writes the prose`.
- Пишуть прозу: `stage`+`draft`, `stage`+`edit`, `scene`, `remaining`, `edit_loop`, `rewrite`. Решта режимів `RunRequest.mode` дозволені, `stage`+`brief` і `stage`+`memory` теж.
- Етапи `execute_stage`, що пишуть прозу: `{'draft','edit','rewrite'}`.
- Відмови HTTP — `RevisionConflict` (409) до будь-якого запису; `execute_stage` кидає `AuthorWritesBlocked(ValueError)`.
- Режими `chat` і `obscura` поводяться як досі (І3); ручні збереження автора без `external_origin` у режимі `author` проходять.
- Документацію пишемо українською; кожен новий Scenario має ID і запис у `docs/verification/traceability.json`; `PYTHONUTF8=1 .venv/Scripts/python.exe scripts/check_docs.py` зелений.

## Review Focus

- Запуск поставлено в черзі в `obscura`, а режим змінено до його кроку: крок `draft` має зупинити запуск з текстом відмови, без версії (Task 3).
- Відповідь моделі вже йде під час перемикання: версії не повинно бути, спроба `failed` (Task 3).
- `POST …/draft` з `external_origin` **без** заголовка моста в режимі `author`: 409, без версії (Task 4).
- Повтор `request_id` запуску, створеного ще в `obscura`, після перемикання повертає наявний запуск, а не 409 (Task 2).
- Новий режим `RunRequest.mode` без рішення: тест повноти червоний (Task 1).

---

### Task 1: Значення режиму й модуль перевірок

**Files:**
- Create: `src/storygen/writing_mode.py`
- Modify: `src/storygen/domain.py:43` (і `StoryCreate`), `src/storygen/web/routes_stories.py:43`, `src/storygen/mcp/bridge.py:717`, `src/storygen/web/static/i18n.json` (uk/en ключі з Global Constraints)
- Test: `tests/web/test_author_mode.py` (новий)

**Interfaces:**
- Produces:
  - `AUTHOR_WRITES: str`, `AUTHOR_CHAT: str` (тексти з Global Constraints);
  - `class AuthorWritesBlocked(ValueError)`;
  - `PROSE_STAGES: frozenset[str] = {'draft','edit','rewrite'}`;
  - `RUN_MODE_WRITES: dict[str, bool | None]` — для кожного значення `RunRequest.mode`: `True` (пише), `False` (не пише), `None` (вирішує `stage`);
  - `writes_prose(request: RunRequest) -> bool`;
  - `is_author(repo, story_id: str) -> bool`.

- [ ] **Step 1: Тести.** У `tests/web/test_author_mode.py`:
  - `test_every_run_mode_has_a_prose_decision`: `set(RUN_MODE_WRITES) == set(get_args(RunRequest.model_fields['mode'].annotation))`.
  - `test_writes_prose_by_mode_and_stage`: `True` для `stage`+`draft`, `stage`+`edit`, `scene`, `remaining`, `edit_loop`, `rewrite`; `False` для `stage`+`brief`, `stage`+`memory`, `prepare`, `rebuild_memory`, `memory_carry`, `evaluate`, `audit`, `character_extract`, `classify`, `publication_suggest`, `timeline_summary`.
  - `test_author_mode_is_accepted_at_creation_and_switch`: `POST /api/stories {writing_mode:'author'}` → 200, і `PUT …/writing-mode` з `author` → ревізія +1.
- [ ] **Step 2: Перевірити, що тести падають.** `PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest tests/web/test_author_mode.py -q`. Очікується ImportError або 422.
- [ ] **Step 3: Реалізувати модуль і розширити `Literal`.** Додати i18n-ключі uk/en.
- [ ] **Step 4: Прогнати тести.** Той самий pytest + `tests/web/test_writing_mode.py tests/mcp/test_bridge_writing_mode.py`. Очікується PASS.
- [ ] **Step 5: Коміт** `feat(R-49): режим твору author і перелік запусків, що пишуть прозу`.

### Task 2: Відмова в `enqueue`

**Files:** Modify `src/storygen/generation/worker.py:65-80`; Test `tests/web/test_author_mode.py`.

**Interfaces:** Consumes `writes_prose`, `is_author`, `AUTHOR_WRITES` з Task 1.

- [ ] **Step 1: Тести.**
  - `test_author_mode_refuses_prose_runs_before_the_queue` (параметризований за шістьма запитами, що пишуть прозу): `POST /api/runs` → 409 з `AUTHOR_WRITES`; кількість запусків твору не змінилася.
  - `test_author_mode_allows_memory_brief_and_audit_runs`: `stage`+`brief`, `stage`+`memory`, `audit` проходять перевірку режиму. Відповідь не 409 з `AUTHOR_WRITES`; інша відмова готовності допустима.
  - `test_same_request_id_after_switch_returns_the_existing_run`: запуск `stage`+`draft` створено в `obscura`, режим змінено на `author`, той самий `request_id` повертає той самий `run.id`.
- [ ] **Step 2: Перевірити, що тести падають.**
- [ ] **Step 3: Реалізувати.** Одразу після `self.repo.get_story(request.story_id)` (після ідемпотентної гілки): якщо `is_author(...)` і `writes_prose(request)`, кинути `RevisionConflict(AUTHOR_WRITES)`.
- [ ] **Step 4: Прогнати тести.** Очікується PASS.
- [ ] **Step 5: Коміт.**

### Task 3: Відмова в `execute_stage` і причина запуску

**Files:** Modify `src/storygen/generation/stages.py` (блок політики біля `:28` і місце після `text=''.join(parts)`), `src/storygen/generation/worker.py:524-526` (`_failure_message`); Test `tests/generation/test_author_mode_stages.py` (новий).

**Interfaces:** Consumes `PROSE_STAGES`, `is_author`, `AuthorWritesBlocked`, `AUTHOR_WRITES`.

- [ ] **Step 1: Тести.** Фальшивий gateway — за зразком наявних тестів `execute_stage` у `tests/generation`.
  - `test_execute_stage_refuses_prose_stage_before_the_call`: твір `author`, `stage='draft'` → `AuthorWritesBlocked`; gateway не викликано; спроби немає.
  - `test_switch_during_the_response_saves_no_version`: gateway під час стріму змінює режим на `author` → `AuthorWritesBlocked`; нової версії `draft` немає; остання спроба `state=='failed'` і `error==AUTHOR_WRITES`.
  - `test_memory_stage_runs_in_author_mode`: `stage='memory'` у творі `author` не кидає `AuthorWritesBlocked`.
  - `test_queued_run_stops_with_the_mode_reason`: через `RunCoordinator` запуск `stage`+`draft` поставлено в `obscura`, режим змінено, крок виконано → `run.state=='failed'`, `run.error==AUTHOR_WRITES`.
- [ ] **Step 2: Перевірити, що тести падають.**
- [ ] **Step 3: Реалізувати.**
  - До `id=new_id()`: `if stage in PROSE_STAGES and is_author(repo, context.story_id): raise AuthorWritesBlocked(AUTHOR_WRITES)`. Перевірка не залежить від `external_origin`.
  - Після `text=''.join(parts)` та сама перевірка, але спершу `attempt.state='failed'; attempt.error=AUTHOR_WRITES; repo.save_attempt(attempt)`.
  - У `_failure_message`: `AuthorWritesBlocked` у кортежі поряд із `ModelPolicyBlocked`.
- [ ] **Step 4: Прогнати тести** разом із `tests/generation -q -k "stage or worker"`. Очікується PASS.
- [ ] **Step 5: Коміт.**

### Task 4: Маршрути застосування й зовнішнього тексту

**Files:** Modify `src/storygen/web/routes_versions.py:92-96, 172-207`, `src/storygen/web/routes_rewrites.py:40-43`, `src/storygen/web/bridge_marker.py:58-67`; Test `tests/web/test_author_mode.py`.

**Interfaces:**
- Produces: `guard_scene_write(request, scene_id: str, stage: str) -> None` (новий обов'язковий параметр; `…/draft` передає `'draft'`);
- Produces: `refuse_external_in_author(repo, scene_id: str) -> None` у `bridge_marker.py`.

- [ ] **Step 1: Тести.**
  - `test_author_mode_refuses_external_draft_with_and_without_bridge_header`: `POST …/draft` з `external_origin`, з `BRIDGE` і без нього → 409 `AUTHOR_CHAT`; версій `draft` не додалося.
  - `test_author_mode_keeps_manual_draft_and_prose`: `POST …/draft` без `external_origin` → 200.
  - `test_author_mode_chat_stages`: з `BRIDGE` `chat-task/draft` і `chat-task/edit` → 409 `AUTHOR_CHAT`; `chat-task/memory` і `chat-task/brief` → 200. Без заголовка `chat-result/edit` з `external_origin` → 409.
  - `test_author_mode_refuses_applying_model_proposals`: `POST …/copyedits/{attempt}` і `POST …/rewrites/{attempt}/apply` → 409 `AUTHOR_WRITES`; ревізія сцени та голови без змін.
  - `test_author_mode_refusals_in_english`: `Accept-Language: en` дає en-тексти з Global Constraints.
- [ ] **Step 2: Перевірити, що тести падають.**
- [ ] **Step 3: Реалізувати.**
  - `guard_scene_write` для мосту: `obscura` — як досі; `author` і `stage in {'draft','edit'}` → `RevisionConflict(AUTHOR_CHAT)`.
  - `refuse_external_in_author` викликати в `chat-result` і в `…/draft` з `external_origin` до запису, незалежно від `from_bridge`.
  - Маршрути застосування спершу перевіряють `is_author` і кидають `RevisionConflict(AUTHOR_WRITES)`. Пропозиції `editor_import` йдуть іншим маршрутом і не змінюються.
- [ ] **Step 4: Прогнати тести** + `tests/web/test_writing_mode.py tests/web/test_chat_stage_routes.py -q`. Очікується PASS.
- [ ] **Step 5: Коміт.**

### Task 5: Міст MCP

**Files:** Modify `src/storygen/mcp/bridge.py` (тексти `:109`, `:125`, `:422`, `create_story :717-726`, `start_run :1306`, `next_steps :1466`), `src/storygen/web/bridge_marker.py` (якщо потрібен текст); Test `tests/mcp/test_bridge_writing_mode.py`.

- [ ] **Step 1: Тести.**
  - `test_create_story_in_author_mode`: `create_story(writing_mode='author')` → `writing_mode=='author'`.
  - `test_start_run_in_author_mode`: `draft`/`edit` → ToolError з текстом «Пишу сам»; `rebuild_memory` → `MEMORY_CHAT_PATH`; `audit` → перегляд.
  - `test_save_draft_in_author_mode_is_refused`: ToolError містить `AUTHOR_CHAT`.
  - `test_next_steps_in_author_mode_offers_memory_not_drafting`: текст містить `get_stage_task(stage='memory')` і не містить `stage='edit'`.
  - `test_server_instructions_describe_author_mode`: інструкції сервера містять `«author»`.
- [ ] **Step 2: Перевірити, що тести падають.**
- [ ] **Step 3: Реалізувати** гілку `author`: тексти, `start_run` (етапи прози → `AUTHOR_WRITES`-подібний текст для чату), `next_steps`, опис `create_story`, `list_stories`.
- [ ] **Step 4: Прогнати** `tests/mcp -q`. Очікується PASS.
- [ ] **Step 5: Коміт.**

### Task 6: SPEC.MD і traceability (ядро)

**Files:** Modify `SPEC.MD` (WRITING-MODE `:6200-6236`, MCP-BRIDGE опис `start_run` `:5437`, відомі обмеження), `docs/verification/traceability.json`.

- [ ] **Step 1: Текст вимог.** WRITING-MODE: третій режим, перевірки сервера, міст, `external_origin` незалежно від позначки, сумісність (старіша версія не відкриває бібліотеки з книгою `author`), відомі обмеження. Нові сценарії:
  - **S05** — запуски, що пишуть прозу, відхиляються, решта проходить;
  - **S06** — крок після перемикання, зокрема відповідь, що вже йшла;
  - **S07** — міст і зовнішній текст у режимі `author`;
  - **S08** — застосування пропозицій.
  
  S09 (інтерфейс) і показ даних пам'яті — в плані обв'язки.
- [ ] **Step 2: traceability.** Кожен новий сценарій прив'язати до тестів Task 1–5. S01 доповнити `test_author_mode_is_accepted_at_creation_and_switch`.
- [ ] **Step 3: Перевірка.** `PYTHONUTF8=1 .venv/Scripts/python.exe scripts/check_docs.py` → «узгоджені».
- [ ] **Step 4: Коміт** `docs(R-49): SPEC WRITING-MODE для режиму author`.
