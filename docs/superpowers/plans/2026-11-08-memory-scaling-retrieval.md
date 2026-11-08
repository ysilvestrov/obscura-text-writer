# Масштабування пам'яті й відбір контексту — план реалізації (#25)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Офлайн-бенчмарк лише на читання, який порівнює стратегії відбору пам'яті (повна, А, Б, В) за розміром і покриттям на реальних і синтетичних історіях, плюс дослідницький документ із рекомендацією.

**Architecture:** Пакет `scripts/memory_bench/` поза кодом продукту. Модулі: видобування знімків сцен із копії даних через `Repository` → чисті dataclass без зв'язку з базою → чисті функції стратегій і метрик → агрегований JSON. Тонкий CLI `scripts/memory_retrieval_bench.py`. Синтетичні довгі історії генеруються в пам'яті за виміряними на реальній історії частотами.

**Tech Stack:** Python 3 (stdlib), `sqlite3` FTS5 з токенізатором `trigram` (SQLite 3.53.1 у `.venv` — перевірено), наявний пакет `storygen`, pytest.

**Spec:** [docs/superpowers/specs/2026-11-08-memory-scaling-retrieval-design.md](../specs/2026-11-08-memory-scaling-retrieval-design.md)

## Global Constraints

- Робоча база `data/storygen.sqlite3` не змінюється. CLI приймає лише копію: `storygen.application.workspace_bench._check_data_dir(path, True)` відмовляє робочій теці (`live_data`) і теці без бази (`not_a_data_copy`).
- У виводі, звітах і тестових асертах на вивід немає текстів записів, плану, прози, імен персонажів і claim ID. Дозволено лише агрегати, коди й ID протагоніста.
- Без платних викликів провайдера, без викликів моделі взагалі, без нових залежностей (ні в `pyproject.toml`, ні завантажень моделей).
- Код продукту в `src/storygen` не змінюється. SPEC.MD не змінюється.
- Мова документів — українська. Ідентифікатори коду — англійські.
- Детермінізм: однаковий вхід → ідентичний JSON (`sort_keys=True`, `ensure_ascii=True`, `indent=2`).
- Мовчазного обрізання немає. Запис, що не вмістився, рахується в `dropped_by_budget`, а ядро, що не вмістилося, — в `overflow`.

## Review Focus

