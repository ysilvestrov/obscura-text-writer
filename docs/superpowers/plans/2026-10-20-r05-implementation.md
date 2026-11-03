# R-05 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking. Виконання пропонується в поточному чаті; один незалежний reviewer на приймання кожної частини a/b/c.

**Goal:** Усунути зайві конфлікти генерації, зробити актуальність перевірною й дозволити явне авторське прийняття без прихованого повтору inference.

**Architecture:** Спочатку предметні операції Repository поглинають SQL зовнішніх сервісів. Потім узгоджений read view породжує dependency snapshot і незалежний target CAS; авторські рішення зберігаються append-only у app_settings. Fingerprint залишається доказом запиту, не алгоритмом актуальності.

**Tech Stack:** Наявні Python/Pydantic/SQLite WAL/FastAPI/Jinja/ES modules/pytest/Node; нові залежності не потрібні.

**Spec:** [R-05-dependency-publication.md](../../specs/changes/R-05-dependency-publication.md), погоджено власником 20.10.2026; чинна архітектурна правда — [SPEC.MD](../../../SPEC.MD).

## Global Constraints

- Поточна гілка й каталог; сторонні dirty branding/UI/publication файли не відкотувати й не комітити.
- Послідовність a→b→c, окремі коміти/перевірки; у SPEC описувати лише реалізоване.
- «Активна спроба використовує зафіксовані налаштування; нові налаштування застосовуються з наступного етапу».
- «Legacy stale без доказового знімка автоматично актуальним не стає».
- «Пам’ять і оцінювання автоматично не підтверджуються» авторським прийняттям прози.
- «Новий модельний виклик і ручне повторне вставлення тексту не потрібні» для прийняття.
- «Таблиці SQLite та user_version=2 не змінюються»; розширення JSON через defaults.
- Немає реальних моделей/витрат, змін авторських data-dir або перезапуску користувацького сервера.
- R-04 block/off перевіряються до inference; немає fallback або прихованого retry.
- RED→GREEN для нової поведінки; повний pytest послідовно з короткими різними basetemp.

## Review Focus

1. Refusal отримано, але запис partial/report падає: block лишається; Task 3 зберігає й запускає регресії R-04.
2. Повтор request_id після зміни readiness/block: повертається той самий run; Task 3 перевіряє порядок lookup перед новими guards.
3. Head A→B→A під час inference: target CAS захищає новий авторський вибір, хоча freshness залежностей може відновитися; Tasks 5–6 мають окремі тести цих двох понять.
4. Preview авторського прийняття застарів до POST: жодного acceptance/перемикання голови; Task 7 перевіряє rollback.
5. Нове джерело замість null і нова сцена на межі контексту: зміна виявляється навіть без старих ребер; Tasks 4–6 перевіряють selectors/order, не лише input_refs.

## Карта файлів і меж

- `src/storygen/run_models.py`: незалежні RunRequest/Run/RunEvent; старі generation імпорти — re-export.
- `storage/invalidation.py`: SQL-інвалідація всередині storage; на першому етапі той самий алгоритм.
- `storage/authoring.py`, `storage/run_store.py`, `storage/settings_store.py`: предметні групи операцій, підключені до Repository; без універсального SQL/callback API.
- `dependency_models.py`: типізовані Snapshot/Selector/TargetCAS/Acceptance, незалежні від generation/storage.
- `storage/context_view.py`: узгоджений read view даних одного твору; `storage/snapshots.py`: порівняння selectors, актуальність та diff.
- `generation/context.py`, `stages.py`, `worker.py`, `evaluation/story_adapter.py`: побудова контексту на view, передавання snapshot/CAS і координація.
- `storage/acceptance.py`: preview/commit acceptance і атомарне просування прийнятого run.
- Наявні authoring/evaluation/HTTP/JS модулі стають клієнтами цих контрактів.
- `tests/storage/test_storage_boundaries.py`, `test_authoring_transactions.py`, `test_run_store.py`, `test_dependency_snapshots.py`, `test_freshness.py`, `test_acceptance.py`: нові предметні регресії.
- `tests/generation/test_publication_snapshot.py`, `test_accepted_resume.py`, `tests/web/test_acceptance.py`, `tests/web/js/acceptance_regressions.mjs`: інтеграція та UI.

