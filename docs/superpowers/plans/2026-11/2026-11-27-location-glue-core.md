# Склеєні назви локацій — ядро: план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Мета.** Правило твору «це одна назва»: розбір рядка «Локація:» не ріже склеєну фразу, а склеювання й розклеювання одразу перераховують місця сцен плану. Охоплює розбір, сховище, API й пошук у прозі. Панель і документація сайту підуть окремим планом периферії.

**Архітектура.**
- Чиста функція розбору отримує фрази твору.
- Фрази зберігаються в `Story.location_glues` (JSON-payload, без міграції).
- Дії `glue_location` і `unglue_location` виконуються в транзакції `change_locations` під CAS ревізії твору. Вони перераховують `Scene.location_ids` сцен з `location_source='plan'`.

**Технології.** Python 3.12, Pydantic v2, SQLite, FastAPI, pytest.

**Спека:** `docs/superpowers/specs/2026-11/2026-11-27-location-glue-design.md` (затверджено 2026-11-27).

## Глобальні обмеження

- Гілка `claude/location-glue` стоїть на гілці PR #346. Після злиття #346 гілку перебазувати на `main`. PR один, на `main`.
- `Story.location_glues`:
  - до 500 фраз;
  - кожна фраза від 3 до 200 символів;
  - ключі (`glue_key`) унікальні;
  - порожній список не серіалізується (`exclude_if`).
- Фраза склеювання:
  - без `/`;
  - після стискання пробілів має 3–200 символів;
  - ключа ще немає;
  - `parse_locations(phrase, інші правила)` дає щонайменше два шляхи.
- Збіг фрази:
  - NFC;
  - без регістру;
  - ’ ʼ ' рівнозначні;
  - між двома словами `\s+`, біля розділового знака `\s*`;
  - межі слів як у `_CONJUNCTION`.
- Склеювання лише прибирає розрізи. Без фраз розбір байт у байт такий самий, як зараз.
- Перерахунок:
  - охоплює всі сцени твору з `location_source='plan'` і непорожнім «Локація:», також у кошику;
  - для зміненої сцени: `stale_scene_material`, ревізія сцени +1, `_save_scene`.
- Сцени `model` не змінюються (І0).
- Тексти помилок українською. Ключі каталогу додасть план периферії:
  - `Склеїти можна лише фразу без «/»`;
  - `Фраза має бути від 3 до 200 знаків`;
  - `Цю назву вже склеєно`;
  - `Фраза не охоплює жодного розрізу`;
  - `Склеєних назв може бути не більше 500`;
  - `Невідома склеєна назва`.
- Перевірка змін: `python scripts/check_docs.py`. Повний прогін — `scripts/verify.py` з `C:/tmp/<коротка-назва>`.

## На що дивитися в рев'ю

1. **Сцена з місцями моделі.** Вона без рядка «Локація:», але проза чи старі місця містять фразу. Склеювання її не змінює: ні `location_ids`, ні ревізії (тест у задачі 3).
2. **Розклеювання після злиття уламка в склеєну картку.** Сцени отримують ID уламків, `canonical` веде їх до склеєної картки, помилки немає (тест у задачі 3).
3. **Застаріла ревізія.** Склеювання дає 409, а `Story.location_glues` і сцени лишаються байт у байт (тест у задачі 4).
4. **Сцена в кошику з фразою.** Вона перераховується разом з активними, але в кандидатах не з’являється (тест у задачі 3).
5. **Фраза з лапками чи дужками.** Склеювання «Кафе «бар, в якому» працює, а кандидат зберігає лапку як у рядку (тест у задачі 1).

---

### Задача 1: Розбір із правилами

**Файли:**
- Змінити: `src/storygen/locations.py`
- Тест: `tests/memory/test_locations_glue.py` (новий, `@pytest.mark.req('MEMORY-LOCATIONS')`)

**Інтерфейси.**
- Отримує нічого.
- Віддає:
  - `parse_locations(line: str, glued: Iterable[str] = ()) -> list[tuple[str, ...]]`;
  - `glue_key(phrase: str) -> str`;
  - `glue_cuts(line: str, glued: Iterable[str] = ()) -> list[tuple[str, tuple[str, ...], tuple[str, ...]]]` — для кожного розрізу між сусідніми непорожніми шматками повертає (фраза, лівий шлях, правий шлях).

- [ ] **Крок 1: тести, що падають**

