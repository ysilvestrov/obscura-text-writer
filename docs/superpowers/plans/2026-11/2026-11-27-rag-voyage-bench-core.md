# Voyage-бенчмарк, ядро: нано й набір перефразувань — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Додати до бенчмарку #25 колонку `voyage-4-nano` і вимірювання рангу цілі на перефразованих запитах (набір генерує Claude, перевіряє власник).

**Architecture:** Ядро за правилом «спершу ядро» (detent pr-slicing): нано як ще одна локальна модель; чисті функції набору (рамка, вибірка, перевірка спільних основ, знімок, перевірка власником); сукупний журнал витрат і генератор через Anthropic API; метрики рангу й попадання в контекст у CLI бенчмарку; локальна сторінка, де власник ставить вердикти кліком. Обв'язка — клієнт Voyage замість Azure, контекстний варіант, прогони й розділ дослідження — окремий план після наскрізної рецензії ядра.

**Tech Stack:** Python 3.12, numpy, sentence-transformers 6.3.0 (дослідницьке venv `C:/tmp/rag-bench/venv`), SDK `anthropic`, pytest.

**Spec:** [docs/superpowers/specs/2026-11/2026-11-27-rag-voyage-bench-design.md](../../specs/2026-11/2026-11-27-rag-voyage-bench-design.md) (затверджено 2026-11-27); базовий дизайн — [2026-11-24-rag-vector-bench-design.md](../../specs/2026-11/2026-11-24-rag-vector-bench-design.md).

## Global Constraints

- Гілка `claude/rag-vector-bench`, worktree `.claude/worktrees/rag-vector-bench`; у main не мерджиться; PR #309 лишається чернеткою.
- Продукт (`src/`), SPEC.MD, `requirements-lock.txt`, `pyproject.toml` — без змін. Нові залежності — лише в `scripts/memory_bench/requirements-vector.txt` з точною версією.
- Вивід скриптів, тести, документи й файли в репозиторії — лише ID, коди й агрегати. Тексти записів, планів і згенерованих запитів — лише поза репозиторієм (`C:\tmp\rag-bench\...`); запис у шлях усередині репозиторію відхиляється кодом `inside_repo` (функція `_inside_repo` з `embeddings.py`).
- Робоча база не читається: `--data` лише копія; робоча тека відхиляється (`_check_data_dir`, як у `run`).
- Хмара (Anthropic): лише твори з префіксами `--cloud-stories` (дозволено: основний твір і тест А `858693d4…`); межа Anthropic $5 сукупно; модель `claude-haiku-5-5`; ціни $0,10 / $0,50 за 1 млн вхідних / вихідних токенів, дата цін `2026-11-27`.
- Ключі — лише з env або з `.env` основної теки `C:\Projects\text-generator\.env` (`ANTHROPIC_API_KEY`); ні ключ, ні тексти не потрапляють у винятки, лог чи вивід.
- Нано: `MongoDB/voyage-4-nano` (на нього переадресує `voyageai/voyage-4-nano`), ревізія `587d8d6dcaec029a9779c2098d6af020e4a07c01`, `trust_remote_code=True`; промпти `Represent the query for retrieving supporting documents: ` і `Represent the document for retrieval: `; розмірності 2048 і 512.
- Рівні запиту: `same` (спільних основ ≥ 2), `syn` і `desc` (спільних основ 0); до 3 спроб, потім `rejected`; понад 10 % випалих у рівні — `unreliable`.
- Перевірка власником: 20 запитів, понад 4 «no» — `owner_check_failed`; коди `owner_check_missing`, `owner_check_stale`.
- Тести запускаються в обох середовищах: дослідницьке `C:/tmp/rag-bench/venv` (з numpy) і середовище продукту `.venv` основної теки (тести, яким потрібні numpy чи anthropic, там пропускаються через `pytest.importorskip`, як у наявних векторних тестах).
- Гейт кожної задачі: `python scripts/check_docs.py` і `python -m pytest -q tests/retrieval_bench` в обох середовищах.

## Review Focus

