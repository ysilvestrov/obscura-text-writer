# R-28b Impact Chunking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Довга перевірка впливу проходить бюджетованими частинами з повним coverage та доказами, не потребуючи нескінченного збільшення лімітів.
**Architecture:** Новий manifest/proof protocol2 для завеликих перевірок; старий протокол1 зберігається для сумісних коротких запитів і старих запусків. DAG extraction→reduction→checks→synthesis, deduplicated exact documents, immutable intervals/tasks/proofs. Фінальний звіт публікує storage лише після перевірки повного графа й live CAS.
**Tech Stack:** Python/Pydantic/SQLite schema4/FastAPI/ES modules, pytest/Playwright, без нових залежностей.
**Spec:** docs/superpowers/specs/2026-10-26-impact-chunking-design.md, погоджено26.10.2026.

## Global Constraints

- Inline у поточній гілці за вибором власника; no worktree/push/paid calls. Один незалежний fresh-context review наприкінці.
- Жодного обрізання/вигаданих доказів/авторських змін; source/target offsets Unicode, exact SHA, temporal projections незмінні.
- Число викликів/верхня вартість і run/story caps до dispatch; старі v1 proofs не перетворюються на v2.
- Кожний wire request перевіряється в обох лімітах, включно з результатами попередніх фаз.
- SPEC/traceability/user docs UA/EN разом із кодом; check_docs і verify фіксують фактичні результати.

## Review Focus

- Повторний однаковий текст не губить різні dependency IDs — Task1 test_dedup_preserves_identity.
- Дуже довгий абзац/emoji/перенесення факту не створюють coverage gaps — Task1 test_unicode_and_large_source.
- Окремі no_impact не очищують root при відсутньому child/uncertainty — Task2 test_missing_or_uncertain_proof.
- Settings/input change і crash на межі checkpoint не спричиняють повтор чи CAS bypass — Task3 test_recovery_and_settings_change.
- Preview бюджету включає синтези, dirty UI зберігається — Task4 API/browser checks.

### Task1: Детермінований manifest і bounded requests

**Files:** Create impact/chunk_models.py, impact/chunking.py, generation/impact_chunk_context.py; tests/impact/test_chunking.py.
**Interfaces:** plan_chunks(repo,plan)->ChunkManifest; task_payload(manifest,task,results)->dict; build_chunk_context(repo,manifest,task,results)->ContextBundle. Manifest містить task DAG, source intervals і fingerprints; result cap фіксується до запуску.
- [x] RED тести детермінізму, dedup, exact interval coverage, oversized Unicode, source/target limits, bounded reduction.
- [x] Реалізувати manifest і measured greedy/binary splitting з paragraph overlap; вартість рахувати за кожним bounded body з резервом результатів.
- [x] GREEN Task1 tests; описати протокол/межі в SPEC і traceability.

### Task2: Валідація повного графа та durable proofs

**Files:** Create impact/chunk_validation.py; modify impact/models.py, storage/impact_store.py, impact_validity.py, impact_checks.py; tests/impact/test_chunk_proofs.py.
**Interfaces:** validate_part(payload,manifest,task,results)->PartResult; verify_chunk_record(record,attempts,read_partial)->None; aggregate_record(manifest,target,proofs)->ImpactRecord v2. Кожен leaf/reducer має direct child coverage; no_impact лише після всього required closure. Sources у quotations відповідають оригіналам і фактично переданим spans.
- [x] RED missing/reordered/tampered proof, quote outside span, uncertainty propagation, legacy v1 compatibility.
- [x] Реалізувати v2 optional fields і proof DAG validation, atomic live CAS, backup/fsck graph; memory verdict окремо.
- [x] GREEN storage/backup tests; SPEC і traceability.

### Task3: Послідовна черга, hard budget і recovery

**Files:** Create generation/impact_chunk_runner.py + chunk prompt; modify worker.py, impact_context.py, stages.py, providers/requests.py; tests/impact/test_chunk_runner.py.
**Interfaces:** execute_chunks(worker,run_id); protocol dispatch через run.impact.protocol; persisted results map task_id→attempt_id, immutable manifest. Старі v1 paths збережені. Нові stage names — impact_part, єдиний native PartResult schema; phase знаходиться у manifest/task.
- [x] RED extraction/reduction/check/synthesis ordering, refusal, output limit, cancellation, paid run cap, checkpoint recovery, settings conflicts.
- [x] Реалізувати measured preflight fallback для великих запитів, exact manifest stamp у preview/start, sequential durable reuse; жодного автоматичного перепланування поза budget.
- [x] GREEN queue/accounting/integration tests; SPEC/traceability.

### Task4: Preview, UI, документи, перевірка та поставка

**Files:** modify routes_impact.py, static/impact.js/i18n.json; tests/web/test_impact_api.py, browser/impact.spec.mjs; docs/impact-review.md, SPEC.MD, traceability, remediation-progress/backlog.
- [x] RED preview count/cost/fingerprint guard і прогрес частин, legacy UI compatibility.
- [x] Показати protocol/chunks/syntheses та phase N/M; findings і journal state не змінюють чинний author workflow.
- [x] GREEN tests/Playwright, dry-run чинного твору без API, check_docs, scripts/verify.py full suite.
- [x] Один fresh whole-feature review; один RED→GREEN fix batch; логічний коміт коду+SPEC/user docs. Реальні API не запускати.
- [x] Для runtime upgrade отримати свіжий safe-state,0active, restart, read-only HTTP/preflight smoke; журнал. No migration якщо app_settings достатньо.

## Rulings

- Невеликий v1 запит залишається v1; протокол2 активується автоматично лише при preflight overflow. Це зберігає короткий workflow і старі completed attempts, а не ставить legacy дані під новий validator.
- При завеликій одиничній службовій оболонці або непоміщенні фактичного результату в погоджений cap — явна зупинка з partials; не вигадуємо необмежений контекст/число викликів.
- Task1–3 можуть бути оформлені одним цілісним feature-комітом, щоб не поставляти непідключений протокол; TDD докази фіксуються для кожної частини.

## Завершення перевірок

verification-e48p48cv:1190passed/0failed/errors/1skipped, source_changed_during_run=false. Browser48passed, після fix batch6impact повторно passed. Check_docs/diffcheck passed. Один незалежний reviewer та fix batch закрито. Реальних model/API calls0. Власник надав свіжий safe-state дозвіл для restart після тестів; поставка наступним кроком. Один цілісний feature-коміт замість проміжних непідключених контрактів.

Поставка: commit7a20816,0active/schema4, свіжий дозвіл автора; сервер8765 перезапущено (launcher37100/child38608). HTTP200 головна/story/GET impact. Після окремого безкоштовного GET офіційного каталогу кеш тарифу Venice gemma-4-uncensored оновлено, budget limits незмінні. Live preflight protocol2 ready=true/52calls, upper reserve1.299753502USD; run count до/після ідентичний, модельних викликів0.
