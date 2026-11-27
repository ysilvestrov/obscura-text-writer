# Проба довгої прози й серії — інтерфейс і документація (R-47, PR 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Автор у збірці Store бачить пробу у вікні Obscura, вмикає її з підтвердженням (книга, серія, імпорт) і після цього працює з книгою чи серією проби без API; сайт, скіли й SPEC це описують.

**Architecture:** Сервер (ядро, PR #343) уже тримає межу. Обв'язка:
- додає відповіді твору поле `long_prose` (`long_prose_for`);
- додає шаблонам два глобали, які в `full` не читають базу;
- переводить модулі книги з загального `app-info.long_prose` на поле твору;
- додає один модуль інтерфейсу проби `long-prose-trial.js`: стан, підтвердження, вмикання, текст «використано».

Інтерфейс лише ховає й пропонує дії; кожну межу перевіряє сервер.

**Tech Stack:** FastAPI + Jinja, ES-модулі без збирання (`src/storygen/web/static`), `i18n.json`, node-тести (`tests/web/js/*.mjs`), Playwright (`tests/web/browser/*.spec.mjs`, фікстура `tests/web/browser/server.py`), pytest.

**Spec:** [2026-11-26-long-prose-trial-design.md](../../specs/2026-11/2026-11-26-long-prose-trial-design.md), §3.4–3.6. Чинні SPEC.MD LONG-PROSE-TRIAL S01–S06 і злитий код ядра мають перевагу над §3 дизайну там, де ядро вже вирішило інакше:
- сім констант замість трьох;
- поле `bible`;
- `/series` відкрита, поки проба вільна.

**Depends on:** #342 і #343 злито (`origin/main` 7092701f).

## Global Constraints

- Тексти відмов сервера не змінюються. Кожна з `TRIAL_USED`, `TRIAL_SERIES_FULL`, `TRIAL_IN_SERIES`, `TRIAL_CONFIRM`, `TRIAL_NOT_NEEDED`, `TRIAL_BOOK_ALONE`, `TRIAL_BIBLE_USED` отримує ключ `trial.refusal.<suffix>` в `i18n.json`. Значення uk точно дорівнює константі, en — переклад. Так `diagnostic()` перекладає відмову, як `book.readonly` = `READ_ONLY`.
- Нові тексти інтерфейсу (uk / en), ключі точні:
  - `trial.offer_book`: «Спробувати частини й арки на цій книзі» / "Try parts and arcs on this book"
  - `trial.offer_series`: «Зробити пробною серією» / "Make this the trial series"
  - `trial.create_series`: «Створити пробну серію» / "Create the trial series"
  - `trial.confirm`: «Увімкнути пробу на «{p0}»? Проба одна. Інші книги з частинами й серії будуть доступні в платній версії.» / "Turn on the trial for “{p0}”? There is one trial. Other books with parts and other series will be available in the paid version."
  - `trial.used`: «Пробу використано на «{p0}»» / "The trial is used on “{p0}”"
  - `trial.used_untitled`: «Пробу вже використано» / "The trial is already used" (коли `title` порожній: твір чи серію видалено)
  - `trial.import_checkbox`: «Імпортувати з частинами як пробну книгу» / "Import with parts as the trial book"
  - `trial.import_hint`: «Без позначки книга імпортується без частин.» / "Without it the book is imported without parts."
  - `trial.leave_warning`: «Книга вийде із серії проби й збереже частини й арки, але місце в серії проби не звільниться.» / "The book leaves the trial series and keeps its parts and arcs, but its place in the trial series is not freed."
  - `trial.series_list_hint`: «Пробною може стати серія, у якій не більше двох книг.» / "A series with at most two books can become the trial series."
- Посилання на список очікування — наявне `app.link.waitlist` з `waitlist_url` з `app-info`. Без адреси посилання немає.
- Після успішного вмикання сторінка перезавантажується (`location.reload()`). `appInfo()` кешує відповідь на сторінку, тож інакше модулі бачили б старий стан.
- У виданнях `full` і `paid` нові глобали шаблонів і поле `long_prose` твору не відкривають базу. Тест із підміненим `repo.db`, як у `tests/book/test_long_prose_for.py`.
- MCP пробу не вмикає. Міст не передає `trial` в імпорт.
- Знімки сайту — лише з нейтральним прикладом. Нових знімків цей PR не додає (див. Task 6).
- Команди з worktree: `PYTHONPATH=$PWD/src PYTHONUTF8=1 /c/Projects/text-generator/.venv/Scripts/python.exe -m pytest … -p no:cacheprovider`. Браузерні: `cd frontend && npx playwright test <spec>`. Після SPEC — `scripts/check_docs.py`, після сайту — `scripts/check_site.py --rehash <slug>`.

## Review Focus

- Перевірки store-видання, що вже є (`build-edition.spec.mjs`, `book-structure.spec.mjs:122`, `library-series.spec.mjs`, `manuscript-import.spec.mjs`), тепер виконуються з вільною пробою. Банер `#book-readonly` зберігає свій точний текст, кнопка проби стоїть поруч в окремому вузлі. Кожен Store-тест скидає пробу (`/test-reset-trial`) у `beforeEach`.
- Назва проби порожня (твір у кошику й видалений назавжди, серію видалено): «Пробу вже використано», без `«null»`.
- `/series` у Store показує серії з інших видань. Їхні сторінки дають 404, тож рядок без посилання. Поки проба вільна, серія з ≤ 2 книгами має кнопку «Зробити пробною серією». Після проби на серії список показує лише її.
- Діалог імпорту в чотирьох станах: `none`, `available`, `used`+`story`, `used`+`series`. Частини йдуть лише з позначкою (і разом із `trial: true`) або в серію проби. `trial` і `series` разом не надсилаються ніколи.
- Мобільний проєкт Playwright: кнопки проби доступні й на вузькому екрані.

---

### Task 1: Поле твору, глобали шаблонів, переклади, модуль проби, фікстура

**Files:**
- Modify: `src/storygen/web/routes_stories.py:144`: у словник відповіді додається `"long_prose": guard.long_prose_for(repo, story)` на верхньому рівні, поруч із `"story"`, а не в моделі `Story`.
- Modify: `src/storygen/web/app.py:68–79`: два глобали поруч із `long_prose()`:
  - `series_screen() -> bool`: у виданні з довгою прозою `True` без бази; інакше стан `trial_state(app.state.repo)` — `available` або `used` з `kind == 'series'`;
  - `series_open(series_id) -> bool` = `guard.series_long_prose(app.state.repo, series_id)`.
- Modify: `src/storygen/web/templates/library.html`:
  - кнопка «Серії» показується за `series_screen()`;
  - посилання на серію в бібліотеці — за `series_open(entry.series.id)`;
  - рядок серії й рядок маркерів частин у діалозі імпорту — за `series_screen()`, далі їх ховає JS (Task 4).
- Modify: `src/storygen/web/static/i18n.json`: ключі з Global Constraints, uk і en.
- Create: `src/storygen/web/static/long-prose-trial.js`:
  - `trialState(info) -> {state, kind, id, title}` з `info.long_prose_trial`; без поля — `{state: 'none'}`;
  - `usedText(state) -> string`: `trial.used` з назвою або `trial.used_untitled`;
  - `claimBody(target) -> {story_id}|{series_id}` з `confirm: true`;
  - `async claimTrial({api, json, confirmDialog, notice, location}, target, title) -> boolean`: підтвердження з `trial.confirm`; на згоду — `POST /api/long-prose-trial`, далі `location.reload()`; відмову показує `notice(e.message,'error')`;
  - `usedNotice(document, state, info) -> HTMLElement`: абзац `usedText` і, якщо є `waitlist_url`, посилання `app.link.waitlist`.
- Modify: `tests/web/browser/server.py`: `POST /test-reset-trial` видаляє `app_settings['long_prose_trial']`. Ендпойнт лише фікстурний, поруч із `/test-build-edition`.
- Test:
  - `tests/web/test_long_prose_trial_ui.py` (новий);
  - `tests/web/js/long_prose_trial.mjs` (новий);
  - перенесені з ядра тести в `tests/series/test_series_trial.py` і `tests/application/test_manuscript_import_trial.py`.

**Interfaces:**
- Produces:
  - поле відповіді `GET /api/stories/{id}` → `long_prose: bool`;
  - глобали `series_screen()` і `series_open(id)`;
  - модуль `long-prose-trial.js` з `trialState`, `usedText`, `claimBody`, `claimTrial`, `usedNotice`;
  - фікстура `/test-reset-trial`.

- [ ] **Step 1: Failing tests (pytest)**
  - `test_story_view_long_prose_full_reads_no_trial`: у `full` поле `long_prose` дорівнює `True`, а `trial_state` не викликається (monkeypatch, що падає).
  - `test_story_view_long_prose_store`: у `store` пласка книга без проби → `False`; книга проби → `True`; друга книга з частинами → `False`.
  - `test_library_template_store_states`: рендер `/` у `store`:
    - проба вільна: є `href="/series"` і `#manuscript-import-series-row`;
    - проба на книзі: обох немає;
    - проба на серії: посилання на неї є, на іншу серію немає.
  - `test_trial_refusals_are_translated`: для кожної з семи констант `translate('trial.refusal.<suffix>','uk') == константа`, а `diagnostic(константа,'en')` дає англійський текст.
  - Перенесені дрібниці ядра (раніше відкладені):
    - `test_restored_trial_book_is_editable_again`: книга проби → кошик → відновлення → `PUT` структури дає 200;
    - `test_refused_third_import_leaves_no_files`: третій імпорт у серію проби → 400 `TRIAL_SERIES_FULL`, у теці твору й імпорту немає нових файлів, `.applying` повернуто.

- [ ] **Step 2: Failing node test** `tests/web/js/long_prose_trial.mjs`, під'єднаний через pytest-обгортку в `test_long_prose_trial_ui.py` у шаблоні `test_book_structure_ui.py`. Перевіряє:
  - `usedText({state:'used',title:'Маяк'})` → `Пробу використано на «Маяк»`;
  - `usedText({state:'used',title:null})` → `Пробу вже використано`;
  - `claimBody({series_id:'s1'})` → `{series_id:'s1',confirm:true}`;
  - `claimTrial` з відмовою підтвердження не викликає `api`; зі згодою викликає `api` один раз і `location.reload` один раз.

- [ ] **Step 3: Run** — усі нові тести FAIL (немає поля, глобалів, ключів, модуля).

- [ ] **Step 4: Implement** файли з розділу Files.

- [ ] **Step 5: Run** `pytest tests/web/test_long_prose_trial_ui.py tests/web/test_book_structure_ui.py tests/web/test_localization.py tests/series/test_series_trial.py tests/application/test_manuscript_import_trial.py` — PASS.

- [ ] **Step 6: Commit** `feat(R-47): поле long_prose твору, глобали серій, переклади відмов і модуль проби`.

---

### Task 2: Книга — модулі за полем твору і кнопка проби

**Files:**
- Modify: `src/storygen/web/static/book-structure-ui.js`:
  - `longProse` береться з `state.view.long_prose`, а не з `appInfo`;
  - банер `#book-readonly` лишається тим самим абзацом із тим самим текстом;
  - коли проба вільна і книга не в серії, після банера стоїть `#book-readonly-trial` з кнопкою `trial.offer_book` (`claimTrial`, `{story_id}`);
  - коли проба використана, на тому самому місці — `usedNotice`.
- Modify: `src/storygen/web/static/book-structure-panel.js`:
  - панель монтується за `view.long_prose` (з `GET /api/stories/{id}`);
  - якщо поле `false`, проба вільна і книга не в серії, на місці панелі стоїть картка з `book.panel.title`, коротким поясненням і кнопкою `trial.offer_book`;
  - проба використана — `usedNotice`;
  - книга в серії без довгої прози — нічого.
- Modify: `src/storygen/web/static/memory-build.js:39–41`: `readOnly()` дорівнює `!state.view?.long_prose && (structured || series_id)`; `offer` у рядку 141 — за `state.view.long_prose`.
- Modify: `src/storygen/web/static/series-facts.js:88`: монтування за полем `long_prose` твору.
- Test:
  - `tests/web/browser/long-prose-trial.spec.mjs` (новий; store-видання й скидання проби в `beforeEach`, повернення `full` в `afterEach`);
  - `tests/web/test_book_structure_ui.py`: провідка модулів.

**Interfaces:**
- Consumes: `long_prose` твору, `long-prose-trial.js` (Task 1).

- [ ] **Step 1: Failing browser tests**
  - `flat book offers the trial in settings and gets the structure panel after it`:
    - пласка книга, сторінка налаштувань → кнопка `Спробувати частини й арки на цій книзі`;
    - діалог із текстом `trial.confirm` і назвою книги → «Так»;
    - після перезавантаження видно `#book-structure-panel` (кнопка «Додати частину»), кнопки проби немає.
  - `structured book banner keeps its text and offers the trial`:
    - `#book-readonly` має точний текст `READ_ONLY`;
    - `#book-readonly-trial button` видно;
    - після вмикання банера немає і `#save-text` не вимкнено.
  - `used trial shows where it went and the waitlist`: проба на книзі A, відкрита книга B з частинами → `#book-readonly-trial` містить `Пробу використано на «A»` і посилання `app.link.waitlist`.
  - `trial book keeps the memory-build menu`: меню збирання пам'яті не приховане для книги проби з частинами.

- [ ] **Step 2: Run** `npx playwright test long-prose-trial.spec.mjs` — FAIL.

- [ ] **Step 3: Implement** чотири модулі.

- [ ] **Step 4: Run** `long-prose-trial.spec.mjs book-structure.spec.mjs build-edition.spec.mjs memory-build.spec.mjs` — PASS в обох проєктах.

- [ ] **Step 5: Commit** `feat(R-47): кнопка проби в книзі, модулі книги за полем long_prose`.

---

### Task 3: Серії — сторінка, бібліотека, налаштування книги

**Files:**
- Modify: `src/storygen/web/static/series-page.js`:
  - **Покажчик серій** (`loadList`) у виданні без довгої прози:
    - поки проба вільна, над списком — `trial.series_list_hint`;
    - форма створення після підтвердження шле `POST /api/series` з `trial: true` і перезавантажує сторінку; кнопка підписана `trial.create_series`;
    - рядок серії без `series_open` не є посиланням;
    - серія з ≤ 2 книгами (без біблії) має кнопку `trial.offer_series`;
    - з пробою на серії список показує лише серію проби (фільтр за `id` з `app-info`), а форма створення прихована.
  - **Екран серії проби:** кнопка «Нова книга» вимкнена, коли в серії вже дві книги, і має підказку з текстом `TRIAL_SERIES_FULL` (`trial.refusal.series_full`). Сервер усе одно відмовить.
  - Стан проби береться з `appInfo()`; у `full` нічого не змінюється.
- Modify: `src/storygen/web/static/series-settings.js:62`, умова монтування форми:
  - `view.long_prose`;
  - або проба на серії, і книга не покрита іншою пробою (`view.long_prose === false`, а книга або вже в серії проби, або поза серіями).
  - Пробна книга `kind=story` форми не має: сервер відповів би `TRIAL_BOOK_ALONE`.
  - У виданні без довгої прози список містить лише «Без серії» і серію проби, без «Нова серія».
  - Вихід книги із серії проби (вибрано «Без серії», книга в серії проби) спершу показує `confirmDialog(trial.leave_warning)`.
- Test:
  - `tests/web/browser/long-prose-trial.spec.mjs`, нові тести;
  - `tests/web/test_long_prose_trial_ui.py`: шаблон `/series` у трьох станах.

- [ ] **Step 1: Failing tests**
  - Browser `free trial creates the trial series from the series page`:
    - бібліотека → «Серії» → назва → «Створити пробну серію» → підтвердження;
    - після перезавантаження список має лише цю серію, форми створення немає.
  - Browser `a series from another edition can become the trial series but is not a link`:
    - серію з двома книгами створено через `/test-build-edition full`, потім повернуто `store`;
    - рядок без `a[href]`, кнопка `Зробити пробною серією` → підтвердження → після перезавантаження рядок веде на `/series/{id}`.
  - Browser `third book of the trial series is disabled with the paid hint`: серія проби з двома книгами → «Нова книга» `disabled` з підказкою `TRIAL_SERIES_FULL`.
  - Browser `leaving the trial series warns that the place stays taken`: налаштування книги серії проби → «Без серії» → «Зберегти» → діалог із `trial.leave_warning`; «Ні» лишає серію.
  - Browser `book settings offer only the trial series`: книга поза серіями, проба на серії → варіанти `['', <id серії проби>]`.
  - Pytest `test_series_index_store_states`: `/series` дає 200 з вільною пробою чи пробою на серії і 404 з пробою на книзі. Це вже S01, тест закріплює шаблон.

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement** `series-page.js` і `series-settings.js`.

- [ ] **Step 4: Run** `long-prose-trial.spec.mjs library-series.spec.mjs` і `pytest tests/web/test_long_prose_trial_ui.py tests/series` — PASS.

- [ ] **Step 5: Commit** `feat(R-47): пробна серія на сторінці серій і в налаштуваннях книги`.

---

### Task 4: Діалог імпорту рукопису

**Files:**
- Modify: `src/storygen/web/static/manuscript-import.js`:
  - **`applyBody(state)`** отримує `state.edition` (поле `edition` перегляду) і `state.trial_checked`:
    - частини й `part_index` надсилаються, якщо `edition.parts_allowed` і виконується одна з умов:
      - видання з довгою прозою (`edition.trial.state === 'none'`);
      - позначено `trial_checked` за `edition.trial.state === 'available'`; тоді в тілі є `trial: true`;
      - вибрано серію з `id === edition.trial.id` за пробою `kind=series`.
    - `series` надсилається лише за `edition.series_allowed`;
    - `trial` і `series` разом не надсилаються ніколи (позначка скидає вибір серії).
  - Поле `long_prose` стану прибирається.
  - **`edition()`:**
    - рядки серії й маркерів частин показуються за `app-info`: довга проза, вільна проба або проба на серії;
    - список серій у виданні без довгої прози містить лише серію проби.
  - **Після перегляду:**
    - за `edition.trial.state === 'available'` і частин у перегляді стоїть позначка `#manuscript-import-trial` з `trial.import_checkbox` і `trial.import_hint`;
    - позначка вимикає вибір серії.
- Modify: `src/storygen/web/templates/library.html`: вузол позначки поруч із `#manuscript-import-series-row`, `hidden`.
- Test:
  - `tests/web/js/manuscript_import_boundaries.mjs`: матриця `applyBody`;
  - `tests/web/browser/manuscript-import.spec.mjs`: нові store-тести зі скиданням проби.

- [ ] **Step 1: Failing node assertions** (ті самі сцени з `part_index`):
  - `none`: частини й серія йдуть, як зараз;
  - `available` без позначки: `parts: []`, без `part_index`, без `trial`;
  - `available` з позначкою: частини, `trial: true`, без `series`, навіть якщо серію вибрано;
  - `used`+`series`, вибрано серію проби: частини й `series`, без `trial`;
  - `used`+`series`, без серії: без частин;
  - `used`+`story`: без частин і серії.

- [ ] **Step 2: Failing browser tests** (Store):
  - `free trial imports a manuscript with parts as the trial book`:
    - рукопис із частинами → є позначка → позначити → «Імпортувати»;
    - відкрита книга має панель структури з частинами;
    - `app-info` → `used`, `kind: 'story'`.
  - `without the checkbox the book is imported flat`.
  - `series trial offers only its series and keeps parts there`.

- [ ] **Step 3: Run** — FAIL.

- [ ] **Step 4: Implement.**

- [ ] **Step 5: Run** `pytest tests/web/test_manuscript_import_ui.py` і `npx playwright test manuscript-import.spec.mjs long-prose-trial.spec.mjs` — PASS.

- [ ] **Step 6: Commit** `feat(R-47): імпорт рукопису як пробної книги в діалозі`.

---

### Task 5: Скіли Claude і міст

**Files:**
- Modify: `integrations/claude/obscura/skills/start-story/SKILL.md:46`. Речення «Parts and series are only for the full edition: check `edition` before offering them» змінюється так:
  - частини й серії є, якщо `edition.parts_allowed` / `series_allowed`;
  - якщо `edition.trial.state` дорівнює `available`, чат не імпортує частини сам: він пояснює автору, що одну книгу з частинами чи одну серію з двох книг можна спробувати безкоштовно, імпортувавши рукопис у вікні Obscura з позначкою «Імпортувати з частинами як пробну книгу», і дає посилання з `next_steps`;
  - без проби пропонує плаский імпорт.
- Modify: `integrations/claude/obscura/skills/series-bible/SKILL.md:44`. Коли `series` дорівнює null, а відмова чи `app-info` кажуть, що проба вільна, чат пояснює, що пробну серію створює автор на сторінці «Серії» у вікні Obscura.
- Test:
  - `tests/mcp/test_bridge_edition.py`: `test_import_confirm_never_sends_trial`. Тіло підтвердження імпорту в мосту не має ключа `trial`, навіть якщо `edition.trial.state == 'available'`.
  - `tests/test_claude_plugin.py`: наявні тести скілів проходять.

- [ ] **Step 1:** Тест моста. Якщо він проходить одразу (міст і так не передає `trial`), це фіксація контракту, не RED; записати це в журнал.

- [ ] **Step 2:** Правки двох скілів.

- [ ] **Step 3: Run** `pytest tests/mcp tests/test_claude_plugin.py tests/test_codex_skills.py` — PASS.

- [ ] **Step 4: Commit** `docs(R-47): скіли пропонують пробу у вікні Obscura`.

---

### Task 6: Сайт uk/en

**Files:** `docs/site/{uk,en}/`. Кожну пару підтвердити `scripts/check_site.py --rehash <slug>`.
- `paid.md`: розділ «Проба в збірці з Microsoft Store»:
  - одна книга з частинами й арками або одна серія з двох книг і біблії, назавжди, одна на теку творів;
  - як увімкнути: налаштування книги, банер, сторінка «Серії», імпорт з позначкою;
  - що лишається платним: третя книга серії, друга серія, друга книга з частинами; межа рейтингу Store у пробі та сама (посилання на [Віковий рейтинг](content-rating.md), як і в наявному пункті сторінки);
  - кошик пробу не повертає.
- `install.md` (розділ Microsoft Store): одне речення про пробу з посиланням на `paid.md`.
- `book-structure.md:5,98`: «У збірці з Microsoft Store їх немає» → «…є лише в пробі».
- `series.md:5,110`: те саме, плюс вихід книги із серії проби не звільняє місця.
- `manuscript-import.md`: позначка «Імпортувати з частинами як пробну книгу».
- `mcp.md:335`: чат пробу не вмикає, а підказка каже, чи вона вільна.

Знімки: наявні знімки сайту знято у виданні `full` (`scripts/capture_screenshots.py`), і обв'язка їх не змінює. Нових знімків Store-екранів не додаю: §5 дизайну лишає їх будівельнику, а без них сторінки зрозумілі. Якщо власник захоче знімок кнопки проби, це окреме доповнення.

- [ ] **Step 1:** Правки шести пар.
- [ ] **Step 2: Run** `scripts/check_site.py --rehash paid install book-structure series manuscript-import mcp` і `pytest tests/test_docs_site.py` — PASS.
- [ ] **Step 3: Commit** `docs(R-47): проба на сайті uk/en`.

---

### Task 7: SPEC, traceability, журнал

**Files:**
- `SPEC.MD`, LONG-PROSE-TRIAL:
  - Новий `LONG-PROSE-TRIAL-S07 — Інтерфейс проби`:
    - пласка книга й банер книги з частинами пропонують пробу з підтвердженням;
    - сторінка «Серії» створює пробну серію або робить нею наявну (≤ 2 книги);
    - діалог імпорту має позначку пробної книги;
    - після вмикання сторінка оновлюється;
    - після проби ці місця показують «Пробу використано на «X»» і список очікування;
    - вихід зі серії проби попереджає.
  - Технічний опис:
    - поле `long_prose` твору;
    - глобали `series_screen` / `series_open`;
    - `long-prose-trial.js`.
  - «Відомі обмеження»: прибрати речення про відсутній інтерфейс; лишити обхід новою текою.
  - BUILD-EDITION-001, тех-пункт «Довга проза»: модулі книги питають поле твору.
  - SERIES-S07: екран серій у Store — для проби.
- `docs/verification/traceability.json`: S07 → тести `long-prose-trial.spec.mjs`, `tests/web/test_long_prose_trial_ui.py`, `tests/web/js/long_prose_trial.mjs` (через pytest-обгортку); S03/S04 доповнити перенесеними тестами Task 1.
- `docs/superpowers/plans/2026-10-20-remediation-progress.md`: запис R-47 (три PR, рішення, відкладене).
- Дизайн-спека: «Фактично: <розмір>, 3 PR, <n> задач» — після злиття PR 3, окремим малим комітом або в цьому PR із розміром за фактом.

- [ ] **Step 1:** Правки SPEC і traceability.
- [ ] **Step 2: Run** `scripts/check_docs.py` — «узгоджено».
- [ ] **Step 3: Commit** `docs(R-47): SPEC і traceability інтерфейсу проби`.

## Завершення

1. Фінальне рев'ю всієї гілки окремим рецензентом.
2. `scripts/verify.py` з `C:/tmp/r47c` (junction на `.venv` і `frontend/node_modules`).
3. Cross-review.
4. PR на `main` з «Closes #287», переліком оновлених сторінок сайту uk/en і результатом verify.
5. Після злиття — оновити основну теку.

Рішення, ухвалені в плані (власник перевіряє):
- **Відкладена дрібниця ядра «`claim()` без власної перевірки видання» лишається.** Усі виклики стоять за перевіркою видання, тож окрема перевірка нічого не дасть. Якщо рішення хибне: новий виклик у `full` міг би записати відмітку, яку `full` не читає.
- **Поле `long_prose` твору не додається в MCP `get_story`.** Скілам вистачає `edition` імпорту й підказки відмови. Якщо рішення хибне: чат не бачить, що книга пробна, доки не отримає відмову.
- **Після вмикання сторінка перезавантажується, кеш `appInfo` не скидається.** Перезавантаження простіше й надійніше для п'яти модулів. Ціна: перезавантаження втрачає незбережені правки на сторінці. Кнопки проби стоять у налаштуваннях і банері книги лише для читання, де незбереженого тексту немає.