## R-05a: межі сховища

### Task 1: Незалежні run-моделі та інвалідація

**Files:** Create `run_models.py`, `storage/invalidation.py`, `tests/storage/test_storage_boundaries.py`; modify `generation/worker.py`, `generation/events.py`, `generation/dependencies.py`, `storage/repository.py`.

**Interfaces:** Produces `run_models.RunRequest`, `Run`, `RunEvent`; `storage.invalidation.invalidate_in_transaction(repo, db, changed_version_ids: list[str], exclude=()) -> list[str]`, `invalidate_story_materials(repo, db, story_id: str) -> None`; public `Repository.invalidate_dependents(ids: list[str]) -> list[str]`.

- [x] Додати AST-перевірку `test_storage_does_not_import_generation`, включно з локальними imports, і `test_run_models_reexports_remain_compatible`:
  `worker.Run is run_models.Run`, `events.RunEvent is run_models.RunEvent`.
- [x] RED: `python -m pytest tests/storage/test_storage_boundaries.py tests/generation/test_dependencies.py -q --basetemp=.pytest-tmp/r05a-1`; очікується заборонений імпорт storage→generation / відсутній незалежний модуль.
- [x] Перенести моделі без зміни полів/валідації. Перенести SQL-інвалідацію, залишити зовнішні функції generation як сумісні делегати публічних Repository методів; db не передається зовнішнім сервісам.
- [x] GREEN тією самою командою. Зберегти незмінні downstream stale/needs_review та ізоляцію творів.

### Task 2: Авторські транзакції й налаштування ролей

**Files:** Create `storage/authoring.py`, частину `storage/settings_store.py`, `tests/storage/test_authoring_transactions.py`; modify `storage/repository.py`, `authoring/service.py`, `blueprints.py`, `imports.py`, `trash.py`.

**Interfaces:** Repository methods `update_scene_plan(scene_id, text, expected_revision) -> Scene`, `update_scene_metadata(scene_id, changes, expected_revision) -> Scene`, `reorder_scenes(story_id, scene_ids, expected_revision) -> Story`, `set_story_trashed(story_id, expected_revision, restore: bool) -> Story`, `set_scene_trashed(story_id, scene_id, expected_revision, restore: bool) -> Scene`.

Ролі: `read_role_settings(story_id) -> dict[str, dict]`, `write_role_settings(story_id, updates: dict[str, dict], expected_revision) -> Story`. Сервіс валідовує RoleSettings; storage повторно перевіряє власність/вид prompt refs і CAS та атомарно зберігає весь пакет ролей.

Матеріали: `publish_story_material(story_id, field: str, version_id, expected_revision) -> Story`, `publish_blueprint(story_id, canon_id, character_cards_id, scenes: list[tuple[SceneCreate, VersionRef]], expected_revision) -> Story`, `register_source(story_id, metadata: dict) -> None`. Створення/перевірка літературних схем і цитат залишається в authoring.

- [x] Додати `test_shared_roles_rollback_if_one_prompt_is_foreign`, `test_blueprint_conflict_keeps_heads_and_scene_order`, `test_restore_conflict_keeps_trash_state`: після помилки жодної часткової зміни відповідних SQL-полів/payload; immutable історичні файли можуть лишитися, як раніше.
- [x] Розширити AST `test_authoring_uses_public_repository_only`: у authoring немає repo.db/приватних Repository операцій або SQL через альтернативне ім’я DB.
- [x] RED: `python -m pytest tests/storage/test_authoring_transactions.py tests/storage/test_storage_boundaries.py tests/authoring -q --basetemp=.pytest-tmp/r05a-2` — нові API/межі відсутні.
- [x] Перенести транзакційні тіла без зміни stale/кошика/CAS; SQL всіх циклів shared roles/blueprint залишається в одній транзакції. Не імпортувати StoryBlueprint із generation у storage: передавати вже перевірені domain refs/SceneCreate.
- [x] GREEN тією самою командою та чинними web authoring/trash/bulk tests.

