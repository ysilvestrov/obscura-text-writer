# Час історії, обв'язка (PR 2): спогади й «Минуле інших арок» — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Сцена-спогад (прапорець або позначка в `Початок:`) додає до пам'яті лише факти, не отримує й не передає станів ядра. Сцени інших арок бачать факти спогадів, чий момент раніший за початок їхньої арки, у розділі «Минуле інших арок». Книга без спогадів не змінюється.

**Architecture:** Усі рішення спираються на `is_flashback(scene)` і `flashback_mode(story, scenes)` (`simple` для пласкої книги, `full` для книги зі структурою) у `memory/story_time.py`. Етап пам'яті спогаду отримує межі схеми з `flashback=True`: дозволено лише `facts.add`, до 6. Збереження журналу перевіряє те саме правило в одному місці, `publish_memory_journal`. Письменник спогаду отримує проєкцію пам'яті без станів (`full`) або не отримує її взагалі (`simple`). Чужі видимі спогади збирає `memory/flashbacks.py::foreign_flashbacks`. Знімки отримують селектори `scene/<id>/flashback` і `scene/<id>/flashback_facts` з правилом типового значення, як у `memory_projection_policy`.

**Tech Stack:** Python 3.12, pytest, Playwright (`@playwright/test` 1.64.1); без змін схеми SQLite: поле лежить у payload сцени.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-13-story-time-flashbacks-design.md`: розділи «Спогад», «Минуле інших арок», «Інтерфейс»; перевірки STORY-TIME-S03…S07. Ядро (PR 1, #162) вже дало `Moment`, `scene_moment`, `before`, `flashback_marked`, `day_key`, `day_label` у `memory/story_time.py` та `arc_start` і `is_flashback` у `book/story_time.py`.

## Global Constraints

- `Scene.flashback: bool = False`. Дозволене в усіх виданнях і не потребує довгої прози. Зміна прапорця підвищує ревізію сцени.
- `is_flashback(scene) = scene.flashback or flashback_marked(scene.beats)`. Усі місця нижче питають лише цю функцію.
- Режим `simple`, коли `structure_kind(story, scenes) == 'flat'`, інакше `full`. Рішення залежить від твору, а не від збірки.
- Пам'ять спогаду: в обох режимах дозволено лише `facts.add`, межа — 6 (у звичайної сцени 3). Порушення — `Violation('$', 'flashback_only_facts')`, а надлишок фактів — `Violation('facts.add', 'add_limit')`.
- Ручне збереження, що змінює стани, лінії, хронологію або вже наявні факти, відхиляється з `ValueError('Спогад додає лише факти')`. Маршрут повертає 400.
- Розділ «Минуле інших арок»: заголовок `uk` — `МИНУЛЕ ІНШИХ АРОК — ФАКТИ СПОГАДІВ`, `en` — `THE PAST OF OTHER ARCS — FACTS FROM FLASHBACKS`. Для кожного спогаду рядок `Сцена N (позначка часу):` / `Scene N (time label):` і факти рядками `- …`. Межа — 40 фактів, першими йдуть найпізніші в порядку читання спогади. Надлишок дає попередження `Минуле інших арок: показано 40 фактів із N.` Назв арок і частин у розділі немає.
- Позначка часу = `day_label(day_key(scene), language)`; якщо в моменті є година, додається `, ГГ:ХХ`.
- Селектори пишуться лише з нетиповим значенням: `flashback` — лише `true`, `flashback_facts` — лише непорожній список. Відсутній селектор `compare_snapshot` вважає типовим (`false`, `[]`).
- Знімки, запити й відбитки книги без спогадів і без нових позначок байт у байт ті самі (S06).
- Документація українською, маркери OpenSpec англійською. Кожен Scenario — у `docs/verification/traceability.json`. `python scripts/check_docs.py` проходить. Сайт uk/en парою: `python scripts/check_site.py --rehash memory` і `--rehash book-structure`. Приклади нейтральні, без матеріалів з `data/`.

## Review Focus

- Спогад без вибраної прози чи пам'яті та спогад зі застарілою пам'яттю: його немає в «Минулому інших арок», немає й винятку. Коли пам'ять з'являється, сцена Б стає застарілою (тест у Task 4).
- Спогад — перша сцена книги: попередньої пам'яті немає, журнал містить лише його факти, а `simple` не падає на порожньому каталозі (тест у Task 2).
- Прапорець увімкнено на сцені, що вже має пам'ять зі зміною стану: її пам'ять і текст застарілі через `scene/<id>/flashback`. Нове ручне збереження того самого журналу відхиляється (тест у Task 1 і Task 2).
- Сцена зустрічі двох арок, для обох з яких спогад видимий: факти показано один раз (тест у Task 4).
- Позначка спогаду в `Початок:` і вимкнений прапорець: сцена лишається спогадом, а прапорець в інтерфейсі увімкнений і недоступний (тест у Task 1 і Task 5).

---

### Task 1: Поле сцени, імпорт і селектор `flashback`

**Files:**
- Modify: `src/storygen/domain.py:86-100` (`SceneCreate.flashback`)
- Modify: `src/storygen/memory/story_time.py` (`is_flashback`, `flashback_mode`)
- Modify: `src/storygen/book/story_time.py` (повторно експортувати `is_flashback` з `memory/story_time.py`)
- Modify: `src/storygen/storage/authoring.py:82-100` (`update_scene_metadata`)
- Modify: `src/storygen/web/routes_stories.py:27,106,151` (тіло PATCH, поля списку сцен)
- Modify: `src/storygen/plan_sections.py` (`FLASHBACK_LINE`, `cut_flashback_line`), `src/storygen/authoring/imports.py:78-125`
- Modify: `src/storygen/dependency_models.py:21`, `src/storygen/storage/snapshots.py` (селектор, `selector_value`, правило типового значення в `compare_snapshot`)
- Test: `tests/memory/test_flashback_scene.py` (новий), `tests/authoring/test_flashback_import.py` (новий)

**Interfaces:**
- Produces: `is_flashback(scene) -> bool`; `flashback_mode(story, scenes) -> Literal['simple','full']`; `cut_flashback_line(text: str) -> tuple[str, bool | None, bool]` (текст без рядка, значення або `None`, чи було недопустиме значення); селектор `DependencySelector(kind='scene', field='flashback')` зі значенням `is_flashback(scene)`; поля списку сцен `flashback` (поле) і `flashback_marked` (позначка в `Початок:`).
- Ruling, записати в журнал: `is_flashback` переходить у `memory/story_time.py`, як у специфікації. `comparison_scene` у тому самому модулі мусить його викликати, а імпорт з `book/story_time.py` замкнув би коло (`book/story_time` імпортує `memory/story_time`). `book/story_time.py` повторно його експортує, тому тести ядра не змінюються.

- [ ] **Step 1: Write the failing tests**

```python
# tests/memory/test_flashback_scene.py — STORY-TIME-S03 (поле й позначка), S06 (селектор лише з нетиповим значенням)
def test_flag_or_mark_makes_a_flashback():
    assert is_flashback(Scene(id='s', story_id='b', position=0, title='С', flashback=True))
    assert is_flashback(Scene(id='s', story_id='b', position=0, title='С', beats='Початок: Рік -3 (спогад)'))
    assert not is_flashback(Scene(id='s', story_id='b', position=0, title='С', beats='Початок: Рік 1'))

