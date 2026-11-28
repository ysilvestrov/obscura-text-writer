# Учасники записів пам'яті, PR 2a (накладка сутностей) — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Старі записи пам'яті отримують учасників і локації через накладку `Story.memory_entities` за `claim_id`. Відбір під бюджет і звужений каталог беруть чинні сутності (автор → подія → модель). Автор виправляє сутності через API, а версії, зібрані з відбором чи звуженим каталогом, стають застарілими лише тоді, коли накладка змінила сутності їхніх кандидатів.

**Architecture:** Накладка — поле payload твору, як позначки ядра/атмосфери (MEMORY-SELECT-S08). Чисте правило `memory/entities.py::effective` і `EntityResolver` не роблять IO. `storage/memory_entities.py` містить три CAS-функції, набір записів книги, резолвер для твору й значення селектора `scene/memory_entities`. Накладка входить рівно в три місця:
- замикання `selection_input()` у `context.py`, яке працює лише при переповненні;
- `narrow_catalog`;
- рядок `memory-view`.

Фільтр проєкції `memory_items` не змінюється (І1). Запуску розмітки, чату й вимірювання тут немає: це PR 2b.

**Tech Stack:** Python 3.12, pydantic, FastAPI, SQLite (без міграції), pytest.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-27-memory-entities-design.md` (затверджено 2026-11-27): §2.3, накладка в §3, API правки з §5, §7, §8 (І1–І4, І6), §9, таблиця рев'ю спеки (рішення 2, 3, 4).

## Поділ PR 2 (pr-slicing, «core first»)

PR 2 за §10 специфікації охоплює накладку, запуск розмітки з переглядом і відбитком, API, застарілість і вимірювання. Це близько дев'яти задач, і запуск та вимірювання стоять на накладці, якої ще немає. Тому PR 2 ділиться на дві частини.

**PR 2a (цей план, 5 задач)** — ядро накладки:
- модель і правило `effective`;
- CAS-функції й API правки;
- накладка у відборі й звуженому каталозі;
- селектор застарілості;
- рядок таблиці.

Сценарії `MEMORY-ENTITIES-S05…S07`.

**PR 2b (окремий план після PR 2a і його наскрізного рев'ю)** — обв'язка, лише перелік:
1. Цілі й групи розмітки: об'єднання кандидатів останньої голови пам'яті кожного родоводу (BOOK-LINEAGE), без дублікатів за `claim_id`, лише записи без чинних учасників чи локацій і без запису `source='author'`. Ще в цій задачі:
   - промпт `memory_entities_v1` (uk/en) і контракт `records[{record, participants, locations}]`;
   - `POST /api/stories/{id}/memory-entities/preview` з `calls_bound = 2 × груп + 2`;
   - `plan_fingerprint` за §4.
2. Запуск `RunRequest.mode='memory_entities'` за механікою `generation/extract_run.py`:
   - контрольна точка й зарахування виклику до надсилання;
   - повтор, потім поділ навпіл, потім пропуск запису з причиною;
   - вичерпаний ліміт викликів дає частковий результат;
   - застосування після кожної групи через `apply_entity_marks` (Task 2) з одним перечитуванням ревізії;
   - підсумок `{marked, skipped}`;
   - worker, readiness, один активний запуск на книгу.
3. MCP:
   - `get_stage_task(stage='memory_entities', group?)` і `save_stage_result` тим самим контрактом;
   - `start_run(action='memory_entities')`: перегляд, потім `confirm=true` з відбитком;
   - інструкції моста.
4. Вимірювання §6:
   - стратегія бенчмарку `product_entities` (продуктовий відбір + `EntityResolver`) на копії `C:\tmp\rag-bench\data`;
   - звіт `target_recall`, змінних цілей і `syn`/`desc` на 32 тис. (реалістична міра) з парним тестом проти `product`;
   - рішення про PR 3 за власником.

Сценарій `MEMORY-ENTITIES-S08` (запуск і чат).

## Рішення, ухвалені в плані (без питань власнику)

| # | Рішення | Причина |
|---|---|---|
| Р1 | Розподіл S05–S08: у 2a — S05 «Накладка й чинні сутності», S06 «Правка накладки», S07 «Відбір і застарілість з накладкою»; у 2b — S08 «Запуск розмітки й чат». | §10 дає PR 2 саме S05…S08, а PR 3 — S09…S10. Нумерація лишається сталою. |
| Р2 | MCP-етап чату й `start_run(action='memory_entities')` переходять з PR 3 у PR 2b. PR 3 лишається діалог, меню, кнопка «Сутності…» й сайт. | Рішення власника 27.11 (питання 1): без виграшу «запуск розмітки — лише в API та MCP». Отже, MCP не може залежати від PR 3. |
| Р3 | Фільтр проєкції `memory_items` накладки не бере. Локації накладки діють лише для кандидатів, які вже є в проєкції. | Специфікація §3, §9 і рев'ю спеки № 3: інакше змінилася б повна проєкція й ламався б І1. Бриф «до фільтра проєкції» суперечить специфікації, а специфікація має перевагу. |
| Р4 | `effective` спершу відкидає невідомі ID учасників (картки немає), а потім перевіряє «непорожнє». Подія з лише видаленим учасником стає записом без учасників і йде за основами імен. | Усуває зауваження фінального рев'ю PR 1: видалений учасник вимикав запасний пошук за іменем. Узгоджено з §2.3 («ID невідомої картки при читанні відкидається»). |
| Р5 | Поле запису `source='author'` діє завжди, навіть порожній список. Поля `model` і події діють лише непорожніми. | Автор має змогу прибрати хибного учасника з події (рішення 4 рев'ю спеки). Порожній список моделі означає «не знайшла», а не «немає». |
| Р6 | `update_memory_entities(..., location_ids=None)` прибирає запис накладки будь-якого джерела; `participant_ids` тоді ігнорується. Непорожні учасники для стану від автора дають 400. Від моделі вони зберігаються як `[]`. | Сигнатура §2.3 робить необов'язковим лише `location_ids`. Для стану накладка дає лише локації (§2.3). Автор має бачити свою помилку, а пакет моделі не має падати через стан. |
| Р7 | `entities_source` рядка таблиці — одне значення: `author`, якщо є запис автора; інакше `model`, якщо модель дала хоч одне поле; інакше `event`, якщо подія має сутності; інакше `null`. | §5 вимагає одного поля, а пріоритет діє окремо для кожного поля. Показується найменш надійне джерело, яке вплинуло. |
| Р8 | Значення селектора `scene/memory_entities` — `dict[claim_id, str]` лише для кандидатів, у яких чинні сутності з накладкою відрізняються від сутностей без неї. Рядок — `'p=<id,…>;l=<id,…>'`. | `DependencySelector.expected` строго `dict[str,str]`. Значення «що дала накладка» (§3) не робить застарілим через затінений запис моделі. |
| Р9 | Набір записів книги для перевірки `claim_id` (`book_claims`) — кандидати (`candidate_events`) голів пам'яті всіх активних сцен, новіші сцени першими, один прохід на виклик. Автор може правити запис, який уже не активний у голові родоводу, але є в голові якоїсь сцени. | Таблиця пам'яті будь-якої сцени показує записи її голови, тож правка з неї має проходити. Один прохід замість `find_claim` на кожен запис пакета. PR 2b бере свої цілі вужче (голови родоводів). |
| Р10 | Пакет моделі з `claim_id` поза книгою чи ID поза картками відхиляється повністю (400), як у §2.3. Відсіяти такі записи до застосування — обов'язок запуску (2b). | Сувора межа сховища. Запуск має свій підсумок `skipped` з причиною. |
| Р11 | У 2a немає змін на сайті `docs/site/{uk,en}`. | Немає інтерфейсу: накладку створює лише API, яким користувач не користується напряму. Рядок таблиці показує ті самі «Учасники»/«Локації», а без запуску (2b) записів накладки немає. Причина піде в опис PR. |
| Р12 | Без перевірки fsck для накладки. | Невідомі ID відкидаються при читанні (Р4), тож збитий запис нічого не ламає. Перевірку можна додати окремо, якщо з'явиться потреба. |
| Р13 | Еталон І6 — нормалізований (ID замінено мітками) запит memory книги без карток. Він знятий кодом merge-base `a9c0e37c` (main до PR 1) і зберігається у `tests/generation/golden/memory_request_no_cards.json`. | Зауваження рев'ю PR 1: тест І6 перевіряв лише відсутність розділу. Еталон, знятий до зміни, ловить будь-яке відхилення. |
| Р15 | `clear_entity_marks` зберігає параметр `source` специфікації, але приймає лише `'model'`. | §2.3 називає параметр. Скасування правок автора поштучне (`PUT` з `location_ids=None`), окремої масової дії власник не просив. |
| Р16 | `PUT` автора замінює обидва поля повністю: порожній список означає «немає» й перекриває подію (Р5). Інтерфейс PR 3 передзаповнює форму чинними значеннями з рядка таблиці (Task 5). | Інакше потрібен третій стан поля («не перекривати»), якого немає в моделі `MemoryEntityMark` специфікації. |
| Р14 | Гілка PR 2a відгалужується від `main` після злиття PR 1, PR — на `main`. | AGENTS.md: усі PR лише на `main`. |

## Global Constraints

- `Story.memory_entities: dict[str, MemoryEntityMark]`, `max_length=20000`. Порожній словник не серіалізується (`exclude_if`), тож payload старих творів байт у байт той самий. Непорожній робить книгу нечитною для старішої Obscura (`extra="forbid"`), без міграції SQLite.
- `MemoryEntityMark{participant_ids: list[str], location_ids: list[str], source: Literal['model','author']}`, кожен список до 200 елементів без повторів.
- Порядок чинних сутностей для кожного поля: поле запису `author` → непорожнє поле події → непорожнє поле запису `model` → порожньо (Р5). Для `character_states` учасників немає ніколи: діє лише `location_ids`.
- Невідомі ID учасників (поза картками поточної версії) відкидаються при читанні. Локації проходять `locations.canonical` за злиттями.
- Накладка не змінює журналів, текстів, `claim_id`, доказів, MEMORY-FORWARD і підтверджень (І3). Пакет моделі ніколи не перезаписує записів `author` (І4).
- CAS на ревізію твору: конфлікт — `RevisionConflict` (409). Без змін ревізія не змінюється. Помилки — `ValueError` (400):
  - «Запису немає в пам’яті твору»;
  - «Невідомий персонаж у розмітці сутностей»;
  - «Невідома локація в розмітці сутностей»;
  - «Учасники дозволені лише для ліній, фактів і хронології»;
  - «Забагато записів розмітки сутностей».
- Фільтр проєкції `memory_items` не змінюється (Р3). Без переповнення запит, відбиток і метрики незмінні (І1). Запис без чинних сутностей класифікується як до зміни (І2). Книга без карток має запит, межі й схему memory без змін (І6).
- Селектор `scene/memory_entities` пишеться лише для версій з `memory_metrics['selection']` або `memory_metrics['narrow']`. У старому знімку його немає, і він не порівнюється.
- Тести мають `@pytest.mark.req('MEMORY-ENTITIES')` на кожній функції. Кожен Scenario має запис у `docs/verification/traceability.json`. `python scripts/check_docs.py` має бути зеленим.
- Документація українською; маркери OpenSpec англійською. Повний pytest і `scripts/verify.py` запускаються з `C:/tmp/me2a`.

## Review Focus

1. Картку персонажа видалили після розмітки (або етап memory записав учасника, якого потім видалили): запис не губиться, а знаходиться за іменем, як запис без учасників. Тест у Task 1 і Task 3.
2. Автор правив запис у таблиці, поки в іншій вкладці застосовувався пакет моделі: пакет зі старою ревізією дає 409, а пакет зі свіжою пропускає запис автора. Тест у Task 2.
3. Локацію з накладки злили з іншою: запис і далі в шарі `place` для сцени в околиці цілі злиття. Тест у Task 1 і Task 3.
4. Накладка є, але запит уміщається: запит, відбиток і знімок байт у байт ті самі, без селектора. Тест у Task 3 і Task 4.
5. Модель розмітила запис, сутності якого вже є в події: такий запис нічого не змінює й не робить застарілими версії. Тест у Task 4.

---

### Task 1: Модель накладки й чинні сутності

**Files:**
- Modify: `src/storygen/domain.py` (`MemoryEntityMark`, `Story.memory_entities` поряд із `memory_kind_overrides`)
- Create: `src/storygen/memory/entities.py`
- Modify: `src/storygen/memory/projection.py` (`candidate_events`; `candidate_claim_ids` = `set(candidate_events(journal))` — рефакторинг без зміни поведінки, наявні тести без змін)
- Modify: `SPEC.MD` (MEMORY-ENTITIES: технічний опис «Накладка» за §2.3, Scenario S05; Requirement — друге речення «Старі записи SHALL отримувати учасників і локації накладкою твору без зміни журналів»), `docs/verification/traceability.json`
- Test: `tests/memory/test_entities_effective.py`

**Interfaces:**
- Produces:
  - `MemoryEntityMark` (domain);
  - `Story.memory_entities: dict[str, MemoryEntityMark]`;
  - `Source = Literal['event','model','author']`;
  - `@dataclass(frozen=True) Effective(participant_ids: tuple[str,...], location_ids: tuple[str,...], participants_from: Source | None, locations_from: Source | None)` з властивістю `source -> Source | None` (Р7);
  - `effective(category: str, participant_ids, location_ids, mark: MemoryEntityMark | None, known_cards: frozenset[str], merged: Mapping[str, str | None]) -> Effective`;
  - `@dataclass(frozen=True) EntityResolver(marks: Mapping[str, MemoryEntityMark], known_cards: frozenset[str], merged: Mapping[str, str | None])` з методами:
    - `of(claim_id, category, participant_ids, location_ids) -> Effective`;
    - `item(item: MemoryItem) -> MemoryItem` (через `dataclasses.replace`; `section=='core'` вважається `character_states`);
    - `items(items) -> tuple[MemoryItem,...]`;
    - `bare() -> EntityResolver` (те саме без `marks`);
  - `projection.candidate_events(journal) -> dict[str, MemoryEvent]` (активні записи й `_timeline_events`).

- [ ] **Step 1: Write the failing tests**

```python
# кожна тестова функція має власний @pytest.mark.req('MEMORY-ENTITIES') (як у PR 1); нижче декоратори опущено для стислості
M = lambda p=(), l=(), s='model': MemoryEntityMark(participant_ids=list(p), location_ids=list(l), source=s)
K = frozenset({'c1', 'c2'})

