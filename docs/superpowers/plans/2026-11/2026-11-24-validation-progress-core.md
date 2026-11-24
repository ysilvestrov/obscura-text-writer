# Видимий прогрес запусків — ядро: план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** запуск зберігає обіцяний план (виклики, верхня межа в доларах, сцени книги) і доповнює його при продовженні; сервер рахує прогрес (`run_progress`) і віддає його в `GET /api/runs/{id}` та подією `progress`; рядок запуску, щойно запущеного з цієї вкладки, розгортається з прогресом і фокусом; пункт меню валідації книги має стани «триває» / «зупинено».

**Architecture:** новий модуль `generation/run_progress.py` — чисті функції над `Run` і його подіями з бази (`list_run_events` з фільтром типів) плюс `emit_progress`, який викликає одна точка — `RunCoordinator.event` після кожної `stage_started`, `stage_finished` і `audit_step` (покриває `audit_run`, цикл worker, `editor_loop` і оцінювання). План запуску доповнюється в `RunCoordinator.enqueue` і `RunCoordinator.resume` (повторна готовність там уже є: `run_readiness` → `readiness.pending_preview` → для `audit` `audit_run.readiness(resume=True)`). Клієнт: чисті правила тексту в `static/run-progress.js`, правила розгортання в `run-summary.js`, правила меню в `book-validation-state.js`; рендер — `runs.js` і `book-validation.js`.

**Tech Stack:** Python 3.12, Pydantic v2, FastAPI, SQLite, vanilla JS (ES modules), pytest, node-скрипти JS-тестів, Playwright.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-24-validation-progress-ux-design.md`, розділи 1–3 (затверджено 24.11.2026). Чинна архітектура — `SPEC.MD` (VALID-RUN, VALID-UI, R20-WORKSPACE, PERF-001 про `GET /api/runs/{id}`).

**Межі цього плану (pr-slicing: ядро).** Панель «Узгодженість сцени» (§4), сайт uk/en, знімки й `manual.md`-процедури панелі — окремий harness-план після end-to-end рев'ю ядра. Спека передбачає один PR (M) на всю зміну, тож це ядро — коміти на гілці `claude/validation-progress-ux`, PR відкривається після harness-плану. SPEC.MD і traceability для того, що ядро змінює архітектурно, — у задачі 5 цього плану.

## Global Constraints

- `planned_telemetry.cost_bound_usd` — «рядок з 4 знаками або null», лише для `mode='audit'`; `planned_telemetry.scenes` — лише для `audit_scope='story'`. Інші режими цих ключів не отримують (`tests/web/test_runs.py` звіряє точний словник для `stage`).
- «Поля лише додаються в `planned_telemetry` (dict): міграція не потрібна; старі запуски їх не мають.»
- Суми доларів на сервері — `Decimal(str(value))`, квантування до `0.0001`: `spent_usd` — `ROUND_HALF_UP`, межа при продовженні — `ROUND_CEILING` (як `audit_cost.usd`, бо це верхня межа); `spent_usd` і `bound_usd` у `progress` — рядки.
- «Запуск без подій дає нулі.» Читання подій для прогресу — один запит із фільтром `type IN ('stage_started','stage_finished','audit_step')`, без `delta` (Р8). Перенос пам'яті (`memory_carry`) → `progress = None`.
- Розгортати й фокусувати «лише запуск, щойно запущений дією автора в цій вкладці». Завантаження сторінки й «Останній запуск» фокус не переносять.
- «`prefers-reduced-motion` — без плавної прокрутки.»
- Нові тексти — ключі `src/storygen/web/static/i18n.json`, `uk` і `en`; плейсхолдери `{p0}`, `{p1}`…
- Серверний `_supersede` (VALID-RUN-S09) не змінюється: ним і далі користується міст MCP і запуск поверх `failed`/`interrupted`.
- `@pytest.mark.req` на нових тестах — лише якщо тест названо в рядку `traceability.json` тієї самої вимоги (`check_docs.py` інакше падає).
- Python-тести: `PYTHONUTF8=1 PYTHONPATH=src /c/Projects/text-generator/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=C:/tmp/vpux/<name> <tests>` — далі «PYTEST <name> <tests>».
- Playwright: `cd frontend && PYTHONPATH="$(cd .. && pwd -W)/src" PYTHONUTF8=1 ./node_modules/.bin/playwright test ../tests/web/browser/<spec> --grep-invert screenshots --reporter=line` — далі «PW <spec>».
- Мусять лишатися зеленими без зміни очікувань (крім названих у задачах): `tests/web/test_resumed_events.py` (Node-мок `runs_follow.mjs` без `scrollIntoView`/`focus`/`matchMedia`/`activeElement`), `tests/web/test_run_status_collapse_ui.py` (буквальні рядки в `runs.js`), `tests/web/test_book_validation_ui.py`, `tests/generation/test_audit_run.py`, `tests/web/test_runs.py`, `tests/generation/test_worker.py`, `tests/generation/test_editor_loop.py`, `tests/generation/test_run_closure.py` (`events[-1]` — подія `state`), `tests/generation/test_rewrite_queue.py`, `tests/evaluation/test_evaluation_language.py` (нові події `progress` з'являються в кожному запуску).

## Review Focus

1. **Перемалювання знімає фокус.** Після згоди `draw()` викликається на кожну подію `state` і робить `status.replaceChildren()`; фокус із заголовка прогресу падає на `body`. Очікування: заголовок лишається у фокусі до кінця запуску. Тест — задача 4, крок 1 (`toBeFocused()` після `needs_review`).
2. **Продовження книги рахує сцену зупинки двічі.** Перегляд resume знову містить сцену зупинки, тож буквальне `visited + scenes_resume` дає «з 3» для книги з двох сцен. Очікування: N — різні сцени. Тест — задача 2 (`test_resume_extends_the_plan_without_counting_a_visited_scene_twice`) і задача 4 (заголовок «сцена 2 з 2» після продовження).
3. **Рядок відстає на крок.** Етап edit сцени чи «решти» йде через `editor_loop.py`, оцінювання — через `execute_evaluation`, а `progress` лише після `stage_finished`/`audit_step` під час виклику k називав би крок k‑1. Очікування: під час виклику рядок називає сцену й зв'язок, що перевіряються зараз. Тест — задача 1 (`test_progress_after_stage_started_names_the_current_link`, `test_editor_loop_pass_emits_progress`).
4. **Зупинена валідація книги не є поточним запуском рядка.** Автор міг відкрити пізніший запуск; меню, що дивиться лише на `state.workspaceRun`, пропонує нову валідацію і мовчки замінює зупинену. Очікування: меню шукає останню валідацію книги серед запусків твору. Тест — задача 3 (`latestBookRun` у `book_validation.mjs`).
5. **Без ціни й без межі.** Старі запуски без `cost_bound_usd`, локальний Ревізор (жодної ціни, межа null), запуск без `planned.calls`, n > N. Очікування: «Витрачено: $x» без «з $y»; без жодної ціни й без межі — частини про долари немає; «сцена n» без «з N»; без N — смуги немає. Тест — задача 3 (`run_progress.mjs`).

## Рішення, ухвалені планом (спека мовчить або суперечить коду)

- **Р1. «Продовжити» в рядку для книги лишається видимим у ядрі.** Спека (§3) ховає його, доки сцена зупинки є, бо продовження переходить у панель (§4). Панелі в ядрі немає, і без кнопки зупинену валідацію неможливо продовжити (ламає VALID-UI-S04 і `book-validation.spec.mjs`). Ядро додає чисте правило `bookResumeInRow` з тестом, а підключає його harness-план разом із «Продовжити валідацію» в панелі.
- **Р2. Що вважається «запуском з цієї вкладки».** Подія `run-enqueued` не міжвкладкова: її шлють обробники цієї ж сторінки (`book-validation.js`, `assisted-writing.js`, `copyedits-workspace.js`). Фокус переносять: `start()`, `resumeRun()`, `continue-after-acceptance` (це продовження з обробника), гілка «знайдено запуск» у `reconcilePrimaryOnce` (`workspace-primary-recovered`) і старт валідації книги — `book-validation.js` після POST шле `run-reveal` замість `run-enqueued`. Не переносять: `follow` при завантаженні сторінки, кнопка «Останній запуск», скасована гілка `reconcilePrimaryOnce` і `run-enqueued` від переписування й редактури: у них власні панелі перегляду в матеріалі, і перенесення фокуса вивело б автора з них.
- **Р3. Сцени при продовженні.** `scenes = len(visited) + кількість сцен із links перегляду resume, яких немає серед visited` (уточнення формули §1, Review Focus 2).
- **Р4. «Завершальний resume».** План не змінюється, коли перегляд resume має `calls == 0` (і коли запуск завершиться без виклику, і коли зупиниться знову без виклику).
- **Р5. Долари без ціни.** З межею частина «Витрачено» є завжди, з «$—», коли якийсь виклик без ціни. Без межі вона з'являється лише тоді, коли витрачено більше нуля (`spent_usd !== '0.0000'`), з «$—» за невідомої частини; локальна модель без цін її не показує зовсім і не мигає «$0.0000» до першого виклику — як каже розділ власника.
- **Р6. `progress` іде й після `stage_started`, через одну точку.** Спека каже «після кожної `stage_finished` і `audit_step`», але тоді під час виклику рядок називає попередній крок. `RunCoordinator.event` після запису `stage_started`, `stage_finished` чи `audit_step` викликає `emit_progress`. У циклі worker `stage_finished` пишеться до `cursor+=1`, тож ця подія ще показує завершене завдання; наступна `stage_started` чи `GET` після `state` дає свіже. Для зупинки `audit` checkpoint зберігається після `audit_step`, тож `stopped` у події `null`; актуальне приходить через `GET /api/runs/{id}` після події `state`.
- **Р8. Читань подій більше, ніж «одне на крок».** Через Р6 прогрес рахується до трьох разів на крок, тож кожне читання бере лише `stage_started`, `stage_finished`, `audit_step` (новий параметр `types` у `list_run_events`), а не потік `delta`.
- **Р7. Фокус «на панель» після «Перейти до сцени N».** Панелі в ядрі немає: фокус іде на `#link-attention`, якщо він видимий, інакше на `#workspace-status-row`. Harness замінює ціль на панель.

