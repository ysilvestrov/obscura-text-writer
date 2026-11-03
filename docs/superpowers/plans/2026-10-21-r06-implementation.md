# R-06 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Власник 21.10.2026 прямо дозволив реалізацію в цій сесії після підготовки плану без додаткового підтвердження.

**Goal:** Побудувати пам’ять лише вперед, з доказовою історією та компактним поточним станом, і захистити сцени від майбутніх розмічених відомостей персонажів.

**Architecture:** Незмінний memory-журнал має чисті loader/validator/reducer і дві детерміновані проєкції. Generation і ручний API використовують captured префікс і R-05 publication guards. Окрема авторська модель відомостей персонажів додає доступність за stable scene ID й неблокувальні попередження для нерозміченого тексту.

**Tech Stack:** Наявні Python 3.10+, Pydantic, SQLite WAL, FastAPI, Jinja, ES modules, pytest і Node; нових залежностей немає.

**Spec:** [Погоджена R-06](../../specs/changes/R-06-memory-v2.md), підтверджена власником 21.10.2026. Чинна реалізована архітектура — [SPEC.MD](../../../SPEC.MD).

## Global Constraints

- Поточна папка/гілка. Чужі dirty branding/publication/UI та попереднє виправлення діагностики worker не відкотувати й не включати в коміти R-06.
- Три послідовні частини a→b→c, кожна має чинний SPEC і локальний коміт.
- M[0] порожня; M[n] = apply(M[n−1], операції прози n); письменник n читає M[n−1].
- Немає summaries, прихованого clipping, inference retry/fallback, нових провайдерів чи зміни R-07/R-12.
- До 12 операцій і до 3 add на категорію. Update/retire лише активних станів/ліній; facts/timeline незмінні.
- Legacy immutable bytes і user_version=2 збережені. Міграція під час читання не змінює freshness.
- Scope: персонажі сцени + загальні стани; порожній cast означає всі чинні стани.
- Немає авторських data-dir, зовнішніх моделей/витрат або перезапуску користувацького сервера для offline-приймання.
- RED→GREEN на предметних регресіях; повний pytest послідовно на коротких різних basetemp.
- Після всіх частин — окремий підбір Venice Evaluator; історичний бюджет не є новим необмеженим дозволом на витрати.

## Review Focus

1. Повтор ранньої сцени після завершення всіх сцен не підхоплює її власну або пізнішу пам’ять — Tasks 2/6.
2. Legacy snapshot після v2 не стирає retired/superseded історію — Tasks 3/4/5.
3. Точна цитата майбутньої сцени не обходить source prefix — Tasks 2/5/6.
4. Порожній результат фільтрації карток не спричиняє fallback до повного опису — Tasks 7/8.
5. Historical stale після reorder не називається пошкодженням; чужий temporal anchor та lost warning після reload виявляються — Tasks 5/8/10.

## Карта файлів

- `memory/models.py`: старі wire-моделі лишаються сумісними.
- Нові `memory/journal.py`, `memory/projection.py`: чисті v2-моделі, loader/replay/операції та текст/каталог/метрики; без repo/SQL/generation imports.
- `memory/service.py`: читання префікса, legacy wrapper, валідація джерел і rebuild.
- `generation/context.py`, `stages.py`, `prompts.py`, memory resources, `providers/models.py`, `streaming.py`: compact input, frozen дані та новий протокол.
- `web/routes_versions.py`: ручне збереження через той самий валідатор.
- Нові `characters/models.py`, `projection.py`, `service.py`: сумісне читання карток, часова проєкція, авторські зміни.
- Нові `web/routes_characters.py`, `web/static/characters.js`; існуючі app/template/context/readiness/runs: API/UI й warnings.
- `storage/integrity.py`, `storage/snapshots.py`, `dependency_models.py`: перевірки історії та фактично використаного scope; storage не імпортує generation.

## R-06a — Компактна проєкція

### Task 1: Канонічний loader і чиста проєкція

