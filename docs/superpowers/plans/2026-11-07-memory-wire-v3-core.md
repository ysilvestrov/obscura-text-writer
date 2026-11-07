# Пам’ять wire v3 — план ядра

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Модель пам’яті повертає згрупований wire v3 із кількома доказами, сервер перекладає його в чинний журнал v2 і повідомляє всі порушення разом.

**Architecture:** Журнал (`memory/journal.py`) отримує адитивне поле `supporting_quotes`. Новий модуль `memory/violations.py` збирає незалежні порушення для v2 і v3. Новий модуль `memory/wire_v3.py` розбирає й перекладає v3 у `MemoryEvent`. Версію wire визначає контракт промпту (`prompt_contracts.py`): стандартний промпт — v3, власний промпт `memory/evidence_delta/2` лишається на v2. Версія передається в спробу через `fragments['memory_wire_version']`.

**Tech Stack:** Python 3, Pydantic v2, pytest, SQLite (без міграції).

**Spec:** `docs/specs/2026-11/memory-wire-v3.md` (затверджено 2026-11-07). Чинний контракт — `SPEC.MD` MEMORY-002…004, PROMPT-CONTRACT, A6.

**Межі ядра.** Сюди не входять динамічна схема з `enum`/`maxItems` (MEMORY-002-S04), показ повного списку порушень в UI, `scripts/memory_replay.py`, інструкції UA/EN і приймальні прогони. Це план периферії, який пишеться після ревізії ядра.

## Global Constraints

- Журнал лишається `schema_version=2`; `supporting_quotes` — від 0 до 2 непорожніх дослівних фрагментів того самого `source_version_id`, за замовчуванням `[]`.
- Якщо `supporting_quotes` порожній, `claim_id`/`event_id` мають бути байт-у-байт такими самими, як у чинних v2-операцій із тим самим першим доказом.
- v3: `add` ≤ 3 у кожній категорії, загалом ≤ 12 операцій, `evidence_ids` — від 1 до 3 унікальних ID, `character_ids` лише в `character_states.add`.
- Діагностика без відлуння моделі: у повідомленнях і `memory_violations` лише мітка операції й код, без текстів, ID зі значень моделі і повідомлень винятків (MEMORY-004).
- `memory_violations` зберігає до 50 записів і `total`; повідомлення помилки показує кількість і перші три.
- Відповідь v3 на контракт v2 і навпаки дає код `wire_version`; прихованого переходу між parser немає (MEMORY-003-S02).
- Кожна архітектурна зміна оновлює `SPEC.MD` і `docs/verification/traceability.json` у тому самому коміті; `python scripts/check_docs.py` має проходити.
- Мова документації — українська; маркери OpenSpec англійською.
- Тести під Windows запускати з короткого шляху (`subst`), бо довгі тимчасові шляхи дають FileNotFoundError (журнал виконання 07.11).

## Review Focus

1. **Резюме незавершеної спроби після оновлення.** Спроба, контекст якої побудували до оновлення (немає `memory_wire_version`), має розбиратися як v2. Тест у задачі 4: `test_attempt_without_wire_version_parses_as_v2`.
2. **Ручне збереження журналу з `supporting_quotes`.** Автор зберігає JSON, де нова подія має додаткову цитату. Канонізація ID не повинна її губити, а цитата поза прозою — відхилятися. Тести в задачі 1.
3. **Update claim, який у тій самій відповіді закрито в іншій групі** (`update` у `character_states` і `retire` того ж ID). Очікується `target_twice`, а не тихе застосування. Тест у задачі 3: `test_v3_same_claim_update_and_retire_is_target_twice`.
4. **Claim іншої категорії в групі update** (ID стану в `open_threads.update`). Очікується `target_unknown`, а категорія з каталогу не підставляється мовчки. Тест у задачі 3.
5. **Порожня відповідь v3** (усі масиви порожні). Вона валідна й фіксує оброблену прозу без подій, як порожній `operations` у v2. Тест у задачі 3.

---

### Task 1: `supporting_quotes` у журналі

**Files:**
- Modify: `src/storygen/memory/journal.py` (`MemoryEvent`, `_add_event`, `validate_memory_journal`, `normalize_manual_memory`)
- Modify: `SPEC.MD` (MEMORY-003: новий Scenario MEMORY-003-S03; A6: абзац про поле)
- Modify: `docs/verification/traceability.json`
- Test: `tests/memory/test_journal.py`, `tests/memory/test_manual_journal.py`