---

### Task 1: `run_progress` на сервері, поле API й подія `progress`

**Files:**
- Create: `src/storygen/generation/run_progress.py`
- Modify: `src/storygen/web/routes_runs.py` (`get_run`)
- Modify: `src/storygen/generation/worker.py` (`RunCoordinator.event` — одна точка виклику `emit_progress`)
- Modify: `src/storygen/storage/run_store.py`, `src/storygen/storage/repository.py` (`list_run_events(..., types=None)`)
- Test: `tests/generation/test_run_progress.py` (новий), `tests/web/test_runs.py`

**Interfaces:**
- Consumes: `Run` (`run_models.py`).
- Changes: `list_run_events(run_id, after_seq=0, types: tuple[str, ...] | None = None) -> list[RunEvent]` у `run_store.py` і обгортці `Repository` — `types` додає `AND type IN (...)`; без `types` поведінка та сама.
- Produces:
  - `usage_usd(usage: dict | None) -> float | None` — те саме правило, що JS `usageUsd`: `usage['cost']` число або `usage['cost']['usd']`, скінченне.
  - `visited_scene_ids(events: list[RunEvent]) -> list[str]` — різні `scene_id` з `stage_started` і `audit_step` у порядку появи, без `None`.
  - `progress_from_events(run: Run, events: list[RunEvent]) -> dict | None`
  - `PROGRESS_EVENTS = ('stage_started', 'stage_finished', 'audit_step')`.
  - `run_progress(repo, run: Run) -> dict | None` = `progress_from_events(run, repo.list_run_events(run.id, types=PROGRESS_EVENTS))`.
  - `emit_progress(coordinator, run_id: str) -> None` — `coordinator.event(run_id, 'progress', data)`, якщо `data is not None`. `RunCoordinator.event(id, type, data)` після запису викликає його, коли `type in PROGRESS_EVENTS` (Р6); подія `progress` сама його не викликає.
  - Форма словника (і `GET /api/runs/{id}['progress']`, і `RunEvent.data` події `progress`):
    ```
    {'calls': {'done': int, 'planned': int | None},
     'spent_usd': str, 'spent_known': bool, 'bound_usd': str | None,
     'scene': {'id': str | None, 'index': int | None, 'total': int | None} | None,
     'step': {'link': str} | {'stage': str} | None,
     'stopped': {'scene_id': str, 'link': str, 'outcome': str} | None}
    ```

Правила `progress_from_events` (зі спеки §2):
- `memory_carry` → `None`.
- `calls.done` — кількість різних `attempt_id` у `stage_finished`; `calls.planned` — `planned_telemetry.calls` (без плану — `None`).
- `spent_usd` — сума `Decimal(str(usage_usd))` за різними `attempt_id`, `ROUND_HALF_UP` до `0.0001`, `'0.0000'` без викликів; `spent_known` — `False`, якщо хоч один такий виклик дає `None`; `bound_usd` — `planned_telemetry.cost_bound_usd`.
- `audit`, `story`: `scene.id` — останній `scene_id` з `stage_started`/`audit_step`, `index = len(visited_scene_ids)`, `total = planned_telemetry.scenes`; без подій — `{'id': None, 'index': 0, 'total': N}`. `audit`, `scene`: `{'id': request.scene_id, 'index': 1, 'total': 1}`. `step` — `{'link': ...}` з останньої `stage_started`/`audit_step` або `None`.
- Генерація: завдання `tasks[min(cursor, len(tasks)-1)]` (порожні `tasks` → `scene` і `step` `None`); `step = {'stage': task['stage']}`; `scene` — `None`, якщо `task['scene_id']` порожній, інакше номер серед різних непорожніх `scene_id` у `tasks` (з 1) і їхня кількість.
- `stopped` — `{scene_id, link, outcome}` з `run.checkpoint`, коли `run.state == 'needs_review'` і checkpoint має `scene_id`; інакше `None`.

- [ ] **Step 1: Написати тести, що падають** (`tests/generation/test_run_progress.py`; хелпери `four_scenes`, `start_book`, `drive`, `Answers`, `DISCREPANCY`, `answer` — з `tests.generation.test_audit_run`; `ready`, `BlockingGateway` — з `tests.generation.test_worker`; `seeded`, `patch` — з `tests.generation.test_editor_loop`)

