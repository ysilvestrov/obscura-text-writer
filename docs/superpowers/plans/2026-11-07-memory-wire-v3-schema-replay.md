# Пам’ять wire v3 — периферія, пакет 1: динамічна схема й офлайн-повтор

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** У режимі `json_schema` Venice примушує ліміти й допустимі ID пам’яті v3, а локальна команда рахує, скільки збережених відповідей проходить перевірку, без звернень до моделі.

**Architecture:** `build_context` фіксує межі схеми (ID фрагментів, змінні claim за категоріями, дозволені персонажі) у `fragments['memory_schema_bounds']`. `generation_request` будує з них динамічну схему через нову чисту функцію `memory_wire_v3_schema`. Офлайн-повтор — чистий модуль `memory/replay.py` і тонкий CLI `scripts/memory_replay.py`, що відкриває базу read-only.

**Tech Stack:** Python 3, Pydantic v2, pytest, SQLite (`mode=ro`).

**Spec:** `docs/specs/2026-11/memory-wire-v3.md` (затверджено 2026-11-07): розділи «Динамічна схема», «Команда офлайн-повтору», «Приймання» 1. План ядра: `docs/superpowers/plans/2026-11-07-memory-wire-v3-core.md`. Висновки ревізії ядра й відкладене — `docs/superpowers/plans/2026-10-20-remediation-progress.md`, запис 07.11 «Ядро пам’яті wire v3».

**Межі пакета.** Повний список порушень у UI, показ `supporting_quotes` у таблиці пам’яті, явний перехід власного промпту `/2` → `/3`, інструкції UA/EN і назва режиму — пакет 2.

## Global Constraints

- Ключі схеми лише з перевіреного набору: `type`, `properties`, `required`, `additionalProperties`, `items`, `enum`, `minItems`, `maxItems`. `uniqueItems` Venice відхиляє (проба П5 нижче), `minLength` не використовувати. Унікальність доказів, непорожній текст, ліміт 12 операцій і `target_twice` перевіряє лише сервер.
- `evidence_ids`: `minItems: 1`, `maxItems: 3`, `items.enum` — ID фрагментів поточної прози.
- `add` кожної категорії: `maxItems: 3`.
- `claim_id` у `update`/`retire` групи: `enum` активних claim саме цієї категорії. Якщо їх немає — `maxItems: 0` і без `enum` (порожній `enum` недопустимий).
- `character_ids` у `character_states.add`: `items.enum` дозволених персонажів сцени. Якщо їх немає — `maxItems: 0` без `enum`.
- Динамічна схема — лише для `response_mode=json_schema` і `memory_wire_version=='3'`. Без `memory_schema_bounds` (старі спроби) — чинна статична схема `strict_schema(MemoryWireV3)`. Для wire 2 — `MemoryOperations`, як зараз.
- Межі беруться з тих самих captured даних, що й перевірка відповіді: та сама проза, той самий `previous_memory`, ті самі дозволені персонажі.
- Офлайн-повтор: лише `mode=ro`, жодної мережі, у виводі лише лічильники й коди. Без текстів, ID claim, ID персонажів, назв творів і шляхів до прози.
- SPEC.MD і `docs/verification/traceability.json` оновлюються в тому самому коміті; `python scripts/check_docs.py` має проходити. Документація українською, маркери OpenSpec англійською.
- Тести під Windows: `--basetemp=C:/tt/<x>` (довгі шляхи).

**П5 (проба 07.11, синтетичний текст).** Venice `qwen-3-8-27b`: `400 Grammar error: Unimplemented keys: ["uniqueItems"]`; `gemma-4-uncensored` зі `uniqueItems`: `500 Inference processing failed`. Без `uniqueItems`: Gemma 2/2 дотрималася `maxItems: 3`, `maxItems: 0` і `enum` для `claim_id` під провокаційним промптом; Qwen 1/2 так само, 1/2 — некоректний JSON (довга порожня відповідь).

## Review Focus

