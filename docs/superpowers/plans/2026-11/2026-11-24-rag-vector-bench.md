# Векторний пошук проти BM25 (стратегія Г) — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Розширити бенчмарк #25 векторним і гібридним добором, метрикою закладених пар і діагностикою ранжування без шарів, прогнати його на основному творі та тексті А і дописати розділ у дослідження #25.

**Architecture:** Нові стратегії `structural_vec[<m>]` / `structural_hybrid[<m>]` повторюють `structural_fts` і відрізняються лише рангом добору залишку бюджету. Ембединги йдуть через інтерфейс `Embedder` з дисковим кешем поза репозиторієм. Векторні залежності — окремий файл вимог для дослідницького середовища. Розмітка пар зберігає лише ID; тексти показуються тільки локально, у файлі поза репозиторієм.

**Tech Stack:** Python 3.12, sqlite FTS5, numpy, sentence-transformers (лише дослідницьке середовище), httpx (Azure, за прапорцем), pytest.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-24-rag-vector-bench-design.md`

## Global Constraints

- **Дані.** Робоча база лише на читання. Скрипт приймає тільки копію теки даних; `data/` відхиляється кодом `live_data` (наявна `_check_data_dir`).
- **Вивід.** У виводі, звітах і репозиторії — лише ID, коди й агрегати. ID записів можна тримати лише у файлі розмітки пар.
- **Кеш.** Кеш ембедингів і файли кандидатів з текстами лежать поза репозиторієм, типово `C:\tmp\rag-bench\…`. Шлях усередині репозиторію відхиляється.
- **Залежності.** Нічого не додається до `requirements-lock.txt` і `pyproject.toml`. Векторні залежності — у `scripts/memory_bench/requirements-vector.txt`. Наявні тести й стратегії працюють без них.
- **Хмара.** Без `--cloud` хмарний клієнт не створюється. Твір поза `--cloud-stories` у хмару не надсилається. Оцінка понад `--cloud-max-usd` зупиняє запуск. У цьому плані реальних хмарних викликів немає.
- **Параметри відбору:** RRF k = 60; порогу схожості немає; рівні оцінки вирішуються за `claim_id`. Векторні оцінки округлюються до 1e-6 перед сортуванням.
- **Моделі:**
  - `e5-base` = `intfloat/multilingual-e5-base`, префікси `query: ` / `passage: `, межа 512 токенів;
  - `bge-m3` = `BAAI/bge-m3`, лише щільні вектори, межа 8192 токени;
  - `azure-3-large` = розгортання Azure `text-embedding-3-large`.
- **Щаблі бюджету для тестових текстів:** 1.0, 0.75, 0.5, 0.35, 0.25 від `tokens_realistic` стратегії `full` цієї сцени.
- **recall@k діагностики:** k = 5, 10, 20.
- **Повні тести й `scripts/verify.py`** запускаються з короткого шляху `C:/tmp/<коротка-назва>` (AGENTS.md), а не з `.claude/worktrees/…`.
- **Документи** українською. PR — чернетка на `main` (#309), не мерджиться.

## Review Focus

1. **Запис пари закрито або змінено до сцени-повтору.** Такий запис не повинен рахуватися ні влучанням, ні промахом. Він іде як `missing_in_memory`, як у `control_hits`. Тест — у Task 2.
2. **Сцена-повтор пропущена екстрактором** (немає пам'яті попередньої сцени або вона не підтверджена, як може статися з частковим текстом Б). Пара отримує `scene_skipped` і не потрапляє в знаменник. Тест — у Task 2.
3. **Порожній план сцени або план довший за межу моделі.** Порожній запит нічого не ранжує, як `fts_rank` з порожнім запитом. Обрізання рахується в `truncated`. Тести — у Task 4 і Task 5.
4. **Кеш з іншої ревізії моделі.** Ключ кешу містить ревізію, тож вектори старої ревізії не перевикористовуються. Тест — у Task 5.
5. **Текст потрапляє у вивід.** Серед рядків JSON-звіту немає жодного тексту запису, плану чи імені. Тест — у Task 7.

---

### Task 1: Розмітка пар (`annotate_pairs.py`)

**Files:**
- Create: `scripts/memory_bench/annotate_pairs.py`
- Test: `tests/retrieval_bench/test_annotate_pairs.py`

**Interfaces:**
- Consumes: `memory_bench.extract.extract_story(repo, story_id, protagonist=None) -> (list[SceneInput], dict)`. `SceneInput.number` — номер сцени (позиція + 1). `SceneInput.records` — активні записи перед сценою.
- Produces:
  - `load_pairs(path) -> dict` — JSON зі списком пар `docs/superpowers/notes/2026-11-24-rag-test-pairs.json`;
  - `candidates(scenes: list[SceneInput], pair: dict) -> list[Record]` — записи сцени-повтору (`SceneInput` з `number == pair['repeat']`), текст яких містить основу хоч одного слова `first_words` / `words`. Основа — перші 5 літер слова з ≥ 4 літер, без урахування регістру й апострофів;
  - CLI `propose --data D --story S --pairs P --out C:\tmp\…\candidates.json` пише `{pair_id: [{claim_id, category, text}]}`. Шлях `--out` усередині репозиторію відхиляється з кодом `inside_repo`;
  - CLI `confirm --data D --story S --pairs P --picks picks.json --annotation A` перевіряє, що кожен ID є серед записів сцени-повтору. Потім пише або доповнює `A` у форматі `{"stories": {story_id: {pair_id: [claim_id, …]}}}`. Невідомий ID дає код `unknown_claim` і нічого не пише;
  - файл розмітки за замовчуванням: `docs/research/data/2026-11-24-rag-pairs-annotation.json`.

- [ ] **Step 1: Тести.**
  - `test_candidates_match_word_stems`: запис «Марія у світлому каре» знаходиться для `first_words` «світле каре», запис «Іде дощ» — ні.
  - `test_candidates_use_repeat_scene_snapshot`: беруться записи з `SceneInput` сцени-повтору, а не першої появи.
  - `test_propose_refuses_out_inside_repo`: код повернення 2, у stderr `inside_repo`.
  - `test_confirm_rejects_unknown_claim`: код `unknown_claim`, файл розмітки не створено.
  - `test_confirm_writes_ids_only`: у файлі розмітки немає жодного тексту запису.

  Сцени будуються helper-ами `tests/retrieval_bench/helpers.py`. CLI тестується з `extract_story`, підміненим через monkeypatch, — без бази.
- [ ] **Step 2:** `python -m pytest tests/retrieval_bench/test_annotate_pairs.py -v` → FAIL (модуля немає).
- [ ] **Step 3:** Реалізувати функції й CLI (`argparse` з підкомандами). Дані відкриваються так само, як у `memory_retrieval_bench.run`: через `_check_data_dir` і `Repository`.
- [ ] **Step 4:** Те саме → PASS. `python -m pytest tests/retrieval_bench -q` → PASS (нічого не зламано).
- [ ] **Step 5:** Commit `feat(bench): розмітка закладених пар (лише ID)`.

### Task 2: Метрика пар і `retrieval_ids`

**Files:**
- Modify: `scripts/memory_bench/model.py` (`Selection`)
- Modify: `scripts/memory_bench/strategies.py` (`_selection`, `structural_fts`)
- Modify: `scripts/memory_bench/metrics.py`
- Test: `tests/retrieval_bench/test_pairs_metric.py`, `tests/retrieval_bench/test_strategies.py`

**Interfaces:**
- Produces:
  - `Selection.retrieval_ids: tuple[str, ...] = ()` — ID, які взяв шар добору (`fts`, далі `vec` / `hybrid`). `structural_fts` заповнює його;
  - `pair_hits(annotation: Mapping[str, list[str]], pairs: dict, scenes_by_number: Mapping[int, SceneInput], selections_by_number: Mapping[int, Selection]) -> list[dict]` — по одному рядку на пару й контрольну пару: `{'id': 'P01', 'kind': 'pair'|'control', 'hit': bool|None, 'by_retrieval': bool|None, 'reason': None|'scene_skipped'|'missing_in_memory'|'not_annotated'}`. Тут `hit` — хоч один ID пари є в `record_ids` сцени-повтору; `by_retrieval` — хоч один є в `retrieval_ids`;
  - `pair_summary(rows) -> dict` — `{'pair': {'hit': n, 'by_retrieval': n, 'total': N}, 'control': {...}}`. У `total` не входять рядки з `reason`.

- [ ] **Step 1: Тести.**
  - `test_structural_fts_reports_retrieval_ids`: запис, узятий лише FTS (немає в шарах), є в `retrieval_ids`; запис ядра — ні.
  - `test_pair_hit_and_by_retrieval`: перевірка обох прапорців.
  - `test_pair_missing_in_memory` (Review Focus 1).
  - `test_pair_scene_skipped` (Review Focus 2).
  - `test_pair_not_annotated`.
  - `test_pair_summary_excludes_reasons_from_total`.
  - `test_pair_rows_contain_no_claim_ids`: у рядках тільки ID пар.
- [ ] **Step 2:** `python -m pytest tests/retrieval_bench/test_pairs_metric.py tests/retrieval_bench/test_strategies.py -v` → нові тести FAIL.
- [ ] **Step 3:** Реалізувати. `_selection` отримує необов'язковий `retrieval=()`.
- [ ] **Step 4:** `python -m pytest tests/retrieval_bench -q` → PASS.
- [ ] **Step 5:** Commit `feat(bench): метрика закладених пар і retrieval_ids`.

### Task 3: Діагностика ранжування й recall ядра / атмосфери

**Files:**
- Create: `scripts/memory_bench/ranking.py`
- Modify: `scripts/memory_bench/metrics.py` (`scene_metrics`, `aggregate`)
- Test: `tests/retrieval_bench/test_ranking.py`, `tests/retrieval_bench/test_metrics.py`

**Interfaces:**
- Consumes: `strategies.fts_rank(candidates, query_text) -> list[Record]`.
- Produces:
  - `Ranker = Callable[[list[Record], str], list[Record]]`;
  - `ranking_pool(scene: SceneInput) -> list[Record]` — `scene.records` без категорії `timeline`;
  - `pair_ranks(rankers: Mapping[str, Ranker], annotation, pairs, scenes_by_number) -> dict` — для кожного рангувальника й виду (`pair` / `control`): `{'recall_at': {'5': n, '10': n, '20': n}, 'total': N, 'median_rank': float|None}`. Ранг пари — найкращий ранг її записів. Запис, якого рангувальник не повернув, має ранг ∞ і рахується як промах;
  - `scene_metrics` додає `targets_core`, `targets_core_hit`, `targets_atmosphere`, `targets_atmosphere_hit`. Атмосфера визначається через `storygen.memory.selection.classify(scene.product)['atmosphere']`, якщо `scene.product` є, інакше всі цілі вважаються ядром. `aggregate` додає `target_recall_core` і `target_recall_atmosphere`.

- [ ] **Step 1: Тести.**
  - `test_pair_ranks_recall_at_k`: пара з рангом 7 входить у @10 і @20, а не в @5.
  - `test_unranked_record_counts_as_miss`.
  - `test_ranking_pool_excludes_timeline`.
  - `test_aggregate_splits_core_and_atmosphere_recall`: `scene.product` = `None`, усі цілі — ядро.
  - `test_target_kinds_use_product_classify`: у `tests/retrieval_bench/test_product.py` наявні фікстури продукту.
- [ ] **Step 2:** pytest цих файлів → FAIL.
- [ ] **Step 3:** Реалізувати.
- [ ] **Step 4:** `python -m pytest tests/retrieval_bench -q` → PASS.
- [ ] **Step 5:** Commit `feat(bench): діагностика ранжування без шарів, recall ядра й атмосфери`.

### Task 4: Попередня перевірка на тексті А (BM25, без векторів)

Рішення дизайну: перевірити до векторів, які шари забирають записи пар. Код тут не пишеться, крім одного режиму CLI.

**Files:**
- Modify: `scripts/memory_retrieval_bench.py`: прапорці `--pairs`, `--pairs-annotation`, `--budget-steps`, секції звіту `pairs`, `ranking`, `budget_steps`
- Test: `tests/retrieval_bench/test_cli.py`

**Interfaces:**
- Consumes: Task 1–3.
- Produces:
  - `--budget-steps 1.0,0.75,0.5,0.35,0.25` — для кожного щабля й кожного варіанта бюджет пам'яті сцени дорівнює `step × full(scene).tokens_realistic` у мірі `realistic`. Секція `budget_steps[step][variant]` = `aggregate(...)` + `pairs: pair_summary(...)`;
  - секція `pairs[variant]` для бюджету з найбільшого `--context`;
  - секція `ranking` = `pair_ranks({'bm25': fts_rank}, …)` плюс розклад того, який шар `structural_fts` узяв кожен запис пари. Ключі — назви шарів, значення — кількості, без ID.

- [ ] **Step 1: Тести** (`test_cli.py`, на синтетичній базі наявного `conftest.py`).
  - `test_budget_steps_section_present`.
  - `test_pairs_section_counts_only`.
  - `test_ranking_section_has_bm25`.
- [ ] **Step 2:** pytest → FAIL.
- [ ] **Step 3:** Реалізувати прапорці й секції. Шари, що взяли записи пар, визначаються різницею: `record_ids` мінус `retrieval_ids`, кожен запис зіставляється з шаром через `_layers`.
- [ ] **Step 4:** `python -m pytest tests/retrieval_bench -q` → PASS. Commit `feat(bench): секції пар, ранжування й щаблів бюджету`.
- [ ] **Step 5: Копія даних.** `C:\tmp\rag-bench\data` знімається через `readonly_database` + `sqlite3.backup` разом із текою `stories/` (як у #25). Перевірити, що розмір і mtime `data/storygen.sqlite3` не змінилися.
- [ ] **Step 6: Розмітка.** `propose` для тексту А (`--story 858693d4`) → агент читає кандидатів у `C:\tmp\rag-bench\candidates-A.json`, складає `C:\tmp\rag-bench\picks-A.json` → `confirm`. Очікується: усі 10 пар і 3 контрольні мають ≥ 1 ID.
- [ ] **Step 7: Прогін.** `python scripts/memory_retrieval_bench.py --data C:\tmp\rag-bench\data --story 858693d4 --synthetic "" --pairs docs/superpowers/notes/2026-11-24-rag-test-pairs.json --pairs-annotation docs/research/data/2026-11-24-rag-pairs-annotation.json --budget-steps 1.0,0.75,0.5,0.35,0.25 > C:\tmp\rag-bench\precheck-A.json`.
- [ ] **Step 8: Звіт власнику.** Коротко: скільки записів пар забирають шари, а скільки лишається добору; recall@k BM25. Продовжувати без чекання, якщо власник не зупинить. Розмітку закомітити: `data(research): розмітка пар тексту А`.

### Task 5: Ембединги, кеш і векторне ранжування

**Files:**
- Create: `scripts/memory_bench/embeddings.py`, `scripts/memory_bench/requirements-vector.txt`
- Modify: `scripts/memory_bench/ranking.py`
- Test: `tests/retrieval_bench/test_embeddings.py`, `tests/retrieval_bench/test_ranking.py`

**Interfaces:**
- Produces:
  - `class Embedder(Protocol)`: `key: str`, `model_id: str`, `revision: str`, `dim: int`, `max_tokens: int`, `truncated: int`, `embed(texts: Sequence[str], kind: Literal['query','passage']) -> np.ndarray` — рядки L2-нормалізовані, `float32`;
  - `FakeEmbedder(dim=16)` — вектор з sha256 тексту, детермінований, без мережі (для тестів);
  - `LocalEmbedder(key, model_id, revision, query_prefix, passage_prefix, max_tokens, threads=1)` на `sentence_transformers.SentenceTransformer(model_id, revision=revision, device='cpu')`. Імпорт усередині конструктора. `truncated` рахує тексти, довші за `max_tokens` за токенізатором моделі;
  - `CachedEmbedder(inner: Embedder, cache_dir: Path)` — ключ `sha256(model_id|revision|kind|prefix|text)`, формат на розсуд виконавця. `cache_dir` усередині репозиторію → `ValueError('inside_repo')`. Поле `hits` / `misses`;
  - `MODELS: dict[str, dict]` — реєстр `e5-base`, `bge-m3`, `azure-3-large` з параметрами з Global Constraints. Ревізії `e5-base` і `bge-m3` — хеш коміту Hugging Face, закріплений у коді при першому завантаженні (Task 8);
  - `vec_rank(candidates, query_text, embedder) -> list[Record]` — косинус (скалярний добуток нормалізованих), оцінка округлена до 1e-6, сортування `(-score, claim_id)`. Порожній запит повертає `[]`;
  - `rrf_rank(candidates, query_text, embedder, k=60) -> list[Record]` — `1/(k+r_bm25) + 1/(k+r_vec)`, ранги з 1. Відсутній у BM25 запис має лише векторну частину. Рівні оцінки — за `claim_id`.

- [ ] **Step 1: Тести.**
  - `test_fake_embedder_is_deterministic_and_normalized`.
  - `test_vec_rank_orders_by_cosine_ties_by_claim_id`.
  - `test_vec_rank_empty_query_ranks_nothing` (Review Focus 3).
  - `test_rrf_combines_ranks_with_k60`: два записи з відомими рангами дають очікуваний порядок.
  - `test_rrf_record_missing_from_bm25_gets_vector_part_only`.
  - `test_cache_hit_skips_inner`: другий виклик → `misses` не росте.
  - `test_cache_key_includes_revision` (Review Focus 4).
  - `test_cache_dir_inside_repo_refused`.
  - `test_embeddings_module_optional`: імпорт `memory_bench.strategies` не тягне `sentence_transformers`.

  Тести з numpy — `pytest.importorskip('numpy')`.
- [ ] **Step 2:** pytest → FAIL.
- [ ] **Step 3:** Реалізувати. `requirements-vector.txt`: `numpy`, `sentence-transformers`, `torch` (CPU-збірка) з точними версіями, перевіреними під час Task 8.
- [ ] **Step 4:** `python -m pytest tests/retrieval_bench -q` → PASS.
- [ ] **Step 5:** Commit `feat(bench): ембединги з кешем, векторне ранжування й RRF`.

### Task 6: Стратегії `structural_vec` / `structural_hybrid` і хмарний клієнт

**Files:**
- Modify: `scripts/memory_bench/strategies.py`
- Modify: `scripts/memory_bench/embeddings.py` (`AzureEmbedder`)
- Test: `tests/retrieval_bench/test_vector_strategies.py`, `tests/retrieval_bench/test_azure.py`

**Interfaces:**
- Consumes: `vec_rank`, `rrf_rank`, `Embedder` з Task 5; `_structural` з `strategies.py`.
- Produces:
  - `vector_strategies(embedder: Embedder) -> dict[str, Callable[[SceneInput, Params], Selection]]` з ключами `f'structural_vec[{embedder.key}]'` і `f'structural_hybrid[{embedder.key}]'`. Тіло те саме, що в `structural_fts`: той самий `pool` і той самий `budget.take`. Відрізняється лише рангувальник і назва шару в `layers` (`vec` / `hybrid`). Обидва заповнюють `retrieval_ids`;
  - `LAYERS` доповнюється `'vec'` і `'hybrid'`;
  - `AzureEmbedder(key, endpoint, api_key, deployment, api_version, price_per_mtok: float, max_usd: float, transport=None)`:
    - викликає `POST {endpoint}/openai/deployments/{deployment}/embeddings?api-version=…` через `httpx`, батчами;
    - перед першим викликом оцінює токени як `ceil(len(text) / 2)` на текст. Якщо `оцінка × price_per_mtok / 1e6 > max_usd`, кидає `ValueError('cloud_budget')`;
    - накопичує `tokens`, `usd`, латентності;
  - `cloud_allowed(story_id: str, prefixes: Sequence[str]) -> bool`.

- [ ] **Step 1: Тести.**
  - `test_vec_strategy_same_pool_and_budget_as_fts`: на однакових даних `structural_vec` і `structural_fts` мають однакові ядро, шари до добору й `dropped_by_budget`. Різниться лише набір `retrieval_ids`.
  - `test_vec_strategy_picks_semantic_match_with_fake`: `FakeEmbedder` з підміненим вектором робить запис першим.
  - `test_hybrid_layer_name`.
  - `test_azure_refuses_over_budget` (`httpx.MockTransport`, жодного запиту не відправлено).
  - `test_azure_parses_embeddings_and_counts_usage`.
  - `test_cloud_allowed_by_prefix_only`.
- [ ] **Step 2:** pytest → FAIL.
- [ ] **Step 3:** Реалізувати.
- [ ] **Step 4:** `python -m pytest tests/retrieval_bench -q` → PASS.
- [ ] **Step 5:** Commit `feat(bench): стратегії structural_vec/hybrid і хмарний клієнт за прапорцем`.

### Task 7: CLI для векторів, відтворюваність і вартість

**Files:**
- Modify: `scripts/memory_retrieval_bench.py`
- Test: `tests/retrieval_bench/test_cli.py`

**Interfaces:**
- Consumes: Task 4–6.
- Produces:
  - прапорці `--vector-models e5-base,bge-m3[,azure-3-large]`, `--cache-dir` (типово `C:\tmp\rag-bench\cache`), `--cloud`, `--cloud-stories`, `--cloud-max-usd` (типово 2.0), `--cloud-price-per-mtok`, `--repro`;
  - модель `azure-3-large` без `--cloud` або для твору поза `--cloud-stories` → код `cloud_not_allowed`, вихід 2. Змінні Azure читаються з оточення: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_EMBEDDING_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION`;
  - векторні варіанти додаються до `variants()` (core upper і lower, як для `structural_fts`). Вони працюють у `real`, `budget_steps`, `pairs`. Синтетика їх не отримує;
  - `ranking` отримує рангувальники `vec[<m>]` і `hybrid[<m>]`;
  - секція `vector`:
    - на кожну модель: `model_id`, `revision`, `dim`, `max_tokens`, префікси, `truncated`, `threads`, версії бібліотек;
    - `index_seconds` (холодний старт окремо), `weights_bytes` (розмір теки моделі в кеші Hugging Face), `cache_bytes`, `cache_hits` / `cache_misses`;
    - для хмари — `tokens`, `usd`, `latency_ms` (p50 / p90);
  - `--repro`: для локальних моделей повторний прогін векторних варіантів з порожнім кешем у тимчасовій теці. `vector[m]['repro_identical_share']` — частка сцен з ідентичними `record_ids`.

