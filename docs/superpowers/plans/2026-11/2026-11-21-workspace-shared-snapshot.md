# Спільний знімок між запитами — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** відкриття твору й збереження не перераховують актуальність книги в кожному запиті: зчитаний знімок твору та його результати спільні для запитів одного покоління даних.

**Architecture:** `Database` веде покоління з лічильником комітів у польоті; з'єднання запам'ятовує покоління під час відкриття. `storage/shared_snapshot.py` зберігає незмінний стан `ContextView` поточного покоління кожного твору й видає тонкі view для читань репозиторію поза транзакцією запису. Розібрані файли версій переходять між поколіннями за `stat`-перевіркою.

**Tech Stack:** Python 3.12, sqlite3 (WAL), FastAPI, pytest.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-21-workspace-shared-freshness-design.md` (затверджено, обсяг L).

## Global Constraints

- Результати з кешем MUST збігатися з приватним знімком; формат даних, схема, API не змінюються, міграції немає.
- Коміт із записом: покоління +1 до коміту і +1 після (успіх чи відкат); читання й відкат без запису не змінюють покоління.
- Спільні: зчитані моделі, `freshness_cache` (крім результатів із `dependency_cycle`), `memo_cache`, `journal_cache`, `preamble_cache`. Приватні в запиті: `resolving`, `impact_current_cache`, `review_current_cache`, профілі токенів.
- `ContextView(repo, db, story_id)` у шляхах запису лишається повністю приватним (рішення 3 дозволяє, але не вимагає, брати спільні результати; беремо простіший варіант).
- Між поколіннями переходять лише вміст файлу версії за (шлях, sha256) з тим самим `st_size`/`st_mtime_ns` і розбори `('memory', id, mode)`, `('cards', id)` разом із ним; `read_partial` щоразу заново.
- Тексти творів не друкуються; виміри — лише на копіях `C:\tmp`, `PYTHON_KEYRING_BACKEND=keyring.backends.fail.Keyring`, порожній env-файл.
- Мова коду й коментарів — як у модулях (англійська в коментарях, українська в повідомленнях).

## Review Focus

1. Інший `Repository` на тій самій теці в тому самому процесі (тести, MCP) пише в базу — перший має побачити зміну: стан покоління спільний для всіх `Database` з тим самим шляхом.
2. Тест чи інструмент пише в SQLite напряму через `sqlite3.connect` (корупція в тестах цілісності) — наступний запит має побачити зміну; поза процесом сервер цього не бачить, тому тести, що так пишуть, мають скидати покоління явно (`Database.bump_generation()` лише для тестів і інструментів, з коментарем).
3. Виняток усередині `connection()` після запису — відкат, покоління все одно змінюється на 2, лічильник у польоті повертається до 0.
4. `memo_cache` спільний: значення, обчислене під час обходу з циклом, не повинно залежати від порядку (`policy`, `tracked`, `names` не читають актуальність — перевірити тестом еквівалентності з циклом).
5. Твір у кошику / сцена в кошику: спільний знімок кидає ті самі `KeyError`, що й приватний.

---

### Task 1: Покоління даних у `Database`

**Files:**
- Modify: `src/storygen/storage/database.py`
- Test: `tests/storage/test_generation.py`

**Interfaces:**
- Produces: `Database.generation() -> int`; `Database.opened_state(db) -> tuple[int, int]` (покоління й комітів у польоті на момент відкриття цього з'єднання); `Database.bump_generation() -> None` (для тестів і інструментів, що писали поза `connection()`); стан — модульний реєстр за `Path.resolve()` бази, спільний для всіх `Database` того самого шляху. З'єднання — підклас `sqlite3.Connection` (`factory=`) з атрибутом `opened`.

- [ ] **Step 1: тести**

```python
def test_read_and_empty_rollback_keep_generation(tmp_path):
    db = Database(tmp_path / 'x.sqlite3'); g = db.generation()
    with db.connection() as c: c.execute('SELECT 1')
    with pytest.raises(RuntimeError), db.connection() as c: raise RuntimeError
    assert db.generation() == g

def test_writing_commit_and_writing_rollback_add_two(tmp_path):
    db = Database(tmp_path / 'x.sqlite3'); g = db.generation()
    with db.connection() as c: c.execute("INSERT INTO app_settings(key,payload) VALUES('k','{}')")
    assert db.generation() == g + 2
    with pytest.raises(RuntimeError), db.connection() as c:
        c.execute("INSERT INTO app_settings(key,payload) VALUES('k2','{}')"); raise RuntimeError
    assert db.generation() == g + 4

