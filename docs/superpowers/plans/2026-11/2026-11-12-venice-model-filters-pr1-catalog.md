# Каталог моделей із позначками й фільтрами (PR 1 із 3) — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Список моделей Venice й OpenRouter у формах ролей і підключень показує позначки приватності, Uncensored, JSON Schema, контекст і ціну з каталогу; фільтри; JSON Schema прив'язано до режиму відповіді. Правила виклику не змінюються.

**Architecture:** Сервер збагачує `ModelOption` полями каталогу й віддає всі онлайн-моделі Venice. Чиста логіка позначок/фільтрів/доступності живе в `static/model-picker.js` і тестується в Node; той самий модуль монтує компонент списку замість `datalist`. Перевірка Venice перед викликом (`validate_model`, вимога `uncensored=true`) у цьому PR не змінюється, тому модель Venice без Uncensored видно, але вибрати не можна.

**Tech Stack:** Python 3.12, FastAPI, pydantic; vanilla JS ES-модулі без збирання; Node-тести (`tests/web/js/*.mjs` через pytest-обгортку); Playwright (`tests/web/browser/*.spec.mjs`).

**Spec:** `docs/superpowers/specs/2026-11/2026-11-12-venice-model-filters-design.md` (затверджено 2026-11-12). Розділи: «Каталог і список (PR 1)», П1, П6, MODEL-005-S01/S02.

## Global Constraints

- Нових залежностей немає (ні Python, ні npm).
- Каталог Venice запитується як зараз: `GET /models` з `type=text`; моделі з `offline=true` не показуються.
- Позначки й ознаки — лише з полів каталогу; відсутнє поле дає «невідомо», а не вигадане значення.
- Позначка для моделей з `supportsE2EE`/`supportsTeeAttestation` — **«TEE»** (рішення власника 12.11.2026), не «E2EE».
- Порядок приватності: TEE > Private > Anonymous; `unknown` поза шкалою. Типовий фільтр — «Private і вище». Для провайдерів без рівня (OpenRouter, local) фільтр приватності неактивний із поясненням.
- JSON Schema: Venice — `capabilities.supportsResponseSchema is True`; OpenRouter — `'structured_outputs' in supported_parameters`; local — `None`.
- `providers/venice.py::validate_model` і `uncensored_models` у цьому PR не змінюються.
- Кожен новий рядок інтерфейсу має ключі в `i18n.json` для `uk` і `en`.
- Сторінки сайту змінюються парою `docs/site/uk/models.md` + `docs/site/en/models.md`, потім `python scripts/check_site.py --rehash models`.
- Коментарі в коді — англійською, документація — українською (OpenSpec-маркери англійською).

## Review Focus

1. Автор вводить ID вручну, а моделі немає в завантаженому каталозі (або каталог не завантажено): поле лишається редагованим, рядок вибраної моделі каже «немає в каталозі» без позначок, збереження не блокується. Тест — Task 2 (`selectable` для `null`), Task 3 (браузер).
2. Каталог не завантажився (немає ключа, мережа): повідомлення про помилку, як зараз; ручний ввід працює. Тест — Task 3.
3. Автор змінив провайдера чи Base URL після завантаження: старий список очищується і не підписує нову модель (нинішня поведінка `capture()`). Тест — Task 3.
4. Рядок каталогу без `pricing` чи з нетиповими ключами ціни: ціна «—», без винятку. Тест — Task 1.
5. Фільтри дають порожній результат: повідомлення «Жодна модель не відповідає фільтрам», а не порожня таблиця. Рядки вибираються з клавіатури (Enter/Space). Тест — Task 2 (порожній результат), Task 3 (клавіатура).

---

### Task 1: Поля каталогу в `ModelOption` і всі онлайн-моделі Venice

**Files:**
- Modify: `src/storygen/providers/models.py` (`ModelOption`)
- Modify: `src/storygen/providers/catalog.py` (`model_option`)
- Modify: `src/storygen/providers/venice.py` (додати `catalog_models`, переключити `model_options`)
- Test: `tests/providers/test_catalog_metadata.py`, `tests/providers/test_venice.py`

