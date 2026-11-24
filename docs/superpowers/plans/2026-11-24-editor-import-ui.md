# R-46 Імпорт редакції з DOCX — інтерфейс і документація (PR 2): план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Автор імпортує DOCX редактора з меню твору: бачить зведення по сценах, за потреби вибирає, що робити зі зміненими сценами, переходить до сцен і бачить пропозицію з міткою «від редактора (DOCX)»; сайт uk/en пояснює, як це робити.

**Architecture:**
- **Бекенд мінімальний:**
  - поле `source` у списку пропозицій і в перегляді правок;
  - ключі i18n для текстів сервера імпорту;
  - фікстура для браузерних тестів.
- **Фронтенд:**
  - новий пункт меню твору і нативний `<dialog id="editor-import-dialog">`;
  - модуль `static/editor-import.js` за зразком `export-form.js`, підключений у новому `static/editor-imports.js`.
- **Документація:** розділ на сторінці сайту `publication` uk/en, знімок діалогу, SPEC EDITOR-IMPORT-S11.

**Tech Stack:** vanilla JS (ES modules), Jinja-шаблони, FastAPI, pytest, Playwright (`frontend/playwright.config.mjs`).

**Spec:** `docs/superpowers/specs/2026-11/2026-11-24-editor-docx-import-design.md` (§6). Ядро — PR #303 (гілка `claude/r46-core`); ця гілка `claude/r46-ui` відгалужена від неї, PR на `main` відкривається після злиття #303.

## Global Constraints

**Тексти й мови**
- Усі нові тексти інтерфейсу — ключі `editor_import.*` в `static/i18n.json`, і в `uk`, і в `en`. Перевірка паритету: `tests/web/test_localization.py:16`.
- Тексти сервера перекладаються через каталог: ключ, чиє uk-значення **точно** дорівнює рядку сервера, змінні частини — `{p0}`, `{p1}` (`web/localization.py::_diagnostic_catalog`).

**Пункт меню**
- Підпис: «Імпорт редакції (DOCX)…» / "Import editor's revision (DOCX)…".
- Розташування: одразу після `#export-story`.
- `id="import-edition"`, `aria-haspopup="dialog"`, `aria-controls="editor-import-dialog"`.
- Доступний в усіх виданнях, без прапорця.

**Діалог**
- Недоступний, поки `state.dirty || state.saving`; причина показується, як у `export-form.js`.
- Файл понад 20 МіБ відхиляється на клієнті до відправлення.
- «Скасувати» після зведення викликає `DELETE /api/stories/{id}/editor-import/{import_id}`.
- Три дії вибору: «Скасувати імпорт» / «Пропустити змінені сцени» / «Замінити все». Остання має пояснення: «Ваші пізніші зміни з'являться як правки, які можна відхилити».

**Посилання**
- Посилання на сцену: `/stories/{story}?scene={id}&material=review` для `changed`, `material=draft` для інших.

**Позначка пропозиції**
- Мітка пропозиції: « · від редактора (DOCX)» / " · from editor (DOCX)".
- Джерело — поле `source: 'editor_import' | None`.

**Документація**
- Документація українською й англійською в парі.
- Знімки лише з нейтральним прикладом (`scripts/capture_screenshots.py::STORIES`).
- `python scripts/check_site.py --rehash publication`.

## Review Focus

1. **Автор має незбережені правки й відкриває імпорт.** Очікування: діалог не відкривається, причина видима; збережений текст не губиться (Task 2).
2. **Сервер повертає 409 «Твір змінився після зведення».** Очікування: діалог показує причину й пропонує переглянути файл ще раз, а не мовчки закривається (Task 2).
3. **Англійська мова інтерфейсу.** Очікування: статуси, попередження й помилки імпорту англійською, без українських рядків (Task 1, Task 2).
4. **Мобільна ширина (Pixel 7).** Очікування: таблиця зведення не виходить за екран, кнопки вибору досяжні (Task 2, Playwright `mobile`).
5. **Повторне відкриття діалогу після імпорту.** Очікування: попереднє зведення не лишається, стан скинуто (Task 2).