**Files:** Create `memory/journal.py`, `memory/projection.py`, `tests/memory/test_journal.py`, `test_projection.py`; retain `memory/models.py` legacy types.

**Interfaces:** `MemoryEvent`, `MemoryJournal(schema_version=2, source_prose_ids, events)`; `load_memory(raw: str) -> MemoryJournal`; `replay_memory(journal) -> dict[str, MemoryEvent]`; `legacy_view(journal) -> MemorySnapshot`; `project_memory(journal, character_ids: list[str], source_scene_numbers: dict[str,int]) -> MemoryProjection(text, metrics)`; `memory_catalog(journal) -> str`.

- [x] RED tests: same v1 bytes twice produce identical IDs; copying a v1 prefix preserves IDs; duplicate events/invalid operation chains reject. Projection assertion: `assert quote not in result.text` and `assert 'source_version_id' not in result.text`, preserving claim text.
- [x] Run `python -m pytest tests/memory/test_journal.py tests/memory/test_projection.py -q --basetemp=.pytest-tmp/r6-1`; expect missing new API.
- [x] Implement chronological v1 conversion and deterministic IDs, strict v2 model/replay, active/retired state, category/scope immutability. Existing `MemorySnapshot` stays legacy wire model. Projection uses selected active states, all facts/timeline/open threads and closure reasons; no technical metadata.
- [x] GREEN same command. Test global/selected/empty cast and old global states; identical source data gives identical text/metrics. No source excerpt is silently truncated.

### Task 2: Prefix reader и compact generation context

**Files:** Modify `memory/service.py`, `generation/context.py`; create `tests/memory/test_prefix.py`; extend `tests/generation/test_context.py`.

**Interfaces:** `journal_before(repo, scene_id: str) -> MemoryJournal`; legacy `memory_before(...) -> MemorySnapshot` delegates to `legacy_view(journal_before(...))`. `ContextBundle.memory_metrics: dict` defaults empty; `ContextOverflow` includes optional memory contribution without breaking old callers.

- [x] RED: seven completed scenes; rebuilding draft/brief scene2 uses only memory scene1. Assert later sentinel absent, scene1 claim present, old refs preserved. Forged exact quote from scene5 in memory scene1 rejects.
- [x] Run `python -m pytest tests/memory/test_prefix.py tests/generation/test_context.py -q --basetemp=.pytest-tmp/r6-2`; expect raw JSON/projection failure.
- [x] Implement captured-view prefix validation and compact section for brief/draft/prose-edit. Memory/snapshot stage keeps legacy wire until Task4. patches stage unchanged. Record journal/projection counts and chars, projection version, fingerprint actual text; total budget checked after rendering.
- [x] GREEN same command plus `tests/generation/test_stale_memory_provenance.py`. Assert future plan edit does not alter memory input; oversized compact input fails before gateway with actual contribution.
- [x] Update SPEC CONTEXT-002/A5/A6 and relevant test matrix as implemented; full suite `python -m pytest -q --basetemp=.pytest-tmp/r6-a`; commit only R-06a files and own SPEC hunks: `feat: project verified prefix memory into compact story context`.

## R-06b — Журнал та операції

### Task 3: Доказовий delta reducer

**Files:** Modify `memory/journal.py`; create `tests/memory/test_operations.py`.

**Interfaces:** `MemoryOperation`, `MemoryOperations(schema_version=2, operations)`; `apply_operations(previous, delta, prose_id: str, prose: str, allowed_character_ids: list[str]) -> MemoryJournal`; `merge_legacy_delta(previous, delta: MemoryDelta, prose_id, prose) -> MemoryJournal`; `merge_legacy_snapshot(previous, snapshot: MemorySnapshot, prose_id, prose) -> MemoryJournal`.