### Task 3: Run/event/evaluation/settings без зовнішнього SQL

**Files:** Create `storage/run_store.py`, завершити `storage/settings_store.py`, `tests/storage/test_run_store.py`; modify `generation/worker.py`, `evaluation/story_adapter.py`, `evaluation/blocks.py`, `storage/repository.py`.

**Interfaces:** `Repository.get_run(id) -> Run`, `list_runs(story_id=None) -> list[Run]`, `save_run(run) -> Run`, `requeue_run(run) -> Run` (із повторною перевіркою active story/scene), `find_run_by_request_id(request_id) -> Run|None`, `enqueue_run(candidate: Run) -> tuple[Run, bool]`, `append_run_event(run_id, type, data) -> RunEvent`, `list_run_events(run_id, after_seq=0) -> list[RunEvent]`, `recover_running_attempts() -> None`. `enqueue_run` повторно перевіряє active story/scene та рівність request при existing request_id; bool означає новий INSERT. Координатор лишає condition і доменний preflight, storage — SQL; callback у відкриту транзакцію не вводиться.

Settings: `read_evaluator_settings(story_id) -> dict|None`, `write_evaluator_settings(story_id, payload: dict) -> None`, `read_calibration(id) -> dict|None`, `register_calibration(id, payload: dict) -> None`, `read_refusal_block(story_id, identity_hash) -> dict|None`, `record_refusal_block(story_id, identity_hash, payload: dict) -> dict`. Перша причина лишається INSERT OR IGNORE. `publish_evaluation(ref_id, expected_story_revision: int, input_refs: list[str]) -> VersionRef` поглинає чинний зовнішній UPDATE stale; точний snapshot замінить цей legacy guard лише в R-05b.

- [x] Додати `test_event_sequences_are_unique_under_two_writers`: два локальні потоки, 20 подій кожен; seq рівно 1…40 без повторів, SQL-порядок replay стабільний.
- [x] Додати `test_enqueue_is_idempotent_before_changed_preflight`, `test_evaluation_publication_detects_concurrent_change` та AST-перевірку всього production поза storage на прямі DB/private API.
- [x] RED: `python -m pytest tests/storage/test_run_store.py tests/storage/test_storage_boundaries.py -q --basetemp=.pytest-tmp/r05a-3` — API/повна межа відсутні.
- [x] Перенести SQL; не змінювати cancel/pause/recovery, серіалізацію run, seq або R-04 порядок block→partial→report. Перед фактичним API лишити guard незалежно від enqueue/readiness.
- [x] GREEN focused: `tests/generation/test_worker.py`, `tests/evaluation/test_evaluator_blocks.py`, `tests/web/test_runs.py`, `tests/web/test_evaluation.py`, `tests/storage`.
- [x] Повний `python -m pytest -q --basetemp=.pytest-tmp/r05a-full`; усі тести PASS, відомий Windows symlink skip позначити окремо. Оновити SPEC A2/A5/A7 і source map, journal; незалежне read-only рев’ю R-05a та виправлення істотних знахідок з RED/GREEN.
- [x] Коміт `refactor: move story and workflow transactions behind repository` лише власних файлів; R-05b/c ще не оголошувати завершеними.

## R-05b: точні залежності й актуальність

### Task 4: Snapshot-моделі та атомарний read view

**Files:** Create `dependency_models.py`, `storage/context_view.py`, `storage/snapshots.py`, `tests/storage/test_dependency_snapshots.py`; modify `domain.py`, `storage/repository.py`, `generation/context.py`.

**Interfaces:** `DependencySelector(kind, owner_id, field, expected)`, `DependencySnapshot(schema_version=1, scope, selectors, refs, scene_order)`, `TargetCAS(scene_id, head, version_id, head_revision)`; всі типізовані, extra forbid. `Story.config_revision=0`, `Scene.head_revisions={}`, `VersionRef.dependency_snapshot=None`, `ContextBundle.dependency_snapshot=None`, `target_cas=None` — сумісні defaults.

