# Voyage-бенчмарк, обв'язка: клієнт Voyage, контекстний варіант, прогони — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Доповнити ядро ([план ядра](2026-11-27-rag-voyage-bench-core.md)) хмарною колонкою `voyage-4` замість Azure і контекстним варіантом пошуку, закрити відкладені знахідки рецензії ядра, провести прогони й записати результат у дослідження #25.

**Architecture:**
- Хмарний клієнт `VoyageEmbedder` займає місце `AzureEmbedder` і платить через той самий сукупний журнал витрат, що й генератор перефразувань (провайдер `voyage`).
- Контексти записів генерує окремий скрипт через Claude Haiku, а кешуються вони поза репозиторієм.
- Бенчмарк читає контексти готовими і сам хмару для них не викликає. Контекстний ранжувальник шукає за текстом «контекст + запис», а повертає оригінальні `Record`. Тому бюджет і контекст сцени не змінюються.
- Прогони й розділ дослідження виконує контролер після задач.

**Tech Stack:** Python 3.12, numpy, httpx, SDK `anthropic`, pytest. Дослідницьке venv — `C:/tmp/rag-bench/venv`.

**Spec:** [docs/superpowers/specs/2026-11/2026-11-27-rag-voyage-bench-design.md](../../specs/2026-11/2026-11-27-rag-voyage-bench-design.md), затверджено 2026-11-27. Розділи «Колонки», «Контекстний варіант», «Хмара», «Відтворюваність». Знахідки рецензії ядра — у журналі `.superpowers/sdd/2026-11-27-rag-voyage-bench-core/progress.md` (рядки `Final: parked`, `Ruling R19`).

## Global Constraints

Усе з Global Constraints плану ядра діє й тут: гілка, продукт без змін, лише ID та агрегати, копія бази, ключі, обидва середовища, гейт задачі. Окремо для цього плану:

- **Voyage, запит.**
  - `POST https://ai.mongodb.com/v1/embeddings`, заголовок `Authorization: Bearer <ATLAS_EMBEDDING_API_KEY>`.
  - Тіло: `{"input": [...], "model": "voyage-4", "input_type": "query" | "document"}`. Вид `query` іде як `query`, вид `passage` — як `document`; будь-який інший вид дає `ValueError('cloud_input_type')`, і запит не робиться.
  - `output_dimension` не передається: типова розмірність 1024.
- **Voyage, відповідь.** `data[].embedding`, `data[].index`, `usage.total_tokens`. Будь-яке інше поле чи форма дає `cloud_bad_response`.
- **Voyage, ліміти й ціна.**
  - До 1000 вхідних текстів і 320 тис. токенів на запит. Батч — 128 текстів.
  - На 429 повторюємо з паузами 1, 2 і 4 с, далі `cloud_http_429`. На інші статуси одразу `cloud_http_<status>`.
  - Ціна $0,06 за 1 млн токенів. Межа провайдера `voyage` — $1 сукупно.
  - Оцінка до виклику: `ceil(len(text) / 2)` токенів на текст.
- **Журнал витрат.**
  - Файл один для обох провайдерів: `C:\tmp\rag-bench\spend.json`.
  - Код перевищення лише один — `cloud_budget_exceeded`. Код `cloud_budget` прибирається.
  - Межа з аргументу CLI не може перевищити межу, записану в журналі.
- **Хмара для творів.** Лише за прапорцем `--cloud` і для префіксів `--cloud-stories`. Дозволено основний твір `039b7438` і тест А `858693d4`.
- **Контекстний варіант.**
  - Контекстні колонки: `ctx_bm25`, `ctx_vec[nano-2048]`, `ctx_vec[voyage-4]` і гібриди `ctx_hybrid[...]` тих самих моделей. Для e5 і bge-m3 контекстних колонок немає.
  - Текст пошуку: `f'{context}\n{record.text}'`. Бюджет і контекст сцени беруть лише `record.text`.
