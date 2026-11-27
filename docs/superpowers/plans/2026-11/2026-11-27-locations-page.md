# Окрема сторінка «Локації» — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Мета:** панель «Локації» переїжджає з вкладки «Пам’ять» сцени на окрему сторінку `/stories/{id}/locations` з кнопкою в шапці твору; робочий простір, повертаючись на екран, звіряє ревізію твору.

**Архітектура:** новий маршрут і шаблон за взірцем «Персонажів»; `locations-panel.js` монтується в сторінку й бере ID твору з `data-story-id`, без `editor.js`; у «Пам’яті» лишається посилання (`locations-link.js`); `scene-revisions` віддає `story_revision`, `scene-sync-workspace.js` перечитує сторінку й за нею.

**Стек:** FastAPI + Jinja2, ванільні ES-модулі, pytest, node-тести `tests/web/js/*.mjs`, Playwright (`pnpm --dir frontend exec playwright test …`).

**Специфікація:** `docs/superpowers/specs/2026-11/2026-11-27-locations-page-design.md` (затверджено 2026-11-27).

## Global Constraints

- Дії панелі, тексти дій, підтвердження, API `/api/stories/{id}/locations…` і дані — без змін.
- Кнопка `a#workspace-locations.button.secondary.icon-button` між `#workspace-characters` і `#workspace-settings`; іконка `static/icons/map-pin.svg` (Lucide map-pin, ISC; ліцензія вже в `static/licenses/lucide-ISC.txt`), клас `.icon-map-pin` в `app.css` поруч з `.icon-users`. Вміст файлу — атрибути як у `icons/users.svg`, тіло: `<path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/>`.
- Нові ключі каталогу uk/en: `locations.nav` («Локації» / «Locations»), `locations.memory_link` («Локації твору →» / «Story locations →»), `locations.page_empty` (порожній стан, див. Task 2).
- `href` кнопки й посилання з «Пам’яті» несуть `scene` і `material`, коли сцена відкрита; «← До твору» — `workspace-links.js::returnLink(storyId, location.search)`.
- Заголовок вкладки: «Локації — <назва> — Obscura» (як у `characters.html`, `data-i18n-title-prefix="locations.nav"`).
- Документація українською; маркери OpenSpec англійською; кожен новий Scenario — запис у `docs/verification/traceability.json`.
- `verify.py` і повний pytest — з `C:/tmp/<коротка>` (detached worktree, junction на `.venv` і `frontend/node_modules`).

## Review Focus

1. Відкриття сторінки без відкритої сцени (прямий URL, кнопка з робочого простору без вибраної сцени) — «← До твору» веде на `/stories/{id}` без параметрів, сторінка працює. → Task 1, pytest на шаблон і Task 4 Playwright.
2. Відхилене збереження опису (409), потім вихід — браузер перепитує; після успішного збереження — не перепитує. → Task 2 (node-тест `hasDrafts`), Task 4 Playwright.
3. Брудний буфер сцени при поверненні з «Локацій» (BFCache/фокус) і зміненій ревізії твору — текст автора не перезаписується. → Task 3, node-тест правила.
4. Власна зміна робочого простору (збереження сцени) рухає ревізію твору — повернення на екран не спричиняє зайвого циклу перечитувань, бо `state.view` уже свіжий. → Task 3, node-тест правила.
5. Mobile 375 px: шапка з додатковою іконкою й сторінка «Локації» без горизонтального прокручування. → Task 4 Playwright.

---

### Task 1: Маршрут, шаблон, кнопка в шапці

**Files:**
- Modify: `src/storygen/web/routes_stories.py` (поруч із `GET /stories/{id}/characters`, рядок ~85)
- Create: `src/storygen/web/templates/locations.html`
- Create: `src/storygen/web/static/icons/map-pin.svg`
- Modify: `src/storygen/web/templates/story.html` (шапка; список скриптів), `src/storygen/web/static/app.css`, `src/storygen/web/static/workspace-navigation.js`, `src/storygen/web/static/i18n.json`
- Test: `tests/web/test_locations_ui.py`

**Interfaces:**
- Produces: сторінка з `main#locations-page.characters-page[data-story-id]`, `a#locations-return`, `section#story-locations`, скрипт `/static/locations-panel.js`; кнопка `#workspace-locations`; ключ `locations.nav`.

- [ ] **Step 1: Тести.** У `tests/web/test_locations_ui.py` замінити `test_story_page_has_the_section_and_both_languages_have_the_texts` на два тести:

