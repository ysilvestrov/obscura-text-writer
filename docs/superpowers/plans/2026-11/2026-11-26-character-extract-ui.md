# R-51 PR 2: обв'язка пошуку персонажів — план

> **Для виконавця:** superpowers:executing-plans (інлайн), фінальне рев'ю всієї гілки — окремим рев'юером.

**Мета:** дати автору в інтерфейсі те, що PR 1 дав через API і MCP: запуск пошуку персонажів зі сторінки «Персонажі», стан запуску, список пропозицій із поштучним прийняттям і посилання з діалогу побудови пам'яті.

**Архітектура:** новий модуль `src/storygen/web/static/character-extract.js` (діалог запуску, рядок стану запуску, список пропозицій) підключається до `characters.js`. Сервер не змінюється: використовуються `POST …/character-extract/preview`, `POST /api/runs`, `GET /api/stories/{id}/runs`, `GET /api/runs/{id}`, `POST /api/runs/{id}/pause|resume|cancel`, `GET …/character-proposal`, `POST …/character-proposal/accept` (з `dry_run`). `memory-build.js` додає посилання.

**Специфікація:** `docs/superpowers/specs/2026-11/2026-11-25-character-extract-design.md` §6, §7 (сайт), Поправка 1 (ідентифікатор `run_id`).

## Глобальні обмеження

- Тексти інтерфейсу — лише ключі `i18n.json` (uk і en); відмови сервера перекладаються каталогом за точним українським текстом (ключі `character_extract.server.*`, значення uk = константа сервера).
- Без `innerHTML`; текст автора (назви сцен, імена, цитати) ніколи не локалізується.
- Ціна — лише `cost.total_usd` сервера (як `costText` у `memory-build.js`), без множення ціни виклику.
- Запуск — лише після «Запустити» з `extract_plan_fingerprint` показаного перегляду; 409 «План змінився» перечитує перегляд, нічого не запускає.
- Ліміт бюджету запуску не передається (сервер бере ліміт із налаштувань; перегляд відмовляє без явного ліміту).
- Нічого не записується без «Прийняти вибране»; перегляд прийняття — `dry_run: true`.
- Кнопка видима, коли хоч одна активна сцена має голову прози (`heads.prose` у `GET /api/stories/{id}`).
- Прийняття недоступне, поки в редакторі карток є незбережені правки (прийняття змінює картки й ревізію твору); після прийняття картки перечитуються.

## Фокус рев'ю

1. Повторне відкриття сторінки під час запуску: стан і кнопки відновлюються з `GET /api/stories/{id}/runs`.
2. Пропозиція, яку вже прийнято чи замінено новим запуском (409): повідомлення сервера, список перечитується, нічого не записано.
3. Швидкі зміни прапорців: застарілі відповіді `dry_run` не перезаписують новіші.
4. Нова картка не вибрана, а її учасник є в складі сцени чи вона кандидат у героя: сервер пропускає з причиною, інтерфейс показує підсумок.
5. Вузький екран: список пропозицій без горизонтальної прокрутки.

---

### Task 1: діалог запуску й стан запуску

**Files:** Create `src/storygen/web/static/character-extract.js`; Modify `src/storygen/web/templates/characters.html`, `src/storygen/web/static/characters.js`, `src/storygen/web/static/characters-page.css`, `src/storygen/web/static/i18n.json`; Test `tests/web/test_character_extract_ui.py`, `tests/web/browser/character-extract.spec.mjs`, фікстура `/test-character-extract` у `tests/web/browser/server.py`.

**Interfaces:** `installCharacterExtract({storyId, api, json, notice, onAccepted, isDirty})` — експорт модуля; `characters.js` викликає його з `onAccepted=()=>load(true)` і `isDirty=()=>buffer.dirty||buffer.saving`.

