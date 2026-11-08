# Швидка відповідь робочого простору — периферійний план

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Мета:** довести типові дії редактора до цілей PERF-001-S03 (≤ 1 с на 68 сценах, ≤ 3 с на синтетичних 300 сценах від кліку до відповіді) і закрити периферійну частину спеки: короткий `/runs`, згортання запитів, повна перевірка всіх операцій без багатохвилинних очікувань.

**Архітектура:** ядро (PR #36) дало `ContextView.peek_*`, один view на перевірку readiness і SQL-фільтри. Цей план (1) скорочує `/runs` разом з усіма споживачами, (2) ділить один view між усіма операціями readiness і прибирає повторні `repo.get_version` у `rebuild_memory`, (3) переводить ендпоїнти вибору сцени на один view, (4) згортає однакові одночасні GET в інтерфейсі, (5) вимірює цілі в браузері й оновлює SPEC.

**Стек:** Python 3 / FastAPI / pydantic, SQLite, ванільний JS (ES-модулі), pytest, node-тести `tests/web/js/*.mjs`, Playwright `tests/web/browser/*.spec.mjs` (`pnpm --dir frontend exec playwright test <spec>`).

**Спека:** `docs/specs/2026-11/workspace-response-speed.md` (розділи «Зміни → Периферія», «Інваріанти», «Тести»). Висновки end-to-end рев'ю ядра: `.superpowers/sdd/2026-11-08-workspace-speed-core/final-review.md` (таблиця «Deferred-minor triage», рядки «Ride»).

**Передумова:** PR #36 злитий у `main`. Гілку `claude/workspace-speed-periphery` перед Task 1 оновити з `main`; PR — лише на `main`.

## Проби, на яких стоїть план (08.11.2026, синтетичні 300 сцен `C:/tt/bench300r`, код ядра)

| Дія сервера | Час |
|---|---|
| `readiness` без `operation` (усі 9 операцій; так запитує інтерфейс при розгорнутих додаткових командах) | ≈ 111 с, з них `rebuild_memory` ≈ 102 с |
| `rebuild_memory`: `repo.get_version(prose)` на кожну з ~150 наступних сцен | ≈ 0,79 с за виклик; `view.peek_version` — ≈ 0 с |
| `repo.get_scene(id)` | 0,42 с |
| `repo.list_versions(story, scene)` | 0,42 с |
| `repo.context_view(story)` (побудова) | 0,28 с |
| `scene_status(view)` на свіжому view | 0,78 с |
| `preview(brief)` / story view | 0,85 / 1,03 с |

Запити інтерфейсу після вибору сцени (з коду слухачів `scene-selected`): `readiness?scene_id&operation` + `/runs` (`runs.js`), `/api/scenes/{id}/versions` (`versions.js`), `/api/scenes/{id}/statistics`, `/api/scenes/{id}/comments`, списки copyedits/rewrites, `/api/stories/{id}/review/...` через `review-session.js` після `/runs`.

Знахідка аудиту: `runs.js` `follow(run)` малює переданий об'єкт (`draw(run)`) до завантаження повного запуску; `draw` читає `planned_telemetry`, `error`, `warning`. З короткою формою `/runs` це показало б «план невідомий» і сховало б помилку, поки не прийде `/api/runs/{id}`.

## Global Constraints

- `/api/stories/{id}/runs` завжди повертає коротку форму; режиму сумісності й параметра для старої відповіді немає (рішення власника 08.11.2026).
- Поля короткої форми рівно: `id`, `story_id`, `request_id`, `state`, `created_at`, `request` (повний), `impact` = `{protocol, phase}` із наявних ключів або `null`. Без `tasks`, `cursor`, `error`, `warning`, `editor_loop`, `editor_loops`, `planned_telemetry`, `cancelled_before_enqueue`, повного `impact`. Повний запуск — лише `GET /api/runs/{id}`.
- Жодного кешу між HTTP-запитами (і жодного кешу відповідей в інтерфейсі після завершення запиту); кожен запит бачить власний знімок SQL.
- Внутрішні методи без копій (`peek_*`, `snapshots.freshness`) не віддають моделі коду, що їх змінює.
- Дайджест бенчмарку на 68 сценах (`--story 039b74`, копія даних) лишається `83b9f22bd9fea5d52ba8b6bbb09f9eb005ff6543b24c60a53b91a0978b9504c5`, якщо задача не змінює навмисно склад виміряних операцій; тоді звіт пояснює зміну й порівнює старий і новий код на однаковому складі.
- Робочу базу `C:\Projects\text-generator\data\storygen.sqlite3` не відкривати на запис; виміри — лише на копії (`…\scratchpad\datacopy1`) і в синтетичних теках `C:/tt/...`.
- Тексти моделі й твору в діагностиці, звітах і журналі не друкувати; лише ID, коди, агрегати.
- Документація українською; маркери OpenSpec англійською; кожен новий Scenario — сталий ID, якір `<a id="...">` і запис у `docs/verification/traceability.json`; `scripts/check_docs.py` проходить.
- Команди: `PYTHONIOENCODING=utf-8 C:/Projects/text-generator/.venv/Scripts/python.exe -m pytest …`; node — як у `tests/web/test_editor_loop_ui.py`.

## Review Focus

1. Короткий запуск потрапляє в `draw()` (через `follow`, кнопку «Останній запуск» або відкриття твору) — користувач не повинен бачити «план невідомий» чи втратити повідомлення про помилку: `follow` малює лише повний запуск. Тест — Task 1.
2. Один споживач змінює спільну відповідь згорнутого запиту — інший споживач не бачить змін: кожен отримує власну копію. Тест — Task 4.
3. Запит із `AbortSignal` поруч з однаковим запитом без сигналу — скасування одного не скасовує інший: запити із сигналом не згортаються. Тест — Task 4.
4. Спільний view для 9 операцій: операція з `MemoryApprovalRequired` або помилкою не впливає на результат наступних — результат «усі операції» дорівнює зібраним окремим запитам. Тест — Task 2.
5. Твір без вибраної сцени (`scene_id=None`) або зі сценою в кошику під час спільного view — ті самі причини відмови, що й окремі запити. Тест — Task 2.

---

### Task 1: Коротка форма `/runs` і всі її споживачі

**Files:**
- Modify: `src/storygen/run_models.py` (функція короткої форми), `src/storygen/web/routes_runs.py:37-39`
- Modify: `src/storygen/web/static/runs.js` (`follow`, кнопки `latest`/`proposal`, відкриття твору, відновлення), `src/storygen/web/static/review-session.js:126`, `src/storygen/web/static/trash.js:54`, інші споживачі, знайдені аудитом
- Test: `tests/web/test_runs_short_form.py` (новий), `tests/web/js/run_readiness.mjs`, `tests/web/js/resumed_run_events.mjs`
- Modify: `SPEC.MD` (опис API `/runs`, новий Scenario `PERF-001-S04`), `docs/verification/traceability.json`

**Interfaces:**
- Produces: `run_summary(run: Run) -> dict` у `storygen.run_models`; `GET /api/stories/{id}/runs` → `{'runs': [run_summary(r) …]}` у тому самому порядку, що й зараз.

- [ ] **Step 1: Аудит споживачів.** `grep -rn "/runs\`\|/runs'\|workspaceRuns\|historyRuns" src/storygen/web/static` і `grep -rn "list_runs\|story_runs" src tests`. Для кожного місця записати у звіт: файл:рядок, які поля читає, чи вистачає короткої форми. Хто читає поле поза формою — переходить на `GET /api/runs/{id}`; поле до форми не додається (рішення спеки).
- [ ] **Step 2: Тести API (мають падати).**

```python
def test_story_runs_returns_short_form(client_with_runs):
    runs = client.get(f'/api/stories/{story_id}/runs').json()['runs']
    assert [r['id'] for r in runs] == expected_ids_in_current_order
    for r in runs:
        assert set(r) == {'id','story_id','request_id','state','created_at','request','impact'}
        assert r['impact'] is None or set(r['impact']) <= {'protocol','phase'}

def test_run_detail_stays_full(client_with_runs):
    run = client.get(f'/api/runs/{failed_run_id}').json()['run']
    assert run['error'] and 'tasks' in run and 'planned_telemetry' in run
```

Фікстура: твір із завершеним `prepare`, пізнішим `draft`, проваленим запуском з `error`/`warning`, сесією рев'ю з `impact.protocol == 3` і запуском іншого твору.
- [ ] **Step 3: JS-тести предикатів (мають падати, де споживач читає відсутнє поле).** У `run_readiness.mjs`: `materialReason('proposal', state, runs)` дає доступну кнопку для коротких запусків `[prepare completed, draft completed]`; `materialReason('latest', …)` доступна за наявності хоча б одного запуску. У `resumed_run_events.mjs` (або новому `runs_follow.mjs`): `follow(shortRun)` не викликає `draw` з об'єктом без `planned_telemetry` — перший `draw` отримує `saved.run` з `/api/runs/{id}`. Для `review-session.js`: вибір сесії за `impact.protocol === 3` працює на короткій формі.
- [ ] **Step 4: Реалізувати** `run_summary` і маршрут; виправити `follow` (малювати лише після `/api/runs/{id}`; до відповіді — без зміни статусу) і споживачів з аудиту.
- [ ] **Step 5: Прогнати** нові тести, `tests/web -q -k "run or review or trash"` і браузерні специфікації, що відкривають запуски (`pnpm --dir frontend exec playwright test brief-proposal.spec.mjs impact.spec.mjs`). Очікувано: PASS. Розмір `/runs` на копії 68 сцен — записати у звіт (було ≈ 1 МБ).
- [ ] **Step 6: SPEC.** Опис API `/runs` — коротка форма з переліком полів; `PERF-001-S04 — Короткий список запусків` (GIVEN твір із запусками, WHEN інтерфейс запитує список, THEN відповідь містить лише поля короткої форми, а повні дані — лише `/api/runs/{id}`, і кнопки, що залежать від історії, мають ту саму доступність) → тести Step 2–3 у traceability. `check_docs.py` — PASS.
- [ ] **Step 7: Commit** `Return the short run list and move its consumers (#27)`.

### Task 2: Усі операції readiness на одному view; `rebuild_memory` без повторних знімків

**Files:**
- Modify: `src/storygen/generation/readiness.py` (`preview`, гілки `brief` і `rebuild_memory`), `src/storygen/generation/worker.py:178-194`
- Modify: `src/storygen/application/workspace_bench.py` (нова операція виміру `readiness:all`)
- Test: `tests/generation/test_readiness_single_view.py`, `tests/storage/test_context_view_readonly.py`

**Interfaces:**
- Consumes: `ContextView.peek_version(id) -> VersionRef` (ядро), `build_context(..., view=)`.
- Produces: `preview(repo, request, view: ContextView | None = None) -> dict`; `RunCoordinator.readiness(...)` без `operation` будує один `repo.context_view(story_id)` і передає його кожному `preview`.

- [ ] **Step 1: Тести (мають падати).**

```python
def test_all_operations_build_one_view(repo_with_story, count_views):
    coordinator.readiness(story_id, scene_id)          # operation=None
    assert count_views() == 1

def test_all_operations_equal_separate_requests(fixture):  # кожна фікстура нижче
    together = coordinator.readiness(story_id, scene_id)['operations']
    separate = {op: coordinator.readiness(story_id, scene_id, operation=op)['operations'][op] for op in OPERATIONS}
    assert together == separate

def test_rebuild_memory_does_not_snapshot_per_scene(repo_300ish, spy_get_version):
    preview(repo, request('rebuild_memory'))
    assert spy_get_version.calls == 0
```

Фікстури еквівалентності: налаштовані ролі й сцени з завершеною прозою; наступна сцена з незавершеною прозою (причина `rebuild_memory` з номером сцени); `scene_id=None`; вибрана сцена в кошику; етап `memory` з `MemoryApprovalRequired`. Сторож мутації: `_dumps(view)` до і після `coordinator.readiness` без `operation` на спільному view однакові.
- [ ] **Step 2: Реалізувати.** `preview(..., view=None)` бере переданий view замість `repo.context_view`; гілка `prepare` використовує той самий view. `rebuild_memory` читає `view.peek_version(head)`; `brief` для `remaining` читає план через view (`view.read_text`), якщо результат той самий, що й `repo.read_text` (перевірити тестом еквівалентності). Без view поведінка `preview` не змінюється.
- [ ] **Step 3: Прогнати** тести Step 1, `tests/generation tests/storage -q`. Очікувано: PASS.
- [ ] **Step 4: Виміряти** бенчмарк на 68 (дайджест незмінний; нова операція `readiness:all` додається поза дайджестом або звіт пояснює зміну дайджесту за Global Constraints) і на `C:/tt/bench300r`: `readiness:rebuild_memory` і `readiness:all`. Ціль: обидва ≤ 3 с на 300 сценах. Результати — у звіт і JSON у теці SDD.
- [ ] **Step 5: Commit** `Share one view across readiness operations (#27)`.

### Task 3: Ендпоїнти вибору сцени на одному view; бенчмарк міряє реальні запити

**Files:**
- Modify: `src/storygen/storage/repository.py` (`get_scene` :255, `list_versions` :310 — необов'язковий `view`), маршрути `routes_versions.py:96`, `routes_statistics.py:8`, `routes_comments.py:8`, маршрути copyedits/rewrites — лише ті, що за виміром Step 1 > 0,2 с на 300 сценах
- Modify: `src/storygen/application/workspace_bench.py` (`scene_select` через `fastapi.testclient.TestClient` на тих самих URL, що інтерфейс; захист `run()` від хибного `--data`)
- Test: `tests/storage/test_workspace_bench.py`, `tests/storage/test_context_view_readonly.py`, `tests/web/test_scene_endpoints_view.py` (новий)

**Interfaces:**
- Produces: `Repository.get_scene(id, include_trashed=False, *, view: ContextView | None = None)`, `Repository.list_versions(story_id, scene_id=None, kind=None, *, view: ContextView | None = None)`; без `view` — поточна поведінка.

- [ ] **Step 1: Виміряти** кожен URL зі списку «Запити інтерфейсу після вибору сцени» через `TestClient` на `C:/tt/bench300r` (а `review/...` — якщо твір має сесію). Таблиця URL → час — у звіт. Далі оптимізуються лише URL > 0,2 с.
- [ ] **Step 2: Тести (мають падати).** Для кожного оптимізованого URL: відповідь з view дорівнює відповіді без view на фікстурі зі stale-ланцюжком і сценою в кошику; кількість побудов `ContextView` за запит ≤ 1. Бенчмарк: `run(data=<тека без storygen.sqlite3>)` → `ValueError` без створення файлу; `run(data=<корінь_репо>/data)` → `ValueError` (захист від робочої бази). Чутливість дайджесту: зміна одного виходу змінює дайджест.
- [ ] **Step 3: Реалізувати** параметр `view`, маршрути з одним view на запит, `scene_select` бенчмарку через `TestClient` на реальних URL і захисти `run()`.
- [ ] **Step 4: Прогнати** тести Step 2, `tests/web tests/storage -q`; бенчмарк 68 (дайджест: склад `scene_select` змінено навмисно — звіт порівнює старий і новий код на новому складі, обидва дайджести рівні) і 300. Ціль: серверна сума запитів вибору сцени ≤ 1 с на 68 і ≤ 3 с на 300.
- [ ] **Step 5: Commit** `Serve scene selection from one view per request (#27)`.

### Task 4: Згортання однакових одночасних GET в інтерфейсі

**Files:**
- Modify: `src/storygen/web/static/api.js` (`api`)
- Test: `tests/web/js/api_coalesce.mjs` (новий) і його запуск у `tests/web/test_api_coalesce.py` (за зразком `test_editor_loop_ui.py`)
- Modify: `SPEC.MD` (UI-001, новий Scenario `UI-001-S03`), `docs/verification/traceability.json`

**Interfaces:**
- Produces: `api(url, options)` — для `GET` без `body` і без `signal` одночасні виклики з однаковим `url` ділять один `fetch`; кожен викликач отримує власну копію даних (`structuredClone`); після завершення запиту запис видаляється (не кеш). Інші виклики — як зараз.

- [ ] **Step 1: Тести (мають падати),** з підмінним `fetch`, що рахує виклики:
  - два одночасні `api('/x')` → 1 `fetch`, результати `deepEqual`, але різні об'єкти (зміна одного не видна в іншому);
  - `await api('/x'); await api('/x')` → 2 `fetch`;
  - два одночасні `POST` → 2 `fetch`;
  - `api('/x',{signal})` поруч з `api('/x')` → 2 `fetch`; скасування першого не відхиляє другий;
  - помилка 500 → обидва викликачі отримують `APIError` з тим самим `status`; наступний виклик знову робить `fetch`.
- [ ] **Step 2: Реалізувати** мапу запитів у дорозі в `api.js`.
- [ ] **Step 3: Прогнати** тест Step 1, `tests/web -q` і браузерні специфікації редактора (`pnpm --dir frontend exec playwright test editor-no-changes.spec.mjs impact.spec.mjs brief-proposal.spec.mjs`). Очікувано: PASS.
- [ ] **Step 4: SPEC.** UI-001: одночасні однакові GET після однієї дії згортаються; `UI-001-S03 — Згортання однакових запитів` → тест Step 1 у traceability. `check_docs.py` — PASS.
- [ ] **Step 5: Commit** `Coalesce identical in-flight GET requests (#27)`.

### Task 5: Вимір цілей у браузері, SPEC і журнал

**Files:**
- Modify: `SPEC.MD` (PERF-001: S03, формулювання, інваріант колонок), `src/storygen/storage/context_view.py` (docstring `is_stale`), `src/storygen/application/workspace_bench.py` (docstring `_shallow_model_copy`), `tests/generation/test_readiness_single_view.py` (гігієна), `docs/verification/manual.md#workspace-speed`, `docs/verification/traceability.json`, `docs/superpowers/plans/2026-10-20-remediation-progress.md`, `docs/STATUS.md`

- [ ] **Step 1: Борг рев'ю ядра (рядки «Ride»).** PERF-001 «MUST збігатися з результатом до зміни» → «з результатом повного перерахунку з копіюванням»; речення в технічному описі: колонки `run_id/scene_id/story_id` спроби й `story_id` запуску не змінюються після вставки (на цьому стоять SQL-фільтри); docstring `is_stale` — не перевіряє кошик і існування, викликач перевіряє сам; docstring `_shallow_model_copy` — лише для CLI-побудови, у сервері заборонено; тест кешу преамбули — випадок промаху за `sha256`, прибрати оманливий коментар `test_readiness_single_view.py:231-233`. `check_docs.py` — PASS.
- [ ] **Step 1a: Серія росту, якої вимагає спека («Тести», П5).** Бенчмарк на нових синтетичних теках `C:/tt/bench50`, `bench100`, `bench200` і наявній `bench300r` (стала кількість версій на сцену) на кінцевому коді; таблиця «сцени → `readiness:brief`, `readiness:all`, `scene_select`, story view» — у журнал.
- [ ] **Step 2: Браузерний вимір (виконує контролер вбудованим браузером).** Сервер застосунку на копії даних 68 сцен і окремо на `C:/tt/bench300r`; за процедурою `manual.md#workspace-speed` для дій «вибір сцени», «перевірка готовності первинної дії», «розгорнути додаткові команди», «відкриття твору» — час від кліку до завершення останнього запиту (`performance.getEntriesByType('resource')`), по 3 повтори, медіана. Без текстів.
- [ ] **Step 3: Записати** таблицю в журнал (08.11.2026 або дата виконання) і результат S03 у traceability: PASS лише якщо всі дії в межах ≤ 1 с / ≤ 3 с; інакше — відоме обмеження з вимірами в SPEC, без оголошення цілі досягнутою.
- [ ] **Step 4: Користувацька документація.** Видима поведінка не змінюється — інструкції UA/EN без змін; причина — у журналі й описі PR.
- [ ] **Step 5: Commit** `Measure workspace speed targets in the browser (#27)`; потім `scripts/verify.py` на чистому дереві (0 failed) і окремий коміт `docs/STATUS.md`.

---

## Після плану

Фінальне рев'ю всієї гілки, `detent cross-review --author claude`, PR на `main` з маркером і таблицею рішень; у PR — посилання на #27 без ключового слова закриття, якщо S03 не PASS. Після злиття — оновити основну теку й додати «Actual» до оцінки спеки.