```python
@pytest.mark.req('MEMORY-LOCATIONS')
def test_locations_page_and_header_button(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))  # як у test_character_availability.py
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        story = client.post('/api/stories', json={'title': 'Пристань'}).json()
        page = client.get(f'/stories/{story["id"]}/locations').text
        assert 'id="locations-page"' in page and f'data-story-id="{story["id"]}"' in page
        assert 'id="locations-return"' in page and 'id="story-locations"' in page
        assert '/static/locations-panel.js' in page
        workspace = client.get(f'/stories/{story["id"]}').text
        assert 'id="workspace-locations"' in workspace and f'/stories/{story["id"]}/locations' in workspace
        assert workspace.index('id="workspace-characters"') < workspace.index('id="workspace-locations"') < workspace.index('id="workspace-settings"')
        assert '/static/locations-panel.js' not in workspace and '/static/editor.js' not in page
        assert client.get('/stories/missing/locations').status_code == 404


@pytest.mark.req('MEMORY-LOCATIONS')
def test_both_languages_have_the_texts():
    catalog = json.loads((STATIC / 'i18n.json').read_text(encoding='utf-8'))
    keys = {k for k in catalog['uk'] if k.startswith('locations.')} | {'memory.locations'}
    assert {'locations.nav', 'locations.memory_link', 'locations.page_empty'} <= keys
    assert keys <= set(catalog['en']) and len(keys) > 20
```

- [ ] **Step 2:** `.venv/Scripts/python.exe -m pytest tests/web/test_locations_ui.py -q` → FAIL (404 сторінки, немає кнопки, немає ключів).
- [ ] **Step 3: Реалізація.**
  - `GET /stories/{id}/locations` → `locations.html` з `{"story": repo.get_story(id)}`, як `characters`.
  - `locations.html` за структурою `characters.html`: `characters-page.css`, `main#locations-page.characters-page[data-story-id]`, `a#locations-return` (текст `m_b38276cdf9d4`, як у персонажів), `header.characters-heading` з `h1` «Локації» (`locations.nav`) і назвою твору, `section#story-locations.story-locations`; скрипт `<script type="module" src="/static/locations-panel.js">`.
  - Кнопка `#workspace-locations` у шапці `story.html` за зразком `#workspace-characters`, `href="/stories/{{story.id}}/locations"`; `workspace-navigation.js` оновлює її `href` тим самим кодом, що й `charactersLink` (винести в одну функцію `linkWithPosition(anchor, path)`).
  - `story.html`: прибрати `/static/locations-panel.js` (до Task 2 панель на сторінці ще шукає `#memory-view` і нічого не малює — проміжний стан у межах PR).
  - Ключі `locations.nav`, `locations.memory_link`, `locations.page_empty` uk/en.
- [ ] **Step 4:** той самий pytest → PASS; `.venv/Scripts/python.exe -m pytest tests/web/test_workspace_layout_ui.py tests/web/test_character_availability.py -q` → PASS.
- [ ] **Step 5: Commit** `feat(locations): сторінка «Локації» й кнопка в шапці твору`.

### Task 2: Панель на сторінці, посилання з «Пам’яті», захист описів

**Files:**
- Modify: `src/storygen/web/static/locations-panel.js`, `src/storygen/web/static/locations.js`, `src/storygen/web/static/app.css` (стилі `.story-locations`/`.location-*` → `characters-page.css` або лишити в `app.css` — на розсуд), `src/storygen/web/static/i18n.json`
- Create: `src/storygen/web/static/locations-link.js`; Modify: `src/storygen/web/templates/story.html` (скрипт `/static/locations-link.js`)
- Test: `tests/web/js/locations.mjs`, `tests/web/test_locations_ui.py`

**Interfaces:**
- Consumes: розмітка сторінки з Task 1.
- Produces: `locations.js::hasDrafts(drafts: Map) -> boolean`; `locations.js::memoryLinkHref(storyId: string, sceneId: string|null, mode: string|null) -> string` (з `scene`/`material`, лише коли обидва є).

- [ ] **Step 1: Тести.** У `tests/web/js/locations.mjs`:

```js
assert.equal(hasDrafts(new Map()),false);
assert.equal(hasDrafts(new Map([['loc_1','текст']])),true);
assert.equal(memoryLinkHref('s1',null,null),'/stories/s1/locations');
assert.equal(memoryLinkHref('s1','sc1','memory'),'/stories/s1/locations?scene=sc1&material=memory');
```

У `tests/web/test_locations_ui.py` новий тест `test_panel_lives_on_its_page`: текст `locations-panel.js` не містить `'./editor.js'`, `'#memory-view'`, `scene-selected`, `story-refreshed`, `refresh(`; містить `'#locations-page'`, `dataset.storyId`, `beforeunload`; `story.html` містить `/static/locations-link.js`.

