# Доказ узгодженості серії, етап 1: план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** стенд B, що міряє, чи знаходить нова перевірка узгодженості підкладені нестиковки в англомовній серії на Claude, з конфігураціями входу K0–K4, суддею, обліком витрат і воротами на відкладеному наборі.

**Architecture:** пакет `scripts/continuity_bench/` за зразком `scripts/editor_bench/` і `scripts/memory_bench/`. Продуктовий код (розбір рукопису, побудова пам'яті, витяг карток, відбір пам'яті, знімок серії, провайдер) імпортується зі `storygen` без сховища й вебзастосунку. Нові частини — лише в стенді: промпт перевірки, план сцени з прози, суддя, метрики. Тексти, кеш відповідей і облік витрат лежать у `C:\tmp\continuity-bench\` і ніколи не потрапляють у репозиторій.

**Tech Stack:** Python 3.12, `storygen` (src), OpenAI SDK через продуктовий `build_openai_client` (OpenRouter), pytest.

**Spec:** [docs/superpowers/specs/2026-11/2026-11-28-continuity-proof-design.md](../specs/2026-11/2026-11-28-continuity-proof-design.md)

## Global Constraints

- Тексти книжок не комітяться. У репозиторії лежать маніфест (URL + SHA-256), латки, касти й звіт (бріф 4.1).
- Модель за замовчуванням — `anthropic/claude-sonnet-5.5` через OpenRouter (рішення виконавця плану; див. «Рішення плану»). Ключ — `OPENROUTER_API_KEY` з `C:\Projects\text-generator\.env`.
- Загальний ліміт етапу 1 — **$50** за обліком `C:\tmp\continuity-bench\spend.json`. Перед кожною платною серією — `--plan` з оцінкою і згода власника в чаті. Якщо прогноз перевищує залишок, запуск відмовляє (бріф, рішення 5).
- Відкладений набір: латки лежать лише в `C:\tmp\continuity-bench\heldout\`, доки не відбулися ворота; запуск `--gate` можливий один раз (маркер-файл) і лише після того, як власник затвердив пороги (вже затверджено 28.11.2026).
- Пороги — дослівно з бріфу 6.3: повнота ≥ 0,80; між книжками ≥ 0,70; за кожним типом ≥ 0,60; точність ≥ 0,70; хибні тривоги на контролі ≤ 1 на 10 тис. слів; дискусійні ≤ 1 на 10 тис. слів; чесність цитат 1,00; перевага над K0: повнота +0,15 або та сама за меншої вартості.
- Кошики знахідок — дослівно з бріфу 6.2a (`planted`, `original`, `explained`, `no_conflict`, `vague`, `fabricated`, `duplicate`, `wrong_fact_place`, `arguable`).
- pytest і довгі прогони — з короткого шляху `C:/tmp/<коротка-назва>` (AGENTS.md, WinError 206).
- Код, ідентифікатори й коментарі — англійською, як у `scripts/editor_bench`; звіт і документи — українською.
- Змін продукту (`src/`) у цьому плані немає; SPEC.MD не змінюється. Перенесення в продукт — окрема специфікація після воріт (бріф 7.2).

## Рішення плану (виконавець плану, на перевірку власнику)

- **Провайдер — OpenRouter, а не прямий Anthropic API.** У продукті немає провайдера Anthropic (`ProviderSettings.provider ∈ {local, openrouter, venice}`), тому прогін A однаково піде через OpenRouter. B на тому самому шляху не потребує нового коду провайдера, і результат B переноситься в A. Мінус: немає Batch API (−50%) і явного кешування промптів; економію дає дисковий кеш відповідей.
- **Модель — Sonnet 5.5** ($2 / $10 за 1 млн токенів у Anthropic; ціну OpenRouter `--plan` бере з його API моделей). Opus 5.5 удвічі дорожчий ($4 / $20) і з'їв би ліміт на воротах. Якщо власник хоче Opus для воріт, потрібно ~ +$15.
- **K4 без повної ручної розмітки.** K4 = пам'ять K1 плюс «факти-місця» з латок, додані як записи пам'яті з дослівною цитатою. Цього досить, щоб відокремити помилки Ревізора від помилок побудови, і не треба розмічати всі факти книжки.
- **K3: план сцени з прози — промпт стенду.** Продуктової ролі «план з прози» немає. Промпт пише коротко: хто, де, коли (момент історії), що змінилося.

## Кошторис (оцінка; уточнює `--plan`)

Англійська ≈ 1,3 токена на слово; сцена ≈ 2 500 слів.

| Крок | На сцену (вхід / вихід, токенів) | Набір розробки, ~40 тис. слів (16 сцен) | Серія, ~300 тис. слів (120 сцен) |
|---|---|---|---|
| Пам'ять (кешується на конфігурацію входу) | 15 тис. / 2 тис. | ≈ $1,1 | ≈ $8 |
| Картки й план (K2/K3, раз на корпус) | 8 тис. / 1 тис. | ≈ $0,4 | ≈ $3 |
| Перевірка одного прогону | 30 тис. / 1,5 тис. | ≈ $1,2 | ≈ $9 |
| K0 (вся книжка/серія одним запитом) | — | ≈ $0,2 | ≈ $1–2 |

Бюджет етапу: ітерації на частині dev ≈ $15–20, повний dev для кандидата ≈ $8, ворота (3 повтори перевірки + пам'ять + K0 + суддя) ≈ $15–20. Запас ≈ $5. Ітерацію, що робить повторну побудову пам'яті, позначати в `--plan` окремо: вона найдорожча.

## Review Focus

1. **Типографські лапки й дефіси.** Латка з `"…"`, а в тексті `“…”`, або модель цитує з прямими лапками. Очікування: застосування латок і перевірка цитат порівнюють нормалізований текст (лапки, апострофи, тире, пробіли) і знаходять збіг. Тест — у задачі 2 і задачі 6.
2. **Стабільні адреси латок.** Зміна правил поділу на сцени не має ламати латки. Очікування: латка адресується книжкою й дослівним фрагментом, а не номером сцени; сцена визначається після застосування. Тест — задача 2.
3. **Повтор перерваного прогону.** Перерваний прогін, запущений знову, бере відповіді з кешу й не записує витрату вдруге. Тест — задача 3.
4. **Цитата через межу сцен або переказ.** Знахідка з цитатою, якої немає дослівно в процитованій сцені, — `fabricated`, навіть якщо вона є в сусідній сцені. Тест — задача 6.
5. **Заголовок і колонтитул Project Gutenberg.** Ліцензійний текст не має потрапити в першу чи останню сцену. Тест — задача 1.

---

### Task 1: Корпус — маніфест, завантаження, сцени

**Files:**
- Create: `scripts/continuity_bench/__init__.py`, `scripts/continuity_bench/corpus.py`
- Create: `docs/research/data/continuity/manifest.json`
- Test: `tests/continuity_bench/__init__.py`, `tests/continuity_bench/conftest.py`, `tests/continuity_bench/test_corpus.py`

**Interfaces:**
- Produces:
  - `ROOT = Path(r'C:\tmp\continuity-bench')`
  - `@dataclass(frozen=True) class Book: series: str; key: str; title: str; url: str; sha256: str; order: int`
  - `@dataclass(frozen=True) class Scene: book: str; index: int; id: str; title: str; text: str; words: int` — `id = f'{book}-{index:03d}'`
  - `load_manifest(path: Path) -> dict[str, list[Book]]` (серія → книжки за `order`)
  - `fetch(book: Book, root: Path = ROOT) -> str` — завантажує один раз у `root/'texts'/f'{book.key}.txt'`, звіряє SHA-256 сирих байтів, повертає текст без заголовка й колонтитулу Gutenberg
  - `strip_gutenberg(text: str) -> str` — вирізає все до рядка `*** START OF` і від `*** END OF`
  - `split_scenes(book_key: str, text: str) -> list[Scene]` — через `storygen.publication.manuscript_read.read_manuscript` і `manuscript_structure.detect` (продуктовий поділ)

- [ ] **Step 1: Write the failing tests** — `conftest.py` додає `scripts/` у `sys.path` (як `tests/retrieval_bench/conftest.py`).

```python
def test_strip_gutenberg_removes_licence():
    raw = 'Header\n*** START OF THE PROJECT GUTENBERG EBOOK X ***\nChapter I\nText.\n*** END OF THE PROJECT GUTENBERG EBOOK X ***\nLicence'
    assert strip_gutenberg(raw).strip() == 'Chapter I\nText.'

