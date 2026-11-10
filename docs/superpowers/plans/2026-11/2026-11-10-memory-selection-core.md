# План: відбір пам'яті під бюджет — ядро (#60, PR 1)

Дизайн: `docs/superpowers/specs/2026-11/2026-11-09-memory-context-selection-design.md` (затверджено 09.11.2026). Цей план покриває лише PR 1: модуль відбору, підключення до збирання контексту brief/draft/edit/rewrite, стратегію `product` у бенчмарку, SPEC MEMORY-SELECT S01–S06 і документацію. Звужений каталог етапу memory (PR 2) і позначки автора (PR 3) — окремі плани після рев'ю ядра.

## Рішення в межах плану

1. **Кандидати — рядки повної проєкції.** Відбір працює з тим самим набором рядків, який рендерить `project_memory` (ядро, стани після фільтра за складом сцени, лінії, факти, хронологія, MEMORY-FORWARD). Тому вибраний текст завжди є підмножиною рядків повного, і запис, якого повна проєкція не показує (стан відсутнього персонажа), не потрапить у запит через FTS. `SelectionInput` замість журналу отримує готові `MemoryItem`; решта полів — як у дизайні.
2. **Рефакторинг без зміни поведінки — окремий коміт.** `project_memory` розкладається на `memory_items(...)` (рядки з метаданими) і `render_memory(...)`. Наявні тести проєкції проходять без змін; байтовий збіг (І1) перевіряє додатковий тест на фікстурі.
3. **Рядок хронології замість резерву — дообрізання.** Дизайн резервує «найдовший можливий рядок» першим. Для 3000 сцен такий резерв (усі номери окремо) з'їдає тисячі символів малого бюджету. Натомість після жадібного добору текст рендериться точно, і, доки він довший за бюджет, вилучається останній доданий нестрижневий запис (рахується в `dropped`). Гарантії ті самі: текст ≤ бюджету, кожна відкинута хронологія позначена (І6), ядро цілісне (І2). Номери сцен у рядку стиснуто в діапазони: `сцени 1–12, 15`.
4. **Ліміт кроків двійкового пошуку — 12.** Після 12 кроків береться найбільший перевірений бюджет, що проходить; він завжди існує, бо нижня межа (ядро + рядок хронології) перевірена першою.
5. **Текст запиту для FTS** — план поточної сцени (`heads.plan`, інакше `beats`) і, лише для draft/edit, `heads.brief`: обидва вже є в `refs`, тож відбір не залежить від матеріалу поза знімком.
6. **Бенчмарк.** `SceneInput` отримує необов'язкове поле `product` (елементи й вхід відбору), яке заповнює лише `extract_story`. Стратегія `product` оцінюється лише на реальних даних; синтетика, наявні стратегії й ключі виводу без змін. Бюджет у токенах міри бенчмарку переводиться в символи двійковим пошуком тієї самої форми, що й у продукті.

## Задачі

### Задача 1 (inline): розкласти `project_memory` на рядки й рендер

`memory/projection.py`:

```python
@dataclass(frozen=True)
class MemoryItem:
    claim_id: str; category: str          # 'core' для слотів ядра
    owner: str | None                     # cid ядра
    line: str                             # рядок без '\n'
    text: str; character_ids: tuple[str,...]; slot: str | None
    source_scene: int | None              # номер сцени джерела останньої події

def memory_items(journal, character_ids, source_scene_numbers, *, hidden_claim_ids=(), forwarded_claim_ids=(), tracked=(), names=None) -> tuple[list[MemoryItem], dict]
def render_memory(items, tracked, names, *, timeline_note=None) -> str
def project_memory(...)  # = render_memory(memory_items(...)) + ті самі метрики
```

`source_scene` для хронології — номер джерела цієї події (як префікс «Сцена N»), для решти — джерело чинної події. Тести: наявні `tests/memory/test_projection.py`, `test_core_projection.py` без змін; новий тест байтового збігу `render_memory(memory_items(...))` з еталонним текстом.

### Задача 2 (dispatch): `memory/selection.py`