**Interfaces:**
- Produces: `MemoryEvent.supporting_quotes: list[str]` (Field default `[]`, max 2); `_add_event(category, text, prose_id, quote, occurrence, characters=(), supporting=()) -> MemoryEvent`; `change_event_id(action, claim_id, text, prose_id, quote, supporting=()) -> str` — винесене обчислення `event_id` для update/retire, яким користуються `apply_operations`, `normalize_manual_memory` і задача 3.

- [ ] **Step 1: Write the failing tests**

```python
def test_supporting_quotes_default_keeps_v2_ids():
    a = _add_event('facts', 'Т', 'p1', 'рядок', 0)
    b = _add_event('facts', 'Т', 'p1', 'рядок', 0, supporting=())
    assert a.supporting_quotes == [] and a.claim_id == b.claim_id
    assert a.claim_id == stable_id('mc_', ['facts', 'Т', 'p1', 'рядок', 0])

def test_supporting_quotes_change_ids_and_are_capped():
    a = _add_event('facts', 'Т', 'p1', 'рядок', 0, supporting=('інший',))
    assert a.supporting_quotes == ['інший'] and a.claim_id != _add_event('facts','Т','p1','рядок',0).claim_id
    with pytest.raises(ValidationError):
        MemoryEvent(**{**a.model_dump(), 'supporting_quotes': ['x', 'y', 'z']})

def test_validate_journal_rejects_supporting_quote_not_in_source(): ...
    # журнал із supporting_quotes=['немає у прозі'] → ValueError('Запис пам’яті не має дослівного підтвердження у прозі')

def test_fsck_reports_bad_supporting_quote(): ...
    # storage/memory_checks.py іде через validate_memory_journal → збережена версія з чужою supporting-цитатою дає помилку fsck

def test_old_journal_without_field_loads_unchanged(): ...
    # load_memory(bytes збереженого v2 журналу без поля) → model_dump_json(exclude_defaults=True) == вихідні bytes за змістом
```

У `test_manual_journal.py`:

```python
def test_manual_save_keeps_supporting_quotes(): ...
    # нова add-подія з supporting_quotes=[рядок поточної прози] → у результаті поле збережено, claim_id канонічний з supporting
def test_manual_save_rejects_supporting_quote_outside_prose(): ...
    # → ValueError('Новий запис потребує доказу поточної сцени')
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/memory/test_journal.py tests/memory/test_manual_journal.py -q`
Expected: FAIL (`supporting` / `supporting_quotes` невідомі).

- [ ] **Step 3: Implement**

- `MemoryEvent.supporting_quotes: list[str] = Field(default_factory=list, max_length=2)`. Валідатор `nonblank` перевіряє і їх.
- `_add_event`: хеш `[category, text, prose_id, quote, occurrence]`; якщо `supporting` непорожній, додати `list(supporting)` останнім елементом. `change_event_id` будується так само від `[action, claim_id, text, prose_id, quote]`.
- `validate_memory_journal` і `normalize_manual_memory`: кожен елемент `supporting_quotes` перевіряється тією самою умовою, що й `quote`. У `normalize_manual_memory` ключ дубліката — `(category, text, quote, tuple(supporting_quotes))`, і поле передається в `_add_event`/`change_event_id`.
- Серіалізація журналу не змінюється для подій без поля. Якщо `model_dump_json` пише `"supporting_quotes":[]` і через це змінюються bytes нових версій, використовуйте `exclude_defaults` лише для цього поля через `field_serializer`/`model_serializer`, а не для всієї моделі. Тест `test_old_journal_without_field_loads_unchanged` фіксує вибір.

- [ ] **Step 4: SPEC і traceability**

MEMORY-003 доповнити реченням про адитивне поле. Новий Scenario `MEMORY-003-S03 — Додаткові цитати журналу` (GIVEN журнал без поля / з полем; WHEN читання, ручне збереження, fsck; THEN старий журнал валідний без змін, а кожна додаткова цитата перевіряється як `quote`). Запис у traceability з двома тестами зі Step 1.

- [ ] **Step 5: Run tests and docs check**

Run: `pytest tests/memory -q` і `python scripts/check_docs.py`
Expected: PASS; check_docs — «узгоджені».

