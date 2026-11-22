# Локації в пам'яті — ядро (PR 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** картки локацій з рядка «Локація:» плану, опис картки в контексті письма, локації записів пам'яті й шар відбору `place`.

**Architecture:** чистий модуль `storygen/locations.py` (розбір, нормалізація, ID, схожість, околиця); таблиці SQLite `story_locations`/`location_dismissals` (міграція 007 з бекфілом); `Scene.location_ids` заповнює `apply_description`; знімок залежностей отримує селектори локацій; журнал і wire v4 — необов'язкове `location_ids`; проєкція й `classify` — шар `place`.

**Tech Stack:** Python 3.12, pydantic, SQLite, pytest.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-22-memory-locations-design.md`

## Global Constraints

- ID: `loc_` + перші 16 hex SHA-256 від `story_id + '\n' + key`, де `key` — нормалізований повний шлях.
- Роздільники рядка: `,`, `;`, `→` і цілі слова `потім`, `далі`, `згодом`, `then`, `later` (без регістру); `і`, `та`, `and` — не роздільники; вкладеність — ` / ` (слеш з будь-якими пробілами).
- Нормалізація: NFC, нижній регістр, пробіли стиснуті, обрізані лапки `"«»“”'` по краях частини й кінцева розділова `.!?…:`; частини шляху з'єднуються `' / '`.
- Опис картки ≤ 2000 знаків; лише автор.
- Нові селектори й поля журналу пишуться так, щоб старі знімки й журнали лишалися байт у байт і актуальними.
- Тести не торкаються даних власника; `PYTHON_KEYRING_BACKEND=keyring.backends.fail.Keyring`.

## Review Focus

1. Рядок «Локація:» з порожнім значенням чи лише роздільниками — жодної картки, `location_ids=[]`.
2. Плани без рядка «Локація:» (усі наявні твори) — знімки, контексти й схема memory байт у байт як раніше.
3. Зациклене злиття (A→B, B→A) — `canonical` не зациклюється.
4. Сцена в кошику під час міграції — локації заповнено.
5. Відповідь memory зі старою схемою (без `location_ids`) для сцени з локаціями — приймається.

---

### Task 1: чистий модуль `locations.py`

**Files:** Create `src/storygen/locations.py`; Test `tests/memory/test_locations_parse.py`.

**Produces:** `parse_locations(line: str) -> list[tuple[str,...]]` (шляхи як частини, у порядку появи, без повторів за ключем); `normalize(parts) -> str`; `location_id(story_id, key) -> str`; `prefixes(parts) -> list[tuple[str,...]]`; `similar(a_path: str, b_path: str) -> bool`; `canonical(merged: Mapping[str,str|None], id) -> str`; `neighbourhood(locations: Mapping[id, Location-like], scene_ids) -> list[str]`.

- [ ] Тести S01: роздільники, «і/та/and», `А / Б`, нормалізація, ID, схожість (той самий лист; слова одного в іншому; Левенштейн ≤ 20 %), canonical з циклом, околиця (предки, нащадки, злиті).
- [ ] RED → реалізація → GREEN; коміт.

### Task 2: таблиці, міграція 007, `Scene.location_ids`, `apply_description`

**Files:** Create `src/storygen/storage/migrations/007_locations.sql`, `src/storygen/storage/locations.py`; Modify `storage/database.py` (SCHEMA_VERSION=7, бекфіл як у 005), `domain.py` (`Scene.location_ids`), `storage/scene_metadata.py`; Test `tests/storage/test_story_locations.py`.

**Produces:** `ensure_locations(db, story_id, paths, now) -> list[str]` (ID листів у порядку рядка, створює префікси з `parent_id`); `load_locations(db, story_id) -> dict[str, StoryLocation]`; `merge_location(db, story_id, id, into)`, `split_location(db, story_id, id)`, `set_description(db, story_id, id, text)`, `dismiss_pair(db, story_id, a, b)`; `StoryLocation(id, path, parent_id, merged_into, description)`.

- [ ] Тести S02: збереження плану з «Локація: Дім / кухня, потім двір» дає три картки й `location_ids` [кухня, двір]; повторне збереження — ті самі ID; зміна рядка інвалідує legacy-версії; міграція з базою v6 (сцена в кошику з рядком) заповнює картки без зміни `revision`.
- [ ] RED → реалізація → GREEN; коміт.

### Task 3: знімок залежностей, `ContextView`, опис у контексті

**Files:** Modify `storage/context_view.py` (`self.locations`, у `SHARED_FIELDS`), `storage/snapshots.py`, `generation/context.py`, `generation/context_labels.py`; Test `tests/storage/test_location_snapshots.py`.

Селектори: `scene.location_ids` (усі непатчеві скоупи, де є `character_ids`, пишеться завжди; відсутній у старому знімку — не порівнюється); `scene.location_neighbourhood` (скоупи з відбором пам'яті, лише коли непорожня); `scene.location_context` (`[[path, description], …]` локацій сцени й предків для brief/draft/prose_edit/author_rewrite, лише коли непорожній). Розділ `scene_locations` після карток персонажів для brief/draft/edit-повного/rewrite.

- [ ] Тести S02/S03/S06: зміна рядка → `is_stale` memory; злиття в околиці → stale, поза — ні; правка опису → stale brief/draft; сцена без локацій — знімок без нових полів, крім `location_ids=[]`; розділ є в brief/draft, немає в memory.
- [ ] RED → реалізація → GREEN; коміт.

### Task 4: журнал і wire v4

**Files:** Modify `memory/journal.py`, `memory/wire_v4.py`, `memory/violations.py`, `memory/merge.py`, `memory/series_start.py`, `generation/context.py` (bounds і розділ дозволених локацій); Test `tests/memory/test_memory_locations.py`.

- [ ] Тести S04: `location_ids` не серіалізується порожнім; `update`/`retire`/закриття лінії/`unknown` успадковують; `replay_memory` відкидає зміну поля в `update`; v4-відповідь з чужим ID → `location_unknown`; без поля — приймається; схема має `location_ids` лише з непорожніми дозволеними; ручне збереження й злиття арок не губить.
- [ ] RED → реалізація → GREEN; коміт.

### Task 5: проєкція й відбір

**Files:** Modify `memory/projection.py` (`MemoryItem.location_ids`, параметр `place`), `memory/selection.py` (`LAYERS`, `SelectionInput.place`, `classify`, `narrow_catalog`), виклики в `generation/context.py`; Test `tests/memory/test_selection_place.py`.

- [ ] Тести S05: предок/нащадок/злита → `place`; стан відсутнього персонажа в околиці не відкидається; `hero_recent`/`present`/`timeline` без змін.
- [ ] RED → реалізація → GREEN; коміт.

### Task 6: SPEC.MD, traceability, повний набір

- [ ] Requirement `MEMORY-LOCATIONS` зі сценаріями S01–S06 у SPEC.MD, записи traceability (S03 частково: API/панель — PR 2), `check_docs.py`, повний pytest у фоні.