def test_author_mark_wins_over_the_event_even_when_empty():
    e = effective('facts', ['c2'], [], M([], [], 'author'), K, {})
    assert e.participant_ids == () and e.participants_from == 'author'

def test_event_wins_over_a_model_mark_and_model_fills_the_gap():
    e = effective('facts', ['c1'], [], M(['c2'], ['l1']), K, {})
    assert (e.participant_ids, e.participants_from) == (('c1',), 'event')
    assert (e.location_ids, e.locations_from) == (('l1',), 'model')

def test_unknown_participant_is_dropped_before_the_non_empty_check():
    # подія лише з видаленим 'gone' → учасники з моделі; без моделі → порожньо (запасний пошук за іменем)
    assert effective('facts', ['gone'], [], M(['c2']), K, {}).participant_ids == ('c2',)
    assert effective('facts', ['gone'], [], None, K, {}).participant_ids == ()

def test_state_takes_only_locations_from_the_mark():
    e = effective('character_states', [], [], M(['c1'], ['l1']), K, {})
    assert e.participant_ids == () and e.location_ids == ('l1',)

def test_locations_follow_merges():
    assert effective('facts', [], ['old'], None, K, {'old': 'new'}).location_ids == ('new',)

def test_source_is_the_weakest_contributor():  # Р7: author / model / event / None
    assert effective('facts', ['c1'], [], M([], ['l1']), K, {}).source == 'model'
    assert effective('facts', ['c1'], [], None, K, {}).source == 'event'
    assert effective('facts', [], [], None, K, {}).source is None

