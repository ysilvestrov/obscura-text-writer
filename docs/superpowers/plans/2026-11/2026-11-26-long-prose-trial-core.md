# Проба довгої прози й серії — ядро (R-47, PR 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** У збірці Store автор може ввімкнути одну пробу на книзі або серії з двох книг, і сервер та MCP поводяться за специфікацією.

**Architecture:** Відмітка проби — запис `app_settings['long_prose_trial']` (`storage/long_prose_trial.py`). Предикати PR 1 у `book/guard.py` у гілці «видання без довгої прози» читають відмітку. Допуск книги в серію проби — у тій самій транзакції, що й місце книги (`series.require_book_slot`). Вмикання — маршрут `POST /api/long-prose-trial`, а також прапорець `trial` у створенні серії й імпорті рукопису. Інтерфейс (крім полів API) — окремий план обв'язки після рев'ю ядра.

**Tech Stack:** Python 3.12, FastAPI, SQLite, pytest; міст MCP (`mcp/bridge.py`, `mcp/edition.py`).

**Spec:** [2026-11-26-long-prose-trial-design.md](../../specs/2026-11/2026-11-26-long-prose-trial-design.md), §3.1–3.5, §3.7.

**Depends on:** PR 1 ([план](2026-11-26-long-prose-trial-refactor.md)) злито; предикати `long_prose_for`, `story_long_prose`, `series_long_prose`, `require_long_prose_for`, `require_series_long_prose` є в `book/guard.py`.

## Global Constraints

- Відмітка: `{"kind": "story" | "series", "id": str, "claimed_at": ISO UTC, "books": [str] }` (`books` лише для `series`, ≤ 2, без біблії). Створюється лише вставкою за відсутності ключа; `kind`, `id`, `claimed_at` не змінюються; `books` лише доповнюється, поки < 2; нічого не видаляється.
- Видання `full` і `paid` відмітку не читають і не пишуть; у них предикати не відкривають базу.
- Межа рейтингу `store` не змінюється.
- Нові відмови — константи в `book/guard.py`, точні тексти:
  - `TRIAL_USED = 'Пробу довгої прози вже використано; інші книги з частинами й серії — у платній версії'`
  - `TRIAL_SERIES_FULL = 'Проба серії дозволяє дві книги; третя — у платній версії'`
  - `TRIAL_IN_SERIES = 'Ця книга входить у серію; оберіть пробою серію'`
  - `TRIAL_CONFIRM = 'Проба одна на всі твори: підтвердьте вибір книги чи серії'` (422)
  - `TRIAL_NOT_NEEDED = 'Довга проза вже є в цій збірці'`
  - `TRIAL_BOOK_ALONE = 'Пробна книга не входить у серію: проба одна'`
- Тексти `NO_LONG_PROSE`, `READ_ONLY`, `READ_ONLY_SERIES` не змінюються.
- Кожна нова відмова потрапляє в `mcp/edition.py::_EXACT`, крім `TRIAL_CONFIRM` і `TRIAL_NOT_NEEDED` (не межа видання).
- Команди: `PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest …`; `scripts/check_docs.py` після змін SPEC.

## Review Focus

- Два паралельні вмикання (дві вкладки): рівно одне успішне, друге — `TRIAL_USED`; відмітка не перезаписана.
- Третя книга серії проби через кожен шлях: `create_book` (без осиротілого твору), `set_story_series`, імпорт рукопису в серію — відмова й без запису; книга, додана у виданні `full`, у Store лише для читання.
- Книга вийшла із серії проби: зберігає частини й арки; повернення в серію не займає нового місця; нова книга не займає звільнене.
- Твір проби в кошику: відмітка лишається, `trial_state` — `used`; відновлений твір знову редагується.
- Middleware: перенесення книги з частинами в серію проби пропускається лише для серії проби; в іншу серію — як і раніше `READ_ONLY`.

---