```python
def test_progress_counts_calls_and_spent_once_per_attempt(tmp_path):
    repo, story, (s1, s2, s3, s4), _ = four_scenes(tmp_path)
    worker, run = start_book(repo, story, Answers(answer(95)))
    run.planned_telemetry = {**run.planned_telemetry, 'scenes': 2, 'cost_bound_usd': '0.0618'}
    repo.save_run(run)
    worker.event(run.id, 'stage_started', {'stage': 'audit_prose', 'scene_id': s2.id, 'link': 'prose'})
    for _ in range(2):  # a replayed event counts once
        worker.event(run.id, 'stage_finished', {'attempt_id': 'a1', 'state': 'completed', 'usage': {'cost': 0.012}})
    worker.event(run.id, 'stage_finished', {'attempt_id': 'a2', 'state': 'completed', 'usage': {'cost': {'usd': 0.0031}}})
    progress = run_progress(repo, repo.get_run(run.id))
    assert progress['calls'] == {'done': 2, 'planned': 2}
    assert (progress['spent_usd'], progress['spent_known'], progress['bound_usd']) == ('0.0151', True, '0.0618')
    assert progress['scene'] == {'id': s2.id, 'index': 1, 'total': 2} and progress['step'] == {'link': 'prose'}

def test_a_call_without_a_price_makes_spent_unknown(tmp_path):
    # same setup, one stage_finished with usage {'cost': 0.01}, one with usage {}
    assert progress['spent_known'] is False and progress['spent_usd'] == '0.0100'

def test_progress_without_events_is_zero(tmp_path):
    # four_scenes + start_book, no driving
    assert progress['calls'] == {'done': 0, 'planned': 2}
    assert (progress['spent_usd'], progress['spent_known']) == ('0.0000', True)
    assert progress['scene']['index'] == 0 and progress['step'] is None and progress['stopped'] is None

def test_book_stop_emits_progress_after_each_step_and_names_the_stop(tmp_path):
    repo, story, (s1, s2, s3, s4), _ = four_scenes(tmp_path)
    worker, run = start_book(repo, story, Answers(answer(95)))
    run = drive(worker, run.id)
    types = [e.type for e in worker.list_events(run.id)
             if e.type in {'stage_started', 'audit_step', 'stage_finished', 'progress'}]
    assert types == ['stage_started', 'progress', 'audit_step', 'progress', 'stage_finished', 'progress',
                     'audit_step', 'progress']
    progress = run_progress(repo, run)  # Р6: the stop is read from the saved run, not from the event
    assert progress['stopped'] == {'scene_id': s3.id, 'link': 'brief', 'outcome': 'discrepancy'}
    assert progress['scene']['id'] == s3.id and progress['scene']['index'] == 2 and progress['calls']['done'] == 1

def test_progress_after_stage_started_names_the_current_link(tmp_path):
    repo, story, (s1, s2, s3, s4), _ = four_scenes(tmp_path)
    worker, run = start_book(repo, story, Answers(answer(95)))
    drive(worker, run.id)
    events = worker.list_events(run.id)
    started = next(i for i, e in enumerate(events) if e.type == 'stage_started')
    during = events[started + 1]
    assert during.type == 'progress'
    assert during.data['step'] == {'link': 'prose'} and during.data['scene']['id'] == s2.id
    assert during.data['calls']['done'] == 0

def test_generation_progress_names_the_scene_and_stage_of_the_cursor():
    tasks = [{'scene_id': 'a', 'stage': 'brief'}, {'scene_id': 'a', 'stage': 'draft'},
             {'scene_id': 'b', 'stage': 'brief'}, {'scene_id': 'b', 'stage': 'draft'}]
    run = Run(id='r', story_id='s', request_id='q', tasks=tasks, cursor=2,
              request=RunRequest(story_id='s', scene_id='a', mode='remaining'), planned_telemetry={'roles': {}, 'calls': 4})
    progress = progress_from_events(run, [])
    assert progress['scene'] == {'id': 'b', 'index': 2, 'total': 2} and progress['step'] == {'stage': 'brief'}
    assert progress_from_events(run.model_copy(update={'cursor': 4}), [])['step'] == {'stage': 'draft'}  # completed: last task
    prepare = run.model_copy(update={'tasks': [{'scene_id': None, 'stage': 'prepare'}], 'cursor': 0})
    assert progress_from_events(prepare, [])['scene'] is None
    assert progress_from_events(prepare, [])['bound_usd'] is None

def test_memory_carry_has_no_progress():
    run = Run(id='r', story_id='s', request_id='q', tasks=[],
              request=RunRequest(story_id='s', scene_id='a', mode='memory_carry'))
    assert progress_from_events(run, []) is None

def test_stage_run_emits_progress_after_the_cursor_moves(tmp_path):
    repo, story, scene = ready(tmp_path)
    gateway = BlockingGateway(); gateway.release.set()
    worker = RunCoordinator(repo, lambda _: gateway)
    run = worker.enqueue(RunRequest(story_id=story.id, scene_id=scene.id, mode='stage', stage='brief'), 'brief')
    drive(worker, run.id)
    events = worker.list_events(run.id)
    finished = next(i for i, e in enumerate(events) if e.type == 'stage_finished')
    progress = events[finished + 1]
    assert progress.type == 'progress' and progress.data['calls'] == {'done': 1, 'planned': 1}
    assert events[-1].type == 'state'  # the closing state event stays last

def test_editor_loop_pass_emits_progress(tmp_path):
    repo, scene, draft, worker, run, calls = seeded(tmp_path, ['{"edits":[]}'])
    worker._execute(run.id)
    events = worker.list_events(run.id)
    steps = sum(e.type in {'stage_started', 'stage_finished'} for e in events)
    assert sum(e.type == 'progress' for e in events) == steps >= 2
```

У `tests/web/test_runs.py`:

```python
def test_get_run_includes_progress(tmp_path):
    # create_app + TestClient as in test_run_preserves_planned_model_metadata_across_settings_changes; enqueue stage brief
    body = client.get(f'/api/runs/{run.id}').json()
    assert body['progress']['calls'] == {'done': 0, 'planned': 1}
    assert body['progress']['step'] == {'stage': 'brief'} and body['progress']['stopped'] is None
```

- [ ] **Step 2: Запустити й переконатися, що падають**

Run: `PYTEST t1 tests/generation/test_run_progress.py tests/web/test_runs.py::test_get_run_includes_progress`
Expected: FAIL — `ModuleNotFoundError: storygen.generation.run_progress` / `KeyError: 'progress'`.

- [ ] **Step 3: Реалізувати `run_progress.py`** за інтерфейсом і правилами вище.

- [ ] **Step 4: Підключити `progress`**
  - `list_run_events(..., types=None)` у `run_store.py` і `Repository`.
  - `RunCoordinator.event`: після `self.repo.append_run_event(...)` — `emit_progress(self, id)`, коли `type in PROGRESS_EVENTS`; повертає записану подію, як раніше. `self.condition` — `RLock`, тож виклик зсередини `with self.condition` безпечний.
  - `routes_runs.get_run`: `'progress': run_progress(worker.repo, run)` у відповіді.

- [ ] **Step 5: Запустити тести задачі й сусідні**

