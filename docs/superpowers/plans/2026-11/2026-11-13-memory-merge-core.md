# Злиття пам'яті, перемішані арки й сцени зустрічі, ядро (проєкт 2, PR 3) — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** сервер приймає перемішані арки в частині й сцени зустрічі; сцена, перед якою сходяться кілька арок, читає підтверджене автором злиття пам'яті (версія `memory_merge`), а без нього контекст не будується й конвеєр зупиняється.

**Architecture:** родовід уже дає голови й `needs_merge` (PR #156); цей план (1) знімає заборону перемішування й додає кілька арок сцени, (2) додає чисте злиття журналів `memory/merge.py`, (3) зберігає злиття як версію твору з головами в payload з CAS, як підсумки #68, (4) замінює всі місця «пам'ять останньої попередньої сцени» однією функцією `memory/previous.py::previous_memory`, яка для сцени зі злиттям повертає версію злиття. Ядро — механізм і API; обв'язка (імпорт `Арки:`, вікно «Злиття пам'яті», множинний вибір арок, позначки в списку сцен, Playwright, сайт, MEMORY-MERGE-S04) — окремий план після рев'ю ядра, у тому самому PR.

**Tech Stack:** Python 3.12, pydantic, FastAPI, SQLite JSON payloads, pytest.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-12-parallel-arcs-design.md` — «Структура», «Родовід», «Злиття», сценарії BOOK-LINEAGE-S02/S03, MEMORY-MERGE-S01/S02/S03/S05.

## Global Constraints

- Пласка книга, книга з послідовними арками й будь-яка книга, де жодна сцена не має `needs_merge`: ті самі запити, відбитки й знімки залежностей, що до зміни; наявні тести проходять без змін (BOOK-LINEAGE-S01).
- `Story.scene_arcs: dict[str, str | list[str]]`; сцена з однією аркою зберігається рядком (payload наявних книг не змінюється), сцена зустрічі — списком щонайменше двох різних арок однієї частини. Читання — лише через `book/structure.py::scene_arc_list`.
- Перевірка структури: частини неперервні за позиціями; кожна активна сцена має щонайменше одну відому арку; арки сцени зустрічі — різні, щонайменше дві, однієї частини. Перемішування арок у частині дозволене.
- Ключ точки злиття: `'heads:' + ','.join(sorted(head_scene_ids))`. Точки: сцени з `needs_merge` і кінець книги, якщо остання частина має кілька голів.
- Версія `memory_merge`: `scene_id=None`, формат JSON, `input_refs` — вибрана пам'ять голів. Голови — `Story.memory_merge_heads: dict[str, str]`, до 10 000 ключів, старі payload — порожній словник, CAS на ревізію твору.
- Подія автора — `source_kind='author'`, `quote=None`, `source_version_id` — вибрана проза найпізнішої за порядком читання голови.
- Текст відмови контексту: «Потрібне злиття пам’яті перед цією сценою»; причина readiness — `memory_merge_required`.
- Без міграції SQLite; без платних викликів моделей; SPEC.MD і traceability — у тому самому коміті, що й код; документація українською.
- Усі запуски Python у worktree — з `PYTHONPATH="$W/src;$W"`, `W=$(pwd -W)`.

## Рішення плану, яких специфікація не фіксує (на затвердження власника)

1. **База злиття — спільний префікс журналів голів, а не пам'ять «найпізнішого спільного предка».** Після злиття на початку частини спільні предки двох арок не мають одного найпізнішого елемента (дві голови попередньої частини не є предками одна одної), тож «пам'ять спільного предка» не визначена. Журнал кожної сцени — журнал попередника плюс нові події (`validate_memory_journal(..., previous)`), тому база = події, чиї джерела входять у перетин `source_prose_ids` усіх голів; вони мусять збігатися в усіх гілках, інакше 400 «Пам’ять арки … спирається на іншу історію; оновіть її». Поле `base_memory_id` версії замінюється на `base_source_prose_ids`. Ціна, якщо неправильно: інша форма версії `memory_merge`, без зміни поведінки.
2. **Однаковий результат у кількох гілках — події лише першої за порядком читання гілки.** Інакше дві однакові `retire` того самого запису валять відтворення журналу.
3. **Рішення `author` для запису, якого в базі немає, з порожнім текстом — нічого не додає** (запис зникає зі злиття).

## Review Focus

- Голова без пам'яті чи з застарілою пам'яттю: `GET` злиття відповідає станом `blocked` з назвою сцени, без 500; `PUT` — 400.
- Автор змінив порядок сцен після підтвердження: ключ точки змінився, контекст відмовляє, рішення переносяться з останньої версії, чиї голови перетинаються з новими.
- Сцена зустрічі, одна з арок якої ще не мала сцен вище: її предки — лише голови наявних арок; без злиття, якщо голова одна.
- Сцена кошика з прив'язкою до кількох арок: відновлення не відмовляє (бере арку сцени перед нею, якщо арки вже не підходять).
- Книга, що закінчується кількома арками: конвеєр на останній сцені не зупиняється, а підсумок останньої частини пояснює, що бракує злиття кінця книги.

---

### Task 1: кілька арок сцени й перемішування

**Files:**
- Modify: `src/storygen/domain.py` (`Story.scene_arcs`)
- Modify: `src/storygen/book/structure.py`
- Modify: `src/storygen/book/protagonists.py` (`arcs_of`)
- Modify: `src/storygen/storage/book_structure.py`, `src/storygen/storage/book_checks.py`
- Modify: `src/storygen/web/routes_structure.py` (`StructureChange.scene_arcs`, `ArcAssignment`)
- Test: `tests/book/test_structure_order.py`, `tests/storage/test_book_structure_meeting.py`

**Interfaces:**
- Produces:
  - `scene_arc_list(scene_arcs: dict, scene_id: str) -> list[str]` — рядок → `[рядок]`, список → копія, немає → `[]`.
  - `canonical_arcs(arcs: list[str]) -> str | list[str]` — один елемент → рядок.
  - `EffectiveStructure.arcs_of: dict[str, tuple[str, ...]]` (лише відомі арки; сцена без відомої арки відсутня); `arc_of` лишається першою аркою для наявних читачів (список сцен, експорт, блоки підсумків).
  - `check_order(structure, scene_arcs, active_scenes) -> list[str]` замінює `check_sequential` (усі виклики й назва ліміту fsck `book_structure_not_sequential` → `book_structure_parts_mixed`).
  - `arc_after_meeting(arcs: list[str], before: str | None) -> str` — арка `before`, якщо вона серед `arcs`, інакше перша; `arc_before` повертає її для сцени зустрічі вище.
  - `assign_scene(repo, story_id, scene_id, arc_ids: list[str], expected_revision)`; `ArcAssignment` приймає `arc_id` або `arc_ids` (рівно одне з двох).

- [ ] **Step 1: тести**
  - `test_interleaved_arcs_are_allowed`: частина з арками А, Б; сцени А, Б, А, Б → `check_order` порожній.
  - `test_parts_must_stay_contiguous`: частина 1, частина 2, знову частина 1 → одне порушення з номером сцени.
  - `test_meeting_scene_needs_two_arcs_of_one_part`: `['a']` у списку, `['a','a']`, арки різних частин → порушення; `['a','b']` однієї частини → ні.
  - `test_single_arc_is_stored_as_string`: `put_structure` з `{'s1': ['a']}` зберігає `'a'`; `{'s1': ['a','b']}` — список.
  - `test_assign_meeting_scene`: `PUT /scenes/{id}/arc` з `arc_ids` двох арок → 200; з `arc_id` — як раніше; з обома — 422.
  - `test_new_scene_after_meeting_scene`: сцена після сцени зустрічі `['a','b']`, перед якою стояла `b` → нова сцена в `b`.
  - `test_restore_meeting_scene_never_refuses`: відновлення сцени зустрічі, одна з арок якої видалена → бере арку сцени перед нею.
- [ ] **Step 2:** `python -m pytest tests/book/test_structure_order.py tests/storage/test_book_structure_meeting.py -q` — FAIL (немає `check_order`).
- [ ] **Step 3:** реалізація за Interfaces; `effective_structure.kind` не змінюється; `protagonists.arcs_of` повертає `scene_arc_list` відомих арок (кошик — `[]`, як зараз).
- [ ] **Step 4:** ті самі тести — PASS; `python -m pytest tests -q -k "structure or book or lineage or protagonist"` — PASS без змін наявних тестів, крім заміни назви `check_sequential` і тексту ліміту fsck.
- [ ] **Step 5:** коміт `feat(book): interleaved arcs and meeting scenes`.

### Task 2: родовід сцен зустрічі й кінця книги

**Files:**
- Modify: `src/storygen/book/lineage.py`
- Test: `tests/book/test_lineage_meeting.py`

**Interfaces:**
- Consumes: `EffectiveStructure.arcs_of` (Task 1).
- Produces:
  - `lineage_map` бере попередників сцени як об'єднання за кожною її аркою (попередня сцена арки або правило першої сцени арки); `previous_in_arc` і `last_of_arc` оновлюються для кожної арки сцени.
  - `merge_key(heads) -> str`.
  - `book_end_heads(story, scenes) -> tuple[str, ...]` — голови останніх сцен арок останньої частини зі сценами (порядок читання); один елемент — злиття не потрібне.

- [ ] **Step 1: тести** (приклади з загального дизайну, ID сцен — `a1, b1, …`):
  - `test_interleaved_arcs_have_own_chains`: частина [А, Б], сцени a1 b1 a2 b2 → `lineage(b2).heads == ('b1',)`, `ancestors == ('b1',)`; `a2.ancestors == ('a1',)`.
  - `test_meeting_scene_merges_arc_heads`: a1 b1 m(А,Б) → `m.heads == ('a1','b1')`, `needs_merge`; наступна a2 → `heads == ('m',)`.
  - `test_part_start_after_interleaved_arcs`: частина 1 [А, Б] a1 b1, частина 2 [В, Г] v1 g1 → `v1.heads == g1.heads == ('a1','b1')`, однаковий `merge_key`.
  - `test_book_end_heads`: остання частина a1 b1 → `('a1','b1')`; послідовна b після a → `('b2',)`.
  - `test_sequential_lineage_is_unchanged`: наявні тести `tests/book/test_lineage*.py` без змін.
- [ ] **Step 2:** `python -m pytest tests/book/test_lineage_meeting.py -q` — FAIL.
- [ ] **Step 3:** реалізація.
- [ ] **Step 4:** `python -m pytest tests/book -q` — PASS.
- [ ] **Step 5:** коміт `feat(book): lineage of meeting scenes and book end`.

### Task 3: чисте злиття журналів

**Files:**
- Create: `src/storygen/memory/merge.py`
- Test: `tests/memory/test_merge_plan.py`

**Interfaces:**
- Consumes: `MemoryJournal`, `MemoryEvent`, `replay_memory`, `_add_event`, `_change_event` (`memory/journal.py`).
- Produces:
  - `shared_base(branches: dict[str, MemoryJournal], order: list[str]) -> MemoryJournal` — рішення плану 1; `ValueError` із ID голови, чий префікс розходиться.
  - `@dataclass Conflict(key: str, values: dict[str, str | None], events: dict[str, list[MemoryEvent]])`; ключ `claim:<id>` або `slot:<character_id>:<slot>`; значення — текст підсумкового запису гілки або `None` (закрито).
  - `@dataclass MergePlan(base: MemoryJournal, clean_events: list[MemoryEvent], conflicts: list[Conflict])`.
  - `plan_merge(branches, order) -> MergePlan` — `order` — ID голів у порядку читання.
  - `build_merged_journal(plan, decisions: dict[str, dict], source_prose_ids: list[str], author_source_id: str) -> MemoryJournal`; рішення `{'choice': head_id | 'author', 'text': str | None}`; `ValueError` з ключем, якщо рішення бракує чи журнал не відтворюється.
  - `carry_decisions(old_conflicts: list[dict], old_decisions: dict, conflicts: list[Conflict]) -> dict` — рішення переноситься, якщо ключ і `values` усіх гілок збігаються.

Правила (специфікація, «Злиття», і рішення плану 2–3):
- Нові події гілки — після `len(base.events)`. Слот-ключ зачеплено, якщо нова подія гілки має цей слот; claim-ключ — для подій без слота.
- Конфлікт — ключ, зачеплений у ≥2 гілках з різним підсумковим значенням. Однакове значення — події першої гілки за `order`. Ключ однієї гілки — у `clean_events`.
- Порядок подій злитого журналу: база, далі всі вибрані події, відсортовані стабільно за (позицією джерела в `source_prose_ids`, індексом гілки в `order`, порядком у гілці), далі події автора.
- Подія автора: слот — `update` активного в базі запису слота, `add` з `slot` (scope — персонаж слота), якщо його немає, `retire` за порожнього тексту й наявного запису; claim — `update`/`retire` запису бази з його категорією й scope, `add` у категорії гілки, якщо в базі запису немає; ID — `_add_event`/`_change_event` з `source_kind='author'`, `quote=None`.

- [ ] **Step 1: тести** (журнали будуються допоміжною функцією тесту з `_extend`, нейтральні тексти «Анна в місті» тощо):
  - `test_change_in_one_branch_merges_cleanly` (S01).
  - `test_different_updates_of_one_record_conflict` (S01): `values == {'h1': 'X', 'h2': 'Y'}`.
  - `test_same_result_in_two_branches_is_not_a_conflict` (S01): обидві гілки закривають запис → у журналі одна `retire`.
  - `test_two_new_records_of_one_slot_conflict` (S05): дві `add` слота `clothing` того самого персонажа → конфлікт `slot:c1:clothing`, жодна з подій не в `clean_events`.
  - `test_retire_against_update_conflicts` (S05).
  - `test_branch_choice_builds_valid_journal` (S05): вибір гілки 2 → `replay_memory` проходить, події гілки 1 цього ключа відсутні.
  - `test_author_value_event_cites_latest_head` (S05): `source_kind == 'author'`, `quote is None`, `source_version_id == author_source_id`.
  - `test_missing_decision_names_the_key`.
  - `test_diverging_prefix_is_rejected`.
  - `test_decisions_carry_only_for_same_values` (S03): той самий ключ з іншим значенням гілки 2 → рішення не переноситься.
- [ ] **Step 2:** `python -m pytest tests/memory/test_merge_plan.py -q` — FAIL (немає модуля).
- [ ] **Step 3:** реалізація.
- [ ] **Step 4:** ті самі тести — PASS.
- [ ] **Step 5:** коміт `feat(memory): pure merge of arc journals`.

### Task 4: версія злиття, голови й стан точки

**Files:**
- Modify: `src/storygen/domain.py` (`VersionKind` + `memory_merge`; `Story.memory_merge_heads`)
- Modify: `src/storygen/storage/repository.py` (формат JSON для `memory_merge`)
- Create: `src/storygen/storage/memory_merges.py`
- Create: `src/storygen/storage/merge_checks.py` (fsck) і підключення поруч із `summary_checks`
- Modify: `src/storygen/dependency_models.py` (поле `memory_merge_heads` у дозволених полях `story`)
- Test: `tests/storage/test_memory_merges.py`

**Interfaces:**
- Consumes: Task 2 (`lineage`, `merge_key`, `book_end_heads`), Task 3.
- Produces:
  - `merge_point(story, scenes, *, scene_id=None, book_end=False) -> MergePoint(key, heads: tuple[str,...], target_scene_ids: tuple[str,...]) | None` — `None`, якщо злиття не потрібне.
  - `merge_state(view, story, scenes, point) -> dict`: `{key, heads: [{scene_id, number, title, arc_titles, memory_id}], state: 'blocked'|'none'|'fresh'|'stale', reason, conflicts: [{key, label, values}], carried: {key: decision}, head_version_id}`; `blocked` — голова без вибраної незастарілої пам'яті (`reason` з номером і назвою сцени) або розбіжний префікс.
  - `usable_merge(view, story, point) -> str | None` — ID версії, якщо голова ключа є, `head_memory_ids` дорівнюють поточній пам'яті голів і версія не застаріла.
  - `save_merge(repo, story_id, key, decisions, expected_revision, expected_head_memory_ids) -> Story` — одна транзакція: перевірка ревізії й пам'яті голів (`RevisionConflict`), `plan_merge` → `build_merged_journal` → `validate_memory_journal` проти прози джерел → версія `memory_merge` (payload `{merge_key, journal, decisions, conflicts, head_memory_ids, base_source_prose_ids}`) → `memory_merge_heads[key]`; понад 10 000 ключів — 400.
  - Перенос рішень: з поточної голови ключа, інакше з останньої версії `memory_merge` твору, чиї `head_memory_ids` належать сценам, що перетинаються з новими головами.

- [ ] **Step 1: тести**
  - `test_save_publishes_version_and_head`: payload, `scene_id is None`, `input_refs == head memory ids`.
  - `test_stale_head_memory_blocks_save` і `test_revision_conflict_keeps_nothing`.
  - `test_new_head_memory_makes_merge_unusable` (S03): нова пам'ять голови → `usable_merge is None`, `merge_state.state == 'stale'`, рішення того самого конфлікту в `carried`.
  - `test_reordered_heads_carry_decisions` (S03).
  - `test_old_payload_reads_empty_merge_heads`.
  - `test_fsck_reports_foreign_merge_head`.
- [ ] **Step 2:** `python -m pytest tests/storage/test_memory_merges.py -q` — FAIL.
- [ ] **Step 3:** реалізація; транзитивна застарілість — звичайні ребра `input_refs`.
- [ ] **Step 4:** ті самі тести — PASS; `python -m pytest tests/storage -q` — PASS.
- [ ] **Step 5:** коміт `feat(memory): memory_merge versions and heads`.

### Task 5: попередня пам'ять сцени через злиття

**Files:**
- Create: `src/storygen/memory/previous.py`
- Modify: `src/storygen/memory/reuse.py` (`_candidate`, `provenance_before`), `src/storygen/memory/service.py` (`publish_memory_journal`), `src/storygen/generation/context.py` (етап memory і письмо), `src/storygen/memory/kinds.py`, `src/storygen/memory/forwarding.py` (`projection_policy`), `src/storygen/storage/snapshots.py` (обидва місця з `previous[-1]`), `src/storygen/generation/dependencies.py` (`_manual_snapshot`), `src/storygen/memory/selection.py` (вікна за родоводом)
- Test: `tests/memory/test_previous_memory.py`, `tests/memory/test_arc_isolation.py`, `tests/test_previous_memory_guard.py`

**Interfaces:**
- Consumes: Task 2, Task 4 (`merge_point`, `usable_merge`).
- Produces:
  - `class MergeRequired(ValueError)` з текстом «Потрібне злиття пам’яті перед цією сценою» і полем `merge_key`.
  - `previous_memory(view, story, scenes, scene, *, peek=False, require=True) -> PreviousMemory(memory_id: str | None, merge_key: str | None, ancestors: list)` — без предків `memory_id=None`; одна голова — пам'ять цієї голови; `needs_merge` — `usable_merge` або `MergeRequired` (`require=False` повертає `memory_id=None` для селекторів і стану).
  - `_candidate` приймає версію `memory_merge` (власник `scene_id None`, `merge_key` збігається) так само, як пам'ять сцени-голови; перевірка `len(source_prose_ids) == len(ancestors)` лишається.
  - Знімки: для сцени зі злиттям замість `head(previous[-1], 'memory')` — селектор `story/memory_merge_heads` `{key: version_id}` і ref версії злиття; для решти — без змін.
  - `SelectionInput` отримує `lineage_numbers: dict[int, int]` (номер книги → номер у родоводі, сцена — останній); `TIMELINE_WINDOW`, `hero_recent` і `replaces` рахують за ним; для ланцюга номери збігаються.

- [ ] **Step 1: тести**
  - `test_merge_scene_without_merge_refuses_context` (S02): `build_context(..., 'brief')` → `MergeRequired`.
  - `test_merged_journal_is_previous_memory` (S02): після `save_merge` етап memory сцени зустрічі бере злитий журнал; ручне збереження пам'яті сцени зустрічі проходить.
  - `test_snapshot_of_merge_scene_selects_merge_head`: новий злиток → текст сцени застарілий.
  - `test_arc_b_sees_no_arc_a_memory` (BOOK-LINEAGE-S03): a1 b1 a2 b2; пам'ять, джерела, хвіст прози й рядки хронології запиту b2 не містять сцен арки А.
  - `test_windows_count_lineage_scenes` (S03).
  - `test_prose_tail_of_merge_scene_is_latest_head`.
  - `test_no_previous_memory_reads_outside_previous_py`: guard — у `src/storygen` немає `[-1].heads.get('memory')` і `[-1].heads['memory']` поза `memory/previous.py`.
- [ ] **Step 2:** `python -m pytest tests/memory/test_previous_memory.py tests/memory/test_arc_isolation.py tests/test_previous_memory_guard.py -q` — FAIL.
- [ ] **Step 3:** реалізація: перехід кожного місця з «Files».
- [ ] **Step 4:** ті самі тести — PASS; повний `python -m pytest -q` — PASS без змін наявних тестів (BOOK-LINEAGE-S01).
- [ ] **Step 5:** коміт `feat(memory): scenes after a merge point read the merge`.

### Task 6: зупинка конвеєра, readiness і API

**Files:**
- Modify: `src/storygen/generation/stages.py` (`execute_stage`: `MergeRequired` → спроба `needs_review` з текстом, без виклику провайдера)
- Modify: `src/storygen/generation/readiness.py` (`MergeRequired` → `ready=False`, `reason` — текст, `reason_code='memory_merge_required'`, `merge_key`)
- Create: `src/storygen/web/routes_memory_merges.py`, підключення в застосунку; запобіжник видання — як для `PUT /structure`
- Test: `tests/generation/test_merge_stop.py`, `tests/web/test_memory_merges_api.py`

**Interfaces:**
- Consumes: Task 4, Task 5.
- Produces:
  - `GET /api/stories/{id}/memory-merges?scene_id=<id>` або `?point=book_end` → `merge_state`; сцена без точки злиття → `{state: 'not_needed'}`.
  - `PUT /api/stories/{id}/memory-merges/{merge_key}` `{decisions, expected_revision, expected_head_memory_ids}` → `{story_revision, version_id}`; 409 на CAS, 400 на невідомий ключ чи брак рішення.

- [ ] **Step 1: тести**
  - `test_run_stops_before_merge_scene` (S02): запуск `remaining` з фейковим провайдером на книзі a1 b1 m → сцени a1, b1 написані, на m стан `needs_review` з текстом, провайдер для m не викликано.
  - `test_readiness_names_memory_merge_required` (S02).
  - `test_book_end_merge_does_not_stop_run` (S05).
  - `test_get_and_put_merge` і `test_put_merge_revision_conflict`.
  - `test_store_edition_refuses_merge_put`.
- [ ] **Step 2:** запуск — FAIL.
- [ ] **Step 3:** реалізація.
- [ ] **Step 4:** ті самі тести — PASS; `python -m pytest tests/generation tests/web -q` — PASS.
- [ ] **Step 5:** коміт `feat(memory): merge API and pipeline stop`.

### Task 7: підсумки частин із кількома арками

**Files:**
- Modify: `src/storygen/memory/summaries.py` (`block_state`), `src/storygen/generation/timeline_summary.py` (`block_inputs`, `_timeline`)
- Test: `tests/memory/test_summary_merge.py`

**Interfaces:**
- Consumes: Task 2, Task 4.
- Produces: `end_of_part_memory(view, story, scenes, block) -> str` — пам'ять кінця частини: одна голова частини або придатне злиття, що відкриває наступну частину; для останньої частини — злиття кінця книги; інакше `ValueError` «Спершу підтвердіть злиття пам’яті в кінці частини». Вхід підсумку й порівняння `memory_version_id` у `block_state` беруть її; пласка книга й частини з однією головою — пам'ять останньої сцени блоку, як зараз.

- [ ] **Step 1: тести** — `test_part_with_two_heads_needs_merge_for_summary`, `test_last_part_summary_reads_book_end_merge` (S05), `test_single_head_part_is_unchanged`.
- [ ] **Step 2:** FAIL. **Step 3:** реалізація. **Step 4:** `python -m pytest tests/memory tests/generation -q -k summary` — PASS.
- [ ] **Step 5:** коміт `feat(memory): part summaries read the end-of-part merge`.

### Task 8: SPEC.MD і traceability

**Files:**
- Modify: `SPEC.MD` (BOOK-STRUCTURE: модель `scene_arcs`, перевірка порядку, API призначення; BOOK-LINEAGE: технічний опис, S02/S03, обмеження; нова вимога MEMORY-MERGE зі сценаріями S01, S02, S03, S05 — S04 додає план обв'язки; CONTEXT-002, MEMORY-001, MEMORY-SELECT (вікна за родоводом), MEMORY-SUMMARY (вхід частини))
- Modify: `docs/verification/traceability.json`
- Modify: `docs/superpowers/plans/2026-10-20-remediation-progress.md`

- [ ] **Step 1:** оновлення тексту; з відомих обмежень прибрати «перемішування арок відхиляється».
- [ ] **Step 2:** `python scripts/check_docs.py` — OK.
- [ ] **Step 3:** повний `python -m pytest -q` — PASS.
- [ ] **Step 4:** коміт `docs(spec): memory merge core`.

Після Task 8 — фінальне рев'ю ядра (як `superpowers:executing-plans`), потім план обв'язки.
