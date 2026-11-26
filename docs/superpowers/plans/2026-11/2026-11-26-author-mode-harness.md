# Режим «Пишу сам» — обв'язка: план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** автор вибирає «Пишу сам» у формах, робочий простір не пропонує генерації прози, діалог пам'яті каже, що отримає модель, а вітрина й сайт описують режим.

**Architecture:** ядро вже є (`storygen/writing_mode.py`, перевірки сервера, міст; коміти до `2c797033`). Обв'язка лише показує режим. `runs.js`, `workspace-state.js` та асистоване письмо читають `state.view.story.writing_mode`. `scene-sync-workspace.js` на фокусі помічає зміну режиму. `readiness.preview` для пам'яті віддає `sends`, а `memory-build.js` його показує.

**Tech Stack:** Jinja-шаблони, vanilla JS (тести `tests/web/js/*.mjs` через node), Playwright (`tests/web/browser`), pytest.

**Spec:** [2026-11-26-author-mode-design.md](../../specs/2026-11/2026-11-26-author-mode-design.md), §5–§8.

**Рев'ю ядра:** ядро перевірено наскрізно. Знахідки виправлено в `2c797033`: копія чернетки в `edit_loop`, тест S06 на рівні запуску, тексти моста. Відкладено одну дрібну: слабкі тести відсутності відмови.

## Global Constraints

- Тексти режиму в інтерфейсі:
  - uk: `writing_mode.author` = «Пишу сам», `writing_mode.author_help` = «Прозу пишете ви; моделі ведуть пам'ять і перевіряють узгодженість, але не пишуть і не переписують текст»;
  - en: «I write myself» / «You write the prose; models keep the memory and check consistency but never write or rewrite the text».
- Типовий режим форми нового твору лишається `obscura` (рішення власника 26.11.2026).
- Порядок у списку: `obscura`, `chat`, `author`.
- У режимі `author` ховаються:
  - кнопки запуску `draft`, `edit_loop`, `scene`, `remaining` у `runs.js`;
  - `#workspace-edit-prose`, `#assisted-writing`, запуск коректури.
  
  Лишаються `prepare`, `brief`, `memory`, `rebuild_memory` і меню «Дії твору».
- Головна дія вкладки:
  - «План» і «Завдання» — `{action:'write'}` з написом «Писати прозу» (`workspace.write_prose`): перемикає на вкладку «Проза»;
  - «Чернетка» — `{action:'use_draft'}`, та сама дія, що `#workspace-use-draft`;
  - «Проза» й «Пам'ять» — без змін.
- Рядок даних пам'яті:
  - uk: «Модель «{model}» отримає: {items}»;
  - локальна адреса (`localhost`, `127.0.0.1`, `[::1]`): «Obscura надсилає текст лише на адресу на цьому комп'ютері; куди його передає далі сервер моделі, залежить від цього сервера».
  
  Обіцянки «не залишає комп'ютер» немає.
- Категорії `sends.items` є ключами i18n `memory_build.sends.<key>`:
  - `prose` — «прозу N сцен (≈ W слів)»;
  - `character_names` — «імена персонажів сцени»;
  - `memory_catalog` — «пам'ять попередніх сцен»;
  - `places` — «шляхи місць сцени»;
  - `series_facts` — «факти біблії серії».
- Тексти вітрини:
  - без дорослих формулювань і рейтингів;
  - без обіцянки «написано людиною».
  
  Store-картка `store_listing/listing.md` лежить поза репозиторієм: її правимо локально, не комітимо.
- Сайт: пари uk/en, `python scripts/check_site.py --rehash <slug>` для кожної зміненої сторінки. Знімки — лише нейтральні приклади.

## Review Focus

- Режим змінено в налаштуваннях в іншій вкладці, редактор без змін у сценах отримує фокус: кнопки генерації мають зникнути (Task 2).
- Твір `author` із наявною AI-чернеткою: вкладка «Чернетка» пропонує «Взяти як прозу», а не «Редагувати» (Task 2).
- Твір із локальною моделлю пам'яті за `http://127.0.0.1:…`: рядок про локальну адресу без обіцянки приватності (Task 3).
- Сцена без місць і твір без серії: у переліку немає «шляхи місць» і «факти біблії» (Task 3).
- Англійський інтерфейс: усі нові написи перекладені (Task 1–3).