### Task 1: Сховище відмітки й предикати з пробою

**Files:**
- Create: `src/storygen/storage/long_prose_trial.py`
- Modify: `src/storygen/book/guard.py` (гілка «без довгої прози» предикатів PR 1; нові константи)
- Test: `tests/storage/test_long_prose_trial.py`, `tests/book/test_long_prose_for.py` (доповнення)

**Interfaces:**
- Produces (`storage/long_prose_trial.py`):
  - `KEY = 'long_prose_trial'`; `Trial` (pydantic: `kind`, `id`, `claimed_at`, `books: list[str] = []`)
  - `read_trial(db) -> Trial | None` (на відкритому з'єднанні) і `trial(repo) -> Trial | None`
  - `claim(db, kind: Literal['story','series'], id: str, books: list[str], now: datetime) -> Trial` — на відкритій транзакції; `ValueError(TRIAL_USED)`, якщо ключ уже є (вставка `INSERT … ON CONFLICT(key) DO NOTHING` і перевірка `changes()`).
  - `admit(db, series_id: str, story_id: str) -> None` — на відкритій транзакції, лише у виданні без довгої прози й лише для серії проби: якщо `story_id` уже в `books` — нічого; якщо місце є — дописати; інакше `ValueError(TRIAL_SERIES_FULL)`. Біблію не дописувати.
  - `trial_state(repo) -> dict` — `{'state': 'none'|'available'|'used', 'kind', 'id', 'title'}`; `none` для видання з довгою прозою (без читання бази); `title` — назва твору чи серії, якщо існують (зокрема в кошику), інакше `None`.
- Produces (`book/guard.py`): предикати PR 1 у виданні без довгої прози: `long_prose_for(repo, story)` = `kind=='story' and id==story.id`, або `kind=='series' and story.id in books`, або `story.series_bible and story.series_id == id`. `series_long_prose(repo, series_id)` = `kind=='series' and id==series_id`.

- [ ] **Step 1: Failing tests** (`tests/storage/test_long_prose_trial.py`), кожен з `store_edition`:
  - `test_claim_is_written_once` — другий `claim` → `TRIAL_USED`, відмітка та сама;
  - `test_concurrent_claims_leave_one` — два потоки з `BEGIN IMMEDIATE` + `claim` різних творів: одне успішне, одна `ValueError`;
  - `test_admit_fills_two_books_then_refuses` — третій `admit` → `TRIAL_SERIES_FULL`, повторний `admit` наявної книги нічого не змінює;
  - `test_trial_state_for_full_reads_nothing` — без `store_edition`, `repo.db = None` → `{'state': 'none', …}`;
  - `test_trashed_trial_story_is_still_used` — твір проби в кошику: `state == 'used'`, `title` — його назва.
  - У `tests/book/test_long_prose_for.py`: книга проби, книга серії в `books`, книга серії поза `books` (False), біблія серії проби (True), інша книга (False).
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.** Шаблон роботи з `app_settings` — як у `storage/model_policy_store.py`.
- [ ] **Step 4: Run, expect PASS**; плюс `tests/book tests/web/test_long_prose_guard.py -q`.
- [ ] **Step 5: Commit** `feat(R-47): відмітка проби довгої прози`.

### Task 2: Вмикання проби на книзі чи серії

**Files:**
- Create: `src/storygen/web/routes_long_prose_trial.py` (підключити в `web/app.py`, як інші роутери)
- Modify: `src/storygen/web/long_prose_guard.py` (`ALLOWED`)
- Test: `tests/web/test_long_prose_trial_api.py`

**Interfaces:**
- Consumes: Task 1.
- Produces: `POST /api/long-prose-trial` тіло `{story_id?: str, series_id?: str, confirm: bool}` (рівно одне з id, інакше 422) → 200 `trial_state`.
  - Видання з довгою прозою → 400 `TRIAL_NOT_NEEDED`; без `confirm` → 422 `TRIAL_CONFIRM`.
  - Твір: активний (не в кошику), не книга серії → інакше `TRIAL_IN_SERIES`; `claim(db, 'story', id, [], now)`.
  - Серія: існує; активних і в кошику книг без біблії ≤ 2 → інакше `TRIAL_SERIES_FULL`; `claim(db, 'series', id, [ці книги], now)`.
  - Усе в одній транзакції `BEGIN IMMEDIATE`.
  - `ALLOWED[('POST', '/api/long-prose-trial')] = 'вмикає пробу; маршрут сам перевіряє книгу чи серію'`.

- [ ] **Step 1: Failing tests:** успішне вмикання твору й серії; без `confirm`; повторне → `TRIAL_USED`; книга серії → `TRIAL_IN_SERIES`; серія з трьома книгами → `TRIAL_SERIES_FULL`; видання `full` → `TRIAL_NOT_NEEDED`; після вмикання твору `PUT /api/stories/{id}/structure` проходить, а для іншої книги з частинами — 400 `READ_ONLY`; обхід маршрутів S08 (`test_every_write_route_is_guarded_or_allowed_with_a_reason`) проходить без змін.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run, expect PASS** разом із `tests/web/test_long_prose_guard.py`.
- [ ] **Step 5: Commit** `feat(R-47): вмикання проби на книзі чи серії`.

### Task 3: Серія проби — створення, книги, перенесення

**Files:**
- Modify: `src/storygen/web/routes_series.py` (`series_create`, `series_index_page`, `story_series`)
- Modify: `src/storygen/storage/series.py` (`require_book_slot` викликає `long_prose_trial.admit`; `create_book` попередня перевірка місця; `set_story_series` — `TRIAL_BOOK_ALONE`)
- Modify: `src/storygen/storage/manuscript_store.py:61-63` — `require_book_slot(db, *series, created.id)`
- Modify: `src/storygen/web/long_prose_guard.py::blocked` — виняток для `PATCH /api/stories/{story_id}/series`
- Test: `tests/series/test_series_trial.py`

**Interfaces:**
- Consumes: Task 1 (`admit`, `claim`, предикати), Task 2 (константи).
- Produces:
  - `SeriesIn` отримує `trial: bool = False`; `POST /api/series` у виданні без довгої прози з `trial=True` створює серію й `claim(db, 'series', id, [], now)` в одній транзакції (розширити `store.create_series(repo, title, *, trial=False)`); без `trial` — як і раніше `NO_LONG_PROSE`.
  - `series_index_page`: 404, лише якщо немає довгої прози, проба не вільна і проба — не серія.
  - `require_book_slot(db, series_id, number, story_id)` після чинних перевірок викликає `admit(db, series_id, story_id)`, якщо `story_id` задано й книга не біблія (біблія йде окремою гілкою `set_story_series` і `admit` не викликає).
  - `create_book`: перед `repo.create_story` — якщо серія є серією проби й `books` уже повний, `ValueError(TRIAL_SERIES_FULL)` (без осиротілого твору); остаточна перевірка — у транзакції через `require_book_slot`.
  - `set_story_series` у виданні без довгої прози: твір, який є пробою `kind=='story'`, у серію не входить → `TRIAL_BOOK_ALONE`.
  - `story_series` (маршрут): у виданні без довгої прози — дозвіл, якщо `series_long_prose(repo, data.series_id)` (серія призначення) або `story_long_prose(repo, story_id)` (вихід зі своєї серії проби); інакше `NO_LONG_PROSE`.
  - `blocked`: для `('PATCH', '/api/stories/{story_id}/series')` повертає `None`, якщо `series_id` з JSON-тіла — серія проби (`series_long_prose`); маршрут далі перевіряє сам.

- [ ] **Step 1: Failing tests** (`store_edition`):
  - створення пробної серії з `trial: true`; без `trial` → `NO_LONG_PROSE`; друга пробна серія → `TRIAL_USED`;
  - дві книги через `create_book` → обидві в `books` і редагуються; третя → `TRIAL_SERIES_FULL`, кількість творів не змінилася;
  - перенесення книги з частинами в серію проби з одним місцем → 200, книга в `books`; в іншу серію → 400 `READ_ONLY`;
  - вихід книги із серії: частини й арки редагуються; повернення — без нового місця; нова книга після виходу → `TRIAL_SERIES_FULL`;
  - книга, додана в серію проби без `store_edition` (видання `full`), потім у Store — `PATCH` її сцени → 400 `READ_ONLY_SERIES`;
  - біблія серії проби редагується й не займає місця;
  - пробна книга (`kind=='story'`) → `PATCH …/series` → `TRIAL_BOOK_ALONE`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run, expect PASS**; плюс `tests/series tests/web/test_long_prose_guard.py -q`.
- [ ] **Step 5: Commit** `feat(R-47): серія проби з двома книгами`.

### Task 4: Імпорт рукопису як пробна книга

**Files:**
- Modify: `src/storygen/application/manuscript_import.py` (`effective_settings`, `preview`, `apply_import`; модель `ManuscriptApply` — поле `trial: bool = False`)
- Modify: `src/storygen/storage/manuscript_store.py` (`publish_manuscript(..., trial: bool = False)` — `claim(db, 'story', created.id, [], now)` у тій самій транзакції, що й книга)
- Test: `tests/application/test_manuscript_import_trial.py`

**Interfaces:**
- Consumes: Task 1, Task 3 (`require_book_slot` → `admit`).
- Produces:
  - `effective_settings`: частини дозволені, якщо є довга проза **або** `trial_state(repo)['state'] == 'available'` (функції потрібен `repo`).
  - `preview(...).edition = {'parts_allowed': …, 'series_allowed': …, 'trial': trial_state(repo)}`; `series_allowed` — довга проза або проба на серії.
  - `apply_import`: у виданні без довгої прози
    - `body.parts` чи `part_index` без серії: потрібне `body.trial` і вільна проба, інакше як і раніше `NO_LONG_PROSE`; `trial` при зайнятій пробі → `TRIAL_USED` (до будь-якого запису);
    - `body.series`: дозволено лише в серію проби (`series_long_prose`), місце перевіряє `require_book_slot` → `admit` у транзакції; інакше `NO_LONG_PROSE`;
    - `trial` разом із `series` → 422.
  - Нова книга з `trial` записує відмітку в транзакції `publish_manuscript`; збій після файлів прози, але до коміту, лишає пробу вільною (чинна логіка прибирання файлів).

- [ ] **Step 1: Failing tests** (`store_edition`): перегляд з вільною пробою розбирає частини й повертає `trial.state == 'available'`; застосування з частинами без `trial` → `NO_LONG_PROSE`; з `trial` → книга з частинами й відмітка `story`; повторно → `TRIAL_USED` і жодного файла чи твору; імпорт у серію проби займає місце, третій → `TRIAL_SERIES_FULL`; `trial` + `series` → 422; видання `full` ігнорує `trial`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run, expect PASS**; плюс `tests/application -q -k manuscript`.
- [ ] **Step 5: Commit** `feat(R-47): імпорт рукопису як пробна книга`.

### Task 5: `app-info` і підказки MCP

**Files:**
- Modify: `src/storygen/web/routes_app_info.py` — поле `long_prose_trial` (`trial_state(repo)`)
- Modify: `src/storygen/mcp/edition.py` — `_EXACT` + речення проби; `edition_refusal(detail, waitlist_url, trial_state=None)`
- Modify: `src/storygen/mcp/bridge.py:393-409` — `waitlist_url()` стає читанням `app-info` з обома полями (`waitlist_url`, `long_prose_trial`), один запит
- Test: `tests/web/test_app_info.py` (новий тест), `tests/mcp/test_bridge_edition.py` (нові тести)

**Interfaces:**
- Produces:
  - `TRIAL_AVAILABLE_TEXT = 'Одну книгу з частинами або одну серію з двох книг можна спробувати безкоштовно у вікні Obscura.\nOne book with parts or one series of two books can be tried for free in the Obscura window.'`
  - `TRIAL_USED_TEXT = 'Безкоштовну пробу вже використано.\nThe free trial has been used.'`
  - Після `PAID_TEXT`: `TRIAL_AVAILABLE_TEXT` для `state=='available'`, `TRIAL_USED_TEXT` для `used`, нічого для `none` чи недоступного `app-info`.
  - S05: відповідь `app-info` містить ще `long_prose_trial`; тест S05 на точний перелік полів доповнюється **новим** тестом, а чинний оновлюється як свідома зміна контракту (SPEC S05 у Task 6).

- [ ] **Step 1: Failing tests:** `app-info` у Store з вільною пробою → `long_prose_trial.state == 'available'`, у `full` → `'none'`; `edition_refusal(TRIAL_SERIES_FULL, url, {'state': 'used'})` містить `TRIAL_USED_TEXT` і посилання; `READ_ONLY` з `available` містить `TRIAL_AVAILABLE_TEXT`; недоступний `app-info` → без речення про пробу.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run, expect PASS**; плюс `tests/mcp tests/web/test_app_info.py -q`.
- [ ] **Step 5: Commit** `feat(R-47): стан проби в app-info і підказках MCP`.

### Task 6: SPEC і traceability

**Files:**
- Modify: `SPEC.MD`, `docs/verification/traceability.json`

- [ ] **Step 1:** Нова вимога `LONG-PROSE-TRIAL` (якір `long-prose-trial`, у змісті після BUILD-EDITION-001) за §3.1–3.5 специфікації, зі сценаріями й тестами з Task 1–5:
  - S01 вмикання з підтвердженням (книга, серія); S02 одна проба (повтор, паралельно, кошик); S03 серія з двох конкретних книг (три шляхи, вихід і повернення, книга з іншого видання, біблія); S04 імпорт рукопису як пробна книга й у серію проби; S05 `full`/`paid` ігнорують відмітку, рівень 2 лишається забороненим; S06 підказка MCP і `app-info` за станом проби.
  - Технічний опис (модулі, ключ, транзакції), сумісність (міграцій немає; старіші версії ключ ігнорують), відомі обмеження (обхід новою текою; інтерфейс — PR 3).
- [ ] **Step 2:** BUILD-EDITION-001: «MUST бути вимкнена у виданні `store`» → «у виданні `store` MUST бути вимкнена для всіх книг, крім книги чи серії проби (LONG-PROSE-TRIAL)»; S05 (поле `long_prose_trial`), S08 (виняток), S09; SERIES-S06; STORE-MCP-001 S05 (речення проби); правила видання в MANUSCRIPT-IMPORT.
- [ ] **Step 3:** traceability — запис на кожен новий сценарій із тестами Task 1–5; змінені сценарії — нові тести.
- [ ] **Step 4:** `PYTHONUTF8=1 .venv/Scripts/python.exe scripts/check_docs.py` → узгоджено.
- [ ] **Step 5: Commit** `docs(R-47): LONG-PROSE-TRIAL у SPEC`. У повідомленні: «Сайт і знімки — у PR 3 (інтерфейс проби ще не видно)».

## Завершення

Фінальне рев'ю всієї гілки (воно ж рев'ю ядра для pr-slicing), `scripts/verify.py` з `C:/tmp/r47b`, cross-review, PR на `main` без «Closes #287». Після злиття — план обв'язки: кнопка проби в книзі, діалог імпорту, сторінка серій і бібліотека в Store, поле `long_prose` твору для модулів книги, банери, сайт uk/en (`paid`, `install`, структура, серії), скіли; останній PR несе «Closes #287».