```python
@dataclass(frozen=True)
class SelectionInput:
    items: tuple[MemoryItem,...]; scene_id: str; scene_number: int; cast: tuple[str,...]; tracked: tuple[str,...]
    names: Mapping[str,str]; query_text: str; kinds: Mapping[str,str]; scene_day: str | None; day_keys: Mapping[int,str|None]

class CoreOverflow(ValueError): ...

@dataclass(frozen=True)
class MemorySelection:
    text: str; selected_claim_ids: tuple[str,...]; layers: dict[str,int]; dropped: dict[str,int]; timeline_note: str | None; char_budget: int

LAYERS=('core','hero_recent','threads','present','general','facts','timeline','atmosphere','fts')
def classify(inp) -> dict[str,list[MemoryItem]]   # кожен елемент рівно в одному шарі (І7)
def minimal_chars(inp) -> int                     # ядро + порожні розділи + рядок усієї відкинутої хронології
def select_memory(inp, char_budget) -> MemorySelection
```

Шари — за дизайном; відстежуваний «у сцені» — `tracked ∩ cast`. Стан, що містить відстежуваного зі складу, іде в `hero_recent` або `atmosphere`; інші стани зі складу — `present`; стани без `character_ids` — `general`. Лінії й факти — за згадкою основ імен учасників (`name_stems`, `mentions` — копія правил бенчмарку); факт, що згадує лише відстежуваних зі складу, — в атмосферу; решта — `fts`. Хронологія старша за вікно 20 сцен не береться ніколи. Атмосфера — квота 10 % `char_budget`, порядок `sha256(scene_id:claim_id)`. FTS5 trigram у `:memory:`, BM25, рівні за `claim_id`, порожній запит нічого не ранжує. Вартість рядка — `len(line)+1`; далі точний рендер і дообрізання (рішення 3).

Тести `tests/memory/test_selection.py`: кожен шар і І7; перевизначення `core/atmosphere`; `hero_recent` за днем і за трьома сценами; бюджет (текст ≤ бюджету, `dropped` сходиться з кількістю кандидатів); квота й хеш-порядок атмосфери; FTS-рівні й порожній запит; рядок хронології з діапазонами; `CoreOverflow`; детермінізм; повний бюджет вибирає все.

### Задача 3 (dispatch): підключення в `make_context`

- `build_context` будує `memory_items` один раз, рендерить повну секцію як зараз і передає `memory_selector=MemorySelector(index, full_text, inp, metrics)` у `make_context`.
- `make_context`: вимірювання запиту виділено в `_measure(...)`. Якщо повний запит переповнений і селектор є — двійковий пошук `char_budget ∈ [minimal_chars, min(len(full)-1, max_input_chars - chars_без_секції)]`, ≤ 12 кроків, критерій — той самий `token_estimate` усього запиту й `max_input_chars`. Нижня межа не проходить або діапазон порожній → `ContextOverflow` з поясненням «ядро пам'яті не вміщається».
- Метрики: `projection_version='memory-uk-v3-selected'`, `projection_chars` вибраного тексту, `selection={layers, dropped, selected_claim_ids, timeline_note, char_budget, steps}`; попередження контексту «Пам'ять відібрано під бюджет: …».
- Тести `tests/generation/test_context_selection.py`: І1 (без переповнення текст, відбиток і метрики незмінні), відбір при малому `context_tokens`, при малому `max_input_chars`, профіль із діапазоном `[min_bytes, max_bytes]`, переповнення ядра, детермінізм, етап memory не змінюється.

### Задача 4 (dispatch): стратегія `product` у бенчмарку

`memory_bench/model.py::SceneInput.product=None`; `extract.py` заповнює його через `memory_items` і `SelectionInput` (`tracked_characters`, `day_key`). `strategies.py::product(scene, params)` — двійковий пошук `char_budget` під токенний бюджет міри бенчмарку, `Selection` з `layers` і `dropped`; без `product` — помилка. CLI: `product` у `real`, `growth`, `control_cases`, не в синтетиці. Тести `tests/retrieval_bench/test_product.py`; старі без змін.

### Задача 5 (inline): SPEC, traceability, документація, замір

- SPEC.MD: CONTEXT-001 (відбір під бюджет, ядро не обрізається), новий Requirement MEMORY-SELECT S01–S06, MEMORY-002/CONTEXT-002 посилання, відомі обмеження, Source map; traceability.
- `docs/token-budget.md`, `docs/memory-view.md`, англійські відповідники — розділ «Відбір пам'яті під бюджет».
- Бенчмарк на свіжій копії даних (критерій приймання PR 1) і запис у журнал виконання; `python scripts/verify.py` → `docs/STATUS.md`.
