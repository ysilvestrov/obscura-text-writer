# Учасники записів пам'яті, PR 1 — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Лінії, факти й хронологія нової пам'яті отримують явних учасників (`participant_ids`), відбір пам'яті під бюджет бере їх замість основ імен, а стара хронологія повертається за учасниками й місцем (шар `past`).

**Architecture:** Нове поле `MemoryEvent.participant_ids` повторює шлях `location_ids` (MEMORY-LOCATIONS): журнал → wire v4 (межі, схема, перевірка, транслятор) → запит етапу memory (розділ дозволених учасників) → проєкція `MemoryItem` → `classify`/`select_memory`/`narrow_catalog` → рядок `memory-view` і таблиця. Накладки розмітки (PR 2) тут немає: чинні учасники — лише поле події.

**Tech Stack:** Python 3.12, pydantic, SQLite (без міграції), vanilla JS (`memory-table.js`), pytest, node-тести `tests/web/js`.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-27-memory-entities-design.md` (затверджено 2026-11-27), §2.1, §2.2, §3 без накладки, §5 (лише показ у таблиці), §7, §8.

## Global Constraints

- Поле `participant_ids` — лише для `facts`, `open_threads`, `timeline`; у `character_states` MUST бути порожнім (там власник — `character_ids`).
- Порожнє `participant_ids` не серіалізується: старі журнали й версії байт у байт. До `claim_id` і `duplicate_key` поле не входить.
- Журнал із будь-якою подією з непорожнім `participant_ids` має `schema_version = 4`; версія журналу ніколи не знижується при продовженні.
- Помилки валідації журналу: «Некоректні учасники пам’яті» (повтор чи порожній ID), «Учасники дозволені лише для ліній, фактів і хронології» (непорожнє поле в стані), «Не можна змінювати учасників claim» (зміна з іншою множиною).
- Межі: `bounds['participant_ids']` пишеться лише для книги з картками персонажів (ID усіх карток твору); без карток межі, схема й запит memory байт у байт як зараз (І6).
- Код порушення wire v4: `participant_unknown`.
- Мітка розділу запиту: ключ `allowed_participant_ids`, тексти uk «ДОЗВОЛЕНІ PARTICIPANT_IDS: …» / en «ALLOWED PARTICIPANT_IDS: …» (повний текст — Task 2).
- Шар `past` у `LAYERS` стоїть після `place`; рядок кладеться в нього лише для `section=='timeline'`, старшого за `TIMELINE_WINDOW`, за учасником зі складу сцени, що не є відстежуваним героєм, або за локацією в околиці. Без учасників і локацій — лише за полями події, без основ імен.
- `SELECTED_PROJECTION = 'memory-uk-v4-selected'`, `SUMMARY_PROJECTION = 'memory-uk-v4-selected-summary'`.
- Запис без учасників класифікується так само, як до зміни (І2); без переповнення запит незмінний (І1).
- Нова вимога SPEC.MD `MEMORY-ENTITIES`; кожен Scenario має запис у `docs/verification/traceability.json`; тести мають `@pytest.mark.req('MEMORY-ENTITIES')`.
- Документація українською; маркери OpenSpec англійською. Повний pytest і `scripts/verify.py` — з `C:/tmp/<коротка-назва>`.

## Review Focus

1. Книга без карток персонажів (імпорт рукопису до пошуку персонажів): запит, межі й схема memory мають бути байт у байт як зараз — тест у Task 2.
2. Перебудова пам'яті книги, де старі журнали v3 продовжує нова відповідь з учасниками: журнал стає v4, старі події не змінюються, ID записів ті самі — тест у Task 1.
3. Ручне збереження пам'яті автором (JSON без `participant_ids` у зміні лінії з учасниками) не має падати — зміна успадковує учасників свого запису — тест у Task 1.
4. Героїня в кожній сцені: стара хронологія лише з нею не заповнює шар `past` — тест у Task 3.
5. Учасник, якого видалили з карток: запис лишається валідним, таблиця не падає, ім'я просто не показується — тест у Task 4.

---

### Task 1: Поле учасників у журналі

**Files:**
- Modify: `src/storygen/memory/journal.py` (`MemoryEvent`, `omit_defaults`, `MemoryJournal.schema_version`, `replay_memory`, `_add_event`, `_change_event`, `_nonstandard`, `_extend`, `apply_operations`, `_inherit_places`, нормалізація ручного збереження ≈ рядок 420–435)
- Modify: `src/storygen/memory/merge.py:95-100`, `src/storygen/memory/core_review.py:266-276`, `src/storygen/memory/wire_v3.py:147-148`
- Modify: `SPEC.MD` (нова вимога `MEMORY-ENTITIES` після MEMORY-LOCATIONS: Requirement, технічний опис журналу, Scenario `MEMORY-ENTITIES-S01`), `docs/verification/traceability.json`
- Test: `tests/memory/test_participants_journal.py`

**Interfaces:**
- Produces: `MemoryEvent.participant_ids: list[str]`; `_add_event(..., participant_ids=())`, `_change_event(..., participant_ids=())`; `MemoryJournal.schema_version: Literal[2,3,4]`.

- [ ] **Step 1: Write the failing tests**

```python
pytestmark = pytest.mark.req('MEMORY-ENTITIES')

