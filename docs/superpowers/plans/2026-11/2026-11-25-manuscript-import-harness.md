# R-48 Імпорт рукопису — обв'язка (PR 2): план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Автор імпортує рукопис через діалог бібліотеки чи MCP, править межі сцен, отримує книгу й будує пам'ять після перегляду з оцінкою вартості; сайт uk/en і SPEC описують усе це.

**Architecture:** Ядро (PR #314) вже дає API `/api/manuscript-import/*`. Ця обв'язка додає:
- серверний перегляд побудови пам'яті з вартістю та відбитком;
- MCP-інструмент `import_manuscript` і дію `start_run(rebuild_memory)`;
- діалог бібліотеки з редагуванням меж;
- кнопку «Побудувати пам'ять (N сцен)» і рядок походження в робочому просторі;
- сайт і SPEC.

Нових таблиць і нових маршрутів імпорту немає.

**Tech Stack:** Python 3.12, FastAPI, pytest; vanilla JS-модулі (`static/*.js`), Jinja-шаблони; Playwright (desktop + mobile); MCP bridge (`mcp/bridge.py`).

**Spec:** `docs/superpowers/specs/2026-11/2026-11-25-manuscript-import-design.md` (§4.4, §5, §6, §7). Чинна поведінка ядра — `SPEC.MD` → `Requirement: MANUSCRIPT-IMPORT` (S01–S10).

## Global Constraints

**Пам'ять і вартість**
- Без підтвердження автора жоден виклик моделі не відбувається. Імпорт моделей не викликає; пам'ять — лише після перегляду вартості.
- Вартість пам'яті — верхня межа в доларах, за зразком `generation/audit_cost.py::upper_bound`:
  - вхід сцени — її проза плюс резерв попередньої пам'яті (`max_input_chars // 8`, як у ядрі), не більше `max_input_chars`;
  - вихід — `max_output_tokens` ролі;
  - ціни — тариф провайдера ролі пам'яті.
- Ціни невідомі (не хмарний провайдер, немає чи застарів тариф) → `cost.total_usd = null` з `reason`. Запуск це не блокує. Чинне правило явного ліміту бюджету для Venice/OpenRouter не змінюється.

**Інтерфейс і тексти**
- Тексти для автора — uk і en у `static/i18n.json`; повідомлення сервера в браузері йдуть через `diagnostic()`.
- Елементи частин і серії приховано, коли `long_prose()` / `appInfo().long_prose === false` (видання `store`). Сервер однаково їх відхиляє.
- Ліміти клієнта збігаються з сервером:
  - 20 МіБ файла (`MAX_FILE`);
  - 500 сцен (`MAX_SCENES`);
  - назва сцени до 200 символів, назва книги до 300.
- Закриття діалогу без збереження надсилає `DELETE /api/manuscript-import/{id}`. Відповідь 409 чи 404 при застосуванні повертає автора до вибору файла, як у діалозі імпорту редакції (`static/editor-import.js`).

**MCP**
- `import_manuscript`: `file_path` — звичайний файл `.docx`/`.md`/`.txt` до 20 МіБ, не посилання; `content_base64` — до 2 МіБ.
- Перегляд без `confirm` віддає лише сцени й попередження, без описів абзаців.

**Документація**
- Сайт uk/en змінюється парами й підтверджується `python scripts/check_site.py --rehash <slug>`.
- Знімки — лише нейтральний приклад.

## Review Focus

1. **Автор пересуває межу на абзац, де вона заборонена** (розділювач, заголовок глави чи частини, передмова без перемикача). Інтерфейс не пропонує туди межу; якщо запит усе ж піде, 400 сервера показано через `diagnostic()`, а прийняті межі не губляться (Task 3).
2. **Рукопис змінився між переглядом і збереженням** (повторний перегляд в іншій вкладці, протермінований тимчасовий файл). 409/404 повертає до вибору файла з поясненням, без часткової книги (Task 3).
3. **Побудова пам'яті з невідомими цінами** (локальна модель, OpenRouter без тарифу). Перегляд показує кількість викликів і «вартість невідома», запуск можливий. Venice/OpenRouter без ліміту бюджету — чинна відмова (Task 1, Task 4).
4. **Книга серії з порожнім знімком початку, попередня книга вже має пам'ять.** Перегляд пам'яті спершу пропонує «Оновити з попередньої книги» і лише потім будує пам'ять (Task 1, Task 4).
5. **MCP: шлях до каталогу, посилання, файл понад 20 МіБ, непідтримуване розширення, base64 понад 2 МіБ.** Зрозуміла відмова без читання файла (Task 2).

---

### Task 1: Перегляд побудови пам'яті з вартістю

**Files:**
- Create: `src/storygen/generation/memory_build.py`
- Modify: `src/storygen/generation/readiness.py` — запис `rebuild_memory` отримує `cost`, `unfit_scenes`, `plan_fingerprint`, `series_refresh`
- Modify: `src/storygen/run_models.py` — `memory_plan_fingerprint: str | None` (64 hex), лише для `mode='rebuild_memory'`; дзеркало `audit_plan_fingerprint` (`run_models.py:38,89-94`)
- Modify: `src/storygen/generation/worker.py:171` — та сама перевірка відбитка для `rebuild_memory` (застарілий → відмова, як для audit)
- Modify: `src/storygen/web/routes_runs.py` — `GET /api/stories/{id}/memory-build` → `{scene_id, count}`
- Test: `tests/generation/test_memory_build.py`, `tests/web/test_memory_build_route.py`

**Interfaces:**
- Produces:
  - `memory_build_target(view) -> tuple[str | None, int]` — перша за позицією сцена, чия голова прози `complete` виду `manual`/`edited`, а голова пам'яті відсутня. `count` — кількість сцен від неї до кінця, які `rebuild_memory` охопить.
  - `memory_cost(repo, settings: RoleSettings, prose_chars: list[int]) -> {per_call_usd: str | None, total_usd: str | None, calls: int, reason: str | None}`. Токени входу сцени — `min(max_input_chars, chars + max_input_chars // 8) * CHARS_TO_TOKENS + INPUT_OVERHEAD`. Тариф і округлення — як `audit_cost.upper_bound`; хмарні провайдери — `audit_cost.CLOUD`.
  - `unfit_scenes(repo, view, settings, scene_ids) -> list[str]` — сцени, чиї запити не вміщуються. Використовує `application.manuscript_import.memory_fits(repo, role)` з роллю пам'яті книги.
  - Запис readiness `rebuild_memory` додатково містить:
    - `cost` (з `memory_cost`);
    - `unfit_scenes`;
    - `plan_fingerprint` — sha256 від (`scene_id`, ID цільових сцен і голів їхньої прози, модель і провайдер ролі пам'яті); лише коли `ready`;
    - `series_refresh: bool` — True, коли книга в серії, `series_start_version_id` порожній і `series_status(...).state == 'source_finished'` (`book/series.py`).

- [ ] **Step 1: Write the failing tests:**
  - `test_target_is_first_scene_without_memory`;
  - `test_target_none_when_all_scenes_have_memory`;
  - `test_cost_upper_bound_with_tariff` — тариф 1 $/2 $ за мільйон, 2 сцени → `total_usd` дорівнює сумі за формулою вище, округленою вгору;
  - `test_cost_unknown_without_tariff_does_not_block` — `total_usd is None`, `reason`, `ready` не змінено;
  - `test_cost_local_provider_is_unknown`;
  - `test_unfit_scenes_listed_for_small_role`;
  - `test_series_refresh_suggested_when_previous_book_has_memory`;
  - `test_stale_memory_fingerprint_rejected_by_worker`;
  - `test_memory_fingerprint_only_for_rebuild_memory` (валідатор `RunRequest`);
  - `test_memory_build_route_returns_target_and_count`.
- [ ] **Step 2: Run** `PYTHONUTF8=1 .venv/Scripts/python -m pytest tests/generation/test_memory_build.py tests/web/test_memory_build_route.py -q -p no:cacheprovider`. Expected: FAIL.
- [ ] **Step 3: Implement.** Новий маршрут — GET, тому `long_prose_guard.ALLOWED` не потрібен; якщо тест обходу маршрутів вимагає — додати з причиною «лише читає».
- [ ] **Step 4: Run** нові тести, а також `tests/generation/` і `tests/web/test_long_prose_guard.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(memory): перегляд побудови пам'яті з оцінкою вартості й відбитком`.

### Task 2: MCP — `import_manuscript` і `start_run(rebuild_memory)`

**Files:**
- Modify: `src/storygen/mcp/bridge.py`:
  - `TOOLS` (рядок 32) і `INSTRUCTIONS` (рядок 62);
  - новий `@server.tool() import_manuscript`;
  - `RUN_ACTIONS` (рядок 38) + `'rebuild_memory'`;
  - гілка `start_run` (рядок 913).
- Modify: `src/storygen/web/bridge_marker.py` — `'rebuild_memory'` у `BRIDGE_RUN_MODES`. `scenes/*/rebuild-memory` лишається лише для автора.
- Modify: `integrations/claude/obscura/skills/start-story/SKILL.md` (+ `references/` за потреби) — сценарій «є готовий рукопис»: `import_manuscript` без `confirm`, показати сцени автору, `confirm=True`, далі `start_run(action='rebuild_memory')` — перегляд, згода автора, запуск. Codex-варіант скілу, якщо він генерується з того самого джерела, — оновити за чинним механізмом (`tests/test_codex_skills.py`).
- Test: `tests/mcp/test_bridge_manuscript.py`; оновити `tests/mcp/test_bridge.py` (перелік інструментів) і `tests/mcp/test_bridge_guide.py`, якщо вони звіряють текст.

**Interfaces:**
- Consumes: HTTP `POST /api/manuscript-import/preview` (multipart `file`, поля маркерів, `language`), `POST /api/manuscript-import/{id}` (тіло `ManuscriptApply`), `DELETE /api/manuscript-import/{id}`; readiness `rebuild_memory` з Task 1 (`plan_fingerprint`, `cost`, `unfit_scenes`, `series_refresh`).
- Produces:
  - `import_manuscript(file_path: str | None = None, file_name: str | None = None, content_base64: str | None = None, language: Literal['uk','en'] = 'uk', chapter_markers: list[str] | None = None, part_markers: list[str] | None = None, chapter_source: str | None = None, import_id: str | None = None, confirm: bool = False, fingerprint: str | None = None, title: str | None = None, content_rating: str | None = None, scenes: list[dict] | None = None, parts: list[dict] | None = None, include_front_matter: bool = False, series: dict | None = None) -> dict`.
    - Без `confirm` повертає `{import_id, fingerprint, file_name, title_suggestion, chapter_source, scenes:[{start,end,title,words,part_index,proposed,warnings}], parts, warnings, tracked_changes, edition}`.
    - З `confirm=True` потрібні `import_id`, `fingerprint`, `title`. Без `scenes` сервер отримує запропоновані перегляд сцени (`start`, `title`, `part_index`). Повертає `{story_id, scene_ids, warnings, next_steps}`.
    - Помилки: шлях не існує, каталог, посилання (`Path.is_symlink()`), розширення не з трійки, понад 20 МіБ, base64 понад 2 МіБ, одночасно `file_path` і `content_base64`.
  - `start_run(action='rebuild_memory', scene_id=None, …)`. `scene_id` за замовчуванням береться з `GET /api/stories/{id}/memory-build`. Без `confirm` — перегляд із `cost`, `unfit_scenes`, `series_refresh`, `plan_fingerprint`. З `confirm` потрібен `plan_fingerprint`, а `RunRequest` іде з `memory_plan_fingerprint`.

- [ ] **Step 1: Write the failing tests** (за зразком `tests/mcp/test_bridge_audit.py`: `build_server(TestClient(create_app(...)))`, `BRIDGE_HEADERS`):
  - `test_import_manuscript_preview_from_path`;
  - `test_import_manuscript_preview_from_base64`;
  - `test_import_manuscript_confirm_creates_book_with_proposed_scenes`;
  - `test_import_manuscript_custom_boundaries`;
  - `test_import_manuscript_rejects_directory_symlink_extension_and_size` (параметризовано; великий файл — `os.truncate`/`seek`, не реальні 20 МіБ у пам'яті);
  - `test_import_manuscript_rejects_base64_over_2_mib`;
  - `test_rebuild_memory_preview_has_cost_and_fingerprint`;
  - `test_rebuild_memory_confirm_requires_fingerprint`;
  - `test_rebuild_memory_confirm_starts_run`;
  - `test_tools_list_includes_import_manuscript`.
- [ ] **Step 2: Run** `PYTHONUTF8=1 .venv/Scripts/python -m pytest tests/mcp/ -q -p no:cacheprovider`. Expected: нові тести FAIL.
- [ ] **Step 3: Implement.** Читання файла — у bridge-процесі, з перевірками до читання. Далі multipart так само, як `upload_cover`/`import_plan_and_characters`.
- [ ] **Step 4: Run** `tests/mcp/`, `tests/test_claude_plugin.py`, `tests/test_skill_bundles.py`, `tests/test_codex_skills.py`, `tests/web/test_long_prose_guard.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(mcp): import_manuscript і побудова пам'яті через start_run`.

### Task 3: Діалог імпорту в бібліотеці

**Files:**
- Create: `src/storygen/web/static/manuscript-import.js` — `installManuscriptImport({api, json, notice, document, appInfo})`, вхідний модуль і логіка (окремий файл-інжектор не потрібен: бібліотека не має `editor.js`-стану)
- Modify: `src/storygen/web/templates/library.html` — кнопка `#manuscript-import-open` поруч із `#new-story`, `<dialog id="manuscript-import-dialog" class="export-dialog manuscript-import-dialog">`, скрипт у `{% block scripts %}`
- Modify: `src/storygen/web/static/app.css` — стилі діалогу, списку сцен, абзаців і кнопки межі (desktop і ширина телефону без горизонтальної прокрутки)
- Modify: `src/storygen/web/static/i18n.json` — ключі `manuscript_import.ui.*` (uk + en)
- Modify: `tests/web/browser/server.py` — `POST /test-manuscript-import` (віддає base64 невеликого DOCX і MD з двома главами, довгою главою із запропонованою межею, розділювачем і передмовою)
- Test:
  - `tests/web/browser/manuscript-import.spec.mjs` (desktop + mobile);
  - `tests/web/test_manuscript_import_ui.py` (статична розмітка);
  - `tests/web/js/manuscript_import_boundaries.mjs` (чиста логіка меж).

**Interfaces:**
- Consumes: `/api/manuscript-import/preview`, `/{id}/paragraphs` (поля `index, text_head, words, heading_level, after_break, role, boundary_allowed`), `POST /{id}`, `DELETE /{id}`; `ManuscriptPreview` (`import_id, fingerprint, file_name, title_suggestion, chapter_source, scenes, parts, front_matter, dropped, warnings, tracked_changes, edition`).
- Produces (експорт із `manuscript-import.js` для тесту `.mjs`):
  - `toggleBoundary(scenes, index, paragraphs) -> scenes` — додає межу на `boundary_allowed` абзаці (нова сцена отримує назву «<назва сцени> (n)» з обрізанням до 200) або прибирає наявну. Першу межу прибрати не можна.
  - `sceneWords(scenes, paragraphs) -> number[]`.
  - `applyBody(state) -> ManuscriptApply`.

**Кроки діалогу:**
1. Вибір файла. Клієнт перевіряє 20 МіБ; `accept=".docx,.md,.txt"`.
2. Перегляд.
   - Таблиця сцен: назва (поле, ≤200), слова, частина, позначка «запропоновано».
   - Розгортання сцени лінива завантажує абзаци (`paragraphs?start&end`). Біля кожного абзацу з `boundary_allowed` — кнопка «Межа тут» / «Прибрати межу».
   - Поля: назва книги (≤300, з `title_suggestion`), мова, рейтинг (як у формі нової книги), маркери глав і частин (зміна → повторний `preview` з `import_id`, новий `fingerprint`, межі автора скидаються з попередженням), джерело глав, перемикач «Додати передмову на початок першої сцени» (коли `front_matter` непорожній), серія з номером (лише `long_prose`).
   - Попередження й відкинуті абзаци — через `diagnostic()`. Понад 500 сцен — кнопка «Імпортувати» вимкнена з поясненням.
3. Підсумок: посилання на книгу й кнопка «Побудувати пам'ять (N сцен)». Вона веде в робочий простір книги з відкритим переглядом пам'яті (Task 4): `/stories/{id}?build_memory=1`.

- [ ] **Step 1: Write the failing tests:**
  - JS:
    - `toggleBoundary` додає межу лише на дозволеному абзаці й прибирає її;
    - назва нової сцени обрізається до 200;
    - `applyBody` збирає `scenes` у зростаючому порядку;
    - `sceneWords` рахує слова сцен після пересування межі.
  - Python: розмітка має `#manuscript-import-open`, `dialog#manuscript-import-dialog`; елементи серії під `long_prose()`.
  - Playwright:
    - імпорт DOCX → таблиця сцен; зміна межі → нова сцена; «Імпортувати» → підсумок із посиланням;
    - на mobile ширина діалогу ≤ ширини вікна;
    - 409 (повторний перегляд з іншою вкладкою через `request`) → повернення до вибору з повідомленням;
    - закриття без збереження надсилає `DELETE` (перехоплення запиту);
    - видання `store` (`/test-build-edition`) — немає поля серії.
- [ ] **Step 2: Run** `PYTHONUTF8=1 .venv/Scripts/python -m pytest tests/web/test_manuscript_import_ui.py -q -p no:cacheprovider`; `node tests/web/js/manuscript_import_boundaries.mjs`; `cd frontend && node node_modules/@playwright/test/cli.js test manuscript-import.spec.mjs`. Expected: FAIL.
- [ ] **Step 3: Implement** за зразком `static/editor-import.js`: стан `epoch`/`pending`/`saving`, `discard()`, `sync()`, фокус після відкриття, закриття й 409.
- [ ] **Step 4: Run** ті самі команди, а також `tests/web/test_localization.py` і `node tests/web/js/localization.mjs`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(manuscript): діалог імпорту рукопису в бібліотеці`.

### Task 4: Побудова пам'яті в робочому просторі й позначка імпорту

**Files:**
- Create: `src/storygen/web/static/memory-build.js` — `installMemoryBuild({api, json, notice, document, state})`
- Modify: `src/storygen/web/templates/story.html`:
  - пункт меню `#story-menu-build-memory` у `#story-menu` (прихований, коли `count == 0`);
  - `<dialog id="memory-build-dialog">`;
  - підключення скрипту.
- Modify: `src/storygen/web/static/external-origin.js` — `ref.manuscript_import` → «Імпортовано з рукопису: {file_name}»
- Modify: `src/storygen/web/static/editor.js:44-52` — для сцени з головою прози `manuscript_import` і без голови плану додати речення «План необов'язковий: валідація перевіряє прозу й пам'ять» (ключ `manuscript_import.ui.plan_optional`) у `#workspace-origin`
- Modify: `src/storygen/web/static/i18n.json`
- Modify: `tests/web/browser/server.py` — фікстура книги з імпортованою прозою без пам'яті (через `publish_manuscript` або API імпорту) і варіант серії з порожнім знімком початку
- Test: `tests/web/browser/memory-build.spec.mjs` (desktop + mobile), `tests/web/test_memory_build_ui.py`

**Interfaces:**
- Consumes:
  - `GET /api/stories/{id}/memory-build`;
  - `GET /api/stories/{id}/readiness?scene_id=…&operation=rebuild_memory` (Task 1: `ready`, `reason`, `calls`, `cost`, `unfit_scenes`, `series_refresh`, `plan_fingerprint`);
  - `POST /api/runs` з `{request_id, request:{mode:'rebuild_memory', scene_id, memory_plan_fingerprint, budget_limit_usd?}}`;
  - `refreshBook(storyId)` з `static/series-status.js:23` для `series_refresh`.
- Produces: діалог перегляду пам'яті.
  - Кількість сцен (N) і викликів; вартість «до X $» або «вартість невідома»; перелік сцен, що не вміщуються (назви, посилання).
  - Якщо `series_refresh` — спершу кнопка «Оновити з попередньої книги» (чинний `refreshBook` із підтвердженням). Після неї перегляд оновлюється.
  - «Побудувати пам'ять» стартує запуск, закриває діалог і передає керування чинній панелі запусків (пауза, скасування, продовження вже є).
  - `?build_memory=1` у URL відкриває діалог після завантаження.

- [ ] **Step 1: Write the failing tests:**
  - Python: розмітка пункту меню й діалогу; `external-origin.js` має гілку `manuscript_import`.
  - Playwright:
    - книга після імпорту: пункт меню «Побудувати пам'ять (N сцен)» видимий; діалог показує N і «вартість невідома» (у фікстурі немає тарифу); «Побудувати» шле `POST /api/runs` з `memory_plan_fingerprint` (перехоплення);
    - сцена показує «Імпортовано з рукопису: …» і речення про необов'язковий план;
    - серія з порожнім знімком → кнопка «Оновити з попередньої книги» перед «Побудувати»;
    - `?build_memory=1` відкриває діалог;
    - mobile без горизонтальної прокрутки.
- [ ] **Step 2: Run** `PYTHONUTF8=1 .venv/Scripts/python -m pytest tests/web/test_memory_build_ui.py -q -p no:cacheprovider`; `cd frontend && node node_modules/@playwright/test/cli.js test memory-build.spec.mjs`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** ті самі команди, а також `editor-import.spec.mjs` (спільний `#workspace-origin`) і `tests/web/test_localization.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(memory): «Побудувати пам'ять» з переглядом вартості й позначка імпорту`.

### Task 5: Сайт, знімки, SPEC

**Files:**
- Create: `docs/site/uk/manuscript-import.md`, `docs/site/en/manuscript-import.md` — сторінка «Імпорт рукопису» / «Importing a manuscript»: формати й ліміти, як розпізнаються глави (маркери, стилі, Пролог/Епілог), межі сцен, передмова, видання, побудова пам'яті з вартістю, MCP (шлях до файла), відомі обмеження
- Modify: `docs/site/site.json` — сторінка `manuscript-import` після `imports`
- Modify: `docs/site/{uk,en}/first-story.md` (розділ «Вже є рукопис») і `docs/site/{uk,en}/memory.md` (побудова пам'яті для імпортованої книги); за потреби — `docs/site/{uk,en}/mcp.md` (інструмент `import_manuscript`)
- Modify: `scripts/capture_screenshots.py` — `capture_manuscript_import(base, lang, ...)` (діалог на кроці перегляду, нейтральний рукопис) → `docs/images/site/{uk,en}/manuscript-import-desktop.png`; за потреби `memory-build-desktop.png`
- Modify: `SPEC.MD` → `Requirement: MANUSCRIPT-IMPORT`:
  - S11 — діалог і межі;
  - S12 — позначка імпорту й необов'язковий план у сцені;
  - S13 — побудова пам'яті з вартістю, відбитком, переліком непридатних сцен і пропозицією оновити серію;
  - S14 — MCP `import_manuscript` і `start_run(rebuild_memory)`.

  Прибрати з відомих обмежень «інтерфейс/MCP — у PR 2». Доповнити опис запуску `rebuild_memory`: `cost`, `memory_plan_fingerprint`.
- Modify: `docs/verification/traceability.json` (S11–S14 → тести Task 1–4), `docs/superpowers/plans/2026-10-20-remediation-progress.md` (запис R-48 PR 2)

- [ ] **Step 1:** Написати сторінки uk і en, оновити `site.json` і згадки.
- [ ] **Step 2:** Запустити знімки: `PYTHONUTF8=1 .venv/Scripts/python scripts/capture_screenshots.py` (або лише нові сценарії, якщо скрипт це підтримує); перевірити зображення на відсутність приватних даних.
- [ ] **Step 3:** `PYTHONUTF8=1 .venv/Scripts/python scripts/check_site.py --rehash manuscript-import`; так само для кожної зміненої сторінки (`first-story`, `memory`, `mcp`). Expected: OK.
- [ ] **Step 4:** SPEC + traceability; `PYTHONUTF8=1 .venv/Scripts/python scripts/check_docs.py`. Expected: OK. Також `tests/test_docs_site.py` і `tests/test_capture_screenshots.py`. Expected: PASS.
- [ ] **Step 5: Commit** `docs(manuscript): сайт uk/en, знімки й SPEC S11–S14`. У тілі — перелік оновлених сторінок uk/en.

Повний набір тестів і `scripts/verify.py` запускає контролер після фінального рев'ю з короткого шляху `C:/tmp/<коротка>` (detached worktree, junction на `.venv` і `frontend/node_modules`); результат — у `docs/STATUS.md`. Останній PR задачі несе `Closes #288`.
