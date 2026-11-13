# Час історії, ядро (PR 1): позначки часу й порядок моментів — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Рядок `Початок:` розпізнає відносні позначки «Рік/Місяць/День» у будь-якому порядку, від'ємні значення, «невідомо» й позначку спогаду; з'являються порядок моментів і початок арки, а ключі дня старих форм не змінюються.

**Architecture:** Розбір і порядок — чисті функції в `memory/story_time.py` (`Moment`, `scene_moment`, `before`, `flashback_marked`); ключ дня, підпис і `day_change` переходять на `Moment`, зберігаючи рядкові ключі `day:N` і `date:…`. Початок арки — `book/story_time.py::arc_start`. Поведінка спогаду (поле сцени, пам'ять, контекст, «Минуле інших арок») — план обв'язки (PR 2).

**Tech Stack:** Python 3.12, pytest; без змін схеми SQLite.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-13-story-time-flashbacks-design.md` (розділ «Позначка часу»; перевірки STORY-TIME-S01, S02).

## Global Constraints

- Ключі дня старих форм: `day:N` для `день N`/`day N`, `date:Д.М.РРРР` для дат (`1.3.24`, `01.03.2024`, `1.3.2024` → `date:1.3.2024`) — байт у байт як зараз.
- Нова відносна форма з роком чи місяцем має ключ `rel:Р.М.Д`; `невідомо`/`unknown` — ключа немає (`None`).
- Розмітка розпізнається обома мовами незалежно від мови твору: `Початок`/`Start`, `Рік`/`Year`, `Місяць`/`Month`, `День`/`Day`, `невідомо`/`unknown`, `(спогад)`/`(флешбек)`/`(flashback)`; регістр неважливий; Markdown-розмітку рядка знято (`plain_line`), як зараз.
- Порядок моментів — лише всередині одного виду (`rel` з `rel`, `date` з `date`); відсутня складова — нуль; перерахунку в дні немає.
- Назви структури книги не входять у запити моделей (BOOK-STRUCTURE).
- Документація українською, маркери OpenSpec англійською; кожен Scenario — у `docs/verification/traceability.json`; `python scripts/check_docs.py` проходить; сайт uk/en парою з `python scripts/check_site.py --rehash memory`.

## Review Focus

- `Початок: день 3` без години (сьогодні не розпізнається) — тепер `day:3`; книга з такими рядками один раз отримає новий ключ дня. Очікування: так і є, і це описано в SPEC як нова форма, а не як регресія.
- Позначка спогаду без моменту (`Початок: (спогад)`) і позначка після дати (`Початок: 01.03.2024, 08:00 (флешбек)`) — момент `None` і дата відповідно, позначка розпізнана.
- Складова двічі (`Рік 1, Рік 2`) або сміття в рядку (`Рік 1 вечір`) — рядок не розпізнається як позначка (момент `None`), без винятку.
- Той самий день з годиною й без (`День 3` і `День 3, 08:00`) — `before` повертає `None`, а не довільний порядок.
- Арка, перша сцена якої — спогад або в кошику — початок береться з першої активної сцени, що не є спогадом.

---

### Task 1: Розбір позначки часу

**Files:**
- Modify: `src/storygen/memory/story_time.py`
- Test: `tests/memory/test_story_time.py`

**Interfaces:**
- Produces: `Moment` (frozen dataclass: `kind: Literal['rel','date','unknown']`, `key: tuple[int,int,int] | None`, `minutes: int | None`, `legacy_day: bool`); `scene_moment(beats: str) -> Moment | None` (`None` — немає розпізнаного рядка `Початок:` або в ньому лише позначка спогаду); `flashback_marked(beats: str) -> bool`; `scene_start(beats) -> tuple[str, str | None] | None` — як зараз для старих форм (`(ключ, 'ГГ:ХХ')`), для нових — `(ключ, година або None)`, для `невідомо` — `None`.

- [ ] **Step 1: Write the failing tests**

```python
from storygen.memory.story_time import Moment, scene_moment, flashback_marked, scene_start

def test_legacy_keys_are_unchanged():
    assert scene_start('Початок: 12.03.2024, 22:00') == ('date:12.3.2024', '22:00')
    assert scene_start('Початок: 1.3.24, 08:00') == ('date:1.3.2024', '08:00')
    assert scene_start('**Початок:** день 3, 07:15') == ('day:3', '07:15')
    assert scene_start('Start: day 4, 06:00') == ('day:4', '06:00')

def test_relative_forms_in_any_order():
    assert scene_moment('Початок: Рік 2, День 14, 08:00') == Moment('rel', (2, 0, 14), 480, False)
    assert scene_moment('Початок: День 14 Рік 2') == Moment('rel', (2, 0, 14), None, False)
    assert scene_moment('Start: Year -20, Month 3') == Moment('rel', (-20, 3, 0), None, False)
    assert scene_start('Початок: Рік 2, Місяць 1, День 14') == ('rel:2.1.14', None)

def test_day_only_keeps_the_day_key():
    assert scene_start('Початок: день 3') == ('day:3', None)
    assert scene_moment('Початок: День -2, 23:30') == Moment('rel', (0, 0, -2), 1410, True)

def test_unknown_and_flashback_marks():
    assert scene_moment('Початок: невідомо') == Moment('unknown', None, None, False)
    assert scene_start('Start: unknown') is None
    assert scene_moment('Початок: (спогад)') is None and flashback_marked('Початок: (спогад)')
    assert scene_start('Початок: 01.03.2024, 08:00 (флешбек)') == ('date:1.3.2024', '08:00')
    assert flashback_marked('Start: Year -5 (Flashback)') and not flashback_marked('Початок: Рік 1')

def test_malformed_lines_are_not_moments():
    for line in ('Початок: Рік 1, Рік 2', 'Початок: Рік 1 вечір', 'Початок: 32 грудня', 'Day 2, 06:00'):
        assert scene_moment(line) is None and scene_start(line) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/memory/test_story_time.py -q`
Expected: FAIL — `ImportError: cannot import name 'Moment'`.

- [ ] **Step 3: Implement the parser in `src/storygen/memory/story_time.py`**

Розбір рядка: перший рядок beats, що після `plain_line` починається з `Початок:`/`Start:`. Спершу відрізати хвостову позначку `\(\s*(спогад|флешбек|flashback)\s*\)` (регістр неважливий) — це `flashback_marked`. Решта — одна з форм: стара дата з комою й годиною (`canonical_date`, як зараз), `невідомо`/`unknown`, або послідовність складових `(рік|year|місяць|month|день|day)\s+([+-]?\d+)`, розділених комою чи пробілами, далі необов'язково `,\s*ГГ:ХХ`; уся решта рядка мусить бути з'їдена, кожна складова — не більше разу, інакше `None`. `legacy_day=True`, коли є лише складова дня (тоді ключ `day:N`); з роком чи місяцем — `rel:Р.М.Д`. `minutes` — `ГГ*60+ХХ` або `None`. Стара форма `день N, ГГ:ХХ` — окремий випадок відносної, ключ `day:N` збігається зі старим.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/memory/test_story_time.py tests/authoring/test_scene_plan_template.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/storygen/memory/story_time.py tests/memory/test_story_time.py
git commit -m "feat(time): parse relative story time marks and the flashback mark"
```

### Task 2: Порядок моментів, ключ і підпис дня, зміна дня

**Files:**
- Modify: `src/storygen/memory/story_time.py`
- Test: `tests/memory/test_story_time.py`

**Interfaces:**
- Consumes: `Moment`, `scene_moment` (Task 1).
- Produces: `before(a: Moment | None, b: Moment | None) -> bool | None`; `day_key(scene) -> str | None` (через `scene_start`); `day_label(key, language) -> str` приймає `rel:Р.М.Д`; `day_change(scenes, scene, character_id, story=None) -> bool` порівнює моменти.

- [ ] **Step 1: Write the failing tests**

```python
from storygen.memory.story_time import before, day_label, scene_moment as m

def test_before_compares_one_kind_only():
    assert before(m('Початок: Рік -20'), m('Початок: Рік 1, День 3')) is True
    assert before(m('Початок: День 30'), m('Початок: Рік 1')) is True
    assert before(m('Початок: Рік 1, День 3'), m('Початок: Рік 1, День 3')) is False
    assert before(m('Початок: 01.03.2024, 08:00'), m('Початок: Рік 1')) is None
    assert before(m('Початок: невідомо'), m('Початок: Рік 1')) is None and before(None, m('Початок: Рік 1')) is None
    assert before(m('Початок: День 3, 08:00'), m('Початок: День 3, 09:00')) is True
    assert before(m('Початок: День 3'), m('Початок: День 3, 09:00')) is None

def test_relative_day_label():
    assert day_label('rel:2.0.14', 'uk') == 'рік 2, день 14' and day_label('rel:2.0.14', 'en') == 'year 2, day 14'
    assert day_label('rel:-20.3.0', 'uk') == 'рік -20, місяць 3'
    assert day_label('day:3', 'uk') == 'день 3' and day_label('date:1.3.2024', 'uk') == '1.3.2024'

def test_day_change_between_day_and_relative_forms():
    a = sc('a', 0, ['h'], 'Початок: Рік 0, День 2')
    assert day_change([a], sc('b', 1, ['h'], 'Початок: день 3, 08:00'), 'h') is True
    assert day_change([a], sc('b', 1, ['h'], 'Початок: День 2, 23:00'), 'h') is False
    assert day_change([a], sc('b', 1, ['h'], 'Початок: невідомо'), 'h') is False
    assert day_change([a], sc('b', 1, ['h'], 'Початок: 02.01.2024, 08:00'), 'h') is False
```

(`sc` — наявний помічник файла.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/memory/test_story_time.py -q`
Expected: FAIL — `ImportError: cannot import name 'before'`.

- [ ] **Step 3: Implement `before`, `day_label` for `rel`, `day_change` on moments**

`before`: `None`, якщо будь-який момент відсутній, `unknown` або види різні; інакше порівняти `key`; при рівних `key` — порівняти `minutes`, коли обидві задані, інакше `None`; рівні моменти — `False`. `day_label('rel:…')`: ненульові складові в порядку рік → місяць → день («рік N», «місяць N», «день N» / «year», «month», «day»); якщо всі нульові — «день 0». `day_change`: моменти попередньої сцени й поточної мають той самий вид (`rel`/`date`, не `unknown`) і різні `key`. Для пар старих форм результат той самий, що зараз (тести `test_day_change_same_form_only` лишаються без змін).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/memory tests/generation/test_writer_day_change.py tests/storage/test_memory_core_selectors.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/storygen/memory/story_time.py tests/memory/test_story_time.py
git commit -m "feat(time): order story moments and compare days across mark forms"
```

### Task 3: Початок арки

**Files:**
- Create: `src/storygen/book/story_time.py`
- Test: `tests/book/test_arc_start.py`

**Interfaces:**
- Consumes: `scene_moment`, `flashback_marked` (Task 1); `effective_structure(story, scenes).arc_of` (`book/structure.py`; для сцени зустрічі — `arcs_of`).
- Produces: `is_flashback(scene) -> bool` (у цьому PR — лише `flashback_marked(scene.beats)`; PR 2 додає поле сцени); `arc_start(story, scenes, arc_id: str) -> Moment | None`.

- [ ] **Step 1: Write the failing tests**

Чисті об'єкти, як у `tests/book/test_lineage.py` (без сховища):

```python
from storygen.book.story_time import arc_start, is_flashback
from storygen.domain import Arc, BookStructure, Part, Scene, Story
from storygen.memory.story_time import scene_moment


def book(beats, arcs, trashed=()):
    scenes = [Scene(id=f's{i}', story_id='b', position=i, title=f'Сцена {i + 1}', beats=text,
                    trashed_at='2026-11-13T00:00:00Z' if i in trashed else None) for i, text in enumerate(beats)]
    structure = BookStructure(parts=[Part(id='p1', title='Одна', arcs=[Arc(id='A'), Arc(id='B')])])
    return Story(id='b', title='Книга', book_structure=structure, scene_arcs={s.id: a for s, a in zip(scenes, arcs)}), scenes


def test_arc_start_is_the_first_scene_that_is_not_a_flashback():
    story, scenes = book(['Початок: Рік -20 (спогад)', 'Без позначки', 'Початок: Рік 1, День 3', 'Початок: Рік 2'], ['A', 'B', 'A', 'B'])
    assert is_flashback(scenes[0]) and not is_flashback(scenes[2])
    assert arc_start(story, scenes, 'A') == scene_moment('Початок: Рік 1, День 3')
    assert arc_start(story, scenes, 'B') is None


def test_arc_start_skips_trashed_scenes():
    story, scenes = book(['Початок: Рік 5', 'Початок: Рік 9', 'Початок: Рік 1', 'Початок: Рік 9'], ['A', 'B', 'A', 'B'], trashed={0})
    assert arc_start(story, scenes, 'A') == scene_moment('Початок: Рік 1')


def test_a_meeting_scene_can_open_its_arcs():
    story, scenes = book(['Початок: Рік 3', 'Початок: Рік 4'], [['A', 'B'], 'B'])
    assert arc_start(story, scenes, 'A') == scene_moment('Початок: Рік 3')
    assert arc_start(story, scenes, 'B') == scene_moment('Початок: Рік 3')
```

Якщо `check_order` не приймає сцену зустрічі першою сценою арки, третій тест будує `scene_arcs` напряму — `arc_start` читає `effective_structure`, а не перевірку порядку.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/book/test_arc_start.py -q`
Expected: FAIL — `ModuleNotFoundError: storygen.book.story_time`.

- [ ] **Step 3: Implement `is_flashback` and `arc_start` in `src/storygen/book/story_time.py`**

Активні сцени (без `trashed_at`) у порядку `position`; перша, що належить арці (`arc_id in structure.arcs_of[scene.id]`) і не `is_flashback`; повернути її `scene_moment(beats)` (зокрема `None`, якщо позначки немає).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/book -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/storygen/book/story_time.py tests/book/test_arc_start.py
git commit -m "feat(time): arc start from the first scene that is not a flashback"
```

### Task 4: SPEC, сайт, перевірки

**Files:**
- Modify: `SPEC.MD`, `docs/verification/traceability.json`, `docs/site/uk/memory.md`, `docs/site/en/memory.md`, `docs/site/sync.json`, `docs/superpowers/specs/2026-11/2026-11-13-story-time-flashbacks-design.md`, `docs/superpowers/plans/2026-10-20-remediation-progress.md`

**Interfaces:**
- Consumes: усе з Task 1–3.

- [ ] **Step 1: SPEC.MD**

Нова вимога `STORY-TIME — Час історії й спогади` після MEMORY-MERGE (запис у змісті поруч з `MEMORY-MERGE`): опис позначки, `Moment`, `before`, `arc_start`, правило ключів; Scenario `STORY-TIME-S01 — Розбір позначок` і `STORY-TIME-S02 — Порядок і початок арки` з текстом зі специфікації; «Відомі обмеження»: спогад поки лише розпізнається (`flashback_marked`), поведінку спогаду додає PR обв'язки. Оновити MEMORY-003 (опис сигналу переходу дня, рядок про `scene_start`) і рядок про шаблони («єдиний виняток — рядок «Початок:»…») під нові форми й ключ `rel:`; MEMORY-003-S06 лишається чинним.

- [ ] **Step 2: Специфікація — уточнення тіла**

У розділі «Позначка часу» специфікації: позначка лише з днем (`день 3`, `День -2`, з годиною чи без) має ключ `day:N`; `rel:Р.М.Д` — лише з роком чи місяцем. Розділ власника не змінюється.

- [ ] **Step 3: Traceability**

`STORY-TIME-S01` → `tests/memory/test_story_time.py::test_legacy_keys_are_unchanged`, `::test_relative_forms_in_any_order`, `::test_day_only_keeps_the_day_key`, `::test_unknown_and_flashback_marks`, `::test_malformed_lines_are_not_moments`; `STORY-TIME-S02` → `::test_before_compares_one_kind_only`, `::test_day_change_between_day_and_relative_forms`, `tests/book/test_arc_start.py` (усі три тести).

- [ ] **Step 4: Сайт**

`docs/site/uk/memory.md` і `docs/site/en/memory.md`: у місці, що описує рядок `Початок:`, — нові форми (рік, місяць, день у будь-якому порядку, від'ємні значення, необов'язкова година, «невідомо») з нейтральним прикладом. Run: `python scripts/check_site.py --rehash memory`. Expected: «Пару memory підтверджено».

- [ ] **Step 5: Run checks**

Run: `python scripts/check_docs.py` → Expected: «…узгоджені». Run: `pytest -q` (повний, у фоні, `--basetemp` під `C:\tmp`) → Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add SPEC.MD docs
git commit -m "docs: story time core — spec, traceability, site"
```