```python
P=['бар, в якому пахне кавою']
def test_glued_phrase_is_not_cut():
    assert parse_locations('Бар, в якому пахне кавою, вулиця',P)==[('Бар, в якому пахне кавою',),('вулиця',)]
    assert parse_locations('Місто / бар,  в якому пахне   кавою / тераса та двір',P)==[('Місто','бар, в якому пахне кавою','тераса'),('двір',)]
def test_glue_keeps_its_separator_and_word_bounds():
    assert parse_locations('бар та в якому пахне кавою',P)==[('бар',),('в якому пахне кавою',)]
    assert parse_locations('Ґрунтобар, в якому пахне кавою',P)==[('Ґрунтобар',),('в якому пахне кавою',)]
def test_glue_matches_case_nfd_apostrophes_and_punctuation_spacing():
    assert parse_locations(unicodedata.normalize('NFD','Бар, в якому пахне кавою, двір'),P)==[('Бар, в якому пахне кавою',),('двір',)]
    assert parse_locations("Комора з п'ятьма полицями, двір",['комора з п’ятьма полицями, двір'])==[("Комора з п'ятьма полицями, двір",)]
    assert parse_locations('бар,в якому пахне кавою',P)==[('бар,в якому пахне кавою',)]
def test_overlapping_and_chained_glues():
    line='бар, в якому пахне кавою, де грає джаз, вулиця'
    assert parse_locations(line,P+['кавою, де грає джаз'])==[('бар, в якому пахне кавою, де грає джаз',),('вулиця',)]
def test_without_glues_the_parse_is_unchanged():
    for line in ['Дім, двір; сад → озеро потім ліс','Бар «Ніч та день» та вулиця','Хата (кухня, сіни та комора) та двір']:
        assert parse_locations(line,())==parse_locations(line)
def test_glue_key():
    assert glue_key('  Бар ,  в якому  П’ЯТЬ ')==glue_key("бар, в якому п'ять")=="бар, в якому п'ять"
def test_glue_cuts_give_the_phrase_across_each_cut():
    assert glue_cuts('Місто / бар, в якому пахне кавою / тераса та двір')==[
        ('бар, в якому пахне кавою',('Місто','бар'),('в якому пахне кавою','тераса')),
        ('тераса та двір',('в якому пахне кавою','тераса'),('двір',))]
    assert glue_cuts('Кафе «бар, в якому», двір')[0][0]=='Кафе «бар, в якому»'
    assert glue_cuts('Бар, в якому пахне кавою, вулиця',P)==[('Бар, в якому пахне кавою, вулиця',('Бар, в якому пахне кавою',),('вулиця',))]
    assert glue_cuts('Дім / , двір')==[]   # an empty piece gives no cut
```

- [ ] **Крок 2.** `pytest tests/memory/test_locations_glue.py -q` падає: немає `glue_key` чи `glue_cuts`.
- [ ] **Крок 3: реалізація в `locations.py`.**
  - Рядок спершу нормалізується в NFC.
  - Захищені проміжки — збіги regex кожної фрази.
  - `_chunks(line, glued)` пропускає розріз, чий початок лежить строго всередині захищеного проміжку.
  - `glue_cuts` бере сирі шматки й позиції розрізів, а фразу `' '.join(line[a:b].split())` формує так:
    - `a` — початок останньої частини лівого шматка, тобто після останнього `/`, з пропуском пробілів;
    - `b` — кінець першої частини правого шматка, тобто до першого `/`, без кінцевих пробілів;
    - розріз, біля якого хоч один шматок не має непорожніх частин, пропускається.
  - Наявні тести `tests/memory/test_locations_parse.py` мають пройти без змін.
- [ ] **Крок 4.** `pytest tests/memory -q` проходить.
- [ ] **Крок 5.** Коміт `feat(locations): розбір зі склеєними фразами`.

### Задача 2: Правила в даних твору, збереження плану й пошук у прозі

**Файли:**
- Змінити:
  - `src/storygen/domain.py` (`Story`);
  - `src/storygen/storage/locations.py` (`plan_location_ids`, нова `story_glues`);
  - `src/storygen/characters/extract.py` (`ExtractState`, `_paths`, `_apply_locations`);
  - `src/storygen/generation/extract_run.py` (створення `ExtractState`).
- Тест: `tests/storage/test_location_glue.py` (новий), `tests/characters/test_extract_accept_locations.py` (додати тест).

**Інтерфейси.**
- Отримує `parse_locations(line, glued)` із задачі 1.
- Віддає:
  - `Story.location_glues: list[str]` (`Annotated[str, StringConstraints(min_length=3,max_length=200)]`, `max_length=500`, `exclude_if=lambda v: not v`);
  - `story_glues(db, story_id: str) -> list[str]`;
  - `ExtractState.glued: list[str] = []`;
  - `_paths(item, numbers, glued=())`.

