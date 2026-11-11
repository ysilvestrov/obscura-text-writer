# Спрощення робочого простору (#89, R-34) — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Права панель — лише поточна сцена; дії твору — у верхньому рядку з трьома іконками й меню-гамбургером; «Редагування книги» — окрема сторінка; стан і керування запуском — один рядок над редактором.

**Architecture:** Лише HTML/CSS/JS робочого простору й одна нова HTML-сторінка `/stories/{id}/revision`. Модулі зберігають ідентифікатори кнопок і обробники; змінюються точки монтування. `impact.js` і `review-session.js` отримують контекст сторінки через `init(context)`, щоб працювати і в робочому просторі (лише позначка уваги), і на новій сторінці.

**Tech Stack:** Jinja2-шаблони, ES modules без збірки (крім наявного bundle редактора), pytest + Node-тести модулів (`tests/web/js/*.mjs`), Playwright (`tests/web/browser`).

**Spec:** `docs/superpowers/specs/2026-11/2026-11-10-workspace-simplification-design.md`

## Global Constraints

- API, домен, черга й дані не змінюються; новий лише HTML-маршрут `GET /stories/{id}/revision`.
- Ідентифікатори наявних кнопок і полів не змінюються (`#add-scene`, `#rename-story`, `#run-budget`, `#export-story`, `#impact-*`, `#review-session`, `#run-status`, `#run-actions`, `#workspace-primary`…).
- Набір дій запуску для кожного стану — з чинної `run-readiness.js::controlReason` без змін.
- Порядок Save → readiness → enqueue (R20-WORKSPACE-S01) і захист незбережених правок при переходах (`beforeunload`) зберігаються.
- Іконки — вбудовані SVG Lucide (ISC) у `static/icons/`, ліцензія в `static/licenses/lucide-ISC.txt`; без пакета-залежності.
- Меню — disclosure: кнопка `#story-menu-toggle` з `aria-expanded`/`aria-controls="story-menu"`; Escape закриває й повертає фокус; клік поза меню закриває.
- Стан розділів правої панелі — `localStorage['obscura.workspace.sections']`, усі читання й записи в try/catch; без сховища розділи закриті.
- UA/EN i18n для кожного нового тексту; один вигляд для всіх.

## Review Focus

1. Сесія послідовної перевірки в фазі редагування автором: автор на сторінці «Редагування книги» відкриває сцену (посилання в робочий простір з `?scene=&material=`), редагує, повертається й завершує — нічого не губиться, а робочий простір показує позначку уваги.
2. Незбережений буфер редактора і клік по пункту меню-посиланню (Редагування книги, Публікація, Бюджет): спрацьовує наявний захист `beforeunload`, текст не губиться.
3. Оцінювач вимкнено: у меню немає «Оцінити твір»/«Оновити звіти», розділ «Оцінювання сцени» прихований; увімкнено, але дія недоступна — кнопка видима й вимкнена з причиною.
4. `localStorage` кидає виняток (приватний режим): сторінка працює, розділи закриті, помилок у консолі немає.
5. Мобільна ширина 375 px: верхній рядок — лише іконки й меню, рядок стану переноситься, права панель іде під редактор, меню не виходить за екран.

---

### Task 1: Словник стану сцени й перелік точок монтування

**Files:**
- Create: `src/storygen/web/static/workspace-status.js`, `tests/web/js/workspace_status.mjs`, `tests/web/test_workspace_status_ui.py`
- Modify: `src/storygen/web/static/editor.js` (список сцен, рядок 89; підпис вкладки), `src/storygen/web/static/workspace-route.js` (рядок стану використовує той самий підпис)

**Interfaces:**
- Produces: `sceneStatus(scene, impactStatus) -> {key: string, label: string}` у `workspace-status.js`; `key` ∈ `not_started | no_text | draft | prose | needs_review | impact_pending | impact_changes | impact_current`; `label` — чинний i18n-підпис (UI-FEEDBACK-S01, `impact.*`).

- [ ] **Step 1:** Node-тест `workspace_status.mjs`: лише план → `not_started`/«Не почато»; бриф без тексту → «Немає тексту»; чернетка → «Є чернетка»; чернетка з `needs_review` → «Потребує перегляду»; `impact_status.prose='pending'` з `needs_review` → `impact.pending`; `changes_required` → `impact.changes_required`; `no_impact` → `impact.current`; проза → `m_79679b4689c4`. Python-обгортка з `@pytest.mark.req('UI-FEEDBACK')`.
- [ ] **Step 2:** Запустити — FAIL (модуля немає).
- [ ] **Step 3:** Перенести вираз з `editor.js:89` у `sceneStatus`; `editor.js` і рядок стану (Task 2) викликають його.
- [ ] **Step 4:** PASS; `tests/web` зелений.
- [ ] **Step 5:** Перелік точок монтування в журнал плану (ledger): `budget.js:11` (`.context-panel`), `runs.js:175` (`#run-actions` / `#generation-controls`), `evaluation.js:9-20` (`#evaluation-panel`), `scene-settings.js:4` і `editor.js:92` (`#context-content`), `impact.js`, `review-session.js` (`#impact-panel`), `exports.js` (`#export-form`), `trash.js:23`. Commit `feat(workspace): one scene status vocabulary (#89)`.