- [ ] **Step 6: Commit**

```bash
git add src/storygen/memory/journal.py tests/memory SPEC.MD docs/verification/traceability.json
git commit -m "Add supporting quotes to memory journal events"
```

---

### Task 2: Збирання всіх порушень (v2)

**Files:**
- Create: `src/storygen/memory/violations.py`
- Modify: `src/storygen/memory/journal.py` (`parse_memory_result`, гілка v2 → через колектор перед `apply_operations`)
- Modify: `src/storygen/memory/diagnostics.py` (`memory_error` для `MemoryViolations`)
- Modify: `src/storygen/generation/stages.py:326-328` (зберегти `attempt.context['memory_violations']`)
- Modify: `SPEC.MD` (MEMORY-004 + Scenario MEMORY-004-S04), `docs/verification/traceability.json`
- Test: `tests/memory/test_violations.py` (новий), `tests/memory/test_diagnostics.py`

**Interfaces:**
- Produces:
  - `Violation = NamedTuple('Violation', [('operation', str), ('code', str)])`; мітка операції — `'operations[3]'` для v2, `'character_states.add[0]'` для v3, `'$'` для конверта.
  - `CODES: dict[str, str]` — код → безпечне українське правило. Коди: `schema`, `wire_version`, `evidence_unknown`, `evidence_count`, `add_limit`, `ops_limit`, `target_unknown`, `target_meta`, `target_twice`, `scope_unknown`.
  - `class MemoryViolations(ValueError)` з `violations: list[Violation]` і `payload() -> {'items': [{'operation','code'}…≤50], 'total': int}`.
  - `check_v2(data: dict, previous: MemoryJournal, fragment_ids: set[str], allowed_character_ids: list[str]) -> list[Violation]`.
  - `pydantic_violations(exc: ValidationError, label: Callable[[tuple], str]) -> list[Violation]` — перетворення помилок схеми на `schema` з міткою операції; використовується і в задачі 3.

- [ ] **Step 1: Write the failing tests**

```python
def test_v2_collects_independent_violations():
    data = {'schema_version': 2, 'operations': [
        add('facts', ev='f000001,f000002'),           # → evidence_unknown
        add('facts'), add('facts'), add('facts'),     # 4 add → add_limit (один раз)
        upd(claim=STATE_ID, category='open_threads'), # → target_meta
        upd(claim=STATE_ID), ]}                       # той самий claim → target_twice
    codes = [(v.operation, v.code) for v in check_v2(data, PREV, FRAGS, ALLOWED)]
    assert ('operations[0]', 'evidence_unknown') in codes
    assert ('operations[4]', 'target_meta') in codes
    assert ('$', 'add_limit') in codes and ('$', 'target_twice') in codes

def test_v2_missing_evidence_is_schema_for_that_operation(): ...
    # op без evidence_id → ('operations[i]', 'schema'); інші операції все одно перевірено
def test_v2_fact_target_is_target_unknown(): ...
    # update claim_id факту → target_unknown
def test_payload_caps_at_50_and_keeps_total(): ...
def test_memory_error_shows_count_and_first_three_without_values():
    msg = memory_error(MemoryViolations([Violation(f'operations[{i}]', 'schema') for i in range(5)]))
    assert msg.startswith('5 порушень') and msg.count(';') == 2 and 'f000' not in msg
```

