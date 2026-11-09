# Знайомства для планувальника — план реалізації (#43)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Мета:** планувальник, чернетка й переписування отримують блок знайомств головного героя. Brief повертає `introduced`, тобто кого представлено в сцені.

**Архітектура:** чистий модуль `src/storygen/characters/acquaintance.py` містить три частини:
- розбір позначок у картках;
- визначення протагоніста;
- підрахунок знайомств за родоводом прийнятої прози попередніх сцен, із запасним правилом.

`build_context` вставляє готовий текст після карток. `WritersBrief` отримує необов'язкове поле `introduced`. Типовим промптом brief стає `brief_uk_v2.txt`. Схеми SQLite, CharacterRecord і Scene не змінюються.

**Технології:** Python 3.12, pydantic, pytest; запуск `.venv/Scripts/python.exe -m pytest`.

**Специфікація:** [docs/superpowers/specs/2026-11/2026-11-09-planner-acquaintances-design.md](../../specs/2026-11/2026-11-09-planner-acquaintances-design.md) (затверджено 2026-11-09). Розділи «Модель і правила», «Межі родоводу» й «Залежності» — обов'язкові.

## Global Constraints

- Нічого не записувати в live-дані `data/`. Тести працюють лише на `tmp_path` через `Repository(tmp_path)`.
- Фікстури мають нейтральні імена (Анна, Богдан, Віра, Галина). У звітах і попередженнях тільки ID, коди й кількості, без текстів карток чи прози.
- Позначка протагоніста: рядок, який після зняття `**`, `*`, `-`, `—` і пробілів, без регістру й кінцевих `.`, `:`, `!` дорівнює одному з варіантів: `протагоніст`, `протагоністка`, `головний герой`, `головна героїня`.
- Позначка знайомства: рядок, що без регістру починається з одного з варіантів `знайомий з`, `знайома з`, `знайомі з`, `знайм з`, далі `:`. Імена розбирає `scene_description.split_participants`, зіставляє `scene_description.resolve_participants`.
- Знайомство симетричне. «Знайомий з:» враховується лише з відомостей, доступних для поточної сцени (правила `project_characters`). Позначка протагоніста діє незалежно від доступності.
- Протагоніст:
  - перша картка з позначкою в порядку набору;
  - якщо позначених кілька — попередження;
  - якщо немає жодної — перший ID складу найранішої активної сцени з непорожнім складом;
  - якщо немає й складу — протагоніста немає.
- `WritersBrief.introduced: list[str] | None = None`. `None` означає «не сказано», а `[]` — «нікого». Контракт промпту brief лишається `schema_version=1`: поле необов'язкове, тож власні промпти v1 сумісні.
- Обхід родоводу йде лише через версії тієї самої сцени. Brief у родоводі читається, навіть якщо він `stale`. ID історичних brief НЕ додаються ні до `refs`, ні до `inputs`.
- Блок будується лише тоді, коли протагоніст є в складі поточної сцени. У блок потрапляють лише учасники `cast(S) \ {H}`. Номер сцени в блоці дорівнює `position + 1`.
- Блок отримують етапи `brief`, `draft`, `rewrite`; етапи `edit` і `memory` — ні.
- Мова коду, повідомлень і документації — українська. Маркери OpenSpec англійські.

## Review Focus

1. Brief у родоводі став застарілим після зміни карток, а прозу Q автор прийняв. Наступна сцена має будуватися без `source_stale`. Тест у Task 3: `test_stale_lineage_brief_does_not_block_next_scene`.
2. `introduced` містить ID поза складом сцени або сам протагоніст. Такі ID ігноруються під час підрахунку, а запуск brief отримує попередження без значень. Тести в Task 2 і Task 3.
3. Попередня сцена без прийнятої прози (лише план або чернетка) нічого не додає, і в ній немає помилки «немає brief». Тест у Task 2.
4. Перестановка сцен: знайомства перераховуються за новими позиціями, а номер «з якої сцени» змінюється. Тест у Task 2.
5. «Знайомий з:» з невідомим або неоднозначним ім'ям дає попередження, але не блокує генерацію. Тест у Task 1.

---

### Task 1: Позначки в картках і протагоніст

**Files:**
- Create: `src/storygen/characters/acquaintance.py`
- Test: `tests/characters/test_acquaintance_markers.py`

**Interfaces:**
- Consumes: `characters.models.CharacterRecord`, `scene_description.split_participants`, `scene_description.resolve_participants`, `domain.Scene` (`id`, `position`, `character_ids`, `trashed_at`, `story_id`).
- Produces:
  - `is_protagonist_line(line: str) -> bool`
  - `known_names_line(line: str) -> list[str] | None` — повертає імена або `None`, якщо рядок не є позначкою.
  - `protagonist(cards: list[CharacterRecord], scenes: list[Scene]) -> tuple[str | None, list[str]]` — повертає `(id, warnings)`.
  - `pre_story_known(cards, scenes, scene_id: str, hero_id: str) -> tuple[set[str], list[str]]` — множина ID, знайомих з героєм до початку історії (симетрично, з урахуванням доступності), і попередження.

