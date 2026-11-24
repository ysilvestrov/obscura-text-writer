# Видимий прогрес запусків — harness: панель «Узгодженість сцени», план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** панель «Узгодженість сцени» замінює `#link-attention` і `#audit-scene`: три рядки зв'язків зі станом і діями-посиланнями, одна головна дія («Перевірити Ревізором» з ціною або «Продовжити валідацію» на сцені зупинки); «Продовжити» валідації книги йде з рядка запуску в панель (Р1), «Перейти до сцени N» фокусує панель (Р7); відкладені дрібниці ядра; SPEC, traceability, сайт uk/en, знімки й `manual.md`.

**Architecture:** чисте правило `sceneConsistency(...)` у `static/link-actions.js` будується поверх наявного `pendingLinks` (дії кожного зв'язку) і дає три рядки, видимість і головну дію. `static/link-decision.js` рендерить його в новій секції `#scene-consistency`, сам читає перегляд сцени (`POST …/audit/preview {scope:'scene'}`) з ключем і захистом від запізнілої відповіді. Продовження з панелі — нова команда робочого простору `resume-run` у `runs.js` поверх приватного `resumeRun`; рядок ховає «Продовжити» книги за наявним `bookResumeInRow`. Повний запуск книги панель бере з останнього `workspace-run-state` (список `/runs` не має `checkpoint`) через чисте `panelBookRun`.

**Tech Stack:** vanilla JS (ES modules), FastAPI/SQLite (лише дві точки подій), pytest, node-скрипти `.mjs` під pytest, Playwright.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-24-validation-progress-ux-design.md`, §4 і решта §3 (затверджено 24.11.2026). Ядро — `docs/superpowers/plans/2026-11/2026-11-24-validation-progress-core.md` (рішення Р1, Р2, Р7) і журнал `.superpowers/sdd/2026-11-24-validation-progress-core/progress.md`. Макет панелі (варіант 1) — `C:\Projects\text-generator\.superpowers\brainstorm\1254-1795474703\content\validation-ui.html` (лише в основній теці, не в worktree).

**Межі (pr-slicing: harness).** Ядро зроблене й пройшло end-to-end рев'ю (коміти `325e69c4..7065b614`). Цей план добудовує решту на тій самій гілці `claude/validation-progress-ux`; спека передбачає один PR (M), тож PR на `main` відкривається після задачі 5. Рефакторингу, що вимагав би окремого PR, немає: `pendingLinks` лишається без змін, нові підписи дає `sceneConsistency`.

## Global Constraints

- Тексти — ключі `src/storygen/web/static/i18n.json`, `uk` і `en`, плейсхолдери `{p0}`, `{p1}`. Повідомлення сервера показуються через `diagnostic()`.
- «`#workspace-scene-status` (стан сцени, UI-FEEDBACK-S03) лишається в рядку стану без змін.»
- Рядки панелі «завжди три, у порядку завдання → проза → пам'ять, кожен із `state: ok|pending|discrepancy|unavailable|missing`». Значки: `✓` ok, `○` pending, `!` discrepancy, `—` unavailable; missing — без значка, стан «ще немає».
- Затвердження — той самий `POST /api/scenes/{id}/links/{link}/decision {action:'approve', fingerprint}`; `unavailable` ніколи не пропонує затвердження (сервер відмовляє 409).
- Платне — лише після наявного перегляду й `confirmDialog`: «Перевірити Ревізором» викликає наявний `invokeWorkspaceCommand('run', {mode:'audit', audit_scope:'scene'})`, «Продовжити валідацію» — наявний `resumeRun` з повторною згодою.
- Кожен виклик `focus`, `scrollIntoView`, `matchMedia`, `document.activeElement`, `matches` у `runs.js` — з `?.`: Node-мок `tests/web/js/runs_follow.mjs` їх не має.
- Мусять лишатися зеленими без зміни очікувань: `tests/web/test_resumed_events.py`, `tests/web/test_run_status_collapse_ui.py` (буквальні рядки в `runs.js`), `tests/web/test_run_progress_ui.py`, `tests/generation/test_run_progress.py`, `tests/web/test_runs.py`.
- `@pytest.mark.req` на новому тесті — лише якщо тест названо в рядку `traceability.json` тієї самої вимоги.
- Python-тести: `PYTHONUTF8=1 PYTHONPATH=src /c/Projects/text-generator/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=C:/tmp/vpux/<name> <tests>` — далі «PYTEST <name> <tests>».
- Playwright: `cd frontend && PYTHONPATH="$(cd .. && pwd -W)/src" PYTHONUTF8=1 ./node_modules/.bin/playwright test ../tests/web/browser/<spec> --grep-invert screenshots --reporter=line` — далі «PW <spec>».
- Знімки сайту — лише з нейтрального seed `scripts/capture_screenshots.py`, без даних автора.

## Review Focus

1. **Рядок забрав інший запуск, а сцена зупинки чекає.** Автор на сцені зупинки натискає «Створити нову пам'ять» (дія рядка пам'яті): рядок запуску переходить на запуск пам'яті, `state.workspaceRun` — уже не книга, а список `/runs` не має `checkpoint`. Очікування: панель і далі показує «Продовжити валідацію» за кешованим повним запуском книги, доки список каже, що цей запуск найновіша валідація книги в тому самому стані; клік, поки інший запуск активний, неактивний з причиною `book_validation.other_run_active`. Тест — задача 3 (`panelBookRun` у `book_validation.mjs`).
2. **Запізнілий перегляд іншої сцени.** Перегляд сцени A приходить після переходу на сцену B і показав би «N викл.» сцени A. Очікування: відповідь застосовується лише за поточним ключем. Тест — задача 2 (Playwright з затриманим `audit/preview`).
3. **Ціна не оновилася після рішення автора.** Після «Я перевірив сам» кількість викликів має зменшитися (2 → 1). Очікування: ключ перегляду містить статуси й відбитки зв'язків, тож рішення перечитує перегляд. Тест — задача 2.
4. **Фокус на перемальовуванні панелі.** `render()` робить `replaceChildren()` на кожну `story-refreshed`; фокус із кнопки панелі падав би на `body`. Очікування: фокус на головній кнопці переживає прихід перегляду; після кліку дії, чия кнопка зникла, фокус на `#scene-consistency`. Тест — задача 2.
5. **Неповна сцена й недоступні зв'язки.** Сцена лише із завданням, сцена без жодного зв'язку, недоступність Ревізора (переповнення) і структурна недоступність (немає пам'яті попередньої сцени). Очікування: без того, що можна вирішити, панелі немає (а не хибне «Сцена узгоджена ✓»); «Продовжити валідацію» активна для `unavailable` Ревізора, а для розбіжності — лише після зміни стану зв'язку. Тест — задача 1.

## Рішення, ухвалені планом (спека мовчить або суперечить коду)

- **Г1. «Переповнення» — не меню.** У §4 «переповнення — «Відкрити налаштування Ревізора»» означає `unavailable` Ревізора через ліміт входу (`OVERFLOW` у `link-actions.js`): дія-посилання в рядку, як зараз. Меню переповнення панель не має.
- **Г2. Без чого вирішувати — без панелі.** Спека: «усі три `missing` — панелі немає». План розширює правило: сцена без жодного рядка в `pending|discrepancy|unavailable` і з `validity ≠ 'valid'` (наприклад, лише завдання, валідне за побудовою) панелі теж не має — інакше вона показала б порожню панель із неактивною кнопкою, а «Сцена узгоджена ✓» була б хибною (знахідка 6 рев'ю спеки).
- **Г3. Рядок із пам'яттю попередньої сцени.** `pendingLinks` зводить З1/З2 `no_previous_memory` в один елемент `previous`. Його текст і дію «Створити пам'ять» несе рядок завдання, якщо З1 недоступний із цієї причини, інакше рядок прози; другий такий рядок має стан `consistency.state_needs_previous` без дій.
- **Г4. Підписи затвердження за станом.** З1/З2 `unchecked` → «Я перевірив сам», `discrepancy` → «Розбіжності немає»; З3 лишає «Залишити попередню пам'ять» / «Створити нову пам'ять». `pendingLinks` і його очікування в `link_decision.mjs` не змінюються (старий рендер працює до задачі 2, тож коміт задачі 1 лишає Playwright зеленим); підписи переписує `sceneConsistency` для дій `approve` завдання й прози.
- **Г5. Звідки панель бере запуск книги.** З `workspace-run-state` (повний запуск із `checkpoint`); якщо рядок перейшов на інший запуск або `workspace-run-pending` дав короткий запуск без `checkpoint` — кешований, за `panelBookRun` (Review Focus 1). Після перезавантаження, коли рядок стежить за пізнішим запуском, кешу немає: «Продовжити валідацію» з'являється після «Валідацію зупинено: показати» в меню. Це відоме обмеження.
- **Г6. Готовність «Продовжити валідацію».** `needs_review` з фазою `awaiting_author` ставить гілка `audit_run.py:215` з `outcome = state.status` (`discrepancy` або `unavailable` Ревізора за `_measured_again`); інші checkpoint-и (`failed`, `stale`, `cancelled`) ставлять інші стани запуску. Правило спеки дослівне: активна, якщо `links[checkpoint.link]?.status !== checkpoint.outcome` або `checkpoint.outcome === 'unavailable'`.
- **Г7. Коли читається перегляд.** Лише для `view === 'full'` без зупинки книги на цій сцені, за ключем `sceneId|brief:status:fingerprint|prose:…|memory:…`. `story-refreshed` після кожного етапу не перечитує перегляду, якщо зв'язки сцени не змінилися.
- **Г8. Фокус після повільного GET.** `revealRun` не забирає фокус з поля введення: якщо `document.activeElement` збігається з `textarea, input, select, [contenteditable]:not([contenteditable="false"])`, рядок розгортається й прокручується, а фокус лишається. Інакше — як у ядрі.
- **Г9. Дрібниці журналу ядра.** Беремо: крадіжку фокуса після повільного GET (Г8), втрату фокуса заголовка, коли наступне малювання не має блоку прогресу (фокус іде на `.run-summary`), `usage` у `stage_finished` пам'яті й конвеєра, Playwright-тест «Валідація триває: показати», `planned` без перевірки скінченності (`Number.isFinite` у `countsOf`). Закрито раніше: «показати» забирає рядок (I2 ядра). `docs/images/workspace-menu-*.png` (Playwright-тест `screenshots`) сайт не використовує — не перезнімаємо. Тексти сервера `stale_material_message` («затвердьте завдання / відповідність») не змінюємо: вони описують дію, а не назву кнопки. Відкладено без шкоди для автора: «крихкий тест завантаження сторінки», `cost_bound_usd` як рядок перегляду, відсутні тести enqueue для інших режимів, мигання лічильників після resume/перезавантаження до наступного GET (пишемо у відомі обмеження R20-WORKSPACE, якщо там немає), O(n) читання подій (уже в SPEC).
- **Г10. `pipeline.generate_scene` і `memory.service.rebuild_memory` worker не викликає** (у `src` немає викликачів, лише тести). Виправлення — дворядковий паритет із тестом на рівні функції; RED через worker не шукати.

---

### Task 1: Чисті правила панелі `sceneConsistency`

**Files:**
- Modify: `src/storygen/web/static/link-actions.js`
- Modify: `src/storygen/web/static/i18n.json`
- Test: `tests/web/js/link_decision.mjs`, `tests/web/test_link_decision_ui.py`

**Interfaces:**
- Consumes: `pendingLinks(materialStatus, sceneId, scenes)` (наявне), `dollars` з `run-summary.js`.
- Produces:
  - `sceneConsistency(materialStatus, sceneId, scenes=[], run=null, preview=null, blocked='') -> {view, pendingCount, total, rows, primary, resume}`:
    - `view: 'none'|'valid'|'full'` — `full`, якщо `run` — валідація книги (`request.mode==='audit' && audit_scope==='story'`) у `needs_review` з `checkpoint.scene_id === sceneId`; інакше `valid` за `materialStatus[sceneId].validity === 'valid'`; інакше `none` при `pendingCount === 0` (Г2); інакше `full`.
    - `rows`: рівно три `{link, title, state, icon, status:{key, params}, actions, confidence?, summary?, discrepancies?, reason?}`; `title` — `consistency.row_<link>`; `reason` — сирий текст Ревізора для `link.audit_unavailable`.
    - `pendingCount` — рядки зі станом `pending|discrepancy|unavailable`; `total` — рядки не `missing`.
    - `primary`: `{action:'audit', label:'consistency.audit', detail:{key,params}|null, disabled, reason}` або `{action:'resume', runId, label:'consistency.resume', disabled, reason}`; `reason: {key, params} | {text} | null`.
    - `resume: boolean` — `primary.action === 'resume'`.
  - Правила стану: статус зв'язку `valid→ok`, `unchecked→pending`, `discrepancy→discrepancy`, `unavailable→unavailable`, `missing` чи відсутній → `missing`. `status`: ok — `consistency.state_ok` / `_ok_auditor` / `_ok_author` за `source`; pending — `consistency.state_pending` (для пам'яті — `link.memory_unchecked`); discrepancy — `consistency.state_discrepancy {p0: confidence ?? '—'}`; unavailable — текст і параметри елемента `pendingLinks` (Г3); missing — `consistency.state_missing`.
  - Головна `audit`, порядок причин: `blocked` → `{text: blocked}`; `preview == null` → `disabled:true, reason:null`, `detail:null`; `!preview.ready` → `{text: preview.reason}`; `preview.calls === 0` → `{key:'consistency.nothing_to_audit'}`. `detail`: `consistency.audit_cost {p0: calls, p1: dollars(Number(total_usd))}`, без `cost.total_usd` — `consistency.audit_calls {p0: calls}`.
  - Головна `resume`: готовність за Г6; не готова → `{key:'consistency.resolve_first'}`; `blocked` має перевагу.
- Нові ключі (uk / en):
  - `consistency.title` «Узгодженість сцени» / «Scene consistency»
  - `consistency.pending_count` «{p0} з {p1} не перевірено» / «{p0} of {p1} not checked»
  - `consistency.valid` «Сцена узгоджена ✓» / «Scene is consistent ✓»
  - `consistency.row_brief` «Завдання відповідає плану й пам’яті попередньої сцени» / «The brief matches the plan and the previous scene’s memory»
  - `consistency.row_prose` «Проза відповідає завданню» / «The prose matches the brief»
  - `consistency.row_memory` «Пам’ять відповідає прозі» / «The memory matches the prose»
  - `consistency.state_ok` «узгоджено» / «consistent»; `consistency.state_ok_auditor` «узгоджено · Ревізор» / «consistent · Auditor»; `consistency.state_ok_author` «узгоджено · ви» / «consistent · you»
  - `consistency.state_pending` «не перевірено» / «not checked»; `consistency.state_missing` «ще немає» / «not yet»
  - `consistency.state_needs_previous` «чекає на пам’ять попередньої сцени» / «waiting for the previous scene’s memory»
  - `consistency.state_discrepancy` «Ревізор: можлива розбіжність (упевненість у відповідності — {p0}%)» / «Auditor: possible discrepancy (confidence in the match: {p0}%)»
  - `consistency.discrepancy_hint` «Пояснення моделі бувають неточні: перечитайте сцену.» / «The model’s explanations can be imprecise: reread the scene.»
  - `consistency.approve_self` «Я перевірив сам» / «I checked it myself»; `consistency.no_discrepancy` «Розбіжності немає» / «No discrepancy»
  - `consistency.audit` «Перевірити Ревізором» / «Check with the Auditor»; `consistency.audit_cost` «{p0} викл., до {p1}» / «{p0} calls, up to {p1}»; `consistency.audit_calls` «{p0} викл.» / «{p0} calls»
  - `consistency.nothing_to_audit` «Ревізору нема що перевіряти: вирішіть зв’язки вручну» / «Nothing for the Auditor to check: resolve the links yourself»
  - `consistency.resume` «Продовжити валідацію» / «Continue validation»; `consistency.resolve_first` «Спершу вирішіть зв’язок» / «Resolve the link first»
  - Ключ `link.audit_scene` прибирає задача 2 (після неї його ніхто не читає; перевірити `grep -rn audit_scene src/storygen/web`). `link.approve_*` і `link.*_discrepancy` лишаються: їх і далі повертає `pendingLinks`.

- [ ] **Step 1: Написати тести, що падають** — у `tests/web/js/link_decision.mjs` імпортувати й `sceneConsistency`; наявні очікування `pendingLinks` лишаються. Додати:

```js
const disc={...link('discrepancy',null,'fp'),source:'auditor',confidence:72,summary:'Можлива розбіжність',discrepancies:[{text:'Інший порт',quote:'Герой іде до порту'}]};
const pv=(calls,total='0.0123',ready=true,reason=null)=>({ready,reason,calls,cost:{total_usd:total}});
let c=sceneConsistency(view({brief:link('unchecked',null,'fb'),prose:disc,memory:{...valid,source:'auditor'}}),'s2',scenes,null,pv(1));
assert.deepEqual(c.rows.map(r=>[r.link,r.state,r.icon]),[['brief','pending','○'],['prose','discrepancy','!'],['memory','ok','✓']]);
assert.deepEqual([c.view,c.pendingCount,c.total,c.resume],['full',2,3,false]);
assert.deepEqual(c.rows[0].actions,[{type:'approve',link:'brief',fingerprint:'fb',label:'consistency.approve_self'}]);
assert.deepEqual(c.rows[1].actions,[{type:'approve',link:'prose',fingerprint:'fp',label:'consistency.no_discrepancy'}]);
assert.deepEqual([c.rows[1].status,c.rows[1].summary,c.rows[1].discrepancies],[{key:'consistency.state_discrepancy',params:{p0:72}},'Можлива розбіжність',disc.discrepancies]);
assert.deepEqual(c.rows[2].status,{key:'consistency.state_ok_auditor',params:{}});
assert.deepEqual(c.primary,{action:'audit',label:'consistency.audit',detail:{key:'consistency.audit_cost',params:{p0:1,p1:'$0.01'}},disabled:false,reason:null});
// preview: loading, not ready, nothing to call, no price, blocked
assert.deepEqual([sceneConsistency(view({brief:link('unchecked')}),'s2',scenes).primary.disabled,sceneConsistency(view({brief:link('unchecked')}),'s2',scenes).primary.reason],[true,null]);
assert.deepEqual(sceneConsistency(view({brief:link('unchecked')}),'s2',scenes,null,pv(0,null,false,'Роль не налаштовано: Ревізор')).primary.reason,{text:'Роль не налаштовано: Ревізор'});
assert.deepEqual(sceneConsistency(view({prose:disc}),'s2',scenes,null,pv(0,'0.0000')).primary.reason,{key:'consistency.nothing_to_audit',params:{}});  // every {key} reason carries params, {} when none
assert.deepEqual(sceneConsistency(view({brief:link('unchecked')}),'s2',scenes,null,pv(2,null)).primary.detail,{key:'consistency.audit_calls',params:{p0:2}});
assert.deepEqual(sceneConsistency(view({brief:link('unchecked')}),'s2',scenes,null,pv(1),'Збережіть зміни').primary,{action:'audit',label:'consistency.audit',detail:{key:'consistency.audit_cost',params:{p0:1,p1:'$0.01'}},disabled:true,reason:{text:'Збережіть зміни'}});
// visibility (Г2): valid line, nothing at all, brief-only scene with nothing to decide
assert.equal(sceneConsistency(view({}),'s2',scenes,null,pv(0)).view,'valid');
assert.equal(sceneConsistency({s2:{links:{brief:link('missing'),prose:link('missing'),memory:link('missing')},validity:'incomplete'}},'s2',scenes).view,'none');
assert.equal(sceneConsistency({s2:{links:{brief:valid,prose:link('missing'),memory:link('missing')},validity:'incomplete'}},'s2',scenes).view,'none');
const briefOnly=sceneConsistency({s2:{links:{brief:link('unchecked'),prose:link('missing'),memory:link('missing')},validity:'incomplete'}},'s2',scenes,null,pv(1));
assert.deepEqual([briefOnly.view,briefOnly.total,briefOnly.rows[1].status],['full',1,{key:'consistency.state_missing',params:{}}]);
// Г3: the previous scene's memory sits on the brief row once
const prev={s2:{links:{brief:link('unavailable','no_previous_memory'),prose:link('unavailable','no_previous_memory'),memory:valid},previous_scene_id:'s1',validity:'unchecked'}};
c=sceneConsistency(prev,'s2',scenes,null,pv(0));
assert.deepEqual(c.rows[0].status,{key:'link.no_previous_memory',params:{p0:'Ранок'}});
assert.deepEqual(c.rows[0].actions,[memory('s1','link.create_memory')]);
assert.deepEqual([c.rows[1].state,c.rows[1].status,c.rows[1].actions],['unavailable',{key:'consistency.state_needs_previous',params:{}},[]]);
// auditor overflow keeps the settings link
const over={status:'unavailable',source:'auditor',reason:'Вхід перевірки перевищує ліміт Ревізора: 9 > 8',fingerprint:'fo'};
c=sceneConsistency(view({prose:over},{validity:'unchecked'}),'s2',scenes,null,pv(0));
assert.deepEqual([c.rows[1].icon,c.rows[1].reason,c.rows[1].actions],['—',over.reason,[{type:'settings',label:'link.open_auditor_settings'}]]);
// resume on the stop scene (Г6)
const book=(cp,state='needs_review')=>({id:'r1',state,request:{mode:'audit',audit_scope:'story'},checkpoint:{phase:'awaiting_author',...cp}});
c=sceneConsistency(view({brief:{...disc,fingerprint:'fb'}},{validity:'discrepancy'}),'s2',scenes,book({scene_id:'s2',link:'brief',outcome:'discrepancy'}),pv(1));
assert.deepEqual([c.view,c.resume,c.primary],['full',true,{action:'resume',runId:'r1',label:'consistency.resume',disabled:true,reason:{key:'consistency.resolve_first',params:{}}}]);
assert.equal(sceneConsistency(view({},{validity:'valid'}),'s2',scenes,book({scene_id:'s2',link:'brief',outcome:'discrepancy'})).primary.disabled,false);  // decided: shown in full though valid
assert.equal(sceneConsistency(view({prose:over},{validity:'unchecked'}),'s2',scenes,book({scene_id:'s2',link:'prose',outcome:'unavailable'})).primary.disabled,false);
assert.equal(sceneConsistency(view({brief:link('unchecked')}),'s2',scenes,book({scene_id:'s1',link:'brief',outcome:'discrepancy'}),pv(1)).primary.action,'audit');
assert.equal(sceneConsistency(view({brief:link('unchecked')}),'s2',scenes,book({scene_id:'s2',link:'brief',outcome:'discrepancy'},'completed'),pv(1)).primary.action,'audit');
```

Хелпер `view(links, extra)` у файлі доповнити полем `validity` (за замовчуванням `'valid'`, коли всі три валідні, інакше `'unchecked'`), щоб не залежати від порядку аргументів. У `tests/web/test_link_decision_ui.py` додати `test_scene_consistency_texts_exist_in_both_languages`: кожен ключ `consistency.*` з переліку вище є в `uk` і `en` і не порожній.

- [ ] **Step 2: Запустити, переконатися, що падає**

Run: `PYTEST t1 tests/web/test_link_decision_ui.py`
Expected: FAIL — `sceneConsistency` не експортовано; ключів `consistency.*` немає.

- [ ] **Step 3: Реалізувати `sceneConsistency` у `link-actions.js` (підписи затвердження — Г4, `pendingLinks` без змін), додати ключі в `i18n.json`.** Рядки будуються з `materialStatus[sceneId].links` і елементів `pendingLinks` за `key` (елемент `previous` — за Г3).

- [ ] **Step 4: Запустити, переконатися, що проходить**

Run: `PYTEST t1 tests/web/test_link_decision_ui.py tests/web/test_book_validation_ui.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/storygen/web/static/link-actions.js src/storygen/web/static/i18n.json tests/web/js/link_decision.mjs tests/web/test_link_decision_ui.py
git commit -m "feat(ui): чисті правила панелі «Узгодженість сцени»"
```

---

### Task 2: Панель у робочому просторі, перегляд сцени й фокус «Перейти до сцени N»

**Files:**
- Modify: `src/storygen/web/templates/story.html` (замість `#link-attention` — `#scene-consistency`; прибрати `#audit-scene`)
- Modify: `src/storygen/web/static/link-decision.js`
- Modify: `src/storygen/web/static/book-validation.js` (`openStopScene`, Р7)
- Modify: `src/storygen/web/static/app.css` (стилі `.link-attention*` → `.scene-consistency*`; селектор режиму «На весь екран», рядок 460)
- Modify: `src/storygen/web/static/i18n.json` (прибрати невживані ключі `link.*`, Task 1)
- Test: `tests/web/browser/link-decision.spec.mjs`, `tests/web/browser/scene-audit.spec.mjs`, `tests/web/browser/book-validation.spec.mjs`

**Interfaces:**
- Consumes: `sceneConsistency` (задача 1); `operationReason` (`run-readiness.js`); `invokeWorkspaceCommand('run', …)`.
- Produces (DOM, на який спираються задачі 3–5):
  - `<section id="scene-consistency" class="scene-consistency" tabindex="-1" aria-labelledby="scene-consistency-title" aria-live="polite" hidden>` на місці `#link-attention` (між `#workspace-hint-info` і `#workspace-status-row`).
  - `view==='valid'`: лише `<p class="consistency-valid">` з `consistency.valid`.
  - `view==='full'`: заголовок `<h3 id="scene-consistency-title">` + `<span class="consistency-badge">` (`consistency.pending_count {p0:pendingCount, p1:total}`, прихований при 0); `<ul class="consistency-rows">` з `<li data-link="brief|prose|memory" data-state="…">`: `.consistency-icon` (`aria-hidden`), `.consistency-title`, `.consistency-status`; для розбіжності — `.consistency-discrepancy` з приглушеним `summary`, `ul.link-discrepancies > li.link-discrepancy` з `<blockquote>`, `consistency.discrepancy_hint`; дії — `button.link-button` з `data-focus-key="<link>:<i>"`.
  - Головна дія: `<p class="consistency-primary"><button id="scene-consistency-primary" type="button">` (без `secondary`), поруч `<small class="consistency-cost muted">` з `detail` і `<small id="scene-consistency-reason">` з причиною; кнопка має `aria-describedby="scene-consistency-reason"`.
  - Функція `blockedReason()` у `link-decision.js`: `operationReason(state, {ready:true})` || (`ACTIVE_RUN.has(state.workspaceRun?.state)` ? `t('m_506ce9f6bdfa')` : '') || (`busy` ? `t('m_08ee1e43995d')` : '').

Поведінка `link-decision.js`:
- `render()`: `sceneConsistency(state.view?.material_status, state.scene?.id, state.view?.scenes, null, previewFor(key), blockedReason())` (у задачі 3 `null` замінить `panelBookRun`); `view==='none'` → `hidden`.
- Перегляд (Г7): `previewKey()`; якщо ключ змінився й `view==='full'` без `resume` — `POST /api/stories/${state.storyId}/audit/preview {scope:'scene', scene_id}`; відповідь застосовується, лише якщо `previewKey()` той самий (Review Focus 2); помилка запиту → `{ready:false, reason:error.message}`. Ключ скидається на `scene-selected`.
- Фокус (Review Focus 4): перед `replaceChildren()` запам'ятати `data-focus-key` (головна кнопка — `primary`), якщо фокус у панелі; після побудови повернути фокус на елемент із тим самим ключем, якщо він є й не `disabled`, інакше на `#scene-consistency` (`preventScroll:true`). Обробник дії рядка першим переносить фокус на `#scene-consistency` (як `runs.js::button` — на обгортку), а вже потім ставить `busy` і перемальовує.
- Дії рядків — наявні обробники `decide`, `carry`, `openSettings`, `createMemory`; головна `audit` → наявний `audit()`. Опитування переносу пам'яті (`CARRY_POLL_MS`) — без змін, умова за рядком пам'яті зі статусом `link.carry_pending`.
- Слухачі: `story-refreshed`, `scene-selected`, `workspace-run-state`, `workspace-run-pending`, `workspace-readiness`, `editor-state-changed` → `render()`.
- `book-validation.js::openStopScene`: після `selectScene` фокус на `#scene-consistency`, якщо не `hidden`, інакше на `#workspace-status-row` (Р7 harness).

- [ ] **Step 1: Переписати браузерні тести під панель (мають падати)**
  - `link-decision.spec.mjs`: `#link-attention` → `#scene-consistency`; ряди за `li[data-link=…]`; «Затвердити завдання»/«Затвердити відповідність» → «Я перевірив сам»; після затвердження обох — `#scene-consistency` має лише текст «Сцена узгоджена ✓»; Review Focus 4: після кліку «Я перевірив сам» `await expect(page.locator('#scene-consistency')).toBeFocused()`.
  - `scene-audit.spec.mjs`: валідна сцена — `#audit-scene` не існує (`toHaveCount(0)`), панель — «Сцена узгоджена ✓»; сцена `/test-scene-audit`: `#scene-consistency-primary` має текст «Перевірити Ревізором», `.consistency-cost` — «N викл.», де N — `calls` з `request.post(…/audit/preview {scope:'scene', scene_id})` (локальний Ревізор без ціни, тож без «до $»); Review Focus 3: «Я перевірив сам» у рядку завдання → `.consistency-cost` стає «N−1 викл.»; Review Focus 4: посилання «Я перевірив сам» у фокусі до приходу перегляду лишається у фокусі після нього (затримати `audit/preview` через `page.route` на 500 мс); `#scene-consistency-primary` у фокусі лишається у фокусі після `page.evaluate(()=>document.dispatchEvent(new CustomEvent('story-refreshed')))`; далі наявний сценарій: перевірка зі згодою, рядок прози `data-state="discrepancy"` з цитатами, «Розбіжності немає».
  - `scene-audit.spec.mjs`, новий тест Review Focus 2 «a late preview of another scene is dropped»: фікстура `/test-book-validation` (дві сцени); `page.route('**/audit/preview', …)` затримує відповідь першої сцени на 1500 мс; відкрити першу сцену, одразу перейти на другу; через 2000 мс `.consistency-cost` другої сцени дорівнює кількості викликів її власного перегляду (прочитати `request.post(...audit/preview {scope:'scene', scene_id: second_id})`).
  - Новий тест «disabled with the reason»: сцена, де лишилася тільки розбіжність (`/test-scene-audit` після перевірки й затвердження завдання) — кнопка неактивна, `#scene-consistency-reason` — «Ревізору нема що перевіряти: вирішіть зв’язки вручну»; правка в редакторі без збереження — причина з `operationReason` (незбережені зміни).
  - `book-validation.spec.mjs`: `#link-attention [data-link="brief"]` → `#scene-consistency li[data-link="brief"]`; «Затвердити завдання» → «Розбіжності немає»; Р7: `await expect(page.locator('#scene-consistency')).toBeFocused()`. «Продовжити» поки натискається в `#run-actions` (задача 3 перенесе його в панель).

- [ ] **Step 2: Запустити, переконатися, що падає**

Run: `PW link-decision.spec.mjs`, `PW scene-audit.spec.mjs`, `PW book-validation.spec.mjs`
Expected: FAIL — `#scene-consistency` не знайдено.

- [ ] **Step 3: Реалізувати розмітку, рендер, перегляд, фокус і стилі за Interfaces.** Стилі — за макетом варіанта 1: рядки з верхньою межею, значки кольорами `--success`/`--text-secondary`/`--warning` наявних токенів `app.css`, розбіжність — блок із лівою смугою кольору попередження. `#workspace.focus-mode #link-attention` → `#workspace.focus-mode #scene-consistency`. Прибрати невживані ключі `link.*` (Task 1, Interfaces).

- [ ] **Step 4: Запустити, переконатися, що проходить**

Run: `PW link-decision.spec.mjs`, `PW scene-audit.spec.mjs`, `PW book-validation.spec.mjs`, `PW workspace-layout.spec.mjs`
Expected: PASS.
Run: `PYTEST t2 tests/web/test_link_decision_ui.py tests/web/test_book_validation_ui.py tests/web/test_run_progress_ui.py tests/web/test_localization.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/storygen/web/templates/story.html src/storygen/web/static/link-decision.js src/storygen/web/static/book-validation.js src/storygen/web/static/app.css src/storygen/web/static/i18n.json tests/web/browser/link-decision.spec.mjs tests/web/browser/scene-audit.spec.mjs tests/web/browser/book-validation.spec.mjs
git commit -m "feat(ui): панель «Узгодженість сцени» замість панелі зв’язків і кнопки «Перевірити сцену»"
```

---

### Task 3: «Продовжити валідацію» в панелі й `bookResumeInRow` у рядку (Р1)

**Files:**
- Modify: `src/storygen/web/static/book-validation-state.js` (`panelBookRun`)
- Modify: `src/storygen/web/static/runs.js` (`updateControls`, команда `resume-run`)
- Modify: `src/storygen/web/static/link-decision.js` (кеш запуску книги, головна `resume`)
- Test: `tests/web/js/book_validation.mjs`, `tests/web/browser/book-validation.spec.mjs`

**Interfaces:**
- Consumes: `sceneConsistency` (задача 1), DOM панелі (задача 2), наявні `bookResumeInRow(run, scenes)`, `revealBlocked(current, run)`, `latestBookRun(runs, current)`.
- Produces:
  - `panelBookRun(cached, runs, current) -> Run | null` у `book-validation-state.js`: `cached`, якщо `current` — той самий запуск у тому самому стані (короткий запуск із `workspace-run-pending` не має `checkpoint`); інакше `current`, якщо це валідація книги; інакше `cached`, якщо `cached` — валідація книги, у `runs` є запис із тим самим `id` і тим самим `state`, а `latestBookRun(runs, null)?.id === cached.id`; інакше `null`.
  - Команда `registerWorkspaceCommand('resume-run', async run => …)` у `runs.js`: `revealBlocked(active, run)` → `throw new Error(t('book_validation.other_run_active'))`; `active?.id !== run.id` → `await follow(run, {reveal:true})`; далі `await resumeRun(false)`.
  - `updateControls`: обгортка дії `resume` прихована й тоді, коли `!bookResumeInRow(active, state.view?.scenes)`.
  - `link-decision.js`: `let bookRun=null`; на `workspace-run-state` — `if(isBook(detail)) bookRun=detail`; у `render()` — `run = panelBookRun(bookRun, state.workspaceRuns, state.workspaceRun)`; для головної `resume` `blocked` = `revealBlocked(state.workspaceRun, run) ? t('book_validation.other_run_active') : operationReason(state,{ready:true})`; клік → `invokeWorkspaceCommand('resume-run', run)` з наявною обробкою помилок (`AbortError` мовчки).

- [ ] **Step 1: Написати тести, що падають**

`book_validation.mjs` (Review Focus 1):

```js
const {panelBookRun}=await import(pathToFileURL(root+'/src/storygen/web/static/book-validation-state.js'));
const stopped={...bookRun('b','needs_review'),checkpoint:{scene_id:'s1',link:'brief',outcome:'discrepancy'}};
const memoryRun={id:'m',state:'running',request:{mode:'stage',stage:'memory'}};
assert.equal(panelBookRun(null,[],stopped),stopped);
assert.equal(panelBookRun(stopped,[{...bookRun('b','needs_review')}],{...bookRun('b','needs_review')}),stopped);  // a short current keeps the full cached run
assert.equal(panelBookRun(stopped,[{...bookRun('b','needs_review')},memoryRun],memoryRun),stopped);  // the row moved to a memory run
assert.equal(panelBookRun(stopped,[{...bookRun('b','completed')}],null),null);                       // resumed elsewhere
assert.equal(panelBookRun(stopped,[{...bookRun('b','needs_review')},{...bookRun('c','queued')}],null),null);  // a newer book run
assert.equal(panelBookRun(null,[{...bookRun('b','needs_review')}],memoryRun),null);                  // no full run: the menu reveals it
```

`book-validation.spec.mjs`, перший тест, після переходу «Перейти до сцени 1»:
- `#run-actions` не має видимої «Продовжити» (`getByRole('button',{name:'Продовжити',exact:true})` — `toBeHidden()`);
- `#scene-consistency-primary` — «Продовжити валідацію», неактивна, `#scene-consistency-reason` — «Спершу вирішіть зв’язок»; кнопки «Перевірити Ревізором» немає;
- після «Розбіжності немає» в рядку завдання — активна; клік → діалог «Сцен до перевірки: 2.», «Підтвердити» → запуск `completed`, далі наявні перевірки (заголовок «перевірено сцен 2 з 2», фокус на заголовку, меню «Книга валідна»).

- [ ] **Step 2: Запустити, переконатися, що падає**

Run: `PYTEST t3 tests/web/test_book_validation_ui.py`; `PW book-validation.spec.mjs`
Expected: FAIL — `panelBookRun` не експортовано; «Продовжити» видима в рядку.

- [ ] **Step 3: Реалізувати `panelBookRun`, команду `resume-run`, приховування в `updateControls` і головну `resume` панелі.** Перед правкою `updateControls` — `grep -n "wrapper.hidden\|resume" tests/web/test_run_status_collapse_ui.py tests/web/test_resumed_events.py` і тести рядків `RUN-RECOVERY-UI-*` у `traceability.json`: буквальні рядки `runs.js`, які вони звіряють, лишаються; нова умова дописується окремим виразом.

- [ ] **Step 4: Запустити, переконатися, що проходить**

Run: `PYTEST t3 tests/web/test_book_validation_ui.py tests/web/test_link_decision_ui.py tests/web/test_resumed_events.py tests/web/test_run_status_collapse_ui.py tests/web/test_run_progress_ui.py`; `PW book-validation.spec.mjs`, `PW scene-audit.spec.mjs`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/storygen/web/static/book-validation-state.js src/storygen/web/static/runs.js src/storygen/web/static/link-decision.js tests/web/js/book_validation.mjs tests/web/browser/book-validation.spec.mjs
git commit -m "feat(ui): «Продовжити валідацію» в панелі сцени зупинки; рядок ховає «Продовжити» книги"
```

---

### Task 4: Відкладені дрібниці ядра (Г8–Г10)

**Files:**
- Modify: `src/storygen/web/static/run-summary.js` (`revealTakesFocus`), `src/storygen/web/static/runs.js` (`revealRun`, `draw`)
- Modify: `src/storygen/web/static/run-progress.js` (`countsOf`)
- Modify: `src/storygen/generation/pipeline.py:20`, `src/storygen/memory/service.py:127`
- Modify: `tests/web/browser/server.py` (`book_validation_fixture(slow_auditor: bool = False)`)
- Test: `tests/web/js/run_summary.mjs`, `tests/web/js/run_progress.mjs`, `tests/generation/test_scene_pipeline.py`, `tests/memory/test_rebuild.py`, `tests/web/browser/book-validation.spec.mjs`

**Interfaces:**
- Produces:
  - `revealTakesFocus(element) -> boolean` у `run-summary.js`: `false`, якщо `element?.matches?.('textarea, input, select, [contenteditable]:not([contenteditable="false"])')`, інакше `true` (Г8). `revealRun` ставить фокус лише за `revealTakesFocus(document.activeElement)`; розгортання й прокрутка — як у ядрі.
  - `draw()`: якщо `refocus` і нового `.run-progress-title` немає — фокус на `summaryNode` (`preventScroll:true`).
  - `countsOf`: `calls?.planned` враховується, лише якщо `Number.isFinite(calls.planned)`, інакше `run_progress.calls_open`.
  - `stage_finished` у `generate_scene` і `rebuild_memory`: `{'attempt_id':…, 'state':…, 'usage':attempt.usage}` (Г10).
  - Фікстура `/test-book-validation?slow_auditor=true` — Ревізор `synthetic-slow` (тримає запуск до скасування).

- [ ] **Step 1: Написати тести, що падають**
  - `run_summary.mjs`: `assert.equal(revealTakesFocus({matches:s=>s.includes('textarea')}),false); assert.equal(revealTakesFocus({matches:()=>false}),true); assert.equal(revealTakesFocus(null),true);`
  - `run_progress.mjs`: `progressText(book,{...base,calls:{done:2,planned:'x'}},scenes).counts` починається з «Викликів: 2» без « / » і `fraction === null`.
  - `test_scene_pipeline.py::test_stage_finished_carries_the_usage` і `test_rebuild.py::test_rebuild_stage_finished_carries_the_usage`: `on_event`, що збирає події; кожна `stage_finished` має ключ `usage`, рівний `attempt.usage` повернутої спроби.
  - `book-validation.spec.mjs`, тест «the running validation is shown from the menu and starts nothing»: фікстура `slow_auditor=true`; перегляд і `POST /api/runs` через `request`; `page.goto` сцени; `#editor` у фокусі; меню — «Валідація триває: показати», активний; клік → `#run-status .run-progress-title` у фокусі, `runs().length === 1`; `finally` — `cancel`.
  - Той самий файл, тест «a slow run GET does not take the focus from the editor» (Г8): `page.route('**/api/runs/*', …)` затримує перший `GET` після `POST /api/runs` на 1500 мс; після «Почати валідацію» — `await page.locator('#editor').focus()`; дочекатися `#run-status .run-progress-title` (з'являється лише після затриманого GET; клас `expanded` ставиться ще до нього) — `#editor` усе ще у фокусі.
  - Той самий файл, тест «the focus stays in the run row when the progress block goes away»: `page.route` для `GET /api/runs/*` повертає відповідь сервера з `progress: null`, коли `run.state === 'needs_review'`; після «Почати валідацію» й `needs_review` у фокусі `#run-status .run-summary`.

- [ ] **Step 2: Запустити, переконатися, що падає**

Run: `PYTEST t4 tests/web/test_run_status_collapse_ui.py tests/web/test_run_progress_ui.py tests/generation/test_scene_pipeline.py tests/memory/test_rebuild.py`; `PW book-validation.spec.mjs`
Expected: FAIL у кожному новому тесті (тест меню «триває» може пройти одразу — це тест на вже виправлену поведінку ядра, відсутній RED записати в журнал).

- [ ] **Step 3: Реалізувати за Interfaces.**

- [ ] **Step 4: Запустити, переконатися, що проходить**

Run: `PYTEST t4 tests/web/test_run_status_collapse_ui.py tests/web/test_run_progress_ui.py tests/web/test_resumed_events.py tests/generation/test_scene_pipeline.py tests/memory/test_rebuild.py tests/generation/test_run_progress.py`; PW для кожного spec із `toBeFocused` (`grep -l toBeFocused tests/web/browser/*.spec.mjs`), щонайменше `book-validation.spec.mjs` і `workspace-telemetry.spec.mjs`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/storygen/web/static/run-summary.js src/storygen/web/static/runs.js src/storygen/web/static/run-progress.js src/storygen/generation/pipeline.py src/storygen/memory/service.py tests/web/browser/server.py tests/web/js/run_summary.mjs tests/web/js/run_progress.mjs tests/generation/test_scene_pipeline.py tests/memory/test_rebuild.py tests/web/browser/book-validation.spec.mjs
git commit -m "fix(ui): рядок не забирає фокус із редактора й не губить його без блоку прогресу; usage у stage_finished пам'яті й конвеєра"
```

---

### Task 5: SPEC.MD, traceability, сайт uk/en, знімки, `manual.md`

**Files:**
- Modify: `SPEC.MD`, `docs/verification/traceability.json`, `docs/verification/manual.md`
- Modify: `docs/site/uk/workspace.md`, `docs/site/en/workspace.md`, `docs/site/uk/troubleshooting.md`, `docs/site/en/troubleshooting.md`
- Modify: `scripts/capture_screenshots.py`; знімки `docs/images/site/{uk,en}/`
- Modify: `docs/STATUS.md` (через `scripts/verify.py`)
- Test: `python scripts/check_docs.py`, `python scripts/check_site.py --rehash workspace`, `--rehash troubleshooting`

**Interfaces:**
- Consumes: імена тестів задач 1–4.
- Produces: сценарії `VALID-LINKS-S15`, `VALID-UI-S06` з якорями `<a id="…"></a>` у стилі сусідніх.

Зміни SPEC.MD (українською, маркери OpenSpec англійською):
- **VALID-LINKS, «Читачі», робочий простір:** панель `#scene-consistency` (`link-actions.js::sceneConsistency`, рендер — `link-decision.js`) замість `#link-attention`; новий `VALID-LINKS-S15 — Панель «Узгодженість сцени»` (GIVEN сцени з неперевіреними, розбіжними, недоступними, валідними й відсутніми зв'язками; WHEN автор відкриває сцену; THEN три рядки в порядку завдання → проза → пам'ять зі значками й станами, розбіжність із впевненістю, підсумком і цитатами; AND дії-посилання «Я перевірив сам» / «Розбіжності немає» з тим самим затвердженням за відбитком; AND валідна сцена — один рядок «Сцена узгоджена ✓», сцена без того, що вирішувати, — без панелі (Г2); AND «Перевірити Ревізором» з «N викл., до $X» з перегляду сцени, неактивна з причиною при 0 викликах, неготовому перегляді, незбережених змінах чи іншому активному запуску).
- **VALID-MEMORY** (абзац «Панель зв'язків», ~7359) і **VALID-AUDITOR** («Панель розбіжностей», ~7548): назва й розмітка панелі, нові підписи (Г4), рядок пам'яті попередньої сцени (Г3).
- **VALID-RUN** («Інтерфейс перевірки сцени», ~7664; S01; відомі обмеження ~7670, ~7679): кнопка «Перевірити Ревізором» у панелі, перегляд читає панель (Г7) і показує виклики й межу; прибрати обмеження «Кнопка «Перевірити сцену» видима й тоді, коли зв'язок чекає рішення» (усунено: 0 викликів — неактивна з поясненням); у 409 замінити «натискає «Перевірити сцену»» на «Перевірити Ревізором».
- **VALID-UI:** абзац «Зупинка» — фокус на `#scene-consistency` (прибрати тимчасове Р7); «Продовжити валідацію» в панелі за Г6, рядок ховає «Продовжити» книги, поки сцена зупинки є (`bookResumeInRow`, прибрати тимчасове Р1 і обмеження «поки лишається в рядку»); прибрати обмеження «Кнопки «Перевірити сцену» немає в сцени `incomplete`» (панель пропонує перевірку З1); додати обмеження Г5. Оновити `VALID-UI-S04` (WHEN «Перейти до сцени 1», «Розбіжності немає» і «Продовжити валідацію» в панелі; AND «Продовжити» в рядку не показано). Новий `VALID-UI-S06 — «Продовжити валідацію» на сцені зупинки` (неактивна з «Спершу вирішіть зв'язок», доки стан зв'язку дорівнює `checkpoint.outcome`; активна після рішення або для `unavailable` Ревізора; панель тримає запуск книги, коли рядок перейшов на інший запуск; сцена зупинки в кошику — «Продовжити» в рядку).
- **RUN-RECOVERY-UI:** виняток із «для paused/needs_review/alternative — resume» і «блокери не приховують кнопку»: валідація книги в `needs_review`, чия сцена зупинки є в творі, показує продовження в панелі сцени зупинки, а не в рядку (VALID-UI-S06); оновити `scope` її рядків traceability, якщо вони згадують видимість resume.
- **R20-WORKSPACE:** рядок стану без `#audit-scene`; `revealRun` не забирає фокус з поля введення (Г8); фокус переходить на підсумок, коли блоку прогресу немає; відоме обмеження — мигання лічильників після продовження чи перезавантаження до наступного GET (якщо ще немає).
- Нові тексти в переліку каталогу VALID-UI: ключі `consistency.*`.

Рядки `traceability.json` (ручна процедура — якорі `docs/verification/manual.md`, причина «Playwright запускається окремим runner; check_docs.py індексує лише pytest IDs»):
- `VALID-LINKS-S15`: `tests/web/test_link_decision_ui.py::test_link_panel_actions`, `::test_scene_consistency_texts_exist_in_both_languages` + `manual.md#link-decision-browser` (наявний якір).
- `VALID-UI-S06`: `tests/web/test_book_validation_ui.py::test_book_validation_helpers`, `tests/web/test_link_decision_ui.py::test_link_panel_actions` + `manual.md#book-validation-browser`.
- Оновити `scope` і тести: `VALID-UI-S04`, `VALID-UI-S05` (тест меню «триває»), `R20-WORKSPACE-S10` (`run_summary.mjs` — `revealTakesFocus`), `VALID-RUN-S01` (+ `manual.md#scene-audit-browser`), `VALID-RUN-S12` (+ `tests/generation/test_scene_pipeline.py::test_stage_finished_carries_the_usage`, `tests/memory/test_rebuild.py::test_rebuild_stage_finished_carries_the_usage`).

Сайт: розділи `workspace.md` «Стан сцени: валідна чи не перевірена», «Перевірка сцени Ревізором», «Валідація книги» (обидві мови) — панель, значки, «Я перевірив сам» / «Розбіжності немає», «Перевірити Ревізором» з ціною й причиною неактивності, «Перейти до сцени N» і «Продовжити валідацію» в панелі, рядок прогресу з «Викликів: n / N · Витрачено: $x з $y»; `troubleshooting.md` — рядки «Ревізору нема що перевіряти: вирішіть зв’язки вручну», «Спершу вирішіть зв’язок» (що робити) і оновлені назви кнопок у наявних рядках. Нові знімки вставити в «Перевірка сцени Ревізором» і «Валідація книги».

Знімки (`capture_screenshots.py`, нейтральний seed; задати рішення):
- `seed()`: сцена 1 («Ранок у селищі»/«Morning in the village») — завдання автора, ручна проза (`save_manual_prose`) і пам'ять (`save_scene_memory`, як у `book_validation_fixture`); сцена 2 — наявні завдання й чернетка плюс ручна проза й пам'ять. Ревізор — `save_role_settings(…, 'auditor', RoleSettings(provider=ProviderSettings(provider='local', base_url='http://127.0.0.1:11434/v1', model='neutral-auditor'), …))`, тож перегляд готовий без ключа й без ціни. `write_auditor_verdict`: сцена 1 З1 `discrepancy`; сцена 2 З2 `discrepancy` (confidence 72, підсумок і одна розбіжність із цитатою з чернетки).
- Зупинена валідація книги — окрема функція `seed_stopped_validation(data_dir, ids)`, яку `main()` викликає після загальних знімків (бібліотека, `workspace-*`, `story-menu-*`, форма завдання, локації, налаштування, публікація), поки сервер іде; так меню лишається «Валідація книги (N)», як описує `workspace.md`. Запуск `audit`/`story` у `needs_review` через `run_store.enqueue_run` і `save_run` (прочитати обидві), `planned_telemetry {'roles':{'auditor':{'provider':'openrouter','model':'neutral/auditor'}}, 'calls':4, 'cost_bound_usd':'0.0210', 'scenes':2}`, `checkpoint {scene_id: сцена 1, link:'brief', outcome:'discrepancy', verdict_id, reason:None, phase:'awaiting_author'}`; події `append_run_event`: `stage_started {stage:'audit_brief', scene_id, link:'brief', model, provider}`, `stage_finished {attempt_id:'shot-1', state:'completed', usage:{'cost':{'usd':0.0052}}}`, `audit_step {scene_id, link:'brief', outcome:'discrepancy', verdict_id, attempt_id:'shot-1'}`.
- Окремий прохід `capture_validation()` (desktop, після `seed_stopped_validation`): на сцені 2 — `#scene-consistency` знімком елемента → `scene-consistency-desktop.png` (○ завдання, ! проза з цитатою, ✓ пам'ять, «Перевірити Ревізором 1 викл.»); `#workspace-status-row` знімком елемента → `run-progress-desktop.png` (розгорнутий рядок зупинки з «Перейти до сцени 1»).
- Після зйомки закомітити лише змінені за змістом знімки: `workspace-*` (тепер із панеллю), нові два; решту з шумом пікселів повернути `git checkout -- <file>`.

- [ ] **Step 1: Внести нові ID у матрицю й переконатися, що перевірка падає**

Run: `PYTHONUTF8=1 /c/Projects/text-generator/.venv/Scripts/python.exe scripts/check_docs.py`
Expected: FAIL «Матриця: зайвий сценарій VALID-LINKS-S15» (і `VALID-UI-S06`).

- [ ] **Step 2: Внести зміни SPEC.MD і `manual.md`** (розділи «Рішення автора», «Перевірка сцени Ревізором», «Валідація книги з меню твору»: нові кроки панелі, `resume` з панелі, тести задачі 4).

- [ ] **Step 3: Оновити сайт uk і en, seed знімків; зняти знімки**

Run: `PYTHONUTF8=1 PYTHONPATH=src /c/Projects/text-generator/.venv/Scripts/python.exe scripts/capture_screenshots.py --work-dir C:/tmp/vpux/shots`
Expected: список знімків, серед них `docs/images/site/uk/scene-consistency-desktop.png` і `run-progress-desktop.png` для обох мов. Переглянути кожен новий знімок (Read) — без приватних матеріалів, панель і рядок видно повністю.

- [ ] **Step 4: Підтвердити пари сторінок і документацію**

Run: `PYTHONUTF8=1 /c/Projects/text-generator/.venv/Scripts/python.exe scripts/check_site.py --rehash workspace` і `… --rehash troubleshooting`
Run: `PYTHONUTF8=1 /c/Projects/text-generator/.venv/Scripts/python.exe scripts/check_docs.py`
Expected: без помилок.

- [ ] **Step 5: Повна перевірка й STATUS**

Run: `PYTEST t5 tests/web tests/generation tests/memory`; `PW link-decision.spec.mjs scene-audit.spec.mjs book-validation.spec.mjs workspace-layout.spec.mjs workspace-telemetry.spec.mjs run-status-collapse.spec.mjs`
Run: `PYTHONUTF8=1 /c/Projects/text-generator/.venv/Scripts/python.exe scripts/verify.py` — фактичний запуск записується в `docs/STATUS.md`.
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add SPEC.MD docs/verification/traceability.json docs/verification/manual.md docs/site docs/images/site scripts/capture_screenshots.py docs/STATUS.md
git commit -m "docs: панель «Узгодженість сцени», продовження валідації з панелі, сайт uk/en і знімки"
```

Після задачі 5: whole-branch рев'ю, крос-рев'ю (`detent:cross-review`), PR на `main` з «Closes #269» лише якщо це останній PR задачі R-44 (інакше без), синхронізація основної теки за AGENTS.md. У описі PR — оновлені сторінки сайту uk/en і знімки.
