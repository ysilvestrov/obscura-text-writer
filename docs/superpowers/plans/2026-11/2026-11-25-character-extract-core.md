# R-51 PR 1 — ядро пошуку персонажів у прозі: план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Запуск `character_extract` читає прозу книги групами сцен роллю «Пам'ять», складає пропозицію карток, імен, героя й складу сцен, а API й MCP дають її переглянути й прийняти поштучно.

**Architecture:** Чиста логіка (групи, нормалізація цитат, обробка відповіді, збирання пропозиції) — у `characters/extract.py` без IO. Виклик моделі — новий етап `character_extract` через чинний `execute_stage` (облік витрат, бюджет, політика). Багатокроковий запуск із контрольною точкою — `generation/extract_run.py` за зразком `generation/audit_run.py`. Прийняття — одна транзакція: нова версія карток через чинне збереження і `apply_cast` з режимом `add`.

**Tech Stack:** Python 3.12, FastAPI, pydantic, SQLite, pytest; MCP-міст `src/storygen/mcp/bridge.py`.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-25-character-extract-design.md` (затверджено злиттям #324, відповідь власника — без обмеження видання).

## Global Constraints

- Шляхи коду — від `src/storygen/` (далі без префікса); тести — `tests/`.
- `group_words`: ціле 1000–20000, типово 5000.
- `catalogue_reserve = min(5 % max_input_chars, 4 000)` символів.
- `extract_output_tokens = min(max(role.max_output_tokens, 16000), context_tokens − input_tokens)`, де `input_tokens` — `token_budget.service.token_estimate(...)['input_tokens']` справжнього запиту; менше за `role.max_output_tokens` → поділ групи / пропуск сцени. Межа вартості рахує `max(role.max_output_tokens, 16000)`.
- Температура виконавця 0,2; провайдер, `max_input_chars`, `context_tokens` — ролі «Пам'ять»; без ролі «Пам'ять» — відмова «Налаштуйте роль «Пам'ять»: пошук персонажів читає прозу її моделлю».
- `calls_bound = 2 × groups + 2`; запуск ніколи не робить більше викликів, і після продовження теж.
- Нова картка: `name` ≤ 80 символів, `other_names` ≤ 10 по ≤ 80, `quotes` 1–2 по ≤ 300; кандидатів героя ≤ 3 на групу, `score` 0–1; герой — найвища сума ≥ 1,0.
- Нормалізація цитат: NFC; пробіли згорнуто; тире `‐‑‒–—―−-` → `-`; апострофи `’ʼ'\`` → `'`; лапки `«»„“”"` → `"`; обрізати по краях пробіли, `.`, `"`, `…`; без регістру. Зберігається відповідний уривок ОРИГІНАЛЬНОЇ прози сцени.
- Читаються активні сцени в порядку читання з головою прози `manual` або `edited`, завершеною; склад пропонується лише сценам із `manual` без рядка учасників у плані.
- Сповіщення-константи (дослівно): `EXTRACT_PLAN_CHANGED = 'План змінився; перегляньте знову'`, `EXTRACT_RUNNING = 'Пошук персонажів уже виконується'`, `EXTRACT_PROSE_CHANGED = 'Проза змінилася; запустіть пошук знову'`, `PROPOSAL_SUPERSEDED = 'Є новіша пропозиція'`, `NO_MEMORY_ROLE` (текст вище), причини пропуску: `'не вміщується в ліміт входу ролі «Пам'ять»'`, `'не вміщується в контекст ролі «Пам'ять»'`, `'модель не дала відповіді'`, `'вичерпано запас викликів'`, `'картка з таким іменем уже є'`.
- Запуск дозволено в обох режимах написання; без обмеження видання.
- Мова документації українська; SPEC.MD і traceability — в тому самому PR; `python scripts/check_docs.py` зелений.
- Коміти закінчуються рядком `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Поправка до спеки, яку вносить цей план (Task 8)

- **Пропозиція живе в `Run.checkpoint['proposal']`**, а не в `StageAttempt.context`: запуск багатокроковий, часткова пропозиція після скасування не має власного виклику. API й MCP ідентифікують пропозицію `run_id` замість `attempt_id`. Позначка прийняття — `Run.checkpoint['accepted_at']`.
- **`CHARACTERS` у §7 спеки** — неіснуючий Requirement: оновлюються `CHARACTER-IMPORT` (походження `model`, джерела з прози, правило залежностей) і `CHARACTER-TIME` (доступність кожної цитати від своєї сцени).

## Review Focus

1. **Цитата з кількох абзаців / з `**` емфазою Markdown у прозі** — звірка після нормалізації має знаходити її й повертати точний оригінальний уривок, що проходить чинну перевірку `quote in text` (тест у Task 2).
2. **Сцену вилучено або прозу змінено між запуском і прийняттям** — пункт пропускається з причиною, решта застосовується (Task 6).
3. **Автор видалив наявну картку, яку пропозиція ставить у склад** — учасник вилучається з пункту до `apply_cast`, прийняття не падає (Task 6).
4. **Продовження після паузи, коли непрочитана сцена змінилася** — 409 `EXTRACT_PROSE_CHANGED`; прочитані сцени не блокують (Task 5).
5. **Модель повертає `{}` / порожні списки / відомий ID картки як `key` нової** — запуск не падає, нічого не пропонується з порожнього (Task 2).

---

### Task 1: Походження `model` і цитати з прози в картках

**Files:**
- Modify: `characters/models.py` (`CharacterEntry.origin`), `characters/service.py` (`_normalize`, `save_character_material`), `storage/character_checks.py`, `authoring/blueprints.py:64`
- Test: `tests/characters/test_model_origin.py`

**Interfaces:**
- Produces: `CharacterEntry.origin: Literal['imported','author','model']`; `characters.service.CARD_SOURCE_KINDS = frozenset({'source_characters','source_plan','character_cards','manual','edited'})`; `_normalize` повертає `refs` БЕЗ версій прози (`manual`/`edited`); `characters.service.save_cards_in_transaction(repo, db, story_id, cards_payload, expected_revision) -> VersionRef` — транзакційне ядро `save_character_material`, яке Task 6 викликає всередині своєї транзакції (сам `save_character_material` стає обгорткою).

- [ ] Step 1: тести:
  - `test_model_entry_needs_no_sources` — `CharacterEntry(id='e',text='Інше ім\'я: Іва',origin='model')` валідна.
  - `test_prose_quote_source_saves` — картка з відомістю `model`, джерело — завершена версія `manual` сцени того самого твору, цитата — підрядок; збереження проходить, `refs` збереженої версії карток не містить ID прози.
  - `test_prose_edit_does_not_stale_cards` — після збереження нової прози сцени версія карток не `stale`.
  - `test_foreign_story_prose_rejected` і `test_incomplete_prose_rejected` — `ValueError('Невірне джерело відомості персонажа')`.
  - `test_integrity_accepts_prose_sources` — `check_character_versions` не додає `invalid_characters` для такої картки.
  - `test_old_version_without_model_loads` — наявні картки без `model` читаються як раніше.
- [ ] Step 2: запустити — FAIL.
- [ ] Step 3: реалізувати; `blueprints.py:64` — лише розширити набір видів (імпорт задуму джерел прози не створює).
- [ ] Step 4: `pytest tests/characters -q` — PASS; `pytest tests/storage -q -k character` — PASS.
- [ ] Step 5: коміт.

### Task 2: Чиста логіка пошуку — `characters/extract.py`

**Files:**
- Create: `characters/extract.py`
- Test: `tests/characters/test_extract.py` (фікстури-відповіді з проби в `tests/characters/data/extract_*.json`: валідна, з вигаданим ID сцени, з дублем «Анничка», з цитатою іншої сцени, з описом «стара», `{}`)

**Interfaces:**
- Produces (усе чисте, без IO):
  - `normalize_with_map(text: str) -> tuple[str, list[int]]` — нормалізований текст і для кожного його символу позиція в оригіналі.
  - `find_quote(scenes: list[SceneProse], quote: str) -> QuoteHit | None`; `SceneProse(scene_id, version_id, text)`, `QuoteHit(scene_id, version_id, quote)` — `quote` = точний оригінальний уривок; цитата через межу сцен → `None`.
  - `plan_groups(scenes: list[tuple[str,int,int]], group_words: int, fits: Callable[[list[str]], bool]) -> tuple[list[list[str]], list[tuple[str,str]]]` — вхід `(scene_id, words, chars)`; жадібно до бюджету; група, що не `fits`, ділиться навпіл; одна сцена, що не `fits` → у пропущені з причиною.
  - `ExtractResponse` (pydantic, `extra='ignore'`) з полями контракту §3.3 спеки й лімітами з Global Constraints; `parse_extract(text: str) -> ExtractResponse` через `model_json.unwrap_model_json`; невалідне → `ValueError`.
  - `ExtractState` (pydantic): `catalogue: list[CatalogueCard]` (`ref`, `name`, `names`, `existing: bool`, `quotes`, `first_scene_id`), `casts: dict[scene_id, list[ref]]`, `scores: dict[ref,float]`, `skipped: list[tuple[str,str]]`, `groups_done: int`, `calls: int`. `ref` — ID наявної картки або `key` нової (`new1`, `new2`… — призначає сервер, не модель).
  - `catalogue_text(state) -> str` і `short_ids(state, group_scene_ids) -> tuple[dict[str,str], dict[str,str]]` — відповідність `c<N>`/`s<N>` ↔ ref/scene_id (номер сцени — серед прочитаних у книзі).
  - `apply_group(state, response, group: list[SceneProse], scene_numbers, card_numbers) -> ExtractState` — правила §3.4 спеки: цитати через `find_quote`, картка без цитати відкидається, ім'я перевіряється `memory.selection.MentionIndex`/`name_stems` у прозі групи, ім'я з малої літери → `suggested=False`, дубль за `scene_description.name_key` зливається як імена (цитати дубля відкидаються), невідомі ID відкидаються.
  - `finalize(state, scenes_meta, has_author_protagonist: bool) -> dict` — пропозиція §4.1 (без `fingerprint`, без `source`): герой (сума ≥ 1,0, три найкращі в `scores`), `casts` з `mode` `set`/`add` лише для сцен, що `scenes_meta[scene_id].cast_eligible`, пропуск сцен без змін.
- [ ] Step 1: тести, по одному на правило: `test_normalized_quote_maps_to_original_span` (тире, апострофи, `**`, перенос рядка), `test_quote_across_scenes_rejected`, `test_groups_whole_scenes_to_budget`, `test_oversized_scene_own_group`, `test_unfit_group_splits_then_skips`, `test_card_without_verbatim_quote_dropped`, `test_alias_absent_from_prose_dropped`, `test_lowercase_alias_unsuggested`, `test_duplicate_by_name_merges_as_names`, `test_invented_scene_id_dropped`, `test_empty_object_is_noop`, `test_protagonist_threshold_and_author_marker`, `test_cast_set_vs_add_and_ineligible`.
- [ ] Step 2: FAIL. Step 3: реалізувати. Step 4: `pytest tests/characters/test_extract.py -q` — PASS. Step 5: коміт.

### Task 3: Етап `character_extract` — налаштування виконавця, промпт, контекст, виклик

**Files:**
- Create: `generation/extract_context.py`, `prompts/character_extract.uk.md`, `prompts/character_extract.en.md` (або чинне місце вбудованих промптів — як у `audit_context.py`)
- Modify: `roles.py` (`STAGE_ROLE['character_extract']='memory'`), `providers/policy.py` (`STAGE_POLICY_ROLE`), `providers/requests.py:70` (structured, схема `ExtractResponse`), `broken_text.stage_category`, `generation/stages.py` (гілка: `attempt.context['extract_response']=parse_extract(text).model_dump()`; помилка розбору → `failed` з повідомленням)
- Test: `tests/generation/test_extract_context.py`

**Interfaces:**
- Consumes: `ExtractResponse`, `parse_extract`, `catalogue_text`, `short_ids` (Task 2).
- Produces:
  - `resolve_extractor(roles: dict[str,RoleSettings]) -> RoleSettings | None` — копія ролі `memory` з `temperature=0.2`, `max_output_tokens=max(role,16000)`; `None` без ролі.
  - `build_extract_context(repo, story_id, settings, state, group: list[SceneProse], scene_numbers, card_numbers) -> ContextBundle | str` — `str` — причина, коли не вміщується (`input chars > max_input_chars` → причина входу; `context_tokens − input_tokens < role.max_output_tokens` → причина контексту); інакше `settings.max_output_tokens` звужено до `extract_output_tokens`. Вимір — `token_estimate`, як `audit_context.build_audit_context`. `scene_id` бандла — перша сцена групи; `policy_role='memory'`.
  - Промпт мовою твору; правила — як у `docs/superpowers/specs/2026-11/2026-11-25-character-extract-probe/probe2.py` `SYSTEM`, плюс ліміти полів.
- [ ] Step 1: тести: `test_extractor_borrows_memory_role`, `test_no_memory_role_is_none`, `test_output_limit_capped_by_context`, `test_unfit_input_returns_reason`, `test_stage_parses_response_into_attempt` (фейковий gateway → `attempt.context['extract_response']`), `test_unparseable_response_fails_attempt`, `test_empty_stop_fails_attempt`.
- [ ] Step 2–4: FAIL → реалізувати → `pytest tests/generation/test_extract_context.py tests/providers -q` PASS. Step 5: коміт.

### Task 4: Перегляд, відбиток, режим запуску

**Files:**
- Create: `characters/extract_plan.py`
- Modify: `run_models.py` (`mode` + `'character_extract'`; поля `group_words: int | None = Field(default=None, ge=1000, le=20000)`, `extract_plan_fingerprint: str | None` з тим самим pattern; валідатори: поля лише для цього режиму, `scene_id is None`), `generation/worker.py` (`enqueue`: guard одного активного → `RevisionConflict(EXTRACT_RUNNING)`; порівняння відбитка → `RevisionConflict(EXTRACT_PLAN_CHANGED)`; `tasks=[]`), `generation/readiness.py` (`preview`/`pending_preview` гілки), `web/routes_characters.py` (`POST /api/stories/{id}/character-extract/preview`)
- Test: `tests/characters/test_extract_plan.py`, `tests/web/test_character_extract_routes.py`

**Interfaces:**
- Consumes: `plan_groups` (Task 2), `resolve_extractor`, `build_extract_context` для `fits` (Task 3), `audit_cost.upper_bound`.
- Produces: `extract_plan(repo, story_id, group_words=5000) -> dict` з ключами `ready, reason, groups: list[list[scene_id]], scenes_count, skipped: list[{scene_id,reason}], calls_bound, cost: {per_call_usd,total_usd,reason}, cards_count, has_protagonist, pending_proposal: bool, plan_fingerprint`; відбиток — sha256 канонічного JSON зі складників §3.6 спеки. Без хмарного ліміту бюджету — `ready=False` з чинним повідомленням бюджету (як `readiness` інших запусків).
- [ ] Step 1: тести: `test_preview_counts_groups_calls_cost`, `test_preview_skips_scenes_without_prose`, `test_preview_without_memory_role_refuses`, `test_fingerprint_changes_with_prose_cards_tariff_budget`, `test_enqueue_stale_fingerprint_409`, `test_second_active_run_409`, `test_paused_run_does_not_block`, `test_preview_route_writes_nothing`, `test_allowed_in_chat_writing_mode`.
- [ ] Step 2–4. Step 5: коміт.

### Task 5: Виконання запуску — `generation/extract_run.py`

**Files:**
- Create: `generation/extract_run.py`
- Modify: `generation/worker.py` (`_execute` диспетчер; `resume`: гілка для цього режиму без вимоги `repeat_interrupted` для незавершеного виклику групи — група повторюється в межах `calls_bound`; `recover_interrupted` — як для audit)
- Test: `tests/generation/test_extract_run.py` (фейковий gateway `Answers` з `tests/generation/test_audit_run.py`, `drive(...)`)

**Interfaces:**
- Consumes: Tasks 2–4.
- Produces: `execute(coordinator, run_id) -> None`. `Run.checkpoint = {'phase':'reading','state': ExtractState.model_dump(), 'pending': [[scene_id,…],…], 'source': {scene_id: {version_id, sha256}}, 'start_cards_version_id', 'group_words', 'calls_bound'}`; після завершення/скасування/вичерпання — `{'phase':'done','proposal': {...§4.1, 'source','partial','calls','cost_usd','fingerprint'}}`.
- Поведінка (дослівно спека §3.4, §3.7): збій виклику → повтор групи 1 раз → поділ навпіл → одна сцена → пропуск `'модель не дала відповіді'`; група не вміщується з поточним каталогом → поділ; `calls == calls_bound` з рештою груп → `completed` з `partial=True` і пропуском решти `'вичерпано запас викликів'`; помилка провайдера/бюджету (`ValueError` з `execute_stage`, не збій розбору) → `failed`, продовжуване; скасування → `cancelled` з частковою пропозицією; пауза → `paused`; продовження перевіряє sha256 прози непрочитаних сцен → інакше `RevisionConflict(EXTRACT_PROSE_CHANGED)`.
- [ ] Step 1: тести: `test_reads_groups_in_order_with_catalogue` (другий запит містить картку першої групи як `c1`), `test_retry_then_split_then_skip`, `test_calls_never_exceed_bound`, `test_bound_exhausted_completes_partial`, `test_cancel_publishes_partial`, `test_pause_resume_continues_next_group`, `test_resume_after_unread_prose_change_409`, `test_provider_error_fails_resumable`, `test_proposal_fingerprint_stable`.
- [ ] Step 2–4. Step 5: коміт.

### Task 6: Пропозиція й прийняття

**Files:**
- Create: `characters/extract_accept.py`
- Modify: `storage/scene_cast.py` (`apply_cast(..., mode='set')` → `mode: Literal['set','add']`; `add` дописує відсутніх у кінець непорожнього складу, решта умов незмінна; приймає `db` для виклику всередині чужої транзакції — `apply_cast_in_transaction(repo, db, story_id, proposal, mode)`), `web/routes_characters.py` (`GET /api/stories/{id}/character-proposal`, `POST /api/stories/{id}/character-proposal/accept`)
- Test: `tests/characters/test_extract_accept.py`, доповнити `tests/web/test_character_extract_routes.py`

**Interfaces:**
- Consumes: `save_cards_in_transaction` (Task 1), proposal (Task 5).
- Produces:
  - `current_proposal(repo, story_id) -> dict | None` — останній `character_extract` запуск книги в стані `completed`/`cancelled` з `phase=='done'`, не прийнятий, і лише якщо після нього не створено жодного іншого запуску `character_extract` цієї книги (у будь-якому стані): новіший запуск робить його неприйнятним (`PROPOSAL_SUPERSEDED`).
  - `AcceptRequest` (pydantic): `run_id, fingerprint, cards: list[{key, names: list[str]}], name_updates: list[{card_id, names}], protagonist: bool, casts: list[scene_id], dry_run: bool=False`.
  - `accept_proposal(repo, story_id, request) -> dict` — `{applied, skipped: [{item, reason}], changed_card_ids, changed_scene_ids, stale_memory_scenes}`; правила §4.3 спеки + Task 8 поправка; `dry_run` — та сама транзакція з відкатом; одна транзакція: картки (CAS ревізії твору), склад, `checkpoint['accepted_at']`. Кожна цитата нової картки — окрема відомість `from_scene` своєї сцени (неактивна сцена → відомість пропускається); «Інше ім'я: …» і «Головний герой» — `timeless`, без джерел.
  - `stale_memory_scenes` — сцени, яким зміниться склад і які мають чинну пам'ять.
- [ ] Step 1: тести: `test_accept_selected_items_only`, `test_quote_entries_per_scene_availability`, `test_new_card_name_taken_skipped`, `test_removed_existing_card_dropped_from_cast`, `test_rejected_new_card_dropped_from_cast`, `test_prose_changed_scene_cast_skipped`, `test_add_mode_appends_missing_only`, `test_set_on_nonempty_applies_as_add`, `test_protagonist_skipped_when_author_marked`, `test_dry_run_writes_nothing_counts_stale_memory`, `test_second_accept_409`, `test_newer_run_supersedes_409`, `test_wrong_fingerprint_409`, `test_saved_cards_pass_raw_quote_check_on_next_save`.
- [ ] Step 2–4. Step 5: коміт.

### Task 7: MCP

**Files:**
- Modify: `mcp/bridge.py` (`RUN_ACTIONS` + `'character_extract'`; `start_run(..., group_words=None)` — перегляд через `POST …/character-extract/preview`, confirm з `plan_fingerprint`, без перевірки режиму написання; `get_run` — блок `character_extract: {checkpoint phase, groups_done, proposal}` з `GET …/character-proposal`; новий інструмент `accept_character_proposal(story_id, run_id, fingerprint, cards=[], name_updates=[], protagonist=False, casts=[], confirm=False)`; `TOOLS` 30), `web/bridge_marker.py` (`BRIDGE_RUN_MODES` + режим, без вимоги режиму obscura, з вимогою відбитка), інструкції сервера (речення про пошук персонажів перед побудовою пам'яті), `integrations/**/start-story` скіл — сценарій «є готовий рукопис»
- Test: `tests/mcp/test_bridge_character_extract.py`, `tests/test_codex_skills.py:134` → 30

**Interfaces:** Consumes Tasks 4–6 routes.

- [ ] Step 1: тести: `test_start_run_preview_then_confirm`, `test_confirm_without_fingerprint_refused`, `test_chat_mode_story_allowed`, `test_get_run_reports_proposal`, `test_accept_tool_preview_then_confirm`, кількість інструментів 30.
- [ ] Step 2–4. Step 5: коміт.

### Task 8: SPEC, traceability, поправка спеки, сайт MCP

**Files:**
- Modify: `SPEC.MD` (новий `### Requirement: CHARACTER-EXTRACT` з S01–S10 за §7 спеки; `CHARACTER-IMPORT`, `CHARACTER-TIME`, `MANUSCRIPT-IMPORT` — правила з Task 1/6; TOC), `docs/verification/traceability.json` (S01–S10 → тести Tasks 1–7), специфікація — розділ «Поправка 1 (реалізація PR 1)» з двома пунктами з початку цього плану і статус «затверджено 2026-11-25; поправка 1 — на погодження власника», `docs/site/{uk,en}/mcp.md` (30 інструментів, `accept_character_proposal`, дія `character_extract`) + `python scripts/check_site.py --rehash mcp`
- [ ] Step 1: внести; Step 2: `python scripts/check_docs.py` — PASS; Step 3: коміт.

Сторінки сайту `characters`, `memory`, `manuscript-import` і знімок — у PR 2 (обв'язка), бо там з'являється інтерфейс.