- [ ] **Крок 1: тести, що падають.**
  - `test_story_payload_without_glues_has_no_field`: payload твору в `stories` не містить `location_glues`.
  - `test_plan_save_uses_story_glues`: твір отримує `location_glues=['бар, в якому пахне кавою']` через `repo._save_story` у транзакції, `bump_generation`. Збереження плану «Локація: Бар, в якому пахне кавою, вулиця» дає `location_ids==[lid('Бар, в якому пахне кавою'), lid('вулиця')]`.
  - `test_extract_paths_respect_glues`: `_paths('бар, в якому пахне кавою', {}, ['бар, в якому пахне кавою'])==[('бар, в якому пахне кавою',)]`.
  - Стан витягу без поля `glued`, тобто старий чекпойнт, читається з `glued==[]`.
- [ ] **Крок 2.** Тести падають.
- [ ] **Крок 3: реалізація.**
  - `plan_location_ids` передає `story_glues(db, story_id)`.
  - `story_glues` читає payload твору з `db`.
  - `extract_run` заповнює `glued=view.get_story(run.story_id).location_glues`.
  - `_apply_locations` передає `state.glued` у `_paths`.
  - Перевірити, чи є місця, що будують `Story` поле за полем (`grep -rn "Story(" src`). Нова книга серії правил не успадковує. Якщо якесь місце копіює твір, що має правила, і губить поле, додати перенесення й тест.
- [ ] **Крок 4.** `pytest tests/storage/test_location_glue.py tests/characters tests/storage/test_story_locations.py -q` проходить.
- [ ] **Крок 5.** Коміт `feat(locations): правила склеювання в даних твору`.

### Задача 3: Склеювання, розклеювання, перерахунок і кандидати в сховищі

**Файли:**
- Змінити: `src/storygen/storage/locations.py`.
- Тест: `tests/storage/test_location_glue.py`.

**Інтерфейси.**
- Отримує `story_glues`, `parse_locations`, `glue_key`, `glue_cuts`.
- Віддає:
  - `glue_location(repo, db, story_id: str, phrase: str) -> None`;
  - `unglue_location(repo, db, story_id: str, key: str) -> None`;
  - `change_locations`, який зберігає твір, перечитаний після `action(db)`;
  - `locations_view(...)['glues'] == [{'key','phrase'}]`;
  - `locations_view(...)['glue_candidates'] == [{'phrase','key','card_ids','scene_ids'}]`.

- [ ] **Крок 1: тести, що падають** (через `store.change_locations(repo, story.id, rev, lambda db: store.glue_location(repo, db, story.id, phrase))`).
  - `test_glue_recomputes_plan_scenes_now`:
    - сцена «Ранок» з «Локація: Бар, в якому пахне кавою, вулиця» отримує ID склеєної картки й ревізію +1;
    - сцена без фрази лишається з тією самою ревізією;
    - текст плану (`beats`) не змінюється.
  - `test_glue_skips_model_scenes`: сцена з `set_model_places` (з `tests/storage/test_story_locations.py`) не змінює ні `location_ids`, ні ревізії.
  - `test_glue_reaches_trashed_plan_scenes`: сцена в кошику має нові ID, а в `glue_candidates` її немає.
  - `test_glue_stales_material`: версія завдання сцени, яка не є головою, стає застарілою, як у наявному тесті застарілості рядка «Локація:» (`tests/storage/test_story_locations.py`).
  - `test_unglue_restores_fragments` повертає ID уламків.
  - `test_unglue_after_merging_a_fragment`:
    - уламок «бар» злито в склеєну картку;
    - після розклеювання сцена має `lid('Бар')` серед `location_ids`, а `canonical` веде його до склеєної картки.
  - `test_glue_validation`. Кожен з шести текстів помилки з глобальних обмежень дає `ValueError` без змін у творі. Повтор перевіряється з іншим регістром і апострофом. Межу 500 перевірити, заповнивши поле 500 фразами.
  - `test_glue_dismisses_new_cards_against_fragments_with_prefixes`:
    - рядок «Місто / бар, в якому пахне кавою / тераса»;
    - після склеювання `suggestions` не має жодної пари нової картки з `Місто / бар`, `в якому пахне кавою`, `в якому пахне кавою / тераса`.
  - `test_candidates`:
    - «Місто / бар, зал» і «Село / бар, зал» дають один кандидат `бар, зал` з `card_ids`, що містять обидві картки «бар» і обидві «зал», і з двома `scene_ids`;
    - після склеювання кандидат зникає, а фраза з’являється в `glues`.
  - `test_glue_recompute_500_scenes_within_a_second`: 500 сцен з фразою, склеювання займає менше 1 с за `time.perf_counter`. Якщо не вкладається, зупинитися й повідомити: спека вимагає розбити перерахунок.
