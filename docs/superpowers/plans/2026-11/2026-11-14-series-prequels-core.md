# Серії 4б: приквели — план ядра

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Стартова пам’ять книги серії з кількох книг (основна книга + приквели), знімок приквела з позначками «минуле/майбутнє» і секція майбутнього в запитах письма.

**Architecture:** Одна функція `start_memory` будує стартову пам’ять злиттям підсумків джерел (`plan_merge` з порожньою основою, конфлікт — на користь найпізнішої за хронологією книги). Знімок `series_start` зберігає список джерел, розв’язані конфлікти, а для приквела — позначки, журнал «минулого» й тексти «майбутнього». Секція майбутнього береться з поточного знімка книги; нової залежності немає.

**Tech Stack:** Python 3.12, FastAPI, pydantic, pytest.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-14-series-prequels-design.md` (затверджено 14.11.2026); база — SERIES-001 у SPEC.MD і спека 4а.

## Global Constraints

- Книга поза серією й послідовна серія без приквелів дають ті самі запити, відбитки й знімки, що до 4б (інваріант SERIES-S05).
- Знімки 4а лишаються чинними; жодна версія не стає застарілою сама, без дії автора.
- Міграції бази немає: нові дані — лише в JSON версії `series_start`.
- Тексти для автора — українською, з ключами uk/en в `i18n.json`, якщо їх показує інтерфейс; приклади в тестах нейтральні.
- Записи без автора не змінюються: позначки зберігаються лише з `confirm: true`.
- Store: `require_long_prose()` на кожному новому записувальному маршруті.

## Review Focus

1. Приквел, що сам є джерелом приквела («приквел до приквела»): переможець конфлікту — пізніший у хронології приквел (тест у Task 2).
2. Книга в кошику серед джерел або як основна книга: не джерело, наступна найближча не-приквел книга стає основною (тест у Task 1).
3. Знімок 4а книги після приквела (одиночні поля `source_*`): читається як список з одного джерела й дає `source_changed`, а не помилку (тест у Task 2).
4. Позначка для ключа, якого вже немає після оновлення: відкидається під час перенесення, нові ключі — `future` (тест у Task 3).
5. Сцена приквела без героїв: секція майбутнього має записи без героїв і не падає; ліміт обрізає з приміткою (тест у Task 4).

---

### Task 1: Приквел за віссю й джерела стартової пам’яті

**Files:**
- Modify: `src/storygen/book/series.py` (`chronology`, `is_prequel`, нові `chronology_moments`, `prequel_ids`, `start_sources`; `series_status` прапорець `prequel`)
- Test: `tests/series/test_series_sources.py`

**Interfaces:**
- Produces:
  - `chronology_moments(books) -> dict[str, tuple[int, int, int]]` — моменти книг на осі (ID → (рік, місяць, день)); `chronology` будується на ній без зміни результату.
  - `prequel_ids(books) -> set[str]` — книги не в кошику на осі, чий момент раніший за момент якоїсь книги не в кошику з меншим номером.
  - `start_sources(stories, story) -> list[Story]` — основна книга (найближча попередня не в кошику й не приквел) і приквели між нею й книгою, у порядку номерів; `[]` поза серією чи для першої книги.
  - `is_prequel(books, story) -> bool` замінює `is_prequel(start)`; `SeriesStatus.prequel` бере нове визначення.

- [ ] **Step 1: Тести** у `tests/series/test_series_sources.py` (книги через `store.set_story_series` з `SeriesStart`, як у `tests/series/test_series_screen.py::book`):
  - `test_prequel_is_earlier_on_the_axis_than_a_smaller_number` — 1 (без `Початок`), 2 (`Рік -10, опора 1`), 3 (`Рік 2, опора 1`), 4 (`Рік 1, опора 1`): `prequel_ids == {2, 4}` (4 раніша за 3).
  - `test_book_off_the_axis_is_not_a_prequel` — 2 з опорою 5 (більший номер): не приквел.
  - `test_sources_are_the_main_book_and_prequels_between` — 1, 2 (приквел), 3: `start_sources(3) == [1, 2]`; `start_sources(2) == [1]`; `start_sources(1) == []`.
  - `test_trashed_main_book_moves_to_the_previous_one` — 1, 2, 3 (приквел до 2), 4; 2 у кошику: `start_sources(4) == [1, 3]`.
  - `test_prequel_of_a_prequel_sources` — 1, 2 (`Рік -10, опора 1`), 3 (`Рік -20, опора 1`): `start_sources(3) == [1, 2]`.
- [ ] **Step 2: Запустити** `pytest tests/series/test_series_sources.py -q` — FAIL (імена не визначені).
- [ ] **Step 3: Реалізувати.** `chronology_moments` — тіло нинішньої `chronology` до сортування; `chronology` = сортування `chronology_moments`. `is_prequel(books, story)` = `story.id in prequel_ids(books)`. Оновити виклик у `series_status` (передає `repo.list_stories(include_trashed=True)` книги серії). `tests/series/test_series_screen.py::test_a_book_with_a_negative_start_is_marked_as_a_prequel` має лишитися зеленим.
- [ ] **Step 4: Запустити** `pytest tests/series -q` — PASS.
- [ ] **Step 5: Commit** `feat(series): prequels by the axis and the sources of the start memory`.

### Task 2: Стартова пам’ять із кількох книг

**Files:**
- Modify: `src/storygen/book/series.py` (нові `StartMemory`, `start_memory`; `_snapshot_status` на список джерел)
- Modify: `src/storygen/memory/series_start.py` (`read_series_start` → `sources` зі старих полів; `SERIES_START_SCHEMA` лишається 1, нові поля необов’язкові)
- Modify: `src/storygen/storage/series.py` (`_snapshot`, `refresh_snapshot`, `_copy_cards` по джерелах)
- Test: `tests/series/test_series_prequel_merge.py`

**Interfaces:**
- Consumes: `start_sources`, `chronology_moments` (Task 1); `plan_merge`, `replay_memory` (`memory/merge.py`, `memory/journal.py`); `summary_journal`, `book_summary`.
- Produces:
  - `@dataclass StartMemory: journal: MemoryJournal; texts: dict[str, str]; sources: list[dict]; resolved: list[dict]; missing: Story | None` — `sources[i] = {story_id, summary_version_id, summary_sha256, characters_version_id, characters_sha256, card_hashes}`; `resolved[i] = {key, kept_story_id, dropped: [{story_id, text}]}`; `missing` — перше джерело без підсумку (тоді `journal` порожній).
  - `start_memory(repo, story) -> StartMemory | None` — `None`, коли джерел немає.
  - `read_series_start(...).source['sources']` — завжди список (знімок 4а: одиночні `source_*` → один елемент; `card_hashes` з `source_card_hashes`).
  - Події злиття: B першим; конфлікт → події журналу джерела з найпізнішим моментом (`chronology_moments`; без моменту чи за рівності — більший номер); у злитому журналі події взятих гілок у порядку `plan.clean` + переможці, як `build_merged_journal` (без author-подій).

- [ ] **Step 1: Тести** у `tests/series/test_series_prequel_merge.py` (на `finished_book` з `tests/series/helpers.py`; приквел — `finished_book` з `Рік -10, опора 1`, що має копію запису книги 1 зі зміненим станом героя через свою пам’ять, і новий факт):
  - `test_book_after_prequel_merges_main_book_and_prequel` — книга 3: журнал знімка має факт книги 1 один раз, новий факт приквела, стан героя з книги 1; `resolved == [{'key': 'slot:A:clothing', 'kept_story_id': book1, 'dropped': [{'story_id': prequel, 'text': …}]}]`; `check_integrity(repo.root).ok`.
  - `test_prequel_without_summary_blocks_the_snapshot` — приквел без пам’яті останньої сцени: `start_memory(...).missing.id == prequel`; `take_snapshot_if_ready` лишає книгу 3 без знімка; `series_status(...).state == 'no_summary'` і `source_story_id == prequel`.
  - `test_prequel_of_a_prequel_conflict_takes_the_later_prequel` — 1, 2 (`Рік -10`), 3 (`Рік -20`), 4: конфлікт між приквелами 2 і 3 → переможець 2.
  - `test_series_4a_snapshot_reads_as_one_source` — знімок, збережений із payload 4а (одиночні поля), читається з `sources` довжиною 1; поява приквела між джерелом і книгою → `source_changed`.
  - `test_sequential_series_snapshot_is_unchanged` — серія 1, 2 без приквелів: журнал і текст знімка книги 2 дорівнюють побудованим `inherit_journal` з підсумку книги 1 (як у 4а).
  - `test_cards_come_from_main_book_then_prequels` — картка лише в приквелі додається в книгу 3; картка B не перезаписується карткою приквела з тим самим ID.
- [ ] **Step 2: Запустити** `pytest tests/series/test_series_prequel_merge.py -q` — FAIL.
- [ ] **Step 3: Реалізувати** `start_memory` (порядок гілок — `start_sources`; один журнал — без `plan_merge`, як у 4а); `_snapshot` пише `sources` і `resolved` (старі одиночні поля більше не пишуться); `_copy_cards` викликається по джерелах у порядку `start_sources` з `refuse` першого знімка; `refresh_snapshot` рахує `CARD_CHANGED` по всіх джерелах; `_snapshot_status` порівнює набір і відбитки джерел, `resolved` повертає в `SeriesStatus` (нове поле `resolved: list = field(default_factory=list)`).
- [ ] **Step 4: Запустити** `pytest tests/series -q` — PASS.
- [ ] **Step 5: Commit** `feat(series): start memory from the main book and prequels`.

### Task 3: Знімок приквела з позначками

**Files:**
- Modify: `src/storygen/storage/series.py` (`_snapshot` для приквела; нові `save_decisions`, `start_facts`)
- Modify: `src/storygen/memory/series_start.py` (`SeriesStartData` — поля `decisions: dict | None`, `future: list`)
- Modify: `src/storygen/book/series.py` (стан `prequel_review`)
- Modify: `src/storygen/web/routes_series.py` (`GET /api/stories/{id}/series/facts`, `PUT /api/stories/{id}/series/decisions`)
- Modify: `src/storygen/web/long_prose_guard.py` (нові маршрути в `ALLOWED`, як маршрут refresh)
- Test: `tests/series/test_series_decisions.py`

**Interfaces:**
- Consumes: `start_memory` (Task 2); `memory.merge._key`.
- Produces:
  - payload `series_start` приквела: `decisions: {key: 'past'|'future'}` (усі ключі стартової пам’яті), `future: [{key, category, text, character_ids}]`, `journal` — події ключів `past` з повним ланцюжком.
  - `start_facts(repo, story_id) -> list[dict]` — `{key, category, text, character_ids, story_id, decision}` у порядку категорій `facts, character_states, open_threads, timeline`, далі тексту; `ValueError(NO_SNAPSHOT)` без знімка.
  - `save_decisions(repo, story_id, decisions: dict[str, str], expected_revision: int) -> Story` — нова версія `series_start` з тими самими `sources`, `resolved` і новими позначками; `ValueError(UNKNOWN_KEYS)` для ключа поза стартовою пам’яттю; значення лише `past`/`future`.
  - `SeriesStatus.state == 'prequel_review'` — приквел зі знімком без `decisions`.
  - HTTP: `PUT` без `confirm: true` — 422 з `DECISIONS_CONFIRM`; `RevisionConflict` — 409; Store — відмова `require_long_prose`.

- [ ] **Step 1: Тести** у `tests/series/test_series_decisions.py`:
  - `test_first_prequel_snapshot_is_all_future` — журнал знімка без подій, `future` має усі записи, `decisions` — усі `future`.
  - `test_saving_past_moves_the_record_chain_into_memory` — позначити стан героя `past`: журнал має його події (add і update), `future` його не має; пам’ять і завдання першої сцени приквела стали застарілими.
  - `test_decisions_need_confirmation_and_known_keys` — HTTP без `confirm` → 422; невідомий ключ → 422; застаріла ревізія → 409.
  - `test_refresh_carries_decisions_and_defaults_new_keys` — після нового запису в книзі 1 і оновлення: старі позначки збережено, новий ключ `future`, зниклий ключ відкинуто.
  - `test_series_4a_prequel_snapshot_is_all_past` — знімок без `decisions`: журнал не змінюється, `start_facts` дає `past` для всіх, стан `prequel_review`.
  - `test_store_refuses_decisions` (фікстура `store_edition`) — `PUT` відхиляється.
- [ ] **Step 2: Запустити** `pytest tests/series/test_series_decisions.py -q` — FAIL.
- [ ] **Step 3: Реалізувати.** Для приквела `_snapshot` фільтрує події `start_memory.journal` за ключами `past` (позначки: передані → перенесені зі старого знімка → `future`), `future` — `replay_memory` решти ключів; текст знімка — лише цитати подій журналу. Перший знімок і `take_snapshot_if_ready` — усі `future`. Переконатися, що порожній журнал проходить `check_integrity` і `scene_series_start`.
- [ ] **Step 4: Запустити** `pytest tests/series tests/storage -q` — PASS.
- [ ] **Step 5: Commit** `feat(series): prequel snapshot with past and future decisions`.

### Task 4: Секція майбутнього

**Files:**
- Create: `src/storygen/memory/future.py`
- Modify: `src/storygen/generation/context.py` (секція перед пам’яттю для `brief`, `draft`, `edit`, `rewrite`)
- Modify: `src/storygen/generation/context_labels.py` (`future_facts`, `future_more`)
- Modify: `src/storygen/application/writing_context.py` (поле `future`)
- Test: `tests/series/test_series_future.py`

**Interfaces:**
- Consumes: `read_series_start(...).future` (Task 3); `memory/selection.mentions`, `name_stems`.
- Produces:
  - `future_lines(future: list[dict], cast: set[str], names: dict[str, str], limit: int) -> tuple[list[str], int]` — рядки й кількість відкинутих: спершу стани героїв сцени, далі факти й лінії, що згадують героїв, далі записи без героїв; усередині — категорія, текст.
  - `future_section(repo, story, scene, language, limit) -> str | None` — `None`, якщо книга не приквел зі знімком або `future` порожнє.
  - Ліміт — `settings.max_input_chars // 8` (у моделі немає фіксованого бюджету пам’яті: його підбирає бінарний пошук; ruling у реєстрі).
  - `writing_context(...)['future']` — `list[str]`; входить у `context_fingerprint` (через `_content`).