1. **Сцена без змінних claim** (перша сцена твору). Схема має бути валідною: `update`/`retire` з `maxItems: 0` без `enum`. Тест у задачі 1: `test_schema_without_mutable_claims_has_no_empty_enum`.
2. **Сцена без персонажів** — `character_ids` з `maxItems: 0`. Тест у задачі 1.
3. **Спроба, побудована ядром без `memory_schema_bounds`**, у режимі `json_schema` — статична схема без падіння. Тест у задачі 1: `test_request_without_bounds_uses_static_v3_schema`.
4. **Повтор на спробі без `partial` або без прози** — рахується в окремому лічильнику, а не падає. Тест у задачі 2.
5. **Повтор не друкує тексти.** Тест у задачі 2 з маркерами-«секретами» в прозі та відповіді перевіряє, що їх немає у виводі.

---

### Task 1: Динамічна схема wire v3

**Files:**
- Modify: `src/storygen/memory/wire_v3.py` (нова `memory_wire_v3_schema`, нова `schema_bounds`)
- Modify: `src/storygen/generation/context.py:150-161` (записати `fragments['memory_schema_bounds']` для wire 3)
- Modify: `src/storygen/providers/requests.py:60-70` (динамічна схема для wire 3 за наявності меж)
- Modify: `SPEC.MD` (MEMORY-002: абзац про динамічну схему; новий Scenario MEMORY-002-S04; A6 — `memory_schema_bounds`), `docs/verification/traceability.json`
- Test: `tests/memory/test_wire_v3_schema.py` (новий), `tests/generation/test_prompt_contracts.py` (запит)

**Interfaces:**
- Produces:
  - `schema_bounds(previous: MemoryJournal, prose: str, allowed_character_ids: list[str]) -> dict` → `{"fragment_ids": [...], "mutable": {"character_states": [...], "open_threads": [...]}, "character_ids": [...]}`. Порядок — як у `fragment_text`, у `replay_memory` і в списку сцени.
  - `memory_wire_v3_schema(bounds: dict) -> dict` — повна JSON Schema відповіді v3 із `schema_version: {"type":"integer","enum":[3]}`, групами, обов’язковими ключами та `additionalProperties: false` на кожному об’єкті.
  - `fragments['memory_schema_bounds']` — `json.dumps(bounds, ensure_ascii=False)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_schema_limits_and_enums():
    s = memory_wire_v3_schema({'fragment_ids': ['f000001', 'f000002'],
        'mutable': {'character_states': ['mc_s'], 'open_threads': ['mc_t']}, 'character_ids': ['c1']})
    facts_add = s['properties']['facts']['properties']['add']
    assert facts_add['maxItems'] == 3
    ev = facts_add['items']['properties']['evidence_ids']
    assert ev == {'type': 'array', 'minItems': 1, 'maxItems': 3, 'items': {'type': 'string', 'enum': ['f000001', 'f000002']}}
    upd = s['properties']['character_states']['properties']['update']['items']['properties']['claim_id']
    assert upd['enum'] == ['mc_s']
    assert s['properties']['open_threads']['properties']['retire']['items']['properties']['claim_id']['enum'] == ['mc_t']
    assert 'update' not in s['properties']['facts']['properties']

def test_schema_uses_only_supported_keywords():
    allowed = {'type', 'properties', 'required', 'additionalProperties', 'items', 'enum', 'minItems', 'maxItems'}
    # обхід усіх вузлів схеми: ключі кожного dict-вузла (крім імен у properties) ⊆ allowed; uniqueItems/minLength відсутні

def test_schema_without_mutable_claims_has_no_empty_enum(): ...
    # mutable порожні → update/retire мають maxItems 0, в них немає 'enum' ніде; схема без порожніх enum
def test_schema_without_characters(): ...   # character_ids → maxItems 0, без enum
def test_every_object_is_closed_and_fully_required(): ...
    # кожен вузол з properties має additionalProperties False і required == list(properties)
def test_valid_answer_matches_schema_shape(): ...
    # v3_response(...) з tests/memory/wire_helpers.py проходить jsonschema-подібну ручну перевірку
    # або MemoryWireV3.model_validate — схема й модель описують ту саму структуру (ключі груп і полів однакові)
def test_schema_bounds_from_captured_inputs(): ...
    # schema_bounds(журнал із фактом, станом, лінією; проза з 3 рядків; ['c1']) → fragment_ids f000001..f000003,
    # mutable містить лише ID стану й лінії, факт відсутній
```

У `tests/generation/test_prompt_contracts.py`:

```python
def test_json_schema_mode_uses_dynamic_v3_schema(): ...
    # build_context для memory з response_mode json_schema → api_request['response_format']['json_schema']['schema']
    # має enum фрагментів поточної прози й fragments['memory_schema_bounds'] записано
def test_request_without_bounds_uses_static_v3_schema(): ...
    # generation_request з fragments {'memory_wire_version':'3'} без bounds → strict_schema(MemoryWireV3)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/memory/test_wire_v3_schema.py tests/generation/test_prompt_contracts.py -q --basetemp=C:/tt/s1`
Expected: FAIL (`memory_wire_v3_schema` невідома).

- [ ] **Step 3: Implement**

- `schema_bounds` використовує `fragment_text(prose)` і `replay_memory(previous)`. Змінні категорії — `character_states`, `open_threads`.
- `memory_wire_v3_schema` будує схему вручну за Global Constraints. Елемент `add`: `text` (`{"type":"string"}`) і `evidence_ids`; для станів ще `character_ids`. Елемент `update`/`retire`: `claim_id`, `text`, `evidence_ids`. Рядки — `{"type":"string"}` без інших ключів.
- `build_context`: для wire 3 додати `memory_schema_bounds` (з тієї самої прози, `past`, `scene.character_ids`). Для wire 2 ключ не пишеться.
- `generation_request`: при `stage=='memory'`, `evidence_delta`, `memory_wire_version=='3'` і наявних `memory_schema_bounds` → `memory_wire_v3_schema(json.loads(...))`, інакше чинна логіка. Оцінка токенів уже рахує `response_format`, бо бере `api_request`; окремих змін не потрібно, але тест `test_json_schema_mode_uses_dynamic_v3_schema` перевіряє, що схема є в `api_request`.

- [ ] **Step 4: SPEC і traceability**

MEMORY-002: абзац — у `json_schema` для wire v3 запит містить схему з `enum` фрагментів, змінних claim за категоріями і дозволених персонажів, `maxItems` 3 для add і 3 для доказів; `maxItems: 0` замість порожнього `enum`; без `uniqueItems`/`minLength`; серверна перевірка лишається обов’язковою. Scenario `MEMORY-002-S04 — Динамічна схема` (GIVEN wire v3 і `json_schema`; WHEN будується запит; THEN схема обмежує add, докази, `claim_id` і scope за captured даними; AND спроба без меж використовує статичну схему). A6: `memory_schema_bounds` у fragments. Traceability → `test_schema_limits_and_enums`, `test_json_schema_mode_uses_dynamic_v3_schema`.

- [ ] **Step 5: Run tests**

Run: `pytest tests/memory tests/generation tests/providers -q --basetemp=C:/tt/s1` і `python scripts/check_docs.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/storygen tests SPEC.MD docs/verification/traceability.json
git commit -m "Constrain memory wire v3 with a per-request JSON schema"
```

---

### Task 2: Офлайн-повтор збережених відповідей

**Files:**
- Create: `src/storygen/memory/replay.py`
- Create: `scripts/memory_replay.py`
- Modify: `SPEC.MD` (A6: абзац про команду), `docs/verification/traceability.json` (якщо вводиться Scenario; інакше без змін)
- Test: `tests/memory/test_replay.py` (новий)

**Interfaces:**
- Consumes: `parse_memory_result(..., wire_version=)`, `check_v2`, `check_v3`, `MemoryViolations`, `load_memory`, `fragment_text`.
- Produces:
  - `replay_response(raw: str, fragments: dict, prose_id: str, prose: str) -> dict` → `{"wire": 2|3, "as_is": "pass"|"fail"|"json", "as_is_codes": [code…], "as_v3": "pass"|"fail"|"json"|None, "as_v3_codes": [code…]}`. `as_v3` заповнюється лише для wire 2.
  - `v2_as_v3(data: dict) -> dict` — переклад v2-відповіді у v3. Операції групуються за категорією. `evidence_id` розбивається за `[,;\s]+` у `evidence_ids`. Для update/retire відкидаються `category` і `character_ids`, а дія незмінної категорії потрапляє в ключ `update`/`retire` її групи (і стає порушенням схеми). `character_ids` лишаються тільки для `character_states.add`.
  - `summarize(rows: list[dict]) -> dict` — лічильники: кількість спроб за wire, pass/fail/json для `as_is` і `as_v3`, `Counter` кодів, кількість пропущених (`no_raw`, `no_prose`, `no_bounds`).
  - CLI: `python scripts/memory_replay.py [--db data/storygen.sqlite3] [--data data] [--story <id>]` друкує `summarize` як відсортований JSON.