---

### Task 1: Джерело пропозиції й тексти сервера англійською

**Files:**
- Modify: `src/storygen/web/routes_versions.py:96-102` — елемент списку отримує `'source': 'editor_import' if a.context.get('editor_import') else None`
- Modify: `src/storygen/generation/copyedit_review.py` (`copyedit_preview`) — те саме поле `source` у відповіді
- Modify: `src/storygen/web/static/i18n.json` — ключі для кожного українського рядка, що сервер імпорту віддає автору: `editor_import.py`, `editor_import_match.py`, `publication/docx_import.py`, `web/routes_editor_import.py`. Сюди входять `STALE_PREVIEW`, `WHOLE_SCENE_DELETED`, `SCENE_CHANGED`, `FORMATTING_LOST`, попередження з числами (`{p0}`), повідомлення 413/400/404.
- Test: `tests/web/test_editor_import_i18n.py`, `tests/web/test_copyedit_review_ui.py` або новий тест API

**Interfaces:**
- Produces:
  - `GET /api/scenes/{id}/copyedits` → `attempts[i].source: str | None`;
  - `GET /api/scenes/{id}/copyedits/{attempt}` → `source: str | None`;
  - ключі `editor_import.server.*` в i18n.

- [ ] **Step 1: Write the failing tests.**
  - `test_proposal_list_marks_editor_import`: після `apply_import` (фікстури з `tests/publication/test_editor_import.py`) список пропозицій сцени має `source == 'editor_import'`. Модельна пропозиція (`tests/generation/test_copyedit_review.py::generate`) має `source is None`. Те саме для перегляду.
  - `test_every_import_message_has_english`: для кожного рядка з переліку вище, а для шаблонів з числами — з підставленими значеннями, `web.localization.diagnostic(text, 'en')` повертає англійський текст (≠ uk, не містить кирилиці). Перелік рядків — явний список у тесті: константи модулів плюс кілька згенерованих попереджень зі справжнього зведення.
- [ ] **Step 2: Run** `PYTHONUTF8=1 .venv/Scripts/python -m pytest tests/web/test_editor_import_i18n.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Поле `source` і ключі `editor_import.server.<name>`. Значення uk точно дорівнюють рядкам сервера; змінні частини — `{p0}` (фіксованого тексту ≥ 8 символів).
- [ ] **Step 4: Run** той самий тест плюс `tests/web/test_localization.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(import): джерело пропозиції й англійські тексти імпорту`.

### Task 2: Пункт меню й діалог імпорту

**Files:**
- Modify: `src/storygen/web/templates/story.html` — пункт `#import-edition` після `#export-story`; `<dialog id="editor-import-dialog" class="export-dialog" aria-labelledby="editor-import-title">`
- Create: `src/storygen/web/static/editor-import.js` — `installEditorImport({state, api, notice, document})`
- Create: `src/storygen/web/static/editor-imports.js` — підключення (як `exports.js`), `<script type="module">` у `story.html` поруч з `exports.js`
- Modify: `src/storygen/web/static/app.css` — таблиця зведення з прокруткою на вузькому екрані
- Modify: `src/storygen/web/static/i18n.json` — `editor_import.*` (меню, заголовок, кнопки, статуси людською мовою, підсумок)
- Modify: `tests/web/test_workspace_layout_ui.py:67` — список id меню
- Modify: `tests/web/browser/server.py` — маршрут `/test-editor-import`
- Test: `tests/web/test_editor_import_ui.py` (статичний), `tests/web/browser/editor-import.spec.mjs`