**Interfaces:**
- Produces: `ModelOption` з полями `id: str`, `name: str | None = None`, `context_tokens`, `max_output_tokens`, `tariff` (як зараз), `uncensored: bool | None`, `privacy: Literal['anonymized','private','unknown'] = 'unknown'`, `tee: bool = False`, `supports_schema: bool | None = None`. JSON-відповідь `POST /api/providers/discover` містить ці поля.
- Produces: `venice.catalog_models(client) -> list[tuple[str, dict]]` — усі моделі з `offline` не `True`.

- [ ] **Step 1: Write the failing tests** у `tests/providers/test_catalog_metadata.py`:

```python
def test_venice_catalog_fields_become_badges(monkeypatch):
    # anonymized uncensored, private schema, tee — all three are returned, offline is not
    rows=[venice_row('a',privacy='anonymized',uncensored=True),venice_row('p',privacy='private',schema=True),
          venice_row('t',privacy='private',e2ee=True,tee=True),venice_row('off',offline=True)]
    found={m.id:m for m in discover(rows,'venice')}
    assert set(found)=={'a','p','t'}
    assert (found['a'].privacy,found['a'].uncensored,found['a'].tee)==('anonymized',True,False)
    assert (found['p'].uncensored,found['p'].supports_schema)==(False,True)
    assert found['t'].tee is True and found['t'].privacy=='private'

def test_missing_fields_stay_unknown(monkeypatch):
    row=venice_row('x'); del row['model_spec']['privacy']; del row['model_spec']['pricing']
    m=discover([row],'venice')[0]
    assert m.privacy=='unknown' and m.tariff is None

def test_openrouter_schema_from_supported_parameters(monkeypatch):
    rows=[or_row('s',['response_format','structured_outputs']),or_row('j',['response_format']),or_row('n',None)]
    found={m.id:m for m in discover(rows,'openrouter')}
    assert (found['s'].supports_schema,found['j'].supports_schema,found['n'].supports_schema)==(True,False,None)
    assert all(m.privacy=='unknown' and m.uncensored is None and m.tee is False for m in found.values())
```

`venice_row`, `or_row`, `discover` — локальні хелпери файла поруч із наявним `row()`. `uncensored` для Venice: `True` лише коли поле дорівнює саме `True`, інакше `False`. Для local: `privacy='unknown'`, `supports_schema=None`, `uncensored=None`.

- [ ] **Step 2: Змінити очікування `test_venice_discovery_requires_true_boolean_not_name_or_description`** у `tests/providers/test_venice.py`: discovery тепер повертає всі онлайн-моделі; тест перевіряє, що `uncensored` дорівнює `True` лише для `qwen-test`, а для `censored`, `uncensored-in-name` і `string-true` — `False`; `offline` відсутня; запит один, `GET`, `type=text`. Перейменувати на `test_venice_discovery_marks_uncensored_only_for_true_boolean`.

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/providers/test_catalog_metadata.py tests/providers/test_venice.py -q`
Expected: FAIL (`ModelOption` не має `privacy`; discovery повертає лише uncensored).

- [ ] **Step 4: Implement.** `ModelOption` — нові поля. `venice.catalog_models(client)` — як `uncensored_models` без умови `uncensored`. `venice.model_options` використовує `catalog_models`. `catalog.model_option(provider,row,repo)` заповнює нові поля за правилами Global Constraints; `name` — `model_spec.name` для Venice, `row['name']` для OpenRouter. Помилка розбору тарифу лишає `tariff=None` (як зараз).

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/providers -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/storygen/providers tests/providers
git commit -m "feat(providers): catalog privacy, TEE, uncensored and schema fields"
```

### Task 2: Чиста логіка позначок, фільтрів і доступності

**Files:**
- Create: `src/storygen/web/static/model-picker.js` (у цьому завданні — лише експортовані чисті функції)
- Modify: `src/storygen/web/static/i18n.json` (ключі `models.badge_*`, `models.filter_*`, `models.blocked_*` для `uk` і `en`)
- Test: `tests/web/js/model_picker.mjs`, `tests/web/test_model_picker.py` (обгортка за зразком `tests/web/test_model_catalog.py`)

