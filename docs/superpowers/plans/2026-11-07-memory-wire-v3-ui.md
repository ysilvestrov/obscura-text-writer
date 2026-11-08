# Пам’ять wire v3, пакет 2: діагностика й докази в UI, перехід власного промпту на v3, інструкції — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Автор бачить повний список порушень невдалої спроби пам’яті й додаткові докази записів, може явно перевести власний промпт пам’яті з `/2` на `/3`, а інструкції UA/EN описують wire v3 і режим `json_schema`.

**Architecture:** Сервер віддає вже збережені `attempt.context.memory_violations` і `memory_warnings` через `/api/runs/{id}` (лише ці ключі, без решти контексту) та `supporting_quotes` у рядках перегляду пам’яті. Новий прапорець `SettingsChange.upgrade_memory_wire` зберігає новий текст власного промпту з контрактом `memory/evidence_delta/3`; без прапорця правило `/2` не змінюється. UI — малі ES-модулі за чинним шаблоном (`uiText`, `t()`, `i18n.json`), тести — Node `.mjs` через pytest-обгортки.

**Tech Stack:** Python 3.12, FastAPI, pydantic; vanilla ES modules; pytest + Node.

**Spec:** `docs/specs/2026-11/memory-wire-v3.md` (затверджено 07.11.2026), розділи «Повна діагностика», «Журнал», «Інструкції UA/EN»; SPEC.MD MEMORY-003/004, PROMPT-CONTRACT.

**База:** `origin/main` **після злиття PR Codex зі стеком codex** (`codex/merge-stack-into-main`). Стек змінює `runs.js`, `settings.js`, `i18n.json`, `routes_settings.py`, `editor.js` — починати раніше означає гарантований конфлікт. Перед Task 1 оновити гілку `claude/memory-wire-v3-ui` до свіжого `origin/main`.

## Global Constraints

- Жодних текстів, ID claim/персонажів чи значень моделі в діагностиці: список порушень показує лише мітку операції (`<категорія>.<дія>, елемент N` / `Операція N` / `Відповідь`) і код (MEMORY-004).
- Список порушень — до 50 записів; якщо `total` > кількості записів, показати «ще N».
- `/api/runs/{id}` не відкриває `attempt.context` цілком: додається лише `memory_violations` і `memory_warnings`, коли вони є.
- `supporting_quotes` — 0–2 дослівні цитати; показуються після основної цитати в тому самому порядку.
- Без `upgrade_memory_wire` власний промпт `/2` лишається `/2` (PROMPT-CONTRACT-S02 не змінюється).
- Мітки кодів порушень — у `i18n.json` для `uk` і `en`; нові рядки UI теж двомовні.
- Документація українською, маркери OpenSpec англійською; кожен новий Scenario — сталий ID і запис у `docs/verification/traceability.json`; `python scripts/check_docs.py` зелений.
- Знімки інтерфейсу лише з нейтральними прикладами.

## Review Focus

1. Спроба пам’яті, що впала до валідації (мережа, JSON decode без збирача), не має `memory_violations` — UI не малює порожній список і не падає.
2. Спроба зі старим контекстом (до ядра) або v2-відповіддю — мітки `Операція N` теж локалізуються.
3. Журнал без `supporting_quotes` (старі записи) — таблиця пам’яті показує лише основну цитату, без порожніх рядків.
4. `upgrade_memory_wire` із порожнім або стандартним текстом — повертає стандартний промпт (v3), не створює власну версію.
5. `upgrade_memory_wire` для ролі, що не є пам’яттю, або режиму `snapshot` — відхиляється, а не тихо ігнорується.

---

### Task 1: Сервер — порушення в API спроби, додаткові докази в перегляді пам’яті, перехід промпту на `/3`

**Files:**
- Modify: `src/storygen/web/routes_runs.py` (`/api/runs/{id}`, рядки ~48–56)
- Modify: `src/storygen/memory/forwarding.py` (`memory_view_from_view`, рядок ~51)
- Modify: `src/storygen/web/routes_settings.py` (`SettingsChange`, `configure_prompts`, `_custom_contract`)
- Modify: `SPEC.MD` (MEMORY-003, MEMORY-004, PROMPT-CONTRACT), `docs/verification/traceability.json`
- Test: `tests/web/test_memory_violations_api.py` (новий), `tests/web/test_memory_forwarding_api.py`, `tests/web/test_evidence_settings.py`

**Interfaces:**
- Produces: кожен елемент `attempts` у `/api/runs/{id}` має необов’язкові `memory_violations: {"items":[{"operation":str,"code":str}], "total":int}` і `memory_warnings: list[str]`; рядок `/api/scenes/{id}/memory-view` має `supporting_quotes: list[str]`; `SettingsChange.upgrade_memory_wire: bool = False`.

- [ ] **Step 1: Тести (мають впасти)**