- [ ] **Step 1: Write the failing tests**

```python
def test_protagonist_line_variants():
    for line in ['Протагоніст','**Головний герой.**','- головна героїня:','— Протагоністка!']:
        assert is_protagonist_line(line)
    assert not is_protagonist_line('Протагоніст іншої історії')

def test_known_names_line_parses_and_ignores_other_lines():
    assert known_names_line('Знайомий з: Анна, Богдан (сусід; давно)')==['Анна','Богдан (сусід; давно)']
    assert known_names_line('**знайм з:** Віра')==['Віра']
    assert known_names_line('Вік: 30.') is None

def test_protagonist_marker_beats_first_cast_and_warns_on_duplicates():
    # cards B(marker), C(marker); earliest non-empty scene cast ['A','B']
    hero,warnings=protagonist(cards,scenes)
    assert hero=='B' and len(warnings)==1

def test_protagonist_defaults_to_first_of_earliest_nonempty_cast():
    # scene pos0 cast [], pos1 cast ['C','A'] -> 'C'; trashed scenes ignored
    assert protagonist(cards_without_markers,scenes)==('C',[])

def test_protagonist_marker_ignores_availability():
    # marker entry from_scene anchored at scene 3 still selects hero for scene 1

def test_pre_story_known_is_symmetric_and_respects_availability():
    # A is hero; B card says 'Знайомий з: Анна' (timeless) -> {'B'}
    # C card says 'Знайомий з: Анна' but from_scene anchored at position 4 -> absent for scene at position 2, present at 4

def test_unknown_known_name_warns_without_blocking():
    known,warnings=pre_story_known(cards,scenes,scene_id,'A')   # 'Знайомий з: Невідомий'
    assert known==set() and warnings and 'Невідомий' not in ' '.join(warnings)
```

Збирай картки через `CharacterRecord.model_validate(dict(schema_version=2,id=...,name=...,entries=[dict(id=...,text=...,availability=...,available_from_scene_id=...,origin='author')]))`. Сцени — як `domain.Scene`, створені через `Repository(tmp_path)`, або через `SimpleNamespace` з потрібними атрибутами.

- [ ] **Step 2: Run, expect FAIL** — `.venv/Scripts/python.exe -m pytest tests/characters/test_acquaintance_markers.py -q` → ImportError.
- [ ] **Step 3: Implement.** Доступність перевіряй тими самими правилами, що й `characters/projection.py::project_characters`: якір `from_scene` має позицію ≤ поточної; відсутній чи чужий якір → `ValueError`, як там. Виділи спільну функцію `entry_available(entry, active_scenes, scene) -> bool` у `projection.py` і використовуй її в обох місцях, не змінюючи поведінки `project_characters`. Попередження без імен, наприклад: `'Позначка «Знайомий з:» містить невідоме або неоднозначне ім’я; перевірте картки.'`
- [ ] **Step 4: Run, expect PASS**, плюс `tests/characters` повністю.
- [ ] **Step 5: Commit** `feat(characters): acquaintance markers and protagonist (#43)`.

### Task 2: Поле `introduced` і підрахунок знайомств за родоводом

**Files:**
- Modify: `src/storygen/generation/models.py` (`WritersBrief`), `src/storygen/generation/planner_output.py` (`FIELDS` + `'introduced'`)
- Modify: `src/storygen/characters/acquaintance.py`
- Test: `tests/characters/test_acquaintance_history.py`, `tests/generation/test_planner_output.py` (додати тести)

**Interfaces:**
- Consumes: Task 1; read-only view (`repo.context_view(story_id)`) з методами `list_scenes`, `get_version`, `read_text`, `get_story`; `VersionRef.input_refs`, `kind`, `scene_id`, `created_at`.
- Produces:
  - `lineage_brief(view, scene) -> VersionRef | None` — найновіший за `created_at` brief цієї сцени в родоводі `heads['prose']`. Обхід іде через `input_refs` версій `draft`/`edited`/`manual`/`brief` тієї ж сцени.
  - `@dataclass(frozen=True) class Acquaintances: hero_id: str | None; known: dict[str, int | None]; warnings: list[str]`. Ключ `known` — ID персонажа, значення — номер сцени (`position+1`) або `None` для «до початку історії».
  - `acquaintances(view, story, scene) -> Acquaintances`. Картки береться з `story.characters_version_id`. Якщо карток немає, повертається `Acquaintances(None, {}, [])`.

