# Серія й послідовні книги (4а), ядро — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Серія як сутність, поля книги, знімок старту («сцена 0» пам'яті й копія карток), попередник перших сцен, попередження й оновлення знімка — через HTTP, без екрана серії.

**Architecture:** Таблиця `series` (міграція 006) і поля `Story`. Знімок — версія твору `series_start`: текст усіх цитат журналу підсумку джерела й JSON з успадкованим журналом (джерело — маркер `series:start`), відбитками джерела й хешами карток. Для пам'яті книги він — джерело на позиції 0, «сцена 0»: споживачі номерів сцен дають йому номер 0. Сцена без предків бере його журнал; її знімки мають селектор `scene/<id>/series_start`.

**Tech Stack:** Python 3.12, FastAPI, SQLite, pydantic, pytest.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-14-series-design.md` (затверджено 2026-11-14). Обв'язка (імпорт преамбули, налаштування й екран серії, експорт, Store лише для читання, MCP `get_story`, сайт) — окремий план після рев'ю ядра.

## Global Constraints

- Книга поза серією дає ті самі запити, відбитки й знімки, що до 4а: жодного нового селектора, поля в запиті чи посилання (SERIES-S05).
- Знімок робиться сам лише в момент входу книги в серію з `series_number > 1`, і лише якщо джерело має підсумок. Дописання чи зміна джерела нічого не змінює саме — лише попередження.
- Джерело — книга серії не в кошику з найбільшим номером, меншим за номер книги; без підсумку знімка немає (без перестрибування).
- Підсумок — злиття кінця книги (`book_end_heads` ≥ 2) або актуальна пам'ять останньої активної сцени; сцени без прози теж активні.
- `series_number` унікальний у серії серед усіх книг, зокрема в кошику; `series_id` і `series_number` ставляться й знімаються разом.
- Видання без довгої прози відхиляє створення, зміну й видалення серії та поля серії в `PATCH` твору (`NO_LONG_PROSE`).
- Тести — лише нейтральні приклади; жодних платних викликів моделей.
- SPEC.MD, traceability і журнал оновлюються в тому самому PR (Task 6).

## Review Focus

1. Друга й подальші сцени книги 2: перевірка префікса попередньої пам'яті (`memory/reuse.py`) з `series_start` на позиції 0 — етап пам'яті, ручна пам'ять, оновлення.
2. Злиття арок у книзі серії: спільна основа включає події знімка; злиття кінця книги 2 як підсумок для книги 3 містить джерело `series_start` книги 2 — знімок книги 3 переписує всі джерела на свій `series_start`.
3. Кошик: книга-джерело в кошику, книга серії в кошику, відновлення книги з зайнятим номером.
4. Старі знімки сцени 1 без селектора після появи, оновлення й зняття знімка (правило типового значення) — і відсутність хибної застарілості в книгах поза серією.
5. Картка з `from_scene` у джерелі, картка з власними правками в книзі 2, однойменна картка з іншим ID під час першого знімка й оновлення.

---

### Task 1: Серія й поля книги

**Files:**
- Create: `src/storygen/storage/migrations/006_series.sql`, `src/storygen/storage/series.py`, `src/storygen/series_models.py`, `src/storygen/web/routes_series.py`
- Modify: `src/storygen/storage/database.py` (`SCHEMA_VERSION=6`, крок міграції), `src/storygen/domain.py` (поля `Story`), `src/storygen/storage/repository.py` (обгортки), `src/storygen/web/app.py` (роутер), `src/storygen/web/routes_stories.py` (`PATCH /api/stories/{id}/series`)
- Test: `tests/series/test_series_entity.py`, `tests/series/__init__.py`

**Interfaces:**
- Produces:
  - `series_models.Series(id: str, revision: int, title: str, created_at: str)`; `SeriesStart(offset: str, anchor: int)` (offset — рядок позначки без години, зберігається як введено).
  - `Story.series_id: str | None`, `series_number: int | None`, `series_start: SeriesStart | None`, `series_start_version_id: str | None` (усі `None` за замовчуванням; JSON без цих ключів читається як раніше).
  - `storage.series`: `create_series(repo, title) -> Series`, `rename_series(repo, id, title, expected_revision) -> Series`, `delete_series(repo, id, expected_revision) -> None`, `list_series(repo) -> list[Series]`, `get_series(repo, id) -> Series`, `series_books(repo, id) -> list[Story]` (зокрема в кошику, за номером).
  - `storage.series.set_story_series(repo, story_id, series_id: str | None, number: int | None, start: SeriesStart | None, expected_revision) -> Story` — CAS; на вході в серію викликає `take_snapshot_if_ready` з Task 3 (до Task 3 — заглушка, що нічого не робить).
  - HTTP: `GET/POST /api/series`, `PATCH/DELETE /api/series/{id}` (`expected_revision`), `PATCH /api/stories/{id}/series`.
  - Повідомлення: `SERIES_TITLE_TAKEN='Серія з такою назвою вже є'`, `SERIES_NUMBER_TAKEN='Номер {number} у серії вже зайнятий'`, `SERIES_NOT_EMPTY='Серію можна видалити лише без книг, зокрема в кошику'`, `SERIES_PAIR='Серія й номер задаються разом'`.

- [ ] **Step 1: Write the failing tests** — `test_create_rename_delete_with_cas` (назва унікальна за `name_key`, `RevisionConflict` на старій ревізії), `test_delete_refuses_a_series_with_a_trashed_book`, `test_number_unique_including_trash` (`ValueError(SERIES_NUMBER_TAKEN.format(number=2))`), `test_series_and_number_go_together`, `test_story_json_without_series_keys_reads_as_before` (старий payload → поля `None`, `model_dump` без змін для байтової рівності знімків не потрібен — перевіряється в Task 6), `test_store_edition_refuses_series_edits` (`store_edition` fixture → 400 з `NO_LONG_PROSE` на `POST /api/series` і `PATCH /api/stories/{id}/series`), `test_migration_from_5_creates_the_table` (база з `user_version=5` → 6, таблиця `series`).
- [ ] **Step 2: Run** `pytest tests/series/test_series_entity.py -q` — Expected: FAIL (модулів немає).
- [ ] **Step 3: Implement** таблицю `series(id TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL)`, крок міграції за зразком 003, сховище за зразком `publication_store` (CAS на `revision`, `BEGIN IMMEDIATE`), `set_story_series` за зразком `book_structure._begin/_save`, роути з `require_long_prose()`.
- [ ] **Step 4: Run** `pytest tests/series/test_series_entity.py tests/storage -q` — Expected: PASS; `self_check` очікує схему 6.
- [ ] **Step 5: Commit** `feat(series): series entity and book fields`.

### Task 2: «Сцена 0» в пам'яті

**Files:**
- Create: `src/storygen/memory/series_start.py`
- Modify: `src/storygen/memory/journal.py` (`validate_memory_journal`), `src/storygen/storage/memory_checks.py`
- Test: `tests/series/test_series_journal.py`

**Interfaces:**
- Produces:
  - `SERIES_MARKER='series:start'`; `SERIES_START_SCHEMA=1`.
  - `inherit_journal(journal: MemoryJournal, texts: dict[str, str]) -> tuple[str, MemoryJournal]` — текст (усі `quote`, `supporting_quotes` і повні тексти версій з `evidence_version_id`, кожен блок окремим рядком, без повторів, у порядку подій) і журнал: ті самі події, у яких `source_version_id` і `evidence_version_id` (якщо він є) замінено на `SERIES_MARKER` — доказ лишається доказом, але вказує на знімок; `source_prose_ids=[SERIES_MARKER]`. `texts` — тексти джерел журналу.
  - `series_start_payload(text: str, journal: MemoryJournal, source: dict) -> str` — JSON версії (`schema_version`, `text`, `journal`, поля джерела зі специфікації).
  - `read_series_start(raw: str, version_id: str) -> SeriesStartData` — `text`, `journal` з маркером, заміненим на `version_id`, відбитки.
  - `source_number(version_ref, numbers: dict[str, int]) -> int` — `0` для `kind=='series_start'`, інакше `numbers[ref.scene_id]`.
- Consumes: `MemoryJournal`, `replay_memory`, `validate_memory_journal`.

- [ ] **Step 1: Write the failing tests** — `test_inherited_journal_keeps_kinds_quotes_and_ids` (prose-подія з двома `supporting_quotes`, author-слот без цитати, подія з `evidence_version_id`: ID записів і види ті самі, `replay_memory` дає ті самі записи за текстами), `test_inherited_quotes_are_in_the_text` (`validate_memory_journal(journal, {id: text})` проходить), `test_scene_journal_extends_series_start` (журнал сцени `[series_id, p1]` проходить `validate_memory_journal`), `test_integrity_accepts_series_start_only_at_position_0` (`check_memory_versions`: `series_start` на позиції 0 — без звіту; на позиції 1 або вид `memory` іншого твору — `invalid_memory`), `test_source_number_is_zero_for_series_start`.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement.** `validate_memory_journal` уже бере тексти за ID джерел — потрібно лише, щоб `check_memory_versions` приймав позицію 0 з `kind=='series_start'`, `scene_id is None`, тим самим твором; текст для перевірки — `read_series_start(...).text`; `owners` і порівняння з `snapshot.scene_order` — з позиції 1.
- [ ] **Step 4: Run** `pytest tests/series/test_series_journal.py tests/memory tests/storage -q` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(series): series start as scene 0 of memory`.