**Interfaces:**
- Consumes:
  - `POST /api/stories/{id}/editor-import/preview` (multipart `file`) → `ImportPreview{import_id, export_id, fingerprint, choice_required, scenes:[ScenePreview{scene_id,title,status,needs_choice,edits,comments,general_comments,dropped_comments,replace_status,warnings}], unmatched, warnings}`;
  - `POST …/{import_id}` JSON `{fingerprint, changed_scenes}` → `ImportResult{imported, draft_only, skipped:[{scene_id,status}], warnings}`;
  - `DELETE …/{import_id}` → 204;
  - `api`/`notice` з `static/api.js`;
  - `t`/`uiText`/`diagnostic` з `static/i18n.js`.
- Produces:
  - фікстура `POST /test-editor-import` → `{story_id, docx_base64, scene_ids}`. Книга з 3 сцен:
    - сцена 1 змінена редактором;
    - сцена 2 має лише примітку;
    - сцена 3 має змінену прозу після експорту, тож `choice_required`.

    Збирається через `export_story` і функції правки з `tests/publication/test_editor_import.py`; за потреби перенести їх у спільний `tests/publication/editor_import_helpers.py`.

- [ ] **Step 1: Write the failing tests.**
  - Статичний `test_editor_import_dialog_markup`:
    - `#import-edition` стоїть одразу після `#export-story` у `#story-menu`;
    - `#editor-import-dialog` — це `dialog`;
    - у ньому є `input[type=file][accept*=".docx"]`, `#editor-import-status[role=status]` і кнопки `#editor-import-submit`, `#editor-import-cancel`;
    - ключі `data-i18n` існують в обох мовах.
  - Playwright `editor-import.spec.mjs` (desktop і mobile):
    1. Посів через `/test-editor-import`, відкриття твору, меню → «Імпорт редакції (DOCX)…».
    2. `setInputFiles` з буфером із фікстури. Зведення показує 3 сцени зі статусами: «змінено», «лише примітки», «прозу змінено після експорту». Видно три дії вибору.
    3. «Пропустити змінені сцени» дає підсумок з 2 імпортованими й 1 пропущеною сценою та посиланням на сцену 1.
    4. Посилання відкриває сцену 1. У панелі «Правки редактора» опція пропозиції має текст із « · від редактора (DOCX)».
    5. Окремий тест: незбережена правка робить пункт меню недоступним з видимою причиною.
    6. Окремий тест: після зведення «Скасувати» надсилає `DELETE` (перевірка через `page.waitForRequest`). Повторне відкриття показує порожній стан.
    7. Окремий тест: перемикання мови на en дає англійські статуси.
  - Знімок для сайту: `page.screenshot` елемента діалогу зі зведенням у `docs/images/site/{uk,en}/editor-import-{project}.png`. Як варіант — кадр у `scripts/capture_screenshots.py` (див. Task 4).
- [ ] **Step 2: Run:**
  - `PYTHONUTF8=1 .venv/Scripts/python -m pytest tests/web/test_editor_import_ui.py tests/web/test_workspace_layout_ui.py -q`
  - `pnpm --dir frontend exec playwright test editor-import.spec.mjs`

  Expected: FAIL.
- [ ] **Step 3: Implement `installEditorImport`.**
  - Стани: вибір файла → зведення → (вибір) → підсумок.
  - Кнопка «Імпортувати ({p0} сцен)» рахує сцени зі статусами `changed`, `comments_only`, `over_limit`. При `choice_required` замість неї три дії: «Скасувати імпорт» = cancel, `skip`, `replace`.
  - Помилки показуються через `diagnostic(error.message)` у статусі діалогу. Для 409 текст пропонує вибрати файл ще раз.
  - Закриття діалогу скидає стан; якщо зведення не підтверджено, надсилає `DELETE`.
  - Посилання ведуть на сцени у форматі з Global Constraints. Перехід — через `selectScene` + `invokeWorkspaceCommand('show', …)`, як `memory-merge-panel.js:124-127`.
- [ ] **Step 4: Run** обидві команди. Expected: PASS.
- [ ] **Step 5: Commit** `feat(import): пункт меню й діалог імпорту редакції`.

### Task 3: Мітка пропозиції в панелі редактури