def test_resolver_replaces_item_entities_and_bare_ignores_marks():
    # item('f1','facts',…) з participant_ids ('gone',) і marks {'f1': M(['c1'])} → item(...).participant_ids == ('c1',);
    # bare().item(...) → ()

def test_story_without_marks_keeps_its_payload_byte_for_byte():
    assert 'memory_entities' not in Story(...).model_dump_json()   # конструктор як у наявних тестах domain

def test_mark_rejects_duplicates_and_too_many_marks():
    # MemoryEntityMark(participant_ids=['c1','c1'], …) → ValidationError; Story з 20 001 записом → ValidationError

def test_candidate_events_cover_candidate_claim_ids():
    # журнал з активним фактом, хронологією й legacy-закриттям лінії: set(candidate_events(j)) == candidate_claim_ids(j)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/memory/test_entities_effective.py -q`
Expected: FAIL (`ModuleNotFoundError: storygen.memory.entities`).

- [ ] **Step 3: Implement**

- `MemoryEntityMark(DomainModel)`: валідатор «без повторів і порожніх ID» з повідомленням «Некоректна розмітка сутностей».
- `Story.memory_entities = Field(default_factory=dict, max_length=20000, exclude_if=lambda v: not v)`.
- `effective`. Збираються кандидати поля в порядку `author`, `event`, `model`, а потім береться перший:

```python
def pick(event_ids, mark_ids, clean):
    if mark and mark.source == 'author':
        return clean(mark_ids), 'author'
    for ids, source in ((event_ids, 'event'), (mark_ids if mark else (), 'model')):
        ids = clean(ids)
        if ids:
            return ids, source
    return (), None
```

  Для учасників `clean` = унікальні ID з `known_cards` у первісному порядку. Для локацій `clean` = унікальні `canonical(merged, id)`. Для `character_states` учасники `((), None)` без виклику `pick`.
- Модуль без IO (імпорти лише `locations.canonical`, `projection.MemoryItem`, `domain.MemoryEntityMark`).
- SPEC.MD:
  - технічний опис «Накладка» (поле, ліміт, порядок, Р4–Р5, канонізація, І3);
  - Scenario `MEMORY-ENTITIES-S05 — Накладка й чинні сутності запису`:
    - GIVEN запис пам'яті й запис накладки за його `claim_id`;
    - WHEN читаються чинні сутності запису;
    - THEN для кожного поля SHALL братися поле автора, інакше непорожнє поле події, інакше непорожнє поле моделі;
    - AND невідомий ID картки SHALL відкидатися до цього вибору, локація SHALL канонізуватися за злиттями, а журнал, `claim_id` і докази SHALL не змінюватися.
  - traceability: цей файл.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/memory -q`
Expected: PASS (наявні тести `candidate_claim_ids` без змін).

- [ ] **Step 5: Commit**

`git commit -m "feat(memory): накладка сутностей і чинні сутності записів (MEMORY-ENTITIES-S05)"`

### Task 2: Збереження накладки й API правки

**Files:**
- Create: `src/storygen/storage/memory_entities.py`
- Modify: `src/storygen/storage/repository.py` (методи-обгортки поряд з `update_memory_kind`)
- Create: `src/storygen/web/routes_memory_entities.py`; Modify: `src/storygen/web/app.py` (`include_router`)
- Modify: `SPEC.MD` (MEMORY-ENTITIES: опис збереження й API, Scenario S06), `docs/verification/traceability.json`
- Test: `tests/storage/test_memory_entities_store.py`

**Interfaces:**
- Consumes: Task 1 `MemoryEntityMark`, `Story.memory_entities`, `candidate_events`, `EntityResolver`.
- Produces:
  - `book_claims(view, story_id) -> dict[str, MemoryEvent]` (Р9);
  - `entity_resolver(view, story) -> EntityResolver` (картки — ID з `load_characters(story.characters_version_id)` або `frozenset()`; `merged` з `view.locations`);
  - `update_memory_entities(repo, story_id, claim_id, participant_ids: list[str], location_ids: list[str] | None, expected_revision: int) -> Story`;
  - `apply_entity_marks(repo, story_id, marks: Mapping[str, tuple[list[str], list[str]]], expected_revision: int) -> tuple[Story, list[str]]` (другий елемент — `claim_id`, записані цим пакетом);
  - `clear_entity_marks(repo, story_id, expected_revision: int, source: Literal['model'] = 'model') -> Story` (прибирає всі записи `source='model'`; параметр — як у §2.3, інших значень у 2a немає, Р15);
  - `Repository.update_memory_entities / apply_entity_marks / clear_entity_marks` з тими самими параметрами без `repo`;
  - HTTP:
    - `PUT /api/stories/{id}/memory-entities` з тілом `{claim_id, participant_ids, location_ids | null, expected_revision}` повертає Story;
    - `POST /api/stories/{id}/memory-entities/clear` з тілом `{expected_revision}` повертає Story.

- [ ] **Step 1: Write the failing tests** (фікстура: `story_with_memory` з `tests/generation/test_context_selection.py`, доповнена версією карток `A`, `B` (ID складу фікстури) і карткою локації `l1`; хелпер `claim(journal, text)` з `tests/generation/test_memory_kind.py`)

```python
# кожна тестова функція має власний @pytest.mark.req('MEMORY-ENTITIES') (як у PR 1); нижче декоратори опущено для стислості

def test_author_edit_is_stored_with_cas_and_without_journal_changes(tmp_path):
    # update_memory_entities(..., ['A'], ['l1'], rev) → story.memory_entities[cid] == MemoryEntityMark(['A'],['l1'],'author'),
    # revision+1; голова пам'яті сцени (version id і sha256) та сама; повтор тих самих значень → revision не змінюється
def test_author_edit_replaces_both_fields(tmp_path):
    # Р16: PUT (['A'], []) для факту з подією location_ids ['l1'] → чинні локації порожні; клієнт передає обидва поля повністю