У `test_diagnostics.py` оновити очікування для сценаріїв, де раніше бралося перше повідомлення Pydantic. Нові очікування — формат «N порушень: Операція i: правило; …». Чинні тести MEMORY-004-S02 (невідомий доказ після нормалізації scope) мають пройти з новим текстом.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/memory/test_violations.py tests/memory/test_diagnostics.py -q`
Expected: FAIL (модуля немає).

- [ ] **Step 3: Implement**

`check_v2`:
1. конверт: `dict`, `schema_version == 2`, `operations` — список, інакше `[('$','schema')]` і стоп;
2. кожен елемент — окремо `MemoryOperation.model_validate`; помилка дає `schema` з міткою цієї операції, і далі цей елемент не перевіряється;
3. для валідних: `evidence_id ∉ fragment_ids` → `evidence_unknown`; scope add поза `allowed` → `scope_unknown`; update/retire — claim неактивний або незмінної категорії → `target_unknown`, а категорія/scope ≠ активному claim → `target_meta`;
4. агрегати по всіх елементах-словниках: >12 операцій → `ops_limit`, >3 add у будь-якій категорії → `add_limit` (одна на відповідь), повтор `claim_id` серед update/retire → `target_twice`.

Нормалізацію зайвого scope (MEMORY-004) виконати до колектора, як зараз. У `parse_memory_result` v2: якщо `check_v2` повернув непорожній список → `raise MemoryViolations(...)`, інакше чинний `apply_operations`. Legacy-шлях `MemoryDelta` без `schema_version` і `snapshot` не змінюються.

`stages.py` (гілка `stage=='memory'` у `except ValueError`): якщо `isinstance(exc, MemoryViolations)` → `attempt.context['memory_violations'] = exc.payload()`. Текст `attempt.error` будується як зараз через `memory_error`.

- [ ] **Step 4: SPEC і traceability**

MEMORY-004: абзац про колекцію порушень (мітки, коди, 50/total, перші три в повідомленні, без значень). Scenario `MEMORY-004-S04 — Кілька незалежних порушень` (GIVEN відповідь із невідомим доказом, перевищенням add і повтором claim; WHEN перевірка; THEN пам’ять не публікується, спроба містить усі три коди з мітками, повідомлення — кількість і перші три, без текстів). Traceability → `test_v2_collects_independent_violations`, `test_memory_error_shows_count_and_first_three_without_values`.

- [ ] **Step 5: Run tests**

Run: `pytest tests/memory tests/generation/test_memory_v2_protocol.py tests/generation/test_evidence_protocols.py -q` і `python scripts/check_docs.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/storygen/memory src/storygen/generation/stages.py tests/memory SPEC.MD docs/verification/traceability.json
git commit -m "Report all memory operation violations at once"
```

---

### Task 3: Розбір і переклад wire v3

**Files:**
- Create: `src/storygen/memory/wire_v3.py`
- Modify: `src/storygen/memory/journal.py` (`parse_memory_result(..., wire_version: int = 2)`)
- Modify: `SPEC.MD` (MEMORY-002 + Scenario MEMORY-002-S02, MEMORY-002-S03), `docs/verification/traceability.json`
- Test: `tests/memory/test_wire_v3.py` (новий)

**Interfaces:**
- Consumes: `_add_event(..., supporting=)`, `change_event_id(...)` (задача 1); `Violation`, `MemoryViolations`, `pydantic_violations`, коди (задача 2).
- Produces:
  - Pydantic-моделі (лише структура, без лімітів кількості, `extra='forbid'` через `DomainModel`): `WireAdd(text: str, evidence_ids: list[str])`, `WireStateAdd(WireAdd)` + `character_ids: list[str]`, `WireChange(claim_id: str, text: str, evidence_ids: list[str])`, `AddOnlyGroup(add: list[WireAdd])`, `StateGroup(add: list[WireStateAdd], update: list[WireChange], retire: list[WireChange])`, `ThreadGroup(add: list[WireAdd], update: list[WireChange], retire: list[WireChange])`, `MemoryWireV3(schema_version: Literal[3], facts: AddOnlyGroup, character_states: StateGroup, open_threads: ThreadGroup, timeline: AddOnlyGroup)`. Усі поля обов’язкові, без default. `text` має `min_length=1`.
  - `check_v3(data: dict, previous, fragment_ids, allowed_character_ids) -> list[Violation]`.
  - `wire_v3_events(wire: MemoryWireV3, previous, prose_id, prose) -> list[MemoryEvent]` (викликається лише після порожнього `check_v3`).
  - `parse_memory_result(raw, previous, prose_id, prose, mode, allowed_character_ids, *, warnings=None, wire_version=2)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_v3_translates_to_v2_journal_with_stable_ids():
    raw = v3(states_add=[sadd('Т', ['f000002'], chars=['c1'])], threads_update=[chg(THREAD_ID, 'Нове', ['f000003'])])
    j = parse_memory_result(raw, PREV, 'p2', PROSE, 'evidence_delta', ['c1'], wire_version=3)
    v2 = parse_memory_result(v2_equivalent(raw), PREV, 'p2', PROSE, 'evidence_delta', ['c1'])
    assert j == v2   # однаковий журнал, коли доказ один