def test_empty_participants_are_not_serialized():
    e = _add_event('facts', 'Маяк згас', 'p1', 'цитата', 0)
    assert 'participant_ids' not in json.loads(e.model_dump_json())

def test_participants_do_not_change_claim_id():
    a = _add_event('facts', 'Маяк згас', 'p1', 'цитата', 0)
    b = _add_event('facts', 'Маяк згас', 'p1', 'цитата', 0, participant_ids=['c1'])
    assert a.claim_id == b.claim_id

def test_participants_on_a_state_are_rejected():
    with pytest.raises(ValueError, match='Учасники дозволені лише для ліній, фактів і хронології'):
        MemoryJournal(events=[_add_event('character_states', 'Оля втомлена', 'p1', 'ц', 0, ['c1'], participant_ids=['c2'])])

def test_duplicate_or_blank_participants_are_rejected():  # ['c1','c1'] і [' '] — «Некоректні учасники пам’яті»

def test_a_change_must_keep_the_participants_of_its_claim():
    # add open_threads з ['c1'], потім _change_event('update', …, participant_ids=['c2']) → «Не можна змінювати учасників claim»

def test_journal_with_participants_is_v4_and_never_goes_back():
    # _extend(v3-журнал з location_ids, …, [add з participant_ids]) → schema_version 4;
    # наступний _extend v4-журналу подіями лише з location_ids → лишається 4

def test_manual_change_without_participants_inherits_them():
    # JSON журналу: add open_threads з participant_ids ['c1'], retire без ключа participant_ids
    # → нормалізація ручного збереження дає retire з ['c1'], журнал валідний