def test_fetch_rejects_hash_mismatch(tmp_path):
    (tmp_path / 'texts').mkdir(); (tmp_path / 'texts' / 'b1.txt').write_bytes(b'abc')
    with pytest.raises(ValueError, match='sha256'):
        fetch(Book('s', 'b1', 'T', 'http://x', '0' * 64, 1), root=tmp_path)

def test_split_scenes_ids_and_no_licence():
    text = 'CHAPTER I\n\n' + 'Word ' * 300 + '\n\nCHAPTER II\n\n' + 'Word ' * 300
    scenes = split_scenes('b1', text)
    assert [s.id for s in scenes] == ['b1-001', 'b1-002']
    assert all('GUTENBERG' not in s.text for s in scenes)
```

- [ ] **Step 2:** `C:/tmp/cb/.venv/Scripts/python -m pytest tests/continuity_bench/test_corpus.py -v` → FAIL (`ModuleNotFoundError`).
- [ ] **Step 3:** реалізувати `corpus.py`; `fetch` використовує `urllib.request` лише коли файлу немає. Маніфест — порожня структура `{"series": {}}`; книжки додає задача 10.
- [ ] **Step 4:** тести → PASS.
- [ ] **Step 5:** commit `feat(continuity-bench): корпус — маніфест, завантаження, сцени`.

### Task 2: Латки — формат, застосування, адреси

**Files:**
- Create: `scripts/continuity_bench/patches.py`
- Test: `tests/continuity_bench/test_patches.py`

**Interfaces:**
- Consumes: `Scene` (задача 1).
- Produces:
  - `TYPES = ('knowledge', 'state', 'traits', 'chronology', 'place_object', 'world_rule')`
  - `@dataclass(frozen=True) class Patch: id: str; book: str; before: str; after: str; type: str; scope: str  # 'within' | 'between'; fact_book: str; fact_quote: str; note: str`
  - `normalize(text: str) -> str` — лапки “”„«» → `"`, ‘’ → `'`, — – → `-`, послідовності пробілів → один пробіл
  - `load_patches(path: Path) -> list[Patch]` (JSONL), перевіряє `type ∈ TYPES`, `scope ∈ {within, between}`
  - `apply_patches(texts: dict[str, str], patches: list[Patch]) -> dict[str, str]` — `ValueError`, якщо нормалізований `before` трапляється в книжці не рівно один раз або `fact_quote` не знайдено в `fact_book`
  - `locate(scenes: list[Scene], book: str, fragment: str) -> str` — id сцени, що містить нормалізований фрагмент