Run: `PYTEST t1 tests/generation/test_run_progress.py tests/web/test_runs.py tests/generation/test_audit_run.py tests/generation/test_worker.py tests/generation/test_editor_loop.py tests/generation/test_run_closure.py tests/generation/test_rewrite_queue.py tests/evaluation/test_evaluation_language.py tests/web/test_resumed_events.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/storygen/generation/run_progress.py src/storygen/web/routes_runs.py src/storygen/generation/worker.py src/storygen/storage/run_store.py src/storygen/storage/repository.py tests/generation/test_run_progress.py tests/web/test_runs.py
git commit -m "feat(runs): прогрес запуску на сервері — run_progress, поле API й подія progress"
```

---

### Task 2: План запуску — межа, сцени й доповнення при продовженні

**Files:**
- Modify: `src/storygen/generation/run_progress.py` (додати `extend_plan`)
- Modify: `src/storygen/generation/worker.py` (`enqueue`: `telemetry`; `resume`: після перевірки `result['ready']`)
- Test: `tests/generation/test_run_progress.py`, `tests/generation/test_audit_run.py` (рядки 180 і 477 — очікуваний словник плану)

**Interfaces:**
- Consumes: `progress_from_events`, `visited_scene_ids` (задача 1); результат `self.run_readiness(id)` — для `audit` має `calls`, `cost.total_usd`, `links[].scene_id` (книга).
- Produces: `extend_plan(plan: dict | None, progress: dict, readiness: dict, visited: list[str]) -> dict | None`:
  - `plan is None` → `None`; `readiness.get('calls', 0) == 0` → `plan` без змін (Р4).
  - Інакше копія `plan` з `calls = progress['calls']['done'] + readiness['calls']`.
  - Якщо ключ `cost_bound_usd` є в `plan`: `Decimal(spent_usd) + Decimal(total_usd)`, `ROUND_CEILING` до `0.0001`, рядок; або `None`, коли `progress['spent_known']` хибне чи `total_usd` відсутній.
  - Якщо ключ `scenes` є в `plan`: `len(visited) + len({scene_id із readiness['links']} - set(visited))` (Р3).
  - Ключів, яких не було в `plan`, не додає.

- [ ] **Step 1: Написати тести, що падають**

```python
def test_extend_plan_rules():
    plan = {'roles': {}, 'calls': 4, 'cost_bound_usd': '2.1000', 'scenes': 16}
    done = {'calls': {'done': 5, 'planned': 4}, 'spent_usd': '0.0200', 'spent_known': True}
    resume = {'calls': 3, 'cost': {'total_usd': '0.3000'},
              'links': [{'scene_id': 's5'}, {'scene_id': 's6'}, {'scene_id': 's6'}]}
    visited = ['s1', 's2', 's3', 's4', 's5']
    assert extend_plan(plan, done, resume, visited) == {'roles': {}, 'calls': 8, 'cost_bound_usd': '0.3200', 'scenes': 6}
    assert extend_plan(plan, {**done, 'spent_known': False}, resume, visited)['cost_bound_usd'] is None
    assert extend_plan(plan, done, {**resume, 'cost': {'total_usd': None}}, visited)['cost_bound_usd'] is None
    assert extend_plan(plan, done, {**resume, 'calls': 0}, visited) == plan
    assert extend_plan(None, done, resume, visited) is None
    assert extend_plan({'roles': {}, 'calls': 3}, {**done, 'calls': {'done': 1, 'planned': 3}}, {'calls': 2}, []) == {'roles': {}, 'calls': 3}

def test_enqueue_stores_the_cost_bound_and_scenes_of_the_preview(tmp_path, monkeypatch):
    repo, story, (s1, s2, s3, s4), _ = four_scenes(tmp_path)
    worker, run = start_book(repo, story, Answers(answer(95)))
    assert run.planned_telemetry == {'roles': {'auditor': {'provider': 'local', 'model': 'auditor'}}, 'calls': 2,
                                     'cost_bound_usd': None, 'scenes': 2}
    monkeypatch.setattr('storygen.generation.audit_cost.upper_bound',
                        lambda repo, settings, calls: {'per_call_usd': '0.0309', 'total_usd': '0.0618', 'reason': None})
    # a fresh four_scenes in tmp_path / 'priced', start_book
    assert run.planned_telemetry['cost_bound_usd'] == '0.0618'

def test_resume_extends_the_plan_without_counting_a_visited_scene_twice(tmp_path):
    repo, story, (s1, s2, s3, s4), _ = four_scenes(tmp_path)
    worker, run = start_book(repo, story, Answers(answer(95)))
    assert drive(worker, run.id).checkpoint['scene_id'] == s3.id  # one call (s2 prose), stop on s3 brief
    decide_link(repo, s3.id, 'brief', 'approve', link_state(repo.context_view(story.id), s3.id, 'brief').fingerprint)
    resumed = worker.resume(run.id)
    # resume preview: s3 prose → 1 call; s3 already visited; the local auditor has no price
    assert resumed.planned_telemetry == {'roles': {'auditor': {'provider': 'local', 'model': 'auditor'}}, 'calls': 2,
                                         'cost_bound_usd': None, 'scenes': 2}
    assert repo.get_run(run.id).planned_telemetry == resumed.planned_telemetry

def test_finishing_resume_keeps_the_plan(tmp_path):
    # flow of test_approving_the_last_link_lets_the_run_complete_on_resume: scene audit, approve the last link
    before = repo.get_run(run.id).planned_telemetry
    worker.resume(run.id)
    assert repo.get_run(run.id).planned_telemetry == before
```

Оновити очікування в `tests/generation/test_audit_run.py`: рядок 180 — додати `'cost_bound_usd': None`; рядок 477 — додати `'cost_bound_usd': None, 'scenes': 2`. Це навмисна зміна плану запуску (спека §1), а не регресія.

- [ ] **Step 2: Запустити й переконатися, що падають**

Run: `PYTEST t2 tests/generation/test_run_progress.py tests/generation/test_audit_run.py`
Expected: FAIL — `ImportError: extend_plan`, словник плану без нових ключів.

- [ ] **Step 3: Реалізувати**
  - `enqueue`: коли `request.mode == 'audit'`, `telemetry['cost_bound_usd'] = readiness['cost']['total_usd']`; коли ще й `audit_scope == 'story'`, `telemetry['scenes'] = readiness['invalid_scenes']`.
  - `run_progress.extend_plan` за інтерфейсом.
  - `resume`: після `if not result['ready']: raise ...` — один `events = self.repo.list_run_events(id)`; якщо `progress_from_events(run, events)` не `None`, `run.planned_telemetry = extend_plan(run.planned_telemetry, progress, result, visited_scene_ids(events))`; далі наявний `requeue_run(run)` зберігає payload разом із планом.

- [ ] **Step 4: Запустити тести**

Run: `PYTEST t2 tests/generation/test_run_progress.py tests/generation/test_audit_run.py tests/web/test_runs.py tests/generation/test_worker.py tests/web/test_audit_preview_api.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/storygen/generation/run_progress.py src/storygen/generation/worker.py tests/generation/test_run_progress.py tests/generation/test_audit_run.py
git commit -m "feat(runs): план запуску зберігає межу вартості й сцени та доповнюється при продовженні"
```

---

### Task 3: Чисті правила клієнта — текст прогресу, розгортання, меню, i18n