def test_thread_resolution_and_merge_keep_participants():
    # core_review: факт розв'язки лінії з ['c1'] має ['c1']; merge.py: зміна запису несе його participant_ids
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/memory/test_participants_journal.py -q`
Expected: FAIL (`_add_event() got an unexpected keyword argument 'participant_ids'`).

- [ ] **Step 3: Implement**

- `MemoryEvent.participant_ids: list[str] = Field(default_factory=list)`; `omit_defaults` прибирає порожнє.
- `replay_memory`: перевірки з Global Constraints поряд із наявними перевірками `location_ids`; для зміни — `previous.participant_ids != event.participant_ids` → «Не можна змінювати учасників claim».
- `_nonstandard` враховує `participant_ids`. `_extend(previous, prose_id, events, schema_version=None)` (сигнатура та сама; `schema_version` тепер нижня межа): версія = `max(previous.schema_version, schema_version or 2, 3 if any(_nonstandard(e) for e in events) else 2, 4 if any(e.participant_ids for e in events) else 2)`.
- Ручне збереження: `_inherit_places` перейменувати на `_inherit_claim_fields` і успадковувати так само `participant_ids`; канонізація (≈ рядок 431) передає `participant_ids=event.participant_ids` у `fields`.
- Скрізь, де зміна чи похідний запис несе `location_ids` свого запису (`apply_operations`, `merge.py`, `core_review.py`, `wire_v3.py`), так само передати `participant_ids`.
- SPEC.MD: Requirement `MEMORY-ENTITIES — Учасники записів пам’яті` (формулювання вимоги — перше речення «Мети» специфікації зміни; технічний опис §2.1), Scenario `MEMORY-ENTITIES-S01 — Учасники нового запису` (GIVEN книга з картками, WHEN етап memory додає факт, лінію чи подію хронології з учасниками, THEN журнал SHALL зберігати `participant_ids` без зміни `claim_id`, AND зміни запису SHALL нести його учасників, AND стан з учасниками SHALL відхилятися); traceability — тести цього файла (Task 2 додасть свої).

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/memory -q`
Expected: PASS (наявні тести журналу без змін).

- [ ] **Step 5: Commit**

`git commit -m "feat(memory): поле учасників записів у журналі (MEMORY-ENTITIES-S01)"`

### Task 2: Wire v4 і запит етапу memory

**Files:**
- Modify: `src/storygen/memory/wire_v4.py` (`WireAddV4`, `schema_bounds_v4`, `check_v4`, `wire_v4_events`, `memory_wire_v4_schema`), `src/storygen/memory/violations.py`
- Modify: `src/storygen/generation/context.py:416-445`, `src/storygen/generation/context_labels.py`, `src/storygen/generation/memory_build.py:216-220`
- Modify: `SPEC.MD` (MEMORY-ENTITIES: опис wire v4 і розділу запиту), `docs/verification/traceability.json`
- Test: `tests/memory/test_wire_v4_participants.py`, `tests/generation/test_memory_participants_context.py`

**Interfaces:**
- Consumes: Task 1 `_add_event(..., participant_ids=...)`.
- Produces: `schema_bounds_v4(..., location_ids=(), participant_ids=())`; `bounds['participant_ids']` (лише непорожній).

- [ ] **Step 1: Write the failing tests**