- Розмітка: розділ `#character-extract` (кнопка `#character-extract-open`, рядок стану `#character-extract-run` з кнопками pause/resume/cancel, контейнер пропозиції `#character-proposal`), діалог `#character-extract-dialog` (поле `#character-extract-words` 1000–20000 крок 500, типово 5000; `#character-extract-summary` — сцени, групи, виклики, модель; `#character-extract-cost`; `#character-extract-skipped` — пропущені сцени з причинами; `#character-extract-pending` — попередження про неприйняту пропозицію; `#character-extract-reason`; `#character-extract-status` role=status; `#character-extract-submit`, `#character-extract-cancel`).
- Перегляд перечитується після зміни розміру групи (із захистом від застарілих відповідей).
- «Запустити»: `POST /api/runs` `{request_id, request:{story_id, scene_id:null, mode:'character_extract', group_words, extract_plan_fingerprint, pause_after:[]}}`; 409 з «План змінився» — перечитати перегляд зі статусом «Перегляд застарів».
- Стан: останній запуск `character_extract` книги; поки активний — опитування `GET /api/runs/{id}` кожні 2 с; показ «Прочитано груп: N з M · викликів: K»; pause/resume/cancel — чинні ендпоінти; завершення → завантажити пропозицію (Task 2).
- `?extract=1` відкриває діалог після завантаження й прибирає параметр.
- Тести: python — розмітка, ключі i18n обох мов, константи сервера = значення uk, відсутність `innerHTML`/`per_call_usd`; браузер — перегляд показує сцени й ціну, «Запустити» шле відбиток, запуск можна скасувати.

### Task 2: список пропозицій і прийняття

**Files:** Modify `character-extract.js`, `i18n.json`, `characters-page.css`; тести ті самі.

- Групи «Нові картки» (ім'я, інші імена з прапорцями, цитати з назвою сцени, перша сцена), «Нові імена» (ім'я наявної картки, імена з прапорцями), «Головний герой» (один прапорець з іменем), «Склад сцен» (сцена, `set`/`add`, учасники). Кожен пункт має прапорець; у групи — «Вибрати все» / «Зняти все».
- Типово вибрано все, крім імен з `suggested: false`.
- Будь-яка зміна → `dry_run` (з номером запиту, застарілі відкидаються) → «Пам'ять N сцен стане застарілою» або «Пам'ять жодної сцени не застаріє».
- «Прийняти вибране» → запис; підсумок: застосовано N, пропущено — список «пункт: причина»; потім `onAccepted()` і пропозиція зникає. 409 — повідомлення сервера й перечитування пропозиції.
- Порожня пропозиція (нічого не знайдено): рядок «Пошук нічого не запропонував».
- Тести: браузер — фікстура з готовою пропозицією; невибране ім'я `suggested:false`; зняття картки змінює рядок застарілості; прийняття створює картку й показує пропуск; знімок `docs/images/character-proposal-{project}.png`.

### Task 3: посилання з побудови пам'яті

**Files:** Modify `memory-build.js`, `i18n.json`; Test `tests/web/browser/memory-build.spec.mjs` (наявний тест попередження) або новий.

- У попередженні «немає карток» `renderCast` додає посилання `#memory-build-extract` «Знайти персонажів у прозі…» на `/stories/{id}/characters?extract=1`.

### Task 4: SPEC, сайт, traceability

- SPEC.MD `CHARACTER-EXTRACT`: опис інтерфейсу (§6) і новий Scenario S11 (інтерфейс: перегляд → запуск → пропозиція → прийняття) з тестом у traceability; `MANUSCRIPT-IMPORT` — посилання з попередження.
- Сайт uk/en: `characters` (новий розділ «Пошук персонажів у прозі»), `memory` (посилання з попередження), `manuscript-import` (порада шукати персонажів до побудови пам'яті), знімок; `check_site.py --rehash` для кожної пари.
- Специфікація зміни: статус «Поправка 1 погоджена злиттям #331».
- Журнал виконання беклогу: запис про PR 2.
