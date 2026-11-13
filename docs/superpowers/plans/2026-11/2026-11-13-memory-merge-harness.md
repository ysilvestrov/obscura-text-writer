# Злиття пам'яті, обв'язка (проєкт 2, крок 3) — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** автор позначає сцену зустрічі в плані (`Арки: А, Б`) або в параметрах сцени, бачить у списку сцен зустрічі й точки, що чекають злиття, і підтверджує злиття у вікні на вкладці пам'яті; зупинений запуск після підтвердження продовжується; сайт описує нове.

**Architecture:** спирається на ядро (`docs/superpowers/plans/2026-11/2026-11-13-memory-merge-core.md`, коміти `382bfe6..8976d55`): `scene_arcs` зі списком для сцени зустрічі, `PUT …/arc` з `arc_ids`, `storage/memory_merges.py` (`merge_point`, `merge_state`, `usable_merge`, `save_merge`), `GET/PUT /api/stories/{id}/memory-merges`, причина готовності `memory_merge_required`. Рев'ю ядра знайшло дві речі, які обв'язка мусить закрити першою: `GET /api/stories/{id}` віддає сцені лише першу арку, тож панель «Структура книги» під час збереження мовчки прибирає решту арок сцени зустрічі; відоме обмеження MEMORY-MERGE про «запуск не продовжується» хибне — `RunCoordinator.resume` повертає в чергу `needs_review` з того самого етапу після перевірки готовності.