1. BM25 не повертає ціль (немає спільних слів — саме так на `syn` / `desc`): ранг має бути «не знайдено» (`None` у даних, у знаковому тесті — гірший за будь-яке місце), а не 0, не виняток і не останнє місце пулу як «знайдено». Тест у задачі 4.
2. Для запису немає пізнішої сцени, де він доходить до пулу: форма «у плані» пропускає його й рахує в `no_scene`, форма «окремо» міряє як звичайно. Тест у задачі 4.
3. Власник вписав вердикт не тим словом («Так», «ok», порожньо): лише `yes` / `no` (без урахування регістру й пробілів) вважаються вердиктом, інше — `owner_check_missing` з кількістю невалідних. Тест у задачі 2.
4. Журнал витрат пошкоджений чи напівзаписаний: `spend_ledger_missing`, жодного виклику; запис — лише атомарною заміною. Тест у задачі 3.
5. Імена персонажів у записі й у запиті: не рахуються спільними основами ні для `same`, ні для `syn` / `desc` (інакше «Марта» дає хибну лексичну спорідненість). Тест у задачі 2.

---

### Task 1: Колонка `voyage-4-nano` (2048 і 512)

**Files:**
- Modify: `scripts/memory_bench/embeddings.py` (`MODELS`, `LocalEmbedder.__init__`, новий `TruncatedEmbedder`)
- Modify: `scripts/memory_retrieval_bench.py` (`make_inner_embedder`, `setup_vectors`, `vector_report` — вага моделі для `truncate` береться з базової)
- Test: `tests/retrieval_bench/test_embeddings.py`, `tests/retrieval_bench/test_cli.py`

**Interfaces:**
- Produces: `MODELS['nano-2048'] = {'kind': 'local', 'model_id': 'MongoDB/voyage-4-nano', 'revision': '587d8d6dcaec029a9779c2098d6af020e4a07c01', 'query_prefix': 'Represent the query for retrieving supporting documents: ', 'passage_prefix': 'Represent the document for retrieval: ', 'max_tokens': 8192, 'trust_remote_code': True}`; `MODELS['nano-512'] = {'kind': 'truncate', 'base': 'nano-2048', 'dim': 512}`.
- Produces: `LocalEmbedder(key, model_id, revision, query_prefix, passage_prefix, max_tokens, threads=1, trust_remote_code=False)`.
- Produces: `TruncatedEmbedder(base, key: str, dim: int)` — `embed(texts, kind)` = перші `dim` координат вектора `base.embed(...)`, повторно нормовані; `key` власний, `model_id`, `revision`, `max_tokens`, `truncated`, `last_truncated` — від `base`; `dim` = `dim`.
- Produces: у `setup_vectors` модель виду `truncate` обгортає вже побудований `cached` своєї базової моделі (кеш спільний, модель вантажиться раз); база відсутня в `--vector-models` → код `truncate_base_missing`.

- [ ] **Step 1: Тести**

```python
def test_truncated_embedder_slices_and_renormalizes():
    base = FakeEmbedder(dim=16)
    t = TruncatedEmbedder(base, 'fake-4', 4)
    full = base.embed(['a', 'b'], 'passage')
    out = t.embed(['a', 'b'], 'passage')
    assert out.shape == (2, 4)
    assert np.allclose(np.linalg.norm(out, axis=1), 1.0)
    assert np.allclose(out, full[:, :4] / np.linalg.norm(full[:, :4], axis=1, keepdims=True))
    assert t.key == 'fake-4' and t.model_id == base.model_id and t.dim == 4

def test_nano_specs():
    assert MODELS['nano-2048']['trust_remote_code'] is True
    assert MODELS['nano-2048']['revision'] == '587d8d6dcaec029a9779c2098d6af020e4a07c01'
    assert MODELS['nano-512'] == {'kind': 'truncate', 'base': 'nano-2048', 'dim': 512}
```

У `test_cli.py` (через наявну підміну `make_inner_embedder` на `FakeEmbedder`): `--vector-models nano-512` без `nano-2048` → код `truncate_base_missing`; `--vector-models nano-2048,nano-512` → обидві колонки у звіті, `make_inner_embedder` викликано один раз.

