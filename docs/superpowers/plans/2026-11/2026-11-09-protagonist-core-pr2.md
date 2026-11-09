# Ядро протагоніста, PR 2: панель «було → стало» — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** автор бачить під пам'яттю сцени, що змінилося в ядрі протагоніста і які лінії закрито, і підтверджує це або виправляє.

**Architecture:** Робота спирається на PR 1 у тому вигляді, в якому його змерджено (#54, a7379d3).
- Підтвердження зберігається як адитивне поле `VersionRef.memory_confirmation` і ставиться через CAS на голову memory.
- Diff ядра й ліній рахується чистою функцією. Вона replay-ить журнал попередньої сцени й голову memory, а `reason` бере з captured wire-відповіді спроби.
- Правки автора будують новий журнал:
  - з wire-відповіді, де правки «Лишити попереднє» вже накладено;
  - або з журналу голови, якщо wire-відповіді немає;
  - поверх цього накладаються події `author`.

  Новий журнал зберігається спільним шляхом ручного збереження і одразу підтверджується.
- Панель — окремий JS-модуль у вкладці «Пам'ять».

**Tech Stack:** Python 3 / FastAPI / pydantic; vanilla ES modules (`src/storygen/web/static`); тести pytest, `tests/web/js/*.mjs`, Playwright.

**Spec:** [docs/superpowers/specs/2026-11/2026-11-09-protagonist-core-memory-design.md](../../specs/2026-11/2026-11-09-protagonist-core-memory-design.md), розділ «Підтвердження (PR 2)». Вхід від фінального огляду PR 1: обмеження «слоти невідстежуваного персонажа заморожені» в SPEC.MD MEMORY-002 і порожній рядок доказу для записів автора без цитати.

## Global Constraints

- `MemoryConfirmation{confirmed_at, by:'author'}` — окреме персистентне поле версії memory. Байти журналу не змінюються. Поле не входить у порівняння залежностей, fingerprint MEMORY-REUSE і хеші: підтвердження не робить застарілою наступну сцену.
- `GET /api/scenes/{id}/core-review` повертає diff голови memory відносно журналу попередньої сцени: зміни слотів, рішення `unknown` з `reason`, закриті лінії, стан підтвердження.
- `POST /api/scenes/{id}/core-review` приймає `{expected_revision, memory_version_id, edits[]}`:
  - без `edits` ставить підтвердження на поточну голову memory, а якщо голова змінилась, повертає 409;
  - з `edits` створює нову версію memory шляхом ручного збереження, публікує її і ставить їй підтвердження.
- Перебудова з wire-відповіді:
  - «Лишити попереднє» перетворює слот на `unchanged`, а лінію — на `open`;
  - «Вписати…» дає запис `author` з цитатою з префікса або без неї;
  - перебудовані події знову перевіряються інваріантами І1–І4, ліміти MEMORY-002 на кількість `add` до правок автора не застосовуються.
- Без captured wire v4 правки накладаються як події `author` поверх журналу голови, і «Лишити попереднє» недоступне.
- Панель стоїть під пам'яттю: рядки «без змін» і «лишається» згорнуті, а зміни, `unknown` і закриття розгорнуті. Дії над рядком: «Прийняти», «Лишити попереднє», «Вписати…». «Вписати…» — це значення плюс необов'язкова цитата зі сцени префікса, яку вибирають через пошук фрагмента. Мітки UA/EN.
- Автоматичний режим не перевіряє підтвердження. Readiness показує кількість сцен із непідтвердженим ядром як інформацію, а не як блок.
- SQL-міграції немає.
- Правила проєкту (AGENTS.md):
  - SPEC.MD оновлюється в тому самому коміті;
  - кожен новий Scenario має сталий ID, `<a id>` і запис у `docs/verification/traceability.json`;
  - документація для користувача — українською та англійською, узгоджено; зображення — з нейтральними прикладами;
  - `python scripts/check_docs.py` проходить без помилок.

## Review Focus

1. **Голова memory змінилась між GET і POST** (паралельна генерація, ручна правка в іншій вкладці). POST з правками чи без повертає 409 і нічого не зберігає → `test_post_conflict_when_head_changed` (Task 1 — без правок, Task 3 — з правками).
2. **Перша сцена твору або голова без ядра** (старий журнал, попередньої сцени немає). GET повертає порожні `slots` і лише лінії, панель показує «ядро ще не заповнене» і не падає → `test_core_review_first_scene_and_legacy_journal` (Task 2).
3. **Відповідь моделі в спробі не читається.** Wire-відповідь обгорнута в fence, спроба видалена, або голову створено вручну. Тоді `has_wire=false`, `reason` порожні, «Лишити попереднє» вимкнене, POST з `keep` дає 422 → `test_core_review_without_wire` (Task 2), `test_keep_rejected_without_wire` (Task 3).
4. **Підтверджена голова, яку потім перегенерували або змінили.** Нова голова показується непідтвердженою, стара зберігає своє поле. Підтвердження не робить застарілою пам'ять наступної сцени → `test_confirmation_does_not_stale_next_scene`, `test_new_head_is_unconfirmed` (Task 1).
5. **«Вписати…» з цитатою, якої немає в прозі префікса**, або з цитатою з пізнішої сцени. Відповідь 422 з українським повідомленням, нову версію не створено → `test_author_quote_must_be_in_prefix` (Task 3).

---

### Task 1: Метадані підтвердження і CAS

**Files:**
- Змінити: `src/storygen/domain.py` (`MemoryConfirmation`, поле `VersionRef.memory_confirmation: MemoryConfirmation | None = None`), `src/storygen/storage/repository.py` (`confirm_memory`)
- Тести: `tests/storage/test_memory_confirmation.py`

**Interfaces:**
- Produces: `class MemoryConfirmation(DomainModel): confirmed_at: str; by: Literal['author']='author'`.
- Produces: `Repository.confirm_memory(scene_id: str, version_id: str, expected_revision: int) -> VersionRef`. Під `BEGIN IMMEDIATE`:
  - перевіряє, що сцена активна, `scene.revision == expected_revision` і `scene.heads['memory'] == version_id`;
  - інакше кидає `RevisionConflict('Пам’ять сцени вже змінилась. Оновіть панель; підтвердження не збережено.')`;
  - переписує JSON рядка `versions` з полем `memory_confirmation`, не чіпаючи файл і `sha256`;
  - ревізію сцени не змінює.

- [ ] **Крок 1: тести, що падають**

```python
def test_confirm_sets_field_without_touching_bytes()      # sha256 і read_text незмінні; get_version(...).memory_confirmation.by=='author'
def test_post_conflict_when_head_changed()                 # confirm на не-голову або зі старою ревізією -> RevisionConflict, поле не з'явилось
def test_confirmation_does_not_stale_next_scene()          # пам'ять сцени 2 свіжа (stale False, compare_snapshot без причин) до і після confirm сцени 1
def test_new_head_is_unconfirmed()                         # нова голова memory має memory_confirmation None; стара версія свого не втратила
def test_confirmation_not_in_reuse_fingerprint()           # MEMORY-REUSE fingerprint (memory/reuse.py) однаковий до і після confirm
```

- [ ] **Крок 2:** `pytest tests/storage/test_memory_confirmation.py -q`. Очікується: FAIL.
- [ ] **Крок 3:** реалізувати за інтерфейсами. Перевірити grep-ом, що жоден селектор чи хеш у `storage/snapshots.py`, `generation/dependencies.py`, `memory/reuse.py` не серіалізує весь `VersionRef`. Якщо такий є, виключити з нього поле.
- [ ] **Крок 4:** `pytest tests/storage tests/memory -q --basetemp=C:/Users/yuriy/AppData/Local/Temp/pc2-t1`. Очікується: PASS.
- [ ] **Крок 5:** SPEC.MD:
  - новий Requirement MEMORY-CONFIRM із Scenario S01 «Підтвердження не робить застарілою наступну сцену» → `test_confirmation_does_not_stale_next_scene`;
  - Scenario S02 «Конфлікт голови» → `test_post_conflict_when_head_changed`;
  - traceability.
- [ ] **Крок 6:** коміт `feat(memory): memory confirmation metadata and CAS (#41)`.

### Task 2: Diff ядра й ліній і GET core-review

**Files:**
- Створити: `src/storygen/memory/core_review.py`
- Змінити: `src/storygen/web/routes_versions.py` (GET `/api/scenes/{scene_id}/core-review`, GET `/api/scenes/{scene_id}/core-review/fragments`)
- Тести: `tests/memory/test_core_review.py`, `tests/web/test_core_review_api.py`

**Interfaces:**
- Consumes: `replay_memory`, `core.SLOTS`, `core.tracked_characters`, `storage.snapshots.core_cards`, `journal_before`, `story_time.day_change`, `memory/replay.strip_wrapper`, `decode_memory`, Task 1 `VersionRef.memory_confirmation`.
- Produces: `captured_wire(view, memory_version_id) -> tuple[dict, dict] | None`. Повертає пару (wire-дані v4, `memory_schema_bounds`) зі спроби `stage=='memory'` з `result_version_id==memory_version_id` і `memory_wire_version=='4'`. Сирий текст береться з `partial_path`, дані декодуються після `strip_wrapper`. Будь-яка помилка дає `None`.
- Produces: `core_review(view, scene_id) -> dict`:

```python
{'scene_id','memory_version_id','revision','has_wire':bool,'day_change':bool,
 'confirmation':{'confirmed_at','by'}|None,
 'slots':[{'character_id','name','slot','label','before':str|None,'after':str|None,
           'status':'unchanged'|'changed'|'unknown'|'introduced'|'author',
           'reason':str|None,'reader_unknown':bool}],
 'threads':[{'claim_id','text','status':'open'|'closed','resolution':str|None}]}
```

  - `before` і `after` — активні значення слотів у `journal_before` і в журналі голови.
  - `status` береться з wire-рішення, коли `has_wire`. Інакше він виводиться з diff: значення змінилось → `changed`, значення зникло → `unknown`, подія `author` → `author`.
  - Порядок: персонажі за `tracked`, слоти за реєстром, лінії за порядком появи в `journal_before`. Лінії, додані в цій сцені, йдуть у кінці зі статусом `open`.
- Produces: `prefix_scenes(view, scene_id) -> list[dict]`, тобто `[{'scene_id','scene_number','title','version_id'}]` для активних сцен з позицією ≤ поточної, що мають вибрану прозу.
- Produces: `prefix_fragments(view, scene_id, query: str = '', source_scene_id: str | None = None, limit=50) -> list[dict]`. Працює серед `fragment_text` вибраної прози сцен з позицією ≤ поточної:
  - з `source_scene_id` — лише ця сцена, і вона має бути з префікса, інакше 422;
  - з непорожнім `query` — пошук без урахування регістру;
  - без `query` і без сцени — 422.

  Повертає `[{'version_id','scene_id','scene_number','fragment_id','text'}]`. GET `/api/scenes/{scene_id}/core-review/fragments?scene_id=&q=` і GET `/api/scenes/{scene_id}/core-review/scenes`.

- [ ] **Крок 1: тести, що падають**

```python
def test_core_review_changed_unknown_closed()            # фікстура з v4-спробою: changed одягу, unknown «при собі» з reason, closed лінії -> поля як у Interfaces
def test_core_review_first_scene_and_legacy_journal()    # перша сцена / голова v2 -> slots == [], threads з журналу, без помилки
def test_core_review_without_wire()                       # голова з ручного збереження -> has_wire False, reason None, status з diff
def test_reader_unknown_flag()                            # запис автора без цитати -> reader_unknown True
def test_prefix_fragments_only_up_to_scene()              # фрагмент із пізнішої сцени не повертається; source_scene_id пізнішої сцени -> 422
def test_prefix_fragments_by_scene()                      # source_scene_id без q -> усі фрагменти цієї сцени в порядку тексту
# API: test_get_core_review_route (200, ключі), test_fragments_route_requires_query_or_scene (422 без q і scene_id), test_scenes_route
```

- [ ] **Крок 2:** `pytest tests/memory/test_core_review.py tests/web/test_core_review_api.py -q`. Очікується: FAIL.
- [ ] **Крок 3:** реалізувати. Відповідь GET містить текст пам'яті й прози автора для його власного UI. Логів із цим текстом не писати.
- [ ] **Крок 4:** `pytest tests/memory tests/web -q --basetemp=C:/Users/yuriy/AppData/Local/Temp/pc2-t2`. Очікується: PASS.
- [ ] **Крок 5:** SPEC.MD MEMORY-CONFIRM: Scenario S03 «Diff показує рішення моделі» → `test_core_review_changed_unknown_closed`; traceability.
- [ ] **Крок 6:** коміт `feat(memory): core review diff and fragment search (#41)`.

### Task 3: POST core-review з правками

**Files:**
- Змінити: `src/storygen/memory/core_review.py` (`apply_core_review`), `src/storygen/memory/service.py` (винести `save_memory_journal`), `src/storygen/web/routes_versions.py` (POST)
- Тести: `tests/memory/test_core_review_apply.py`, `tests/web/test_core_review_api.py`

**Interfaces:**
- Consumes: Task 1 `confirm_memory`, Task 2 `captured_wire`, `core_review`, `wire_v4.wire_v4_events`, `journal._add_event` і `_change_event`, `validate_memory_journal`.
- Produces: `save_memory_journal(repo, scene_id, journal, expected_revision) -> VersionRef`. Це перевірка, знімок залежностей, `save_version` і `set_head`, винесені з `save_scene_memory`. `save_scene_memory` після цього лише нормалізує текст і викликає `save_memory_journal`. Поведінка ручного збереження не змінюється, чинні тести проходять без правок.
- Produces: модель тіла `CoreReviewBody{expected_revision:int, memory_version_id:str, edits:list[CoreEdit]=[]}`. Правка — `CoreEdit`:
  - `{'kind':'slot','character_id','slot','action':'keep'|'set','text':str|None,'quote':str|None,'evidence_version_id':str|None}`;
  - `{'kind':'thread','claim_id','action':'keep'|'close','text':str|None,'quote':str|None,'evidence_version_id':str|None}`.

  Для `set` і `close` поле `text` обов'язкове. `quote` без `evidence_version_id` означає цитату з прози поточної сцени.
- Produces: `apply_core_review(repo, scene_id, body) -> dict`, яка повертає новий `core_review`:
  - якщо `edits` порожні, викликає `confirm_memory`;
  - інакше будує базовий журнал. Коли `has_wire`, це `wire_v4_events` над копією wire-даних, де для кожного `keep` слот замінено на `{"status":"unchanged"}`, а лінію — на `{"status":"open"}`. Коли wire немає, це журнал голови, а `keep` дає 422 «Лишити попереднє недоступне: у цієї версії немає відповіді моделі»;
  - поверх базового журналу додає події `source_kind='author'`:
    - слот `set`: `update` активного запису слота або `add` зі `slot`;
    - лінія `close`: `retire` лінії з текстом-розв'язкою, а з цитатою ще й `facts` `add` з `resolves_claim_id`;
  - перевіряє цитату дослівно проти `evidence_version_id or prose_id`. `evidence_version_id` має бути вибраною прозою префікса, інакше 422 «Цитату не знайдено в прозі цієї або попередніх сцен»;
  - викликає `validate_memory_journal`, потім `save_memory_journal` і `confirm_memory` для нової версії. Перевірка ревізії та голови йде до запису: якщо `memory_version_id` не є головою, повертається 409.

- [ ] **Крок 1: тести, що падають**

```python
def test_confirm_without_edits()                       # memory_confirmation на голові, нова версія не створена
def test_keep_unknown_restores_slot()                  # wire unknown «при собі» + keep -> слот активний, атмосферного запису немає, нова голова підтверджена
def test_keep_closed_thread_stays_open()               # closed + keep -> лінія активна, факту-розв'язки немає
def test_set_slot_without_quote_is_reader_unknown()    # set без цитати -> author, quote None; у проєкції письменника суфікс «читачеві невідомо»
def test_author_quote_must_be_in_prefix()              # цитата не з префікса / з пізнішої сцени -> 422, версія не створена
def test_keep_rejected_without_wire()                  # голова без wire + keep -> 422
def test_post_conflict_when_head_changed()             # memory_version_id не голова -> 409, нічого не збережено
def test_edits_make_next_scene_memory_stale()          # після правок пам'ять сцени N+1 stale звичайним механізмом
def test_manual_save_unchanged()                       # чинні тести ручного збереження проходять без змін (запуск tests/memory -k manual)
```

- [ ] **Крок 2:** `pytest tests/memory/test_core_review_apply.py -q`. Очікується: FAIL.
- [ ] **Крок 3:** реалізувати. Помилки домену віддавати HTTP-кодами за наявним у `routes_versions.py` патерном: `RevisionConflict` → 409, `ValueError` → 422.
- [ ] **Крок 4:** `pytest -q --basetemp=C:/Users/yuriy/AppData/Local/Temp/pc2-t3`. Очікується: PASS.
- [ ] **Крок 5:** SPEC.MD MEMORY-CONFIRM: Scenario S04 «Лишити попереднє перебудовує з відповіді моделі» → `test_keep_unknown_restores_slot`; Scenario S05 «Без відповіді моделі лише записи автора» → `test_keep_rejected_without_wire`; traceability.
- [ ] **Крок 6:** коміт `feat(memory): core review edits rebuild the scene journal (#41)`.

### Task 4: Панель у вкладці «Пам'ять»

**Files:**
- Створити: `src/storygen/web/static/core-review.js`, `tests/web/js/core_review.mjs`, `tests/web/browser/core-review.spec.mjs`
- Змінити: `src/storygen/web/static/memory-table.js` (монтування панелі над таблицею; мітка «без цитати» замість порожнього доказу), `src/storygen/web/static/i18n.json`, `src/storygen/web/static/app.css`, `tests/web/browser/server.py` (фікстура сцени з v4-спробою: changed, unknown, closed)

**Interfaces:**
- Consumes: Task 2 GET, Task 3 POST, наявні `api`, `json`, `notice`, `refresh` з `installMemoryTable`.
- Produces: `export function coreReviewModel(review, edits) -> {groups:[{kind:'changed'|'quiet', rows}], canKeep:boolean, dirty:boolean}`. Це чиста функція для unit-тесту: рядки `unchanged`/`open` → `quiet` (згорнута група), інші → `changed`.
- Produces: `export function installCoreReview({container, api, json, notice, refresh}) -> {load(sceneId)}`. Панель:
  - заголовок і стан підтвердження;
  - дії рядка «Прийняти», «Лишити попереднє» (вимкнено, коли `!has_wire`) і «Вписати…»;
  - **«Вписати…» відкриває панель запису** (рішення власника 09.11.2026):
    - поле значення (для лінії — текст розв'язки);
    - вибір сцени з `/core-review/scenes`, де типово стоїть поточна;
    - список фрагментів вибраної сцени з `/core-review/fragments?scene_id=` і поле пошуку, що звужує список;
    - вибір одного фрагмента як цитати або «Без цитати». Типово цитата порожня, і тоді запис стає «читачеві невідомо», про що панель пише;
    - кнопки «Застосувати» і «Скасувати». «Застосувати» додає правку в чернетку панелі (`set` або `close` з `quote` та `evidence_version_id` вибраної сцени), а не шле запит на сервер;
  - кнопка «Підтвердити» шле POST без правок або з правками;
  - 409 показує повідомлення сервера й перезавантажує панель;
  - для першої сцени чи старого журналу — текст «Ядро ще не заповнене».
- Тексти UA/EN — через ключі `i18n.json` за чинним патерном `t("m_…")`.

- [ ] **Крок 1: тести, що падають**
  - `tests/web/js/core_review.mjs`:
    - групування;
    - `canKeep=false` без wire;
    - `dirty` після «Вписати…»;
    - EN-мітки існують для всіх ключів панелі.
  - `core-review.spec.mjs`, desktop і mobile:
    - зміни розгорнуті, «без змін» згорнуті;
    - «Підтвердити» без правок показує «Підтверджено»;
    - «Лишити попереднє» на `unknown` + «Підтвердити» створює нову версію, і рядок стає `unchanged`;
    - «Вписати…»: вибір попередньої сцени й фрагмента + «Застосувати» + «Підтвердити» → рядок показує нове значення без «читачеві невідомо»; той самий шлях з «Без цитати» → позначка «читачеві невідомо»; «Скасувати» не змінює чернетку;
    - на mobile немає горизонтального прокручування;
    - знімки `docs/images/core-review-desktop.png` і `-mobile.png` з нейтральною фікстурою.
- [ ] **Крок 2:** `node tests/web/js/core_review.mjs`. Очікується: FAIL.
- [ ] **Крок 3:** реалізувати.
- [ ] **Крок 4:**
  - `node tests/web/js/core_review.mjs` і `node tests/web/js/memory-table.mjs` проходять;
  - Playwright запускати з кореня worktree: `npx playwright test -c frontend/playwright.config.mjs core-review memory`. Тоді знімки потрапляють у `docs/images`, а не у `frontend/docs`. Потрібні junction `frontend/node_modules` і `.venv` на основну теку та `PYTHONPATH` на `src` цього worktree;
  - очікується: PASS.
- [ ] **Крок 5:** коміт `feat(memory): core review panel under memory (#41)`.

### Task 5: Readiness, слоти колишнього протагоніста, документація

**Files:**
- Змінити: `src/storygen/generation/readiness.py` (preview `remaining` і `scene`), `src/storygen/memory/wire_v4.py`, `src/storygen/memory/projection.py` (`memory_catalog_v4`), `SPEC.MD`, `docs/memory-view.md`, `docs/en/memory-view.md`, `docs/superpowers/plans/2026-10-20-remediation-progress.md`
- Тести: `tests/generation/test_core_readiness.py`, `tests/memory/test_wire_v4.py`

**Interfaces:**
- Produces: у preview операцій `remaining` і `scene` інформаційне поле `unconfirmed_core_scenes: int`. Це кількість активних сцен, у яких голова memory має ядро (є подія зі `slot`) і `memory_confirmation is None`. Поле не впливає на `ready` і на причини блокування. UI readiness показує його як інформаційний рядок, ключ `i18n.json`.
- Produces (закриття обмеження з фінального огляду PR 1): записи зі `slot` персонажа, якого немає в `tracked`, у `bounds.mutable`, у каталозі й у `check_v4` поводяться як звичайні змінні стани:
  - їх можна `update` і `retire` через `character_states`;
  - вони не потрапляють у `core`.

  Інваріант І1 для відстежуваних не змінюється.

- [ ] **Крок 1: тести, що падають**

```python
def test_unconfirmed_count_is_info_not_block()          # 2 сцени з ядром, 1 підтверджена -> unconfirmed_core_scenes == 1, ready не змінився
def test_former_protagonist_slot_is_mutable_state()     # слот Анни після перенесення позначки на Богдана: claim у mutable, retire через character_states приймається
def test_tracked_slot_still_only_via_core()             # слот відстежуваного в character_states.update -> target_unknown, як зараз
```

- [ ] **Крок 2:** `pytest tests/generation/test_core_readiness.py tests/memory/test_wire_v4.py -q`. Очікується: FAIL.
- [ ] **Крок 3:** реалізувати.
- [ ] **Крок 4:** повний набір: `pytest -q --basetemp=C:/Users/yuriy/AppData/Local/Temp/pc2-t5`. Очікується: PASS.
- [ ] **Крок 5:** документація:
  - SPEC.MD:
    - прибрати відоме обмеження «заморожені слоти» з MEMORY-002 і записати його як усунене відхилення, Scenario → `test_former_protagonist_slot_is_mutable_state`;
    - у MEMORY-CONFIRM додати S06 «Readiness лише інформує» → `test_unconfirmed_count_is_info_not_block`.
  - `docs/memory-view.md` і `docs/en/memory-view.md`: розділ «Підтвердження ядра» (панель, дії, «Лишити попереднє» лише для згенерованих версій, автоматичний режим) зі знімками з Task 4.
  - Журнал виконання: запис PR 2.
  - `PYTHONIOENCODING=utf-8 python scripts/check_docs.py` без помилок.
- [ ] **Крок 6:** коміт `feat(memory): unconfirmed core in readiness, former protagonist slots, docs (#41)`.

---

## Після задач

1. Фінальне рев'ю всієї гілки.
2. `scripts/verify.py` з короткого тимчасового worktree (`git worktree add --detach C:\wpc HEAD`, junction `.venv`, `PYTHONPATH=C:/wpc/src`), бо з `.claude/worktrees` шляхи перевищують MAX_PATH. `docs/STATUS.md` скопіювати в гілку й закомітити.
3. `npx -y @ysilvestrov/detent cross-review --author claude`, таблиця рішень в описі PR.
4. PR на `main`. Після мерджу дописати в специфікацію «Фактично: <розмір>, 2 PR, <m> задач».