- [ ] **Step 2:** `.venv/Scripts/python.exe -m pytest tests/web/test_locations_ui.py -q` → FAIL.
- [ ] **Step 3: Реалізація.**
  - `locations-panel.js`: `box()` → `#locations-page #story-locations`; `storyId` з `document.querySelector('#locations-page')?.dataset.storyId`; `load()` викликається одразу при імпорті; без імпорту `editor.js`, без `refresh()` (після `offerInvalidation` нічого не перечитувати); `h3` заголовка розділу прибрати (заголовок сторінки — `h1` у шаблоні), `h4` «Схожі назви»/«Склеєні назви» → `h2`; підказка `locations.hint` лишається під заголовком; порожній стан — `locations.page_empty` з посиланням на сторінку «Персонажі» (`/stories/{id}/characters`). Текст uk: «У творі ще немає локацій. Картки з’являються з рядка «Локація:» у плані сцени, наприклад `Локація: Бар / задня кімната`, і з пошуку місць у прозі на сторінці «Персонажі».»; en — відповідник.
  - `beforeunload`: `if(hasDrafts(drafts)){event.preventDefault();event.returnValue=''}`.
  - `locations-link.js`: на `scene-selected` і `story-refreshed` (з `editor.js::state`) додає в кінець `#memory-view` один `p.memory-locations-link` з `a` (`locations.memory_link`, `href=memoryLinkHref(state.storyId, state.scene?.id, state.mode)`), не дублюючи; лишається після «Підсумків хронології» (якщо ті перемальовуються пізніше — перенести вузол у кінець).
- [ ] **Step 4:** pytest файлу → PASS; `node tests/web/js/locations.mjs .` → без помилок.
- [ ] **Step 5: Commit** `feat(locations): панель на окремій сторінці, посилання з «Пам’яті», захист описів`.

### Task 3: Робочий простір звіряє ревізію твору

**Files:**
- Modify: `src/storygen/web/routes_stories.py::scene_revisions` (рядок ~149), `src/storygen/web/static/scene-sync.js`, `src/storygen/web/static/scene-sync-workspace.js`
- Test: `tests/web/test_scene_revisions_api.py`, `tests/web/js/scene_sync.mjs`, `tests/web/test_scene_sync_ui.py`

**Interfaces:**
- Produces: відповідь `GET /api/stories/{id}/scene-revisions` = `{scenes, writing_mode, story_revision: int}`; `scene-sync.js::storyChanged(view, payload) -> boolean` (`payload.story_revision` — ціле й відрізняється від `view.story.revision`; відсутнє поле → `false`).

- [ ] **Step 1: Тести.**
  - `test_scene_revisions_api.py`: оновити точну рівність у `test_scene_revisions_follow_the_story_view` на `{'scenes': {}, 'writing_mode': 'chat', 'story_revision': story['revision']}`; новий `test_scene_revisions_carry_the_story_revision` (за зразком `test_scene_revisions_carry_the_writing_mode`): після `PUT /api/stories/{id}/writing-mode` `story_revision` у `scene-revisions` дорівнює `GET /api/stories/{id}` → `story.revision` і більша за початкову.
  - `scene_sync.mjs`: `storyChanged({story:{revision:3}},{story_revision:3})===false`; `…{story_revision:4}===true`; `…{}===false`.
  - `test_scene_sync_ui.py::test_workspace_loads_the_sync_and_its_notice` доповнити: `scene-sync-workspace.js` містить `pageshow` і `storyChanged`.
- [ ] **Step 2:** `.venv/Scripts/python.exe -m pytest tests/web/test_scene_revisions_api.py tests/web/test_scene_sync_ui.py -q` → FAIL.
- [ ] **Step 3: Реалізація.** `scene_revisions` додає `"story_revision": story.revision` (одне читання `get_story`). `check()` у `scene-sync-workspace.js`: `const storyMoved=storyChanged(state.view,payload)`; рання відмова (`return`) лише коли немає ні зміни режиму, ні `storyMoved`, ні змін сцен за наявним правилом; далі незмінно `refresh({fresh:true})` (брудний буфер не перезаписується — наявна поведінка `loadView`). Слухач `pageshow`: `if(event.persisted)trigger()`.
- [ ] **Step 4:** pytest обох файлів → PASS; `.venv/Scripts/python.exe -m pytest tests/web/test_scene_sync_ui.py -q` (запускає `scene_sync.mjs`) → PASS.
- [ ] **Step 5: Commit** `feat(workspace): звірка ревізії твору при поверненні на екран`.

### Task 4: Playwright, знімок, SPEC, довідка