`Repository.context_view(story_id) -> ContextView` читає story/scenes/version metadata/source selectors в одній read-транзакції. View має read-only get_story/get_scene/list_scenes/get_version/active_source/read_text для контексту; після транзакції тексти читаються за зафіксованими immutable refs/хешами. `build_dependency_snapshot(view, scene_id, stage, settings, input_refs) -> DependencySnapshot` формує декларативні selectors за матрицею R05-SNAPSHOT; інтерпретатор не виконує довільний SQL.

- [x] Додати `test_context_view_does_not_mix_heads_from_two_transactions`: конкурентна заміна між читаннями не створює змішаного view; текст відповідає captured hashes.
- [x] Додати `test_snapshot_records_missing_canon`, `test_memory_tracks_only_prefix_order`, `test_patches_ignore_unread_scene_metadata`, `test_unknown_snapshot_version_fails_closed`; перевіряти конкретні null/ID й результати порівняння, не внутрішній порядок словника.
- [x] RED: `python -m pytest tests/storage/test_dependency_snapshots.py -q --basetemp=.pytest-tmp/r05b-4` — модель/view відсутні.
- [x] Побудову контексту перевести на view; зберігати лише семантично використані selectors, не всі поля всіх прочитаних сцен. Параметри активної спроби залишаються frozen input. Пороги контексту/точний текст промптів не змінювати цією задачею.
- [x] GREEN тією самою командою плюс `tests/generation/test_context.py`; перевірити старі серіалізовані payload без нових полів.

### Task 5: Публікація через snapshot і target CAS

**Files:** Modify `storage/repository.py`, `storage/authoring.py`, `storage/settings_store.py`, `generation/stages.py`, `worker.py`, `evaluation/story_adapter.py`; create `tests/generation/test_publication_snapshot.py`.

**Interfaces:** `Repository.commit_stage_result` зберігає сумісний підпис; нові attempts перевіряють snapshot і TargetCAS в тій самій write-транзакції. `publish_evaluation` приймає додатковий optional `snapshot=None` й використовує legacy expected_story_revision тільки без snapshot. Кожний вибір голови збільшує відповідний head_revision; налаштування збільшують config_revision і legacy story.revision.

- [x] Тести `test_scene_six_plan_change_does_not_block_scene_two_memory`, `test_unrelated_role_change_does_not_block_patches`, `test_replaced_prose_or_previous_memory_blocks_publication`, `test_added_canon_conflicts_with_missing_selector`, `test_target_head_aba_still_conflicts`.
- [x] Окремі тести `test_role_change_applies_to_next_stage`, `test_legacy_attempt_keeps_conservative_revision_check`, `test_evaluation_window_checks_exact_inputs`; нова голова залишається untouched при alternative, result blob зберігається.
- [x] RED focused: `python -m pytest tests/generation/test_publication_snapshot.py -q --basetemp=.pytest-tmp/r05b-5` — зайві конфлікти/відсутня перевірка snapshot.
- [x] Замінити глобальні revision-перевірки тільки для нових перевірених snapshots; target CAS не включати до content-baseline/fingerprint, інакше результат стає застарілим від власної публікації. Reuse усе ще порівнює точний request fingerprint.
- [x] GREEN focused і worker/evaluator регресії, включно з R-04 block та idempotency.

### Task 6: Єдина похідна актуальність і fsck

**Files:** Modify `storage/snapshots.py`, `repository.py`, `invalidation.py`, `integrity.py`, `memory/service.py`, `generation/readiness.py`, `src/storygen/application/exports.py`; create `tests/storage/test_freshness.py`; expand storage backup/integrity tests.

**Interfaces:** `compare_snapshot(view, snapshot) -> list[DependencyChange]`, `resolve_freshness(view, version_id) -> FreshnessResult(stale, reasons, baseline_id)`; результати використовуються в get/list versions, context, heads/readiness та export_snapshot в межах того самого read view. Unknown/legacy правила явні; історичні model input_refs не переписуються. `DependencyChange` містить selector, expected/current і reason code.

