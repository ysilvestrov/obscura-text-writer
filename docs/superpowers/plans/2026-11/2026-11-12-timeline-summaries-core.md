# Підсумки хронології (#68) — ядро: план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** блоки підсумків, версія й голови, придатність, шар `summary` у відборі пам'яті, окремий запуск `timeline_summary` і API — без інтерфейсу.

**Architecture:** підсумок — версія твору `timeline_summary` (JSON) з явними `input_refs`; голови — `Story.timeline_summary_heads` із CAS на ревізію твору. Придатність обчислюється при кожному збиранні контексту з поточних блоків і вибраної пам'яті. Підсумок бере участь лише у відборі (переповнений запит); запит, що вміщається, не змінюється.

**Tech Stack:** Python 3.12, FastAPI, SQLite JSON payload, pydantic, pytest (підставний шлюз, без платних викликів).

**Spec:** `docs/superpowers/specs/2026-11/2026-11-12-timeline-summaries-design.md`

## Global Constraints

- `TIMELINE_WINDOW=20` (`memory/selection.py`) не змінюється; блок пласкої книги — 10 активних сцен; останній неповний блок підсумку не має.
- Межі тексту: 1200 символів для блоку, 2000 для частини, після `strip()`.
- Ключі блоків: `part:<part_id>`, `range:<first>-<last>`; до 1000 голів у творі.
- Запит без використаного підсумку — байт у байт той самий (MEMORY-SELECT І1); `projection_version` з підсумком — `memory-uk-v3-selected-summary`.
- Роль — `memory`; стадія `timeline_summary` у `MULTI_SCENE_STAGES`; MCP не змінюється.
- Міграції SQLite немає: старі payload читаються з порожнім словником голів.
- Тести — лише підставні шлюзи; приватні історії з `data/` не використовуються.

## Review Focus

1. Видалена/відновлена сцена всередині блоку зсуває номери: голова лишається, але `scene_ids` не збігаються → `blocks_changed`, у запит не йде (тест у Task 3).
2. Перебудова підсумку після тексту, зібраного зі старим: текст застаріває через селектор, навіть якщо стара версія не `stale` (Task 3).
3. Фінальне підрізання вилучає підсумок: записи блоку за вікном — у лічильнику, у вікні — відкинуті бюджетом, без подвійного рахунку (Task 3).
4. Подвійний запуск підсумку того самого блоку — відмова до черги (Task 4).
5. Структурована книга в `store`: PUT виправлення й POST запуску відхиляє запобіжник довгої прози (Task 5, обхід маршрутів).

---

### Task 1: Блоки, поле голів, вид версії

**Files:**
- Create: `src/storygen/memory/summary_blocks.py`
- Modify: `src/storygen/domain.py` (`VersionKind` + `timeline_summary`; `Story.timeline_summary_heads: dict[str,str] = Field(default_factory=dict,max_length=1000)`)
- Modify: `src/storygen/storage/repository.py::save_version` (`timeline_summary` — формат `json`)
- Test: `tests/memory/test_summary_blocks.py`

**Interfaces:**
- Produces: `SummaryBlock(key: str, title: str, scene_ids: tuple[str,...], first_number: int, last_number: int, part: bool)` (frozen dataclass); `summary_blocks(story, scenes) -> list[SummaryBlock]` (scenes — активні, у порядку); `BLOCK_SIZE=10`; `limit(block) -> int` (1200 / 2000); `recommended(block, last_memory_number: int) -> bool` = `block.first_number < last_memory_number + 1 - TIMELINE_WINDOW`; `replaces(block, scene_number: int) -> bool` = `first_number < scene_number - TIMELINE_WINDOW and last_number < scene_number`.

- [ ] Тести: 25 сцен пласкої книги → ключі `range:1-10`, `range:11-20`, без блоку 21–25; книга з двома частинами (BOOK-STRUCTURE) → `part:p1`, `part:p2` з назвами частин і номерами; частина без активних сцен блоку не має; `recommended` для 1–10: false при N_last=20, true при 21; `replaces` для 1–10: false для сцени 21, true для 22 і 23; для 11–20 true з 32; старий payload твору без поля читається з `{}`.
- [ ] Реалізація, прогін, коміт `feat(memory): timeline summary blocks and heads field`.

### Task 2: Збереження підсумку

**Files:**
- Create: `src/storygen/storage/timeline_summaries.py`
- Modify: `src/storygen/storage/integrity.py` (виклик перевірки голів), `src/storygen/storage/book_checks.py` або новий `storage/summary_checks.py`
- Test: `tests/storage/test_timeline_summaries.py`

