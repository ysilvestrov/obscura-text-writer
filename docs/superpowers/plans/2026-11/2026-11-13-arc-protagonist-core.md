# Протагоніст арки, ядро (проєкт 2, PR 2) — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** у арки з'являється протагоніст; відстежувані персонажі (ядро стану) визначаються для кожної сцени як протагоністи її арок і записуються в знімок сцени; панель пам'яті й вибір запиту класифікують слоти ядра щодо сцени.

**Architecture:** чиста функція `book/protagonists.py::scene_tracked` замінює книжковий `tracked_characters` у всіх місцях, що будують контекст, знімки й рядки пам'яті. Поки в книзі немає явного протагоніста, знімки пишуть селектор твору, як зараз (інваріант BOOK-LINEAGE-S01); з першим явним протагоністом — селектор сцени. Ядро — механізм; обв'язка (імпорт рядка `Протагоніст:`, поле в панелі «Структура книги», герой знайомств, сайт) — окремий план після рев'ю ядра, у тому самому PR.

**Tech Stack:** Python 3.12, pydantic, FastAPI, pytest; один рядок у `memory-table.js`.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-12-parallel-arcs-design.md` — розділи «Структура», «Родовід» (рядок про `tracked_characters`), «Поправка 1» пункти 1–3, сценарій BOOK-LINEAGE-S04.

## Global Constraints

- Книга без арок, книга з послідовними арками й будь-яка книга без явного протагоніста: ті самі запити, відбитки й знімки залежностей, що до зміни; наявні тести проходять без змін (BOOK-LINEAGE-S01).
- `Arc.protagonist_id: str | None` — ID картки; при збереженні структури картка має бути в поточному наборі карток, інакше 400 без збереження.
- `tracked_characters` для сцени: протагоністи її арок (явні; для арки без протагоніста — виведений протагоніст книги), без дублікатів, у порядку арок.
- Селектор сцени: `DependencySelector(kind='scene', owner_id=<scene id>, field='tracked_characters', expected=list[str])`.
- Перемішування арок і сцени зустрічі ще заборонені (PR 3); `Story.scene_arcs` лишається `dict[str,str]`.
- Без міграції SQLite; SPEC.MD — у тому самому коміті, що й код; документація українською.

## Review Focus

- Картку протагоніста видалено з набору після збереження структури: сцена бере виведеного героя книги, без 500 і без запису в структуру.
- Автор прибрав усі явні протагоністи (або розпустив структуру): знімки з селектором сцени лишаються свіжими, якщо значення збігається з виведеним героєм.
- Старий клієнт шле `PUT /memory-kind` без `scene_id`: заборона діє, якщо слот ядровий хоча б в одній активній сцені.
- Сцена кошика або сцена без відомої арки: відстежуваний — виведений герой книги.
- Знімки, збережені до оновлення в книзі без явних протагоністів, лишаються свіжими (значення селектора твору те саме).

---

### Task 1: протагоніст в арці й відстежувані сцени

**Files:**
- Modify: `src/storygen/domain.py` (клас `Arc`)
- Create: `src/storygen/book/protagonists.py`
- Test: `tests/book/test_protagonists.py`

**Interfaces:**
- Produces:
  - `Arc.protagonist_id: str | None = None` (старі payload читаються без змін);
  - `has_explicit_protagonists(story) -> bool` — у явній структурі є арка з непорожнім `protagonist_id`;
  - `scene_tracked(story, cards, scenes, scene) -> list[str]` — правило з Global Constraints; виведений герой — `memory.core.tracked_characters(cards, scenes)`; явний `protagonist_id`, якого немає серед `cards`, вважається відсутнім; без явної структури або без відомої арки сцени — виведений герой;
  - `arcs_of(story, scene) -> list[str]` — арки сцени зі структури (зараз 0 або 1; у PR 3 — список).

- [ ] **Step 1: тести** (книги будуються прямо в `Story`, як у `tests/book/test_lineage.py::book`; картки — `characters.models.load_characters` над JSON із `tests/storage/test_memory_core_selectors.py::cards`, герой книги A позначений рядком `HERO`):
  - `test_flat_book_tracks_the_book_hero` — `scene_tracked(...) == tracked_characters(cards, scenes) == ['A']`;
  - `test_arc_protagonist_overrides_the_book_hero` — частини `[['X'], ['Y']]`, `Y.protagonist_id='B'`: сцени X → `['A']`, сцени Y → `['B']`;
  - `test_missing_card_falls_back_to_the_book_hero` — `protagonist_id='Z'` без картки → `['A']`;
  - `test_scene_without_a_known_arc_and_trashed_scene` — обидві → `['A']`;
  - `test_explicit_flag` — `has_explicit_protagonists` хибне без явних і для пласкої книги, істинне з одним явним.
- [ ] **Step 2:** `pytest tests/book/test_protagonists.py -q` → FAIL (модуля немає).
- [ ] **Step 3:** реалізація.
- [ ] **Step 4:** той самий запуск → PASS; `pytest tests/book tests/storage -q` → PASS.
- [ ] **Step 5:** коміт `feat(book): arc protagonist and scene tracked characters`.

### Task 2: збереження протагоніста в структурі

**Files:**
- Modify: `src/storygen/web/routes_structure.py` (`ArcIn`), `src/storygen/storage/book_structure.py` (`build_structure`, `put_structure`)
- Test: `tests/storage/test_book_structure_protagonist.py`

**Interfaces:**
- Consumes: `Arc.protagonist_id` (Task 1); `storage.snapshots.core_cards(view, story)`.
- Produces: `PUT /api/stories/{id}/structure` приймає `parts[].arcs[].protagonist_id: str | None` (`max_length=64`).

- [ ] **Step 1: тести:**
  - `test_put_structure_saves_the_protagonist` — після PUT `story.book_structure.parts[1].arcs[0].protagonist_id == 'B'`, ревізія +1;
  - `test_unknown_card_is_refused_without_saving` — `pytest.raises(ValueError, match='^Протагоніст арки — картка, якої немає серед персонажів$')`, ревізія твору не змінилась;
  - `test_import_continuation_keeps_the_protagonist` — `place_imported` з продовженням останньої частини зберігає `protagonist_id` наявної арки.
- [ ] **Step 2:** запуск → FAIL.
- [ ] **Step 3:** `build_structure` передає `protagonist_id`; `put_structure` у тій самій транзакції перевіряє кожен непорожній `protagonist_id` проти ID карток `core_cards(ContextView(repo, db, story_id), story)` (повідомлення з тесту). Видалення картки пізніше структуру не переписує — Task 1 повертає виведеного героя.
- [ ] **Step 4:** запуск → PASS; `pytest tests/storage tests/web -q -k structure` → PASS.
- [ ] **Step 5:** коміт `feat(book): save the arc protagonist`.

### Task 3: селектор відстежуваних персонажів сцени

**Files:**
- Modify: `src/storygen/dependency_models.py` (дозволені поля `scene`), `src/storygen/storage/snapshots.py` (`memory_core_selectors`, `selector_value`, `compare_snapshot`, `freshness`)
- Test: `tests/storage/test_scene_tracked_selector.py`

**Interfaces:**
- Consumes: `has_explicit_protagonists`, `scene_tracked` (Task 1).
- Produces:
  - селектор `scene/<id>/tracked_characters`; `memory_core_selectors` рахує `tracked=scene_tracked(...)` і пише селектор сцени, якщо `has_explicit_protagonists(story)`, інакше селектор твору зі значенням `tracked`, як зараз. Сцени порівняння дня (`comparison_scene`) беруться для цього `tracked`;
  - `compare_snapshot(view, snapshot, scene_id: str | None = None)`; `freshness` передає `ref.scene_id`. З `scene_id` селектор `story/tracked_characters` порівнюється зі `scene_tracked` цієї сцени (переклад поруч із `legacy_selectors`); без нього — з `tracked_characters(cards, scenes)`, як зараз.

- [ ] **Step 1: тести** (helpers `setup`/`cards`/`memory_version`/`reasons` — з `tests/storage/test_memory_core_selectors.py`; структура дві частини по одній арці, сцени С1 в арці X, С2 в арці Y):
  - `test_without_explicit_protagonists_the_story_selector_stays` — знімок С2 має `('story', story.id, 'tracked_characters'): ['A']` і не має селектора сцени;
  - `test_explicit_protagonist_records_the_scene_selector` — `Y.protagonist_id='B'`: знімок С2 має `('scene', s2.id, 'tracked_characters'): ['B']`, без селектора твору;
  - `test_arc_protagonist_change_stales_only_its_arc` — знімки С1 і С2 після першого явного протагоніста; зміна `Y.protagonist_id` на `'A'` → `('selector_changed','tracked_characters') in reasons(С2)` і не в `reasons(С1)`;
  - `test_late_protagonist_stales_only_written_scenes_of_its_arc` — знімки С1 і С2 без явних протагоністів (селектор твору `['A']`); потім `Y.protagonist_id='B'` → `('selector_changed','tracked_characters')` у `reasons(С2)`, а `reasons(С1)` без `tracked_characters` (питання власника: написані сцени ранніх арок не переписуються);
  - `test_removing_explicit_protagonists_keeps_matching_scene_snapshots` — знімок С1 із селектором сцени `['A']`; після зняття всіх явних протагоністів → без `tracked_characters` у причинах.
- [ ] **Step 2:** запуск → FAIL.
- [ ] **Step 3:** `selector_value` для `scene/tracked_characters`: `scene_tracked(peek_story, core_cards, peek_scenes, peek_scene(owner))`; `story/tracked_characters` — як зараз; переклад селектора твору на сцену версії — у `compare_snapshot`.
- [ ] **Step 4:** запуск → PASS; `pytest tests/storage/test_memory_core_selectors.py tests/generation/test_writer_day_change.py -q` без змін тестів → PASS.
- [ ] **Step 5:** коміт `feat(memory): tracked characters selector per scene`.

> **Відхилення під час виконання (журнал, Task 3–4).** `compare_snapshot` не отримав параметра `scene_id`: сцену-власника знімка визначає `snapshots.snapshot_scene` із самих селекторів, а поточне значення селектора твору рахує `snapshots.current_value` (його ж використовує огляд впливу). Підміна селектора на селектор сцени змінювала звіт огляду впливу пласкої книги, тому від неї відмовились.

### Task 4: місця, що читають відстежуваних, і ядро щодо сцени

**Files:**
- Modify: `src/storygen/generation/context.py` (`memory_projection`, етап memory — `everyone`), `src/storygen/impact/planning.py:91-98`, `src/storygen/memory/service.py:70-71`, `src/storygen/memory/core_review.py:85`, `src/storygen/memory/kinds.py` (`tracked_ids`), `src/storygen/memory/forwarding.py:84`, `src/storygen/storage/memory_kinds.py`, `src/storygen/storage/repository.py` (`update_memory_kind`), `src/storygen/web/routes_rating.py` (`MemoryKindChange`), `src/storygen/web/static/memory-table.js:87`
- Test: `tests/book/test_protagonist_guard.py`, `tests/memory/test_scene_core_slots.py`

**Interfaces:**
- Consumes: `scene_tracked` (Task 1).
- Produces:
  - `memory.kinds.tracked_ids(view, scene) -> set[str]` (замість `(view, story)`);
  - `update_memory_kind(repo, story_id, claim_id, kind, expected_revision, scene_id: str | None = None)`; з `scene_id` заборона діє, якщо слот ядровий у цій сцені; без нього — якщо ядровий хоча б в одній активній сцені; невідома або чужа сцена → `KeyError('Сцену не знайдено')`;
  - `MemoryKindChange.scene_id: str | None = Field(default=None, max_length=64)`; `memory-table.js` шле `scene_id: snapshot.scene.id`.

- [ ] **Step 1: тести:**
  - `test_tracked_characters_is_called_only_by_the_protagonist_module` — `tracked_characters(` у `src/storygen` лише в `memory/core.py` і `book/protagonists.py` (регулярний вираз `\btracked_characters\(`, як `tests/book/test_lineage_guard.py`);
  - `test_other_arc_protagonist_slot_is_an_ordinary_state` — журнал зі слотом `clothing` персонажа A (будівники подій — `tests/memory/test_core_projection.py::ev/journal`), сцена арки Y з протагоністом B: рядок `memory_view` для цього слота має `'slot': False`; у сцені арки X — `True`;
  - `test_mark_is_refused_only_where_the_slot_is_core` — `update_memory_kind(..., scene_id=<сцена Y>)` для слота A зберігає позначку; `scene_id=<сцена X>` → `ValueError` з наявним текстом `'Слот ядра завжди показується; тип не змінюється'`; без `scene_id` → той самий `ValueError`;
  - `test_memory_stage_tracks_the_scene_protagonist` — `memory_projection(...)` для сцени арки Y повертає `tracked == ['B']`.
- [ ] **Step 2:** запуск → FAIL (охоронець перелічує місця).
- [ ] **Step 3:** кожне місце бере `scene_tracked(story, cards, scenes, scene)` для своєї сцени; `core_review` з `bounds` лишає `bounds['tracked']`.
- [ ] **Step 4:** нові тести PASS; повний `pytest -q` без змін наявних тестів → PASS.
- [ ] **Step 5:** коміт `refactor(memory): core slots follow the scene's arcs`.

### Task 5: SPEC і traceability

- [ ] SPEC.MD: BOOK-STRUCTURE — `Arc.protagonist_id`, перевірка картки, і уточнення «структура не входить у контекст» → «входить лише через відстежуваних персонажів»; BOOK-LINEAGE — правило `scene_tracked`, двоїстий селектор і сумісність (поправка 1, п. 3), сценарій BOOK-LINEAGE-S04 (ядро; імпорт `Протагоніст:` — у плані обв'язки); MEMORY-SELECT — ядро щодо сцени, `scene_id` у `PUT /memory-kind`; перелік селекторів залежностей; відомі обмеження (протагоніст із видаленою карткою мовчки повертає героя книги).
- [ ] `docs/verification/traceability.json`: BOOK-LINEAGE-S04 — тести Task 1–4; `python scripts/check_docs.py` → OK.
- [ ] Користувацька документація в ядрі не змінюється: інтерфейсу ще немає (причина — у коміті); сайт — план обв'язки.
- [ ] Коміт `docs(spec): BOOK-LINEAGE-S04 arc protagonist core`.
