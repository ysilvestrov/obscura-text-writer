# Серії 4a — обв'язка. План реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** дати автору доступ до серій ядра: імпорт преамбули, налаштування книги, екран серії, EPUB, Store лише для читання, MCP `get_story`, сайт.

**Architecture:** обв'язка спирається на ядро як воно є (`storage/series.py`, `book/series.py`, `web/routes_series.py`, блок `series` у поданні твору). Нових механізмів пам'яті немає. Інтерфейс — окремі модулі `static/series-*.js` і шаблон `series.html` за зразком `story-mode.js` і `library.html`.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, ванільний JS-модулі, pytest, Playwright (`tests/web/browser/*.spec.mjs`).

**Spec:** `docs/superpowers/specs/2026-11/2026-11-14-series-design.md` (погоджена); ядро — `docs/superpowers/plans/2026-11/2026-11-14-series-core.md`, реєстр рішень — `.superpowers/sdd/2026-11-14-series-core/progress.md`.

## Global Constraints

- Довга проза лише у виданнях `full`/`paid`; у `store` екрана серій немає, записи серії відхиляються, книга з `series_id` — лише читання й експорт.
- Рядки преамбули: `Серія:`/`Series:`, `Номер:`/`Number:`, `Початок:`/`Start:`; вирізаються з плану; зайнятий номер чи нерозбірний рядок — попередження без полів серії, решта плану імпортується; номер самої книги не зайнятий.
- Знімок під час імпорту з преамбулою береться до імпорту файлу карток тієї самої партії.
- Оновлення знімка — з підтвердженням (діалог застосунку, `dialogs.js`), бо робить застарілою пам'ять перших сцен.
- EPUB/FB2/PDF: поля циклу з картки публікації; порожні — назва серії й номер.
- Переклади uk/en у `i18n.json`; сайт `docs/site/{uk,en}/` парами з `check_site.py --rehash`; знімки екрана лише на нейтральному прикладі.
- SPEC.MD SERIES-001 доповнюється S06/S07 і знімає «відомі обмеження» обв'язки.

## Review Focus

- Преамбула з `Серія:` нової назви: серія створюється; з наявною назвою іншого регістру — та сама серія.
- Партія «план + картки»: картки файлу, однойменні з картками знімка, пропускаються, а не дублюються.
- Книга серії в Store: читання й експорт працюють, будь-який запис — READ_ONLY_SERIES.
- Порожні поля циклу картки публікації: EPUB бере серію; заповнені — лишаються.
- Екран серії з книгою в кошику й книгою без `Початок`: книга в кошику позначена, книга без опори — поза віссю.

---

### Task 1: Імпорт преамбули

**Files:**
- Modify: `src/storygen/plan_sections.py` (`cut_series_lines(preamble) -> (text, SeriesLines | None, invalid: bool)`), `src/storygen/authoring/imports.py` (`import_sources`: перед циклом файлів — вхід у серію за першою преамбулою плану партії; `_plan` вирізає рядки з активного плану)
- Test: `tests/series/test_series_import.py`

**Interfaces:**
- Produces: `SeriesLines{title: str, number: int, start: SeriesStart | None}`; `parse_series_start(text) -> SeriesStart | None` (позначка STORY-TIME без години зі знаком через `memory/story_time.scene_moment` + перше число після неї — `anchor`).
- Consumes: ядро `find_series`, `create_series`, `set_story_series`.

- [ ] Step 1: тести — `test_preamble_puts_the_book_into_a_new_series` (номер 1, серію створено, рядків немає в `source_plan`), `test_preamble_with_existing_series_takes_the_snapshot_before_cards` (партія план+картки: картка «Анна» з файлу пропущена як дубль, ID картки знімка `A`), `test_taken_number_warns_and_imports_the_plan`, `test_unparsed_lines_warn`, `test_own_number_is_not_taken`, `test_store_edition_leaves_lines_in_the_plan` (без довгої прози рядки не розбираються).
- [ ] Step 2: RED. Step 3: реалізація. Step 4: `pytest tests/series tests/authoring -q` → PASS. Step 5: commit `feat(series): plan preamble import`.

### Task 2: Store лише для читання й MCP

**Files:**
- Modify: `src/storygen/web/long_prose_guard.py` (`blocked`: книга з `series_id` у виданні без довгої прози → `READ_ONLY_SERIES`), `src/storygen/book/guard.py` (`READ_ONLY_SERIES = 'Ця книга входить у серію; у цій збірці вона доступна лише для читання й експорту'`), `src/storygen/mcp/bridge.py` (`get_story` → `series: {title, number, start, status}` або `None`)
- Test: `tests/series/test_series_edition.py`