- [x] Додати `test_new_version_recovers_after_dependency_a_b_a`, `test_legacy_stale_never_recovers_without_acceptance`, `test_adding_or_trashing_scene_changes_relevant_order`, `test_export_and_context_agree_on_freshness`, `test_snapshot_refs_corruption_is_reported_by_fsck`.
- [x] RED: `python -m pytest tests/storage/test_freshness.py -q --basetemp=.pytest-tmp/r05b-6` — чинні незворотні stale прапорці не відновлюються.
- [x] Реалізувати derived freshness нових baseline, лишити legacy stale й needs_review консервативними. Цикл/відсутній/чужий ref не вважається fresh. Структуру/власність нових метаданих перевіряти у read-only fsck, без repair.
- [x] GREEN focused, backup→restore нового/legacy каталогу з однаковими heads/hash/freshness. Повний `python -m pytest -q --basetemp=.pytest-tmp/r05b-full`; SPEC DATA/CONTEXT/A2/A5/A7 та journal, незалежне рев’ю.
- [x] Коміт `feat: publish against precise dependency snapshots`; R-05c ще не завершено.

## R-05c: авторське прийняття та продовження

### Task 7: Preview та транзакційне acceptance

**Files:** Create `storage/acceptance.py`, `tests/storage/test_acceptance.py`; modify `dependency_models.py`, `repository.py`, `integrity.py`, `web/routes_versions.py`.

**Interfaces:** `Repository.preview_acceptance(scene_id, version_id) -> AcceptancePreview(version_id, expected_revision, changes, baseline, preview_fingerprint)`; `accept_version(scene_id, version_id, expected_revision, preview_fingerprint, note=None) -> AcceptanceResult(scene, version, acceptance)`.

API: `GET /api/scenes/{scene_id}/acceptance-preview?version_id=...`; `POST /api/scenes/{scene_id}/accept-version` з version_id/expected_revision/preview_fingerprint/optional note. Новий baseline scope author_text фіксує поточні авторитетні матеріали/план/metadata/order, не приписуючи моделі нові прочитані refs. Ключ ledger `acceptance:<story_id>:<acceptance_id>`; попередній baseline ID у payload.

- [x] Тести `test_accept_stale_prose_preserves_text_and_model_provenance`, `test_accept_draft_creates_new_baseline`, `test_acceptance_does_not_refresh_memory_or_evaluation`, `test_preview_race_rolls_back_head_and_ledger`.
- [x] Параметризований reject: foreign/incomplete/corrupt/missing/memory/evaluation/brief. Повторні рішення додають записи, не переписують перший; fsck виявляє неправильну власність/формат acceptance.
- [x] RED: `python -m pytest tests/storage/test_acceptance.py -q --basetemp=.pytest-tmp/r05c-7` — API відсутній/чинний set_head відхиляє stale.
- [x] Реалізувати preview та повторну перевірку baseline/CAS/цілісності при commit. Звичайний вибір fresh версії не потребує acceptance. Preview fingerprint — оптимістична перевірка стану, не секрет/автентифікація.
- [x] GREEN focused і чинні accept-draft/manual-memory/trash тести.

### Task 8: Явний перегляд і прийняття в UI

**Files:** Modify `web/static/versions.js`, `editor.js`, `web/templates/story.html` лише в місцях acceptance; create `tests/web/test_acceptance.py`, `tests/web/js/acceptance_regressions.mjs`, pytest Node wrapper.

**Interfaces:** UI отримує AcceptancePreview й показує текст та expected/current diff перед окремим confirm POST. Fresh-кнопки лишаються сумісними. Dirty/saving/history buffers та scene revision не обходяться.

- [x] Тести Node: stale draft/prose можуть відкрити preview; memory/evaluation/brief не отримують універсальної кнопки; dirty блокує commit; 409 зберігає буфер і не показує success; POST надсилає preview_fingerprint.
- [x] HTTP: 200 для valid acceptance, 400 для kind/ownership, 409 для застарілого preview; рішення з’являється в історії й не перезаписує старий result attempt.
- [x] RED: `python -m pytest tests/web/test_acceptance.py -q --basetemp=.pytest-tmp/r05c-8` і Node wrapper.
- [x] Реалізувати двокроковий UI за наявною візуальною системою без стороннього redesign; врахувати вже наявні dirty правки versions/editor/template й stage лише власний diff.
- [x] GREEN HTTP/Node та попередні editor buffers/version-history регресії.