---

### Task 1: Вибір режиму у формах і перший екран

**Files:** `src/storygen/web/templates/library.html`, `templates/settings.html`, `static/i18n.json` (uk/en: `writing_mode.author`, `writing_mode.author_help`, оновлені `writing_mode.help`, `writing_mode.help_settings`, нове `m_…` або іменований ключ підзаголовка першого екрана); Test `tests/web/test_writing_mode.py`.

- [ ] **Step 1: Тести.**
  - `test_new_story_form_offers_author_mode`: у HTML бібліотеки є `<option value="author"`, а `obscura` лишається `selected`.
  - `test_settings_page_offers_author_mode`: `#story-mode-form` має `option value="author"`.
  - `test_library_intro_names_writing_yourself`: підзаголовок містить «Пишіть самі» (uk) і «Write it yourself» (en через `Accept-Language`).
- [ ] **Step 2: Перевірити, що тести падають.**
- [ ] **Step 3: Реалізувати.**
  - Додати опції й тексти.
  - Підзаголовок першого екрана (uk/en): «Пишіть самі або з моделлю — Obscura пам'ятає книгу й показує, що змінила правка.» / «Write it yourself or with a model — Obscura remembers the book and shows what an edit changed.».
  - `writing_mode.help` описує три режими; `help_settings` — що «Пишу сам» зупиняє кроки прози запуску, що вже йде.
- [ ] **Step 4: Прогнати тести.** `pytest tests/web/test_writing_mode.py tests/web/test_i18n*.py -q`.
- [ ] **Step 5: Коміт.**

### Task 2: Робочий простір у режимі «Пишу сам»

**Files:** `static/runs.js` (`updateControls`), `static/workspace-state.js` (`primaryAction`, `performPrimary`), `static/assisted-writing.js`, copyedit-панель (знайти запуск коректури в `static/`), `static/scene-sync-workspace.js`, `web/routes_stories.py:147` (`scene-revisions` віддає ще `writing_mode`), `static/i18n.json` (`workspace.write_prose`, `workspace.author_proposal`); Tests `tests/web/js/workspace_state.mjs` (або наявний JS-тест `primaryAction`), `tests/web/test_scene_revisions*.py`, Playwright `tests/web/browser/author-mode.spec.mjs` (новий) + фікстура в `tests/web/browser/server.py` (`/test-author-mode`).

**Interfaces:**
- Produces:
  - `authorMode(state) -> boolean` у `workspace-state.js` (експорт);
  - `GET /api/stories/{id}/scene-revisions` → `{scenes, writing_mode}`.

- [ ] **Step 1: Тести.**
  - JS: `primaryAction` у режимі `author` для `plan`/`brief` повертає `action:'write'`, а для `draft` — `action:'use_draft'`. `prose`/`memory` не змінюються.
  - pytest: `scene-revisions` має `writing_mode`.
  - Playwright (desktop і mobile):
    - (а) твір `author`: кнопок «Чернетка», «Редагувати», «Уся сцена», «Пройти решту» немає, а «Завдання» і «Пам'ять» є; головна дія вкладки «План» — «Писати прозу», клік відкриває вкладку «Проза»;
    - (б) режим змінено через API, `focus` → кнопки генерації зникають;
    - (в) у творі з пропозицією коректури показано пояснення `workspace.author_proposal`, а кнопки прийняття вимкнено.
- [ ] **Step 2: Перевірити, що тести падають.**
- [ ] **Step 3: Реалізувати.**
  - `updateControls` ставить `hidden` на `draft`, `edit_loop`, `scene`, `remaining`, якщо `authorMode(state)`.
  - `performPrimary` обробляє `write` (перемикач вкладки «Проза» і фокус редактора) і `use_draft` (той самий обробник, що `#workspace-use-draft`).
  - `check()` у `scene-sync-workspace.js` порівнює `writing_mode` з `state.view.story.writing_mode` і за різниці викликає `refresh({fresh:true})`.
  - Сторінка перемальовується на `story-refreshed`.