```python
def test_bounds_without_cards_are_byte_for_byte_the_same():
    assert schema_bounds_v4(j, prose, ['c1'], [], {}) == schema_bounds_v4(j, prose, ['c1'], [], {}, participant_ids=())
    assert 'participant_ids' not in json.dumps(memory_wire_v4_schema(schema_bounds_v4(j, prose, ['c1'], [], {})))

def test_schema_requires_participants_in_facts_threads_and_timeline_adds_only():
    s = memory_wire_v4_schema(schema_bounds_v4(j, prose, ['c1'], [], {}, participant_ids=['c1', 'c2']))
    for cat in ('facts', 'open_threads', 'timeline'):
        item = s['properties'][cat]['properties']['add']['items']
        assert item['properties']['participant_ids']['items']['enum'] == ['c1', 'c2']
        assert 'participant_ids' in item['required']
    assert 'participant_ids' not in s['properties']['character_states']['properties']['add']['items']['properties']

def test_unknown_or_repeated_participant_is_refused():  # ['zz'] і ['c1','c1'] → Violation(..., 'participant_unknown')

def test_old_answer_without_participants_is_valid():  # check_v4 відповіді без поля → []

def test_translated_journal_keeps_participants_and_is_v4():
    # wire_v4_events з facts.add participant_ids ['c2'] → подія з ['c2'], schema_version 4;
    # закриття лінії з ['c1'] → факт розв'язки з ['c1']

# tests/generation/test_memory_participants_context.py
def test_memory_request_lists_every_card_as_allowed_participants():
    # книга з картками c1 (у складі сцени) і c2 (поза складом): розділ
    # «ДОЗВОЛЕНІ PARTICIPANT_IDS» з {"c1": ім'я, "c2": ім'я}, bounds['participant_ids'] == ['c1','c2']

def test_memory_request_without_cards_is_unchanged():
    # книга без карток: user_text і bounds без participant_ids (порівняння з очікуваним до зміни)

def test_sends_cover_participants_section():  # SECTION_CATEGORIES['allowed_participant_ids'] == 'memory_catalog'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/memory/test_wire_v4_participants.py tests/generation/test_memory_participants_context.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

- `WireAddV4.participant_ids: list[str] = Field(default_factory=list)` (`WireStateAddV4` — без поля).
- `schema_bounds_v4(..., participant_ids=())`: `if participant_ids: bounds['participant_ids']=list(participant_ids)`.
- Схема: для `facts`, `open_threads`, `timeline` `add` — `{'participant_ids': _scope(bounds['participant_ids'])}` разом із `places`, лише коли межі його мають (обов'язковість — як у `location_ids`).
- `check_v4`: для `add` цих трьох категорій `scope_unknown(item.participant_ids, set(bounds.get('participant_ids', ())))` → `participant_unknown`. `violations.py`: `'participant_unknown': 'Невідомий учасник: participant_ids містить персонажа поза дозволеним списком або повтор.'`
- `wire_v4_events`: `add` передає `participant_ids=getattr(item,'participant_ids',[])`; факт розв'язки лінії — `participant_ids` лінії; `change` — `participant_ids` запису; виклик `_extend(previous, prose_id, events, 3)` лишається (з Task 1 `3` — нижня межа, тож журнал з учасниками стає v4).
- `context.py`: `participants = {card.id: names.get(card.id, card.name) for card in cards}`; `participant_section = [label('allowed_participant_ids', language) + '\n' + dump(participants)] if participants else []`; додати поряд із `*place_section` в обох гілках (`bible` і звичайній); `schema_bounds_v4(..., participant_ids=list(participants))`.
- `context_labels.py`: `'allowed_participant_ids': {'uk': 'ДОЗВОЛЕНІ PARTICIPANT_IDS: додайте до нового факту, лінії чи події хронології participant_ids усіх персонажів, які діють у записі чи про яких у ньому йдеться (порожній список — якщо таких немає). Словник ID → ім’я:', 'en': 'ALLOWED PARTICIPANT_IDS: give a new fact, thread or timeline event the participant_ids of every character who acts in it or whom it is about (an empty list if there are none). ID → name:'}`.
- `memory_build.SECTION_CATEGORIES['allowed_participant_ids'] = 'memory_catalog'`.
- SPEC.MD: технічний опис §2.2 у MEMORY-ENTITIES; traceability S01 доповнити тестами цього завдання.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/memory tests/generation -q`
Expected: PASS (знімкові тести запиту memory для книг із картками оновити свідомо — лише додатковий розділ; без карток не змінюються).

- [ ] **Step 5: Commit**

`git commit -m "feat(memory): учасники в wire v4 і запиті етапу memory"`

### Task 3: Відбір за учасниками й шар `past`

**Files:**
- Modify: `src/storygen/memory/projection.py:70-80,130-131` (`MemoryItem.participant_ids`), `src/storygen/memory/selection.py` (`LAYERS`, `classify`, `select_memory`, `minimal_chars`, `narrow_catalog`), `src/storygen/generation/context.py:91-92`
- Modify: `SPEC.MD` (MEMORY-SELECT: перелік шарів і `past`, відоме обмеження про основи імен; MEMORY-ENTITIES: Scenario S02, S03), `docs/verification/traceability.json`
- Test: `tests/memory/test_selection_participants.py`

**Interfaces:**
- Consumes: Task 1 `MemoryEvent.participant_ids`.
- Produces: `MemoryItem.participant_ids: tuple[str,...] = ()`; `'past'` у `LAYERS`, у `selection.layers`/`dropped`.