**Files:**
- Create: `src/storygen/web/static/run-progress.js`
- Modify: `src/storygen/web/static/run-summary.js` (`runExpanded`, `syncRunPrefs`, `toggleRunExpansion`; експорт `dollars`)
- Modify: `src/storygen/web/static/book-validation-state.js` (`bookMenuState`, нові `latestBookRun`, `bookResumeInRow`)
- Modify: `src/storygen/web/static/i18n.json`
- Test: `tests/web/js/run_progress.mjs` (новий), `tests/web/test_run_progress_ui.py` (новий), `tests/web/js/run_summary.mjs`, `tests/web/js/book_validation.mjs`, `tests/web/test_book_validation_ui.py`

**Interfaces:**
- Consumes: форма `progress` (задача 1); `t` з `./i18n.js`; `stoppedAuditScene` з `./run-summary.js`.
- Produces:
  - `run-summary.js`: `export const dollars=value=>…` (наявне правило: `< 0.01` — 4 знаки, інакше 2). `runExpanded`/`syncRunPrefs`/`toggleRunExpansion` вважають `needs_review` таким самим станом розкриття, як `failed` (`collapsedFailure` без перейменування).
  - `run-progress.js`: `progressText(run, progress, scenes) -> {title: string, step: string, counts: string, fraction: number | null} | null` (`null` для `progress == null`).
  - `book-validation-state.js`:
    - `latestBookRun(runs, current) -> run | null` — остання з `runs` з `request.mode==='audit' && request.audit_scope==='story'`; той самий `id`, що в `current`, замінюється на `current`; `current`-валідація книги, якої ще немає в `runs`, повертається сама.
    - `bookMenuState(count, bookRun=null)` — `bookRun.state ∈ {queued, running, pause_requested, cancellation_requested}` → `{key:'book_validation.menu_running', params:{}, disabled:true}`; `∈ {paused, needs_review}` → `{key:'book_validation.menu_stopped', params:{}, disabled:false, show:true}`; інакше — наявні три результати без змін (форма без `show`, тож чинні `deepEqual` лишаються).
    - `bookResumeInRow(run, scenes) -> boolean` — `false` лише для валідації книги в `needs_review`, чия сцена зупинки є (`stoppedAuditScene` не `null`). У ядрі не підключається (Р1).

Правила `progressText` (§3, Р5):
- `title`: книга без сцени (`scene.index === 0` або `scene.id` порожній) — `t('run.mode_audit_book')`; книга з `total` і `index <= total` — `run_progress.book_scene {p0:index, p1:total, p2:назва}`; інакше `run_progress.book_scene_open {p0:index, p1:назва}`; перевірка сцени — `run_progress.scene_audit {p0:назва}`; генерація зі сценою — `run_progress.generation {p0:index, p1:total, p2:етап}`; без сцени — `run_progress.stage_only {p0:етап}`. Назва — `scenes.find(id).title`, без сцени в поданні — `'—'`. Етап — `run_progress.stage_<stage>` для `brief|draft|edit|memory|evaluate`, інакше сирий `stage`.
- `step`: `run_progress.link_<link>` для `audit`; для генерації `''`.
- `counts`: `run_progress.calls {p0:done, p1:planned}` або `run_progress.calls_open {p0:done}` без `planned`; через ` · ` — `run_progress.spent_bound {p0, p1}` з межею (завжди), `run_progress.spent {p0}` без межі лише при `spent_usd !== '0.0000'` (Р5); `p0` — `dollars(Number(spent_usd))` або `'$—'` при `spent_known === false`, `p1` — `dollars(Number(bound_usd))`.
- `fraction`: `min(1, max(0, done / planned))` при `planned > 0`, інакше `null`.

Ключі i18n (uk / en):

| Ключ | uk | en |
|---|---|---|
| `run_progress.book_scene` | Валідація книги: сцена {p0} з {p1}, «{p2}» | Book validation: scene {p0} of {p1}, “{p2}” |
| `run_progress.book_scene_open` | Валідація книги: сцена {p0}, «{p1}» | Book validation: scene {p0}, “{p1}” |
| `run_progress.scene_audit` | Перевірка сцени «{p0}» | Scene check: “{p0}” |
| `run_progress.generation` | Сцена {p0} з {p1}, етап: {p2} | Scene {p0} of {p1}, stage: {p2} |
| `run_progress.stage_only` | Етап: {p0} | Stage: {p0} |
| `run_progress.link_brief` / `_prose` / `_memory` | завдання ↔ план / проза ↔ завдання / пам'ять ↔ проза | brief ↔ plan / prose ↔ brief / memory ↔ prose |
| `run_progress.stage_brief` / `_draft` / `_edit` / `_memory` / `_evaluate` | завдання / чернетка / редактура / пам'ять / оцінювання | brief / draft / edit / memory / evaluation |
| `run_progress.calls` / `run_progress.calls_open` | Викликів: {p0} / {p1} / Викликів: {p0} | Calls: {p0} / {p1} / Calls: {p0} |
| `run_progress.spent_bound` / `run_progress.spent` | Витрачено: {p0} з {p1} (верхня межа) / Витрачено: {p0} | Spent: {p0} of {p1} (upper bound) / Spent: {p0} |
| `book_validation.menu_running` | Валідація триває… | Validation in progress… |
| `book_validation.menu_stopped` | Валідацію зупинено: показати | Validation stopped: show |
| `book_validation.cancel` | Скасувати валідацію | Cancel validation |

- [ ] **Step 1: Написати тести, що падають**

`tests/web/js/run_progress.mjs` (за зразком `book_validation.mjs`, корінь у `process.argv[2]`):

```js
const book={id:'r',state:'running',request:{mode:'audit',audit_scope:'story'}};
const scenes=[{id:'s5',title:'Назва',position:4}];
const base={calls:{done:5,planned:23},spent_usd:'0.0200',spent_known:true,bound_usd:'2.1000',
  scene:{id:'s5',index:5,total:16},step:{link:'brief'},stopped:null};
let view=progressText(book,base,scenes);
assert.equal(view.title,'Валідація книги: сцена 5 з 16, «Назва»');
assert.equal(view.step,'завдання ↔ план');
assert.equal(view.counts,'Викликів: 5 / 23 · Витрачено: $0.02 з $2.10 (верхня межа)');
assert.ok(Math.abs(view.fraction-5/23)<1e-9);
assert.equal(progressText(book,{...base,scene:{id:'s5',index:17,total:16}},scenes).title,'Валідація книги: сцена 17, «Назва»');
assert.equal(progressText(book,{...base,scene:{id:'s5',index:5,total:null}},scenes).title,'Валідація книги: сцена 5, «Назва»');
assert.equal(progressText(book,{...base,scene:{id:null,index:0,total:16},step:null},scenes).title,'Валідація книги');
assert.equal(progressText(book,{...base,scene:{id:'gone',index:2,total:16}},scenes).title,'Валідація книги: сцена 2 з 16, «—»');
assert.equal(progressText(book,{...base,bound_usd:null},scenes).counts,'Викликів: 5 / 23 · Витрачено: $0.02');
assert.equal(progressText(book,{...base,spent_known:false},scenes).counts,'Викликів: 5 / 23 · Витрачено: $— з $2.10 (верхня межа)');
assert.equal(progressText(book,{...base,spent_usd:'0.0000',spent_known:false,bound_usd:null},scenes).counts,'Викликів: 5 / 23');  // Р5: local, no price
assert.equal(progressText(book,{...base,calls:{done:0,planned:23},spent_usd:'0.0000',spent_known:true,bound_usd:null},scenes).counts,'Викликів: 0 / 23');  // no «$0.0000» before the first call
assert.equal(progressText(book,{...base,spent_usd:'0.0100',spent_known:false,bound_usd:null},scenes).counts,'Викликів: 5 / 23 · Витрачено: $—');
assert.equal(progressText(book,{...base,calls:{done:0,planned:23},spent_usd:'0.0000'},scenes).counts,'Викликів: 0 / 23 · Витрачено: $0.0000 з $2.10 (верхня межа)');
const open=progressText(book,{...base,calls:{done:5,planned:null}},scenes);
assert.equal(open.fraction,null);assert.match(open.counts,/^Викликів: 5 · /);
assert.equal(progressText(book,{...base,calls:{done:30,planned:23}},scenes).fraction,1);
const sceneCheck={...book,request:{mode:'audit',audit_scope:'scene',scene_id:'s5'}};
assert.equal(progressText(sceneCheck,{...base,scene:{id:'s5',index:1,total:1},step:{link:'memory'}},scenes).step,'пам\'ять ↔ проза');
assert.equal(progressText(sceneCheck,{...base,scene:{id:'s5',index:1,total:1}},scenes).title,'Перевірка сцени «Назва»');
const gen={id:'g',state:'running',request:{mode:'remaining'}};
view=progressText(gen,{...base,bound_usd:null,scene:{id:'s5',index:3,total:10},step:{stage:'draft'}},scenes);
assert.equal(view.title,'Сцена 3 з 10, етап: чернетка');assert.equal(view.step,'');
assert.equal(progressText(gen,{...base,scene:null,step:{stage:'prepare'}},scenes).title,'Етап: prepare');
assert.equal(progressText(gen,null,scenes),null);
```