- [x] RED: add state then update then retire over three prose sources. Assert same claim ID, three evidence-backed events, only current state before retire and none afterward. Reject immutable update, unknown/retired target, duplicate target, unknown scope/evidence, >12 ops and >3 add/category.
- [x] Run `python -m pytest tests/memory/test_operations.py -q --basetemp=.pytest-tmp/r6-3`; expect missing reducer.
- [x] Implement pure atomic reduction. Source quote/ID assigned by server; evidence fragmentation uses shared pure helper (extract existing fragment algorithm to a neutral module if needed, re-export `generation.evidence` APIs). No partial mutation of caller data.
- [x] GREEN same command. Legacy adapters preserve complete prior log and exact multiplicity of prior active entries; a valid old delta adds only, malformed v2 never falls back.

### Task 4: Модельний протокол і налаштування

**Files:** Modify `generation/context.py`, `stages.py`, `prompts.py`, memory prompt resources, `providers/models.py`, `providers/streaming.py`, `authoring/blueprints.py`, `web/static/settings.js`; extend `tests/generation/test_evidence_protocols.py`, `tests/web/test_evidence_settings.py`.

**Interfaces:** `parse_memory_result(raw, previous, prose_id, prose, mode, allowed_character_ids) -> MemoryJournal` in `memory/journal.py`; frozen `fragments.previous_memory` canonical JSON and `fragments.memory_allowed_character_ids` JSON. Memory input displays catalog, not old proof log. Default new `RoleSettings.memory_mode='evidence_delta'`; persisted missing legacy value resolves `snapshot` in saved-settings loader.

- [x] RED: v2 operations response publishes full journal, legacy wire responses work after a retired claim. Assert prompt has active claim IDs but not old quote or previous source IDs. Assert old saved missing mode remains snapshot; new role uses evidence_delta.
- [x] Run `python -m pytest tests/generation/test_evidence_protocols.py tests/web/test_evidence_settings.py -q --basetemp=.pytest-tmp/r6-4`.
- [x] Implement versioned v2 prompt/schema and frozen scope; preserve legacy snapshot prompt with active proof view. Stage verifies captured prefix/prose, not concurrent heads; supported legacy parser selected by explicit valid shape. Keep custom prompts as stored; label snapshot deprecated in UI.
- [x] GREEN same command and `tests/generation/test_publication_snapshot.py`. Extend memory dependency selectors only when allowed scope is actually passed; no new cards/future plan dependency.

### Task 5: Ручна пам’ять і maintenance

**Files:** Modify `memory/service.py`, `web/routes_versions.py`, `storage/integrity.py`; extend `tests/web/test_memory_save_regression.py`, `tests/storage/test_integrity.py`, `test_backup.py`; create `tests/memory/test_manual_journal.py`.

**Interfaces:** `validate_memory_journal(journal, source_versions: dict[str,str], previous: MemoryJournal | None=None) -> MemoryJournal`; `save_scene_memory(repo,scene_id,text,expected_revision) -> VersionRef` in memory service. API response remains compatible Scene. Fsck uses pure validator only, never migrating Repository.

- [x] RED: manual v1/v2 preserve previous-scene events; current-scene suffix may be corrected in a new version; future-source quote rejects; stale revision returns409 without altering head/buffer.
- [x] Run `python -m pytest tests/memory/test_manual_journal.py tests/web/test_memory_save_regression.py tests/storage/test_integrity.py tests/storage/test_backup.py -q --basetemp=.pytest-tmp/r6-5`.
- [x] Implement common normalization/validation and full v2 save. Fsck checks historical snapshot against captured order if present, not current heads; unverifiable legacy historical order is a report limitation, not fabricated corruption. Current memory consumption always validates exact active prefix. Add backward-compatible `IntegrityReport.limitations=[]` if needed for this distinction.
- [x] GREEN same command. Cold mixed v1/v2 backup/restore preserves all bytes/hashes and log. Corrupt sequence/source/citation gives specific issues; current-head changes alone give stale rather than corrupted immutable history.

### Task 6: Масштаб, гонки та приймання b