**Interfaces:**
- Consumes: Task 1.
- Produces: `summary_payload(block, memory_version_id, text, origin, language) -> str` (JSON `{schema_version:1, block_key, scene_ids, memory_version_id, text, origin, language}`); `read_summary(view, version_id) -> dict`; `save_summary_version(repo, story_id, block, memory_ids: list[str], text, origin, language, previous_id=None, run_id=None) -> VersionRef` (`input_refs` = пам'ять кожної сцени блоку + попередня версія для `author`); `publish_summary(repo, story_id, block_key, version_id, expected_revision) -> Story` (CAS ревізії; версія цього твору, `kind=='timeline_summary'`, той самий `block_key`; попередня голова → `invalidate_in_transaction`); `save_author_summary(repo, story_id, block_key, text, expected_version_id, expected_revision) -> Story` (CAS і на ревізію, і на голову; ті самі `scene_ids`/`memory_version_id`; межа довжини й непорожність).
- Fsck: `summary_head_wrong_version` (corruption), коли голова вказує не на `timeline_summary` цього твору з тим самим ключем.

- [ ] Тести: публікація ставить голову й піднімає ревізію; застаріла ревізія → `RevisionConflict`, голова не змінилась; чужий ключ або вид → `ValueError`; нова голова робить застарілою версію, що мала стару голову серед `input_refs`; авторське виправлення — нова версія `origin='author'`, CAS на голову; зміна прози сцени блоку робить версію підсумку `stale` (ребро від пам'яті); fsck ловить голову на версію пам'яті.
- [ ] Реалізація, прогін, коміт `feat(storage): timeline summary versions and heads`.

### Task 3: Придатність і шар `summary` у відборі

**Files:**
- Create: `src/storygen/memory/summaries.py`
- Modify: `src/storygen/memory/selection.py`, `src/storygen/memory/projection.py::render_memory` (kwarg `summary_lines=()`, після рядка-лічильника), `src/storygen/generation/context.py` (вхід відбору, `refs`, метрики, селектор, попередження), `src/storygen/generation/context_labels.py` (рядки підсумку й попередження uk/en), `src/storygen/dependency_models.py` (поле `story/timeline_summary_heads`), `src/storygen/storage/snapshots.py::selector_value`
- Test: `tests/memory/test_summary_selection.py`, `tests/generation/test_context_summaries.py`

**Interfaces:**
- Consumes: Tasks 1–2.
- Produces: `SummaryCandidate(block_key, version_id, first_number, last_number, line)`; `usable_summaries(view, story, scenes, scene) -> tuple[list[SummaryCandidate], list[StaleSummary]]` (`StaleSummary(block_key, first_number, last_number, reason)`; причини `stale`, `blocks_changed`, `memory_changed`); `block_state(view, story, scenes, block) -> tuple[str, str|None]` (`none|fresh|stale`, причина) — його читає API.
- `SelectionInput.summaries: tuple[SummaryCandidate,...] = ()`, `SelectionInput.stale_summaries: tuple[StaleSummary,...] = ()`; `MemorySelection.summaries: tuple[tuple[str,str],...]` (ключ, версія), `MemorySelection.warnings: tuple[str,...]`.
- Відбір: кандидати — `replaces(block, n)`; шар `summary` після `facts`, перед `timeline`, від найпізнішого блоку; вибраний підсумок покриває номери блоку: такі записи хронології не беруться й не рахуються; вилучений фінальним підрізанням — записи блоку за вікном ідуть у лічильник, у вікні — `dropped['timeline']`. `LAYERS` отримує `summary`.
- Контекст: з вибраним підсумком — `refs += version_ids`, `projection_version='memory-uk-v3-selected-summary'`, `selection.summaries=[{block_key,version_id}]`, селектор `DependencySelector(kind='story', owner_id=story.id, field='timeline_summary_heads', expected={key: head})`; `selector_value` повертає `{key: heads.get(key, '')}` для ключів `expected`.
- Рядки: «Підсумок сцен A–B: …», «Підсумок частини «Назва» (сцени A–B): …»; en «Summary of scenes A–B: …», «Summary of part “Title” (scenes A–B): …». Попередження: «Підсумок сцен A–B застарів: перебудуйте його в панелі пам'яті» — для непридатної голови, чий блок мав невзяті записи.

- [ ] Тести (чисті, `test_summary_selection.py`): сцена 23 — підсумок 1–10 вибрано, жоден запис 1–10 не взято й не пораховано, записи 11+ як раніше; рендер: лічильник, далі підсумки, далі записи; без лічильника підсумки першими; тісний бюджет — пізніший блок береться першим, невміщений повертає записи; підрізання підсумку — рахунок без подвоєння.
- [ ] Тести (`test_context_summaries.py`, сцени з журналами пам'яті): запит, що вміщається, байт у байт той самий з головою підсумку; переповнений запит сцени 23 з придатним підсумком — рядок підсумку, `input_refs` містить версію, знімок має селектор, `compare_snapshot` після нової голови повертає зміну; сцена 21 — підсумок не береться; зміна прози сцени 5 — `stale`, попередження, підсумку немає; перестановка сцен — `blocks_changed`; запит без підсумку не має селектора.
- [ ] Реалізація, прогін разом із `tests/memory/test_selection.py tests/generation/test_context_selection.py tests/generation/test_memory_kind.py`, коміт `feat(memory): timeline summaries replace old blocks in selection`.

### Task 4: Запуск `timeline_summary`

**Files:**
- Create: `src/storygen/generation/timeline_summary.py`, `src/storygen/generation/resources/timeline_summary_{uk,en}_v1.txt`
- Modify: `run_models.py` (`mode` + `timeline_summary`, `summary_block_key: str|None` до 80 символів, валідатор: обов'язковий для цього режиму без `scene_id`, заборонений для інших), `language.py::PROMPTS`, `providers/policy.py` (`STAGE_POLICY_ROLE`, `MULTI_SCENE_STAGES`), `generation/worker.py` (завдання, подвійний запуск, гілка виконання, повідомлення збою), `generation/stages.py` (обробка відповіді), `generation/readiness.py` (`preview`, `pending_preview`), `providers/streaming.py` (назва ролі в повідомленні)
- Test: `tests/generation/test_timeline_summary_run.py`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces: `build_summary_context(repo, story_id, block_key) -> ContextBundle` (роль `memory` із `get_role_settings`; `enforce_edition_limit` для кожної сцени блоку; вхід — JSON `{story_title, part_title, scenes:[{number,title}], timeline:[«Сцена N: текст»]}` із записів хронології сцен блоку в пам'яті останньої сцени блоку; `input_refs` — пам'ять кожної сцени блоку; `fragments` — `summary_block_key`, `summary_scene_ids`, `summary_memory_id`, `summary_limit`; `ContextOverflow` як у пропозиції публікації); `readiness(repo, request) -> dict` (як `publication_metadata.readiness`); `validate_summary(text, limit, language) -> str` (порожній, задовгий, інша мова → `ValueError` з довіреним повідомленням; мова: для `uk` кириличних літер більше за латинські, для `en` навпаки); `finish_summary(repo, attempt, context, text, run_id)` у `stages.py`: версія `origin='model'` + `publish_summary`; `RevisionConflict` → версія без публікації, спроба `alternative`.
- Причини неготовності: блок неповний чи відсутній, сцена без пам'яті, застаріла пам'ять сцени.

- [ ] Тести: 12 сцен із пам'яттю → запуск із підставним шлюзом публікує голову `range:1-10`, версія `origin='model'`; відповідь 1300 символів — помилка без публікації; англійський текст в українському творі — помилка; зміна ревізії між збиранням і відповіддю — `alternative`, голова не змінилася; сцена без пам'яті — неготовність і відмова в черзі; другий запуск того самого блоку, поки перший у черзі, — `ValueError`; рейтинг запиту — найвищий серед сцен блоку (сцена з рейтингом 18+ посередині блоку в `store` → відмова); `STAGE_POLICY_ROLE['timeline_summary']=='memory'`.
- [ ] Реалізація, прогін разом із `tests/generation/test_publication_metadata.py tests/providers/test_model_policy.py`, коміт `feat(generation): timeline summary run`.

### Task 5: API

**Files:**
- Create: `src/storygen/web/routes_timeline_summaries.py`
- Modify: `src/storygen/web/app.py` (підключення)
- Test: `tests/web/test_timeline_summaries_api.py`

**Interfaces:**
- `GET /api/stories/{story_id}/timeline-summaries` → `{story_revision, blocks:[{key,title,first_number,last_number,state,reason,recommended,ready,ready_reason,text,version_id,origin}]}`.
- `GET /api/stories/{story_id}/timeline-summaries/readiness?block_key=` → як `/publication-suggestions/readiness`.
- `PUT /api/stories/{story_id}/timeline-summaries/{block_key}` `{text, expected_version_id, expected_revision}` → `save_author_summary`; 409 на конфлікт.

- [ ] Тести: список для 25 сцен (стани, рекомендація після пам'яті сцени 21); PUT із застарілою ревізією → 409; PUT задовгого тексту → 400; обхід маршрутів запобіжника довгої прози проходить (PUT під перевіркою).
- [ ] Реалізація, прогін разом із `tests/web/test_long_prose_guard.py`, коміт `feat(web): timeline summaries API`.
