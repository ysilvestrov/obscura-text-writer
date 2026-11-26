# R-51, специфікація 2, PR 1: ядро місць сцен — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (виконання в цій сесії). Кроки — чекбокси.

**Мета:** пошук `character_extract` пропонує місця сцен, а прийняття записує їх у сцени й картки локацій.

**Архітектура:** чиста логіка (`characters/extract.py`) отримує каталог локацій, розбір і перевірку місць; запуск (`generation/extract_run.py`) зберігає їх у стані, пропозиція — групу `locations`; прийняття (`characters/extract_accept.py`) пише місця в тій самій транзакції, що картки й склад. Правило плану (`storage/scene_metadata.py`) береже місця `model`.

**Специфікація:** [2026-11-26-location-extract-design.md](../../specs/2026-11/2026-11-26-location-extract-design.md) (затверджена злиттям #335). Обсяг PR 1 — §3, §4, §6 (SPEC, traceability, тести) без §5 (UI — PR 2).

## Глобальні обмеження

- `EXTRACT_MIN_OUTPUT_TOKENS = 24000`; промпт `character_extract_v2` (uk/en), `v1` лишається.
- До 3 місць на сцену; новий шлях до 120 символів; `l<N>` — ID каталогу локацій.
- Причини пропуску: `сцену вилучено`, `проза сцени змінилася`, `проза сцени не авторська`, `план сцени називає місце`, `немає чого додати`.
- `Scene.location_source: 'plan' | 'model'`, типово `plan`; схема БД не змінюється.
- `AcceptRequest.locations` типово `[]`; стара пропозиція без `locations` має порожню групу.

## Фокус рев'ю

1. Сцена, у якій прийнято і склад, і місця: друге записування читає сцену з транзакції (ревізія не губиться).
2. `l<N>` у середині шляху («l8 / Стая»), повтор батька («l8 / Стая» при `l8` = «Полонина / Стая»), невідомий `l<N>`.
3. Шлях злитої картки: у пропозиції — не пропонується, якщо ціль уже в сцені; при прийнятті — не дублюється.
4. Продовження старої контрольної точки без `locations` у стані.
5. `sync_story_cast` і збереження плану без «Локація:» не стирають місць `model`.

---

### Задача 1: правило плану й `location_source`

**Файли:** `src/storygen/domain.py`, `src/storygen/storage/scene_metadata.py`; тест `tests/storage/test_story_locations.py`.

- [ ] Тест `test_plan_rule_keeps_model_places` (параметри: `plan`/`model` × рядок відсутній / порожній «Локація:» / непорожній): `model` без значення — місця й джерело лишаються; непорожній — місця плану, `plan`; `plan` без значення — `[]`. Плюс `test_creating_and_importing_keep_model_places` через `sync_story_cast`.
- [ ] `Scene.location_source: Literal['plan','model'] = 'plan'`; `apply_description` за §4.4.

### Задача 2: каталог, контракт, перевірка (чиста логіка)

**Файли:** `src/storygen/characters/extract.py`; тест `tests/characters/test_extract.py`.

**Інтерфейси:** `CatalogueLocation(ref, path, existing)`, `SceneLocation(ref, suggested)`, `ExtractState.locations`, `ExtractState.scene_locations`; `SceneCast.locations: list[str]`; `location_text(state, language)`; `SceneMeta(..., location_eligible=False, locations=())`; `finalize(state, meta, has_protagonist, place_ids=None)` дає `locations`.

- [ ] Тести: місце за `l<N>`, новий вкладений шлях, `l<N> / Вужче`, повтор батька, невідомий `l<N>`, понад 3 місця, незгадане місце `suggested=False`, межа чотирилітерного слова («Стая» не знаходить «стариня», «Хата» знаходить «хаті»), новий шлях поповнює каталог, `finalize`: `set`/`add`, наявне за канонічною карткою не пропонується, неприйнятна сцена без пункту.
- [ ] Реалізація.

### Задача 3: запуск, контекст, відбиток

**Файли:** `generation/extract_context.py`, `generation/extract_run.py`, `characters/extract_plan.py`, `storage/locations.py`, `language.py`, промпти v2; тести `tests/generation/test_extract_context.py`, `tests/generation/test_extract_run.py`, `tests/characters/test_extract_plan.py`.

- [ ] Тести: запит має «Каталог локацій:» з `l<N>`, промпт v2, ліміт 24000; відбиток плану змінюється від нової картки локації чи злиття; пропозиція запуску має `locations` і `source.locations`; стара контрольна точка без `locations` продовжується з каталогом книги.
- [ ] Реалізація.

### Задача 4: прийняття й MCP

**Файли:** `characters/extract_accept.py`, `mcp/bridge.py`; тести `tests/characters/test_extract_accept.py`, `tests/mcp/test_bridge_character_extract.py`.

- [ ] Тести: `set`, `add`, кожна причина пропуску, шлях злитої картки й повтор шляху, сцена зі складом і місцями в одному прийнятті, `dry_run` нічого не пише, невідомий шлях чи сцена — 400, стара пропозиція без `locations`; MCP передає `locations`.
- [ ] Реалізація.

### Задача 5: SPEC і traceability

- [ ] SPEC.MD: CHARACTER-EXTRACT (каталог, контракт, перевірка, S12, S13), MEMORY-LOCATIONS (`location_source`, правило плану, S02), MCP-BRIDGE (`locations`); traceability; `check_docs.py`.
- [ ] Повний прогін `verify.py` з `C:/tmp/r51lcv`, фінальне рев'ю, крос-рев'ю, PR.