def test_mode_follows_the_book(tmp_path):
    # flat book → 'simple'; arc_book(tmp_path, 'A B', [['A','B']]) → 'full'

def test_patch_sets_flag_and_bumps_revision(tmp_path):
    # repo.update_scene_metadata(scene.id, {'flashback': True}, scene.revision).revision == scene.revision + 1

def test_flag_stales_memory_and_prose_through_the_selector(tmp_path):
    # arc_book(... 'A B A' ...); ставимо прапорець на сцені 3 → її пам'ять застаріла;
    # знімок пам'яті сцени 3 до зміни не мав селектора flashback (типове значення порівнюється через compare_snapshot)

def test_book_without_flashbacks_writes_no_flashback_selector(tmp_path):
    # усі знімки arc_book(... 'A B A' ...): жодного selector.field == 'flashback'
```

```python
# tests/authoring/test_flashback_import.py — STORY-TIME-S03, S07 (усі видання)
def test_flashback_line_is_cut_and_sets_the_field():
    assert cut_flashback_line('Спогад: так\nАнна йде містом.\n') == ('Анна йде містом.\n', True, False)
    assert cut_flashback_line('**Flashback:** no\nText\n') == ('Text\n', False, False)
    assert cut_flashback_line('Спогад: можливо\nText\n') == ('Text\n', None, True)