**Tech Stack:** Python 3.12, FastAPI, pytest, ванільний JS, node-тести, Playwright.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-12-parallel-arcs-design.md` — «Структура» (рядок `Арки:`, «Арки» в параметрах сцени), «Інтерфейс» (вікно злиття, позначки списку сцен), сценарій MEMORY-MERGE-S04; чинна SPEC.MD — BOOK-STRUCTURE, MEMORY-MERGE.

## Global Constraints

- Рядок `Арки: А, Б` / `Arcs: A, B` (регістр неважливий, після зняття Markdown, як `Арка:`) вирізається з плану сцени; назви — через кому або крапку з комою, порожні відкидаються, повтори зливаються, до 20 назв по 200 символів. Одна назва — звичайна арка, не зустріч. Розбір — лише у виданні з довгою прозою, інакше рядок лишається текстом.
- Наступна сцена без рядка після сцени зустрічі продовжує арку, що стояла перед зустріччю, якщо вона серед арок зустрічі, інакше першу з перелічених (як `book/structure.py::arc_after_meeting`).
- `arc_id` сцени в `GET /api/stories/{id}` лишається першою аркою (старі клієнти); нове поле `arc_ids` — усі арки сцени в порядку структури (один елемент для звичайної сцени, `[]` без арки).
- Вибір арок сцени — лише арки тієї самої частини; сервер усе одно перевіряє (`check_order`).
- Вікно злиття не стирає вибору автора після 409: стан перечитується, вибір конфліктів з тими самими ключем і значеннями лишається.
- Тексти інтерфейсу — `i18n.json` (uk/en); приклади в тестах і на сайті — нейтральні (без матеріалів із `data/`); сайт — пари `docs/site/{uk,en}/book-structure.md` і `docs/site/{uk,en}/memory.md`, підтверджені `check_site.py --rehash`.

## Review Focus

- Панель «Структура книги» в книзі зі сценою зустрічі: перейменування арки й «Зберегти» лишають сцену в обох арках; лічильник сцен арки рахує сцену зустрічі в кожній її арці (видалення такої арки відмовляє).
- Поле «Арка» сцени зустрічі: зміна основної арки на арку іншої частини знімає зустріч (одна арка), а не шле арки двох частин.
- Вікно злиття для точки зі станом `blocked` (у голови немає свіжої пам'яті): причина видна, кнопка підтвердження вимкнена, таблиці немає.
- Злиття кінця книги: вікно показується на вкладці пам'яті останньої активної сцени поряд із її власним станом (`not_needed`).
- Сцена після злиття, підтвердженого в іншій вкладці: позначка «потрібне злиття» зникає після `story-refreshed`, без перезавантаження.

---

### Task H1: усі арки сцени в API й панелі; продовження після злиття

**Files:**
- Modify: `src/storygen/web/routes_stories.py:103` (`arc_ids`), `src/storygen/mcp/bridge.py:230-236` (`arc_ids` у сценах `get_story`), `src/storygen/web/static/book-structure.js` (`createBuffer`, лічильник `used`), `SPEC.MD` (MEMORY-MERGE: відоме обмеження про продовження → чинна поведінка)
- Test: `tests/web/test_structure_api.py`, `tests/web/js/book_structure.mjs`, `tests/generation/test_merge_stop.py`

**Interfaces:**
- Consumes: `EffectiveStructure.arcs_of: dict[scene_id, tuple]` (ядро, Task 1).
- Produces: сцени `GET /api/stories/{id}` з `arc_ids: list[str]`; `createBuffer(book, scenes)` бере `scene.arc_ids` (запасний варіант — `[scene.arc_id]`), `buffer.scene_arcs[id]` — рядок для однієї арки, список для кількох; `buffer.used` рахує кожну арку сцени.

- [ ] **Step 1: тести:**
  - pytest `test_story_lists_all_arcs_of_a_meeting_scene` — книга `a1 b1 a+b` (`tests/memory/merge_helpers.py::arc_book`, частина `[['A','B']]`): сцена 3 має `arc_ids == ['A','B']`, `arc_id == 'A'`; сцена 1 — `['A']`;
  - node `createBuffer keeps meeting arcs in the payload` — `payload(createBuffer(book,[{id:'s3',arc_id:'A',arc_ids:['A','B']}]),1).scene_arcs.s3` дорівнює `['A','B']`; `remove(buffer,0,1)` для арки B → `'book.error.has_scenes'`;
  - pytest `test_resume_after_merge_runs_the_stopped_task` — як `test_run_stops_before_merge_scene`, далі `confirm(...)` злиття з поточною пам'яттю голів і `worker.resume(run.id)` → стан `queued`, `cursor` той самий; `worker._execute(run.id)` → провайдер викликано один раз.
- [ ] **Step 2:** запуск → FAIL (`arc_ids` відсутнє; payload з `'A'`; resume — PASS уже зараз, це тест-документація поведінки, не RED; зафіксувати в журналі).
- [ ] **Step 3:** реалізація; SPEC.MD MEMORY-MERGE «Відомі обмеження»: замінити речення про те, що запуск не продовжується, на «Запуск, зупинений перед точкою злиття, продовжується кнопкою «Продовжити» після підтвердження (`RunCoordinator.resume` перевіряє готовність і повертає той самий етап у чергу); «Продовжити після прийнятого етапу» відмовляє, бо зупинений етап не має результату». Технічний опис BOOK-STRUCTURE (API): `arc_ids` сцени; MCP `get_story` — `arc_ids`.
- [ ] **Step 4:** `pytest tests/web/test_structure_api.py tests/generation/test_merge_stop.py tests/mcp -q` і `pytest tests/web/test_book_structure_ui.py -q` (запускає `node tests/web/js/book_structure.mjs <root>`) → PASS.
- [ ] **Step 5:** коміт `fix(book): keep every arc of a meeting scene in the API and the structure panel` (у тілі — усунене відхилення й виправлене обмеження SPEC).

### Task H2: рядок `Арки:` в імпорті

**Files:**
- Modify: `src/storygen/plan_sections.py` (`ARCS_LINE`, `BookSection.arc_titles`, `_cut_arc_lines`, `split_book_plan`), `src/storygen/import_models.py` (`ImportedScene.arc_titles`), `src/storygen/authoring/imports.py:107`, `src/storygen/storage/import_store.py:82`, `src/storygen/storage/book_structure.py::place_imported`
- Test: `tests/authoring/test_import_meeting.py`

**Interfaces:**
- Produces:
  - `ARCS_LINE = re.compile(r'^(?:арки|arcs)\s*:\s*(.*)$', re.IGNORECASE)`;
  - `BookSection.arc_titles: tuple[str, ...] | None = None` — дві й більше назви для сцени зустрічі; тоді `arc_title` — арка, яку продовжує наступна сцена без рядка (правило з Global Constraints);
  - `ImportedScene.arc_titles: list[str] | None = Field(default=None, max_length=20)`;
  - елемент `created` у `place_imported` отримує шостий член `arc_titles`; сцена з ним прив'язується до списку арок поточної частини (знайдених за назвою або створених у порядку переліку) через `canonical_arcs`.

- [ ] **Step 1: тести:**
  - `test_arcs_line_makes_a_meeting_scene` — план `# Частина 1` / сцени з `Арка: Дорога`, `Арка: Місто`, `**Арки:** Дорога; Місто` → третя сцена в обох арках, у тексті плану рядка немає;
  - `test_scene_after_meeting_returns_to_the_arc_before_it` — `Арка: Місто`, `Арки: Дорога, Місто`, сцена без рядка → вона в «Місто»;
  - `test_scene_after_meeting_takes_the_first_listed_arc` — `Арка: Ліс`, `Арки: Дорога, Місто`, сцена без рядка → «Дорога»;
  - `test_single_title_in_arcs_line_is_one_arc` — `Арки: Дорога` → `scene_arcs` — рядок;
  - `test_edition_without_long_prose_keeps_the_arcs_line` — видання store: рядок лишається в beats.