```python
def test_run_details_expose_memory_violations_without_context(client, failed_memory_run):
    attempt = client.get(f'/api/runs/{failed_memory_run}').json()['attempts'][-1]
    assert attempt['memory_violations']['total'] == 3
    assert {i['code'] for i in attempt['memory_violations']['items']} == {'evidence_unknown', 'add_limit', 'target_unknown'}
    assert 'context' not in attempt and 'fragments' not in json.dumps(attempt)

def test_run_details_without_violations_have_no_key(client, completed_memory_run):
    assert 'memory_violations' not in client.get(f'/api/runs/{completed_memory_run}').json()['attempts'][-1]

def test_memory_view_rows_carry_supporting_quotes(...):
    # подія з двома supporting_quotes → row['supporting_quotes'] == [q2, q3]; стара подія → []

def test_upgrade_memory_wire_saves_v3_contract(...):
    # чинний власний промпт /2; SettingsChange(prompt_text=<новий текст>, upgrade_memory_wire=True)
    # → нова версія має prompt_contract memory/evidence_delta/3
def test_upgrade_memory_wire_confirm_without_text_saves_v3(...)   # confirm_prompt_contract + upgrade
def test_upgrade_with_standard_or_blank_text_returns_builtin(...)  # prompt_version_id is None
def test_upgrade_rejected_for_non_memory_role_or_snapshot(...)     # ValueError → 400/422
def test_v2_prompt_without_upgrade_stays_v2(...)                   # регресія PROMPT-CONTRACT-S02
def test_contract_follows_incoming_prompt_version_id(...)
    # _custom_contract бере збережений контракт із settings.prompt_version_id запиту, а не з попередніх налаштувань ролі
```

Фікстури брати з наявних `tests/web/test_evidence_settings.py` і `tests/web/test_memory_forwarding_api.py`; спробу з порушеннями — збереженням `StageAttempt` з `context['memory_violations']` (як у `tests/memory/test_violations.py`).

- [ ] **Step 2: Запустити — FAIL**

`PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/web/test_memory_violations_api.py tests/web/test_memory_forwarding_api.py tests/web/test_evidence_settings.py -q --basetemp=C:/tt/p2t1`

- [ ] **Step 3: Реалізація**
  - `routes_runs.py`: `public` = `model_dump(exclude={'context'})` плюс `memory_violations`/`memory_warnings` із `a.context`, лише якщо ключ присутній і має очікуваний тип (`dict` / `list`).
  - `forwarding.py`: `'supporting_quotes': list(event.supporting_quotes)`.
  - `routes_settings.py`: `upgrade_memory_wire` дозволений лише для `role=='memory'` і `settings.memory_mode=='evidence_delta'` (інакше `ValueError('Перехід на v3 можливий лише для власного промпту пам’яті за доказами')`); за прапорця `_custom_contract` повертає `expected_contract` (`/3`). `_custom_contract` читає збережений контракт за `settings.prompt_version_id` (вхідні налаштування).

- [ ] **Step 4: SPEC + traceability**
  - MEMORY-004: новий `Scenario: MEMORY-004-S05 — Повний список порушень у деталях спроби` (GIVEN спроба з `memory_violations`; WHEN читаються деталі запуску; THEN API віддає список і `total` без контексту; AND UI показує мітки й коди, «ще N» понад 50).
  - MEMORY-003: доповнити MEMORY-003-S03 або новий `MEMORY-003-S04 — Додаткові докази в перегляді пам’яті`.
  - PROMPT-CONTRACT: замінити «окремий UI вибору `/3` … поза ядром» на опис `upgrade_memory_wire`; новий `Scenario: PROMPT-CONTRACT-S03 — Явний перехід власного промпту пам’яті на v3`.
  - traceability: тести Task 1 для S05/S04/S03 (UI-частину S05 доповнить Task 2).

- [ ] **Step 5: Тести й docs — PASS**

Той самий pytest + `tests/web tests/memory -q`, `PYTHONIOENCODING=utf-8 python scripts/check_docs.py`.

- [ ] **Step 6: Commit** (повідомлення: що змінено; «Docs: SPEC/traceability; user docs — Task 3»).

### Task 2: UI — список порушень, додаткові докази, назва режиму, перехід на v3

**Files:**
- Create: `src/storygen/web/static/memory-violations.js`
- Modify: `src/storygen/web/static/runs.js` (термінальний стан запуску), `memory-table.js` (рядок ~59, блок доказу), `settings.js` (рядок ~31 — опції `memory_mode`; блок контракту ~59), `settings-state.js` (`expectedPromptContract`), `i18n.json`
- Test: `tests/web/js/memory_violations.mjs` + `tests/web/test_memory_violations_ui.py`; доповнити `tests/web/js/memory-table.mjs`, `tests/web/js/evaluator_settings.mjs` або наявний тест налаштувань для `expectedPromptContract`

