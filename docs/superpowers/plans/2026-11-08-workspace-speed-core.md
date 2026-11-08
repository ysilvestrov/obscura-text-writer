# Швидка відповідь робочого простору — ядро (сервер)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Прибрати серверні причини повільних відповідей робочого простору (глибокі копії, повторні знімки, розбір усіх спроб) без жодної зміни результатів.

**Architecture:** `ContextView` отримує внутрішні методи читання без копій для обчислення актуальності; публічні методи й далі копіюють. Readiness будує один `ContextView` на виклик і передає його в `build_context`. Списки спроб і запусків фільтруються в SQL за наявними колонками. Інтерфейс (`/runs` коротка форма, згортання запитів) — окремий периферійний план після end-to-end рев'ю ядра.

**Tech Stack:** Python 3.12, FastAPI, pydantic v2, SQLite, pytest.

**Spec:** `docs/specs/2026-11/workspace-response-speed.md` (затверджено 2026-11-08).

## Global Constraints

- Результати readiness, story view, freshness, CAS і dependency snapshot MUST бути тими самими, що й до зміни (spec, «Інваріанти»).
- Жодного кешу між HTTP-запитами; кешування лише в межах одного `ContextView` (spec, рішення 2).
- Без SQL-міграції, нових індексів, зміни формату payload або блобів (spec, рішення 3).
- SQL лише в `src/storygen/storage/` (`tests/storage/test_storage_boundaries.py`).
- Робочу базу `C:\Projects\text-generator\data\storygen.sqlite3` не змінювати; бенчмарки — на копії. Тексти твору й моделей не друкувати, лише ID, коди, час і хеші.
- Документація українською; маркери OpenSpec англійською. Кожен новий Scenario має запис у `docs/verification/traceability.json`; `PYTHONIOENCODING=utf-8 python scripts/check_docs.py` проходить.
- pytest на цій машині: `C:/Projects/text-generator/.venv/Scripts/python.exe -m pytest --basetemp=C:/tt/x <шляхи>` з кореня worktree `C:\Projects\text-generator-speed` (`pyproject.toml` уже задає `pythonpath = ["src"]`). Далі в плані `…pytest` означає саме цю команду.

## Review Focus

1. **Сцена або твір у кошику.** Внутрішні методи мусять кидати `KeyError` так само, як публічні, щоб селектор на сцену в кошику давав `selector_unavailable`, а не мовчки «актуально». Тест — Task 2, крок 1.
2. **Аліасинг.** Значення з `selector_value` (`character_ids`, порядок сцен) потрапляють у `DependencyChange.current`; зміна цього списку викликачем не повинна змінити сцену в `ContextView`. Тест-сторож мутації — Task 2, крок 1.
3. **Цикл залежностей і спільний кеш freshness.** Внутрішній результат із `freshness_cache` віддається без копії; цикл має й далі давати stale, а зміна публічної копії — не псувати кеш. Тест — Task 2, крок 1.
4. **Readiness без вибраної сцени / з порожнім твором** — ті самі повідомлення (`Оберіть сцену`, `Матеріал не знайдено; оновіть сторінку`) після переходу на один view. Тест — Task 3, крок 1.
5. **Спроба з `copyedit_proposal`/`rewrite_proposal` = `null` або порожнім об'єктом.** SQL-префільтр `IS NOT NULL` не має змінити множину, яку раніше давав Python-фільтр за істинністю. Тест — Task 4, крок 1.

---

### Task 1: Бенчмарк і цифровий відбиток результатів

**Files:**
- Create: `scripts/workspace_bench.py`
- Create: `src/storygen/application/workspace_bench.py` (логіка: синтетичний твір, вимірювання, digest; скрипт — тонка обгортка, як `scripts/memory_replay.py` над `storygen.memory.replay`). SQL тут заборонений — лише публічний API Repository, `readiness.preview`, `impact.presentation.scene_status`.
- Test: `tests/storage/test_workspace_bench.py`

**Interfaces:**
- Produces: `python scripts/workspace_bench.py --data <копія data> [--story <id-префікс>] [--json]` і `python scripts/workspace_bench.py --synthetic <N> --workdir <тека> [--json]`. Вихід JSON: `{"story": "<id8>", "scenes": N, "timings": {"readiness:<op>": сек, "story_view": сек, "list_attempts": сек, "list_runs": сек, "scene_select": сек}, "digest": "<sha256>"}`.
- Produces: `workspace_bench.build_story(repo, scenes: int) -> str` (повертає story_id): N сцен, кожна з планом, ручною прозою (`save_manual_prose`) і пам'яттю (`save_scene_memory`, один факт на сцену, як `tests/memory/test_forwarding.py::seeded`).
- `digest` — sha256 від канонічного JSON (`sort_keys=True, ensure_ascii=False, default=str`) усіх 9 відповідей readiness для середньої сцени, `story_view`-еквівалента (`impact_status`, effective scenes) і відфільтрованих ID спроб/запусків. Порівняння digest до/після — головний доказ еквівалентності на реальних даних.