- **Контексти.**
  - Модель `claude-haiku-5-5`. Межа провайдера `anthropic` — $5 сукупно; уже витрачено $0,073.
  - Обрізана відповідь (`stop_reason == 'max_tokens'`) чи порожня ніколи не потрапляє в кеш.
- **Видалення.** Мертвого коду Azure в гілці не лишається. Історичні результати Azure в дослідженні #25 лишаються як історія.

## Review Focus

1. **Збій хмари посеред прогону.** Батч 3 упав, а батчі 1–2 уже оплачені. Їхні вектори мають лишитися в кеші, а журнал має містити рівно оплачене. Повтор платить лише за решту. Тест у задачі 2.
2. **Контекстна колонка й бюджет.** Ранжувальник шукає за контекстом, а в бюджет і в `record_ids` ідуть оригінальні записи з оригінальною ціною. Перевірка: та сама сцена з порожніми контекстами дає ті самі `record_ids` і `layers`, що й безконтекстна колонка. Тест у задачі 4.
3. **Запис пулу без контексту.** Без `source_scene` текст пошуку — це сам запис, і запис рахується в `no_source`. Якщо ключ запису зі сценою походження відсутній у файлі контекстів, бенчмарк відмовляє з кодом `contexts_stale`. Мовчки змішувати контекстні й звичайні рядки не можна. Тест у задачі 4.
4. **Журнал витрат.** Межа з CLI, вища за записану в журналі, не діє: працює менша з двох. Файл без поля `caps` дістає його один раз, при першому відкритті. Тест у задачі 1.
5. **Обрізана чи порожня відповідь Haiku на контекст.** Така відповідь не кешується, рахується як `truncated` і повторюється до 3 спроб, потім `failed`. Повторний запуск генератора платить лише за `failed`. Тест у задачі 3.

---

### Task 1: Борги ядра й спільне читання ключів

Знахідки рецензії ядра, відкладені в цей план. Нові задачі спираються на `read_env_key` і межі з журналу.

**Files:**
- Modify: `scripts/memory_bench/cloud_spend.py` (межі в журналі, `read_env_key`)
- Modify: `scripts/rag_paraphrases.py` (архів вердиктів, `--owner-k`, M8, `owner` у маніфесті)
- Modify: `scripts/memory_bench/annotate_pairs.py` (спільний `_inside_repo`)
- Test: `tests/retrieval_bench/test_cloud_spend.py`, `tests/retrieval_bench/test_paraphrase_gen.py`, тест annotate_pairs, де він є

**Interfaces:**
- Produces: `read_env_key(name: str, env_file) -> str` у `cloud_spend.py`. Шукає спершу в `os.environ`, далі в рядках `KEY=VALUE` env-файла; якщо ключа немає — `''`. `rag_paraphrases.read_key` стає тонкою обгорткою над нею.
- Produces: `SpendLedger.open(path, caps, create=False)` записує `caps` у файл один раз, коли поля `caps` там ще немає. Відтоді `self.caps[p] = min(caps_with_file[p], caps_from_arg[p])`.
- Produces: генератор із `--owner-k`, відмінним від 20, відмовляє кодом `owner_k_invalid` ще до створення клієнта.

- [ ] **Step 1: Тести**