- [ ] **Step 1: Write the failing tests**

```python
def test_apply_with_typographic_quotes():
    texts = {'b1': 'She said, “I never saw him.” Then left.'}
    p = Patch('p1', 'b1', 'She said, "I never saw him."', 'She said, "I saw him at the ball."', 'knowledge', 'within', 'b1', 'Then left', '')
    assert 'at the ball' in apply_patches(texts, [p])['b1']

def test_apply_rejects_ambiguous_before():
    texts = {'b1': 'He left. He left.'}
    with pytest.raises(ValueError, match='exactly once'):
        apply_patches(texts, [Patch('p1', 'b1', 'He left.', 'He stayed.', 'state', 'within', 'b1', 'He', '')])

def test_locate_after_resplit():
    scenes = [Scene('b1', 1, 'b1-001', '', 'Alpha beta.', 2), Scene('b1', 2, 'b1-002', '', 'Gamma “delta”.', 2)]
    assert locate(scenes, 'b1', 'Gamma "delta"') == 'b1-002'
```

- [ ] **Step 2:** pytest → FAIL. **Step 3:** реалізувати; заміна йде в оригінальному тексті за позицією, знайденою в нормалізованому (мапа індексів). **Step 4:** PASS. **Step 5:** commit `feat(continuity-bench): латки з нормалізацією й стабільними адресами`.

