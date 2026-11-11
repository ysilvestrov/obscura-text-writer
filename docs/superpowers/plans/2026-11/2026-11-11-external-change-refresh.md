# Оновлення відкритої сцени після змін ззовні (#105) — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Робоча сторінка під час повернення у вікно помічає зміни сцен, зроблені ззовні, і показує їх, не перезаписуючи незбереженого тексту.

**Architecture:** Легкий ендпоінт ревізій сцен. Чистий модуль `scene-sync.js` порівнює ревізії, обирає новішу сцену, планує перевірку з тротлінгом і відкладенням та обчислює повідомлення. Модуль `scene-sync-workspace.js` підключає це до сторінки, а наявний обробник `story-refreshed` підміняє чистий буфер.

**Tech Stack:** FastAPI, SQLite (JSON1), ES modules, Node-тести через pytest.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-11-external-change-refresh-design.md`

## Global Constraints

- Тротлінг перевірки: 2 с. Події: `visibilitychange` (коли `!document.hidden`) і `focus`.
- Тексти UA/EN: «Сцену змінено ззовні» / «The scene was changed elsewhere»; «Відкрити новішу версію» / «Open the newer version»; «Сцену перенесено в кошик в іншому вікні — скопіюйте текст» / «The scene was moved to the trash elsewhere — copy your text».
- Помилка мережі під час перевірки ігнорується тихо.
- Чистий буфер означає: `!state.dirty && !state.saving && !body.ghost-open && bufferOrigin==='current'`.

## Review Focus

- Перевірка, запущена під час власного `refresh`/збереження, виконується після нього (тест планувальника).
- Відкрите переписування по пам’яті блокує підміну в обробнику `story-refreshed`.
- Повідомлення зникає після завантаження новішого буфера й не з’являється без зміни ззовні.
- Сцену з брудним буфером перенесено в кошик: збереження відмовляє з причиною.
- Невідомий або перенесений у кошик твір → 404 на `scene-revisions`.

---

### Task 1: Ендпоінт ревізій сцен

**Files:** Modify `src/storygen/storage/repository.py`, `src/storygen/web/routes_stories.py`; Test `tests/web/test_scene_revisions_api.py`.

**Interfaces — Produces:** `Repository.scene_revisions(story_id: str) -> dict[str, int]`; `GET /api/stories/{id}/scene-revisions` → `{"scenes": {id: revision}}`.

- [ ] Тест: ревізії й набір id збігаються з `GET /api/stories/{id}` після створення сцени, зміни голови (`save_version` + `set_head`) і перенесення сцени в кошик; невідомий твір → 404; твір у кошику → 404. Запустити, переконатися, що падає (404 на маршруті).
- [ ] Реалізувати один SQL-запит: `json_extract(payload,'$.revision')` / `'$.trashed_at'` з `scenes WHERE story_id=?` після `_active_story`. Тест проходить. Коміт.

### Task 2: Чистий модуль `scene-sync.js`

**Files:** Create `src/storygen/web/static/scene-sync.js`; Test `tests/web/js/scene_sync.mjs`, `tests/web/test_scene_sync_ui.py`.

**Interfaces — Produces:**
- `revisionsChanged(viewScenes, revisions, bufferScene) -> {changed, currentChanged, currentGone}`
- `newerScene(a, b)` → та зі сцен із вищою `revision` (null-безпечна)
- `externalNotice(state) -> 'changed' | 'gone' | null` (лише коли `state.externalChange`)
- `cleanBuffer(state, ghostOpen) -> bool`
- `createSceneSync({check, busy, now, interval=2000}) -> {trigger(), settle()}`

- [ ] Node-тест на всі п’ять функцій: зміна ревізії, нова/зникла сцена, поточна сцена зникла; вибір новішої сцени; повідомлення лише з прапорцем; тротлінг 2 с; виклик під час busy відкладається й виконується в `settle()`; помилка `check` не ламає наступних викликів. Запустити → падає (модуля немає).
- [ ] Реалізувати. Тест проходить. Коміт.

### Task 3: Підключення до сторінки

**Files:** Create `src/storygen/web/static/scene-sync-workspace.js`; Modify `editor.js`, `versions.js`, `workspace-route.js`, `templates/story.html`, `i18n.json`, `app.css`; Test `tests/web/test_scene_sync_ui.py`.

- [ ] Структурні тести (RED): обробник `story-refreshed` перевіряє `ghost-open`; `show()` використовує `newerScene`; статуси вкладок і `workspaceMaterials` читають `liveScene`; `saveBuffer` відмовляє для `externalNotice(state)==='gone'`; `loadBuffer` скидає `externalChange`; `refresh` веде лічильник `state.refreshing` у `finally`; шаблон містить `#external-change` і підключає `scene-sync-workspace.js`; ключі i18n є обома мовами.
- [ ] Реалізувати: `clearSceneBuffer` винести з виклику `installSceneTrash` і експортувати; модуль підключення реагує на `focus`/`visibilitychange`, викликає `scene-revisions`, ставить `state.externalChange`, для зниклої сцени з чистим буфером викликає `clearSceneBuffer()`, далі `refresh()`; повідомлення рендериться на `editor-state-changed`/`story-refreshed`, кнопка викликає команду `show`. Тести проходять. Перевірка в браузері: запис чернетки через API в іншому «вікні», повернення фокуса — буфер оновлено; з брудним буфером — повідомлення.
- [ ] Коміт.

### Task 4: Специфікація й документація

- [ ] SPEC.MD: новий Scenario `MCP-BRIDGE-S11` (оновлення відкритої сторінки), знято рядок відомого обмеження #105 із вказівкою усуненого відхилення; traceability; сайт `mcp.md` UA/EN + `check_site.py --rehash mcp`; журнал виконання. `scripts/check_docs.py` ok. Коміт.