`tests/web/js/run_summary.mjs` — додати:

```js
const review={id:'r5',state:'needs_review'};let p={expandedRun:null,collapsedFailure:null};
assert.equal(runExpanded(review,p),true,'needs_review opens once by itself');
p=toggleRunExpansion(review,p);assert.equal(runExpanded(review,p),false,'the author collapses it');
p=syncRunPrefs({id:'r5',state:'queued'},p);assert.equal(runExpanded({id:'r5',state:'running'},p),false);
assert.equal(runExpanded({id:'r5',state:'needs_review'},p),true,'the next stop opens it again');
```

`tests/web/js/book_validation.mjs` — додати (після імпорту `latestBookRun`, `bookResumeInRow`):

```js
const bookRun=(id,state)=>({id,state,request:{mode:'audit',audit_scope:'story'},checkpoint:{scene_id:'s1'}});
const gen={id:'g',state:'paused',request:{mode:'scene'}};
assert.deepEqual(bookMenuState(2,bookRun('b','running')),{key:'book_validation.menu_running',params:{},disabled:true});
assert.deepEqual(bookMenuState(2,bookRun('b','needs_review')),{key:'book_validation.menu_stopped',params:{},disabled:false,show:true});
assert.deepEqual(bookMenuState(2,bookRun('b','paused')),{key:'book_validation.menu_stopped',params:{},disabled:false,show:true});
assert.deepEqual(bookMenuState(2,bookRun('b','failed')),{key:'book_validation.menu_count',params:{p0:2},disabled:false});
assert.equal(latestBookRun([bookRun('b','needs_review'),gen],gen).id,'b','a later generation run does not hide the stopped validation');
assert.equal(latestBookRun([bookRun('b','running')],bookRun('b','needs_review')).state,'needs_review','the fuller current run wins');
assert.equal(latestBookRun([],bookRun('n','queued')).id,'n');
assert.equal(latestBookRun([gen],gen),null);
const stopScenes=[{id:'s1',position:0}];
assert.equal(bookResumeInRow({...bookRun('b','needs_review')},stopScenes),false);
assert.equal(bookResumeInRow({...bookRun('b','needs_review')},[]),true,'the stop scene is in the trash');
assert.equal(bookResumeInRow(gen,stopScenes),true);
```

`tests/web/test_run_progress_ui.py`:

```python
def test_run_progress_rules():  # runner as in test_book_validation_ui.test_book_validation_helpers, file run_progress.mjs

def test_run_progress_texts_exist_in_both_languages():
    keys = ['run_progress.book_scene', 'run_progress.book_scene_open', 'run_progress.scene_audit', 'run_progress.generation',
            'run_progress.stage_only', 'run_progress.link_brief', 'run_progress.link_prose', 'run_progress.link_memory',
            'run_progress.stage_brief', 'run_progress.stage_draft', 'run_progress.stage_edit', 'run_progress.stage_memory',
            'run_progress.stage_evaluate', 'run_progress.calls', 'run_progress.calls_open', 'run_progress.spent_bound',
            'run_progress.spent', 'book_validation.menu_running', 'book_validation.menu_stopped', 'book_validation.cancel']
    # both locales have every key, and each locale's placeholders {pN} match the uk value
```

- [ ] **Step 2: Запустити й переконатися, що падають**

Run: `PYTEST t3 tests/web/test_run_progress_ui.py tests/web/test_run_status_collapse_ui.py::test_run_summary_rules tests/web/test_book_validation_ui.py`
Expected: FAIL — немає модуля `run-progress.js`, `needs_review` не розгортається, немає `latestBookRun`, немає ключів.

- [ ] **Step 3: Реалізувати** `run-progress.js`, зміни `run-summary.js` і `book-validation-state.js`, ключі в `i18n.json` (обидві мови).

- [ ] **Step 4: Запустити тести**

Run: `PYTEST t3 tests/web/test_run_progress_ui.py tests/web/test_run_status_collapse_ui.py tests/web/test_book_validation_ui.py tests/web/test_resumed_events.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/storygen/web/static/run-progress.js src/storygen/web/static/run-summary.js src/storygen/web/static/book-validation-state.js src/storygen/web/static/i18n.json tests/web/js/run_progress.mjs tests/web/js/run_summary.mjs tests/web/js/book_validation.mjs tests/web/test_run_progress_ui.py
git commit -m "feat(ui): правила тексту прогресу, розгортання needs_review і станів меню валідації"
```

---

### Task 4: Рядок запуску й пункт меню в браузері

**Files:**
- Modify: `src/storygen/web/static/runs.js`
- Modify: `src/storygen/web/static/book-validation.js`
- Modify: `src/storygen/web/static/app.css` (`.run-progress*`, `.link-button`)
- Test: `tests/web/browser/book-validation.spec.mjs`, `tests/web/test_run_progress_ui.py`

**Interfaces:**
- Consumes: `progressText` (задача 3), `bookMenuState`, `latestBookRun` (задача 3), `GET /api/runs/{id}['progress']` і подія `progress` (задача 1).
- Produces (DOM і події, на які спиратиметься harness):
  - Блок `.run-progress.run-detail` у `#run-status`: `.run-progress-title` (`tabindex="-1"`), `.run-progress-step` (немає при порожньому кроці), `<progress class="run-progress-bar" max="1">` (немає при `fraction == null`), `.run-progress-counts`, `.run-progress-model.muted` (моделі плану `provider / model`, як у наявному рядку плану). Блок замінює абзац «План: …», коли `progress` відомий; згорнутий вигляд — наявний підсумок.
  - `follow(run, {reveal=false}={})`; `revealRun()` — `runPrefs.expandedRun=active.id`, `applyExpanded`, `#workspace-status-row` `scrollIntoView({block:'nearest', behavior: reduce?'auto':'smooth'})` (`reduce` — `matchMedia?.('(prefers-reduced-motion: reduce)')?.matches`), фокус на `.run-progress-title`, інакше на `.run-summary`, з `preventScroll:true`. Виклики `scrollIntoView`, `focus`, `matchMedia`, `document.activeElement` захищені `?.` — Node-мок `runs_follow.mjs` їх не має.
  - Подія документа `run-reveal` (`detail`: короткий або повний запуск): той самий запуск, що `active`, → `revealRun()`; інакше `follow(detail, {reveal:true})`.