### Task 2: Рядок стану з керуванням запуском і лімітом

**Files:**
- Modify: `src/storygen/web/templates/story.html` (у `.workspace-sticky` після `.editor-toolbar`: `<div id="workspace-status-row" class="workspace-status-row">` з `#workspace-scene-status`, `#run-status`, `#run-actions`, `#workspace-error-settings`, `#review-attention` (hidden), `<details id="run-options"><summary>Параметри запуску</summary></details>`); прибрати `section.workspace-status` з `.context-panel`
- Modify: `src/storygen/web/static/budget.js` (на сторінці твору: не монтувати панель; поле `#run-budget` у `#run-options`; подія `workspace-budget-updated` лишається), `workspace-route.js` (`#workspace-scene-status` = `sceneStatus(...).label`), `app.css`
- Test: `tests/web/test_workspace_layout_ui.py` (розбір `story.html` через `html.parser`), browser `tests/web/browser/workspace-layout.spec.mjs`

**Interfaces:**
- Consumes: `sceneStatus` (Task 1).
- Produces: контейнери `#workspace-status-row`, `#run-options`, `#review-attention` для Task 3.

- [ ] **Step 1:** Python-тест: `#run-actions`, `#run-status`, `#run-budget`-контейнер `#run-options` усередині `.workspace-sticky`; у `.context-panel` немає `#run-actions`, `#run-status`, `.workspace-status`. Browser-тест: для запуску в стані `paused` (fixture-ендпойнт тестового сервера, якщо є, інакше через API) у рядку стану видимі «Скасувати» й «Продовжити», а «Повторити» видима й вимкнена з причиною; поле `#run-budget` у `#run-options`.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Перенести розмітку; `budget.js` на сторінці твору монтує тільки поле ліміту в `#run-options` і підсумок меню (Task 3 додає вузол); CSS: рядок переноситься (`flex-wrap`).
- [ ] **Step 4:** PASS; наявні browser-spec, що шукають кнопки запуску в `.context-panel`, оновити на `#workspace-status-row` (ідентифікатори ті самі).
- [ ] **Step 5:** Commit `feat(workspace): status row with run controls and next-run limit (#89)`.

### Task 3: Верхній рядок, меню й сторінка «Редагування книги»

**Files:**
- Create: `src/storygen/web/static/icons/{users,settings,plus,menu}.svg`, `src/storygen/web/static/licenses/lucide-ISC.txt`, `src/storygen/web/static/story-menu.js`, `src/storygen/web/templates/revision.html`, `src/storygen/web/static/revision-page.js`
- Modify: `story.html` (storybar: три іконки з `aria-label`/`title` і `<span class="label">` для ≥1280 px; `#story-menu-toggle` з `.menu-dot`; `<nav id="story-menu" hidden>` з пунктами; `<dialog id="export-dialog">` з наявною `#export-form`; прибрати `#impact-panel`, `#review-session`, `#impact-reports`, `.publication-panel`), `routes_stories.py` (`GET /stories/{id}/revision`), `impact.js` і `review-session.js` (`export function init(context)`; контекст `{state, refresh, selectScene, openScene}`), `evaluation.js` (кнопки `story` і «Оновити звіти» монтуються в пункти меню `#story-menu-evaluate`/`#story-menu-reports`; список звітів оцінювання лишається в розділі «Оцінювання сцени»), `exports.js` (`#export-story` у меню відкриває `dialog.showModal()`), `budget.js` (підсумок `#story-menu-budget` через `compactBudgetText`-подібний `menuBudgetText(data)`), `app.css`
- Test: `tests/web/test_workspace_layout_ui.py`, `tests/web/js/story_menu.mjs` (+ обгортка), `tests/web/test_revision_page.py`, browser `workspace-layout.spec.mjs`; оновити `impact.spec.mjs`, `sequential-review.spec.mjs`, `review-evidence.spec.mjs` на нову сторінку

**Interfaces:**
- Consumes: `#review-attention` (Task 2).
- Produces: `menuBudgetText(data) -> string` (`budget-format.js`): «Бюджет · витрачено $X з $Y», без `limit_nanos` — без «з …», без даних — «Бюджет · невідомо»; `init(context)` у `impact.js`/`review-session.js`; подія `review-attention` `{count}` для позначки меню.