### Task 9: Продовження після прийнятої альтернативи й фінальне приймання

**Files:** Modify `storage/acceptance.py`, `storage/run_store.py`, `generation/worker.py`, `web/routes_runs.py`, `web/static/runs.js`; create `tests/generation/test_accepted_resume.py`; update SPEC/runbook/journal.

**Interfaces:** `RunCoordinator.continue_after_acceptance(id, version_id, expected_cursor, expected_scene_revision, acceptance_id=None) -> Run`; однойменна предметна Repository операція атомарно перевіряє run/task/cursor, attempt.result_version_id, selected head та freshness/baseline. `POST /api/runs/{id}/continue-after-acceptance` приймає ці поля. Для свіжого явно вибраного alternative acceptance_id може бути null; за stale потрібен чинний acceptance.

- [x] Тести `test_remaining_continues_after_accepted_result_without_inference_repeat`, `test_wrong_task_version_or_cursor_does_not_advance`, `test_dependency_change_after_acceptance_blocks_continue`, `test_cancellation_or_refusal_block_cannot_be_bypassed`.
- [x] RED: `python -m pytest tests/generation/test_accepted_resume.py -q --basetemp=.pytest-tmp/r05c-9` — чинний resume не має атомарного continuation.
- [x] Просувати лише правильний cursor після явної дії, не переписуючи історичний alternative attempt у completed. Ніякого автоматичного продовження після перемикання head; звичайний retry лишається явним повтором.
- [x] Інтеграційний fake-gateway прогін семи сцен: pause/restart, relevant+irrelevant edit, прийняття одного alternative, resume, повна memory/evaluation lineage, export; жодних справжніх API.
- [x] Повний `python -m pytest -q --basetemp=.pytest-tmp/r05c-full`, `git diff --check`, валідні docs-links; SPEC із реалізованими Requirement/Scenario й матрицею тестів. Незалежний reviewer пакета c та виправлення значущих знахідок RED/GREEN.
- [x] Коміт `feat: accept reviewed story versions and continue workflow safely`. Журнал: R-05a/b/c та залежна частина 3 R-03 завершені лише за наявності всіх перевірок; наступна задача R-06.

## Примітки до виконання й самоперевірка плану

Чинні context/export тести перевірено: `tests/generation/test_context.py`, `tests/authoring/test_exports.py`; exporter — `src/storygen/application/exports.py`. Команди `python` вище виконувати через `./.venv/Scripts/python.exe`. HTTP/Node/subprocess pytest потребує дозволу sandbox; це локальні перевірки, не модельні витрати.

Покриття специфікації: STORAGE→1–3; SNAPSHOT→4–5; FRESHNESS→6; ACCEPT→7–8; RESUME→9; сумісність/цілісність→4/6/7; R-04 захист→3/5/9. Task 3 породжує run/settings API, Task 4 — типи/view, Task 5 їх споживає, Task 6 породжує єдину freshness, Tasks 7–9 її використовують. Новий state не є fresh від самого існування JSON-поля; legacy fallback збережено.

План не змінює три погоджені продуктові рішення. Якщо конкретний snapshot scope потребує матеріалу, якого немає в матриці, спочатку уточнити контракт у специфікації, не узаконювати приховану залежність тестом під випадковий код.


## Результат виконання

Усі 9 задач виконані в погодженому порядку. R-05a: коміт 5dee3d6; R-05b: 71e3bcc; R-05c — окремий фінальний коміт цього пакета. Незалежні read-only рев’ю для a/b/c завершені, істотну знахідку b і дрібну c виправлено з RED/GREEN. Фінально **397 passed, 1 skipped** (Windows symlink privilege), 41.25 с. Новий web-тест має ім’я test_acceptance_api.py, щоб не конфліктувати з однойменним storage-модулем у pytest. Окремий acceptance.js обслуговує preview/dirty guards і continuation helper; CSS додає лише preview-компонування. Детальні результати й обґрунтовані уточнення — у remediation-progress.md. Реальних моделей або авторських data-dir не використовували.