- [ ] **Step 1: Write the failing test** `test_bench_digest_is_stable_and_synthetic_story_has_requested_size`: `build_story(repo, 5)` створює 5 сцен із `heads['plan']`, `heads['prose']`, `heads['memory']`; два послідовні виклики функції digest на тому самому repo дають однаковий рядок довжиною 64; `timings` має ключі `readiness:brief` … `readiness:edit_loop` (9 шт.), `story_view`, `list_attempts`, `list_runs`, `scene_select`.
- [ ] **Step 2: Run** `…pytest tests/storage/test_workspace_bench.py -v` → FAIL (`ModuleNotFoundError`).
- [ ] **Step 3: Implement** у `workspace_bench.py` функції `build_story`, `measure(repo, story_id) -> dict` (timings + digest) і тонкий `scripts/workspace_bench.py` з `main(argv)`. `scene_select` — сума часу функцій, які викликає вибір сцени: `/scenes/{id}/versions`, `copyedits`, `rewrites`, `readiness?operation=brief`, `/runs`, story view (через ті самі репозиторні виклики, що й маршрути). Скрипт не друкує текстів.
- [ ] **Step 4: Run test** → PASS.
- [ ] **Step 5: Baseline.** На копії `C:/Users/yuriy/AppData/Local/Temp/claude/b7ec400ed7aa6179/4ff819a8-5ed1-4360-b8f2-0c2b890020e0/scratchpad/datacopy1` (або свіжій копії робочих даних через SQLite backup API) і на `--synthetic 300` запустити скрипт до будь-яких змін коду; JSON зберегти в `.superpowers/sdd/…/baseline-68.json` і `baseline-300.json` (git-ignored). Записати digest і час у журнал виконання.
- [ ] **Step 6: Commit** `git add scripts/workspace_bench.py src/storygen/application/workspace_bench.py tests/storage/test_workspace_bench.py && git commit -m "Add workspace benchmark with result digest (#27)"`.

### Task 2: Читання без копій у `ContextView` і обчисленні актуальності

**Files:**
- Modify: `src/storygen/storage/context_view.py` (нові методи; `get_version`, `effective_scene`)
- Modify: `src/storygen/storage/snapshots.py` (`selector_value`, `compare_snapshot`, `resolve_freshness`)
- Modify: `src/storygen/memory/forwarding.py` (`choices_at`)
- Modify: `src/storygen/memory/reuse.py` (`_candidate`: лише читання полів `VersionRef`)
- Test: `tests/storage/test_context_view_readonly.py`

**Interfaces:**
- Produces у `ContextView` (docstring: «внутрішнє читання без копії; не змінювати результат»):
  - `peek_story(id) -> Story` — `KeyError`, якщо id не той або твір у кошику (як `get_story`).
  - `peek_scene(id) -> Scene` — `KeyError`, якщо сцена в кошику (як `get_scene`).
  - `peek_scenes(story_id) -> list[Scene]` — активні сцени в порядку `list_scenes`.
  - `peek_version(id) -> VersionRef` — сирий запис (поле `stale` не перераховане); `KeyError` за відсутності або якщо сцена версії в кошику.
  - `is_stale(id) -> bool` — `snapshots.freshness(self, id).stale`.
- Produces у `snapshots`: `freshness(view, version_id) -> FreshnessResult` — без копії, спільний об'єкт кешу; `resolve_freshness` = `freshness(...).model_copy(deep=True)` (публічна поведінка незмінна).
- Значення-списки, що повертає `selector_value`, — нові списки (`list(...)`), не посилання на поля сцени.

