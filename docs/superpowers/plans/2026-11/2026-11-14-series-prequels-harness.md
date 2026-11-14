# Приквели в серії 4б — обв'язка. План реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** дати автору доступ до приквелів ядра: перегляд фактів пізніших книг із позначками «минуле/майбутнє», джерела й розв’язані конфлікти на екрані серії, приквел у MCP і сайт.

**Architecture:** обв'язка спирається на ядро як воно є: `GET /api/stories/{id}/series/facts`, `PUT /api/stories/{id}/series/decisions`, `SeriesStatus{prequel, resolved, state='prequel_review'}`, `writing_context.future`. Нового механізму пам’яті немає. Інтерфейс — новий модуль `static/series-facts.js` у налаштуваннях книги за зразком `series-settings.js` і `dialogs.js`; екран серії — `series-page.js`.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, ванільні JS-модулі, pytest, Playwright (`tests/web/browser/series.spec.mjs`).

**Spec:** `docs/superpowers/specs/2026-11/2026-11-14-series-prequels-design.md` (затверджена); ядро — `docs/superpowers/plans/2026-11/2026-11-14-series-prequels-core.md`, реєстр рішень — `.superpowers/sdd/2026-11-14-series-prequels-core/progress.md`.

## Висновки самоперевірки ядра, на які спирається план

- Порожнє поле `future` не входить у відбиток контексту MCP — новий код MCP має це зберегти.
- Тексти стану `series.status.prequel`/`prequel_review` і розділ сайту «Приквели» вже оновлено в ядрі; обв’язка доповнює сайт екраном фактів.
- Статус не несе списку джерел — для рядка «джерела: …» його треба додати (`SeriesStatus.sources`).

## Global Constraints

- Довга проза лише у виданнях `full`/`paid`; у `store` кнопки перегляду фактів немає, `PUT` позначок відхиляється.
- Збереження позначок — з підтвердженням (діалог застосунку, `dialogs.js`), бо робить застарілими пам’ять і завдання перших сцен; `expected_revision` — ревізія, яку бачив автор; 409 — повідомлення й перезавантаження.
- Позначки ставляться лише в застосунку; інструментів MCP для них немає.
- Переклади uk/en у `i18n.json`; сайт `docs/site/{uk,en}/series.md` парою з `check_site.py --rehash series`; знімки екрана не обов’язкові, лише на нейтральному прикладі.
- SPEC.MD SERIES-001: S11 і зняти «відомі обмеження» обв’язки.

## Review Focus

- Приквел без записів стартової пам’яті (книга 1 без фактів): перегляд показує «немає записів», «Зберегти» вимкнене.
- Збереження без змін: кнопка вимкнена, лічильник 0 — без нової версії й застарілості.
- Книга, що перестала бути приквелом (змінено номер): кнопки перегляду немає, а `PUT` відповідає 422 з поясненням.
- Екран серії з книгою після двох приквелів: джерела в порядку номерів, розв’язані конфлікти з назвами книг, без ID.
- Store: кнопки немає й для книги-приквела, лише читання.

---

### Task 1: Джерела в стані й MCP

**Files:**
- Modify: `src/storygen/book/series.py` (`SeriesStatus.sources: list = field(default_factory=list)` — ID книг-джерел знімка в порядку `sources`)
- Modify: `src/storygen/mcp/bridge.py` (`story_series`: `prequel`, `resolved_count`)
- Test: `tests/series/test_series_prequel_harness.py`, `tests/mcp/` (наявний тест `get_story` серії)

**Interfaces:**
- Produces: `series_status(...).sources -> list[str]`; `story_series(data) -> {title, number, start, status, prequel: bool, resolved_count: int}`.

- [ ] **Step 1: Тести**: `test_status_lists_the_sources_of_a_book_after_prequel` (книга 3 після приквела 2: `status.sources == [book1, prequel]`, `len(status.resolved) == 1`); `test_get_story_shows_prequel_and_review_state` (MCP `get_story` приквела: `series.prequel is True`, `series.status == 'fresh'`; знімок 4а — `prequel_review`); `test_scene_context_of_a_prequel_has_future` (MCP `get_scene_context` має `future` з рядком стану героя).
- [ ] **Step 2: Запустити** — FAIL.
- [ ] **Step 3: Реалізувати.**
- [ ] **Step 4: Запустити** `pytest tests/series tests/mcp -q` — PASS.
- [ ] **Step 5: Commit** `feat(series): sources in the status and the prequel in MCP`.