**Files:**
- Modify: `tests/web/browser/locations.spec.mjs`, `tests/web/browser/card-invalidation.spec.mjs`, `scripts/capture_screenshots.py` (рядки ~258–263), `docs/images/site/{uk,en}/locations-desktop.png`, `SPEC.MD` (MEMORY-LOCATIONS: абзац «Панель «Локації»», S07, S08, S11, новий S12; MCP-BRIDGE: `story_revision` і `pageshow`), `docs/verification/traceability.json`, `docs/verification/manual.md#locations-panel`, `docs/site/{uk,en}/memory.md`, `docs/superpowers/plans/2026-10-20-remediation-progress.md` (запис про зміну поза беклогом, якщо журнал так веде такі зміни)

- [ ] **Step 1: Playwright.** У `locations.spec.mjs` усі cases відкривають `/stories/${id}/locations` і шукають `#locations-page #story-locations` замість `#memory-view #story-locations`; очікування щодо дій не змінювати. Case «location change … memory-kind conflict» переписати: відкрити робочий простір на `material=memory`, перейти кнопкою `#workspace-locations`, зберегти опис, «← До твору» (`#locations-return`) → URL має ті самі `scene`/`material`; змінити тип запису — без конфлікту; рядок запису після злиття на сторінці показує ціль. Нові cases:
  - вхід і порожній стан: `/stories/${id}/locations` твору без локацій показує текст `locations.page_empty` і посилання на «Персонажі»; у «Пам’яті» є `.memory-locations-link`, що веде на сторінку з `scene`/`material`;
  - `beforeunload`: набрати опис, клік «← До твору» → `page.on('dialog')` отримує `beforeunload`, `dismiss()` лишає на сторінці з набраним текстом;
  - звірка: робочий простір на `material=memory` відкрито; через `request` змінити опис локації (API з `expected_revision`); `page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true})))`; дочекатися запиту `GET /api/stories/{id}`; змінити тип запису — без конфлікту;
  - mobile: шапка робочого простору й сторінка «Локації» без горизонтального прокручування (`scrollWidth <= clientWidth`).
  `card-invalidation.spec.mjs`: селектор пагорба — на сторінці «Локації».
  Run: `pnpm --dir frontend exec playwright test locations.spec.mjs card-invalidation.spec.mjs characters-page.spec.mjs workspace-layout.spec.mjs` → усе passed (desktop і mobile).
- [ ] **Step 2: Знімок.** `capture_screenshots.py` відкриває `/stories/{id}/locations` і знімає `#locations-page`; перезняти `locations-desktop.png` uk/en тим способом, який описано в самому скрипті; нейтральні приклади вже в ньому.
- [ ] **Step 3: SPEC і traceability.** MEMORY-LOCATIONS: абзац панелі — окрема сторінка `/stories/{id}/locations` (`templates/locations.html`), кнопка в шапці, посилання з «Пам’яті», `beforeunload`, без `refresh`; S07 «WHEN автор на сторінці «Локації» …», останній AND — після повернення до твору (кнопкою чи відновленням сторінки) зміна типу запису не конфлікт; S08, S11 — «на сторінці «Локації»»; новий `MEMORY-LOCATIONS-S12 — Сторінка «Локації»` (вхід із шапки й «Пам’яті», повернення до тієї самої сцени й матеріалу, порожній стан, перепитування при незбережених описах, звірка ревізії твору при поверненні на екран, mobile без горизонтального прокручування). MCP-BRIDGE: `scene-revisions` має `story_revision`; зміна ревізії твору теж перечитує сторінку; перевірка також на `pageshow` з `persisted`. traceability: S12 → `tests/web/test_locations_ui.py::test_locations_page_and_header_button`, `::test_panel_lives_on_its_page`, `tests/web/test_scene_revisions_api.py::test_scene_revisions_carry_the_story_revision`, `tests/web/test_scene_sync_ui.py::test_workspace_loads_the_sync_and_its_notice` + manual `docs/verification/manual.md#locations-panel` (Playwright, verify.py не запускає); у S07 замінити посилання на перейменований тест на `::test_both_languages_have_the_texts`. `manual.md#locations-panel`: нові cases і нова адреса.
- [ ] **Step 4: Довідка.** `docs/site/uk/memory.md` і `en`: «Картки видно на сторінці **Локації**: кнопка з міткою місця в шапці твору або посилання «Локації твору →» у вкладці **Пам’ять**»; підпис знімка «Сторінка «Локації» …»; згадки «в панелі «Локації»» → «на сторінці «Локації»». `python scripts/check_site.py --rehash memory`.
- [ ] **Step 5:** `python scripts/check_docs.py` → OK; повний pytest і `python scripts/verify.py` з `C:/tmp/lp1` → 0 failed, 0 errors.
- [ ] **Step 6: Commit** `docs(locations): SPEC S12, Playwright, довідка й знімок сторінки «Локації»`.