def test_location_none_removes_the_mark(tmp_path):        # будь-якого джерела; ключа cid більше немає
def test_stale_revision_is_a_conflict(tmp_path):          # expected_revision-1 → RevisionConflict, для всіх трьох функцій
def test_unknown_claim_card_or_location_is_refused(tmp_path):
    # 'nope' → «Запису немає в пам’яті твору»; ['zz'] → «Невідомий персонаж…»; ['lz'] → «Невідома локація…»
def test_author_participants_on_a_state_are_refused(tmp_path):  # «Учасники дозволені лише для ліній, фактів і хронології»
def test_model_batch_never_overwrites_the_author(tmp_path):
    # автор розмітив f1; apply_entity_marks({f1:(['B'],[]), f2:(['A'],[])}) → f1 без змін, f2 source 'model', applied == ['f2']
def test_model_batch_stores_no_participants_for_a_state(tmp_path):  # стан s1 з (['A'],['l1']) → MemoryEntityMark([], ['l1'], 'model')
def test_model_batch_with_an_unknown_claim_is_refused_whole(tmp_path):  # Р10: нічого не записано, revision та сама
def test_clear_removes_only_model_marks(tmp_path):
def test_too_many_marks_are_refused(tmp_path):            # monkeypatch MAX_ENTITY_MARKS=1 → «Забагато записів розмітки сутностей»
def test_book_claims_take_timeline_and_records_of_every_head(tmp_path):
    # запис хронології й активний факт сцени 1 є в book_claims, коли голова сцени 2 містить їх теж; закритий стан — ні
def test_memory_entities_http(tmp_path):
    # TestClient: PUT → 200 і story.revision; PUT зі старою ревізією → 409; невідомий claim → 400; POST clear → 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/storage/test_memory_entities_store.py -q`
Expected: FAIL (`ModuleNotFoundError: storygen.storage.memory_entities`).

- [ ] **Step 3: Implement**

- Кожна функція працює за схемою `update_memory_kind`:
  1. `BEGIN IMMEDIATE`;
  2. `repo._active_story`;
  3. CAS із повідомленням «Твір уже змінено. Оновіть таблицю; розмітку сутностей не збережено.»;
  4. перевірки через `ContextView(repo, db, story_id)`;
  5. `story.model_copy(update={'memory_entities': marks, 'revision': revision+1})`, а без змін — повернення `story`.
- `MAX_ENTITY_MARKS = 20000`.
- `book_claims`: сцени без `trashed_at` за `position` спаданням; журнал голови `memory` через `memory.kinds._journal`; перший побачений `claim_id` перемагає.
- Перевірки виконуються в такому порядку: `claim_id` ∈ `book_claims`, учасники ⊆ ID карток, локації ⊆ `view.locations` (будь-яка, зокрема злита), стан з учасниками. Для автора помилка, для моделі `[]` (Р6).
- Маршрути: моделі тіла `DomainModel` з `claim_id: Field(min_length=1, max_length=200)`, списками до 200 елементів і `expected_revision: int`.
- SPEC.MD:
  - опис трьох функцій, Р6, Р9, Р10, HTTP;
  - Scenario `MEMORY-ENTITIES-S06 — Правка накладки`:
    - GIVEN твір із пам'яттю;
    - WHEN автор зберігає сутності запису або пакет моделі застосовує розмітку;
    - THEN запис автора SHALL мати `source='author'`, пакет моделі SHALL не перезаписувати його, а скасування SHALL прибирати лише записи моделі;
    - AND кожна зміна SHALL бути CAS на ревізію твору (409 при конфлікті, ревізія без змін при повторі), а невідомий запис, персонаж чи локація SHALL давати 400.
  - traceability.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/storage tests/web -q`
Expected: PASS.

- [ ] **Step 5: Commit**

`git commit -m "feat(memory): збереження накладки сутностей і API правки (MEMORY-ENTITIES-S06)"`

### Task 3: Накладка у відборі й звуженому каталозі

**Files:**
- Modify: `src/storygen/generation/context.py` (замикання `selection_input()` ≈ рядок 555; `narrower()` ≈ рядок 448)
- Modify: `src/storygen/memory/selection.py` (`narrow_catalog(..., place=(), entities: EntityResolver | None = None)`)
- Create: `tests/generation/golden/memory_request_no_cards.json`, `tests/generation/cardless_memory.py`
- Modify: `SPEC.MD` (MEMORY-SELECT: «учасник сцени» і шар `place` — за чинними сутностями; MEMORY-LOCATIONS: посилання на накладку локацій і обмеження «накладка не повертає в проєкцію стан відсутнього»), `docs/verification/traceability.json`
- Test: `tests/memory/test_selection_entities.py`, `tests/generation/test_context_entities.py`

**Interfaces:**
- Consumes: Task 1 `EntityResolver.items/of`; Task 2 `entity_resolver(view, story)`, `Repository.apply_entity_marks`.
- Produces: `narrow_catalog(..., entities=None)` (без резолвера — поля події, як зараз; це потрібно бенчмарку).

- [ ] **Step 1: Write the failing tests** (хелпери `inp`, `item`, `layer_of` з `tests/memory/test_selection.py`)

```python
# tests/memory/test_selection_entities.py
# кожна тестова функція має власний @pytest.mark.req('MEMORY-ENTITIES') (як у PR 1); нижче декоратори опущено для стислості

def test_model_mark_puts_a_thread_without_participants_into_threads():
    # лінія без participant_ids і без згадки імені; resolver з marks {t: M(['a'])}, 'a' у складі → classify(inp(resolver.items(items))) → 'threads'