Рішення для сесії перевірки (поправка до специфікації): сторінка «Редагування книги» показує попередній перегляд, запуск, сесію й звіти; «Відкрити сцену» на ній веде в робочий простір (`/stories/{id}?scene=…&material=…`). У робочому просторі `#review-attention` у рядку стані показує «Перевірка впливу чекає на вас» з посиланням на сторінку, коли сесія потребує автора, а меню — позначку кількості `pending_count`.

- [ ] **Step 1:** Тести: Node `story_menu.mjs` — `menuBudgetText` для `{exposure_nanos:420000000, limit_nanos:5000000000}` → «$0.42»/«$5.00» за локаллю (як `usd`), без ліміту, без даних; Python — шаблон має `#story-menu-toggle[aria-expanded=false][aria-controls=story-menu]`, три іконки з `aria-label`, пункти меню з наявними `id`; `GET /stories/{id}/revision` → 200 і містить `#impact-panel`, `#review-session`, `#impact-reports`; `story.html` їх не містить. Browser: Enter відкриває меню, Escape закриває й фокус на кнопці; клік поза закриває; при `pending_count>0` (fixture `impact_status`) позначка на кнопці й число в пункті.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Реалізація: `story-menu.js` (disclosure), маршрут і шаблон, `init(context)` у `impact.js`/`review-session.js` (робочий простір викликає з `editor.js`-станом лише для позначки уваги; сторінка — з `revision-page.js`, що завантажує `GET /api/stories/{id}` і runs), експорт у `<dialog>`, «Оцінити твір»/«Оновити звіти» у меню; «Перейменувати твір» у меню викликає наявний `#rename-story`.
- [ ] **Step 4:** PASS; оновлені browser-spec зелені.
- [ ] **Step 5:** Commit `feat(workspace): story toolbar, menu and book revision page (#89)`.

### Task 4: Права панель сцени й правила видимості

**Files:**
- Modify: `story.html` (`.context-panel`: `<details class="tool-section" data-section="scene">` з `#context-content`, `<details class="tool-section" data-section="evaluation" id="evaluation-section">` з `#evaluation-panel`; прибрати «Контекст твору», ціль слів), `editor.js:92` (журнал імпорту — у `details.importer` лівої панелі, `#import-journal`), `evaluation.js` (розділ прихований, коли оцінювача немає або `policy==='off'`; тимчасово недоступні кнопки вимкнені з причиною), створити `static/tool-sections.js`
- Test: `tests/web/js/tool_sections.mjs` (+ обгортка), browser `workspace-layout.spec.mjs`

**Interfaces:**
- Produces: `restoreSections(root, storage)` / `rememberSection(details, storage)` у `tool-sections.js`; `storage` — об'єкт із `getItem/setItem`, що може кидати.

- [ ] **Step 1:** Node-тест: відновлення відкритих розділів зі збереженого JSON; невалідний JSON і сховище, що кидає, → усі закриті без винятку; toggle записує. Browser: відкрити «Налаштування сцени», надрукувати в редакторі (dirty), перезавантажити не треба — toggle не змінює `state.dirty`, сцену й матеріал; після reload розділ відкритий; з вимкненим оцінювачем розділ «Оцінювання сцени» і пункти меню оцінювання приховані.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Реалізація.
- [ ] **Step 4:** PASS; `tests/web` і browser-spec робочого простору зелені.
- [ ] **Step 5:** Commit `feat(workspace): scene-only side panel with remembered sections (#89)`.

### Task 5: SPEC, traceability, документація UA/EN і знімки

**Files:**
- Modify: `SPEC.MD` (R20-WORKSPACE новий Scenario; UI-FEEDBACK «Один словник стану»; новий Requirement WORKSPACE-TOOLS з Scenario; імпакт-перевірка — окрема сторінка, Scenario «Матеріали чекають перегляду» / «Немає матеріалів»; RUN-RECOVERY-UI і WORKSPACE-TELEMETRY — місце показу), `docs/verification/traceability.json`
- Modify: `docs/visual-editor.md`, `docs/prototype-runbook.md`, `docs/impact-review.md`, `docs/en/editor-workflow.md` (+ інші сторінки з описом правої панелі, знайдені `grep`), знімки `docs/images/workspace-*.png` desktop/mobile на нейтральному творі; seed `scripts/seed_workspace_demo.py`
- Modify: специфікація (розділ «Поправки»: сесія перевірки й позначка уваги; журнал імпорту в лівій панелі), беклог R-34, журнал виконання, `docs/STATUS.md` (verify.py у detached worktree)

- [ ] **Step 1:** SPEC і traceability; `python scripts/check_docs.py` — «узгоджені».
- [ ] **Step 2:** Документація й знімки (Playwright, desktop і mobile).
- [ ] **Step 3:** Повний `python -m pytest -q` — PASS.
- [ ] **Step 4:** Commit `docs(workspace): SPEC, traceability and UA/EN guides for the simplified workspace (#89)`.