**Files:** Create `tests/integration/test_memory_v2_flow.py`; extend `tests/generation/test_publication_snapshot.py`, `tests/storage/test_freshness.py`; update SPEC/runbook/progress.

**Interfaces:** Synthetic chain fixture `build_chain(repo, count: int)` contains repeated state changes, closure, long evidence, selected cast and deterministic fake responses. No network factories.

- [x] RED integration cases for 7/15 scenes and scene2 regeneration after completion; assert unique event IDs and prefix counts, no future sentinel, log/replay equality, projection ≤ half legacy proof JSON for this fixture. Measure journal/catalog/projection/whole request separately.
- [x] Run `python -m pytest tests/integration/test_memory_v2_flow.py tests/generation/test_publication_snapshot.py tests/storage/test_freshness.py -q --basetemp=.pytest-tmp/r6-6`.
- [x] Resolve protocol integration failures without relaxing evidence or R-05 CAS. Include changed prose/previous memory/cast during inference → alternative; future plan edits → completed; acceptance baseline changes stale memory; exact A→B→A freshness preserved.
- [x] GREEN, update SPEC MEMORY-001/002/new journal/scope requirements and A2/A5/A6; full suite `python -m pytest -q --basetemp=.pytest-tmp/r6-b`; commit own files/hunks: `feat: update story memory through evidence backed journal operations`.

## R-06c — Часова доступність персонажів

### Task 7: Сумісні картки і чиста часова проєкція

**Files:** Create `characters/__init__.py`, `characters/models.py`, `characters/projection.py`, `tests/characters/test_character_models.py`, `test_projection.py`.

**Interfaces:** `CharacterCitation`, `CharacterEntry(id,text,availability,available_from_scene_id,origin,sources)`, `CharacterRecord(schema_version=2,id,name,entries)`; `load_characters(raw: str) -> list[CharacterRecord]`; `project_characters(cards, scenes: list[Scene], scene_id: str) -> CharacterProjection(text,warnings,included_entry_ids,excluded_count)`.

- [x] RED table n−1/n/n+1, timeless, unclassified exact text, selected cast, legacy conversion stable IDs. Assert excluded future secret absent even when projection empty. Unknown/foreign/trashed anchor rejects only relevant selected cards.
- [x] Run `python -m pytest tests/characters/test_character_models.py tests/characters/test_character_projection.py -q --basetemp=.pytest-tmp/r6-7`.
- [x] Implement strict versioned loader, deterministic legacy unclassified entry, availability by stable scene ID and active order. `from_scene` data enters separate author directive section, not past evidence. No automatic temporal inference or raw fallback.
- [x] GREEN same command; reorder changes availability with ID preserved, legacy raw descriptions yield warning. Source citation type is pure; do not import generation into storage through character modules.

### Task 8: Сценовий контекст і стійкі попередження

**Files:** Modify `generation/context.py`, `readiness.py`, `worker.py`, `web/static/run-readiness.js`, `runs.js`; create `tests/generation/test_character_context.py`, `tests/web/test_context_warnings.py`, `tests/web/js/context_warnings.mjs`.

**Interfaces:** `ContextBundle.context_warnings: list[str]=[]`; readiness `warnings: list[str]` alongside legacy singular warning; worker `context_warning` event and deduplicated Run.warning preserving evaluator diagnostics. No Run schema migration.

- [x] RED: future card fact absent in brief/draft/edit, raw fallback absent; nonblocked unclassified warning visible in confirmation/status and after reload; warning does not erase refusal/evaluation warning and later failure still error.
- [x] Run `python -m pytest tests/generation/test_character_context.py tests/web/test_context_warnings.py -q --basetemp=.pytest-tmp/r6-8` (Node scenario via pytest wrapper).
- [x] Integrate common projector and frozen warnings, existing character refs/hash/CAS and full scene order; memory inference remains isolated from cards. Readiness can warn for remaining tasks without requiring their ungenerated prose; active execution derives warnings from actual ContextBundle.
- [x] GREEN same command; prompt/brief/canon outside temporal schema is explicitly outside no-spoiler guarantee. prepare protocol remains v1-compatible and new cards default unclassified.