def test_overlay_location_puts_a_fact_into_place():          # M([], ['l1']), inp.place ∋ 'l1' → 'place'
def test_deleted_participant_falls_back_to_names():
    # подія facts з ('gone',) і текстом зі згадкою учасника сцени → після resolver.items(...) шар 'facts' (не 'fts')
def test_author_empty_override_falls_back_to_names():         # подія ('x',), автор [] → класифікація за основами імен
def test_old_timeline_with_an_overlay_participant_goes_to_past():  # хронологія сцени 2 при 40, M(['a']) → 'past'
def test_record_without_any_entities_is_classified_as_before():
    # набір scene_items() через resolver з порожніми marks дає ті самі шари, що без resolver (І2)
def test_narrow_catalog_keeps_facts_and_states_by_the_overlay():
    # факт без учасників і без згадки з M(['a']) лишається; стан відсутнього з M([], ['l1']) при place {'l1'} лишається;
    # без entities ті самі записи не лишаються

# tests/generation/test_context_entities.py — так само @pytest.mark.req('MEMORY-ENTITIES') на кожній функції
def test_fitting_request_with_marks_is_byte_identical(tmp_path):
    # story_with_memory + apply_entity_marks: build_context(brief, settings()) — user_text і fingerprint ті самі, що до розмітки;
    # те саме для етапу memory, що вміщається (фікстура test_memory_stage_narrow, role() без ліміту): user_text і bounds ті самі
def test_overflowing_request_selects_by_the_overlay(tmp_path):
    # tight(repo, scene): факт COAST (категорія facts у фікстурі) без згадок → після M(['B']) ('B' у складі, не відстежуваний) COAST у memory_section, projection_version SELECTED_PROJECTION
def test_overlay_location_does_not_return_an_absent_state_to_the_projection(tmp_path):
    # стан відсутнього персонажа з M([], [локація сцени]) → немає в повній проєкції; omitted_state_count той самий (Р3)
def test_narrowed_memory_stage_uses_the_overlay(tmp_path):
    # фікстура tests/generation/test_memory_stage_narrow.py::story: факт з M(['a']) потрапляє в звужений каталог
def test_memory_request_without_cards_matches_the_golden(tmp_path):
    # cardless_memory_request(tmp_path) == json.loads(golden) — user_text, bounds, schema після normalize_ids (І6)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/memory/test_selection_entities.py tests/generation/test_context_entities.py -q`
Expected: FAIL (тести еталона — через відсутній файл).

- [ ] **Step 3: Produce the golden from main before PR 1 (Р13)**

- Окремий модуль `tests/generation/cardless_memory.py`, що імпортує лише API, наявні в `a9c0e37c` (`Repository`, `StoryCreate`, `SceneCreate`, `MemoryJournal`, `_add_event`, `build_context`, `memory_wire_v4_schema`), а не модулі PR 2. Тест `test_context_entities.py` імпортує його. Модуль містить:
  - `cardless_memory_request(tmp_path) -> dict[str, str]`: книга без карток, одна сцена з прозою й попередньою пам'яттю;
  - `normalize_ids(text, ids) -> str`: кожен ID твору, сцен і версій, а також кожен `mc_…`/`me_…` (`claim_id` і `event_id` похідні від ID версії прози через `claim_owner`, тож без нормалізації вони різні в кожному прогоні) заміняється на `<id0>`, `<id1>`… у порядку першої появи.

  Хелпер повертає `{'user_text', 'bounds': fragments['memory_schema_bounds'], 'schema': json.dumps(memory_wire_v4_schema(bounds), sort_keys=True)}` після нормалізації.
- Еталон: `git worktree add --detach C:/tmp/me2g a9c0e37c`, junction `.venv` → основна тека; скопіювати туди лише `tests/generation/cardless_memory.py`.
- `python -c "from tests.generation.cardless_memory import cardless_memory_request; …"` з `C:/tmp/me2g` пише JSON у `tests/generation/golden/memory_request_no_cards.json` цієї гілки.
- Потім `cmd /c rmdir C:\tmp\me2g\.venv` і `git worktree remove C:/tmp/me2g`.

- [ ] **Step 4: Implement**