- [ ] **Step 1: Тести** у `tests/series/test_series_future.py`:
  - `test_brief_and_draft_of_a_prequel_get_the_future_section` — заголовок мітки `future_facts` і рядок стану героя сцени є в `build_context(..., 'brief')` і `'draft'`; рядка «минулого» немає.
  - `test_memory_stage_has_no_future_section`.
  - `test_limit_trims_with_a_note` — `future_lines` з малим лімітом відкидає записи без героїв першими й повертає кількість; секція має примітку `future_more`.
  - `test_scene_without_cast_gets_records_without_heroes`.
  - `test_writing_context_future_changes_the_fingerprint` — збереження позначок змінює `context_fingerprint` сцени приквела.
  - `test_sequential_series_requests_are_unchanged` — у серії без приквелів запит `draft` книги 2 не має мітки `future_facts` і збігається з запитом без 4б (порівняння з еталоном, побудованим до зміни: зберегти текст запиту в тесті через `build_context` до Step 3 і перевірити, що Step 3 його не змінив).
- [ ] **Step 2: Запустити** `pytest tests/series/test_series_future.py -q` — FAIL.
- [ ] **Step 3: Реалізувати** `memory/future.py`; у `build_context` додати секцію після `ending_goal`/горизонту й до `memory_header` лише для `stage in {'brief','draft','edit','rewrite'}`; ref на знімок уже є в 4а.
- [ ] **Step 4: Запустити** `pytest tests/series tests/generation tests/mcp -q` — PASS.
- [ ] **Step 5: Commit** `feat(series): future section for prequel scenes`.