### Task 3: Підсумок книги й знімок

**Files:**
- Create: `src/storygen/book/series.py`
- Modify: `src/storygen/storage/series.py` (`take_snapshot`, `take_snapshot_if_ready`), `src/storygen/web/routes_series.py` (`POST /api/series/{id}/books`)
- Test: `tests/series/test_series_snapshot.py`, `tests/series/helpers.py`

**Interfaces:**
- Produces:
  - `book.series.source_book(stories: list[Story], story: Story) -> Story | None` — правило джерела.
  - `book.series.book_summary(view, story) -> tuple[str | None, str | None]` — `(version_id, reason)`: ID версії злиття кінця книги чи пам'яті останньої активної сцени; `reason` ∈ `SUMMARY_NEEDS_MERGE='потрібне злиття кінця книги'`, `SUMMARY_NO_MEMORY='остання сцена без актуальної пам’яті'`, `None`.
  - `storage.series.take_snapshot(repo, story_id, expected_revision) -> Story` — зберігає `source_characters`, `character_cards` (копія) і `series_start`, ставить `characters_version_id` і `series_start_version_id`. Відмови: `NO_SOURCE='Попередня книга ще не має підсумку'`, `CARD_NAME_CLASH='Картки з тими самими іменами вже є в книзі: {names}'`.
  - `take_snapshot_if_ready(repo, story_id)` — викликається з `set_story_series` і `POST /api/series/{id}/books` лише на вході в серію; тихо нічого не робить без підсумку.
  - `tests/series/helpers.py`: `finished_book(root, repo=None) -> (repo, story, scenes)` — книга 1 з двох сцен (`two_scenes` + пам'ять сцени 2), картка `A` з відомістю `from_scene`; `second_book(repo, series_id) -> Story` — книга 2 з однією сценою з прозою.
- Consumes: Task 1 (`set_story_series`), Task 2 (`inherit_journal`, `series_start_payload`), `merge_point(..., book_end=True)`, `usable_merge`, `read_previous_journal`.

- [ ] **Step 1: Write the failing tests** — `test_source_is_nearest_previous_not_in_trash`, `test_no_snapshot_without_a_summary_and_no_skip` (книга 2 без пам'яті останньої сцени → книга 3 без знімка, хоч книга 1 дописана), `test_unfinished_book_has_no_summary` (сцена плану без прози в кінці), `test_book_with_arcs_summary_is_the_book_end_merge`, `test_entering_the_series_takes_the_snapshot` (журнал `series_start` має записи книги 1 з тими самими ID; `characters_version_id` книги 2 — копія з ID `A`; `from_scene` → `timeless`; `check_character_versions` і `check_memory_versions` без звітів), `test_card_name_clash_refuses`, `test_finishing_the_source_later_takes_no_snapshot` (книга 2 увійшла без підсумку джерела; дописання книги 1 → `series_start_version_id` лишається `None`, жодна версія книги 2 не застаріла), `test_new_book_button_takes_the_snapshot`.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement.** Підсумок джерела читається через `ContextView` джерела; журнал злиття — `read_previous_journal` з `merge_key`. Якщо журнал підсумку сам починається з `series_start` (книга 3 від книги 2), його текст береться з `read_series_start(...).text`. Копія карток: тексти процитованих відомостей — блоки нової `source_characters`; цитати переписуються на неї.
- [ ] **Step 4: Run** `pytest tests/series -q` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(series): book summary and the start snapshot`.

### Task 4: Попередник, «сцена 0» в контексті й селектор

**Files:**
- Modify: `src/storygen/memory/previous.py`, `src/storygen/memory/reuse.py`, `src/storygen/generation/context.py` (рядки з `scene_numbers[...]`, ~262 і ~363), `src/storygen/memory/forwarding.py` (~85-89), `src/storygen/storage/snapshots.py` (селектор і `compare_snapshot`), `src/storygen/generation/dependencies.py` (`_manual_snapshot`), `src/storygen/storage/memory_checks.py` (якщо порівняння порядку не покрито в Task 2)
- Test: `tests/series/test_series_memory.py`

**Interfaces:**
- Produces:
  - `previous_memory(view, scene)` для сцени без предків книги з `series_start_version_id` → `PreviousMemory(<series_start id>, None, [])`; `read_previous_journal` читає журнал через `read_series_start`.
  - `memory.series_start.scene_series_start(story, scenes, scene) -> str | None` — ID знімка для сцени без предків, інакше `None`.
  - Селектор `scene/<id>/series_start` (`expected` — ID або `None`) і посилання на версію: у знімках етапів `memory`, `brief`, `draft`, `prose_edit`, `author_rewrite` сцени без предків книги з `series_id`. `selector_value` обчислює `scene_series_start`. `compare_snapshot` для цих етапів без селектора додає `expected=None` (значення поза серією — `None`, тож книги поза серією не застарівають).
- Ruling (план): селектор сценовий (`scene/<id>/series_start`), а не `story/<id>/series_start` зі специфікації — значення `None` для сцен із предками робить правило типового значення безпечним для всіх сцен.

- [ ] **Step 1: Write the failing tests** — `test_writer_of_the_first_scene_sees_the_hero_state_of_book_1` (`build_context(... 'brief')` містить стан «Халат»), `test_memory_stage_of_the_first_scene_extends_series_start` (виконаний етап пам'яті з фейковою відповіддю: `source_prose_ids[0]` = знімок), `test_second_scene_passes_the_prefix_check` (етап пам'яті й `memory_for_manual_edit` сцени 2), `test_timeline_of_book_1_leaves_the_window_after_20_scenes` і `test_hero_state_of_book_1_is_recent_in_the_first_scenes` (через `select_memory` з номерами від `source_number`), `test_refresh_or_leaving_stales_brief_draft_and_memory_of_scene_1`, `test_old_snapshot_without_the_selector_stales_after_a_snapshot_appears`, `test_book_outside_series_writes_no_series_selector`.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement.** Усі `scene_numbers[repo.get_version(id).scene_id]` → `source_number(repo.get_version(id), numbers)`. `reuse._candidate`: без предків, але зі знімком — журнал знімка, `sources={id: text}`; з предками — `journal.source_prose_ids[1:]` зіставляються з предками, якщо `[0]` — знімок книги. `forwarding`: версія доказу виду `series_start` — джерело «сцени 0».
- [ ] **Step 4: Run** `pytest tests/series tests/memory tests/generation -q` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(series): series start as the predecessor of first scenes`.

### Task 5: Стан знімка й оновлення

**Files:**
- Modify: `src/storygen/book/series.py` (`series_status`), `src/storygen/storage/series.py` (`refresh_snapshot`), `src/storygen/web/routes_stories.py` (блок `series` у поданні твору, `POST /api/stories/{id}/series/refresh`)
- Test: `tests/series/test_series_refresh.py`

**Interfaces:**
- Produces:
  - `series_status(view, story) -> SeriesStatus | None` (`None` поза серією): `state` ∈ `'fresh'`, `'source_changed'`, `'source_finished'`, `'no_summary'`, `'first'`; `source_story_id`; `changed_cards: list[str]` (ID карток, чий хеш у джерелі ≠ `source_card_hashes`).
  - Подання твору: `series: {id, title, number, start, status}` лише для книги серії.
  - `refresh_snapshot(repo, story_id, expected_revision) -> tuple[Story, list[str]]` — новий `series_start` з поточного підсумку; картки: додаються відсутні за ID і `name_key`; повертає попередження (однойменні, змінені).
- Consumes: Task 3 `take_snapshot` (без попереднього знімка оновлення = перший знімок).

- [ ] **Step 1: Write the failing tests** — `test_new_memory_of_book_1_warns_without_staling_book_2`, `test_card_change_in_source_is_listed_but_own_edits_are_not`, `test_source_finished_later_warns_and_refresh_takes_the_first_snapshot`, `test_trashed_or_renumbered_source_warns`, `test_refresh_adds_new_cards_and_skips_same_name`, `test_refresh_stales_scene_1_memory` (через Task 4 селектор).
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** стан під час читання (без запису), оновлення з CAS і підтвердженням `confirm: true` у тілі запиту.
- [ ] **Step 4: Run** `pytest tests/series -q` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(series): snapshot status and refresh`.

### Task 6: Незмінність, SPEC, traceability, журнал

**Files:**
- Create: `tests/series/test_series_invariance.py`
- Modify: `SPEC.MD` (нова вимога SERIES: технічний опис ядра, інваріанти, сумісність/міграція 006, відомі обмеження «обв'язка в наступному PR»; згадки в MEMORY-001 (джерело `series_start`), DATA (таблиця `series`), DEPENDENCY (селектор)), `docs/verification/traceability.json`, `docs/superpowers/plans/2026-10-20-remediation-progress.md`
- Test: усе вище

- [ ] **Step 1: Write the test** `test_book_outside_series_is_unchanged` — книги `two_scenes` і `arc_book` (A B A): запити, відбитки й знімки `brief`/`memory` без `series_start`; `compare_snapshot` старих знімків — без змін.
- [ ] **Step 2: Run** — Expected: PASS одразу (інваріант; мутація — тимчасово завжди додавати селектор → FAIL, перевірити й повернути).
- [ ] **Step 3:** SPEC.MD SERIES-S01…S05 (S06/S07 — у плані обв'язки) з ID; traceability; `python scripts/check_docs.py` → OK.
- [ ] **Step 4:** повний `pytest -q` у фоні → усе зелене.
- [ ] **Step 5: Commit** `docs(series): spec, traceability, journal — core`.
