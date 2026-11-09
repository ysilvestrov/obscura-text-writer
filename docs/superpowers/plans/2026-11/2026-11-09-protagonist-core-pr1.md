# Ядро стану протагоніста — PR 1 (модель і протокол) — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Мета:** етап memory відповідає wire v4 з обов'язковими рішеннями за кожним слотом ядра протагоніста й кожною активною лінією. Сервер заміщує слоти, закриває лінії з фактом-розв'язкою, а письменник бачить секцію «ЯДРО СТАНУ».

**Архітектура:** журнал пам'яті v3 отримує необов'язкові поля події (`slot`, `source_kind`, `evidence_version_id`, `resolves_claim_id`, необов'язкову `quote`). Новий модуль `memory/wire_v4.py` перевіряє відповідь і перекладає її в події журналу, а `memory/core.py` тримає реєстр слотів і відстежуваних персонажів. `memory/story_time.py` виводить перехід дня з рядка «Початок:». Контракт промпту пам'яті стає `memory/evidence_delta/4`, режим `snapshot` для нових викликів зникає.

**Стек:** Python 3, pydantic v2, FastAPI, pytest; JS налаштувань без збирача.

**Специфікація:** `docs/superpowers/specs/2026-11/2026-11-09-protagonist-core-memory-design.md` (затверджено 2026-11-09). Панель підтвердження й API `core-review` — PR 2, окремий план після рев'ю цього ядра.

## Global Constraints

- **Робоча база.** `data/storygen.sqlite3` не змінювати. Тести працюють лише на `tmp_path`. Тексти твору й моделі не друкувати.
- **Платні виклики.** Жодних викликів провайдера, лише фейкові відповіді в тестах.
- **Реєстр слотів**, точно в такому порядку:

  | name | Мітка UA | Мітка EN | Застаріває після переходу дня |
  |---|---|---|---|
  | `clothing` | одяг | clothing | так |
  | `carried` | при собі | carried | так |
  | `location` | місце | location | ні |
  | `body` | тілесний стан | body | так |
  | `company` | з ким | company | ні |

  Версія реєстру — `core-slots-v1`.
- **Сумісність журналів.**
  - Журнали `schema_version` 2 (і legacy-знімки) читаються без змін.
  - Нові поля не серіалізуються за типових значень. Тож подія без них побайтово збігається з v2-формою, з тими самими `claim_id` і `event_id`.
  - Журнал, створений відповіддю v4, має `schema_version: 3`.
- **Правила журналу без послаблень:**
  - `source_version_id` нової події дорівнює прозі поточної сцени;
  - порядок джерел не спадає (`journal.py:99-101`);
  - нові події не посилаються на прозу попередніх сцен (`journal.py:291`).
- **Ключові слова JSON-схеми wire v4** — лише `type`, `properties`, `required`, `additionalProperties`, `items`, `enum`, `minItems`, `maxItems`. Без `anyOf`, `oneOf` і `uniqueItems`.
- **Ліміти wire v4.** До 3 `add` на категорію і до 12 `add` сумарно. Рішення в `core` і `threads` не входять у жоден ліміт.
- **Мова.** SPEC і документація українською, структурні маркери OpenSpec англійською. Кожен новий Scenario має сталий ID і запис у `docs/verification/traceability.json`. Перевірка — `python scripts/check_docs.py`.
- **Запуск тестів:**
  - Python: `C:/Projects/text-generator/.venv/Scripts/python.exe`;
  - `--basetemp` під `C:/Users/yuriy/AppData/Local/Temp/pytest-core-<task>`;
  - `check_docs` з `PYTHONIOENCODING=utf-8`.

## Review Focus

1. **Повторна перегенерація пам'яті старого твору.** Попередній журнал v2 без ядра → відповідь v4 без значень у слотах (`unchanged` усюди) → журнал v3 без подій ядра і без помилок. Тест у Task 3: `test_v4_on_v2_previous_without_core`.
2. **Протагоніста немає у сцені.** `tracked` у межах порожній, `core` — порожній об'єкт, ядро переходить без змін. Перехід дня рахується від останньої сцени з ним. Тести в Task 2 (`test_day_change_skips_scenes_without_character`) і Task 3 (`test_core_absent_character_has_no_keys`).
3. **`unknown` для запису автора без цитати.** Атмосферна подія теж `author` без цитати, і валідатор журналу її приймає. Тест у Task 3: `test_unknown_of_author_unquoted_slot`.
4. **Прихована лінія закривається.** Факт-розв'язка не потрапляє ні до письменника, ні в таблицю перенесення як увімкнений. Тест у Task 5: `test_hidden_thread_resolution_stays_hidden`.
5. **Зміна позначки протагоніста без зміни прози.** Пам'ять сцени стає застарілою через селектор `tracked_characters`. Тест у Task 2: `test_tracked_change_makes_memory_stale`.

---

### Task 1: Журнал v3 і реєстр слотів

**Файли:**
- Створити: `src/storygen/memory/core.py`
- Змінити: `src/storygen/memory/journal.py` (`MemoryEvent`, `MemoryJournal`, `_add_event`, `change_event_id`, `_change_event`, `_extend`, `replay_memory`, `validate_memory_journal`, `normalize_manual_memory`)
- Тести: `tests/memory/test_core_journal.py`

**Інтерфейси:**
- Створює:
  - `core.SlotDef(name: str, label_uk: str, label_en: str, expires_on_day_change: bool)` — frozen dataclass;
  - `core.SLOTS: tuple[SlotDef, ...]`;
  - `core.SLOT_REGISTRY_VERSION = 'core-slots-v1'`;
  - `core.slot_def(name) -> SlotDef` (`KeyError` для невідомого);
  - `core.tracked_characters(cards, scenes) -> list[str]`. Повертає `[hero]` через `characters.acquaintance.protagonist(cards, active_scenes)` або `[]`.
- `MemoryEvent` отримує поля:
  - `slot: str | None = None`;
  - `source_kind: Literal['prose','author'] = 'prose'`;
  - `evidence_version_id: str | None = None`;
  - `resolves_claim_id: str | None = None`;
  - `quote: str | None` (без значення за замовчуванням: поле обов'язкове, але може бути `None`).
- `MemoryJournal.schema_version: Literal[2, 3] = 2`.
- `_add_event(category, text, prose_id, quote, occurrence, characters=(), supporting=(), *, slot=None, source_kind='prose', evidence_version_id=None, resolves_claim_id=None)`.
- `change_event_id(...)` і `_change_event(...)` отримують ті самі ключові параметри.
- `_extend(previous, prose_id, events, schema_version=None)`. `None` залишає `previous.schema_version`, якщо жодна нова подія не має нестандартних полів, інакше ставить 3.

**Ruling, записати в журнал виконання.** Специфікація зв'язує факт-розв'язку з лінією словами «за тим самим джерелом». Тут це явне поле `resolves_claim_id`, бо збіг тексту й цитати не є надійним ключем. Вартість, якщо рішення хибне: ще одне необов'язкове поле журналу.

- [ ] **Крок 1: Написати тести, що падають**

```python
def test_default_fields_keep_v2_bytes_and_ids():
    # подія без нових полів: model_dump_json не містить slot/source_kind/evidence_version_id/resolves_claim_id;
    # claim_id/event_id збігаються з тими, що дає _add_event без ключових параметрів (зафіксувати на відомому прикладі)
def test_extra_fields_change_ids_and_serialize():
    # _add_event(..., slot='clothing') має інший claim_id, ніж без slot; json містить "slot":"clothing"
def test_author_without_quote_is_valid_only_for_author():
    # MemoryEvent(source_kind='author', quote=None, evidence_version_id=None) ok;
    # quote=None при source_kind='prose' -> ValidationError; quote=None з evidence_version_id або supporting -> ValidationError
def test_slot_requires_single_character_state_and_known_slot():
    # slot на facts -> ValidationError; два character_ids -> ValidationError; slot='hat' -> ValidationError
def test_replay_rejects_second_active_slot_value():
    # два add character_states з тим самим (персонаж, slot) без retire першого -> ValueError (І1)
def test_update_cannot_change_slot():
    # update із slot, відмінним від slot claim -> ValueError
def test_evidence_version_quote_checked_against_that_prose():
    # validate_memory_journal: подія з evidence_version_id=prose_A, quote з prose_A -> ok;
    # quote, якої немає в prose_A -> ValueError; evidence_version_id поза source_prose_ids або пізніше за source -> ValueError
def test_extend_promotes_schema_version():
    # previous v2 + подія зі slot -> schema_version 3; previous v2 + звичайна подія -> 2
def test_manual_memory_accepts_author_events():
    # normalize_manual_memory приймає нові події source_kind='author' з quote=None і з evidence_version_id ранішої прози,
    # source_version_id == prose_id; validate_memory_journal потім перевіряє цитату з evidence_version_id
def test_tracked_characters_uses_protagonist():
    # картка з рядком «Протагоніст» -> [її id]; без карток -> []
```

- [ ] **Крок 2: Запустити й побачити падіння**

Run: `pytest tests/memory/test_core_journal.py -q`
Expected: FAIL (ImportError `storygen.memory.core` / нові поля відсутні).

- [ ] **Крок 3: Реалізувати**

- **Серіалізатор** `MemoryEvent` викидає нові поля за типових значень (`slot` і `evidence_version_id` = `None`, `source_kind` = `'prose'`, `resolves_claim_id` = `None`). `quote` `None` теж не серіалізується.
- **ID.** У `_add_event` і `change_event_id` до списку `value` додається словник лише нестандартних полів: `{'slot': …, 'source_kind': 'author', 'evidence': id, 'no_quote': True, 'resolves': id}`, і тільки коли він непорожній. Порядок: після `supporting`, якщо той є.
- **`replay_memory`**:
  - І1: множина `(character_ids[0], slot)` серед активних;
  - `update` зберігає `slot` попереднього claim, інакше `ValueError`;
  - `retire` звільняє слот.
- **`validate_memory_journal`**:
  - цитату перевіряти в `source_versions[event.evidence_version_id or event.source_version_id]`;
  - для `quote=None` перевірки цитати немає;
  - `evidence_version_id` має стояти в `journal.source_prose_ids` не пізніше за `source_version_id`.
- **`normalize_manual_memory`**: для нових подій вимога «цитата в поточній прозі» діє лише за `evidence_version_id is None and quote is not None`.

- [ ] **Крок 4: Запустити тести модуля й увесь пакет пам'яті**

Run: `pytest tests/memory -q`
Expected: PASS (наявні тести без змін).

- [ ] **Крок 5: SPEC**

- MEMORY-003: абзац про журнал v3 з полями й правилами серіалізації.
- Scenario `MEMORY-003-S03` «Журнал v3 сумісний за байтами» → `test_default_fields_keep_v2_bytes_and_ids`.
- Scenario `MEMORY-001-S0x` «Запис автора без цитати» → `test_author_without_quote_is_valid_only_for_author`. Номер узяти наступний вільний.
- Записи в `traceability.json`, далі `check_docs`.

- [ ] **Крок 6: Коміт** `feat(memory): journal v3 fields and core slot registry (#41)`

---

### Task 2: Перехід дня і залежності пам'яті

**Файли:**
- Створити: `src/storygen/memory/story_time.py`
- Змінити: `src/storygen/storage/snapshots.py` (scope `memory` у `build_dependency_snapshot`, `selector_value`)
- Тести: `tests/memory/test_story_time.py`, `tests/storage/test_memory_core_selectors.py`

**Інтерфейси:**
- Споживає: `core.tracked_characters`.
- Створює:
  - `story_time.scene_start(beats: str) -> tuple[str, str] | None`. Повертає `(day_key, time)`, де `day_key` — `'date:Д.М.Р'` або `'day:N'`.
  - `story_time.day_change(scenes, scene, character_id) -> bool`. `scenes` — активні сцени твору.
  - `story_time.comparison_scene(scenes, scene, character_id) -> Scene | None`. Повертає останню активну сцену перед `scene`, де `character_id` у складі.
- Селектори в scope `memory`:
  - `('scene', scene.id, 'memory_day_key', day_key|None)` для поточної сцени і для сцени порівняння кожного відстежуваного персонажа;
  - `('story', story.id, 'tracked_characters', [...])`.
- `selector_value` обчислює обидва поля з view: `scene_start(peek_scene.beats)`; `tracked_characters` з карток `characters_version_id` і `peek_scenes`.

- [ ] **Крок 1: Написати тести, що падають**

```python
def test_scene_start_date_and_day_forms():
    assert scene_start('Початок: 12.03.2024, 22:00\n…')==('date:12.03.2024','22:00')
    assert scene_start('**Початок:** день 3, 07:15')==('day:3','07:15')
    assert scene_start('Day 2, 06:00')is None   # без «Початок:» сигналу немає
    assert scene_start('Початок: day 4, 06:00')==('day:4','06:00')
def test_day_change_same_form_only():
    # попередня 'date:01.01.2024', поточна 'date:02.01.2024' -> True; та сама дата -> False;
    # 'day:1' проти 'date:…' -> False; відсутня мітка в одній зі сцен -> False
def test_day_change_skips_scenes_without_character():
    # сцена1 (герой, день1), сцена2 (без героя, день2), сцена3 (герой, день2): day_change(…, сцена3, hero) is True
def test_beats_wording_change_keeps_memory_fresh():
    # зміна тексту beats без зміни дня -> freshness memory без змін (selector memory_day_key той самий)
def test_day_key_change_makes_memory_stale():
    # зміна дати в «Початок:» поточної сцени -> пам'ять сцени stale з reason selector_changed
def test_tracked_change_makes_memory_stale():
    # позначка «Протагоніст» переходить на іншу картку (нова версія карток) -> пам'ять stale
```

- [ ] **Крок 2: Запустити й побачити падіння**

Run: `pytest tests/memory/test_story_time.py tests/storage/test_memory_core_selectors.py -q`
Expected: FAIL.

- [ ] **Крок 3: Реалізувати**

- **Розбір часу.** Регулярний вираз для першого рядка, що після `plain_line` (`characters.acquaintance`) починається з `Початок:` (регістр не важливий). Значення: `\d{1,2}\.\d{1,2}\.\d{2,4}\s*,\s*\d{1,2}:\d{2}` або `(день|day)\s+\d+\s*,\s*\d{1,2}:\d{2}`.
- **Селектори** додаються лише за `settings.memory_mode=='evidence_delta'`, як наявний селектор `character_ids`.

- [ ] **Крок 4: Запустити тести модуля і наявні тести залежностей**

Run: `pytest tests/memory tests/storage -q`
Expected: PASS.

- [ ] **Крок 5: SPEC**

- CONTEXT-003 або MEMORY-002: технічний абзац про селектори `memory_day_key` і `tracked_characters`.
- Scenario «Перехід дня з рядка Початок» → `test_day_change_skips_scenes_without_character`.
- Scenario «Зміна протагоніста робить пам'ять застарілою» → `test_tracked_change_makes_memory_stale`.
- Речення в SPEC про шаблони («окремої моделі фізичного часу … немає») доповнити: рядок «Початок:» тепер використовується для сигналу переходу дня в пам'яті.

- [ ] **Крок 6: Коміт** `feat(memory): day-change signal and core dependencies (#41)`

---

### Task 3: Wire v4 — моделі, перевірка, переклад, схема

**Файли:**
- Створити: `src/storygen/memory/wire_v4.py`
- Тести: `tests/memory/test_wire_v4.py`, `tests/memory/test_wire_v4_schema.py`; доповнити `tests/memory/wire_helpers.py` функцією `v4_response(core=None, threads=None, **groups)`

**Інтерфейси:**
- Споживає: `journal._add_event`, `_change_event`, `_extend`, `replay_memory` (Task 1), `core.SLOTS` і `slot_def`, `wire_v3.AddOnlyGroup` і `StateGroup`, а також `violations.Violation` і `scope_unknown`.
- Створює:
  - `MemoryWireV4`: `schema_version: Literal[4]`, `core: dict[str, dict[str, CoreDecision]]`, `threads: dict[str, ThreadDecision]`, `facts: AddOnlyGroup`, `character_states: StateGroup`, `open_threads: AddOnlyGroup`, `timeline: AddOnlyGroup`.
    - `CoreDecision`: `status: Literal['unchanged','changed','unknown','introduced']`, `text: str`, `evidence_ids: list[str]`, `reason: str`.
    - `ThreadDecision`: `status: Literal['open','closed']`, `resolution: str`, `evidence_ids: list[str]`.
    - Невживані поля мають бути порожніми (`""` або `[]`).
  - `schema_bounds_v4(previous, prose, allowed_character_ids, tracked: list[str], day_change: dict[str, bool]) -> dict` з ключами:
    - `fragment_ids`;
    - `mutable` (`character_states` — лише claim без `slot`);
    - `threads` (активні `open_threads` у порядку replay);
    - `character_ids`;
    - `tracked` (`{cid: [назви слотів]}` лише для `cid` у `allowed_character_ids`);
    - `unestablished` (`{cid: [слоти, чинне значення яких має source_kind='author' і quote=None]}`);
    - `day_change`;
    - `slot_registry` (`'core-slots-v1'`).
  - `check_v4(data, previous, bounds) -> list[Violation]`.
  - `wire_v4_events(wire, previous, prose_id, prose, bounds) -> MemoryJournal`, з `schema_version=3`.
  - `memory_wire_v4_schema(bounds) -> dict`.

**Ruling, записати в журнал.** Специфікація задає `day_change: bool`. Після виправлення 6 перехресного рев'ю сигнал рахується окремо для кожного персонажа, тому в межах він `dict[cid, bool]`. Вартість, якщо рішення хибне: немає, бо зараз відстежуваний один.

- [ ] **Крок 1: Написати тести, що падають**

```python
def test_changed_into_empty_slot_adds_slotted_state()
def test_changed_into_occupied_slot_updates_same_claim()        # claim_id той самий, operation 'update', slot збережено
def test_unknown_moves_value_to_atmosphere()                    # retire слота + add без slot з тим самим текстом;
                                                                 # обидві source_version_id=prose_id, quote і evidence_version_id вихідного запису
def test_unknown_of_author_unquoted_slot()                      # атмосферний add: source_kind='author', quote=None; validate_memory_journal ok
def test_introduced_converts_author_value_to_prose()            # update з тим самим текстом, source_kind='prose', цитата поточної прози
def test_introduced_only_for_unestablished_slot()               # 'introduced' для слота з prose-значенням -> Violation(code='target_unknown')
def test_closed_thread_retires_and_adds_resolution_fact()       # retire text=resolution; facts add з resolves_claim_id=claim лінії, той самий доказ
def test_missing_slot_or_thread_key_is_schema_violation()       # пропущений слот або claim лінії -> Violation(path 'core.<cid>.<slot>' / 'threads.<id>', 'schema')
def test_non_empty_unused_fields_are_schema_violation()         # 'unchanged' з text!='' -> schema
def test_thirteen_closed_threads_are_valid()                    # 13 closed з доказами -> жодного ops_limit/add_limit
def test_add_limits_still_apply()                               # 4 facts add -> add_limit; 13 add сумарно -> ops_limit
def test_core_absent_character_has_no_keys()                    # tracked порожній -> core має бути {}; зайвий ключ -> schema
def test_v4_on_v2_previous_without_core()                       # попередній v2 без ядра, усе 'unchanged' -> журнал v3, нових подій ядра немає
def test_v3_answer_gets_wire_version()                          # відповідь schema_version 3 -> Violation('$','wire_version')
def test_translation_order_is_deterministic()                   # core (tracked, порядок SLOTS) -> threads (порядок bounds) -> facts, character_states, open_threads, timeline
# test_wire_v4_schema.py
def test_schema_uses_only_allowed_keywords()                    # рекурсивний обхід: множина ключів ⊆ дозволених
def test_schema_requires_every_slot_and_thread()                # required == усі слоти / усі claim ліній
def test_introduced_in_enum_only_for_unestablished()
def test_schema_without_fragments_forbids_evidence()            # evidence_ids maxItems 0 там, де фрагментів немає
```

- [ ] **Крок 2: Запустити й побачити падіння**

Run: `pytest tests/memory/test_wire_v4.py tests/memory/test_wire_v4_schema.py -q`
Expected: FAIL (ImportError).

- [ ] **Крок 3: Реалізувати**

Переклад за таблицею специфікації (розділ «Переклад у журнал»):
- **`unknown`**, коли слот і так порожній: подій немає.
- **Перший доказ** стає `quote`, решта — `supporting_quotes`, як у v3.
- **Дублікати `add`** відстежуються тим самим ключем `duplicates`, що у `wire_v3_events`.
- **Схема.** Значення слота — закритий об'єкт `{status, text, evidence_ids, reason}`. Усі ключі обов'язкові, `evidence_ids` має `minItems: 0`, `maxItems: 3`. Значення лінії — `{status, resolution, evidence_ids}`.
- **Перевірки сервера:**
  - для `changed`, `introduced` і `closed`: 1–3 унікальні відомі `evidence_ids`, непорожній `text` або `resolution`;
  - для `unknown`: непорожній `reason`;
  - решта полів порожні.
- **`character_states.update/retire`** у v4 дозволені лише для claim без `slot`, інакше `target_unknown`.

- [ ] **Крок 4: Запустити тести**

Run: `pytest tests/memory -q`
Expected: PASS.

- [ ] **Крок 5: SPEC**

- MEMORY-002: розділ «Wire v4» з формою, лімітами й перекладом.
- Scenario `MEMORY-002-S05` «Обов'язкові рішення v4» → `test_missing_slot_or_thread_key_is_schema_violation`.
- `MEMORY-002-S06` «Заміщення слота» → `test_changed_into_occupied_slot_updates_same_claim`.
- `MEMORY-002-S07` «Закриття лінії з розв'язкою» → `test_closed_thread_retires_and_adds_resolution_fact`.
- `MEMORY-002-S08` «Повна правильна відповідь не впирається в ліміт» → `test_thirteen_closed_threads_are_valid`.
- traceability, `check_docs`.

- [ ] **Крок 6: Коміт** `feat(memory): wire v4 with mandatory core and thread decisions (#41)`

---

### Task 4: Підключення v4 до конвеєра і контракту промпту

**Файли:**
- Змінити:
  - `src/storygen/prompt_contracts.py`;
  - `src/storygen/providers/models.py` (`memory_mode`);
  - `src/storygen/generation/context.py` (гілка `stage=='memory'`);
  - `src/storygen/memory/projection.py` (`memory_catalog_v4`);
  - `src/storygen/providers/requests.py`;
  - `src/storygen/memory/journal.py` (`_parse_memory_data`: `wire_version==4`);
  - `src/storygen/generation/prompts.py`;
  - `src/storygen/web/routes_settings.py` (`_custom_contract`);
  - `src/storygen/web/static/settings.js` і `settings-state.js`;
  - `src/storygen/web/static/i18n.json`.
- Створити: `src/storygen/generation/resources/memory_delta_uk_v4.txt`.
- Тести:
  - `tests/generation/test_memory_v4_pipeline.py`;
  - оновити `tests/generation/test_prompt_contracts.py`;
  - перевести на `v4_response` наявні тести, що женуть повний етап memory фейковою відповіддю v3 (див. Ruling).

**Інтерфейси:**
- Споживає: Task 1–3.
- **Контракт.** `expected_contract('memory', settings)` → `PromptContract(stage='memory', mode='evidence_delta', schema_version=4)`. `compatible_contract` для пам'яті приймає лише 4. `memory_wire_version(ref)` → `4`, якщо `ref` дорівнює `None`, інакше збережену версію.
- **`RoleSettings.memory_mode`** — `Literal['evidence_delta'] = 'evidence_delta'` з `field_validator(mode='before')`, що перетворює `'snapshot'` на `'evidence_delta'`.
- **Fragments контексту пам'яті:**
  - `memory_wire_version='4'`;
  - `memory_schema_bounds` = JSON від `schema_bounds_v4(...)`;
  - `memory_tracked` = JSON-список.
- **`memory_catalog_v4(journal, tracked: list[str], names: dict[str,str]) -> str`** — JSON з ключами:
  - `core`: `{cid: {slot: {value, source: 'prose'|'author', reader_unknown: bool}}}`;
  - `threads`: `[{claim_id, text}]`;
  - `mutable`: стани без слота;
  - `immutable`.

**Ruling, записати в журнал.** Тести, що женуть повний етап memory фейковою відповіддю v3, переводяться на `v4_response`. Тести самого `wire_v3` лишаються без змін, бо parser v3 потрібен для replay збережених спроб. Вартість, якщо рішення хибне: зміни в чужих тестах, які видно в diff.

- [ ] **Крок 1: Написати тести, що падають**

```python
def test_expected_memory_contract_is_v4()
def test_custom_v2_and_v3_memory_prompts_are_incompatible()     # validate_role_prompt -> ValueError «Несумісний промпт: потрібно memory/evidence_delta/4»
def test_upgrade_flag_assigns_v4()                              # SettingsChange(upgrade_memory_wire=True) для збереженого /2 і /3 -> новий промпт із /4
def test_snapshot_mode_reads_as_evidence_delta()                # RoleSettings.model_validate({'memory_mode':'snapshot',…}).memory_mode=='evidence_delta'
def test_memory_context_has_v4_bounds_and_core_catalog()        # build_context(…,'memory',…): fragments memory_wire_version=='4', bounds.tracked=={hero:[5 слотів]}
def test_day_change_notice_in_memory_context()                  # сцени з різними днями: секція «ЗМІНИВСЯ ДЕНЬ» з day_key обох сцен; без мітки — секції немає
def test_request_uses_v4_schema()                               # requests body json_schema == memory_wire_v4_schema(bounds)
def test_stage_publishes_v4_journal()                           # фейкова відповідь v4 -> опублікована memory schema_version 3 з подією slot
def test_default_memory_prompt_is_v4()                          # role_prompt('memory',…) читає memory_delta_uk_v4.txt і згадує core та threads
```

- [ ] **Крок 2: Запустити й побачити падіння**

Run: `pytest tests/generation/test_memory_v4_pipeline.py tests/generation/test_prompt_contracts.py -q`
Expected: FAIL.

- [ ] **Крок 3: Реалізувати**

- **`context.py`.** Для wire 4 секції такі:
  - «ЯДРО СТАНУ ВІДСТЕЖУВАНИХ ПЕРСОНАЖІВ — УСІ СЛОТИ ОБОВ'ЯЗКОВІ»;
  - «АКТИВНІ ЛІНІЇ — ДЛЯ КОЖНОЇ ОБОВ'ЯЗКОВЕ open/closed»;
  - каталог;
  - «ЗМІНИВСЯ ДЕНЬ: <day_key попередньої> → <day_key поточної>», якщо `day_change`;
  - дозволені `character_ids`;
  - нумеровані фрагменти.

  `tracked` береться з `core.tracked_characters` і перетинається зі складом сцени. `day_change` обчислюється через `story_time.day_change`.
- **Промпт `memory_delta_uk_v4.txt`.** Береться за основу v3 і доповнюється:
  - форма `core` і `threads`;
  - правила `unknown` лише з причиною і `introduced` лише для слотів «читачеві невідомо»;
  - лінія закривається тільки доказом розв'язки, зокрема непрямої, і ніколи через відсутність персонажа.
- **UI налаштувань:**
  - прибрати `option value="snapshot"`;
  - мітка режиму — «Операції пам'яті v4 за доказами»;
  - прапорець оновлення показувати для збережених `/2` і `/3`, текст «Перевести власний промпт на формат v4»;
  - `expectedPromptContract` повертає `/4`;
  - ключі в `i18n.json` для UA/EN.

- [ ] **Крок 4: Запустити весь набір тестів**

Run: `pytest -q -x --basetemp=C:/Users/yuriy/AppData/Local/Temp/pytest-core-t4`
Expected: PASS. Кожен змінений чужий тест — лише заміна відповіді v3 на `v4_response`.

- [ ] **Крок 5: SPEC і документація**

- **PROMPT-CONTRACT:** очікуваний `memory/evidence_delta/4`, `/2` і `/3` несумісні, `upgrade_memory_wire` → `/4`.
  - Усунене відхилення не вказувати: це навмисна зміна контракту, і в журналі змін це треба записати.
- **Режим `snapshot`** прибрано для нових викликів.
- **Scenarios:**
  - «Старий власний промпт пам'яті» → `test_custom_v2_and_v3_memory_prompts_are_incompatible`;
  - «Режим snapshot читається як evidence_delta» → `test_snapshot_mode_reads_as_evidence_delta`.
- **Користувацька документація UA/EN** розділу налаштувань пам'яті (знайти через `grep -rl "snapshot" docs/*.md docs/en/*.md`): режим v4 і оновлення власного промпту.

- [ ] **Крок 6: Коміт** `feat(memory): memory stage on wire v4 and prompt contract /4 (#41)`

---

### Task 5: Секція ядра в контексті письменника

**Файли:**
- Змінити: `src/storygen/memory/projection.py` (`project_memory`), `src/storygen/memory/forwarding.py` (`memory_view_from_view`, приховування розв'язки)
- Місце виклику `project_memory` (знайти через `grep -rn "project_memory(" src`): передати `tracked` і `names`.
- Тести: `tests/memory/test_core_projection.py`

**Інтерфейси:**
- Споживає: Task 1 і `core.tracked_characters`.
- `project_memory(journal, character_ids, source_scene_numbers, *, hidden_claim_ids=(), tracked=(), names=None)`. `metrics['projection_version']` стає `'memory-uk-v3'`.
- `effective_hidden(journal, hidden_claim_ids) -> set[str]`. Додає до прихованих факти, у яких `resolves_claim_id` належить прихованим (І5). Використовується і в `project_memory`, і в `memory_view_from_view`: рядок факту-розв'язки має `forward=False`, коли лінія прихована і для самого факту автор нічого не вибирав.

- [ ] **Крок 1: Написати тести, що падають**

```python
def test_core_section_first_and_not_filtered_by_cast()          # «ЯДРО СТАНУ — <ім'я>» перед ФАКТАМИ, навіть якщо героя немає в character_ids сцени
def test_core_lines_in_registry_order_skip_empty()              # «одяг: …», «місце: …»; порожні слоти не виводяться
def test_author_unquoted_value_has_reader_unknown_suffix()      # суфікс « (читачеві невідомо: якщо знадобиться, введи в тексті як нове)»
def test_slotted_states_not_duplicated_in_current_states()
def test_hidden_core_value_not_shown()                          # MEMORY-FORWARD діє на ядро
def test_v4_closure_rendered_only_as_fact()                     # retire з парним resolves-фактом не в ХРОНОЛОГІЇ; факт у ФАКТАХ
def test_legacy_closure_stays_in_timeline()                     # retire без парного факту — у ХРОНОЛОГІЇ, як раніше
def test_hidden_thread_resolution_stays_hidden()                # лінія прихована -> факт-розв'язка не в проєкції; у memory_view forward=False
```

- [ ] **Крок 2: Запустити й побачити падіння**

Run: `pytest tests/memory/test_core_projection.py -q`
Expected: FAIL.

- [ ] **Крок 3: Реалізувати** за інтерфейсами. Мітки слотів беруться з `core.SLOTS[*].label_uk`.

- [ ] **Крок 4: Запустити весь набір тестів**

Run: `pytest -q --basetemp=C:/Users/yuriy/AppData/Local/Temp/pytest-core-t5`
Expected: PASS.

- [ ] **Крок 5: SPEC, документація, журнал**

- **CONTEXT-001 або 002:** секція ядра як обов'язковий шар. Scenario «Ядро перед іншою пам'яттю» → `test_core_section_first_and_not_filtered_by_cast`.
- **MEMORY-FORWARD:** І5. Scenario «Розв'язка прихованої лінії» → `test_hidden_thread_resolution_stays_hidden`.
- **Користувацька документація UA/EN** розділу пам'яті:
  - ядро протагоніста, слоти;
  - закриття ліній;
  - «читачеві невідомо»;
  - перехід дня через рядок «Початок:».
- **Запис у `docs/superpowers/plans/2026-10-20-remediation-progress.md`.**
- `python scripts/check_docs.py` без помилок.

- [ ] **Крок 6: Коміт** `feat(memory): core section and resolution forwarding in writer context (#41)`

---

## Після задач

1. Фінальне рев'ю всієї гілки, тобто end-to-end рев'ю ядра. Його висновки стають вхідними даними плану PR 2.
2. `python scripts/verify.py` на чистому дереві, з `PYTHONPATH` на `src` цього worktree. Результат записати в `docs/STATUS.md`, закомітити.
3. `npx -y @ysilvestrov/detent cross-review --author claude` і таблиця рішень в описі PR.
4. PR на `main` з посиланням на специфікацію і переліком оновленої документації UA/EN.