### Task 5: SPEC, traceability, журнал

**Files:**
- Modify: `SPEC.MD` (SERIES-001: опис 4б, S08–S10, «Відомі обмеження» — інтерфейс приквела в обв’язці)
- Modify: `docs/verification/traceability.json`
- Modify: `docs/superpowers/plans/2026-10-20-remediation-progress.md`
- Test: `tests/series/test_series_invariance.py` (розширити на послідовну серію)

- [ ] **Step 1: Тест** `test_sequential_series_is_unchanged` у `tests/series/test_series_invariance.py` — знімок книги 2 у серії без приквелів має `sources` довжини 1 і ті самі журнал і текст, що в 4а; селектори першої сцени ті самі.
- [ ] **Step 2: Запустити** — PASS після Tasks 2–4 (мутація: зробити `resolved` непорожнім завжди → тест падає; повернути).
- [ ] **Step 3: SPEC.MD** — до SERIES-001 додати вимогу приквела (MUST/SHALL з розділу власника спеки), технічний опис `start_memory`, позначок і секції майбутнього, Scenario S08–S10 з ID; «Відомі обмеження»: екран перегляду фактів і позначки на екрані серії — обв’язка (S11). Traceability S08–S10 з тестами Tasks 1–4. Запис у журналі.
- [ ] **Step 4: Запустити** `python scripts/check_docs.py` — «узгоджені»; `pytest tests/series -q` — PASS.
- [ ] **Step 5: Commit** `docs(series): SERIES-001 prequels core in SPEC and traceability`.