**Правило** (зі специфікації). Для кожної активної Q з `position < scene.position` і `heads.get('prose')`, у порядку позицій:
- якщо H ∉ cast(Q) → нічого;
- якщо `lineage_brief` існує і його `introduced is not None` → `set(introduced) ∩ cast(Q) \ {H}`;
- інакше → `cast(Q) \ {H}`.

Перша сцена, де персонаж з'явився, задає його номер. Позначки «до початку історії» мають пріоритет (`None`).

- [ ] **Step 1: Write failing tests**

```python
def test_introduced_field_optional_and_distinguishes_null_from_empty():
    assert WritersBrief.model_validate_json('{"objective":"o","beats":["b"]}').introduced is None
    assert WritersBrief.model_validate_json('{"objective":"o","beats":["b"],"introduced":[]}').introduced==[]

def test_introduced_wrong_type_reports_field():  # in test_planner_output.py
    # parse_planner_output('{"objective":"o","beats":["b"],"introduced":"A"}','brief',[]) raises; planner_failure message startswith 'introduced'

def test_lineage_brief_wins_over_newer_head():
    # scene1: brief b1(introduced=['B']) -> draft(input_refs=[b1]) -> edited prose(input_refs=[draft]) as head; later brief b2(introduced=[]) set as head
    # acquaintances for scene2 (cast [A,B,C]) -> known=={'B':1}

def test_fallback_for_prose_without_brief_and_legacy_brief():
    # scene1 manual prose, cast [A,B]; scene2 brief without introduced -> draft -> prose, cast [A,C]
    # scene3 -> known=={'B':1,'C':2}

def test_explicit_empty_introduced_keeps_unknown():
    # lineage brief introduced=[] , cast [A,B] -> scene2: 'B' not in known

def test_ids_outside_cast_and_hero_ignored():
    # introduced=['A','Z','C'] with cast(Q)=[A,B] (A hero) -> nothing from Q (C not in cast(Q))

def test_scene_without_accepted_prose_adds_nothing():
    # scene1 has only plan/draft head, no prose -> known=={}

def test_hero_absent_from_past_scene_adds_nothing():

def test_reorder_changes_scene_numbers():
    # after moving scene with first meeting from position 0 to 1, number becomes 2

def test_pre_story_tag_wins_with_none():
```

Версії створюй через `repo.save_version(story.id, scene.id, kind, text, input_refs)` і `repo.set_head(...)`, як у `tests/generation/test_scene_cast_filter.py`. Brief — `WritersBrief(...).model_dump_json()`.

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.** Поле `introduced: list[str] | None = None` ставиться після `proposed_changes`. Повтори в списку прибираються з `introduced`, порядок зберігається (валідатор). `lineage_brief` читає `introduced` через `WritersBrief.model_validate_json(view.read_text(id))`; brief, який не розбирається, вважається відсутнім (запасне правило). Застарілість не перевіряється.
- [ ] **Step 4: Run, expect PASS**, плюс `tests/generation/test_planner_output.py tests/characters`.
- [ ] **Step 5: Commit** `feat: introduced field and lineage-based acquaintances (#43)`.

### Task 3: Блок у контексті, промпт brief v2, попередження запуску

**Files:**
- Modify: `src/storygen/characters/acquaintance.py` (рендер блоку)
- Modify: `src/storygen/generation/context.py` (`build_context`, одразу після `character_material`)
- Create: `src/storygen/generation/resources/brief_uk_v2.txt`
- Modify: `src/storygen/generation/prompts.py` (`default_prompt('brief')` → v2; решта етапів лишається на v1)
- Modify: `src/storygen/generation/stages.py` (після `parse_planner_output` для `brief`)
- Test: `tests/generation/test_acquaintance_context.py`; оновити `tests/generation/test_prompt_contracts.py`, якщо там фіксується текст або ім'я промпту brief

**Interfaces:**
- Consumes: Task 2 — `acquaintances(view, story, scene) -> Acquaintances`.
- Produces:
  - `acquaintance_material(view, story, scene, stage: str) -> tuple[str, list[str]]` повертає `(text, warnings)`. Текст порожній, якщо: немає героя; героя немає в cast(S); у cast(S) \ {H} нікого; або `stage not in {'brief','draft','rewrite'}`.
  - `unexpected_introduced(scene, hero_id: str | None, introduced: list[str] | None) -> bool`.

Блок (точна шапка; формулювання рядків інструкції лишено будівельнику):

```
ЗНАЙОМСТВА ГОЛОВНОГО ГЕРОЯ — <ім'я героя>
Знайомі: <Ім'я> (до початку історії); <Ім'я> (зі сцени N)
Ще не представлені: <Ім'я> [id=<ID>]; ...
<інструкція>
```