### Task 9: Авторський API і редактор доступності

**Files:** Create `characters/service.py`, `web/routes_characters.py`, `web/static/characters.js`, `tests/web/test_character_availability.py`, `tests/web/js/character_editor.mjs`; modify app.py/story.html minimally; reuse existing tokens.

**Interfaces:** `read_character_material(repo,story_id,scene_id=None) -> dict`; `save_character_material(repo,story_id,cards,expected_revision) -> dict`; GET/PUT `/api/stories/{story_id}/characters` with optional GET scene_id preview and PUT expected_revision/cards. Publication through `Repository.publish_story_material(...,'characters_version_id',...)`.

- [x] RED API source ownership/quote, author origin without citation, duplicate IDs, stable IDs on edit, active anchor validation, CAS409. JS regression ensures preview/late response never overwrites scene buffer or newer card edits; plain text cannot execute HTML.
- [x] Run `python -m pytest tests/web/test_character_availability.py -q --basetemp=.pytest-tmp/r6-9` (including Node wrapper in same file or unique sibling module).
- [x] Implement captured validation then immutable cards version + CAS publication. Imported origin requires citations; authored entries explicit. Editor in context panel supports split/edit entries, availability selector, active-scene selector, save and scene preview; use textContent and accessible labels. No automatic author-source migration or model calls.
- [x] GREEN command; inspect desktop/mobile synthetic UI using applicable UI skill. Keep any own synthetic server separate; stop only its process. Update SPEC API/data/warnings contracts in this part's commit.

### Task 10: Цілісність і завершення c

**Files:** Modify `storage/integrity.py`; extend `tests/storage/test_integrity.py`, `test_backup.py`, `tests/integration/test_memory_v2_flow.py`; update SPEC, runbook and progress/backlog.

**Interfaces:** Fsck validates v1/v2 card shape, citations, IDs, anchor ownership; archived anchor in historical cards is distinct from current active-card usability. Existing backup protocol unchanged.

- [x] RED: mixed cards/memory restore, foreign anchor, bad source quote, version2 metadata after reorder/trash, unclassified legacy after reopen. Confirm privacy: no exact author data or secrets in fixtures/artifacts.
- [x] Run `python -m pytest tests/storage/test_integrity.py tests/storage/test_backup.py tests/integration/test_memory_v2_flow.py -q --basetemp=.pytest-tmp/r6-10`.
- [x] Implement missing checks using pure models and captured history, never call generation from storage. Finish requirement/scenario/test mapping and runbook memory/availability instructions; mark only verified work complete.
- [x] GREEN; full suite `python -m pytest -q --basetemp=.pytest-tmp/r6-c`; git diff-check and verify only own hunks staged. Commit `feat: scope character details by narrative scene availability`.

## Самоперевірка та handoff

- [x] R06-PREFIX → Tasks2/5/6; PROJECTION/SCOPE → Tasks1/2/3/4; JOURNAL/DELTA → Tasks1/3/4; COMPAT/LINEAGE → Tasks2/4/5/6/10; CHARACTER-TIME → Tasks7/8/9/10; BUDGET → Tasks2/6.
- [x] Єдині імена типів/сигнатур і pure imports; не змішувати v1 wire із v2 журналом; historical/current prefix перевіряються в правильному часі.
- [x] Сторонні зміни й worker-діагностика лишилися окремо; кожний архітектурний коміт містить актуальний SPEC.
- [x] Виконати в цьому чаті без нового запиту підтвердження плану — пряма вказівка власника.
- [x] Після a/b/c перейти до Venice: спочатку catalog/capabilities і вимір actual evaluator request без inference; лише потім конкретний платний пробний виклик за погодженими даними й чинним бюджетом.