def test_v3_update_takes_category_and_scope_from_catalog(): ...
    # update STATE_ID зі scope ['c1'] → подія має scope ['c1'], хоч у wire його немає
def test_v3_multiple_evidence_become_supporting_quotes(): ...
    # evidence_ids [f1, f5, f9] → quote=рядок f1, supporting_quotes=[f5, f9] у порядку переліку
def test_v3_violations(): ...
    # 4 facts.add → ('facts.add', 'add_limit'); evidence_ids [] або 4 ID або дубль → 'evidence_count';
    # невідомий ID → 'evidence_unknown'; 4×3 add + 1 update → ('$','ops_limit')
def test_v3_same_claim_update_and_retire_is_target_twice(): ...
def test_v3_claim_from_other_category_is_target_unknown(): ...
def test_v3_fact_claim_cannot_be_targeted(): ...   # facts не має update у схемі → schema
def test_v3_empty_response_records_prose(): ...    # усі масиви порожні → journal.source_prose_ids+=[p2], подій 0
def test_wire_version_mismatch():
    with pytest.raises(MemoryViolations) as e:
        parse_memory_result(v2_raw, PREV, 'p2', PROSE, 'evidence_delta', [], wire_version=3)
    assert e.value.violations == [Violation('$', 'wire_version')]
    # і навпаки: v3_raw з wire_version=2 → той самий код
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/memory/test_wire_v3.py -q`
Expected: FAIL (модуля немає).

- [ ] **Step 3: Implement**

`check_v3`:
1. конверт — `dict`. Якщо `schema_version` дорівнює 2 або є `operations` → `wire_version`. `MemoryWireV3.model_validate` при помилці дає `pydantic_violations` з мітками `<категорія>.<дія>[i]` і стоп;
2. по кожному елементу: `evidence_ids` порожній, довший за 3 або з дублем → `evidence_count`; ID поза фрагментами → `evidence_unknown`; scope `character_states.add` поза дозволеними → `scope_unknown`; `claim_id` у групі не є активним claim саме цієї категорії → `target_unknown`;
3. агрегати: `add` > 3 у категорії → `('<категорія>.add', 'add_limit')`; сума всіх елементів > 12 → `('$','ops_limit')`; повтор `claim_id` серед усіх update/retire обох груп → `('$','target_twice')`.

`wire_v3_events`: обхід категорій у порядку `CATEGORIES`, у групі `add` → `update` → `retire`, у масиві — порядок відповіді. Для add — `_add_event(category, text, prose_id, frag[ids[0]], occurrence, chars, supporting=[frag[i] for i in ids[1:]])`, ключ дубліката `(category, text, quote, tuple(supporting))`. Для update/retire `category`/`character_ids` беруться з `replay_memory(previous)[claim_id]`, `event_id` — через `change_event_id`. Далі `_extend(previous, prose_id, events)`.

`parse_memory_result`: після `unwrap`/`decode`, коли `mode=='evidence_delta'`: при `wire_version==3` → `check_v3` → `MemoryViolations` або `_extend(... wire_v3_events ...)`. При `wire_version==2`: якщо `schema_version==3` → `MemoryViolations([('$','wire_version')])`, інакше чинний шлях із задачі 2. Нормалізація scope MEMORY-004 стосується лише v2: у v3 немає `character_ids` поза `character_states.add`, тому зайве поле дає `schema`. Попередження про обгортку — як зараз.

- [ ] **Step 4: SPEC і traceability**

MEMORY-002: абзац про wire v3 (структура, межі, `evidence_ids`, серверна категорія/scope, порядок перекладу, ідентичність ID для одного доказу). Scenario `MEMORY-002-S02 — Переклад v3 у журнал` і `MEMORY-002-S03 — Кілька доказів`. Traceability → `test_v3_translates_to_v2_journal_with_stable_ids`, `test_v3_multiple_evidence_become_supporting_quotes`.

- [ ] **Step 5: Run tests**

Run: `pytest tests/memory -q` і `python scripts/check_docs.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/storygen/memory tests/memory SPEC.MD docs/verification/traceability.json
git commit -m "Parse and translate memory wire v3"
```

---

### Task 4: Контракт промпту v3, каталог v3 і вибір wire

**Files:**
- Create: `src/storygen/generation/resources/memory_delta_uk_v3.txt`
- Modify: `src/storygen/prompt_contracts.py` (`expected_contract`, `validate_role_prompt`, нова `memory_wire_version`)
- Modify: `src/storygen/generation/prompts.py` (`role_prompt` → v3 файл)
- Modify: `src/storygen/memory/projection.py` (нова `memory_catalog_v3`)
- Modify: `src/storygen/generation/context.py:150-158` (каталог і `fragments['memory_wire_version']`)
- Modify: `src/storygen/generation/stages.py:240` (передати `wire_version`)
- Modify: `src/storygen/providers/requests.py:67` (статична схема `MemoryWireV3` при wire 3)
- Modify: `src/storygen/web/static/settings.js:59` (очікуваний контракт `/3`, збережений `/2` для пам’яті показується як сумісний)
- Modify: `SPEC.MD` (PROMPT-CONTRACT + Scenario PROMPT-CONTRACT-S02; A6 — каталог v3), `docs/verification/traceability.json`
- Test: `tests/generation/test_prompt_contracts.py`, `tests/memory/test_projection.py`, `tests/generation/test_memory_v2_protocol.py`, а також stage-level тести з v2-відповідями від стандартного промпту (див. Step 6)

**Interfaces:**
- Consumes: `parse_memory_result(..., wire_version=)`, `MemoryWireV3` (задача 3).
- Produces: `expected_contract('memory', settings)` → `memory/evidence_delta/3`; `memory_wire_version(ref: VersionRef | None) -> int` (3 для стандартного промпту, `ref.prompt_contract.schema_version` для власного); `memory_catalog_v3(journal) -> str`; ключ `fragments['memory_wire_version']` (`'2'`/`'3'`) у контексті спроби.

- [ ] **Step 1: Write the failing tests**

```python
def test_builtin_memory_prompt_is_v3(): ...
    # expected_contract('memory', evidence_delta) == PromptContract(stage='memory', mode='evidence_delta', schema_version=3)