- [ ] **Step 1: Write the failing tests**

```python
def test_v2_as_v3_splits_evidence_and_drops_meta():
    v3 = v2_as_v3({'schema_version': 2, 'operations': [
        {'action': 'add', 'category': 'facts', 'claim_id': None, 'text': 'Т', 'character_ids': [], 'evidence_id': 'f000001, f000002'},
        {'action': 'update', 'category': 'open_threads', 'claim_id': 'mc_t', 'text': 'Н', 'character_ids': ['c1'], 'evidence_id': 'f000003'}]})
    assert v3['facts']['add'] == [{'text': 'Т', 'evidence_ids': ['f000001', 'f000002']}]
    assert v3['open_threads']['update'] == [{'claim_id': 'mc_t', 'text': 'Н', 'evidence_ids': ['f000003']}]
    assert v3['schema_version'] == 3 and v3['timeline'] == {'add': []}

def test_replay_counts_multi_evidence_as_fixed_by_v3(): ...
    # v2-відповідь з 'f000001,f000002' → as_is fail з evidence_unknown, as_v3 pass
def test_replay_v3_response_uses_wire_from_fragments(): ...
    # fragments memory_wire_version '3' → wire 3, as_v3 None
def test_replay_json_error_is_counted(): ...
def test_summarize_and_cli_print_no_texts(tmp_path): ...
    # мінімальна база (через наявні workspace-хелпери тестів пам’яті) з однією невдалою спробою;
    # проза й відповідь містять маркери 'СЕКРЕТ-ПРОЗИ', 'СЕКРЕТ-ВІДПОВІДІ'; CLI-вивід (subprocess або main(argv)) не містить маркерів,
    # ID claim і ID персонажів; лічильники відповідають очікуваним
def test_attempt_without_partial_is_skipped_not_crash(): ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/memory/test_replay.py -q --basetemp=C:/tt/s2`
Expected: FAIL (модуля немає).

- [ ] **Step 3: Implement**

- `replay_response`:
  1. зняти обгортку й розібрати JSON як `parse_memory_result`. Помилка — `json`;
  2. `as_is` — `parse_memory_result(raw, load_memory(fragments['previous_memory']), prose_id, prose, 'evidence_delta', allowed, wire_version=wire)`. `MemoryViolations` → `fail` з кодами, інший `ValueError` → `fail` з кодом `other`;
  3. для wire 2 — те саме для `json.dumps(v2_as_v3(data))` з `wire_version=3`.
- CLI відкриває `sqlite3.connect(f"file:{db}?mode=ro", uri=True)` і бере спроби `stage=='memory'` з `memory_mode=='evidence_delta'` у станах `completed`/`failed`. Прозу знаходить як `expected_source_prose_ids[-1]` у таблиці `versions` (`relative_path` відносно `--data`; якщо це тека, файл `<id>.txt`), `partial` — `--data / partial_path`. Нічого не пише. `--story` фільтрує за `story_id`.

- [ ] **Step 4: SPEC**

A6: абзац про `scripts/memory_replay.py` — read-only, без мережі, лише лічильники; два варіанти для v2-відповідей; результат — показник формату, а не семантики. Scenario не потрібен (засіб розробника, не поведінка застосунку); traceability не змінюється.

- [ ] **Step 5: Run tests**

Run: `pytest tests/memory -q --basetemp=C:/tt/s2` і `python scripts/check_docs.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/storygen/memory/replay.py scripts/memory_replay.py tests/memory/test_replay.py SPEC.MD
git commit -m "Add offline replay of stored memory responses"
```

---

## Після пакета

1. Ревізія гілки пакета, крос-рев'ю PR, PR зі стеком на `claude/memory-wire-v3`.
2. Приймання 1: `python scripts/memory_replay.py` на робочій базі (read-only) — `as_v3` має дати ≥ 9 додаткових pass порівняно з `as_is`.
3. Приймання 2 (погоджено власником 07.11, бюджет ≈ $0,05): ≥ 10 сцен, Gemma 4, wire v3, `json_schema`, temperature 0,7, на копії бази; частка валідних ≥ 90%; огляд семантики 3 сцен власником.