```python
def test_ledger_persists_caps_once_and_takes_the_lower(outside_dir):
    path = outside_dir / 'spend.json'
    SpendLedger.open(path, {'anthropic': 5.0}, create=True)
    assert json.loads(path.read_text())['caps'] == {'anthropic': 5.0}
    raised = SpendLedger.open(path, {'anthropic': 50.0})
    assert raised.caps['anthropic'] == 5.0
    lowered = SpendLedger.open(path, {'anthropic': 1.0})
    assert lowered.caps['anthropic'] == 1.0
    assert json.loads(path.read_text())['caps'] == {'anthropic': 5.0}

def test_ledger_without_caps_field_gets_it_on_first_open(...): ...  # old file {'providers': {...}} → caps added, providers kept

def test_new_provider_cap_is_added_to_existing_caps(...):  # {'anthropic':5} on file, open with {'voyage':1} → file has both

def test_read_env_key_env_first_then_file_and_never_prints(monkeypatch, outside_dir, capsys): ...

def test_owner_archive_never_overwrites(...):
    # three snapshot changes with the same first 8 chars of the old snapshot (forge the snapshots):
    # owner-check.<old8>.json, owner-check.<old8>-2.json, owner-check.<old8>-3.json all exist with their own verdicts

def test_owner_k_other_than_20_refused_before_client(...):  # main([... '--owner-k', '10']) → {"error": "owner_k_invalid"}, fake make_client never called

def test_manifest_carries_owner_summary_when_owner_file_matches(...):
    # after set_verdict yes ×20, a cached rerun with --manifest writes manifest['owner'] == {'yes': 20, 'no': 0, 'invalid': 0, 'status': 'ok'}
    # with a stale or missing owner file: manifest['owner'] == {'status': 'owner_check_missing' | 'owner_check_stale', ...}
```

Тест annotate_pairs: якщо шлях лежить в основній теці фейкового checkout, `propose` відмовляє (фікстура з тесту F5 у `test_paraphrase.py`).

- [ ] **Step 2: Запустити, щоб тести впали.**
- [ ] **Step 3: Реалізувати.**
  - **Архів вердиктів.** Перший вільний із ряду `owner-check.<old8>.json`, `owner-check.<old8>-2.json`, …; `os.replace` лише в неіснуюче ім'я.
  - **M8.** Змінна циклу в `rag_paraphrases.py:263` перейменовується, щоб не затіняти API-ключ. Широкий `except` там розділяється: помилки кешу й ОС дають `cache_write_failed`, помилки виклику — `anthropic_call_failed`.
  - **`annotate_pairs.py`.** Імпортує `_inside_repo` з `memory_bench.paraphrase` замість власної копії.
- [ ] **Step 4: Тести проходять** в обох середовищах.
- [ ] **Step 5: Поправка до специфікації.** Доповнити розділ «Набір перефразувань / Зберігання» абзацом `*Поправка 27.11 (обв'язка).*`:
  - маніфест містить підсумок вердиктів власника (`owner`), щойно файл вердиктів відповідає знімку;
  - «форма» — це вимір звіту, а не поле запиту, тому в маніфесті її немає;
  - межа витрат кожного провайдера записується в журнал при першому відкритті, і аргумент CLI її лише знижує.
- [ ] **Step 6: Commit** `fix(bench): борги ядра — архів вердиктів, межі в журналі, спільне читання ключів`.

---

### Task 2: Клієнт Voyage замість Azure

**Files:**
- Modify: `scripts/memory_bench/embeddings.py`: прибрати `AzureEmbedder` і `azure-3-large`; додати `VoyageEmbedder` і `MODELS['voyage-4']`; `CachedEmbedder` пише кеш порціями; `dtype` входить у ключ кешу.
- Modify: `scripts/memory_retrieval_bench.py`:
  - прибрати `CLOUD_ENV`, `CLOUD_PRICE_PER_MTOK`, `--cloud-max-usd` і `--cloud-price-per-mtok`;
  - додати `--spend-ledger`, `--voyage-max-usd`, `--env-file` і `--repro-cloud`;
  - змінити `main`, `make_inner_embedder`, `setup_vectors`, `repro_share` і довідку.
- Delete: `tests/retrieval_bench/test_azure.py`
- Create: `tests/retrieval_bench/test_voyage.py`
- Modify: `tests/retrieval_bench/test_cli.py`, `tests/retrieval_bench/test_embeddings.py` — місця, що згадують Azure.