def test_custom_v2_memory_prompt_stays_valid_and_selects_v2(): ...
    # власний промпт із контрактом memory/evidence_delta/2 → validate_role_prompt повертає ref; memory_wire_version(ref)==2
def test_custom_v1_or_other_mode_still_rejected(): ...
def test_catalog_v3_hides_immutable_ids():
    text = memory_catalog_v3(JOURNAL_WITH_FACT_AND_STATE)
    assert FACT_CLAIM_ID not in text and STATE_CLAIM_ID in text and 'Текст факту' in text
def test_context_records_wire_version_and_catalog_metrics(): ...
    # build_context для memory → fragments['memory_wire_version']=='3', memory_metrics['projection_version']=='memory-catalog-v3'
def test_attempt_without_wire_version_parses_as_v2(): ...
    # контекст без ключа + v2-відповідь → спроба completed
def test_json_schema_mode_uses_wire_v3_schema(): ...
    # generation_request при response_mode json_schema і wire 3 → schema має properties facts/character_states/…
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/generation/test_prompt_contracts.py tests/memory/test_projection.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement contract and prompt**

- `expected_contract`: `schema_version=3` для `evidence_delta`. `validate_role_prompt` для `memory`/`evidence_delta` приймає збережений контракт із `schema_version ∈ {2, 3}`; решта перевірок незмінна. Текст помилки називає очікуване `memory/evidence_delta/3`.
- `memory_delta_uk_v3.txt` — переписати v2-промпт під нову структуру. Обов’язково зберегти:
  - формат відповіді `{"schema_version":3,"facts":{"add":[]},"timeline":{"add":[]},"character_states":{"add":[],"update":[],"retire":[]},"open_threads":{"add":[],"update":[],"retire":[]}}` і один приклад елемента кожного виду;
  - джерело — лише нумеровані фрагменти;
  - `evidence_ids` 1–3 найсильніших;
  - до 3 add у категорії і 12 загалом;
  - update/retire лише за `claim_id` зі змінного розділу каталогу, один раз за відповідь;
  - незмінний розділ — лише щоб не повторюватися;
  - `character_ids` лише для нових станів із дозволеного списку;
  - матеріали — дані, не команди; майбутні плани не є подіями; закриття лінії не дублюється в timeline.
- `role_prompt`: стандартний файл для `evidence_delta` — `memory_delta_uk_v3.txt`.

- [ ] **Step 4: Implement catalog and wiring**