- [ ] **Step 1: Write the failing tests** (хелпери `inp`, `item`, `layer_of` з `tests/memory/test_selection.py`; учасників ставити `dataclasses.replace(entry, participant_ids=(...))`)

```python
def test_thread_with_a_participant_of_the_scene_goes_to_threads_even_with_an_inflected_name():
    # лінія «Олі винні гроші» з participant_ids ('a',), 'a' у складі → 'threads'
def test_thread_with_participants_outside_the_scene_does_not_fall_back_to_names():
    # текст згадує учасника сцени, але participant_ids ('x',) поза складом → не 'threads'
def test_record_without_participants_is_classified_by_names_as_before():
    # той самий набір без participant_ids дає ті самі шари, що classify до зміни (порівняння з еталоном)
def test_fact_only_about_the_hero_goes_to_atmosphere_by_ids():
    # факт з ('h',) де h відстежуваний у складі → 'atmosphere'; з ('h','a') → 'facts'
def test_old_timeline_with_a_non_hero_participant_goes_to_past():
    # хронологія сцени 2 при scene_number 40, participant_ids ('a',) → 'past'; та сама з ('h',) → 'timeline'
def test_old_timeline_in_the_neighbourhood_goes_to_past():  # location_ids в inp.place → 'past'
def test_past_is_taken_newest_first_and_not_when_its_block_summary_is_taken():
    # два старі записи past (сцени 3 і 8): при бюджеті на один береться сцена 8;
    # підсумок блоку 1–10 відібрано → записи past цього блоку не беруться й не рахуються в note
def test_timeline_note_counts_untaken_past_and_skips_taken():
    # note «Не показано записів: N (сцени …)» не містить номера взятого запису past
def test_hero_in_every_scene_does_not_fill_past():
    # 30 старих записів хронології лише з ('h',) → layers['past'] порожній
def test_narrow_catalog_keeps_facts_by_participants_and_names_without_them():
    # факт з ('a',) без згадки імені лишається; факт без учасників зі згадкою — лишається, як раніше
def test_selected_projection_version_is_v4():  # SELECTED_PROJECTION == 'memory-uk-v4-selected'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/memory/test_selection_participants.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

- `MemoryItem.participant_ids: tuple[str,...] = ()`; `memory_items` заповнює з події. Фільтр проєкції за складом не змінювати.
- `LAYERS = ('core','hero_recent','threads','present','place','past','general','facts','summary','timeline','atmosphere','fts')`.
- `classify`: `p = set(item.participant_ids)`; учасник сцени = `p & cast if p else mentions(text, cast_stems)`; для фактів «лише про героя» = `bool(p & heroes) and not (p & (cast-heroes))`, якщо `p`, інакше наявне правило за основами. Для `section=='timeline'`: якщо джерело старше за `TIMELINE_WINDOW` (`scenes_back`) і (`p & (cast - set(inp.tracked))` або `here`) → `'past'`, інакше `'timeline'`.
- `select_memory`: `past` береться після підсумків і перед `timeline`, відсортований за `source_scene` спаданням, пропускаючи `covered(item)`; `note()`, `minimal_chars` і попередження про застарілі підсумки рахують `layers['timeline'] + layers['past']`. Видалення підсумку в циклі обрізання рахує в `dropped['timeline']` записи обох шарів блоку.
- `narrow_catalog`: факт лишається, якщо `cast & set(event.participant_ids)` (за наявності учасників) або згадка (без них), або локація.
- `context.py`: `SELECTED_PROJECTION='memory-uk-v4-selected'`, `SUMMARY_PROJECTION='memory-uk-v4-selected-summary'`.
- SPEC.MD: у MEMORY-SELECT додати `past` у перелік шарів і жадібний порядок, змінити відоме обмеження про відмінки («лише для записів без учасників»); `projection_version` оновити. MEMORY-ENTITIES-S02 «Відбір за учасниками» і S03 «Стара хронологія за сутностями» з GIVEN/WHEN/THEN за §3 специфікації; traceability.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/memory tests/generation tests/retrieval_bench -q`
Expected: PASS (наявні тести відбору без учасників — без змін, крім очікуваного `projection_version`).