**Interfaces:**
- Consumes: JSON `ModelOption` з Task 1.
- Produces (усі експортовані з `model-picker.js`):
  - `PRIVACY_RANK = {unknown:-1, anonymized:0, private:1, tee:2}`; `privacyLevel(model) -> 'tee'|'private'|'anonymized'|'unknown'` (`tee` якщо `model.tee`).
  - `modelBadges(model) -> Array<{kind:'uncensored'|'tee'|'private'|'anonymized'|'unknown'|'schema', key:string}>` — порядок: uncensored, рівень приватності, schema.
  - `providerReportsPrivacy(provider) -> boolean` (`true` лише для `venice`).
  - `filterModels(models, {query, uncensoredOnly, minPrivacy, schemaOnly}, provider) -> models[]` — `minPrivacy ∈ {'any','private','tee'}` ігнорується, коли `providerReportsPrivacy(provider)` хибне; пошук — підрядок без регістру в `id` або `name`.
  - `schemaLocked(responseMode) -> boolean` (`responseMode==='json_schema'`).
  - `selectable(model, {provider, responseMode}) -> {ok:boolean, reason:null|'venice_uncensored_pending'|'schema_required'}` — `model===null` → `{ok:true}`; Venice і `uncensored!==true` → `venice_uncensored_pending`; `schemaLocked` і `supports_schema!==true` → `schema_required`.
  - `formatPrice(usd) -> string` (`'—'` для `null`/`undefined`).

- [ ] **Step 1: Write the failing test** `tests/web/js/model_picker.mjs`:

```js
const tee={id:'t',tee:true,privacy:'private',uncensored:false,supports_schema:false};
const pri={id:'p',name:'Private One',privacy:'private',uncensored:true,supports_schema:true};
const anon={id:'a',privacy:'anonymized',uncensored:true,supports_schema:true};
const unk={id:'u',privacy:'unknown',uncensored:null,supports_schema:null};
assert.deepEqual(modelBadges(pri).map(b=>b.kind),['uncensored','private','schema']);
assert.deepEqual(modelBadges(tee).map(b=>b.kind),['tee']);
assert.deepEqual(filterModels([tee,pri,anon],{query:'',uncensoredOnly:false,minPrivacy:'private',schemaOnly:false},'venice').map(m=>m.id),['t','p']);
assert.deepEqual(filterModels([tee,pri,anon],{query:'',uncensoredOnly:false,minPrivacy:'tee',schemaOnly:false},'venice').map(m=>m.id),['t']);
assert.deepEqual(filterModels([unk],{query:'',uncensoredOnly:false,minPrivacy:'private',schemaOnly:false},'openrouter').map(m=>m.id),['u']);
assert.deepEqual(filterModels([pri,anon],{query:'private o',uncensoredOnly:false,minPrivacy:'any',schemaOnly:false},'venice').map(m=>m.id),['p']);
assert.deepEqual(filterModels([tee],{query:'',uncensoredOnly:true,minPrivacy:'any',schemaOnly:false},'venice'),[]);
assert.deepEqual(selectable(tee,{provider:'venice',responseMode:'prompt_json'}),{ok:false,reason:'venice_uncensored_pending'});
assert.deepEqual(selectable(anon,{provider:'venice',responseMode:'json_schema'}),{ok:true,reason:null});
assert.deepEqual(selectable({...pri,supports_schema:false},{provider:'venice',responseMode:'json_schema'}),{ok:false,reason:'schema_required'});
assert.deepEqual(selectable(unk,{provider:'openrouter',responseMode:'json_schema'}),{ok:false,reason:'schema_required'});
assert.deepEqual(selectable(null,{provider:'venice',responseMode:'json_schema'}),{ok:true,reason:null});
assert.equal(formatPrice(undefined),'—');
for(const b of modelBadges(pri))assert.notEqual(t(b.key),b.key); // every badge key exists in i18n (uk)
setLocale('en'); for(const b of modelBadges(tee))assert.notEqual(t(b.key),b.key);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/web/test_model_picker.py -q`
Expected: FAIL (модуля немає).