- [ ] **Step 1: Write the failing tests** (фікстура — `tests/storage/test_freshness.py::setup` плюс 3-сценний `tests/memory/test_forwarding.py::seeded`):
  - `test_peek_methods_raise_like_public_ones_for_trashed_scene`: після `repo.set_scene_trashed(story.id, scene.id, scene.revision, restore=False)` `view.peek_scene(id)` і `view.get_scene(id)` обидва кидають `KeyError`; `compare_snapshot` для знімка з селектором на цю сцену містить `reason == 'selector_unavailable'`.
  - `test_readiness_and_status_do_not_mutate_view_models`: дампи (`model_dump()`) усіх `view.scenes`, `view.versions` і `view.story` до та після `scene_status(view)`, `[view.effective_scene(s.id) for s in view.list_scenes(...)]` і `compare_snapshot` для кожного prose-знімка однакові; зміна `change.current.append('x')` у будь-якому повернутому `DependencyChange` не змінює `view.scenes[...]`.
  - `test_shared_freshness_cache_survives_public_copy_mutation_and_cycle_stays_stale`: `resolve_freshness(view, id).reasons.clear()` не змінює `freshness(view, id).reasons`; існуючий сценарій циклу (`test_freshness.py::test_cycle_never_counts_as_fresh`) з `freshness` дає `stale is True`.
  - `test_peek_path_matches_copying_path`: для fixture-твору обчислити readiness усіх 9 операцій, `scene_status` і freshness кожної версії; потім `monkeypatch` замінює `peek_scene/peek_scenes/peek_version/peek_story` на варіанти з `model_copy(deep=True)` і `freshness` на копіювальний — результати (канонічний JSON) рівні.
- [ ] **Step 2: Run** `…pytest tests/storage/test_context_view_readonly.py -v` → FAIL (`AttributeError: peek_scene`).
- [ ] **Step 3: Implement.** У `selector_value` і `compare_snapshot` замінити `get_story/get_scene/list_scenes/get_version` на `peek_*`, а `ref.stale` — на `view.is_stale(id)`. `ContextView.get_version` робить перевірку кошика через `peek_scene` і бере stale з `freshness`; `effective_scene` — `is_stale`. `choices_at` читає `peek_scene/peek_scenes`. `reuse._candidate` читає `kind/scene_id/story_id/complete/sha256` через `peek_version` (stale там не використовується). `build_dependency_snapshot` не змінювати (14 викликів, ~0,4 с — поза гарячим шляхом).
- [ ] **Step 4: Run** новий файл і чинні `tests/storage tests/memory tests/generation tests/review tests/impact` → PASS.
- [ ] **Step 5: Digest.** `scripts/workspace_bench.py` на тій самій копії: digest = baseline; записати час.
- [ ] **Step 6: Commit** `"Read dependency state without deep copies (#27)"`.

### Task 3: Один `ContextView` на перевірку передумов і кеш розбору плану

**Files:**
- Modify: `src/storygen/generation/context.py` (`build_context(..., view=None)`)
- Modify: `src/storygen/generation/readiness.py` (`preview`)
- Modify: `src/storygen/storage/snapshots.py` (`source_preamble`)
- Modify: `src/storygen/storage/context_view.py` (`self.preamble_cache = {}`)
- Test: `tests/generation/test_readiness_single_view.py`

**Interfaces:**
- Consumes: `peek_*`, `freshness` з Task 2.
- Produces: `build_context(repo, scene_id, stage, settings, *, editor_source_id=None, memory_approval=None, view=None) -> ContextBundle`. З `view` не викликає `repo.get_scene`/`repo.context_view`, а бере `view.get_scene(scene_id)`; без `view` поведінка незмінна.
- Produces: `source_preamble(view, ref)` кешує результат у `view.preamble_cache[(ref.id, ref.sha256)]`.

- [ ] **Step 1: Write the failing tests:**
  - `test_preview_builds_one_context_view_for_stage_operations`: `monkeypatch` обгортає `Repository.context_view` лічильником; `preview` для `brief` на 3-сценному творі робить рівно 1 виклик (зараз — кілька, плюс приховані через `repo.get_scene/list_scenes/get_version`; лічильник рахує й конструктор `ContextView` через patch `storygen.storage.context_view.ContextView.__init__`, очікування — 1 конструкція).
  - `test_preview_errors_unchanged_without_scene_and_for_missing_material`: `preview` без `scene_id` → `reason == 'Оберіть сцену'`; для сцени, видаленої після побудови запиту, → `'Матеріал не знайдено; оновіть сторінку'` (як зараз).
  - `test_source_preamble_parses_plan_once_per_view`: patch `storygen.plan_sections.split_plan` лічильником; два `compare_snapshot` з селектором `source_preamble` на одному view → 1 виклик.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** У `preview` (гілка stage/scene/remaining/rebuild_memory) створити `view=repo.context_view(story.id)` після `repo.get_story`; `scenes=view.list_scenes(story.id)` (preview не читає `needs_review`); обидва виклики `build_context(..., view=view)`; `character_material` — з тим самим `view`. Гілку `prepare` і делеговані режими не змінювати. `repo.get_version(prompt_id)` лишити (окрема семантика legacy-актуальності в `Repository.get_version`).
- [ ] **Step 4: Run** новий файл, `tests/generation/test_readiness.py` і решту `tests/generation tests/memory` → PASS.
- [ ] **Step 5: Digest** = baseline; записати час.
- [ ] **Step 6: Commit** `"Reuse one context view per readiness check (#27)"`.