- [ ] **Step 5: Commit**

`git commit -m "feat(memory): відбір за учасниками й шар past (MEMORY-ENTITIES-S02, S03)"`

### Task 4: Учасники в таблиці пам'яті, документація

**Files:**
- Modify: `src/storygen/memory/forwarding.py:86-109` (рядок `memory-view`), `src/storygen/web/static/memory-table.js:100,116-117`, `src/storygen/web/static/i18n.json` (`memory.participants` uk/en)
- Modify: `SPEC.MD` (MEMORY-ENTITIES-S04; сумісність і відомі обмеження за §7, §9 специфікації), `docs/verification/traceability.json`
- Modify: `docs/site/{uk,en}/…` — сторінка, що описує таблицю пам'яті (знайти за «Локації:» / «Locations:»), і `python scripts/check_site.py --rehash <slug>`
- Test: `tests/memory/test_memory_view_participants.py`, `tests/web/js/memory-table.mjs`

**Interfaces:**
- Consumes: Task 1 `MemoryEvent.participant_ids`.
- Produces: поле рядка `memory-view` `participants: list[str]` (імена).

- [ ] **Step 1: Write the failing tests**

```python
def test_memory_view_row_has_participant_names():
    # запис з participant_ids ['c1'] → row['participants'] == [поточне ім'я c1]
def test_unknown_participant_is_skipped():
    # participant_ids ['gone'] (картки немає) → row['participants'] == [], без винятку
```

```js
// tests/web/js/memory-table.mjs
// рядок з participants ['Оля'] показує «Учасники: Оля»; пошук «Оля» знаходить рядок, у тексті якого імені немає
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/memory/test_memory_view_participants.py -q` і `node tests/web/js/memory-table.mjs`
Expected: FAIL.

- [ ] **Step 3: Implement**

- `forwarding.py`: імена з карток твору (`load_characters` версії карток) за поточними іменами сцени (`scene_names`), невідомі ID пропускаються; `'participants': [...]` у рядку.
- `memory-table.js`: пошук враховує `row.participants`; під цитатою перед «Локації» — `t('memory.participants',{p0: row.participants.join('; ')})` з класом `hint memory-participants`, лише якщо список непорожній.
- `i18n.json`: `"memory.participants": "Учасники: {p0}"` (uk) / `"Participants: {p0}"` (en).
- SPEC.MD: S04 «Таблиця пам’яті показує учасників»; сумісність (журнал v4 не відкриває старіша Obscura, повернення лише з резервної копії; власні промпти `/4` без інструкції розділу дають записи без учасників) і відомі обмеження (учасники станів, крім власника, не записуються; стара пам'ять без учасників до PR 2).
- Сайт: рядок про «Учасники:» поряд із «Локації:» в обох мовах; `python scripts/check_site.py --rehash <slug>`.

- [ ] **Step 4: Run checks**

Run: `python -m pytest tests/memory tests/web -q`, `node tests/web/js/memory-table.mjs`, `python scripts/check_docs.py`
Expected: PASS, `check_docs` зелений.

- [ ] **Step 5: Commit**

`git commit -m "feat(memory): учасники в таблиці пам'яті; SPEC і сайт (MEMORY-ENTITIES-S04)"`

### Завершення PR 1

- [ ] `python scripts/verify.py` з `C:/tmp/me1` (detached worktree на HEAD, junction на `.venv` і `frontend/node_modules`); у описі PR — коміт і passed/failed/errors/skipped.
- [ ] Перехресна рецензія гілки (`npx -y @ysilvestrov/detent cross-review --author claude`), PR на `main`, оновлення основної теки після злиття.