### Task 2: Перегляд фактів пізніших книг

**Files:**
- Create: `src/storygen/web/static/series-facts.js`
- Modify: `src/storygen/web/templates/settings.html` (кнопка `data-series-facts` у `#story-series-form`, діалог `#series-facts-dialog`), `src/storygen/web/static/series-settings.js` (показ кнопки за `series.status.prequel`), `src/storygen/web/static/i18n.json` (`series.facts.*`), стилі за наявними класами діалогів
- Test: `tests/web/browser/series.spec.mjs` (новий case), `tests/series/test_series_screen.py` (шаблон має кнопку й діалог)

**Interfaces:**
- Consumes: `GET .../series/facts` → `{facts: [{key, category, text, character_ids, story_id, decision}]}`; `PUT .../series/decisions {decisions, expected_revision, confirm: true}`.
- Produces: діалог із групами за категоріями (`series.facts.category.<name>`), рядок запису — текст, назва книги-джерела, перемикач «минуле/майбутнє»; «Усе — майбутнє»; лічильник змін `series.facts.changed`; «Зберегти» — лише змінені ключі, після `confirmDialog(series.facts.confirm)`.

- [ ] **Step 1: Тести**: Playwright `prequel facts review` — серія з дописаною книгою 1 (фікстура сервера з нейтральною пам’яттю, як у наявних cases), приквел 2 `Рік -10, опора 1`; кнопка видна; перегляд показує записи книги 1 з позначкою «майбутнє»; перемкнути стан героя на «минуле», лічильник 1, «Зберегти» → діалог підтвердження → після збереження перегляд показує «минуле», статус «знімок актуальний». pytest `test_settings_page_has_the_facts_review` — шаблон має `data-series-facts` і `#series-facts-dialog`.
- [ ] **Step 2: Запустити** — FAIL.
- [ ] **Step 3: Реалізувати.** Кнопка прихована для книги не-приквела й у Store (`appInfo().long_prose`).
- [ ] **Step 4: Запустити** `pytest tests/series -q`, `cd frontend && npx playwright test series` — PASS (desktop і mobile).
- [ ] **Step 5: Commit** `feat(series): review the facts of later books in a prequel`.

### Task 3: Екран серії: джерела й розв’язані конфлікти

**Files:**
- Modify: `src/storygen/web/static/series-page.js`, `src/storygen/web/static/i18n.json` (`series.sources`, `series.resolved_summary`, `series.resolved_item`)
- Test: `tests/web/browser/series.spec.mjs`

**Interfaces:**
- Consumes: `GET /api/series/{id}` → `books[].status.sources`, `books[].status.resolved`.
- Produces: на картці книги з двома й більше джерелами — «Джерела: книга 1, приквел 2»; розгортання `<details>` «Автоматично взято стан книги 1: N записів» зі списком «текст приквела → лишилося значення книги 1» (назви книг, без ID).

- [ ] **Step 1: Тест** Playwright `series screen shows the sources after a prequel`.
- [ ] **Step 2: Запустити** — FAIL.
- [ ] **Step 3: Реалізувати.**
- [ ] **Step 4: Запустити** `cd frontend && npx playwright test series` — PASS.
- [ ] **Step 5: Commit** `feat(series): sources and resolved conflicts on the series screen`.

### Task 4: SPEC, сайт, ручна процедура

**Files:**
- Modify: `SPEC.MD` (SERIES-001: S11, обв’язка в технічному описі, «Відомі обмеження»), `docs/verification/traceability.json`, `docs/verification/manual.md#series-browser`, `docs/site/{uk,en}/series.md` (розділ «Приквели»: перегляд фактів і позначки), `docs/superpowers/plans/2026-10-20-remediation-progress.md`

- [ ] **Step 1:** SPEC S11 з ID і traceability (pytest-тести Tasks 1–3 + ручна процедура для Playwright).
- [ ] **Step 2:** сайт uk/en, `python scripts/check_site.py --rehash series`.
- [ ] **Step 3: Запустити** `python scripts/check_docs.py` — «узгоджені»; `pytest tests/series -q` — PASS.
- [ ] **Step 4: Commit** `docs(series): prequel interface in SPEC, site and manual check`.