- [ ] **Крок 2.** Тести падають.
- [ ] **Крок 3: реалізація.**
  - `glue_location` валідує фразу, записує твір з новим списком через `repo._save_story` без зміни ревізії, перераховує сцени й приховує пари.
  - `unglue_location` перевіряє ключ (`Невідома склеєна назва`), прибирає його й перераховує.
  - **Спільний перерахунок** (`_recompute_plan_places(repo, db, story_id) -> list[tuple[list[str], list[str]]]`, пари «до» й «після» для змінених сцен):
    - обирає сцени, де `plan_fields(beats).get('location')` і `location_source=='plan'`;
    - для кожної рахує нові ID через `plan_location_ids`;
    - якщо ID інші — пише їх у сцену, викликає `stale_scene_material`, ставить ревізію +1 і викликає `_save_scene`.
  - **Приховані пари:**
    - нові картки — ID у `load_locations` після мінус до;
    - старі — ID «до» змінених сцен разом з предками за `parent_id`, мінус ID «після» з предками;
    - `dismiss_pair` для кожної пари нова × стара.
  - **`change_locations`:** після `action(db)` викликати `repo._active_story(db, story_id)` і зберегти його з ревізією +1.
- [ ] **Крок 4.** `pytest tests/storage tests/web/test_locations_api.py tests/web/test_locations_remove_place.py -q` проходить.
- [ ] **Крок 5.** Коміт `feat(locations): склеювання й розклеювання з перерахунком сцен`.

### Задача 4: API, SPEC і traceability

**Файли:**
- Змінити:
  - `src/storygen/web/routes_locations.py`;
  - `SPEC.MD` (MEMORY-LOCATIONS);
  - `docs/verification/traceability.json`.
- Тест: `tests/web/test_locations_glue_api.py` (новий; використовує `setup`, `base` з `tests/web/test_locations_api.py`).

**Інтерфейси.**
- Отримує `glue_location`, `unglue_location`.
- Віддає:
  - `POST {base}/glue` з `{expected_revision, phrase}`;
  - `POST {base}/unglue` з `{expected_revision, key}`;
  - відповідь — `locations_view` разом з `dependent_scene_ids`.

- [ ] **Крок 1: тести, що падають.**
  - `test_glue_api_returns_view_and_dependent_scenes`:
    - 200;
    - `glues[0]['phrase']=='бар, в якому пахне кавою'`;
    - `story_revision` +1;
    - сцена з брифом і фразою є в `dependent_scene_ids`.
  - `test_glue_api_conflict_changes_nothing`: стара ревізія дає 409, а payload твору й сцен байт у байт той самий (як `stored` у `test_locations_remove_place.py`).
  - `test_glue_api_validation_400`: фраза з `/` дає 400.
  - `test_unglue_api`: невідомий ключ дає 400, відомий — 200, і `glues==[]`.
  - Тіло без `phrase` або `phrase` довжиною понад 200 дає 422. Модель тіла: `phrase: str = Field(min_length=1, max_length=400)`, а точну межу 200 після стискання перевіряє сховище.
- [ ] **Крок 2.** Тести падають.
- [ ] **Крок 3: реалізація маршрутів** за зразком `merge`/`split` через `change(...)`.
- [ ] **Крок 4: SPEC.MD, розділ MEMORY-LOCATIONS.**
  - «Розбір»: склеєні фрази, правила збігу, `glue_cuts`.
  - «Дані»: `Story.location_glues` (межі, `exclude_if`), новий записувач `Scene.location_ids` (`glue_location`/`unglue_location`), приховані пари.
  - «API»: два маршрути, поля `glues` і `glue_candidates`, тексти помилок.
  - Інваріанти І5–І7 зі спеки.
  - «Сумісність»: старіша версія не відкриє твір з правилом.
  - «Відомі обмеження»: замінити «назва з комою поки ріжеться» на «склеювання діє на весь твір; уламкові картки лишаються».
  - Scenario:
    - `MEMORY-LOCATIONS-S09` — розбір зі склеєними фразами;
    - `MEMORY-LOCATIONS-S10` — склеювання й розклеювання в сховищі, API й пошуку в прозі.
  - У traceability S09 вказує на `tests/memory/test_locations_glue.py`, а S10 — на `tests/storage/test_location_glue.py`, `tests/web/test_locations_glue_api.py` і тест витягу.
  - S11 (панель) додасть план периферії.
- [ ] **Крок 5.** `python scripts/check_docs.py` і `pytest tests/web/test_locations_glue_api.py tests/memory tests/storage -q` проходять.
- [ ] **Крок 6.** Коміт `feat(locations): API склеювання й SPEC`.

## Після ядра

- **Наскрізне рев'ю ядра.** Читається вся гілка разом, знахідки записуються.
- **Окремий план периферії:**
  - панель («Склеїти з…», «Склеєні назви», «Розклеїти»);
  - ключі каталогу uk/en для помилок і підписів;
  - JS і Playwright (S11);
  - `docs/site/{uk,en}/memory.md` з rehash.
- Потім `verify.py`, cross-review PR і один PR на `main`.