Поведінка `runs.js`:
- Стан модуля `runProgress = {runId, data}` оновлюють `saved.progress` і `current.progress` з `GET /api/runs/{id}` у `follow` та обробнику `state`, а також подія `progress` (`event.data`). `draw(run)` з голим `Run` (відповіді pause/cancel) бере `runProgress`, якщо `runId === run.id`.
- Подія `progress` оновлює вузли блоку на місці (`textContent`, `value`), не перемальовуючи `#run-status`, тож фокус лишається.
- `draw()`: якщо перед `replaceChildren()` фокус був на `.run-progress-title` у `#run-status`, після побудови фокус повертається на новий заголовок (`preventScroll:true`) — Review Focus 1.
- Рядки `stage_started` (`stage · model · provider`) додаються, лише коли для цього запуску `runProgress` порожній.
- `reveal:true` передають (Р2): `start()` після успішного POST, `resumeRun()`, обробник `continue-after-acceptance`, гілка «знайдено» в `reconcilePrimaryOnce`, слухач `run-reveal`. Слухач `run-enqueued` лишається без `reveal`. `revealRun()` викликається після `draw(saved.run)` у `follow`; `expandedRun` можна поставити ще перед першим `draw`.
- `needs_review` валідації книги: кнопка «Скасувати» в `#run-actions` має текст `t('book_validation.cancel')` і клас `link-button` замість `secondary`; для інших запусків — наявні текст і клас. «Продовжити» не ховається (Р1).

Поведінка `book-validation.js`:
- `renderMenu`: `bookMenuState(count, latestBookRun(state.workspaceRuns, lastRun || state.workspaceRun))`; `disabled = menu.disabled || busy || (!menu.show && ACTIVE_RUN.has(state.workspaceRun?.state))`; перемальовується й на `workspace-readiness` (тоді оновлюється `state.workspaceRuns`).
- Клік: `menu.show` → `document.dispatchEvent(new CustomEvent('run-reveal', {detail: bookRun}))`, запуску немає; інакше наявний `validate()`.
- `validate()` після успішного `POST /api/runs` шле `run-reveal` з новим запуском замість `run-enqueued` (Р2).
- `#run-stop-scene`: видимий — клас без `secondary` (стиль primary); клік — `selectScene(scene)`, далі фокус на `#link-attention` (`tabindex=-1`), якщо він не `hidden`, інакше на `#workspace-status-row` (Р7).

- [ ] **Step 1: Написати тести, що падають**

У `book-validation.spec.mjs`, перший тест, після кліку «Почати валідацію» й `needs_review` (замість наявних перевірок до `jump`):

```js
const status=page.locator('#run-status'),title=status.locator('.run-progress-title');
await expect(status).toHaveClass(/expanded/);
await expect(title).toHaveText('Валідація книги: сцена 1 з 2, «Ранок»');
await expect(status.locator('.run-progress-step')).toHaveText('завдання ↔ план');
await expect(status.locator('.run-progress-counts')).toHaveText(/^Викликів: 1 \/ 4/);
await expect(status.locator('progress.run-progress-bar')).toHaveAttribute('value','0.25');
await expect(title).toBeFocused();  // Review Focus 1: survives the redraws of queued → running → needs_review
const cancel=page.locator('#run-actions').getByRole('button',{name:'Скасувати валідацію'});
await expect(cancel).toHaveClass(/link-button/);
await expect(jump).not.toHaveClass(/secondary/);
// The menu leads to the stopped run and starts nothing.
await page.locator('#editor').focus();
await toggle.click();
await expect(item).toHaveText('Валідацію зупинено: показати');
await item.click();
await expect(title).toBeFocused();
expect((await runs()).length).toBe(1);
// A page load opens the stopped run (needs_review) but does not move the focus.
await page.reload();
await expect(page.locator('#run-status')).toHaveClass(/expanded/);
await expect(page.locator('#run-status .run-progress-title')).not.toBeFocused();
```

Після продовження й `completed` (Review Focus 2):

```js
await expect(page.locator('#run-status .run-progress-title')).toHaveText('Валідація книги: сцена 2 з 2, «Вечір»');
await expect(page.locator('#run-status .run-progress-counts')).toHaveText(/^Викликів: \d \/ 4/);
```

У `tests/web/test_run_progress_ui.py` — статична перевірка розмітки, яку Playwright бачить лише через поведінку:

```python
def test_runs_render_progress_and_reveal_only_runs_started_here():
    runs = (STATIC / 'runs.js').read_text(encoding='utf-8')
    assert "from './run-progress.js'" in runs and "event.type==='progress'" in runs
    assert "'run-reveal'" in runs and 'prefers-reduced-motion' in runs
    page_load = runs.rsplit("api(`/api/stories/${state.storyId}/runs`).then(", 1)[1].split('\n', 1)[0]
    assert 'reveal' not in page_load  # the page load follows without reveal
    css = (STATIC / 'app.css').read_text(encoding='utf-8')
    assert '.run-progress' in css and '.link-button' in css
```

- [ ] **Step 2: Запустити й переконатися, що падають**

Run: `PW book-validation.spec.mjs` і `PYTEST t4 tests/web/test_run_progress_ui.py`
Expected: FAIL — немає `.run-progress-title`, рядок не розгорнутий, меню показує «Валідація книги (2)».

- [ ] **Step 3: Реалізувати** зміни `runs.js`, `book-validation.js`, `app.css` за описом вище. `.link-button` — кнопка без фону й рамки, колір `var(--accent-text)`, підкреслення, `:hover` без зміни фону. `.run-progress-bar` — ширина 100%.

- [ ] **Step 4: Запустити тести**

Run: `PW book-validation.spec.mjs`, `PW run-status-collapse.spec.mjs`, `PW save-and-run.spec.mjs`
Run: `PYTEST t4 tests/web/test_run_progress_ui.py tests/web/test_run_status_collapse_ui.py tests/web/test_resumed_events.py tests/web/test_book_validation_ui.py tests/web/test_run_jump.py tests/web/test_workspace_layout_ui.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/storygen/web/static/runs.js src/storygen/web/static/book-validation.js src/storygen/web/static/app.css tests/web/browser/book-validation.spec.mjs tests/web/test_run_progress_ui.py
git commit -m "feat(ui): розгорнутий рядок прогресу з фокусом для запуску з вкладки, меню «триває / зупинено»"
```

---

### Task 5: SPEC.MD і traceability для архітектурних змін ядра

**Files:**
- Modify: `SPEC.MD` (VALID-RUN, VALID-UI, R20-WORKSPACE; згадка `progress` у тексті про `GET /api/runs/{id}` у PERF-001 «Технічний опис і сумісність»)
- Modify: `docs/verification/traceability.json`
- Modify: `docs/verification/manual.md` (`#book-validation-browser`: нові перевірки Playwright-кейсу)
- Test: `python scripts/check_docs.py`