**Interfaces:**
- Consumes: `SpendLedger`, `BudgetExceeded`, `LedgerMissing`, `read_env_key` (задача 1).
- Produces: `MODELS['voyage-4'] = {'kind': 'cloud', 'model_id': 'voyage-4', 'revision': 'atlas-1024', 'dim': 1024, 'max_tokens': 32000}`; `CLOUD_KEYS = ('voyage-4',)`.
- Produces: `VoyageEmbedder(key, api_key, ledger: SpendLedger, transport=None, sleep=time.sleep, model_id='voyage-4', revision='atlas-1024', dim=1024)`.
  - `BATCH = 128`, `PROVIDER = 'voyage'`, `PRICE_PER_MTOK = 0.06`.
  - `embed(texts, kind)`. Перед першим запитом рядок у stderr: `cloud_estimate provider=voyage tokens=<n> usd=<x> spent_usd=<y> max_usd=<cap>`. Потім `ledger.check('voyage', est)`. Після кожного успішного батча — `ledger.record('voyage', total_tokens * 0.06 / 1e6, total_tokens, 0)`.
  - Атрибути `tokens`, `latencies`, `truncated = 0`, `last_truncated` (усі False), `query_prefix = passage_prefix = ''`, `close()`.
- Produces: `CachedEmbedder.embed` викликає `inner.embed` порціями по `getattr(inner, 'BATCH', len(missing))` і пише кожну порцію на диск до наступної.
- Produces: шлях кешу: `'|'.join((model_id, revision, kind, prefix, text))`, а коли `getattr(inner, 'dtype', None)` не порожній, ще `'|dtype=' + dtype` (M5). Ключі e5 і bge-m3 не змінюються, бо в них `dtype` немає.
- Produces: коди відмови `setup_vectors`. Усі перевіряються до побудови будь-якого embedder і до мережі:
  - `cloud_not_allowed` — немає `--cloud` або твір поза `--cloud-stories`;
  - `cloud_config_missing` — порожній `ATLAS_EMBEDDING_API_KEY`;
  - `spend_ledger_missing` — журнал не читається; бенчмарк журнал не створює.
- Produces: `main` друкує код, а не traceback, для `ValueError('cloud_…')`, `BudgetExceeded` і `LedgerMissing`.
- Produces: `--repro-cloud` (лише разом із `--repro`). Додає `repro_identical_share` для хмарних моделей — це один платний перепрогін на порожньому кеші. Без прапорця `--repro` хмару не чіпає.

- [ ] **Step 1: Тести на підробному транспорті `httpx.MockTransport`** (`test_voyage.py`, `pytest.importorskip('numpy')` і `('httpx')`):

```python
def test_request_shape_and_input_type(): # body == {'input': [...], 'model': 'voyage-4', 'input_type': 'document'} for kind passage; 'query' for query; Bearer header
def test_unknown_kind_raises_before_request(): # kind 'other' → ValueError('cloud_input_type'), transport never called
def test_vectors_follow_index_and_are_normalized(): # data returned in reversed index order → rows in input order, norms 1.0
def test_ledger_records_each_batch_and_estimate_printed(capsys): # 130 texts → 2 requests, ledger calls == 2, usd == sum(total_tokens)*0.06/1e6, stderr has 'cloud_estimate provider=voyage'
def test_budget_refused_before_any_request(): # ledger spent 0.999, cap 1.0, big estimate → BudgetExceeded, transport never called
def test_429_retries_then_succeeds(): # 429, 429, 200 → result; sleep called with 1, 2
def test_429_exhausted_gives_code(): # 4×429 → ValueError('cloud_http_429'); sleep calls [1, 2, 4]
def test_errors_never_echo_text_or_key(): # 500 with body containing the text → str(error) == 'cloud_http_500', no text/key in it
def test_bad_response_code(): # missing usage.total_tokens → 'cloud_bad_response'
def test_partial_failure_keeps_paid_batches(outside_dir):
    # CachedEmbedder over VoyageEmbedder, 300 texts, transport fails on the 3rd request with 500:
    # raises cloud_http_500; 256 vectors on disk; ledger has 2 calls;
    # a rerun with a working transport sends only the remaining 44 texts
```