1. **Сцена без голови `memory` або з пам'яттю, що потребує підтвердження** (`journal_for_read` кидає `ValueError`). Сцена пропускається з кодом `skipped_needs_confirmation` / `skipped_no_memory`, прогін продовжується. Тест у задачі 2.
2. **Протагоніста немає у складі сцени.** Його ядро однаково потрапляє в контекст Б/В (на відміну від `full`). Тест у задачі 3.
3. **Бюджет менший за ядро.** `overflow=True`, ядро не обрізається, інші шари порожні, від'ємних розмірів немає. Тест у задачі 3.
4. **Короткі імена й апостроф** («Ія», «Мар'яна» / «Мар’яна»). Основа імені менше 3 літер не дає збігів, обидва апострофи нормалізуються. Тест у задачі 3.
5. **Історія з 0 або 1 сценою, порожній склад сцени.** Порожні метрики з `scene_count`, без ділення на нуль. Тести в задачах 4 і 6.

---

## Структура файлів

| Файл | Відповідальність |
|---|---|
| `scripts/memory_bench/__init__.py` | порожній |
| `scripts/memory_bench/model.py` | dataclass `Record`, `SceneInput`, `Selection`; рендер секції; міри токенів |
| `scripts/memory_bench/extract.py` | `Repository` → `list[SceneInput]` (+ коди пропусків), протагоніст, імена |
| `scripts/memory_bench/strategies.py` | `full`, `all_active`, `full_a`, `structural`, `structural_fts`, каталог етапу memory |
| `scripts/memory_bench/metrics.py` | метрики сцени, агрегування, контрольні випадки |
| `scripts/memory_bench/synthetic.py` | частоти з реальної історії → синтетичні `SceneInput` на N сцен; лінійна регресія росту |
| `scripts/memory_retrieval_bench.py` | CLI |
| `tests/memory_bench/conftest.py` | додає `scripts/` у `sys.path`; фікстура синтетичної бази |
| `tests/memory_bench/test_*.py` | тести за задачами |
| `docs/research/2026-11-XX-memory-scaling-retrieval.md` | документ дослідження (задача 7) |

---

### Task 1: Модель, рендер і міри токенів

**Files:**
- Create: `scripts/memory_bench/__init__.py`, `scripts/memory_bench/model.py`
- Create: `tests/memory_bench/conftest.py`, `tests/memory_bench/test_model.py`

**Interfaces:**
- Produces:
  - `Record(claim_id: str, category: str, text: str, character_ids: tuple[str, ...], source_scene: int | None, last_changed_scene: int | None, timeline_kind: Literal['timeline','retired_thread'] | None)` — frozen. `source_scene` — номер сцени (1-based) прози-джерела. `timeline_kind` заповнюється лише для записів хронології.
  - `SceneInput(scene_id: str, number: int, cast: tuple[str, ...], plan_text: str, prose_text: str, records: tuple[Record, ...], timeline: tuple[Record, ...], protagonist: str, names: Mapping[str, str], targets: frozenset[str], first_meetings: int)` — frozen. `records` — активні записи до сцени після `hidden_before`. `timeline` — події хронології в порядку журналу, як їх бере `project_memory`. `targets` — claim ID, які етап memory цієї сцени оновив або закрив.
  - `Selection(strategy: str, record_ids: tuple[str, ...], layers: Mapping[str, int], chars: int, tokens_conservative: int, tokens_realistic: int, overflow: bool, dropped_by_budget: int)`.
  - `render(records: Sequence[Record], timeline: Sequence[Record], summary_chars: int = 0) -> str` — формат `project_memory`: чотири секції з мітками `ФАКТИ / ПОТОЧНІ СТАНИ / ВІДКРИТІ ЛІНІЇ / ХРОНОЛОГІЯ`, рядки `— `, префікс `Сцена N: ` для хронології, `Немає.` для порожньої секції. `summary_chars > 0` додає в хронологію один рядок-заповнювач такої довжини.
  - `tokens_conservative(text: str) -> int` = `len(canonical(text).encode('utf-8')) + 256`, де `canonical` — `storygen.token_budget.core.canonical` (так само, як `utf8_body_conservative` у `core.py:47`).
  - `tokens_realistic(text: str) -> int` = `ceil(len(text) / CHARS_PER_TOKEN)`. `CHARS_PER_TOKEN` — константа з коментарем-посиланням на значення з `docs/research/2026-10-26-local-token-counting.md`. Якщо документ дає діапазон, береться консервативніший край.

- [ ] **Step 1: Write the failing tests** у `tests/memory_bench/test_model.py`. `conftest.py` вставляє `ROOT/'scripts'` у `sys.path`.

```python
def test_render_matches_project_memory_for_same_records(journal_fixture):
    # journal_fixture: MemoryJournal з facts, character_states (scoped і unscoped), open_threads (один retired), timeline
    records, timeline = records_from_journal(journal_fixture, numbers)   # helper у conftest через extract.records_from_journal (Task 2) — до Task 2 будуйте вручну
    expected = project_memory(journal_fixture, [], numbers).text
    assert render(records, timeline) == expected

def test_tokens_conservative_matches_core_fallback():
    assert tokens_conservative('Марія') == len(canonical('Марія').encode('utf-8')) + 256

def test_tokens_realistic_is_ceil():
    assert tokens_realistic('a' * 10) == math.ceil(10 / CHARS_PER_TOKEN)

def test_render_summary_placeholder_length():
    assert len(render([], [], summary_chars=600)) - len(render([], [])) >= 600
```

- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/memory_bench/test_model.py -v`. Expected: FAIL (`ModuleNotFoundError: memory_bench`).
- [ ] **Step 3: Implement** `model.py` за інтерфейсами вище. Порядок секцій — `storygen.memory.journal.CATEGORIES`.
- [ ] **Step 4: Run** той самий pytest. Expected: PASS.
- [ ] **Step 5: Commit** `git add scripts/memory_bench tests/memory_bench && git commit -m "Add memory bench model, render and token measures (#25)"`

---

### Task 2: Видобування знімків сцен із копії даних

**Files:**
- Create: `scripts/memory_bench/extract.py`
- Modify: `tests/memory_bench/conftest.py` (фікстура синтетичної бази)
- Create: `tests/memory_bench/test_extract.py`

**Interfaces:**
- Consumes: `Record`, `SceneInput` (Task 1).
- Produces:
  - `records_from_journal(journal: MemoryJournal, numbers: Mapping[str, int], hidden: set[str]) -> tuple[tuple[Record, ...], tuple[Record, ...]]` — активні записи (через `replay_memory`, без `hidden`) і хронологія (події `timeline` плюс `open_threads` з `operation=='retire'`, як у `project_memory`). `last_changed_scene` — номер сцени останньої події цього claim.
  - `extract_story(repo: Repository, story_id: str, protagonist: str | None = None) -> tuple[list[SceneInput], dict[str, int]]` — сцени в порядку `position`. Другий елемент — лічильник кодів пропуску (`skipped_no_memory`, `skipped_needs_confirmation`, `skipped_no_plan`).
  - `name_stems(name: str) -> tuple[str, ...]` — нижній регістр, `’`→`'`, розбиття на слова. Для слова довжиною > 4 основа — слово без останньої літери, інакше слово ціле. Основи коротші за 3 літери відкидаються.

Джерела даних (функції продукту, лише читання):
- журнал до сцени — `storygen.memory.reuse.journal_for_read(repo, scene.id)` (`ValueError` → `skipped_needs_confirmation`);
- приховані — `storygen.memory.forwarding.hidden_before(repo, scene.id)`;
- номери сцен для прози — як у `generation/context.py:224-225`;
- цілі сцени — події журналу `load_memory(repo.read_text(scene.heads['memory']))`, яких немає в журналі до сцени, з `operation in {'update','retire'}` → їхні `claim_id`; без голови `memory` цілі порожні, а сцена — `skipped_no_memory`, якщо немає й журналу до неї;
- план — `repo.read_text(scene.heads['plan'])`, інакше `scene.beats`;
- проза — `repo.read_text(scene.heads['prose'])`, якщо є, інакше `''`;
- імена — `load_characters(repo.read_text(story.characters_version_id))` (`storygen.characters`, див. `characters/context.py:20-22`) → `{record.id: record.name}`; без карток — `{}`;
- протагоніст — аргумент, інакше ID, що найчастіше трапляється в `scene.character_ids` (за рівності — найменший ID);
- `first_meetings` — кількість персонажів складу сцени, яких не було в складі жодної попередньої сцени.

- [ ] **Step 1: Write the failing tests.** Фікстура `synthetic_repo(tmp_path)` будує через API продукту (за зразком `workspace_bench._build_story` і `tests/memory/test_forwarding.py`) історію на 4 сцени з картками на 2 персонажів («Марія», «Остап»). Пам'ять містить: факт зі згадкою «Марію»; стан Марії (scoped), оновлений у сцені 3; відкриту лінію, закриту в сцені 4; один запис, прихований автором після сцени 2.

```python
def test_extract_targets_are_updates_and_retires_of_that_scene(synthetic_repo):
    scenes, skipped = extract_story(*synthetic_repo)
    assert scenes[2].targets == {STATE_CLAIM} and scenes[3].targets == {THREAD_CLAIM}

def test_extract_respects_hidden_before(synthetic_repo):
    scenes, _ = extract_story(*synthetic_repo)
    assert HIDDEN_CLAIM not in {r.claim_id for r in scenes[2].records}

def test_extract_protagonist_defaults_to_most_frequent_cast(synthetic_repo):
    scenes, _ = extract_story(*synthetic_repo)
    assert scenes[0].protagonist == MARIA_ID

def test_extract_skips_scene_needing_confirmation(repo_with_unconfirmed_memory):
    scenes, skipped = extract_story(*repo_with_unconfirmed_memory)
    assert skipped['skipped_needs_confirmation'] == 1

def test_extract_first_meetings(synthetic_repo):
    scenes, _ = extract_story(*synthetic_repo)
    assert [s.first_meetings for s in scenes] == EXPECTED_FIRST_MEETINGS

def test_name_stems_inflection_and_apostrophe():
    assert name_stems('Марія') == ('марі',) and name_stems('Мар’яна') == name_stems("Мар'яна")
    assert name_stems('Ія') == ()

def test_records_from_journal_render_parity(synthetic_repo):   # замінює ручну побудову з Task 1
    ...  # render(records_from_journal(j, numbers, set())) == project_memory(j, [], numbers).text
```

- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/memory_bench/test_extract.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `extract.py`. Перевести тест паритету рендеру з Task 1 на `records_from_journal`.
- [ ] **Step 4: Run** `.venv/Scripts/python.exe -m pytest tests/memory_bench -v`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "Extract per-scene memory snapshots for the bench (#25)"` (з `git add` нових файлів).

---

### Task 3: Стратегії відбору й бюджет

**Files:**
- Create: `scripts/memory_bench/strategies.py`
- Create: `tests/memory_bench/test_strategies.py`

**Interfaces:**
- Consumes: `SceneInput`, `Selection`, `render`, міри токенів (Task 1); `name_stems` (Task 2).
- Produces:
  - `Params(memory_budget_tokens: int, measure: Literal['conservative','realistic'], core_mode: Literal['upper','lower'], core_recent_scenes: int = 3, atmosphere_share: float = 0.10, timeline_window: int = 20, chapter_scenes: int = 10, summary_chars: int = 600)` — frozen.
  - `STRATEGIES: dict[str, Callable[[SceneInput, Params], Selection]]` з ключами `full`, `all_active`, `full_a`, `structural`, `structural_fts`.
  - `mentions(record: Record, stems: Iterable[str]) -> bool` — основа збігається з початком слова в `record.text.lower()` (з нормалізацією апострофа).

Правила стратегій:
- `full` — рівно правило `project_memory`: стани зі scope поза складом відкидаються. Рендер через `render`. `overflow` = розмір > бюджету; нічого не обрізається.
- `all_active` — усі `records` + уся `timeline`.
- `full_a` — `full`, але хронологія старша за `timeline_window` сцен замінюється заповнювачем `ceil(old_scenes / chapter_scenes) * summary_chars`.
- `structural` — шари в такому порядку; кожен береться, доки вміщається в бюджет за вибраною мірою:
  1. `core` — стани протагоніста (scope містить протагоніста). У режимі `lower` — лише з `last_changed_scene >= number - core_recent_scenes`, старші йдуть в `atmosphere`. Ядро береться завжди. Якщо ядро саме перевищує бюджет, то `overflow=True` і решта шарів порожня.
  2. `present` — стани зі scope, що перетинає `cast`.
  3. `general` — стани без scope.
  4. `threads` — відкриті лінії, що згадують когось із `cast` або протагоніста.
  5. `facts` — факти, що згадують когось із `cast` або протагоніста.
  6. `timeline` — останні `timeline_window` сцен повністю, старші — заповнювачем, як у `full_a`.
  7. `atmosphere` — кандидати: старші стани протагоніста (режим `lower`) і факти зі згадкою протагоніста, що не потрапили в шар 5. Ліміт — `atmosphere_share * memory_budget_tokens`. Порядок — за `sha256(f'{scene_id}:{claim_id}')`.
  
  Записи, що не вмістилися в межах шарів 2–7, рахуються в `dropped_by_budget`.
- `structural_fts` — `structural`, після чого залишок бюджету добирається з невибраних `records` через in-memory `sqlite3` FTS5 `tokenize='trigram'`. Запит — слова `plan_text` довжиною ≥ 3, екрановані в лапках і з'єднані `OR`. Порядок — `bm25` зростанням, далі `claim_id`. Порожній запит нічого не добирає.

- [ ] **Step 1: Write the failing tests** на синтетичних `SceneInput`, побудованих у тесті (без бази):

```python
def test_full_equals_project_memory_rule(): ...          # той самий набір ID, що дає правило project_memory
def test_core_included_even_when_protagonist_not_in_cast():
    sel = STRATEGIES['structural'](scene(cast=('c2',), protagonist='c1'), params())
    assert CORE_ID in sel.record_ids and CORE_ID not in STRATEGIES['full'](scene(cast=('c2',), protagonist='c1'), params()).record_ids
def test_core_overflow_keeps_core_and_empties_rest():
    sel = STRATEGIES['structural'](big_core_scene(), params(memory_budget_tokens=300))
    assert sel.overflow and set(sel.record_ids) == CORE_IDS and sel.dropped_by_budget > 0 and sel.chars > 0
def test_budget_never_exceeded_without_overflow():
    for n in (500, 2000, 8000):
        sel = STRATEGIES['structural_fts'](rich_scene(), params(memory_budget_tokens=n))
        assert sel.overflow or measure(sel) <= n
def test_core_lower_moves_old_states_to_atmosphere(): ...
def test_atmosphere_rotation_deterministic_and_varies_between_scenes():
    a = STRATEGIES['structural'](scene(id='s1'), p); b = STRATEGIES['structural'](scene(id='s1'), p); c = STRATEGIES['structural'](scene(id='s2'), p)
    assert a == b and atmosphere_ids(a) != atmosphere_ids(c)
def test_mentions_inflected_name_and_short_name():
    assert mentions(rec('Бачили Марію вчора'), name_stems('Марія'))
    assert not mentions(rec('Ія прийшла'), name_stems('Ія'))
def test_fts_fills_remainder_with_ties_by_claim_id(): ...
def test_fts_empty_plan_adds_nothing(): ...
def test_full_a_saves_chars_on_long_timeline(): ...
```

- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/memory_bench/test_strategies.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `strategies.py`.
- [ ] **Step 4: Run** `.venv/Scripts/python.exe -m pytest tests/memory_bench -v`. Expected: PASS.
- [ ] **Step 5: Commit** `"Add memory selection strategies with explicit budget (#25)"`.

---

### Task 4: Каталог етапу memory і метрики

**Files:**
- Modify: `scripts/memory_bench/strategies.py`
- Create: `scripts/memory_bench/metrics.py`, `tests/memory_bench/test_metrics.py`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces:
  - `catalog_full(scene: SceneInput) -> Selection` — змінні записи (`character_states`, `open_threads`) і незмінні тексти. Розмір рахується за `memory_catalog_v3` на тих самих записах (реалізувати через рендер того ж JSON, `separators=(',',':')`).
  - `catalog_narrow(scene: SceneInput, params: Params) -> Selection` — змінні записи шарів `core` (режим `upper`), `present`, `general`, `threads`, плюс FTS-добір змінних записів за запитом із `prose_text`. Незмінні — лише ті, що вибрав би `structural`.
  - `scene_metrics(scene: SceneInput, sel: Selection) -> dict` з ключами `chars`, `tokens_conservative`, `tokens_realistic`, `overflow`, `dropped_by_budget`, `targets`, `targets_hit`, `core_size`, `atmosphere_count`, `layers`.
  - `aggregate(rows: list[dict], selections: list[Selection]) -> dict` з ключами: `scene_count`; `chars` (`mean`/`max`); `tokens_*` (`mean`/`max`); `fits_rate`; `overflow_scenes`; `target_recall` (= Σhit/Σtargets, `None` при Σtargets=0); `scenes_with_missed_target`; `atmosphere_mean`; `atmosphere_jaccard_adjacent` (середня схожість атмосферних наборів сусідніх сцен); `first_meetings_total`.
  - `control_hits(cases: list[dict], selections_by_scene: Mapping[str, Selection], skipped: set[str]) -> list[dict]` — вхід `{"scene_id", "claim_id"}`. Вихід — `{"index", "hit": bool | None, "reason": "missing_in_memory" | "scene_skipped" | None}`, без ID. Запис, якого немає в `records` сцени, дає `missing_in_memory` (поза межами #25 → #41).

- [ ] **Step 1: Write the failing tests**

```python
def test_target_recall_counts_hits(): ...                       # 2 цілі, 1 у виборі → 0.5
def test_aggregate_empty_story():
    assert aggregate([], [])['scene_count'] == 0 and aggregate([], [])['target_recall'] is None
def test_narrow_catalog_contains_all_targets_on_fixture(): ...   # цілі — стани присутніх і пов'язана лінія
def test_narrow_catalog_smaller_than_full_on_rich_scene(): ...
def test_control_hits_missing_in_memory_and_no_ids_in_output():
    out = control_hits([{'scene_id': 's3', 'claim_id': 'absent'}], sels, set())
    assert out == [{'index': 0, 'hit': None, 'reason': 'missing_in_memory'}]
def test_jaccard_adjacent(): ...
```

- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/memory_bench/test_metrics.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `.venv/Scripts/python.exe -m pytest tests/memory_bench -v`. Expected: PASS.
- [ ] **Step 5: Commit** `"Add memory-stage catalog narrowing and bench metrics (#25)"`.

---

### Task 5: Синтетичні довгі історії й регресія росту

**Files:**
- Create: `scripts/memory_bench/synthetic.py`, `tests/memory_bench/test_synthetic.py`

**Interfaces:**
- Consumes: `SceneInput`, `Record` (Task 1).
- Produces:
  - `Rates` — frozen. На сцену: нові записи кожної категорії, частка оновлень/закриттів станів і ліній, середня довжина тексту запису за категорією, розмір складу, частка сцен із протагоністом, кількість персонажів, частка нових персонажів.
  - `measure_rates(scenes: list[SceneInput]) -> Rates` — лише агрегати з реальної історії.
  - `generate(rates: Rates, scene_count: int, seed: int = 0) -> list[SceneInput]` — детермінований генератор (`random.Random(seed)`). Тексти — синтетичні рядки потрібної довжини, із вставленими іменами персонажів відповідно до scope, щоб `mentions` працював. План сцени містить імена складу.
  - `fit_linear(points: list[tuple[int, float]]) -> tuple[float, float]` — найменші квадрати (нахил, зсув), без numpy. Порожній вхід або одна точка → `ValueError`.

- [ ] **Step 1: Write the failing tests**

```python
def test_generate_is_deterministic(): assert generate(R, 50, seed=1) == generate(R, 50, seed=1)
def test_generate_rates_roundtrip(): ...   # measure_rates(generate(R, 2000)) у межах 10 % від R за ключовими полями
def test_fit_linear_exact(): assert fit_linear([(1, 3.0), (2, 5.0), (3, 7.0)]) == pytest.approx((2.0, 1.0))
def test_structural_size_bounded_on_long_synthetic():
    scenes = generate(R, 3000)
    assert max(STRATEGIES['structural'](s, P).chars for s in scenes[-50:]) <= P_BUDGET_CHARS_BOUND
```

- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/memory_bench/test_synthetic.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `.venv/Scripts/python.exe -m pytest tests/memory_bench -v`. Expected: PASS.
- [ ] **Step 5: Commit** `"Add synthetic long-story generator and growth fit (#25)"`.

---

### Task 6: CLI

**Files:**
- Create: `scripts/memory_retrieval_bench.py`, `tests/memory_bench/test_cli.py`

**Interfaces:**
- Consumes: усе вище.
- CLI: `--data <копія теки даних>` (обов'язковий), `--story <префікс ID>`, `--protagonist <ID>`, `--context 32768,65536,131072`, `--output-reserve 8192`, `--other-context auto|<tokens>`, `--memory-share 0.25`, `--core-recent 3`, `--synthetic 300,3000`, `--control-cases <file>`, `--seed 0`.
- Решта контексту (`--other-context auto`): з останньої завершеної спроби `draft` цієї сцени (`repo.list_attempts(story_id, scene_id=…)`) — оцінка всього запиту мінус оцінка секції пам'яті з `context_breakdown`. Якщо даних немає, береться `memory_share * (context - output_reserve)`; у виводі `other_context_source: attempt|share` з лічильником.
- Бюджет пам'яті = `context - output_reserve - other_context`, мінімум 0.
- Вивід (stdout): `{"story": {"scene_count", "skipped", "protagonist_id", "first_meetings_total"}, "real": {<context>: {<measure>: {<strategy>[core=<mode>]: aggregate}}}, "memory_stage": {<context>: {"full": aggregate, "narrow": aggregate}}, "growth": {<strategy>: {"slope_chars", "intercept_chars", "projected": {"300", "3000"}}}, "synthetic": {<N>: {<context>: {<strategy>: aggregate}}}, "control_cases": [...] | null, "params": {...}}`.
- Коди помилок (stderr, exit 2): `live_data`, `not_a_data_copy`, `story_not_found`, `db_unreadable`. Повідомлення винятків не друкуються.

- [ ] **Step 1: Write the failing tests**

```python
def test_cli_refuses_live_data(): assert run_cli(['--data', str(ROOT/'data')]).returncode == 2 and 'live_data' in stderr
def test_cli_output_has_no_texts_or_claim_ids(synthetic_repo_dir):
    out = run_cli(['--data', str(synthetic_repo_dir), '--synthetic', '50'])
    assert out.returncode == 0
    for secret in ALL_RECORD_TEXTS + ALL_CLAIM_IDS + ['Марія', 'Остап']: assert secret not in out.stdout
def test_cli_does_not_modify_database(synthetic_repo_dir):
    before = sha256(db_bytes); run_cli([...]); assert sha256(db_bytes) == before
def test_cli_deterministic(synthetic_repo_dir): assert run_cli(args).stdout == run_cli(args).stdout
def test_cli_single_scene_story(one_scene_dir): assert json.loads(run_cli([...]).stdout)['story']['scene_count'] == 1
```

> Примітка щодо незмінності бази. `Repository(copy)` може записувати в копію (WAL, міграції). Тест хешує базу після першого відкриття фікстурою, тобто перевіряє, що бенчмарк сам нічого не змінює. Якщо відкриття `Repository` змінює файл навіть без операцій, тест хешує стан після `Repository(...)`, а CLI відкриває копію лише один раз.

- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/memory_bench/test_cli.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `.venv/Scripts/python.exe -m pytest tests/memory_bench -v`, далі `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/check_docs.py`. Expected: PASS / OK.
- [ ] **Step 5: Commit** `"Add memory retrieval bench CLI (#25)"`.

---

### Task 7: Прогін на копії реальних даних і документ дослідження

**Files:**
- Create: `docs/research/2026-11-XX-memory-scaling-retrieval.md` (дата — день прогону)
- Modify: `docs/superpowers/plans/2026-10-20-remediation-progress.md`, `docs/STATUS.md` (через `verify.py`)

- [ ] **Step 1: Копія даних.** Коли застосунок не працює, скопіювати `data/storygen.sqlite3` (разом із `-wal`/`-shm`, якщо вони не порожні) і теки файлів версій у scratch-теку сесії. Робочу теку не відкривати на запис.
- [ ] **Step 2: Прогін** `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/memory_retrieval_bench.py --data <копія> --story <68-сценова> --synthetic 300,3000 > <scratch>/bench-68.json`, те саме для 11-сценової історії. Також `scripts/memory_replay.py --db <копія>/storygen.sqlite3 --data <копія>` для частоти `target_unknown`/`target_twice`. JSON зберігати в scratch, не в репозиторії. У документ іде лише агреговане.
- [ ] **Step 3: Документ дослідження** за розділом 4 дизайну: методика й наближення (згадка імені, дві межі ядра, моделювання А, дві міри токенів, синтетика), таблиці за стратегіями × контекстами × мірами, каталог етапу memory, прогноз для 300/3000, рекомендація + дешевший варіант і що він втрачає, модель даних (тип запису ядро/атмосфера, строк дії й дні історії, знайомства для планувальника, ієрархічні підсумки та їх інвалідація), жанровий огляд, кабінетна оцінка Г (залежності, розмір моделі, відтворюваність; без завантажень) і ризики векторного RAG, збереження MEMORY-001/002, CONTEXT-001, CONTEXT-003 і відтворюваності `ContextBundle`, зв'язки з #41, #31, #39. Контрольні випадки — «немає, підтримка є».
- [ ] **Step 4: Перевірка** `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/verify.py` (оновлює `docs/STATUS.md`) і `scripts/check_docs.py`. Expected: 0 failed / OK.
- [ ] **Step 5: Журнал виконання** — запис про #25: що виміряно, головні цифри, рекомендація, наступний крок (design spec із грою оцінок, якщо рекомендація змінює архітектуру), «SPEC.MD не змінюється, інструкції UA/EN не потребують змін: код продукту не змінено».
- [ ] **Step 6: Commit, push, PR на `main`** з посиланням на #25 і причиною, чому документація користувача не змінюється. Після злиття оновити основну теку (`git checkout main && git pull --ff-only`) і перевірити ревізію.