- [ ] Step 1: тести — `test_store_opens_a_series_book_read_only` (GET і експорт 200, PATCH сцени й запуск — 400 з текстом), `test_mcp_get_story_reports_the_series`, `test_mcp_story_outside_series_has_no_series`.
- [ ] Step 2–4: RED → реалізація → `pytest tests/series tests/web/test_long_prose_guard*.py tests/mcp -q` PASS. Step 5: commit `feat(series): store read-only and MCP info`.

### Task 3: Експорт

**Files:**
- Modify: `src/storygen/publication/book.py` або місце збирання `book.snapshot.publication.card` (заповнення `cycle_title`/`cycle_number` з серії за порожніх полів)
- Test: `tests/series/test_series_export.py`

- [ ] Step 1: тести — `test_epub_takes_the_series_when_cycle_is_empty`, `test_card_cycle_wins_over_the_series`, `test_fb2_sequence_from_series`.
- [ ] Step 2–4: RED → реалізація → PASS. Step 5: commit `feat(series): export cycle from the series`.

### Task 4: Налаштування книги

**Files:**
- Create: `src/storygen/web/static/series-settings.js`
- Modify: `src/storygen/web/templates/settings.html` (форма `#story-series-form` у розділі «writing»: серія — список наявних + «Нова серія…», номер, початок; кнопка «Зберегти»; блок стану й «Оновити з попередньої книги»), `src/storygen/web/static/i18n.json`
- Test: `tests/web/test_series_ui.py` (статичні перевірки шаблону/модуля, як `test_book_structure_ui.py`), `tests/web/browser/series.spec.mjs`

- [ ] Step 1: тести — форма є лише за довгої прози; модуль надсилає `PATCH /api/stories/{id}/series` з `expected_revision`; оновлення — через `confirmDialog` з `confirm: true`; переклади uk/en повні.
- [ ] Step 2–4: RED → реалізація → PASS. Step 5: commit `feat(series): book settings`.

### Task 5: Екран серій

**Files:**
- Create: `src/storygen/web/templates/series.html`, `src/storygen/web/static/series-page.js`, `src/storygen/web/static/series-axis.js` (чиста функція `axisLayout(books) -> {placed, outside}` за `Початок`: книги з однією точкою відліку на осі, без опори чи з іншою — поза віссю)
- Modify: `src/storygen/web/routes_series.py` (`GET /series` — список, `GET /series/{id}` — екран; `GET /api/series/{id}` — книги з номером, назвою, кошиком і станом), `library.html` (посилання «Серії» лише за довгої прози), заголовок книги серії в `story.html` (назва серії, номер, попередження)
- Test: `tests/series/test_series_screen.py`, `tests/web/browser/series.spec.mjs`

- [ ] Step 1: тести — `test_series_api_lists_books_with_status_and_trash`, `test_series_pages_absent_in_store`, `axisLayout` (node-тест у Playwright-файлі або pytest через `node --test`, як у наявних модулях), браузер: два порядки, стан, «Нова книга серії», «Оновити з попередньої книги» з попередженням.
- [ ] Step 2–4: RED → реалізація → PASS. Step 5: commit `feat(series): series screen`.

### Task 6: Сайт, SPEC, traceability, журнал

**Files:**
- Create: `docs/site/{uk,en}/series.md` (+ запис у `docs/site/site.json`), знімки екрана на нейтральному прикладі
- Modify: `SPEC.MD` (SERIES-001: S06, S07, зняти обмеження обв'язки), `docs/verification/traceability.json`, `docs/verification/manual.md` (`#series-browser`), `docs/superpowers/plans/2026-10-20-remediation-progress.md`, `docs/STATUS.md` (`verify.py`)

- [ ] Step 1: сторінки сайту uk/en, `python scripts/check_site.py --rehash series`.
- [ ] Step 2: SPEC/traceability → `python scripts/check_docs.py` OK.
- [ ] Step 3: повний `pytest -q` і Playwright `series.spec.mjs` → зелено; `python scripts/verify.py` → STATUS.md.
- [ ] Step 4: commit `docs(series): site, spec and traceability — harness`.

## Відхилення під час виконання

- Task 5: окремого `series-axis.js` з `axisLayout` немає. Вісь обчислює сервер (`book/series.chronology`), а `GET /api/series/{id}` віддає `placed`/`outside`; одна реалізація правила хронології замість двох. Перевірки — pytest `tests/series/test_series_screen.py`.
- Task 5: позначка приквела (`SeriesStatus.prequel`) додана за специфікацією, хоча план її не мав.