Тести в `test_cli.py`:
- `voyage-4` без `--cloud` → `cloud_not_allowed`;
- твір поза списком → `cloud_not_allowed`;
- без ключа → `cloud_config_missing`;
- без журналу → `spend_ledger_missing`;
- `BudgetExceeded` усередині `run` → stdout порожній, stderr `cloud_budget_exceeded`, код 2;
- `--repro` без `--repro-cloud` не викликає `make_inner_embedder` для хмарної моделі вдруге.

Тест в `test_embeddings.py`: `LocalEmbedder` з `dtype='float32'` і без нього дає різні шляхи кешу; e5 без `dtype` дає той самий шлях, що й до зміни (зафіксувати очікуваний sha256).

- [ ] **Step 2: Запустити, щоб тести впали.**
- [ ] **Step 3: Реалізувати.** Ключ читається через `read_env_key('ATLAS_EMBEDDING_API_KEY', args.env_file)`. Типове значення `--env-file`: `C:\Projects\text-generator\.env`.
- [ ] **Step 4: Тести проходять** в обох середовищах. `grep -rn "zure" scripts tests` не знаходить нічого.
- [ ] **Step 5: Commit** `feat(bench): клієнт Voyage замість Azure через сукупний журнал витрат`.

---

### Task 3: Генератор контекстів записів

**Files:**
- Create: `scripts/memory_bench/context_gen.py` — промпт, ключ кешу, генерація; без numpy і без `anthropic` при імпорті.
- Create: `scripts/rag_contexts.py` — CLI, будова як у `rag_paraphrases.py`.
- Modify: `scripts/memory_bench/paraphrase_gen.py` — `AnthropicClient(api_key, model=HAIKU, max_tokens=MAX_TOKENS)`.
- Test: `tests/retrieval_bench/test_context_gen.py`

**Interfaces:**
- Consumes: `AnthropicClient`, `CompletionClient`, `SpendLedger`, `read_env_key`, `load_story` / `_check_data_dir` з `rag_paraphrases.py`.
- Produces: `CONTEXT_PROMPT` (текст нижче), `CONTEXT_PROMPT_ID = sha256(CONTEXT_PROMPT)`, `CONTEXT_MAX_TOKENS = 4096`.
- Produces: `context_key(record: Record, prose: str) -> str`. Це sha256 рядка `'|'.join((HAIKU, CONTEXT_PROMPT_ID, record.claim_id, str(record.source_scene), sha256(record.text), sha256(prose)))`.
- Produces: `context_targets(scenes: list[SceneInput]) -> tuple[list[tuple[Record, str]], int]`. Повертає унікальні за `(claim_id, text)` записи пулів ранжування (`category != 'timeline'`) з `source_scene`, чия сцена є в `scenes`, разом із прозою цієї сцени. Другий елемент — кількість записів без `source_scene` або без сцени (`no_source`).
- Produces: `generate_context(record, prose, client, ledger) -> tuple[str | None, str]`. Друге значення — статус: `ok`, `truncated`, `empty`, `refusal` (`stop_reason` `refusal`), `stop_<причина>` (будь-яка інша причина зупинки, крім `end_turn`) чи `budget`. Спроба з будь-яким статусом, крім `ok`, оплачується, не кешується й повторюється до 3 разів.
  - Відповідь `stop_reason == 'max_tokens'` або порожня після `strip()` дає `None`.
  - Оплачується кожна спроба. До 3 спроб; далі `failed`.
- Produces: `contexts.json` у `--out` поза репозиторієм:
  - `{'meta': {'model', 'prompt_id', 'story', 'prices_date'}, 'items': {key: {'claim_id', 'source_scene', 'status': 'ok'|'failed', 'context'?}}, 'snapshot': sha256 відсортованих (key, status)}`;
  - запис у файл — атомарний.