def test_import_sets_flag_in_an_edition_without_long_prose(tmp_path, monkeypatch):
    # build_edition без long_prose; план «## Сцена 1\nСпогад: так\n…» → сцена з flashback=True, beats без рядка
    # «Спогад: можливо» → попередження з текстом «Спогад:», поле False
```

- [ ] **Step 2: Run them and see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/memory/test_flashback_scene.py tests/authoring/test_flashback_import.py -q`
Expected: FAIL (`ImportError: cannot import name 'flashback_mode'`, `cut_flashback_line`)

- [ ] **Step 3: Implement**

- `SceneCreate.flashback: bool = False`.
- `update_scene_metadata`: дозволені поля плюс `flashback`. Повну інвалідацію heads запускають лише поля поза `{'prose_language', 'flashback'}`, бо прапорець робить версії застарілими через селектор.
- `routes_stories.py`: `flashback: bool | None = None` у тілі PATCH. У списку сцен `"flashback_marked": flashback_marked(scene.beats)`.
- `FLASHBACK_LINE = re.compile(r'^(?:спогад|flashback)\s*:\s*(.*)$', re.IGNORECASE)` по `_plain(line)`. Значення `так|yes|true` → `True`, `ні|no|false` → `False`, інше → недопустиме.
- `_plan` в обох виданнях: `cut_flashback_line(section.text)` до `SceneCreate`. Обрізаний текст іде в `beats` і в версію `scene_plan`. Недопустиме значення дає попередження `Рядок «Спогад:» має бути «так» або «ні»; прапорець не поставлено.` Якщо хоч один рядок вирізано, джерельний план зберігається обрізаним, як для `publication.structured`.
- Селектор у `build_dependency_snapshot`: для скоупів `memory`, `brief`, `draft`, `prose_edit`, `author_text` і `author_rewrite` записувати `select('scene', scene.id, 'flashback', True)` лише тоді, коли `is_flashback(scene)`. У `selector_value` додати `('scene', 'flashback') → is_flashback(view.peek_scene(owner))`. У `compare_snapshot` для цих скоупів додати відсутній селектор з `expected=False`, власник — `snapshot_scene(selectors)` (зразок — `memory_projection_policy`, рядки 261-263). У `dependency_models.py:21` додати `'flashback'`.

- [ ] **Step 4: Run them and see them pass**

Run: `.venv/Scripts/python.exe -m pytest tests/memory/test_flashback_scene.py tests/authoring/test_flashback_import.py tests/book tests/storage -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/storygen/domain.py src/storygen/memory/story_time.py src/storygen/book/story_time.py src/storygen/storage/authoring.py src/storygen/web/routes_stories.py src/storygen/plan_sections.py src/storygen/authoring/imports.py src/storygen/dependency_models.py src/storygen/storage/snapshots.py tests/memory/test_flashback_scene.py tests/authoring/test_flashback_import.py
git commit -m "feat(time): flashback scene field, plan line and snapshot selector"
```

### Task 2: Пам'ять спогаду — лише факти

**Files:**
- Create: `src/storygen/memory/flashbacks.py` (`check_flashback_journal`; Task 3 і Task 4 доповнюють модуль)
- Modify: `src/storygen/memory/wire_v4.py:47-176,221+` (`schema_bounds_v4(..., flashback=False)`, `check_v4`, `memory_wire_v4_schema`)
- Modify: `src/storygen/generation/context.py:298-370` (гілка `memory`)
- Modify: `src/storygen/memory/service.py:78-92` (`publish_memory_journal`), `src/storygen/memory/core_review.py:70-77`
- Test: `tests/memory/test_flashback_memory.py` (новий); `tests/memory/merge_helpers.py` (`arc_book(..., beats=None)`)