- [ ] **Step 3: Implement the functions in `model-picker.js` and add i18n keys.** Тексти (uk / en): `models.badge_uncensored` «Uncensored» / «Uncensored»; `models.badge_tee` «TEE» / «TEE»; `models.badge_private` «Private» / «Private»; `models.badge_anonymized` «Anonymous» / «Anonymous»; `models.badge_unknown` «Приватність невідома» / «Privacy unknown»; `models.badge_schema` «JSON Schema» / «JSON Schema»; `models.blocked_venice_uncensored_pending` «Моделі Venice без позначки Uncensored стануть доступні після оновлення правил виклику.» / «Venice models without the Uncensored mark become available after the call rules update.»; `models.blocked_schema_required` «Модель не підтримує JSON Schema. Виберіть іншу модель або режим „JSON за промптом“.» / «The model does not support JSON Schema. Choose another model or the “JSON via prompt” mode.»; `models.privacy_not_reported` «OpenRouter не повідомляє рівень приватності.» / «OpenRouter does not report a privacy level.»; `models.no_match` «Жодна модель не відповідає фільтрам.» / «No model matches the filters.».

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/web/test_model_picker.py tests/web/test_model_catalog.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/storygen/web/static/model-picker.js src/storygen/web/static/i18n.json tests/web/js/model_picker.mjs tests/web/test_model_picker.py
git commit -m "feat(web): model picker badges, filters and selectability rules"
```

### Task 3: Компонент списку замість `datalist` у формах ролі й підключення

**Files:**
- Modify: `src/storygen/web/static/model-picker.js` (додати `mountModelPicker`)
- Modify: `src/storygen/web/static/settings.js:29,75-78` (форма ролі)
- Modify: `src/storygen/web/static/settings-connection.js:21-35` (спільний віджет підключення)
- Modify: `src/storygen/web/static/app.css` (стилі списку, позначок; лише наявні токени кольорів)
- Modify: `src/storygen/web/static/i18n.json` (заголовки колонок і фільтрів, `models.not_in_catalog`)
- Keep: `src/storygen/web/static/model-catalog.js::modelMetadataLabel` (використовується в рядку вибраної моделі)
- Test: `tests/web/browser/model-picker.spec.mjs` (за зразком `build-edition.spec.mjs`; відповідь `/api/providers/discover` підміняється через `page.route` синтетичними моделями)

**Interfaces:**
- Consumes: функції Task 2; `mountModelCatalog` лишається для сумісності або замінюється — вирішує виконавець, але `modelMetadataLabel` і поведінка `capture()`/очищення при зміні провайдера чи Base URL зберігаються.
- Produces: `mountModelPicker({host, modelInput, providerInput, baseUrlInput, responseModeInput}) -> {capture():string, setModels(models, captured):boolean, clear():void, validate():null|string}`; `validate()` повертає ключ `models.blocked_*` для поточного вибору або `null`. Форми викликають `validate()` перед збереженням і показують текст замість відправлення.

- [ ] **Step 1: Write the failing browser test** `tests/web/browser/model-picker.spec.mjs` з тестами:
  - `catalog shows badges and the default privacy filter hides anonymous models` — 4 синтетичні моделі Venice (TEE, Private+Uncensored+schema, Anonymous+Uncensored, Private без schema); після «Отримати список моделей» видно 3 рядки, рядок Anonymous з'являється після вибору «будь-яка»; у рядку Private видно «Uncensored», «Private», «JSON Schema» і ціну.
  - `json schema mode locks the filter and blocks a non-schema model` — режим «JSON Schema»: галочка JSON Schema `checked` і `disabled`, рядок без schema має `aria-disabled="true"`; перемикання на «JSON за промптом» знімає блокування.
  - `venice model without uncensored is visible but cannot be chosen yet` — клік по рядку TEE не змінює `model`, видно текст `models.blocked_venice_uncensored_pending`.
  - `manual id outside the catalog is kept and marked` — ввід `custom-model` вручну: рядок вибраної моделі «немає в каталозі», збереження форми проходить.
  - `changing provider clears the loaded list` — після завантаження змінити провайдера на OpenRouter: таблиця порожня, фільтр приватності `disabled` з поясненням `models.privacy_not_reported`.
  - `rows are selectable from the keyboard` — фокус на рядку + Enter вибирає модель.

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --dir frontend exec playwright test model-picker.spec.mjs`
Expected: FAIL.