- Produces: маніфест без текстів (`--manifest`, дозволено в репозиторії): `meta`, `snapshot`, `items: {key: {claim_id, source_scene, status}}`.
- Produces: stdout — один JSON: `{'targets', 'ok', 'failed', 'truncated', 'no_source', 'cached', 'usd_spent', 'usd_ledger_total', 'est_usd_per_call', 'prices_date', 'snapshot'}` або `{'error': code}`.
  - Коди відмови до створення клієнта: `cloud_not_allowed`, `inside_repo`, `spend_ledger_missing`, `anthropic_key_missing`, коди даних як у генераторі перефразувань.
  - Повторний запуск бере `ok` з кешу (той самий `contexts.json`) і платить лише за `failed` та нові ключі.

Текст промпта (точний):

```text
Нижче — сцена історії і один запис пам'яті, зроблений за цією сценою. Напиши одне-два коротких речення контексту: хто, де і коли в історії стосується цей запис, щоб запис можна було знайти пошуком серед інших записів цієї історії. Не переказуй запис і не додавай нового. Відповідай лише текстом контексту.
```

Далі в промпті йдуть блоки `Сцена:\n<проза>` і `Запис: <текст>`.

- [ ] **Step 1: Тести** (фейковий клієнт; `anthropic` не потрібен):

```python
def test_context_key_changes_with_prose_scene_text_and_claim(): # each field change → new key; same inputs → same key
def test_targets_unique_and_no_source_counted(): # synthetic scenes: duplicate record across scenes counted once; record without source_scene → no_source
def test_truncated_or_empty_reply_never_cached_and_retried(): # client returns ('…', stop 'max_tokens'), then ('', end_turn), then ok → status ok after 3 calls, ledger 3 calls, truncated counter 1
def test_three_failures_give_failed_and_rerun_pays_only_failed(outside_dir): # rerun with a working client → calls == number of failed
def test_budget_stops_before_call(): # ledger near cap → no call, status 'budget', run exits {'error': 'cloud_budget_exceeded'} after saving what was paid
def test_output_and_manifest_carry_no_text(outside_dir, capsys): # stdout and manifest have no record/prose/context text (search a sentinel word)
def test_refusals_before_client(): # story outside --cloud-stories, --out inside repo, missing ledger, missing key → codes; make_client not called
```

- [ ] **Step 2: Запустити, щоб тести впали.**
- [ ] **Step 3: Реалізувати.** `est_usd_per_call` рахується з середньої довжини промпта цілей: `ceil(chars / 2)` вхідних токенів плюс 600 вихідних, за цінами Haiku.
- [ ] **Step 4: Тести проходять** в обох середовищах (у середовищі продукту без `anthropic`).
- [ ] **Step 5: Commit** `feat(bench): генератор контекстів записів через Claude Haiku`.

---

### Task 4: Контекстні колонки в бенчмарку

**Files:**
- Modify: `scripts/memory_bench/ranking.py` — `contextual(ranker, search_text)`.
- Modify: `scripts/memory_bench/strategies.py` — `context_strategies(...)`.
- Modify: `scripts/memory_retrieval_bench.py`:
  - `--contexts`, `load_contexts`, реєстрація назв у `VECTOR_PREFIXES`/`CORE_AWARE` і `retrieval_layer`;
  - ранжувальники для пар і перефразувань;
  - секція `contexts` у звіті.
- Modify: `scripts/memory_bench/paraphrase_eval.py` — `strategy_name` для `ctx_*`; базова лінія «лише план» (M6).
- Test: `tests/retrieval_bench/test_context_columns.py`, `tests/retrieval_bench/test_paraphrase_eval.py`, `tests/retrieval_bench/test_cli.py`