def test_connection_remembers_state_at_open_and_sees_commit_in_flight(tmp_path): ...
    # відкрити читача всередині коміту іншого з'єднання (хук перед комітом) → opened_state()[1] == 1

def test_two_databases_on_one_path_share_generation(tmp_path):
    a, b = Database(p), Database(p); write via b; assert a.generation() == b.generation()
```

- [ ] **Step 2:** `pytest tests/storage/test_generation.py -q` → FAIL (`generation` не існує).
- [ ] **Step 3:** реалізувати: у `connection()` після `yield` (до виходу з `with db`) — якщо `db.total_changes`: під замком `in_flight += 1; generation += 1`; після виходу з `with db` (коміт або відкат) — `in_flight -= 1; generation += 1`. `opened` записується під замком до першого `SELECT` (одразу після `connect`).
- [ ] **Step 4:** тест → PASS; `pytest tests/storage -q` → PASS.
- [ ] **Step 5:** коміт `feat(storage): покоління даних у Database (#39)`.

### Task 2: Спільний знімок і тонкий view

**Files:**
- Create: `src/storygen/storage/shared_snapshot.py`
- Modify: `src/storygen/storage/context_view.py`, `src/storygen/storage/snapshots.py` (`freshness`, `compare_snapshot`), `src/storygen/storage/repository.py` (`context_view`, `scene_view`, `get_scene`, `get_version`, інші читання з `ContextView` поза транзакцією запису — перелік зафіксувати в тесті)
- Test: `tests/storage/test_shared_snapshot.py`; оновити `tests/impact/test_planning_speed.py::test_memo_does_not_survive_the_request` (перейменувати: пам'ять не переживає запис), `tests/storage/test_context_view_readonly.py::test_second_request_sees_change_made_between_requests` (докстрінг)

**Interfaces:**
- Consumes: `Database.opened_state(db)`, `Database.generation()`.
- Produces:
  - `shared_snapshot.read_view(repo, db, story_id) -> ContextView` — спільний або приватний view;
  - `ContextView.state()` / `ContextView.from_state(state, db)` — розділення на незмінний стан і тонкий view;
  - `LayeredCache` (`get`, `__contains__`, `__getitem__`, `__setitem__` → спільний шар, `set_private(key, value)`);
  - `view.cycle_hits: int`, `view.shared_lock: RLock | None`;
  - `SnapshotStore` на `Repository` (`repo.snapshots`), ключ (твір, покоління), лише поточне покоління, не більше 4 творів (LRU), старіше не замінює новіше.

- [ ] **Step 1: тести**
  - `test_reads_of_one_generation_share_state`: два `repo.context_view(id)` без запису → `a.scenes is b.scenes`, `a.freshness_cache` має спільний шар з `b`.
  - `test_write_starts_a_new_generation`: запис між запитами → новий стан, нова актуальність (запис змінює stale версії — як у `test_second_request_sees_change_made_between_requests`).
  - `test_commit_between_open_and_capture_keeps_view_private`: хук у `ContextView.__init__` робить коміт іншим з'єднанням → view не опублікований, наступний запит будує новий.
  - `test_older_generation_never_replaces_newer`.
  - `test_write_transaction_view_is_private`: `ContextView(repo, db, id)` у `BEGIN IMMEDIATE` має власні моделі; запис у модель + відкат не змінює наступну відповідь.
  - `test_impact_and_review_current_caches_are_private`.
  - `test_cycle_results_stay_private_and_match_fresh_view`: цикл із трьох версій A→B→C→A і зовнішній вхід X→A; для кожного порядку запитів результати (з причинами) на спільному знімку = на свіжому приватному view.
  - `test_parallel_requests_compute_top_level_once`: 4 потоки, `resolve_freshness` однієї версії → `_compute` верхнього рівня викликано 1 раз.
  - `test_repository_reads_share_the_snapshot`: `scene_view`, `get_scene`, `get_version`, `context_view` → один стан.
  - `test_shared_equals_private_after_writes`: послідовність запитів/записів (`setup` з `test_freshness`, `assessed` з `test_storage`, forwarding) — JSON readiness, `scene_status`, `plan_review(...).fingerprint` однакові для спільного і для `ContextView(repo, db, id)`.
  - `test_trashed_story_and_scene_raise_like_private`.
- [ ] **Step 2:** запустити → FAIL.
- [ ] **Step 3:** реалізувати.
  - `ContextView.__init__` без змін для приватного шляху; `state()` повертає словник зчитаних полів і спільних кешів; `from_state` створює view з `resolving=set()`, `cycle_hits=0`, `freshness_cache=LayeredCache(state.fresh)`, приватними `impact_current_cache`/`review_current_cache`, `token_profiles` — заново з `db` (`SELECT … token_profile:%`).
  - `read_view`: `(g, active) = opened_state(db)`; якщо `active == 0` і `generation() == g` і стан (твір, g) є — `from_state`; інакше будувати приватний view, потім під замком `SnapshotStore` перевірити `active == 0 and generation() == g and not db.total_changes` і опублікувати.
  - `freshness`: якщо `not view.resolving and view.shared_lock` — увійти під замок і повторити перевірку кешу; рахувати `cycle_hits` у гілці циклу `freshness` і в обох гілках циклу `compare_snapshot`; результат із приростом `cycle_hits` або з причиною `dependency_cycle` — `set_private`.
- [ ] **Step 4:** нові тести й `pytest tests/storage tests/impact tests/generation tests/memory -q` → PASS.
- [ ] **Step 5:** коміт `feat(storage): спільний знімок твору між запитами (#39)`.

### Task 3: Незмінні розбори між поколіннями

**Files:**
- Modify: `src/storygen/storage/shared_snapshot.py` (`ImmutableStore`), `src/storygen/storage/context_view.py` (`read_blob`, `memo`)
- Test: `tests/storage/test_shared_snapshot.py`

**Interfaces:**
- Produces: `ImmutableStore.read(files, path, sha) -> bytes` (повторно лише за тим самим `st_size`/`st_mtime_ns`, інакше `FileStore.read`); `ImmutableStore.parsed(key, sha, build)`; ліміт ≈ 128 МБ вмісту й 8192 розборів (LRU). `memo()` для `('memory', id, …)` і `('cards', id)` спершу викликає `view.read_blob(ref.relative_path, ref.sha256)` у поточному поколінні.

- [ ] **Step 1: тести** `test_blob_reused_across_generations_only_with_same_stat`; `test_deleted_or_replaced_file_gives_integrity_error_next_generation` (видалити/перезаписати файл версії, запис у базу → `freshness(...).reasons` містить `integrity_error`); `test_cards_and_journals_parsed_once_across_a_write` (лічильник `load_characters`/`load_memory`); `test_scene_values_recomputed_after_write`.
- [ ] **Step 2:** FAIL. **Step 3:** реалізувати. **Step 4:** PASS + `pytest tests/storage tests/impact -q`.
- [ ] **Step 5:** коміт `feat(storage): незмінні розбори між поколіннями (#39)`.

### Task 4: Сторожі й профілі токенів

**Files:**
- Test: `tests/storage/test_shared_snapshot_guards.py`; за потреби — тести, що пишуть через `sqlite3.connect`, викликають `bump_generation()`

- [ ] **Step 1: тести** `test_only_allowed_modules_open_sqlite` (AST/regex по `src/storygen`: `sqlite3.connect` лише в `database.py`, `backup.py`, `integrity.py`, `pre_migration.py`, `fts.py`); `test_no_commit_outside_connection` (`.commit()`/`COMMIT` лише в міграціях `database.py`); `test_clis_take_the_lock_or_write_only_token_profiles` (перелік `*/cli.py`, що створюють `Repository`: `AppInstanceLock` або `token_budget/cli.py`); `test_token_profiles_written_elsewhere_are_seen` (другий `Repository` у тому самому процесі після `bump`-незалежного шляху: запис профілю → наступний `repo.context_view(...).token_records('profile')` бачить).
- [ ] **Step 2–4:** FAIL → реалізація/виправлення тестів із прямим записом → PASS.
- [ ] **Step 5:** коміт `test(storage): сторожі спільного знімка (#39)`.

### Task 5: SPEC, traceability, виміри

**Files:** `SPEC.MD` (PERF-001: вимога, S02, новий S06, технічний опис, інваріанти, виміри S03), `docs/verification/traceability.json` (S06 → тести Task 1–4; S02 — оновлені тести), `docs/verification/manual.md#workspace-speed` (результат), `docs/superpowers/plans/2026-10-20-remediation-progress.md`, спека (результати).

- [ ] **Step 1:** повний `pytest` у фоні (`--basetemp=C:/tmp/p39b-full`) → усі зелені.
- [ ] **Step 2:** виміри: `scripts/workspace_bench.py` (digest збігається з `main`), браузер за `manual.md#workspace-speed` на свіжих копіях 68 і 300 (старий і новий код), макет `C:\tmp\p39c-probe.py` не потрібен.
- [ ] **Step 3:** SPEC/traceability/manual/журнал; `PYTHONUTF8=1 .venv/Scripts/python.exe scripts/check_docs.py` → OK.
- [ ] **Step 4:** коміт `docs(spec): PERF-001-S06 спільний знімок (#39)`.