- [ ] **Step 3: Implement `mountModelPicker` and wire it into both forms.** Розмітка — як затверджений прототип: рядок вибраної моделі (ID, позначки, контекст, ціна, кнопка «Змінити»), панель фільтрів (пошук, «Лише Uncensored», «Приватність» з варіантами «будь-яка / Private і вище / лише TEE», «JSON Schema»), таблиця з колонками «Модель», «Позначки», «Контекст», «Вхід, $/1M», «Вихід, $/1M» і сортуванням кліком по заголовку, підвал «Показано N з M». Рядки — `role="button"`, `tabindex="0"`. Зміна `responseModeInput` перебудовує список і виклик `validate()`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pnpm --dir frontend exec playwright test model-picker.spec.mjs && python -m pytest tests/web -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/storygen/web/static tests/web/browser/model-picker.spec.mjs
git commit -m "feat(web): model picker replaces the datalist in role and connection forms"
```

### Task 4: Серверна перевірка JSON Schema під час збереження

**Files:**
- Modify: `src/storygen/web/routes_settings.py` (`PUT /api/stories/{story_id}/settings`, `PUT …/settings/shared-provider`)
- Create: `src/storygen/providers/schema_support.py`
- Test: `tests/web/test_model_schema_save.py`

**Interfaces:**
- Consumes: `discover_models(settings, http_client=None, *, repo=None)`; `ModelOption.supports_schema` з Task 1.
- Produces: `schema_mismatch(settings: ProviderSettings, http_client=None) -> str | None` — повертає авторський текст помилки, якщо `settings.response_mode=='json_schema'`, провайдер `venice` або `openrouter`, модель знайдена в каталозі і `supports_schema is False`; `None` у всіх інших випадках, зокрема коли каталог недоступний, модель не знайдена або `supports_schema is None`.

- [ ] **Step 1: Write the failing tests:** `test_save_rejects_known_non_schema_model_in_schema_mode` (Venice, каталог через `httpx.MockTransport` з `supportsResponseSchema:false` → 422 з текстом «Модель не підтримує JSON Schema»); `test_save_allows_when_catalog_unavailable` (транспорт повертає 500 → збереження проходить); `test_save_allows_prompt_json_mode` (той самий каталог, `prompt_json` → проходить). HTTP-клієнт для перевірки береться з того самого механізму, яким тести вже підміняють провайдера (див. `tests/web` фікстури для `/api/providers/discover`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/web/test_model_schema_save.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement `schema_mismatch` and call it for each role/provider being saved before the write; mismatch → `ValueError` з текстом (маршрути вже перетворюють `ValueError` на 422).**

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/web -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/storygen/providers/schema_support.py src/storygen/web/routes_settings.py tests/web/test_model_schema_save.py
git commit -m "feat(settings): reject a known non-schema model in JSON Schema mode on save"
```

### Task 5: Специфікація, traceability, сайт

**Files:**
- Modify: `SPEC.MD` — новий `Requirement: MODEL-005 — Каталог моделей у налаштуваннях` зі Scenario MODEL-005-S01 і MODEL-005-S02 (текст — зі специфікації зміни); у MODEL-003 додати речення: «Список моделей SHALL показувати й моделі без `uncensored=true`; до оновлення правил виклику їх вибір для Venice заблоковано»; технічний опис провайдерів — нові поля `ModelOption`.
- Modify: `docs/verification/traceability.json` — MODEL-005-S01 → `tests/providers/test_catalog_metadata.py`, `tests/web/test_model_picker.py`; MODEL-005-S02 → `tests/web/browser/model-picker.spec.mjs`, `tests/web/test_model_schema_save.py`. Тестам додати маркер `@pytest.mark.req('MODEL-005')` за правилом проєкту.
- Modify: `docs/site/uk/models.md`, `docs/site/en/models.md` — розділ про список моделей, позначки, фільтри й JSON Schema; знімок лише з нейтральними синтетичними даними (без приватних матеріалів).
- Modify: `docs/superpowers/plans/2026-10-20-remediation-progress.md` — запис про PR 1.

- [ ] **Step 1: Edit the documents above.**
- [ ] **Step 2: Run** `python scripts/check_site.py --rehash models` **і** `python scripts/check_docs.py`. Expected: exit 0.
- [ ] **Step 3: Run the gate** `python scripts/check_docs.py && python -m pytest -q`. Expected: PASS.
- [ ] **Step 4: Run** `python scripts/verify.py` **і записати фактичний результат у `docs/STATUS.md`.**
- [ ] **Step 5: Commit**

```bash
git add SPEC.MD docs tests
git commit -m "docs: MODEL-005 model catalog contract, traceability and site pages"
```

---

## Далі

Після злиття PR 1 і наскрізного рев'ю — окремі плани для PR 2 (згода й блокування після відмови, заміна MODEL-003) і PR 3 (модель письменника для сцен 0–1), за правилом «спершу ядро, потім обв'язка».