**Interfaces:**
- Consumes: `contexts.json` і `context_key` (задача 3), `vector_rankers`, `_structural_retrieval`.
- Produces: `contextual(ranker: Ranker, search_text: Mapping[str, str]) -> Ranker`.
  - Ранжує проксі-копії `dataclasses.replace(r, text=search_text.get(r.claim_id, r.text))`, а повертає оригінальні об'єкти пулу в отриманому порядку.
  - Ключ мапи — `(claim_id, текст запису)`: оновлені записи ділять `claim_id`, а ключ контексту вже містить текст запису (рішення P5).
- Produces: `CTX_MODELS = ('nano-2048', 'voyage-4')`.
- Produces: `context_strategies(search_text, embedders) -> dict` з такими стратегіями:
  - `structural_ctx_fts` (шар `ctx_fts`);
  - для кожної моделі з `CTX_MODELS`, що є серед `--vector-models`: `structural_ctx_vec[<key>]` (шар `ctx_vec`) і `structural_ctx_hybrid[<key>]` (шар `ctx_hybrid`).
- Produces: назви колонок у звітах пар і перефразувань — `ctx_bm25`, `ctx_vec[<key>]`, `ctx_hybrid[<key>]`. `strategy_name('ctx_bm25') == 'structural_ctx_fts'`, `strategy_name('ctx_vec[m]') == 'structural_ctx_vec[m]'`.
- Produces: `load_contexts(path, scenes, story_id) -> tuple[dict[str, str] | None, dict | None, str | None]`, тобто мапа `claim_id → текст пошуку`, секція звіту й код помилки.
  - **`inside_repo`** — тека всередині репозиторію.
  - **`contexts_missing`** — файл не читається.
  - **`contexts_stale`**:
    - `meta.story`, `meta.model` чи `meta.prompt_id` не збігаються;
    - перерахований `context_key` запису зі сценою походження відсутній у `items`;
    - `snapshot` не відповідає `items`.
  - Записи зі статусом `failed` шукаються за власним текстом і рахуються.
- Produces: секція звіту `contexts`: `{'snapshot', 'ok', 'failed', 'no_source', 'models': [...]}`, без текстів.
- Produces: у `evaluate_paraphrases` для форми `in_plan` — `baseline_plan[level][column][step][core]` і `baseline_plan_n[level]`: частка попадань цілі в контекст, коли запит — лише план сцени без речення перефразування (M6); знаковий тест `sign_in_context_vs_plan` рахується для кожної клітинки рівня.

- [ ] **Step 1: Тести:**

```python
def test_contextual_ranks_by_search_text_returns_originals(): # fts over proxies: query word only in context → record ranked first; returned object `is` the original
def test_ctx_strategy_with_empty_contexts_equals_plain_column(): # synthetic story: structural_ctx_fts with search_text == {} gives the same record_ids, layers counts (ctx_fts vs fts) and text as structural_fts
def test_ctx_budget_uses_record_text_only(): # long context, tight budget: chosen records and Selection.text identical to plain column when ranking order is equal
def test_load_contexts_codes(outside_dir): # missing → contexts_missing; other story / prompt_id → contexts_stale; one key removed → contexts_stale; failed item → searched by own text and counted
def test_no_source_record_uses_own_text(): # record without source_scene: search text == record.text, counted in no_source
def test_ctx_names_registered(): # variants() yields both cores for structural_ctx_*; retrieval_layer gives ctx_fts / ctx_vec / ctx_hybrid
def test_paraphrase_baseline_plan(): # synthetic: baseline_plan present per column/step/core; equals in_context when the paraphrase sentence is empty
def test_cli_contexts_round_trip(outside_dir): # fake contexts.json for the synthetic story + FakeEmbedder keys standing in for nano-2048 (monkeypatched CTX_MODELS) → report has ctx columns in real, pairs/ranking and paraphrases; no text sentinel in stdout
```