**Files:**
- Modify: `src/storygen/web/static/change-review.js:99` (опція спроби) і `render(data)` (`:38`) — рядок над правками «Пропозиція з імпорту редакції (DOCX); модель не викликалася»
- Modify: `src/storygen/web/static/i18n.json`
- Test: `tests/web/test_copyedit_review_ui.py` (статичний: ключ і використання), Playwright покрито в Task 2 крок 4

**Interfaces:**
- Consumes: `attempt.source`, `data.source` з Task 1.

- [ ] **Step 1: Write the failing test** `test_change_review_marks_editor_import`. `change-review.js` використовує ключ `editor_import.proposal_label` для `source === 'editor_import'`; ключ є в обох мовах.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** мітку в опції й рядок у перегляді.
- [ ] **Step 4: Run** статичний тест і `pnpm --dir frontend exec playwright test editor-import.spec.mjs`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(import): мітка пропозиції з імпорту редакції`.

### Task 4: Сайт, знімки, SPEC

**Files:**
- Modify: `docs/site/uk/publication.md` і `docs/site/en/publication.md` — новий розділ `### Імпорт редакції (DOCX)` / `### Importing the editor's revision (DOCX)` після розділу про рукопис для редактора. Зміст:
  1. Експортуйте DOCX і віддайте редактору.
  2. Редактор править у Word, краще в режимі виправлень, і лишає примітки.
  3. Меню твору → «Імпорт редакції (DOCX)…» → зведення.
  4. Що означають статуси.
  5. Вибір при зміні прози після експорту.
  6. Де знайти правки (вкладка редактури, мітка) і коментарі (чернетка).
  7. Обмеження: таблиці, зображення, виноски; Google Docs не перевірено; однорядкові списки чи цитати, попередження про форматування.
- Modify: `docs/site/uk/revision.md` і `en/revision.md` — одне речення з посиланням на розділ, якщо в сторінці є список джерел пропозицій.
- Modify: `scripts/capture_screenshots.py` — кадр діалогу зі зведенням для обох мов, з нейтральним твором `STORIES`; тест `tests/test_capture_screenshots.py` за наявним зразком. Зображення: `docs/images/site/{uk,en}/editor-import-desktop.png`.
- Modify: `docs/site/sync.json` через `python scripts/check_site.py --rehash publication` (і `revision`, якщо змінено).
- Modify: `SPEC.MD`:
  - EDITOR-IMPORT: прибрати з «Відомих обмежень» відсутність інтерфейсу й англійських текстів;
  - додати `Scenario: EDITOR-IMPORT-S11 — Діалог імпорту в меню твору` (меню, зведення, три дії, підсумок з посиланнями, мітка пропозиції, недоступність при незбережених правках);
  - EXPORT-001: згадати сусідній пункт меню.
- Modify: `docs/verification/traceability.json` — S11 → тести Task 2–3 (Playwright і статичні).

- [ ] **Step 1: Write the docs and SPEC changes.**
- [ ] **Step 2: Capture images:** `python scripts/capture_screenshots.py --work-dir C:/tmp/obscura-shots`. Expected: файли `editor-import-desktop.png` для uk і en, на яких видно таблицю зведення.
- [ ] **Step 3: Run:**
  - `python scripts/check_site.py --rehash publication`
  - `PYTHONUTF8=1 .venv/Scripts/python scripts/check_docs.py`
  - `PYTHONUTF8=1 .venv/Scripts/python -m pytest tests/test_docs_site.py tests/test_capture_screenshots.py -q`

  Expected: OK, PASS.
- [ ] **Step 4: Full suite** (окремо, з короткого шляху, як для PR 1):
  - `PYTHONUTF8=1 .venv/Scripts/python -m pytest -q -p no:cacheprovider`
  - `pnpm --dir frontend exec playwright test`

  Expected: PASS.
- [ ] **Step 5: Commit** `docs(import): сайт uk/en, знімки й SPEC для імпорту редакції`. У тілі коміту — оновлені сторінки й мовні версії.