- [ ] **Step 2:** запуск → FAIL.
- [ ] **Step 3:** реалізація; `ARC_LINE` не чіпати (`арки:` і `arcs:` під нього не підпадають — перевірити тестом).
- [ ] **Step 4:** `pytest tests/authoring tests/storage -q` → PASS.
- [ ] **Step 5:** коміт `feat(book): import meeting scenes from the Arcs line`.

### Task H3: кілька арок у параметрах сцени

**Files:**
- Modify: `src/storygen/web/static/book-structure.js` (`meetingOptions`), `src/storygen/web/static/book-structure-ui.js` (`arcField`), `src/storygen/web/static/i18n.json` (`book.scene_meeting`, `book.scene_meeting_hint`), `tests/web/browser/server.py` (фікстура `POST /test-arc-book` на `arc_book`)
- Test: `tests/web/js/book_structure.mjs`, `tests/web/browser/book-structure.spec.mjs`

**Interfaces:**
- Consumes: `arc_ids` сцени (H1); `PUT /api/stories/{id}/scenes/{scene_id}/arc` з `arc_id` або `arc_ids` (ядро).
- Produces: `meetingOptions(book, arcIds, label) -> [{value, label, checked}]` — інші арки частини першої арки `arcIds`, у порядку структури; `[]`, якщо в частині одна арка.

- [ ] **Step 1: тести:** node — `meetingOptions` для `['A','B']` у частині `[A,B,C]` → `B` checked, `C` ні, `A` відсутня; арка в частині сама → `[]`. Playwright (фікстура `a1 b1 a2` з однією частиною `[A,B]`): `meeting arcs are ticked and saved` — у сцени 3 позначити «B» у групі «Сцена зустрічі з арками» → повідомлення збереження, перезавантаження, позначка лишилась; зміна основної арки → група перебудована, зустріч знята.
- [ ] **Step 2:** запуск → FAIL.
- [ ] **Step 3:** під полем «Арка» — `fieldset` з `legend` «Сцена зустрічі з арками» і прапорцями `meetingOptions`; прапорець шле `arc_ids = [основна, ...позначені]`, зміна основної арки шле `arc_id` (зустріч знімається); відмова сервера повертає показаний стан.
- [ ] **Step 4:** node (через pytest-обгортку) і `npx playwright test -c frontend/playwright.config.mjs book-structure.spec.mjs` (з `PYTHONPATH=<worktree>/src`) → PASS.
- [ ] **Step 5:** коміт `feat(book): meeting arcs in the scene parameters`.

### Task H4: позначки сцени зустрічі й потрібного злиття в списку сцен

**Files:**
- Modify: `src/storygen/storage/memory_merges.py` (`merge_markers`), `src/storygen/web/routes_stories.py` (`memory_merge` сцени), `src/storygen/web/static/book-structure.js` (`groupScenes`: `meeting`, `merge`), `src/storygen/web/static/editor.js:104-128` (значки), стилі, `i18n.json` (`book.badge.meeting`, `book.badge.merge`)
- Test: `tests/storage/test_memory_merges.py`, `tests/web/js/book_structure.mjs`

**Interfaces:**
- Produces: `merge_markers(view, story, scenes) -> {scene_id: 'required' | 'fresh'}` — лише цільові сцени точок злиття (один `lineage_map`); сцени `GET /api/stories/{id}` мають `memory_merge: 'required' | 'fresh' | null`; рядки `groupScenes` типу `scene` мають `meeting: bool` (`arc_ids.length > 1`) і `merge`.

- [ ] **Step 1: тести:** pytest `test_merge_markers_follow_the_merge` — `meeting_book`: сцена 4 `required`, після `save_merge` — `fresh`, інші сцени відсутні; node — `groupScenes` дає `meeting` і `merge` у рядку сцени зустрічі.
- [ ] **Step 2:** запуск → FAIL.
- [ ] **Step 3:** назва сцени в кнопці — окремий `span` (локалізація `uiText` не стирає значків); значки `span.scene-badge` з `aria-label`; виділення активної сцени (`editor.js:128`) лишається за номером.
- [ ] **Step 4:** `pytest tests/storage/test_memory_merges.py -q`, node і наявні Playwright списку сцен (`book-structure.spec.mjs`, `collapsible-scenes.spec.mjs`) → PASS.
- [ ] **Step 5:** коміт `feat(book): meeting and merge badges in the scene list`.

### Task H5: вікно «Злиття пам'яті» (MEMORY-MERGE-S04)