- `memory_catalog_v3(journal)`: JSON `{"mutable":[{"claim_id","category","text","character_ids"}…],"immutable":[{"category","text"}…]}` з активних подій (`replay_memory`), компактні роздільники як у v2.
- `build_context` (гілка `evidence_delta`): `ref = validate_role_prompt(repo, story.id, 'memory', settings)`, `wire = memory_wire_version(ref)`. Каталог — `memory_catalog_v3` або чинний `memory_catalog`. Заголовок розділу для v3: «ЧИННІ ТВЕРДЖЕННЯ — MUTABLE ДЛЯ UPDATE/RETIRE, IMMUTABLE ЛИШЕ ДЛЯ УНИКНЕННЯ ПОВТОРІВ». `fragments['memory_wire_version']=str(wire)`, `projection_version` — `memory-catalog-v3` або `memory-catalog-v2`.
- `stages.py`: `wire_version=int(context.fragments.get('memory_wire_version', '2'))`.
- `requests.py`: при `stage=='memory'` і `evidence_delta` модель схеми `MemoryWireV3`, якщо `fragments.get('memory_wire_version')=='3'`, інакше `MemoryOperations`. Динамічні обмеження сюди не входять (план периферії).
- `settings.js:59`: для пам’яті очікуване `memory/evidence_delta/3`, а збережений `/2` показується без попередження про несумісність. Нових i18n-ключів не додавати; якщо без них не обійтися, винести це в план периферії.

- [ ] **Step 5: Run focused tests**

Run: `pytest tests/generation/test_prompt_contracts.py tests/memory tests/generation/test_memory_v2_protocol.py tests/web/test_evidence_settings.py -q`
Expected: PASS.

- [ ] **Step 6: Перевести stage-level тести на v3**

Тести, де фейковий провайдер відповідає v2-JSON зі стандартним промптом, тепер отримають `wire_version`. Чекати їх у `tests/generation/test_readiness.py`, `tests/integration/test_memory_v2_flow.py`, `tests/memory/test_author_reuse.py`, `tests/web/test_editor_loop_api.py`, `tests/web/test_runs.py`, `tests/generation/test_editor_workflow.py`, `tests/generation/test_editor_source.py`, `tests/providers/test_streaming.py`. Для кожного:
- якщо тест про v2-протокол — призначити власний промпт `memory/evidence_delta/2` через чинний helper налаштувань;
- інакше замінити відповідь на v3 через спільний helper `tests/memory/wire_helpers.py::v3_response(**groups) -> str`.

Очікування журналу не змінюються, якщо доказ один (Global Constraints).

Run: `pytest tests/memory tests/generation tests/web tests/integration tests/providers -q`
Expected: PASS.

- [ ] **Step 7: SPEC і traceability**

PROMPT-CONTRACT: перелік контрактів — `memory/evidence_delta/3` стандартний, `/2` сумісний для власних промптів, wire визначає контракт. Scenario `PROMPT-CONTRACT-S02 — Власний промпт пам’яті v2` (GIVEN власний промпт `/2`; WHEN запуск; THEN каталог v2, схема v2, parser v2, а відповідь v3 відхиляється кодом `wire_version`). A6: каталог v3 і `memory_wire_version` у fragments. Traceability → `test_custom_v2_memory_prompt_stays_valid_and_selects_v2`, `test_wire_version_mismatch`.

- [ ] **Step 8: Gate і commit**

Run: `python scripts/check_docs.py`, потім `python scripts/verify.py` (з короткого шляху), і записати результат у `docs/STATUS.md`.
Expected: check_docs «узгоджені»; verify — без failed.

```bash
git add src tests SPEC.MD docs/verification/traceability.json docs/STATUS.md
git commit -m "Select memory wire v3 by prompt contract"
```

---

## Після ядра

1. Ревізія всієї гілки ядра (фінальний whole-branch review), записати висновки в журнал виконання.
2. Окремий план периферії з урахуванням цих висновків:
   - динамічна схема з `enum`/`maxItems` (MEMORY-002-S04) і її внесок у бюджет токенів;
   - показ повного списку порушень у деталях спроби;
   - `scripts/memory_replay.py`;
   - інструкції UA/EN і текст режиму в налаштуваннях;
   - приймальні кроки 1–2 спеки, з окремою згодою на витрати прогону.