**Interfaces:**
- Consumes: `is_flashback`, `flashback_mode` (Task 1).
- Produces: `schema_bounds_v4(previous, prose, allowed, tracked, day_change, *, keep=None, flashback=False)`. З `flashback=True` межі мають `'flashback': True`, `tracked={}`, `unestablished={}`, `mutable={'character_states': []}`, `threads=[]`. Без прапорця ключа `'flashback'` немає, тому межі звичайної сцени байт у байт ті самі. `check_flashback_journal(journal, previous) -> None` (у `memory/flashbacks.py`) — `ValueError('Спогад додає лише факти')`. `arc_book(root, tokens, parts, events=None, *, repo=None, beats=None)` — `beats[i]` замість `'Анна йде містом.'` для сцени `i`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/memory/test_flashback_memory.py — STORY-TIME-S03
def test_schema_allows_only_fact_adds():
    bounds = schema_bounds_v4(MemoryJournal(), 'Анна йде містом.', ['c1'], ['c1'], {'c1': True}, flashback=True)
    schema = memory_wire_v4_schema(bounds)
    # schema['properties']['core'] і ['threads'] без властивостей; character_states/open_threads/timeline: add з maxItems 0
    assert bounds['flashback'] is True and bounds['tracked'] == {} and bounds['day_change'] == {}

def test_check_rejects_a_state_and_admits_six_facts():
    # відповідь із character_states.add → Violation('$','flashback_only_facts'); 6 facts.add → []; 7 → add_limit

def test_simple_mode_memory_stage_gets_no_catalog(tmp_path):
    # пласка книга, сцена 2 — спогад: build_context(..., 'memory', ...).user_text не містить label('memory_core'/'memory_claims')
    # і містить фрагменти прози; fragments['memory_schema_bounds'] має "flashback": true

def test_full_mode_memory_stage_keeps_the_catalog(tmp_path):
    # arc_book 'A B A', сцена 3 — спогад: каталог є, межі flashback

def test_next_scene_gets_flashback_facts_and_the_same_states(tmp_path):
    # сцена 1 додає стан c1/clothing; сцена 2 (спогад) — лише факт; сцена 3 у previous memory має факт спогаду,
    # а replay стану clothing той самий, що після сцени 1

def test_manual_memory_changing_a_state_is_400(tmp_path, client):
    # PUT ручної пам'яті спогаду з оновленням стану → 400 і текст «Спогад додає лише факти»; з новим фактом → 200

def test_first_scene_flashback_has_only_its_facts(tmp_path):
    # спогад — сцена 1 пласкої книги: етап будується, журнал = лише його факти

def test_core_review_of_a_flashback_is_empty(tmp_path):
    # core_review(...) → {'flashback': True, 'slots': [], 'threads': [], 'day_change': False}
```

- [ ] **Step 2: Run them and see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/memory/test_flashback_memory.py -q`
Expected: FAIL (`TypeError: schema_bounds_v4() got an unexpected keyword argument 'flashback'`)

- [ ] **Step 3: Implement**

- `check_v4`: `if bounds.get('flashback')`, будь-який елемент поза `facts.add` або рішення в `core`/`threads` дає один `Violation('$', 'flashback_only_facts')`. Межа `facts.add` — 6, а `ops_limit` не змінюється. Схема: для інших розрядів `add` з `maxItems: 0`.
- Гілка `memory` у `build_context`, коли `is_flashback(scene)`: `tracked=[]`, `changed={}`, `schema_bounds_v4(..., flashback=True)`. У `simple` `stage_sections` пропускає три розділи каталогу й `day_changed`, а `narrower` — `None`. У `full` каталог той самий, що зараз.
- `publish_memory_journal`: якщо `is_flashback(ctx.scene)`, викликати `check_flashback_journal(journal, ctx.previous)` до `validate_memory_journal`. Правило: кожен запис `replay_memory(previous)` присутній незмінним у `replay_memory(journal)`, а нові записи — лише розряду `facts`. Маршрут ручної пам'яті вже перетворює `ValueError` на 400, тому треба лише перевірити це тестом.
- `core_review`: для спогаду після першого `result` повернути `{**result, 'flashback': True}` без слотів і ліній. Застосування перевірки ядра проходить через `publish_memory_journal`, тож правило діє й там.