- Для `brief` інструкція каже: не називати ще не представлених на ім'я, доки їх не представлено в тексті; якщо представлення відбувається в цій сцені, додати їхні ID в `introduced`.
- Для `draft`/`rewrite` інструкція та сама, але без згадки поля.
- Порожній рядок «Знайомі»/«Ще не представлені» не виводиться.
- `[id=…]` виводиться лише для `brief`.

- [ ] **Step 1: Write failing tests**

```python
@pytest.mark.parametrize('stage',['brief','draft','rewrite'])
def test_block_present_for_writing_stages(stage):  # first scene, hero A marked, cast [A,B], B card 'Знайомий з: Анна' -> 'Знайомі: Богдан (до початку історії)'

@pytest.mark.parametrize('stage',['edit','memory'])
def test_block_absent_for_edit_and_memory(stage):

def test_brief_block_lists_unintroduced_with_ids_and_field_instruction():
    # cast [A,C], no tags -> 'Ще не представлені: Віра [id=C]' and 'introduced' in text

def test_no_block_when_hero_not_in_cast():

def test_stale_lineage_brief_does_not_block_next_scene(tmp_path):
    # scene1 lineage brief marked stale (repo stale mechanism after cards change), prose head edited + memory head present;
    # build_context(repo, scene2.id, 'brief', settings) succeeds, and the brief ID is not in bundle refs

def test_default_brief_prompt_is_v2_and_mentions_introduced():
    assert 'introduced' in default_prompt('brief')

def test_brief_run_warns_on_unexpected_introduced():
    assert unexpected_introduced(scene_with_cast_AB,'A',['C'])
    assert unexpected_introduced(scene_with_cast_AB,'A',['A'])
    assert not unexpected_introduced(scene_with_cast_AB,'A',['B'])
    assert not unexpected_introduced(scene_with_cast_AB,'A',None)
```

Контекст будуй через `build_context(repo, scene.id, stage, RoleSettings(provider=ProviderSettings(model='fake'), edit_mode='patches' if stage=='edit' else 'prose'))`, як у `tests/generation/test_scene_cast_filter.py`. Для `memory` потрібна прийнята проза поточної сцени. Для `rewrite` потрібна чернетка: `editor_source_id`.

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
  - `brief_uk_v2.txt` = v1 плюс поле `introduced` у JSON-формі відповіді (`"introduced":["ID"]`) і одне речення про його зміст.
  - У `stages.py` після розбору brief: якщо `unexpected_introduced(...)`, додати до `attempt.context['planner_warnings']` текст `'Планувальник: introduced містить ID поза складом сцени або головного героя; їх не враховано.'`
  - У `build_context` блок додається до `sections` після карток, попередження — до `warnings`. До `refs` нічого не додається.
- [ ] **Step 4: Run, expect PASS**, плюс `.venv/Scripts/python.exe -m pytest tests/generation tests/characters -q`.
- [ ] **Step 5: Commit** `feat(generation): acquaintance block in brief/draft/rewrite, brief prompt v2 (#43)`.

### Task 4: SPEC.MD, traceability, користувацька документація

**Files:**
- Modify: `SPEC.MD` — новий `### Requirement: PLANNER-ACQUAINTANCE` після `CHARACTER-TIME`, з якорем `<a id="planner-acquaintance"></a>`. Згадати `introduced` у `PLANNER-JSON`.
- Modify: `docs/verification/traceability.json`
- Modify: `docs/scene-description.md` (розділ «# Персонажі»), `docs/en/characters.md`
- Modify: `docs/superpowers/plans/2026-10-20-remediation-progress.md` (запис про #43 і #44)

- [ ] **Step 1:** Написати Requirement зі Scenarios `PLANNER-ACQUAINTANCE-S01…S05`, як у розділі специфікації «SPEC.MD і перевірки». Кожен Scenario має `<a id>`, GIVEN/WHEN/THEN. Окремо додати відомі обмеження: знайомство — намір планувальника; запасне правило до #44; блоку немає, якщо героя немає в складі.
- [ ] **Step 2:** Додати до traceability записи S01–S05 з конкретними тестами з Task 1–3.
- [ ] **Step 3:** Run `.venv/Scripts/python.exe scripts/check_docs.py` → без помилок.
- [ ] **Step 4:** Документація UA/EN: позначки «Протагоніст/Головний герой» і «Знайомий з:» (взаємність, часова мітка), поле `introduced` у завданні, умова «герой у складі сцени». Знімки інтерфейсу не потрібні, бо UI не змінюється.
- [ ] **Step 5:** Повний набір тестів: `.venv/Scripts/python.exe -m pytest -q` → зелений.
- [ ] **Step 6: Commit** `docs: PLANNER-ACQUAINTANCE spec, traceability, user docs (#43)`.