**Files:**
- Create: `src/storygen/web/static/memory-merge.js` (чисті функції), `src/storygen/web/static/memory-merge-panel.js` (секція `#memory-merge` у `#memory-view`), `tests/web/js/memory_merge.mjs` з pytest-обгорткою `tests/web/test_memory_merge_ui.py` (як `test_book_structure_ui.py`), `tests/web/browser/memory-merge.spec.mjs`
- Modify: `src/storygen/web/templates/story.html` (модуль), `src/storygen/web/static/runs.js` (кнопка «Відкрити злиття пам'яті»), `src/storygen/web/static/i18n.json` (`merge.*`), `tests/web/browser/server.py` (фікстура `POST /test-memory-merge` на `meeting_book`)

**Interfaces:**
- Consumes: `GET …/memory-merges?scene_id=|point=book_end`, `PUT …/memory-merges/{key}` (ядро); `reason_code='memory_merge_required'` у готовності сцени й продовження запуску (ядро; `pending_preview` передає `preview`).
- Produces:
  - `mergeRows(state) -> [{key, label, values:[{headId, title, value}], choice, text, carried}]` — `choice`/`text` з `state.carried`;
  - `keepChoices(oldRows, newRows) -> newRows` — переносить `choice`/`text` рядків з тим самим `key` і тими самими `values`;
  - `decisionsPayload(rows) -> {key: {choice} | {choice:'author', text}}`;
  - `confirmReason(state, rows) -> '' | i18n-ключ` (`merge.reason.blocked`, `merge.reason.undecided`).

- [ ] **Step 1: тести:** node — `mergeRows` з `carried`; `keepChoices` після зміни значення голови не переносить вибір, за тих самих значень — переносить; `decisionsPayload` для власного значення; `confirmReason` для `blocked` і нерозв'язаного конфлікту. Playwright (`memory-merge.spec.mjs`, нейтральний приклад «Анна в куртці»/«Анна в плащі»): `the merge window lists heads and the conflict` (дві голови з назвами арок, рядок конфлікту з двома значеннями); `choosing a head confirms the merge` → повідомлення, стан «актуальне»; `an author value is saved`; `a revision conflict keeps the choice` (зміна ревізії через інший запит до натискання → 409, повідомлення, вибір лишився, повторне натискання проходить); `a stopped run opens the merge` (готовність сцени з `memory_merge_required` показує кнопку, вона відкриває вкладку пам'яті з `#memory-merge`).
- [ ] **Step 2:** запуск → FAIL.
- [ ] **Step 3:** секція: заголовок, стан (`none`/`fresh`/`stale`/`blocked` + причина), голови (номер, назва, арки), таблиця конфліктів (значення кожної голови — перемикач; «Своє значення» — перемикач і поле до 4000 символів), позначка «перенесено з попереднього злиття», кнопка «Підтвердити злиття» з `expected_revision` і `expected_head_memory_ids`; на 409 — повідомлення, перечитування й `keepChoices`. Для останньої активної сцени додатково запит `point=book_end`, якщо точка є. Кнопка в `runs.js`: для поточної сцени — `invokeWorkspaceCommand('show','memory')` і фокус на секції, для іншої — перехід за `sceneUrl(scene,'memory')`.
- [ ] **Step 4:** node (через pytest-обгортку) і `npx playwright test -c frontend/playwright.config.mjs memory-merge.spec.mjs` (desktop і mobile) → PASS.
- [ ] **Step 5:** коміт `feat(memory): merge window in the memory panel`.

### Task H6: SPEC, traceability, сайт

- [ ] SPEC.MD: BOOK-STRUCTURE-S04 (рядок `Арки:`), S06 (прапорці зустрічі, значки списку), технічний опис імпорту й інтерфейсу; MEMORY-MERGE — сценарій S04 «Вікно злиття» (таблиця, перенесені рішення, власне значення, CAS без втрати вибору, перехід зі зупиненого запуску), технічний опис інтерфейсу й `merge_markers`; прибрати з «Відомих обмежень» пункт про обв'язку. Traceability: MEMORY-MERGE-S04, BOOK-STRUCTURE-S04/S06 — нові тести; `python scripts/check_docs.py` → OK.
- [ ] Сайт: `docs/site/{uk,en}/book-structure.md` — розділ «Чергування арок і сцени зустрічі» / «Interleaved arcs and meeting scenes» (рядок `Арки:`, прапорці, значки); `docs/site/{uk,en}/memory.md` — розділ «Злиття пам'яті» / «Memory merge» (коли потрібне, вікно, власне значення, застарілість, продовження запуску, злиття кінця книги); нейтральні приклади; `python scripts/check_site.py --rehash book-structure` і `--rehash memory`.
- [ ] Повний `pytest -q`, node-тести й Playwright повністю (desktop+mobile) → PASS; коміт `docs: memory merge harness — spec, site`.

Після H6 — фінальне рев'ю всього кроку 3, cross-review (`detent`), PR у `main`, `verify.py` і `docs/STATUS.md`, оновлення основної теки.