- `context.py`, `selection_input()`: `items = entity_resolver(view, story).items(items)` перед `SelectionInput(...)`, де `view = repo if hasattr(repo, 'peek_scene') else repo.context_view(story.id)` (як у `kinds()`). `memory_items` і `project_memory` не змінюються.
- `narrower()`: `narrow_catalog(..., place=scene_place(repo, scene), entities=entity_resolver(view, story))`.
- `narrow_catalog`: для кожної події `e = entities.of(event.claim_id, event.category, event.participant_ids, event.location_ids) if entities else Effective-з-події`. Правила стану, факту й місця беруть `e.participant_ids` і `e.location_ids`.
- Окіл сцени (`neighbourhood`) містить і злиті, і канонічні ID. Тому канонізація локацій події в `effective` не змінює збігу з `place` для запису без накладки (І2).
- SPEC.MD:
  - MEMORY-SELECT, технічний опис `classify`: «за чинними сутностями ([MEMORY-ENTITIES](#memory-entities)): автор → подія → модель; невідомий учасник відкидається».
  - Відоме обмеження про основи імен: «для записів без чинних учасників».
  - MEMORY-LOCATIONS: шар `place` і `narrow_catalog` беруть чинні `location_ids`; фільтр проєкції — лише локації події (Р3).
  - Scenario `MEMORY-ENTITIES-S07 — Відбір і застарілість з накладкою` (THEN про застарілість додає Task 4):
    - GIVEN запис із накладкою;
    - WHEN пам'ять сцени відбирається під бюджет або каталог етапу memory звужується;
    - THEN шари й звужений каталог SHALL брати чинні сутності запису;
    - AND запит, що вміщається, SHALL лишатися байт у байт тим самим, фільтр проєкції за складом SHALL не брати локацій накладки, а книга без карток SHALL мати запит memory, як до учасників.
  - traceability.

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/memory tests/generation tests/retrieval_bench -q`
Expected: PASS. Наявні тести відбору й бенчмарку без змін.

- [ ] **Step 6: Commit**

`git commit -m "feat(memory): накладка сутностей у відборі й звуженому каталозі (MEMORY-ENTITIES-S07)"`

### Task 4: Застарілість версій від накладки

**Files:**
- Modify: `src/storygen/dependency_models.py` (`'memory_entities'` в `allowed['scene']`; коментар до `expected`)
- Modify: `src/storygen/storage/memory_entities.py` (`entities_value`), `src/storygen/storage/snapshots.py::selector_value` (гілка поряд із `memory_kind_overrides`)
- Modify: `src/storygen/generation/context.py::_finish_context` (≈ рядок 238)
- Modify: `SPEC.MD` (MEMORY-ENTITIES: опис селектора; S07 доповнити THEN про застарілість; розділ власника/сумісність: старі знімки без селектора), `docs/verification/traceability.json`
- Test: `tests/generation/test_memory_entities_staleness.py`

**Interfaces:**
- Consumes: Task 1 `EntityResolver.bare`, `candidate_events`; Task 2 `entity_resolver`, `apply_entity_marks`, `update_memory_entities`.
- Produces:
  - `entities_value(view, scene_id) -> dict[str, str]` (Р8): кандидати попередньої пам'яті сцени (`previous_memory(..., peek=True, require=False)` + `read_previous_journal`, як у `kinds.kind_overrides`), лише ті, де пара `(participant_ids, location_ids)` з `resolver.of(...)` відрізняється від тієї самої пари з `resolver.bare().of(...)` (джерела `*_from` не порівнюються), значення `f"p={','.join(e.participant_ids)};l={','.join(e.location_ids)}"`, ключі за зростанням;
  - селектор `DependencySelector(kind='scene', owner_id=scene.id, field='memory_entities', expected=entities_value(...))`.

- [ ] **Step 1: Write the failing tests** (хелпери `tight`, `claim`, `COAST` з `tests/generation/test_memory_kind.py`; фікстура з картками з Task 2)

```python
# кожна тестова функція має власний @pytest.mark.req('MEMORY-ENTITIES') (як у PR 1); нижче декоратори опущено для стислості

def test_fitting_request_records_no_entities_selector(tmp_path):
def test_selected_version_records_the_selector_and_goes_stale_on_a_mark(tmp_path):
    # selected = build_context(brief, tight).dependency_snapshot; selector memory_entities expected == {}
    # apply_entity_marks({COAST: (['B'], [])}) → compare_snapshot дає зміну з current == {COAST: 'p=B;l='}
def test_narrowed_memory_stage_records_the_selector(tmp_path):  # фікстура test_memory_stage_narrow; 'narrow' у metrics → селектор є
def test_shadowed_model_mark_does_not_stale(tmp_path):
    # подія вже має participant_ids ['A']; модель дає (['B'], []) → entities_value == {}, compare_snapshot без зміни memory_entities
def test_author_mark_equal_to_the_event_does_not_stale(tmp_path):  # автор зберіг ті самі ID, що в події → entities_value == {}
def test_author_override_and_clearing_stale_the_version(tmp_path):
    # update_memory_entities → зміна; clear_entity_marks після моделі → значення знову {}
def test_mark_of_a_claim_absent_before_the_scene_does_not_stale(tmp_path):  # перша сцена: entities_value == {}
def test_old_snapshot_without_the_selector_is_not_compared(tmp_path):
    # знімок без селектора memory_entities + розмітка → compare_snapshot без змін memory_entities
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/generation/test_memory_entities_staleness.py -q`
Expected: FAIL (`Невідомий селектор залежностей`).

- [ ] **Step 3: Implement**

- `_finish_context`: окремо від блоку `'selection'`, але поряд із ним: `if scene and ('selection' in memory_metrics or 'narrow' in memory_metrics): snapshot.selectors.append(...)`. Обчислювати тут, а не через `memory_selector`, бо rewrite повертається в `make_context` з базовими метриками (та сама причина, що для `memory_kind_overrides`).
- `selector_value`: `if kind=='scene' and field=='memory_entities': return entities_value(view, owner)`.
- `entities_value` читає лише через `peek_*`, як `kind_overrides`. Нечитна пам'ять дає `{}`.
- SPEC.MD:
  - опис селектора (Р8, умова `selection`/`narrow`, кандидати лише до сцени, відсутній селектор не порівнюється);
  - S07 доповнити: «AND зміна накладки SHALL робити застарілими лише версії, зібрані з відбором чи звуженим каталогом, і лише коли змінилися чинні сутності кандидатів, активних до сцени»;
  - traceability S07 — тести Task 3 і цього файла.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/generation tests/storage -q`
Expected: PASS.

- [ ] **Step 5: Commit**

`git commit -m "feat(memory): селектор scene/memory_entities для версій з відбором (MEMORY-ENTITIES-S07)"`

### Task 5: Чинні сутності в рядку таблиці пам'яті; SPEC

**Files:**
- Modify: `src/storygen/memory/forwarding.py:86-109` (рядок `memory-view`)
- Modify: `SPEC.MD` (MEMORY-ENTITIES: опис рядка таблиці; сумісність §7 і обмеження §9 для накладки; S04 не змінюється), `docs/verification/traceability.json` (S05/S07 доповнити тестами цього файла)
- Test: `tests/memory/test_memory_view_entities.py`

**Interfaces:**
- Consumes: Task 1 `Effective`; Task 2 `entity_resolver`.
- Produces: нові поля рядка `memory-view` для інтерфейсу PR 3:
  - `participant_ids: list[str]` і `location_ids: list[str]` (чинні; локації канонічні);
  - `entities_source: 'event' | 'model' | 'author' | None` (Р7);
  - `participants` і `locations` беруться з чинних ID.

- [ ] **Step 1: Write the failing tests** (хелпери `setup`, `remember_with` з `tests/memory/test_memory_view_participants.py`)

```python
# кожна тестова функція має власний @pytest.mark.req('MEMORY-ENTITIES') (як у PR 1); нижче декоратори опущено для стислості

def test_row_shows_overlay_participants_and_locations(tmp_path):
    # запис без учасників + apply_entity_marks (['c1'], [l1]) → row['participants'] == [ім'я c1], row['locations'] == [шлях l1],
    # row['participant_ids'] == ['c1'], row['entities_source'] == 'model'
def test_author_mark_is_shown_as_author(tmp_path):            # entities_source == 'author'
def test_event_entities_are_shown_as_event_and_unmarked_as_none(tmp_path):
def test_row_drops_a_deleted_participant_id(tmp_path):        # participant_ids ['gone'] → participant_ids == [], без винятку
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/memory/test_memory_view_entities.py -q`
Expected: FAIL (`KeyError: 'entities_source'`).

- [ ] **Step 3: Implement**

- У `memory_view_from_view`: `resolver = entity_resolver(view, story)`; для кожного запису `e = resolver.of(event.claim_id, event.category, event.participant_ids, event.location_ids)`.
- Поля рядка: `'locations': places(e.location_ids)`, `'participants': [names[id] for id in e.participant_ids if id in names]`, `'participant_ids': list(e.participant_ids)`, `'location_ids': list(e.location_ids)`, `'entities_source': e.source`.
- `memory-table.js` не змінюється: він уже показує `participants` і `locations`.
- SPEC.MD:
  - рядок таблиці (нові поля, Р7);
  - сумісність: «непорожня накладка робить книгу нечитною для старішої Obscura; повернення лише з резервної копії; старі знімки без `scene/memory_entities` не застарівають»;
  - відомі обмеження: «розмітка моделі може помилятися — виправлення поштучне через `PUT /memory-entities`; накладка не повертає в проєкцію стан відсутнього персонажа»;
  - переглянути технічний опис PR 1 «стара пам'ять без учасників до PR 2» і замінити його на «до розмітки (PR 2b)».

- [ ] **Step 4: Run checks**

Run: `python -m pytest tests/memory tests/web -q`, `node tests/web/js/memory-table.mjs`, `python scripts/check_docs.py`
Expected: PASS, `check_docs` зелений.

- [ ] **Step 5: Commit**

`git commit -m "feat(memory): чинні сутності в таблиці пам'яті; SPEC накладки"`

### Завершення PR 2a

- [ ] `python scripts/verify.py` з `C:/tmp/me2a` (detached worktree на HEAD, junction на `.venv` і `frontend/node_modules`; перед `git worktree remove` — `cmd /c rmdir` для junction). В опис PR — коміт і passed/failed/errors/skipped. `docs/STATUS.md` не комітити.
- [ ] В опис PR: сайт не змінюється (Р11), еталон І6 знято з `a9c0e37c` (Р13), список PR 2b.
- [ ] Перехресна рецензія гілки (`npx -y @ysilvestrov/detent cross-review --author claude`). PR на `main` (Р14), без «Closes #N»: серія не завершена. Злиття — за правилом серії memory-entities: самозлиття PR серії, останній лишається власнику. Потім оновити основну теку.
- [ ] Наскрізне рев'ю ядра (pr-slicing, крок 3): записати висновки в журнал виконання. Лише після цього пишеться план PR 2b від коду, як він є.

## Self-review

- **Покриття специфікації (частина 2a):**
  - §2.3 модель, порядок, невідомі ID, канонізація — Task 1;
  - CAS-функції, ліміт, 400/409, І4 — Task 2;
  - §3 накладка в шарах і `narrow_catalog`, фільтр проєкції без накладки (рев'ю спеки № 3) — Task 3;
  - селектор для `selection` і `narrow` (рев'ю спеки № 2) — Task 4;
  - §5 API правки й поля рядка — Task 2, Task 5;
  - §7 і §9 — Task 5;
  - І1, І2, І6 — Task 3; І3 — Task 1 і Task 2; І4 — Task 2. І5 і І7 — PR 2b і чинні тести шарів.
  - §4 і §6 свідомо в PR 2b (див. «Поділ»).
- **Зауваження рев'ю PR 1:** запасний пошук за іменем при видаленому учаснику (Р4, Task 1 і Task 3); слабкий тест І6 (Р13, Task 3).
- **Узгодженість типів:** `EntityResolver.of/items/bare`, `entity_resolver(view, story)`, `apply_entity_marks(...) -> tuple[Story, list[str]]`, `entities_value(view, scene_id) -> dict[str, str]` однакові в Task 1–5. `narrow_catalog(..., entities=None)` зберігає виклик бенчмарку.
- **Пропорція:** код — лише алгоритм вибору поля (`pick`), решта — сигнатури, значення й тести.