### Task 4: Фільтрування спроб і запусків у SQL

**Files:**
- Modify: `src/storygen/storage/repository.py` (`list_attempts`)
- Modify: `src/storygen/storage/run_store.py` (`list_runs`)
- Modify: `src/storygen/web/routes_versions.py` (`list_copyedit_proposals`), `src/storygen/web/routes_rewrites.py` (`list_rewrites`)
- Test: `tests/storage/test_attempt_filters.py`

**Interfaces:**
- Produces: `Repository.list_attempts(story_id, run_id=None, *, scene_id=None, context_key=None) -> list[StageAttempt]`. `context_key` ∈ `{'copyedit_proposal', 'rewrite_proposal'}`, інакше `ValueError`; SQL: `story_id=?` [+ `run_id=?`] [+ `scene_id=?`] [+ `json_extract(payload, '$.context.' || ?) IS NOT NULL`], `ORDER BY rowid`. Позиційний `run_id` лишається сумісним із чинними викликачами.
- Produces: `run_store.list_runs(repo, story_id=None)` з `WHERE story_id=?`, якщо задано; порядок `rowid`.
- Маршрути зберігають чинний Python-фільтр за істинністю `a.context.get(key)` і станами поверх SQL-префільтра.

- [ ] **Step 1: Write the failing tests:** два твори, по дві сцени, кілька запусків; спроби з `copyedit_proposal` = непорожній об'єкт, `{}`, `null`, відсутній; так само `rewrite_proposal`.
  - `test_sql_filters_match_python_filters`: для кожної комбінації (`run_id`, `scene_id`, `context_key`) результат `list_attempts` (ID у порядку) дорівнює Python-фільтру над повним `list_attempts(story_id)`.
  - `test_routes_return_same_attempts_as_before`: `TestClient` `GET /api/scenes/{id}/copyedits` і `/rewrites` повертають ті самі ID, що й обчислені старим виразом у тесті.
  - `test_unknown_context_key_is_rejected`: `list_attempts(..., context_key='x')` → `ValueError`.
  - `test_list_runs_filters_by_story_in_sql`: результат дорівнює Python-фільтру; запуски іншого твору відсутні.
- [ ] **Step 2: Run** → FAIL (`TypeError: unexpected keyword 'scene_id'`).
- [ ] **Step 3: Implement** у storage; маршрути передають `scene_id=` і `context_key=`.
- [ ] **Step 4: Run** новий файл, `tests/storage/test_storage_boundaries.py`, `tests/web` → PASS.
- [ ] **Step 5: Digest** = baseline; записати час.
- [ ] **Step 6: Commit** `"Filter attempts and runs in SQL (#27)"`.

### Task 5: SPEC.MD, traceability, вимірювання й журнал

**Files:**
- Modify: `SPEC.MD` (нова `### Requirement: PERF-001 — Швидка відповідь робочого простору`; згадка `ContextView` peek-методів у технічному описі сховища)
- Modify: `docs/verification/traceability.json`
- Modify: `docs/superpowers/plans/2026-10-20-remediation-progress.md`
- Modify: `docs/STATUS.md` (через `scripts/verify.py`)

- [ ] **Step 1:** Додати PERF-001 зі Scenario `PERF-001-S01` (еквівалентність → `tests/storage/test_context_view_readonly.py::test_peek_path_matches_copying_path`, `tests/storage/test_attempt_filters.py::test_sql_filters_match_python_filters`), `PERF-001-S02` (сторож мутації → `…::test_readiness_and_status_do_not_mutate_view_models`), `PERF-001-S03` (ручна процедура: `scripts/workspace_bench.py` на копії робочих даних і `--synthetic 300`; межі ≤ 1 с / ≤ 3 с на типову дію перевіряються після периферійного плану; причина ручної процедури — залежить від машини). Технічний опис: внутрішні `peek_*` лише для читання, без кешу між запитами.
- [ ] **Step 2: Run** `PYTHONIOENCODING=utf-8 …python scripts/check_docs.py` → «узгоджені».
- [ ] **Step 3: Measure.** Бенчмарк на копії (68 сцен) і `--synthetic 300`: таблиця baseline → після ядра, digest рівні. Записати в журнал виконання (без текстів).
- [ ] **Step 4: Run** `PYTHONIOENCODING=utf-8 …python scripts/verify.py` → 0 failed; результат у `docs/STATUS.md`.
- [ ] **Step 5: Commit** `"Specify PERF-001 and record core measurements (#27)"`.

Після Task 5: end-to-end рев'ю ядра (фінальне whole-branch рев'ю), потім окремий периферійний план (коротка форма `/runs`, споживачі, згортання запитів, перевірка меж PERF-001-S03 у браузері).