### Task 3: Виклик моделі, кеш відповідей і облік витрат

**Files:**
- Create: `scripts/continuity_bench/ledger.py`, `scripts/continuity_bench/transport.py`
- Test: `tests/continuity_bench/test_ledger.py`

**Interfaces:**
- Produces:
  - `CAP_USD = Decimal('50')`
  - `class BudgetExceeded(RuntimeError)`
  - `class Ledger: __init__(self, path: Path, cap: Decimal = CAP_USD)`; `spent() -> Decimal`; `ensure(estimate: Decimal) -> None` (кидає `BudgetExceeded`, якщо `spent + estimate > cap`); `record(label: str, model: str, prompt_tokens: int, completion_tokens: int, usd: Decimal) -> None`
  - `@dataclass(frozen=True) class Price: input_per_m: Decimal; output_per_m: Decimal`
  - `prices(models: list[str]) -> dict[str, Price]` — з `https://openrouter.ai/api/v1/models` (поле `pricing`)
  - `class Transport: __init__(self, model: str, ledger: Ledger, cache_dir: Path, client=None, price: Price | None = None)`; `calls: int` (лічильник реальних викликів); `call(stage: str, system: str, user: str, schema: dict | None, label: str) -> str`
    - ключ кешу — SHA-256 від `json.dumps({model, stage, system, user, schema}, sort_keys=True)`; влучання в кеш нічого не записує в облік
    - промах: `generation_request(stage, settings, system, user, fragments=())` → `sdk_arguments(...)` → `client.chat.completions.create(**args)`; клієнт — `build_openai_client(settings)` для `ProviderSettings(provider='openrouter', model=model)`; використання — `normalize_usage`

- [ ] **Step 1: Write the failing tests** (фейковий клієнт повертає фіксований `usage`).

```python
def test_cache_hit_does_not_charge(tmp_path):
    led = Ledger(tmp_path / 'spend.json'); fake = FakeClient(text='{"findings": []}', prompt=1000, completion=100)
    t = Transport('anthropic/claude-sonnet-5.5', led, tmp_path / 'cache', client=fake, price=Price(Decimal(2), Decimal(10)))
    t.call('memory', 'S', 'U', None, 'x'); spent = led.spent(); t.call('memory', 'S', 'U', None, 'x')
    assert fake.calls == 1 and led.spent() == spent == Decimal('0.003')

def test_ensure_refuses_over_cap(tmp_path):
    led = Ledger(tmp_path / 'spend.json', cap=Decimal('1')); led.record('a', 'm', 0, 0, Decimal('0.9'))
    with pytest.raises(BudgetExceeded):
        led.ensure(Decimal('0.2'))
```

- [ ] **Step 2:** FAIL. **Step 3:** реалізувати; `Transport` приймає необов'язковий `price` для тестів, інакше бере з `prices()`. Облік — JSON-файл, запис атомарний (тимчасовий файл + `replace`). **Step 4:** PASS. **Step 5:** commit `feat(continuity-bench): транспорт OpenRouter, кеш відповідей, облік витрат`.

### Task 4: Вхід K1–K4 — пам'ять, картки, план, еталонні факти

**Files:**
- Create: `scripts/continuity_bench/inputs.py`, `scripts/continuity_bench/prompts/scene_plan_en_v1.txt`
- Create: `docs/research/data/continuity/cast-<series>.json` (задача 10 заповнює)
- Test: `tests/continuity_bench/test_inputs.py`