- [ ] **Step 1: Тести** (з `FakeEmbedder`, підміненим у реєстрі через monkeypatch).
  - `test_vector_variants_in_real_and_steps`.
  - `test_synthetic_has_no_vector_variants`.
  - `test_cloud_model_without_flag_refused`.
  - `test_repro_identical_share_with_fake_is_one`.
  - `test_report_contains_no_texts` (Review Focus 5): кожен текст запису, плану та ім'я з тестової бази відсутній у `json.dumps(report)`.
- [ ] **Step 2:** pytest → FAIL.
- [ ] **Step 3:** Реалізувати.
- [ ] **Step 4:** `python -m pytest tests/retrieval_bench -q` → PASS.
- [ ] **Step 5:** Commit `feat(bench): векторні варіанти в CLI, відтворюваність і вартість`.

### Task 8: Прогін і розділ дослідження

**Files:**
- Modify: `scripts/memory_bench/embeddings.py` (закріплені ревізії), `scripts/memory_bench/requirements-vector.txt` (точні версії)
- Modify: `docs/research/2026-11-08-memory-scaling-retrieval.md`
- Modify: `docs/STATUS.md` (запис `verify.py`, якщо його вимагає `check_docs`)

- [ ] **Step 1: Середовище.** `C:\tmp\rag-bench\venv` з залежностями продукту (`requirements-lock.txt`) + `requirements-vector.txt`. Завантажити обидві моделі й закріпити хеші ревізій у `MODELS` і точні версії бібліотек у файлі вимог.
- [ ] **Step 2: Текст А.** `python scripts/memory_retrieval_bench.py --data C:\tmp\rag-bench\data --story 858693d4 --synthetic "" --vector-models e5-base,bge-m3 --repro --pairs … --pairs-annotation … --budget-steps 1.0,0.75,0.5,0.35,0.25 > C:\tmp\rag-bench\run-A.json`.
- [ ] **Step 3: Основний твір.** Без `--story` береться твір з найбільшою кількістю сцен; `--vector-models e5-base,bge-m3 --repro`, контексти за замовчуванням → `C:\tmp\rag-bench\run-main.json`. Пар немає, тому лише `real`, `ranking` за цілями не рахується.
- [ ] **Step 4: Розділ дослідження.** Новий розділ «Векторний пошук (Г): вимірювання 24.11.2026» у дослідженні #25 за розділом 8 дизайну:
  - таблиці поруч із наявними (символи, recall ядра й атмосфери, вміщення 32 / 64 / 128 тис.);
  - пари й контрольні пари (n з N, «узято добором»);
  - recall@k діагностики;
  - щаблі бюджету тексту А;
  - відтворюваність і вартість;
  - перегляд рекомендації одним із трьох висновків;
  - обмеження: 12 сцен, мало пар, текст Б і хмара пізніше.

  У документі — лише агрегати.
- [ ] **Step 5: Перевірки.**
  - `PYTHONIOENCODING=utf-8 python scripts/check_docs.py` → «…узгоджені.», вихід 0;
  - повні тести й `python scripts/verify.py` — з detached worktree у `C:/tmp/rvb` (junction на `.venv` і `frontend/node_modules`). Результат записати в `docs/STATUS.md`, якщо цього вимагає `check_docs`.
- [ ] **Step 6: Здача.** Commit `docs(research): вимірювання векторного пошуку (Г) для #25`, push, оновити опис чернетки PR #309 (результати, оновлена документація: лише дослідження, SPEC.MD і сайт не змінюються). Не мерджити. Скопіювати в основну теку лише нові файли дослідження, якщо власник попросить. Основна тека лишається на `main`, бо PR не мерджиться: так погоджено.