- [ ] **Step 2: Запустити — падають** (`pytest tests/retrieval_bench/test_embeddings.py tests/retrieval_bench/test_cli.py -q` у дослідницькому venv).
- [ ] **Step 3: Реалізувати.** `trust_remote_code` передається в `SentenceTransformer(model_id, revision=revision, device='cpu', trust_remote_code=trust_remote_code)`; `make_inner_embedder` бере `spec.get('trust_remote_code', False)`. Перед першим реальним завантаженням: прочитати `modeling_qwen3_bidirectional.py` завантаженої ревізії й переконатися, що він збігається з переглянутим (91 рядок, імпорти лише `torch` / `transformers`).
- [ ] **Step 4: Тести проходять** в обох середовищах.
- [ ] **Step 5: Ручна проба нано (поза тестами).** У дослідницькому venv з `HF_HOME=C:\tmp\rag-bench\hf` завантажити модель (дозволено #301), потім із `HF_HUB_OFFLINE=1` прогнати адаптований `C:\tmp\rag-bench\exp\speed.py` для `nano-2048` (1 і 16 потоків). Записати в звіт задачі: розмір ваг, час завантаження, мс на запис і на план, розмірність. Лише числа.
- [ ] **Step 6: Commit** `feat(bench): колонка voyage-4-nano (2048 і 512)`.

### Task 2: Чисті функції набору перефразувань

**Files:**
- Create: `scripts/memory_bench/paraphrase.py`
- Test: `tests/retrieval_bench/test_paraphrase.py`

**Interfaces:**
- Consumes: `Record`, `SceneInput` (`model.py`); `record_layers`, `Params`, `_WORD`, `_norm` (`strategies.py`); `name_stems` (`extract.py`); `_inside_repo` (`embeddings.py` — винести в `paraphrase.py` власну копію перевірки шляху, щоб модуль імпортувався без numpy).
- Produces:
  - `LEVELS = ('same', 'syn', 'desc')`
  - `@dataclass(frozen=True) class Query: claim_id: str; level: str; text: str; status: str; record_sha256: str = ''  # status: 'ok' | 'rejected'; record_sha256 — sha256 тексту запису, з якого згенеровано`
  - `content_words(text: str, names: Iterable[str]) -> list[str]` — слова `_WORD` над `_norm(text)`, довжина ≥ 3, не в `STOPWORDS`, не спільноосновні з жодною основою імен (`name_stems` кожного імені).
  - `share_stem(a: str, b: str) -> bool` — спільний початок ≥ 3, якщо коротше слово має 3–4 літери, інакше ≥ 4.
  - `shared_stems(query: str, record_text: str, names) -> int` — кількість різних змістовних слів запису, що мають спільну основу хоч з одним змістовним словом запиту.
  - `level_ok(level: str, query: str, record_text: str, names) -> bool` — `same`: ≥ 2; `syn`, `desc`: 0.
  - `sampling_frame(scenes: list[SceneInput], params: Params) -> list[Record]` — унікальні за `claim_id` записи, що хоч в одній сцені є в `scene.records`, не мають шару в `record_layers` і не `timeline`; сортування за `claim_id`.
  - `sample_targets(frame: list[Record], n_scenes: int, n: int, seed: int) -> list[Record]` — алгоритм нижче.
  - `in_plan_scene(record: Record, scenes: list[SceneInput], params: Params) -> SceneInput | None` — перша за номером сцена з `number > record.source_scene`, де запис є в `records`, без шару й не `timeline`.
  - `manifest(queries: list[Query], meta: dict) -> dict` — `{'meta': meta, 'queries': [{'claim_id', 'level', 'status', 'sha256', 'record_sha256'}]}` (sha256 тексту запиту, без тексту; `meta` генератора містить `model`, `prompt_id`, `seed`, `n`), сортування за (`claim_id`, рівень за порядком `LEVELS`).
  - `snapshot_hash(manifest: dict) -> str` — sha256 від `json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(',', ':'))`.
  - `owner_sample(queries: list[Query], k: int, seed: int) -> list[Query]` — лише `ok`; по колу за рівнями `LEVELS`, усередині рівня — перемішування `random.Random(f'{seed}:{level}')` списку, відсортованого за `claim_id`.
  - `write_owner_file(path: Path, sample: list[Query], snapshot: str, record_texts: dict[str, str]) -> None` — JSON `{'snapshot': ..., 'items': [{'claim_id', 'level', 'sha256', 'text', 'record_text', 'verdict': None}]}` (текст запису — щоб власник бачив, із чим порівнювати); шлях у репозиторії → `ValueError('inside_repo')`.
  - `set_verdict(path: Path, index: int, verdict: str | None) -> dict` — атомарно (`<path>.<pid>.tmp` + `os.replace`) записує `verdict` (`'yes'`, `'no'` або `None` — скасувати) для елемента `index`; повертає `{'yes', 'no', 'pending', 'failed': no > 4}`; інше значення чи індекс поза межами → `ValueError('bad_verdict')`.
  - `check_owner_file(path: Path, queries: list[Query], snapshot: str, max_no: int = 4) -> tuple[str | None, dict]` — код або `None` і `{'yes': int, 'no': int, 'invalid': int}`.

`STOPWORDS` (точно): `який яка яке які там тут щоб але або для від при про над під без між через після перед цей ця це ці той та те ті вже ще лише теж так його її їх він вона воно вони був була було були має мав мала собі себе свій своя своє свої весь вся все всі коли якщо ніж навіть саме дуже знову`.

Алгоритм `sample_targets`: страта = (`category`, третина), третина = `min(2, (source_scene - 1) * 3 // n_scenes)`; якщо `n >= len(frame)` — увесь фрейм. Інакше кожна непорожня страта (у порядку сортування ключа страти) отримує 1; решта `n - кількість_страт` ділиться пропорційно розміру страти (найбільші залишки, нічия — за ключем страти), не більше за розмір страти; усередині страти — `random.Random(f'{seed}:{category}:{third}').sample(відсортовані_за_claim_id, k)`. Результат сортується за `claim_id`.

- [ ] **Step 1: Тести** (на `helpers.rec` / `helpers.scene`, імена з `helpers.NAMES`):

```python
@pytest.mark.parametrize('a,b,expected', [('дах', 'даху', True), ('тече', 'течу', True),
    ('кросівки', 'кросівок', True), ('кросівки', 'кров', False), ('маяк', 'мак', False)])
def test_share_stem(a, b, expected): assert share_stem(a, b) is expected

def test_names_are_not_shared_stems():
    assert shared_stems('Марія знову там', 'Марія шукає ключ', NAMES.values()) == 0

def test_level_ok():
    rec_text = 'Ключ від ліхтарної кімнати лежить у бляшанці'
    assert level_ok('same', 'Знову ключ у бляшанці', rec_text, [])
    assert not level_ok('syn', 'Знову ключі в бляшанках', rec_text, [])
    assert level_ok('desc', 'Металева коробка з-під заварки ховає те, чим відмикають верх', rec_text, [])

def test_sampling_frame_excludes_layers_and_timeline(): ...   # core / present / timeline записи не у фреймі; запис без шару — у фреймі один раз
def test_sample_targets_deterministic_and_stratified(): ...   # той самий seed → ті самі ID; кожна непорожня страта ≥ 1; n ≥ len → увесь фрейм
def test_in_plan_scene_first_later_scene_or_none(): ...
def test_manifest_has_no_texts_and_snapshot_changes_with_text():
    q = [Query('r1', 'syn', 'текст запиту', 'ok')]
    m = manifest(q, {'seed': 0})
    assert 'текст' not in json.dumps(m, ensure_ascii=False)
    assert snapshot_hash(m) != snapshot_hash(manifest([Query('r1', 'syn', 'інший', 'ok')], {'seed': 0}))

def test_owner_file_codes(tmp_path):   # missing file → owner_check_missing; verdict 'Так' → missing, invalid=1;
    ...                                # змінений текст одного запиту → owner_check_stale; 5×'no' → owner_check_failed; 20 валідних, ≤4 'no' → None
```

Шлях `tmp_path` у тестах лежить поза репозиторієм (pytest `--basetemp` на коротких шляхах); якщо ні — тест задає `monkeypatch` кореня репозиторію.

- [ ] **Step 2: Запустити — падають.**
- [ ] **Step 3: Реалізувати** `paraphrase.py` (без numpy й без anthropic в імпортах).
- [ ] **Step 4: Тести проходять** в обох середовищах.
- [ ] **Step 5: Commit** `feat(bench): чисті функції набору перефразувань`.

### Task 3: Сукупний журнал витрат і генератор через Claude

**Files:**
- Create: `scripts/memory_bench/cloud_spend.py`, `scripts/memory_bench/paraphrase_gen.py`, `scripts/rag_paraphrases.py`
- Modify: `scripts/memory_bench/requirements-vector.txt` (додати `anthropic==2.13.0`)
- Test: `tests/retrieval_bench/test_cloud_spend.py`, `tests/retrieval_bench/test_paraphrase_gen.py`

**Interfaces:**
- Consumes: `Query`, `LEVELS`, `level_ok`, `sampling_frame`, `sample_targets`, `manifest`, `snapshot_hash`, `owner_sample`, `write_owner_file` (задача 2).
- Produces:
  - `class SpendLedger` з `@classmethod open(cls, path: Path, caps: dict[str, float], create: bool = False) -> 'SpendLedger'` — файл `{'providers': {name: {'usd', 'input_tokens', 'output_tokens', 'calls'}}, 'prices_date': str}`; відсутній при `create=False` чи нечитабельний → `LedgerMissing` (код `spend_ledger_missing`); `check(provider: str, est_usd: float) -> None` → `BudgetExceeded` (код `cloud_budget_exceeded`), якщо `spent + est > cap`; `record(provider: str, usd: float, input_tokens: int, output_tokens: int) -> None` — запис через `<path>.<pid>.tmp` і `os.replace`.
  - `class LedgerMissing(Exception)`, `class BudgetExceeded(Exception)` — без тексту в повідомленнях, лише код.
  - `PROMPT: str`, `PROMPT_ID: str` (sha256 `PROMPT`), `HAIKU = 'claude-haiku-5-5'`, `PRICE_IN = 0.10`, `PRICE_OUT = 0.50` (за 1 млн), `PRICES_DATE = '2026-11-27'`.
  - `class CompletionClient(Protocol): def complete(self, prompt: str) -> tuple[str, int, int]: ...  # текст, input_tokens, output_tokens`
  - `class AnthropicClient` — `__init__(api_key: str, model: str = HAIKU)`, `complete(prompt)` через SDK; до написання звірити виклик із skill `claude-api` (Python, `messages.create`, `usage.input_tokens` / `usage.output_tokens`, Haiku 5.5: thinking адаптивний за замовчуванням — `effort` `low`, якщо SDK це підтримує; без потокового виводу).
  - `generate(records: list[Record], names: list[str], client: CompletionClient, ledger: SpendLedger, attempts: int = 3) -> list[Query]` — для кожного запису до `attempts` викликів; кожен виклик повертає JSON `{"same": str, "syn": str, "desc": str}`; перший текст, що пройшов `level_ok`, фіксується для рівня; рівні, що не пройшли за `attempts`, — `Query(..., text=<останній варіант або ''>, status='rejected')`; нерозбірливий JSON = невдала спроба для всіх ще не зафіксованих рівнів. Перед кожним викликом `ledger.check('anthropic', оцінка)`, де оцінка = (`len(prompt) / 2` × `PRICE_IN` + 600 × `PRICE_OUT`) / 1e6; після — `ledger.record` з фактичних токенів.
  - CLI `scripts/rag_paraphrases.py`: `--data` (копія), `--story`, `--out` (тека поза репозиторієм; пише `set.json` з текстами, `owner-check.json`), `--manifest` (шлях маніфесту без текстів; дозволено в репозиторії), `--n 40`, `--seed 0`, `--owner-k 20`, `--cloud-stories`, `--spend-ledger` (за замовчуванням `C:\tmp\rag-bench\spend.json`), `--anthropic-max-usd 5.0`, `--init-spend-ledger`, `--env-file` (за замовчуванням `C:\Projects\text-generator\.env`). Друкує лише JSON з лічильниками (`targets`, `queries_ok` і `rejected` за рівнем, `usd_spent`, `snapshot`) або `{"error": code}`. Коди: `inside_repo`, `cloud_not_allowed`, `anthropic_key_missing`, `spend_ledger_missing`, `cloud_budget_exceeded`, `live_data`, `story_not_found`.

`PROMPT` (українською; фіксується в коді, зміна змінює `PROMPT_ID`): завдання — для запису пам'яті історії написати три речення-згадки, як у плані пізнішої сцени, що повертають ту саму деталь: `same` — з двома-трьома словами запису; `syn` — та сама деталь синонімами, жодне змістовне слово запису не повторюється навіть в іншій формі; `desc` — через ознаку, наслідок чи вигляд, без слів запису. Не вживати імена (передаються списком). Відповідь — лише JSON з трьома ключами. Записи, імена й категорія підставляються в кінець промпту.

- [ ] **Step 1: Тести**

```python
def test_ledger_missing_and_corrupt(tmp_path):
    with pytest.raises(LedgerMissing): SpendLedger.open(tmp_path / 'spend.json', {'anthropic': 5.0})
    (tmp_path / 'spend.json').write_text('{bad', encoding='utf-8')
    with pytest.raises(LedgerMissing): SpendLedger.open(tmp_path / 'spend.json', {'anthropic': 5.0})

def test_ledger_is_cumulative_across_opens(tmp_path):
    p = tmp_path / 'spend.json'
    a = SpendLedger.open(p, {'anthropic': 5.0}, create=True); a.record('anthropic', 3.0, 10, 5)
    b = SpendLedger.open(p, {'anthropic': 5.0})
    with pytest.raises(BudgetExceeded): b.check('anthropic', 2.5)
    b.check('anthropic', 1.9)

def test_generate_retries_and_rejects():   # фейковий клієнт: 1-ша відповідь — syn повторює слово, 2-га — ок; desc ніколи не ок
    ...                                    # → syn ok з 2-ї спроби, desc rejected після 3 викликів; ledger.calls == 3
def test_generate_bad_json_counts_as_attempt(): ...
def test_cli_refusals(tmp_path, monkeypatch): ...   # --out у репозиторії → inside_repo; story поза --cloud-stories → cloud_not_allowed;
                                                    # без ключа → anthropic_key_missing; без журналу → spend_ledger_missing; клієнт не створюється
```

Тести генератора не імпортують `anthropic` (фейковий `CompletionClient`); тест `AnthropicClient` — лише `pytest.importorskip('anthropic')` і перевірка, що конструктор не робить мережевих викликів.

- [ ] **Step 2: Запустити — падають.**
- [ ] **Step 3: Реалізувати.** `pip install anthropic==2.13.0` у дослідницьке venv.
- [ ] **Step 4: Тести проходять** в обох середовищах.
- [ ] **Step 5: Ручна проба ключа Anthropic** — один виклик `AnthropicClient.complete` з нейтральним текстом (без текстів творів), записати лише статус і кількість токенів; журнал створити `--init-spend-ledger` і переконатися, що витрата записалась.
- [ ] **Step 6: Commit** `feat(bench): журнал витрат і генератор перефразувань через Claude`.

### Task 4: Метрики рангу й попадання в контекст

**Files:**
- Create: `scripts/memory_bench/paraphrase_eval.py`
- Modify: `scripts/memory_retrieval_bench.py` (аргумент `--paraphrases <тека>`, перевірка власника до будь-якого обчислення, секція звіту `paraphrases`)
- Test: `tests/retrieval_bench/test_paraphrase_eval.py`, `tests/retrieval_bench/test_cli.py`

**Interfaces:**
- Consumes: `Query`, `sampling_frame`, `in_plan_scene`, `check_owner_file`, `manifest`, `snapshot_hash` (задача 2); `fts_rank`, `_structural_retrieval`, `vector_strategies` (`strategies.py`); `vec_rank`, `rrf_rank` (`ranking.py`); `full`, `Params`.
- Produces:
  - `rank_of(target: str, ordered: list[Record]) -> int | None` — 1-based місце або `None`, якщо рангувальник ціль не повернув.
  - `sign_test(a: list[int | None], b: list[int | None]) -> dict` — `{'a_better', 'b_better', 'ties', 'p'}`; `None` гірший за будь-яке число, два `None` — нічия; p — точний двобічний, як `sign_test` у `adhoc_2026_11_25/offline_checks.py`.
  - `evaluate_paraphrases(scenes, queries, rankers: dict[str, Ranker], strategies: dict[str, Callable], params_of, steps: tuple[float, ...] = (0.75, 0.5, 0.35)) -> dict` — для кожного рівня й колонки: `n`, `rejected`, `unreliable` (`rejected / (n + rejected) > 0.10`), форма `standalone` (пул = `sampling_frame`, запит = текст) і `in_plan` (сцена = `in_plan_scene`, пул = записи сцени без шару й не `timeline`, запит = `plan_text + ' ' + текст`): `median_rank` (за знайденими), `found`, `top5`, `top10` (частки від `n`), `no_scene` (лише `in_plan`); для `in_plan` також `in_context[step][core]` — частка, де ціль у `record_ids` стратегії колонки при бюджеті `step × full(s).tokens_realistic` і ядрі `upper` / `lower`; `sign_vs_bm25` для кожної колонки, крім `bm25`, за записами.
  - Колонки: `bm25`, `vec[<модель>]`, `hybrid[<модель>]` для кожної моделі з `--vector-models`; стратегії: `structural_fts`, `structural_vec[<модель>]`, `structural_hybrid[<модель>]`.
  - CLI: `--paraphrases` без `--vector-models` дозволено (лише BM25). Перед побудовою моделей — `check_owner_file(<тека>/owner-check.json, …, snapshot_hash(manifest(...)))`; код → вихід з цим кодом. `set.json` читається з теки; тека в репозиторії → `inside_repo`.

- [ ] **Step 1: Тести** (на `helpers.scene` / `helpers.rec` і `FakeEmbedder`):

```python
def test_rank_of_none_when_not_returned():
    assert rank_of('x', [rec('a', 'facts', 'щось')]) is None

def test_sign_test_none_is_worst():
    r = sign_test([1, None, 3], [None, None, 5])
    assert (r['a_better'], r['b_better'], r['ties']) == (2, 0, 1)

def test_bm25_without_overlap_counts_as_not_found(): ...   # syn-запит без спільних слів: bm25 found == 0, top5 == 0, без винятку
def test_in_plan_without_later_scene_goes_to_no_scene(): ...
def test_rejected_and_unreliable(): ...                    # 1 rejected із 5 → unreliable True; 0 із 5 → False; rejected не входять у n
def test_in_context_uses_budget_steps_and_both_cores(): ...
def test_cli_refuses_without_owner_check(tmp_path, monkeypatch): ...   # немає owner-check.json → owner_check_missing; змінений set.json → owner_check_stale; моделі не будуються
def test_report_has_no_texts(): ...                        # json.dumps(report['paraphrases']) не містить жодного тексту запиту чи запису
```

- [ ] **Step 2: Запустити — падають.**
- [ ] **Step 3: Реалізувати** `paraphrase_eval.py` і підключення в `_build_report` (секція `paraphrases` лише за `--paraphrases`; решта звіту без змін).
- [ ] **Step 4: Тести проходять** в обох середовищах; наявні тести `tests/retrieval_bench` — без змін очікувань.
- [ ] **Step 5: Повна перевірка гілки.** Detached worktree на коміт задачі в `C:/tmp/rvb2` з junction на `.venv` і `frontend/node_modules`, звідти `python scripts/verify.py`; результат (коміт, passed / failed / errors / skipped) — у звіт задачі й потім в опис PR #309; `docs/STATUS.md` не комітити. Перед `git worktree remove` прибрати junction через `cmd /c rmdir`.
- [ ] **Step 6: Commit** `feat(bench): ранг цілі й попадання в контекст на перефразуваннях`.

---

### Task 5: Сторінка перевірки для власника (клік замість правки файла)

Вимога власника 27.11.2026: вердикт обирається кліком, а не вписується у файл. Сторінка показує тексти твору, тому лише локально: не публікується, не йде в репозиторій, сервер слухає тільки `127.0.0.1`.

**Files:**
- Create: `scripts/rag_owner_review.py` (сервер на `http.server` зі стандартної бібліотеки, HTML і JS вбудовані в модуль)
- Test: `tests/retrieval_bench/test_owner_review.py`

**Interfaces:**
- Consumes: `set_verdict`, `check_owner_file` (задача 2); файл `owner-check.json` (задача 3 пише його в `--out`).
- Produces: CLI `python scripts/rag_owner_review.py --dir <тека з owner-check.json> [--port 8765] [--no-browser]` — тека в репозиторії → `{"error": "inside_repo"}`, немає файла → `{"error": "owner_check_missing"}`; друкує лише адресу `http://127.0.0.1:<port>/` і відкриває її в браузері за замовчуванням (`webbrowser.open`), якщо нема `--no-browser`.
- Produces: `make_server(path: Path, port: int) -> http.server.ThreadingHTTPServer`, прив'язаний до `('127.0.0.1', port)`; маршрути:
  - `GET /` — сторінка;
  - `GET /items` — JSON `{'items': [{'index', 'level', 'record_text', 'text', 'verdict'}], 'summary': {...}}`;
  - `POST /verdict` з JSON `{'index': int, 'verdict': 'yes' | 'no' | null}` → `set_verdict`, відповідь — новий `summary`; помилка → 400 `{'error': 'bad_verdict'}`; інші маршрути — 404; запит із заголовком `Origin`, що не є `http://127.0.0.1:<port>`, — 403 (захист від запитів зі сторонніх сторінок).

**Сторінка** (українською, без зовнішніх ресурсів, працює в світлій і темній темі):
- угорі — лічильник «перевірено N з 20 · годиться X · ні Y» і стан порогу: «набір проходить» / «понад 4 «ні» — набір буде згенеровано заново»;
- коротка підказка до рівнів: `same` — «мають бути спільні слова із записом»; `syn` — «та сама деталь іншими словами, без слів запису»; `desc` — «деталь описано через ознаку чи наслідок»; питання до власника — «Чи це справді та сама деталь і чи дотримано правило рівня?»;
- картка на кожен запит: запис (джерело), рівень із підказкою, запит; дві кнопки «Годиться» / «Ні» (обрана підсвічена, повторний клік скасовує); вибір зберігається одразу (POST), без кнопки «Зберегти»; помилка збереження показується на картці;
- клавіатура: `1` / `2` для поточної картки, `Tab` між картками; видимий фокус.

- [ ] **Step 1: Тести** — сервер на вільному порту в потоці, запити через `http.client`:

```python
def test_server_binds_localhost_only(tmp_path): ...        # server.server_address[0] == '127.0.0.1'
def test_get_items_and_post_verdict_updates_file(tmp_path): ...   # POST yes → файл має 'yes'; summary.yes == 1; POST null → знову None
def test_bad_verdict_and_unknown_route(tmp_path): ...      # 'Так' → 400 bad_verdict; /etc → 404
def test_foreign_origin_rejected(tmp_path): ...            # Origin: https://example.com → 403, файл без змін
def test_cli_refuses_repo_dir_and_missing_file(tmp_path): ...
```

- [ ] **Step 2: Запустити — падають.**
- [ ] **Step 3: Реалізувати.**
- [ ] **Step 4: Тести проходять** в обох середовищах (лише стандартна бібліотека).
- [ ] **Step 5: Ручна перевірка сторінки** на фейковому `owner-check.json` з нейтральними текстами (20 вигаданих записів), у вбудованому браузері: кліки зберігаються у файл, лічильник і поріг оновлюються, темна тема читається. Записати в звіт задачі, що перевірено.
- [ ] **Step 6: Commit** `feat(bench): локальна сторінка перевірки перефразувань`.

---

## Після ядра (не в цьому плані)

1. Наскрізна рецензія ядра (фінальна рецензія гілки за subagent-driven-development); знахідки — у журнал.
2. Генерація набору на основному творі (`rag_paraphrases.py`), перевірка власником 20 запитів на локальній сторінці (`rag_owner_review.py`).
3. Окремий план обв'язки: клієнт Voyage замість `AzureEmbedder` (`--cloud`, `cloud_allowed`, журнал витрат провайдера `voyage`, межа $1), контекстний варіант (кеш контекстів із хешем прози сцени), прогони, розділ дослідження #25 і оновлення опису PR #309.