**Interfaces:**
- Consumes: `Scene`, `Patch` (1, 2), `Transport` (3).
- Produces:
  - `CONFIGS = ('K1', 'K2', 'K2u', 'K3', 'K4')`
  - `@dataclass class BuiltSeries: journals: dict[str, MemoryJournal]  # після кожної сцени; cards: dict | None; plans: dict[str, str] | None; bible: str | None`
  - `build_series(scenes: list[Scene], books: list[Book], config: str, transport: Transport, *, cast: dict | None, bible: str | None, patches: list[Patch]) -> BuiltSeries`
    - **K1:** пам'ять сцена за сценою продуктовим етапом memory: перша сцена — `prose_memory_request`; далі запит складається як у `generation/context.py::build_context` з `memory_catalog_v4`, `schema_bounds_v4`, `role_prompt('memory', settings, 'en')`, `generation_request('memory', ...)`; розбір — `parse_memory_result(..., wire_version='4')`. На межі книжок пам'ять переходить через `memory.series_start.inherit_journal` (SERIES-001)
    - **K2u:** спершу картки з прози продуктовим витягом: `characters.extract.plan_groups` / `apply_group` / `finalize`, запит з `load_prompt('character_extract_v2', 'en')` і `generation_request('character_extract', ...)` (без сховища: тексти груп будує `extract_context._user_text`); далі пам'ять, як K1, з відстежуваними персонажами з карток
    - **K2:** як K2u, але картки перед побудовою пам'яті виправлено за `cast-<series>.json` (злиття дублів, імена, аліаси); кількість виправлень записується в `BuiltSeries.cards['corrections']`
    - **K3:** K2 + план сцени промптом `scene_plan_en_v1.txt` (хто, де, момент історії, що змінилося; ≤ 120 слів) + біблія серії
    - **K4:** K1 + для кожної латки запис `facts` із `text=fact_quote`, `quote=fact_quote` у журналі сцени `locate(scenes, fact_book, fact_quote)`
  - Результат кешується на диск у `ROOT/'built'/f'{series}-{config}-{prompt_hash}.pkl'`; повтор не викликає модель

- [ ] **Step 1: Write the failing tests** — фейковий `Transport`, що повертає заздалегідь записані валідні відповіді wire v4 для двох сцен у двох книжках.

```python
def test_k1_inherits_memory_across_books(fake_transport, two_book_scenes):
    built = build_series(two_book_scenes, BOOKS, 'K1', fake_transport, cast=None, bible=None, patches=[])
    first_b2 = two_book_scenes[1].id
    assert any(e.claim_id.startswith('b1') or e.source_version_id for e in built.journals[first_b2].events)

def test_k4_adds_fact_quote_as_record(fake_transport, two_book_scenes, patch_between):
    built = build_series(two_book_scenes, BOOKS, 'K4', fake_transport, cast=None, bible=None, patches=[patch_between])
    assert any(e.quote == patch_between.fact_quote for j in built.journals.values() for e in j.events)

def test_built_series_cached(fake_transport, two_book_scenes, tmp_path):
    build_series(two_book_scenes, BOOKS, 'K1', fake_transport, cast=None, bible=None, patches=[])
    calls = fake_transport.calls
    build_series(two_book_scenes, BOOKS, 'K1', fake_transport, cast=None, bible=None, patches=[])
    assert fake_transport.calls == calls
```