- [ ] **Step 2: Запустити, щоб тести впали.**
- [ ] **Step 3: Реалізувати.**
- [ ] **Step 4: Тести проходять** в обох середовищах.
- [ ] **Step 5: Commit** `feat(bench): контекстні колонки пошуку (контекст лише для ранжування)`.

---

## Після задач: прогони й документи (контролер)

Ці кроки виконує контролер, а не субагенти. Вони платні в межах уже погоджених меж, і звіти тут дивляться лише в агрегатах.

1. **Фінальна рецензія гілки** за subagent-driven-development, одна хвиля виправлень, `verify.py` з `C:/tmp/rvb4`.
2. **Кеш нано.** Видаляти нічого не треба: після задачі 2 `dtype` входить у ключ, тож старі bf16-вектори просто не збігаються з новими ключами. Підтвердити в звіті прогону, що `nano-2048` має `misses` > 0 при першому прогоні.
3. **Перевірка на нейтральному рядку.** Один виклик `VoyageEmbedder` через журнал на рядку «перевірка зв'язку», без тексту твору. Очікуємо вектор 1024, `usage.total_tokens` > 0 і новий рядок `voyage` у журналі.
4. **Контексти:**
   - `rag_contexts.py --story 039b7438 --out C:\tmp\rag-bench\ctx-main --manifest docs/research/data/2026-11-27-rag-contexts-main-manifest.json`;
   - те саме для `858693d4` → `ctx-testa`, `…-testa-manifest.json`.

   Маніфести додаються через `git add -f`. Зупинитися, якщо `failed` > 5 % цілей.
5. **Прогони** (`C:/tmp/rag-bench/venv`, `--data` — копія `C:\tmp\rag-bench\data`, вивід у `C:\tmp\rag-bench\runs\`):
   - **Основний твір.** Параметри:
     - `--story 039b7438 --vector-models e5-base,bge-m3,nano-2048,nano-512,voyage-4`;
     - `--paraphrases C:\tmp\rag-bench\para-main --contexts C:\tmp\rag-bench\ctx-main --budget-steps 1.0,0.75,0.5,0.35`;
     - `--cloud --cloud-stories 039b7438,858693d4 --repro`.

     Результат — `runs\main.json`.
   - **Тест А.** Ті самі моделі, `--pairs docs/superpowers/notes/2026-11-24-rag-test-pairs.json --pairs-annotation docs/research/data/2026-11-24-rag-pairs-annotation.json --contexts C:\tmp\rag-bench\ctx-testa --budget-steps …`. Результат — `runs\testa.json`.
   - **Відтворюваність Voyage.** Один раз: основний твір із `--vector-models voyage-4 --repro --repro-cloud`. Результат — `runs\main-voyage-repro.json`.
6. **Розділ дослідження** «Voyage 4, перефразування й контекст: вимірювання 27.11.2026» у `docs/research/2026-11-08-memory-scaling-retrieval.md`. Лише агрегати. Зміст:
   - знаменники й частку випалих за рівнями, позначку `unreliable`;
   - медіану рангу, `found`, топ-5/10 за рівнями й колонками;
   - знакові тести (обрізаний ранг — основний) і попадання в контекст на щаблях проти `baseline_plan`;
   - ефект контексту (`ctx_*` проти безконтекстних);
   - локальне проти хмари (нано проти `voyage-4`);
   - відтворюваність, ціну за журналом із датою цін, обмеження (набір пише модель, чергування в корені);
   - перегляд рекомендації #25.

   Команди відтворення, що згадують `azure-3-large`, замінити на чинні. Історичні результати Azure лишаються як є.
7. **Опис PR #309.** Додати:
   - коміти `1d7e846f` і обв'язки;
   - лічильники генерації: 118 із 120, випало 2, обрізаних 0;
   - перевірку власника 20/20;
   - контексти й прогони;
   - результат `verify.py`.

   Перевірити, що PR відкритий (не змерджений) і досі має статус чернетки.