- [ ] **Step 4: Прогнати** JS-тести (`node tests/web/js/<file>.mjs`), pytest і Playwright (`cd frontend; PYTHONPATH=<root>/src node node_modules/@playwright/test/cli.js test ../tests/web/browser/author-mode.spec.mjs -c playwright.config.mjs`), а також наявні `workspace*.spec.mjs` і `runs*.spec.mjs`.
- [ ] **Step 5: Коміт.**

### Task 3: Що отримає модель пам'яті

**Files:** `src/storygen/generation/readiness.py` (гілка пам'яті ~`:167-172`), `src/storygen/generation/memory_build.py` (нова `memory_sends(repo, view, settings, targets, context) -> dict`), `static/memory-build.js`, `static/i18n.json` (`memory_build.sends.*`); Tests `tests/generation/test_memory_sends.py` (новий), `tests/web/browser/memory-build.spec.mjs`.

**Interfaces:**
- Produces: `result['sends'] = {'items': [{'key': str, 'scenes'?: int, 'words'?: int}], 'local': bool}` у перегляді `rebuild_memory` і `stage`+`memory`.

- [ ] **Step 1: Тести.**
  - `test_sends_cover_every_section_of_the_memory_request`: зібрати контекст пам'яті (`build_context(..., 'memory', ...)`) для сцени з місцями й біблією серії. Кожна мітка розділу запиту з набору міток `generation/context.py` має категорію в `SECTION_CATEGORIES`, і кожна категорія з запиту є в `sends.items`.
    - Мітки: `current_prose`, `prose_fragments`, `allowed_ids`, `memory_core`, `memory_threads`, `memory_claims`, `day_changed`, `allowed_location_ids`, `bible_facts`.
    - Якщо додати нову мітку без категорії, тест падає.
  - `test_sends_words_sum_the_prose_of_target_scenes`: `words` дорівнює сумі слів прози цільових сцен.
  - `test_sends_omit_places_and_series_when_absent`.
  - `test_local_endpoint_is_flagged`: `base_url` з `localhost`, `127.0.0.1` чи `[::1]` дає `local=True`; `https://openrouter.ai/...` і Codex — `False`.
  - Playwright: діалог показує рядок «отримає: …», а для локальної моделі — рядок про локальну адресу.
- [ ] **Step 2: Перевірити, що тести падають.**
- [ ] **Step 3: Реалізувати** `SECTION_CATEGORIES` (мітка → категорія), `memory_sends`, рендер у `memory-build.js` під рядком моделі.
- [ ] **Step 4: Прогнати** pytest і `memory-build.spec.mjs`.
- [ ] **Step 5: Коміт.**

### Task 4: Документація, вітрина, SPEC

**Files:**
- `docs/site/{uk,en}/`: `workspace.md` (новий розділ «Режим «Пишу сам»» / «"I write myself" mode»), `first-story.md`, `memory.md`, `mcp.md`, `index.md`;
- `integrations/claude/obscura/skills/{start-story,draft-scene,revise,series-bible}/SKILL.md` — рядок про `author` там, де названо режими;
- знімок `docs/site/images/{uk,en}/workspace-author.png` через `scripts/capture_screenshots.py` на нейтральному прикладі;
- `SPEC.MD` (WRITING-MODE S09 — інтерфейс; MEMORY-BUILD — новий сценарій «що отримає модель»), `docs/verification/traceability.json`;
- журнал `docs/superpowers/plans/2026-10-20-remediation-progress.md`;
- «Фактично» в специфікації;
- локально `store_listing/listing.md` в основній теці: розділ «WRITE IT YOURSELF» / «ПИШІТЬ САМІ» і рядок у «Product features».

- [ ] **Step 1: Тексти сайту й скілів.** Після кожної пари запустити `PYTHONUTF8=1 .venv/Scripts/python.exe scripts/check_site.py --rehash <slug>`.
- [ ] **Step 2: Знімок.** Запустити `scripts/capture_screenshots.py` лише для нового знімка; випадково перезаписані знімки повернути `git checkout -- <files>`.
- [ ] **Step 3: SPEC і traceability.** Для S09 вказати тести Playwright як ручну процедуру з причиною. Сценарій MEMORY-BUILD прив'язати до тестів Task 3.
- [ ] **Step 4: Перевірка.** `check_docs.py` → «узгоджені»; `pytest tests/test_claude_plugin.py tests/test_capture_screenshots.py tests/docs* -q`.
- [ ] **Step 5: Коміт.**