**Interfaces:**
- Consumes: імена тестів задач 1–4 (рядки матриці посилаються лише на наявні pytest ID).
- Produces: сценарії `VALID-RUN-S11`, `VALID-RUN-S12`, `VALID-UI-S05`, `R20-WORKSPACE-S10` з якорями `<a id="…"></a>` у стилі сусідніх.

Зміни SPEC.MD (українською, маркери OpenSpec англійською):
- **VALID-RUN, технічний опис:** `planned_telemetry` для `audit` має `cost_bound_usd` (`cost.total_usd` перегляду, на який погодився автор; рядок з 4 знаками або null), для книги — `scenes` (`invalid_scenes`); продовження доповнює план за `extend_plan` (Р3, Р4); `generation/run_progress.py::run_progress` і форма `progress`; подія `progress` після кожної `stage_started`, `stage_finished` і `audit_step` з однієї точки `RunCoordinator.event` (Р6 — навмисне розширення спеки, щоб рядок називав поточний крок); читання подій прогресу з фільтром типів (Р8); `GET /api/runs/{id}` повертає `progress`. Сумісність: ключі лише додаються, міграції немає; старі запуски без `cost_bound_usd`/`scenes`.
- **Нові сценарії:**
  - `VALID-RUN-S11 — План запуску з межею й доповнення при продовженні` (GIVEN валідація книги з переглядом; WHEN запуск ставиться в чергу, зупиняється й продовжується після рішення; THEN план має межу й сцени перегляду; AND продовження додає виклики й межу resume до зробленого, не рахуючи відвідану сцену вдруге; AND завершальне продовження без викликів лишає план).
  - `VALID-RUN-S12 — Прогрес запуску на сервері` (виклики n / N, витрачено, сцена й крок, зупинка; подія `progress` після кожного кроку; перенос пам'яті без прогресу; генерація — сцена й етап курсора).
  - `VALID-UI-S05 — Пункт меню під час і після зупинки` (триває → неактивний «Валідація триває…»; `paused`/`needs_review` → «Валідацію зупинено: показати» веде до рядка запуску без нового запуску; навіть коли поточний запуск рядка інший).
  - `R20-WORKSPACE-S10 — Розгорнутий рядок прогресу для запуску з вкладки` (розгортання, прокрутка й фокус на заголовок лише для запуску з цієї вкладки; фокус не губиться на перемальовуванні; завантаження сторінки фокус не переносить; `needs_review` розгортає рядок один раз).
- **Змінені тексти:** VALID-RUN-S09 — додати AND: меню твору не ставить валідацію поверх зупиненої `paused`/`needs_review` (VALID-UI-S05); заміну з інтерфейсу дають лише `failed`/`interrupted`, міст — як раніше. R20-WORKSPACE, абзац про згортання рядка, і S04 — `needs_review` розгортається один раз, як `failed`; запуск із вкладки розгорнутий. VALID-UI — опис `bookMenuState` зі станами `running`/`stopped` і `latestBookRun`; «Перейти до сцени N» — головна кнопка; «Скасувати валідацію» — посилання; ключі `run_progress.*`, `book_validation.menu_running|menu_stopped|cancel`.
- **Відомі обмеження (VALID-UI / R20-WORKSPACE):** старі запуски показують «Витрачено: $x» без «з $y»; прогрес видно лише в полі зору рядка; щоб почати нову валідацію поверх зупиненої, її спершу скасовують; «Продовжити» для книги поки в рядку, панель — окремий план (Р1); виклики оцінювача не входять у «Викликів: n» і «Витрачено» (оцінювання пише `evaluation_finished`, не `stage_finished`), тож запуск сцени чи «решти» з оцінюванням може закінчитися з n < N; прогрес рахується до трьох разів на крок (Р6, Р8). Прибрати чи звузити обмеження «Згода на валідацію книги не попереджає, що зупинені перевірки … буде замінено» до `failed`/`interrupted` і запусків моста.

Рядки `traceability.json` (поле `scope` — що саме доводять тести; ручна процедура — лише наявний якір `docs/verification/manual.md#book-validation-browser` з причиною «Playwright запускається окремим runner; check_docs.py індексує лише pytest IDs»):
- `VALID-RUN-S11`: `tests/generation/test_run_progress.py::test_extend_plan_rules`, `::test_enqueue_stores_the_cost_bound_and_scenes_of_the_preview`, `::test_resume_extends_the_plan_without_counting_a_visited_scene_twice`, `::test_finishing_resume_keeps_the_plan`.
- `VALID-RUN-S12`: `tests/generation/test_run_progress.py::test_progress_counts_calls_and_spent_once_per_attempt`, `::test_a_call_without_a_price_makes_spent_unknown`, `::test_progress_without_events_is_zero`, `::test_book_stop_emits_progress_after_each_step_and_names_the_stop`, `::test_progress_after_stage_started_names_the_current_link`, `::test_generation_progress_names_the_scene_and_stage_of_the_cursor`, `::test_memory_carry_has_no_progress`, `::test_stage_run_emits_progress_after_the_cursor_moves`, `::test_editor_loop_pass_emits_progress`, `tests/web/test_runs.py::test_get_run_includes_progress`.
- `VALID-UI-S05`: `tests/web/test_book_validation_ui.py::test_book_validation_helpers` + manual.
- `R20-WORKSPACE-S10`: `tests/web/test_run_progress_ui.py::test_run_progress_rules`, `::test_run_progress_texts_exist_in_both_languages`, `::test_runs_render_progress_and_reveal_only_runs_started_here`, `tests/web/test_run_status_collapse_ui.py::test_run_summary_rules` + manual.
- `VALID-RUN-S09`, `R20-WORKSPACE-S04`: оновити `scope` під змінений текст.

- [ ] **Step 1: Запустити перевірку до змін (очікувано зелена) і внести нові ID лише в матрицю**

Run: `PYTHONUTF8=1 /c/Projects/text-generator/.venv/Scripts/python.exe scripts/check_docs.py`
Expected після додавання рядків матриці без сценаріїв у SPEC: FAIL «Матриця: зайвий сценарій VALID-RUN-S11» (і так для решти).

- [ ] **Step 2: Внести зміни SPEC.MD і `manual.md`** за переліком вище.

- [ ] **Step 3: Запустити перевірку документації й повний набір тестів ядра**

Run: `PYTHONUTF8=1 /c/Projects/text-generator/.venv/Scripts/python.exe scripts/check_docs.py`
Expected: без помилок.
Run: `PYTEST t5 tests/generation/test_run_progress.py tests/generation/test_audit_run.py tests/generation/test_worker.py tests/generation/test_editor_loop.py tests/web/test_runs.py tests/web/test_audit_preview_api.py tests/web/test_run_progress_ui.py tests/web/test_run_status_collapse_ui.py tests/web/test_book_validation_ui.py tests/web/test_resumed_events.py`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add SPEC.MD docs/verification/traceability.json docs/verification/manual.md
git commit -m "docs(spec): план запуску, прогрес на сервері, рядок прогресу й стани меню валідації"
```

Після ядра: end-to-end рев'ю гілки (pr-slicing, крок 3), знахідки — у журнал виконання; лише потім harness-план (панель §4, підключення `bookResumeInRow`, сайт uk/en, знімки, `verify.py` → `docs/STATUS.md`, PR на `main`).