- [ ] **Step 4: Run them and see them pass**

Run: `.venv/Scripts/python.exe -m pytest tests/memory -q`
Expected: PASS (наявні тести `test_wire_v4.py` без змін)

- [ ] **Step 5: Commit**

```bash
git add src/storygen/memory/wire_v4.py src/storygen/memory/flashbacks.py src/storygen/generation/context.py src/storygen/memory/service.py src/storygen/memory/core_review.py tests/memory/test_flashback_memory.py tests/memory/merge_helpers.py
git commit -m "feat(time): flashback memory adds facts only"
```

### Task 3: Письменник спогаду і сигнал дня

**Files:**
- Modify: `src/storygen/memory/story_time.py:126-138` (`comparison_scene`)
- Modify: `src/storygen/generation/context.py:246-268,410-440` (`memory_projection`, `writer_day_change`, розділ пам'яті письменника)
- Modify: `src/storygen/memory/flashbacks.py` (`present_only_journal`)
- Check: MCP writing-context, що викликає `memory_projection` (`grep -rn memory_projection src/storygen/mcp`), отримує те саме правило без окремого коду.
- Test: `tests/memory/test_flashback_writer.py` (новий)

**Interfaces:**
- Consumes: `is_flashback`, `flashback_mode` (Task 1).
- Produces: `present_only_journal(journal) -> MemoryJournal` (без подій `character_states`, зі збереженими `source_prose_ids`); `memory_projection(...)` для спогаду: у `full` — проєкція `present_only_journal(past)` з `tracked=()`; у `simple` — `projection` дорівнює `None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/memory/test_flashback_writer.py — STORY-TIME-S04
def test_short_prose_flashback_writer_has_no_memory(tmp_path):
    # пласка книга, сцена 2 — спогад: label('memory_header') відсутній у build_context(..., 'brief').user_text, memory_selector None

def test_book_flashback_writer_has_no_core_or_states(tmp_path):
    # arc_book 'A A' з events: сцена 1 — стан c1/clothing і факт; сцена 2 — спогад:
    # текст факту є, тексту стану й label('memory_core') немає

def test_flashback_neither_gives_nor_breaks_the_day_signal(tmp_path):
    # beats: 'Початок: День 1', 'Початок: Рік -5 (спогад)', 'Початок: День 2', усі з c1 у складі, c1 відстежуваний:
    # writer_day_change для сцени 2 → None; для сцени 3 → нотатка «день 1» → «день 2» (порівняння зі сценою 1)
    assert comparison_scene(scenes, scenes[2], 'c1', story).id == scenes[0].id
```

- [ ] **Step 2: Run them and see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/memory/test_flashback_writer.py -q`
Expected: FAIL (у контексті спогаду є розділ пам'яті; `comparison_scene` повертає сцену 2)

- [ ] **Step 3: Implement**

- `comparison_scene`: фільтр `and not is_flashback(item)`.
- `writer_day_change`: на початку `if is_flashback(scene): return None`.
- `build_context` для письменника: якщо `projection is None`, розділ пам'яті не додається, `memory_selector=None`, а `memory_index` не використовується. Хвіст попередньої прози (`previous_tail`) лишається.

- [ ] **Step 4: Run them and see them pass**

Run: `.venv/Scripts/python.exe -m pytest tests/memory tests/generation tests/mcp -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/storygen/memory/story_time.py src/storygen/memory/flashbacks.py src/storygen/generation/context.py tests/memory/test_flashback_writer.py
git commit -m "feat(time): flashback writer context and day signal"
```

### Task 4: «Минуле інших арок»

**Files:**
- Modify: `src/storygen/memory/flashbacks.py` (`ForeignFlashback`, `foreign_flashbacks`, `foreign_section`)
- Modify: `src/storygen/generation/context_labels.py` (`foreign_flashbacks`, `foreign_flashback_scene`)
- Modify: `src/storygen/generation/context.py` (розділ після пам'яті й нотатки дня, refs, попередження)
- Modify: `src/storygen/storage/snapshots.py`, `src/storygen/dependency_models.py:21` (`flashback_facts`)
- Test: `tests/memory/test_foreign_flashbacks.py` (новий)

**Interfaces:**
- Consumes: `arc_start`, `before`, `scene_moment`, `day_key`, `day_label` (ядро); `is_flashback` (Task 1); `previous_scenes`, `effective_structure(...).arcs_of`.
- Produces: `ForeignFlashback(scene_id: str, number: int, memory_id: str, time_label: str, facts: tuple[str, ...])` (frozen dataclass); `foreign_flashbacks(view, story, scenes, scene, language) -> list[ForeignFlashback]` у порядку читання; `foreign_section(items, language) -> tuple[str | None, str | None]` (текст розділу й попередження); значення селектора — `sorted([f.scene_id, f.memory_id, f.time_label] for f in items)`.
- Ruling, записати в журнал: специфікація пише `foreign_flashbacks(story, scenes, scene)`, але умова «вибрана незастаріла пам'ять» потребує view. Тому функція отримує `view` і `language` (останній — для позначки часу) і повертає записи, а не лише id.

- [ ] **Step 1: Write the failing tests**

```python
# tests/memory/test_foreign_flashbacks.py — STORY-TIME-S05
# Книга 'A B' (одна частина [['A','B']]): сцена 1 арки A — 'Початок: Рік -5 (спогад)' з фактом «Давня подія»,
# сцена 2 арки B — 'Початок: Рік 1'. Другий варіант: 'A A B' з present-сценою арки A першою.
def test_foreign_flashback_before_arc_start_is_shown(tmp_path):
    context = build_context(repo, scenes[1].id, 'brief', SETTINGS)
    assert 'МИНУЛЕ ІНШИХ АРОК' in context.user_text and 'Давня подія' in context.user_text
    assert 'Сцена 1 (рік -5):' in context.user_text
    assert 'Частина 1' not in section_of(context)  # назви частин і арок (у тестовій книзі — «Частина 1», «A», «B») у розділ не входять
    assert scenes[0].heads['memory'] in context.input_refs

def test_not_shown_when_below_later_unknown_or_arc_start_unknown(tmp_path):
    # спогад нижче за сцену B; момент 'Рік 3 (спогад)' пізніший за 'Рік 1'; 'Початок: невідомо (спогад)';
    # сцена B без «Початок:» → розділу немає, user_text ідентичний книзі без спогаду

def test_meeting_scene_shows_a_fact_once(tmp_path):
    # 'A B C A+B' з трьома арками: спогад арки C видимий для A і B → «Давня подія» трапляється один раз

def test_lineage_flashback_is_not_foreign(tmp_path):
    # спогад арки A, сцена A нижче: факт приходить через попередню пам'ять, розділу немає

def test_limit_of_forty_facts_warns(tmp_path):
    # 7 спогадів по 6 фактів → 40 фактів у розділі, першими факти найпізніших спогадів, попередження «показано 40 фактів із 42»

def test_flashback_without_fresh_memory_is_skipped_then_stales_the_scene(tmp_path):
    # пам'ять спогаду не записана → розділу немає; версія brief сцени B; пам'ять спогаду записана → brief застарілий

def test_changes_stale_the_scene_including_old_snapshots(tmp_path):
    # brief сцени B записано; кожна зміна окремо робить його застарілим:
    #   нова пам'ять спогаду; 'Рік -5' → 'Рік -4' (видимий і далі); знятий прапорець;
    #   прапорець, поставлений пізніше на сцені 'Рік -5' без позначки (старий знімок без селектора → застарілий)
```

- [ ] **Step 2: Run them and see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/memory/test_foreign_flashbacks.py -q`
Expected: FAIL (`ImportError: cannot import name 'foreign_flashbacks'`)

- [ ] **Step 3: Implement**

- `foreign_flashbacks` бере сцени вище за `scene` за `position`, що не входять у `previous_scenes(story, scenes, scene)`, з `is_flashback(item)`. Далі лишаються сцени з `heads['memory']`, де версія не застаріла й `complete`, і з `scene_moment(item.beats)` не `None`, для яких `before(moment, arc_start(story, scenes, arc)) is True` хоча б для однієї арки з `arcs_of[scene.id]`. Пласка книга одразу дає `[]`.
- Факти спогаду — `replay_memory(journal)` записи розряду `facts`, чий `source_version_id == journal.source_prose_ids[-1]`, у порядку подій.
- `build_context` для brief/draft/edit/rewrite (не `memory`, не `edit` у режимі patches/diff): після пам'яті й нотатки дня додати розділ, `refs` — пам'ять кожного спогаду, попередження — у `warnings`. Без спогадів не відбувається нічого.
- Знімок для тих самих скоупів письменника: `select('scene', scene.id, 'flashback_facts', value)` лише з непорожнім значенням. `selector_value` перераховує значення з view. `compare_snapshot` додає відсутній селектор з `expected=[]`.

- [ ] **Step 4: Run them and see them pass**

Run: `.venv/Scripts/python.exe -m pytest tests/memory tests/book tests/storage tests/generation -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/storygen/memory/flashbacks.py src/storygen/generation/context_labels.py src/storygen/generation/context.py src/storygen/storage/snapshots.py src/storygen/dependency_models.py tests/memory/test_foreign_flashbacks.py
git commit -m "feat(time): the past of other arcs from foreign flashbacks"
```

### Task 5: Інтерфейс і видання

**Files:**
- Modify: `src/storygen/web/static/scene-settings.js:11-20` (прапорець «Спогад»)
- Modify: `src/storygen/web/static/book-structure.js:27-32` (`sceneRow.flashback`, мітка `book.badge.flashback`)
- Modify: `src/storygen/web/static/book-structure-ui.js` (підказка біля арки з невідомим початком)
- Modify: `src/storygen/web/routes_structure.py` або відповідь структури (`arc_start_unknown: list[arc_id]`, лише якщо в книзі є спогад)
- Modify: `src/storygen/web/static/i18n.json` (uk/en): `scene.flashback`, `scene.flashback_help`, `scene.flashback_marked`, `book.badge.flashback`, `book.arc_start_unknown`
- Test: `tests/web/browser/flashback.spec.mjs` (новий), `tests/web/test_flashback_api.py` (новий)

**Interfaces:**
- Consumes: поля сцени `flashback` і `flashback_marked` (Task 1), `arc_start` (ядро).
- Produces: тексти — `Спогад` / `Flashback`; пояснення недоступного прапорця — `Спогад задано позначкою в рядку «Початок:».` / `The flashback is set by the mark in the «Start:» line.`; мітка — `спогад` / `flashback`; підказка — `Початок арки невідомий: додайте «Початок:» першій сцені, що не є спогадом.` / `The arc start is unknown: add «Start:» to its first scene that is not a flashback.`

- [ ] **Step 1: Write the failing tests**

```python
# tests/web/test_flashback_api.py — STORY-TIME-S07
def test_patch_flashback_in_an_edition_without_long_prose(client, monkeypatch):
    # видання без long_prose: PATCH {'flashback': True} → 200; сцена в списку має flashback True;
    # build_context спогаду — режим simple (без розділу пам'яті)

def test_structure_reports_arcs_with_unknown_start_only_with_a_flashback(client):
    # книга з аркою без «Початок:» і без спогадів → []; зі спогадом → [arc_id]
```

```js
// tests/web/browser/flashback.spec.mjs — нейтральна книга, локаль uk-UA і en-US
// 1) прапорець «Спогад» ставиться й зберігається; у списку сцен з'являється «спогад»;
// 2) сцена з 'Початок: Рік -2 (спогад)': прапорець checked і disabled, видно пояснення;
// 3) панель «Структура книги» показує підказку біля арки без «Початок:».
```

- [ ] **Step 2: Run them and see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/web/test_flashback_api.py -q`, then `npx playwright test -c frontend/playwright.config.mjs flashback` from the worktree root (з junction `frontend/node_modules` і `.venv`, `PYTHONPATH` на `src` цього worktree)
Expected: FAIL (немає поля `arc_start_unknown`; немає прапорця)

- [ ] **Step 3: Implement**

Прапорець — `<label><input type="checkbox" name="flashback">…</label>` після мови прози. `disabled`, коли `scene.flashback_marked`. Значення надсилається тим самим PATCH. Мітка в списку: `sceneMarks` додає `row.flashback && 'book.badge.flashback'`, де `flashback = scene.flashback || scene.flashback_marked`. Підказка панелі виводиться лише для довгої прози, бо панель там і живе.

- [ ] **Step 4: Run them and see them pass**

Run: the same two commands, plus `npx playwright test -c frontend/playwright.config.mjs scene-settings book-structure memory-merge`
Expected: PASS. Після повного прогону Playwright відновити `docs/images/brief-link-*.png` командою `git checkout -- docs/images` і не комітити їх.

- [ ] **Step 5: Commit**

```bash
git add src/storygen/web tests/web/test_flashback_api.py tests/web/browser/flashback.spec.mjs
git commit -m "feat(time): flashback checkbox, scene mark and arc start hint"
```

### Task 6: Специфікація, незмінність, сайт і журнал

**Files:**
- Modify: `SPEC.MD` (STORY-TIME: S03–S07, технічний опис спогаду й «Минулого інших арок», інваріанти, сумісність знімків; прибрати відоме обмеження «поведінка спогаду — в обв'язці»; згадки в CONTEXT-002, MEMORY-001, BOOK-STRUCTURE, BOOK-LINEAGE)
- Modify: `docs/verification/traceability.json` (STORY-TIME-S03…S07)
- Modify: `docs/site/{uk,en}/memory.md`, `docs/site/{uk,en}/book-structure.md`
- Modify: `docs/superpowers/plans/2026-10-20-remediation-progress.md`, `docs/STATUS.md`
- Test: `tests/memory/test_flashback_invariance.py` (новий)

- [ ] **Step 1: Write the failing test**

```python
# tests/memory/test_flashback_invariance.py — STORY-TIME-S06
def test_book_without_flashbacks_is_unchanged(tmp_path):
    # arc_book 'A B A' і пласка книга: для кожної сцени й етапу brief/draft/memory —
    # жодного селектора flashback/flashback_facts, у memory_schema_bounds немає ключа "flashback",
    # у user_text немає «МИНУЛЕ ІНШИХ АРОК»; відбиток контексту дорівнює відбитку з тією самою книгою,
    # де is_flashback підмінено на lambda s: False (monkeypatch)
```

Решта незмінності — наявні тести пакета, що проходять без змін (як у BOOK-LINEAGE-S01).

- [ ] **Step 2: Run it**

Run: `.venv/Scripts/python.exe -m pytest tests/memory/test_flashback_invariance.py -q`
Expected: PASS. Тест охороняє вже реалізоване: перевірити, що він падає, якщо тимчасово записувати селектор `flashback=False`, і відкотити цю зміну.

- [ ] **Step 3: Docs**

- SPEC.MD: сценарії S03–S07 з тими самими ID, що в специфікації. У traceability — тести з Task 1–6 (`scope` — коротко українською). Перевірка: `python scripts/check_docs.py`, очікувано `OK`.
- Сайт: у `memory` (uk/en) — спогад, його пам'ять і «Минуле інших арок»; у `book-structure` (uk/en) — спогади в книзі з арками й підказка про невідомий початок. Потім `python scripts/check_site.py --rehash memory` і `python scripts/check_site.py --rehash book-structure`. Знімки інтерфейсу не оновлюються. Якщо оновлюються, то лише на нейтральному прикладі.
- Журнал: запис про PR 2, рішення (Ruling-и з Task 1 і Task 4), перевірки.

- [ ] **Step 4: Full verification**

Run: повний `pytest` у фоні з `--basetemp=C:/tmp/st-harness-pytest`; потім `verify.py` з короткого шляху (`git worktree add --detach C:/tmp/st-harness HEAD`, junction `.venv`, запуск, копіювання `docs/STATUS.md` назад, прибирання junction через `cmd /c rmdir` і `git worktree remove --force`).
Expected: `failed 0`; `docs/STATUS.md` з результатом для поточного коміту.

- [ ] **Step 5: Commit**

```bash
git add SPEC.MD docs/verification/traceability.json docs/site docs/superpowers/plans/2026-10-20-remediation-progress.md docs/STATUS.md tests/memory/test_flashback_invariance.py
git commit -m "docs: story time harness — spec, traceability, site, journal"
```