**Interfaces:**
- Consumes: поля Task 1.
- Produces: `export function violationDetails(violations, {t}) -> HTMLElement|null` у `memory-violations.js`; `expectedPromptContract(stage, mode, stored, custom, text, upgrade=false)`.

- [ ] **Step 1: Тести (Node, мають впасти)**
  - `violationDetails(undefined)` і `violationDetails({items:[],total:0})` → `null`.
  - 3 записи → `<details>` з 3 `<li>`, кожен «мітка · локалізований код»; `total: 57`, 50 записів → останній рядок «ще 7».
  - Мітки `Операція 2`, `Відповідь`, `facts.add, елемент 1` проходять як є (вони вже людські з сервера), а невідомий код показується сирим.
  - Таблиця пам’яті: рядок із `supporting_quotes:[a,b]` → у `<details>` три абзаци в порядку quote, a, b; рядок без поля → один.
  - `expectedPromptContract('memory','evidence_delta',{stage:'memory',mode:'evidence_delta',schema_version:2},'p1','текст',true)` → `memory/evidence_delta/3`; без `upgrade` → `/2`.

- [ ] **Step 2: Запустити — FAIL** (`pytest tests/web/test_memory_violations_ui.py tests/web/test_memory_table_ui.py ... -q`)

- [ ] **Step 3: Реалізація**
  - `runs.js`: коли термінальна спроба запуску (останній елемент `attempts` із відповіді `/api/runs/{id}`) має `memory_violations`, додати `violationDetails(...)` до `status` під повідомленням помилки.
  - `memory-table.js`: у `proof` додати абзац на кожну `row.supporting_quotes`.
  - `settings.js`: опція `evidence_delta` — «Операції пам’яті v3 за доказами» (новий i18n-ключ uk/en, старий `m_205a34669725` не перевикористовувати); під режимом підказка: «Для моделей, що підтримують схему, оберіть режим відповіді json_schema — він унеможливлює більшість помилок формату». Коли збережений контракт власного промпту `/2` — прапорець «Перевести власний промпт на формат v3» (`upgrade_memory_wire`), з поясненням, що текст промпту має вимагати групований формат v3; підпис очікуваного контракту враховує прапорець.
  - `i18n.json`: мітки кодів (`evidence_unknown`, `evidence_count`, `add_limit`, `ops_limit`, `target_unknown`, `target_meta`, `target_twice`, `scope_unknown`, `schema`, `wire_version`, `unmappable` не потрібен), «ще {p0}», заголовок списку — uk і en.

- [ ] **Step 4: SPEC + traceability** — UI-частина MEMORY-004-S05 і PROMPT-CONTRACT-S03 → Node-тести.

- [ ] **Step 5: PASS** — `pytest tests/web -q`, `check_docs.py`.

- [ ] **Step 6: Commit.**

### Task 3: Інструкції UA/EN і відкладені дрібниці

**Files:**
- Modify: `docs/memory-view.md` (UA), `docs/evidence-and-copyediting.md` (рядок 7: опис формату — тепер групований v3, `evidence_ids` 1–3, додаткові докази), `README.md` (посилання за потреби)
- Create: `docs/en/memory-view.md` (EN-відповідник; додати до EN-навігації, якщо вона є після злиття стеку)
- Modify: `src/storygen/generation/context.py` (проза пам’яті читається один раз для меж схеми й фрагментів), `SPEC.MD` (MEMORY-002: `schema_version` — integer `enum: [3]`)
- Test: `tests/memory/test_replay.py` (`--story` фільтрує, недоступна БД → код 2 і `db_unavailable` у stderr), наявні тести контексту без змін

- [ ] **Step 1: Тести replay (FAIL для нових випадків, якщо поведінка відсутня; інакше одразу PASS — це закриття прогалин покриття)**
- [ ] **Step 2: Рефактор подвійного читання прози** — поведінка й тести контексту без змін (`tests/generation -q` зелений до й після).
- [ ] **Step 3: Документація**
  - UA/EN: що таке пам’ять за доказами v3; кілька доказів на запис і де їх видно; повний список порушень у статусі запуску й що означають коди; рекомендація `json_schema`; як перевести власний промпт на v3 і що старий `/2` працює далі.
  - Знімок таблиці пам’яті/статусу — лише якщо в `docs/images` уже є відповідний знімок; нейтральний приклад.
- [ ] **Step 4: Перевірки** — `check_docs.py`; `python scripts/verify.py` (0 failed, запис у `docs/STATUS.md`).
- [ ] **Step 5: Commit** (повідомлення: оновлені UA/EN інструкції).

## Після задач

Фінальна ревізія гілки, cross-review (`--author claude`), PR у `main`, запис у журнал виконання, оновлення основної теки (після злиття стеку codex вона вже може бути на `main`). Після злиття останнього PR зміни — рядок «Actual» в оцінці спеки.