- [ ] **Step 2:** FAIL. **Step 3:** реалізувати; у разі розбіжності з `build_context` перевага в продукту — віддзеркалювати його, не спрощувати (бріф 5.2: K1–K3 беруть пам'ять так само, як продукт). **Step 4:** PASS. **Step 5:** commit `feat(continuity-bench): вхід K1–K4 на продуктовій пам'яті й витягу карток`.

### Task 5: Відбір пам'яті для перевірки

**Files:**
- Create: `scripts/continuity_bench/selection.py`
- Test: `tests/continuity_bench/test_selection.py`

**Interfaces:**
- Consumes: `BuiltSeries` (4).
- Produces: `check_input(scene: Scene, built: BuiltSeries, config: str, char_budget: int | None) -> tuple[str, list[str]]` — текст пам'яті для перевірки й список включених `claim_id`.
  - K1–K3: `projection.memory_items(...)` → `selection.select_memory(SelectionInput(...), char_budget)`, бюджет — як `scripts/memory_bench/strategies.py::product` (двійковий пошук продукту); `CoreOverflow` → ядро без атмосфери й позначка в логах
  - K4: уся пам'ять без бюджету
  - K2/K3 додають текст карток; K3 — план сцени й біблію

- [ ] **Step 1:** тести: (а) K4 включає всі `claim_id`; (б) K1 з бюджетом 2 000 символів повертає ≤ 2 000 символів і не губить записи ядра сцени; (в) K3 містить рядок плану сцени.
- [ ] **Step 2:** FAIL. **Step 3:** реалізувати. **Step 4:** PASS. **Step 5:** commit `feat(continuity-bench): відбір пам'яті як у продукті`.

### Task 6: Нова перевірка узгодженості й чесність цитат

**Files:**
- Create: `scripts/continuity_bench/check.py`, `scripts/continuity_bench/prompts/continuity_check_en_v1.txt`
- Test: `tests/continuity_bench/test_check.py`

**Interfaces:**
- Consumes: `Transport` (3), `check_input` (5), `normalize` (2).
- Produces:
  - `FINDING_SCHEMA` — strict JSON schema: `{"findings": [{"error_quote": str, "fact_scene": str, "fact_quote": str, "type": enum(TYPES), "explanation": str}]}`
  - `@dataclass(frozen=True) class Finding: scene: str; error_quote: str; fact_scene: str; fact_quote: str; type: str; explanation: str; quotes_ok: bool`
  - `run_check(scenes: list[Scene], built: BuiltSeries, config: str, transport: Transport, *, repeat: int) -> list[Finding]` — сцена за сценою; `repeat` входить у мітку й у ключ кешу, щоб повтори не бралися з кешу
  - `quotes_ok(f, scene_text: dict[str, str]) -> bool` — нормалізований `error_quote` є в тексті `f.scene`, а `fact_quote` — у `f.fact_scene` (або в пам'яті з цією цитатою для K4)

Промпт перевірки: проза поточної сцени + пам'ять твору до неї (із `check_input`); знайти лише суперечності поточної сцени з пам'яттю; кожна знахідка — дві дослівні цитати; не повідомляти про те, що текст пояснює (брехня, минулий час, сон, таємниця, яку читач ще не знає); порожній список — нормальна відповідь.

- [ ] **Step 1: Write the failing tests**

```python
def test_quote_from_neighbour_scene_is_not_ok():
    texts = {'b1-001': 'He had a scar.', 'b1-002': 'She smiled.'}
    f = Finding('b1-002', 'He had a scar.', 'b1-001', 'He had a scar.', 'traits', '', False)
    assert quotes_ok(f, texts) is False

def test_quote_with_straight_quotes_matches_curly():
    texts = {'b1-002': 'He said “never”.', 'b1-001': 'Yes.'}
    assert quotes_ok(Finding('b1-002', 'He said "never".', 'b1-001', 'Yes.', 'knowledge', '', False), texts)

def test_repeats_are_not_served_from_cache(fake_transport, scenes, built):
    run_check(scenes, built, 'K1', fake_transport, repeat=1); n = fake_transport.calls
    run_check(scenes, built, 'K1', fake_transport, repeat=2)
    assert fake_transport.calls == 2 * n
```

- [ ] **Step 2:** FAIL. **Step 3:** реалізувати. **Step 4:** PASS. **Step 5:** commit `feat(continuity-bench): перевірка узгодженості з двома цитатами`.

### Task 7: K0 — замінник «уся книжка в Claude»

**Files:**
- Create: `scripts/continuity_bench/k0.py`, `scripts/continuity_bench/prompts/k0_en_v1.txt`
- Test: `tests/continuity_bench/test_k0.py`

**Interfaces:**
- Produces: `run_k0(scenes: list[Scene], books: list[Book], transport: Transport, *, context_tokens: int, repeat: int) -> list[Finding]`
  - серія одним запитом, якщо `≈ 1,3 × слів + промпт ≤ context_tokens`; інакше книжки по черзі з підсумком попередніх (≤ 2 000 слів, той самий транспорт); режим записується у звіт
  - знахідки мають той самий формат; сцену визначає `locate` за `error_quote`; без збігу — `scene=''`, `quotes_ok=False`

- [ ] **Step 1:** тести: (а) малий корпус іде одним запитом; (б) за `context_tokens=1000` — по книжках, кількість викликів = книжки + підсумки; (в) цитата без збігу → `quotes_ok=False`.
- [ ] **Step 2:** FAIL. **Step 3:** реалізувати. **Step 4:** PASS. **Step 5:** commit `feat(continuity-bench): базова лінія K0`.

### Task 8: Оцінювання — збіг із латками, суддя, метрики, діагностика

**Files:**
- Create: `scripts/continuity_bench/score.py`, `scripts/continuity_bench/judge.py`, `scripts/continuity_bench/prompts/judge_en_v1.txt`
- Test: `tests/continuity_bench/test_score.py`

**Interfaces:**
- Consumes: `Finding`, `Patch`, `locate`, `normalize`, `BuiltSeries`.
- Produces:
  - `BASKETS = ('planted', 'original', 'explained', 'no_conflict', 'vague', 'fabricated', 'duplicate', 'wrong_fact_place', 'arguable')`
  - `match(findings, patches, scenes) -> tuple[dict[str, Finding], list[Finding]]` — влучання латки: та сама сцена й нормалізований `error_quote` перетинає `after` щонайменше 20 символами; друга знахідка на ту саму латку — `duplicate`; інші — «не збіглися»
  - `localized(f: Finding, p: Patch, scenes) -> bool` — `fact_scene == locate(scenes, p.fact_book, p.fact_quote)` або цитати перетинаються ≥ 20 символів; інакше кошик `wrong_fact_place` (влучання, провал локалізації)
  - `judge(unmatched: list[Finding], scene_text, transport) -> dict[int, str]` — кошик для кожної незбіглої знахідки за рубрикою бріфу 6.2a; `fabricated` ставить детермінована перевірка, а не суддя
  - `export_review(path, items)` / `import_review(path) -> dict[int, str]` — CSV для людини: усі `arguable` і `original` + 20% решти (seed 288); `disagreement(judge, human) -> float`; якщо > 0,10 — звіт вимагає ручної перевірки решти
  - `metrics(...) -> dict` — повнота загалом / між книжками / за типами; точність `(planted + original + wrong_fact_place) / (усі − duplicate − arguable)`; хибні й дискусійні на 10 тис. слів; локалізація; чесність цитат; вартість і час з обліку
  - `diagnose(patch, built, check_inputs, findings) -> int` — крок 1–4 бріфу 5.3: факту немає в журналах → 1; є, але `claim_id` немає у вході сцени → 2; був у вході, знахідки немає → 3; знахідка є, але `quotes_ok=False` або провал локалізації → 4

- [ ] **Step 1: Write the failing tests** — синтетичні латки й знахідки: влучання, дубль, хибне місце-факт; точність без `arguable` і `duplicate`; `diagnose` повертає 2, коли факт у журналі, а не у вході.
- [ ] **Step 2:** FAIL. **Step 3:** реалізувати. **Step 4:** PASS. **Step 5:** commit `feat(continuity-bench): збіг, суддя, метрики й діагностика`.

### Task 9: CLI — план, платний прогін, звіт, ворота

**Files:**
- Create: `scripts/continuity_bench/run.py`
- Test: `tests/continuity_bench/test_cli.py`

**Interfaces:**
- Consumes: усе вище.
- Produces: команди
  - `python scripts/continuity_bench/run.py --plan --set dev|heldout --configs K0,K1,... [--subset first-40k] [--repeats N]` — оцінка токенів і доларів за цінами `prices()`, залишок ліміту; модель не викликається
  - `--paid` (ті самі аргументи) — `Ledger.ensure(оцінка)` перед стартом, далі побудова, перевірка, K0, суддя; результати в `ROOT/'runs'/<мітка>/results.json`
  - `--report <мітка>` — таблиця метрик і порогів (позначка пройдено/ні), діагностика пропусків, без текстів книжок
  - `--set heldout --gate` — відмова, якщо є `ROOT/'heldout'/'GATE_USED'`; перед стартом створює маркер; `--repeats 3` обов'язково

- [ ] **Step 1:** тести: `--plan` не викликає транспорт; `--gate` удруге відмовляє з повідомленням про використаний набір; `--paid` з оцінкою понад залишок відмовляє до першого виклику; `--report` не містить жодного рядка зі сцени.
- [ ] **Step 2:** FAIL. **Step 3:** реалізувати. **Step 4:** PASS. **Step 5:** commit `feat(continuity-bench): CLI з кошторисом і воротами`.

### Task 10: Дані — серії, касти, латки dev і відкладені латки

**Files:**
- Modify: `docs/research/data/continuity/manifest.json`
- Create: `docs/research/data/continuity/cast-<dev-series>.json`, `docs/research/data/continuity/patches-dev.jsonl`, `docs/research/data/continuity/bible-<dev-series>.md`
- Create (поза репозиторієм): `C:\tmp\continuity-bench\heldout\patches-heldout.jsonl`, `cast-…`, `bible-…`

- [ ] **Step 1:** обрати серію dev і серію відкладеного набору за умовами бріфу 4.2 (суспільне надбання в США та ЄС, ≥ 2 книжки зі спільними персонажами, 150–400 тис. слів); вписати книжки з URL Project Gutenberg і SHA-256 у маніфест; `fetch` і `split_scenes` проходять для кожної книжки.
- [ ] **Step 2:** латки dev: 24–30, щонайменше 4 кожного типу (`world_rule` — лише якщо в серії є біблія), половина `between`; частина «природних» (переписане речення, а не заміна слова, бріф 9). `load_patches` + `apply_patches` проходять без помилок.
- [ ] **Step 3:** каст dev (імена, аліаси, злиття) і коротка нейтральна біблія з першої книжки.
- [ ] **Step 4:** **відкладений набір пише окремий субагент**, якому не показують промптів стенду й латок dev; він отримує лише бріф 4.3, формат `Patch` і серію. Файли — тільки в `C:\tmp\continuity-bench\heldout\`. У репозиторій вони потрапляють разом зі звітом воріт.
- [ ] **Step 5:** commit `data(continuity-bench): корпус dev, касти, латки` (без відкладених файлів).

### Task 11: Ітерації на dev

Платні прогони. Кожна серія — `--plan`, згода власника в чаті з сумою, `--paid`, `--report`.

- [ ] **Step 1:** перший прогін на частині dev (`--subset first-40k`): K0, K1, K4. Різниця K4 − K1 показує, скільки втрачає побудова пам'яті; K4 сам по собі — стелю перевірки.
- [ ] **Step 2:** за діагностикою змінювати промпт перевірки, промпт плану, конфігурацію входу (K2, K2u, K3). Кожна зміна — рядок журналу в звіті: версія промпту, конфігурація, метрики, витрата.
- [ ] **Step 3:** коли найкраща конфігурація проходить пороги 6.3 на частині dev — повний dev для неї (3 повтори). Якщо проходить, вона стає кандидатом на ворота.
- [ ] **Step 4:** якщо залишок ліміту < оцінки воріт, зупинитися й запитати власника.

### Task 12: Ворота й звіт

**Files:**
- Create: `docs/research/2026-11-28-continuity-proof.md`
- Create (після воріт): `docs/research/data/continuity/patches-heldout.jsonl` та касти/біблія відкладеного набору

- [ ] **Step 1:** `--plan --set heldout --configs K0,<кандидат> --repeats 3`; згода власника; `--paid --set heldout --gate --repeats 3`.
- [ ] **Step 2:** розкласти знахідки суддею; людина перевіряє CSV (`export_review`); `import_review`; розбіжність ≤ 0,10, інакше ручна перевірка решти.
- [ ] **Step 3:** звіт українською: методика, корпус (маніфест, без текстів), журнал ітерацій, таблиця воріт проти порогів 6.3, порівняння з K0, діагностика пропусків, справжні нестиковки оригіналу (кандидати для демо), вартість, обмеження. Скопіювати відкладені латки в репозиторій.
- [ ] **Step 4:** `python scripts/check_docs.py` проходить; commit `docs(research): доказ узгодженості, етап 1 — результати воріт`.
- [ ] **Step 5:** PR на `main`; в описі — результат воріт і чи потрібна специфікація перенесення в продукт (бріф 7.2). Документація користувача не змінюється: продукт не змінено.

Прогін A, демо й етап 2 — окремі плани після воріт (бріф 2b, 7, 8).
