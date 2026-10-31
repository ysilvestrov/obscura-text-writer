# R-28 Book Revision Impact Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Автор запускає перевірку змістового впливу змінених передумов; no_impact прибирає потребу перегляду конкретного тексту, changes_required показує Dirty з доказами.

**Architecture:** Окрема операція черги impact з двома фазами delta/check, planner та окремими промптами. Незмінні типізовані записи impact у чинному app_settings і blobs; атомарні застосування/відхилення. Freshness overlay заміщує лише повністю перевірену змістову застарілість конкретного target без зміни його старого snapshot або авторського AcceptanceRecord.

**Tech Stack:** Python/Pydantic, SQLite schema4, FastAPI, ES modules, чинні streaming/billing/token-budget, pytest/Playwright.

**Spec:** docs/superpowers/specs/2026-10-25-book-revision-impact-design.md (погоджено власником 25.10.2026).

## Global Constraints

- Явна кнопка, без автоматичних платних викликів, повторів чи переписування.
- Planner, окремі delta/check промпти; UA/EN UI, український аналіз.
- Повне coverage, exact source citations, chronology/horizon, no silent truncation.
- Точний target/source fingerprint і CAS; integrity/missing/incomplete не перекриваються.
- Пам’ять та forwarding не переписуються; потрібність оновлення окрема від Dirty прози.
- Confirmed run-limit є жорсткою межею разом зі story-limit.
- Реальні API-тести й restart робочого сервера тільки після окремого погодження.
- SPEC/traceability/user docs у тих самих змінах; виконувати check_docs і verify.
- Рішення реалізатора: використовуємо app_settings як наявні acceptance records, без зайвої міграції; backup/fsck перевіряють нові типи явно. Поточна гілка/checkout за чинним вибором власника.

## Review Focus

- Різні історичні бази: delta keys не зливають різні пари джерел — Task1 test_distinct_historical_bases.
- Stale draft/memory не блокують повний no_impact прози, але corruption блокує — Task2 test_transitive_semantic_overlay_and_integrity.
- Нова правка/відхилення висновку негайно скасовує overlay — Task2 test_overlay_invalidated_and_rejected.
- Crash між збереженням спроби й checkpoint не повторює API — Task3 test_saved_attempt_recovery.
- Dirty буфер і локалізація під час фонового аналізу не гублять текст — Task4 browser test.

### Task 1: Знімки передумов, моделі й валідація coverage

**Files:** Create src/storygen/impact/{__init__,models,planning,validation}.py; tests/impact/test_planning.py, test_validation.py.
**Interfaces:** plan_impact(view) -> ImpactPlan; capture_target(view,version_id) -> ImpactTarget; validate_delta(payload,group) -> DeltaReport; validate_check(payload,target,delta) -> CheckReport. Fingerprint — канонічний JSON SHA256.

- [x] Написати RED tests: old→current selectors/refs, різні історичні бази, exact evidence, chronology, empty prose, legacy missing snapshot, unknown/reorder unsupported.
- [x] Запустити pytest tests/impact/test_planning.py tests/impact/test_validation.py; підтвердити RED.
- [x] Реалізувати models/planning/validation. Сталі source keys з позначеними old/new versions; target contains raw source text plus safe temporal projection. Missing/unknown не очищувати. Перевіряти повний набір coverage IDs і material IDs.
- [x] GREEN targeted tests; оформити R-28 change spec і Task1 scenarios у SPEC/traceability.
- [x] Коміт доменних контрактів/тестів/документації.

### Task 2: Durable reports, atomic overlay, audit/backup

**Files:** Create src/storygen/storage/impact_store.py, impact_checks.py; modify repository.py, context_view.py, snapshots.py, integrity.py; tests/impact/test_storage.py, test_backup.py.
**Interfaces:** Repository.impact(action,**data); operations save_report, apply_report, reject_report, state. ContextView loads applications; resolve_freshness checks valid current no_impact overlay after immutable integrity guards. No generation import in storage.

- [x] RED atomic CAS/rejection/idempotency, transitive semantic overlay vs corrupt blob, new input invalidation, brief/prose separation, prefix memory unchanged, roundtrip backup.
- [x] Implement append-only report/application records under impact:{story_id}:..., safe typed refs and current full target fingerprint. current baseline traverses narrative dependencies explicitly; source old snapshots preserved. Atomic application verifies completed proof/run/attempt and live source stamp; no global stale update.
- [x] Integrate freshness and effective scene, backup/fsck structural/ref checks. Negative findings do not freshen text; memory remains independently stale.
- [x] GREEN storage/integrity regressions; SPEC/traceability; commit.

### Task 3: Planner delta/check, queue, budgets, recovery

**Files:** Create generation/impact_context.py, impact_runner.py, resources/impact_delta_uk_v1.txt, impact_check_uk_v1.txt; modify run_models.py, worker.py, readiness.py, providers/requests.py, generation/stages.py only for explicit new stages if needed. Tests/impact/test_runner.py, test_context.py.
**Interfaces:** build_impact_context(repo,plan,task,delta=None) -> ContextBundle; readiness(repo,request); execute(worker,run_id). RunRequest mode=impact, impact_plan_fingerprint; Run.impact checkpoint. StageAttempt stages impact_delta/impact_check.

- [x] RED one delta per identical group, independent scene verdicts, schema/citation failures, no empty-output acceptance, refusal stops series, usage ledger/hard run budget, pause/cancel, saved attempt recovery.
- [x] Implement separate prompts/schema and exact bodies through generation_request/token_estimate; no generic planner prompt injected. Context does not receive future prose. Frozen run plan, per-attempt settings; exact checkpoint keys. Build delta then checks sequentially; full source context not just model delta. Store partial/result before advancing cursor. Completed proof reuse without model call.
- [x] Use existing StreamBuffer/accounting with mandatory run and story limits; complete no_impact applies under worker condition plus storage CAS, alternative for changed inputs; uncertain/error leaves material unreviewed.
- [x] GREEN runner/context/readiness/provider regressions; SPEC/traceability; commit.

### Task 4: API and bilingual author workflow

**Files:** Create web/routes_impact.py, static/impact.js; modify app.py, templates/story.html, static/i18n.json, static/scene-state.js or actual existing scene-status module. Tests/web/test_impact_api.py; tests/web/browser/impact.spec.mjs + synthetic server.
**Interfaces:** GET /api/stories/{id}/impact (state), POST /api/stories/{id}/impact/preview (plan/preflight), POST /api/stories/{id}/impact (request_id, fingerprint, budget_limit_usd), POST /api/stories/{id}/impact/{assessment_id}/reject. Queue controls use existing run endpoints.

- [x] RED explicit enqueue/no real calls, target ownership, stale preview conflict, pending/Dirty/no_impact state. Browser neutral fixture starts two-phase fake planner, presents findings and preserves dirty draft.
- [x] Add compact expandable story impact panel with preview/confirmation, scenes/materials/model/calls/budget, stage progress and last-call costs. Report findings use textContent, quote+source label, separate memory status. Link findings to scene/material; allow reject/recheck. Button disabled without eligible saved texts or busy Save.
- [x] Update status labels: pending semantic changes not Dirty; Dirty only current changes_required prose. No prose remains unstarted. Do not change other pipeline order.
- [x] GREEN API + synthetic desktop/mobile tests; check localization and dirty/locale behavior. User docs UA/EN, neutral screenshots, SPEC/traceability; commit.

### Task 5: End-to-end verification and review

**Files:** tests/impact/test_integration.py; docs/impact-review.md, docs/STATUS.md, remediation-progress.md.

- [x] RED→GREEN book revision examples: punctuation/no narrative effect, time/fact/motivation change, stale source chain, memory proof mismatch, replay/cancellation/new sources.
- [x] Run check_docs, scripts/verify.py with appropriate full suite and Playwright; record actual evidence and limitations.
- [x] Fresh whole-branch reviewer under executing-plans; fix important issues RED→GREEN and record rulings. No unrequested API costs.
- [x] Request fresh safe restart only once concrete tested implementation is ready. No migration required; preserve production historical defects and author data. Verify live HTTP/static source only, no paid real calls.
- [x] Logical commits, updated backlog/progress. Keep branch local unless PR/push explicitly requested.

## Pre-flight self-review

Task1 produces typed snapshots for Task2 and Task3; Task2 alone decides CAS/freshness, Task3 never writes SQL. Task3 produces attempt checkpoints for Task4 standard queue controls; Task4 cannot publish model conclusions itself. Task5 covers interactions and final review. Design memory semantics deliberately do not update journal. Existing immutable refs survive all operations. Full source fingerprint rather than story revision avoids invalidation by unrelated UI settings; chronology/order selectors remain explicit.

## Фактичний результат виконання

Tasks 1–4 оформлюються одним цілісним feature-комітом: проміжні контракти не поставляються окремо. Повна фінальна перевірка `verification-jqo_una1`: 1165 passed, 1 skipped, 0 failed/errors; знімок під час запуску не змінювався. Playwright: 46 desktop/mobile до рев’ю, 4 R-28 після виправлень рев’ю. check_docs пройшов. Платні API не викликалися. Запит на свіжий safe-state для перезапуску надіслано; відповідь і live smoke check ще очікуються.

Поставка: після свіжого дозволу автора й перевірки 0 active runs сервер8765 перезапущено (launcher13416, child40388). Головна, сторінка твору й GET impact повернули HTTP200. Міграції та модельних викликів немає; коміт реалізації e614d95.
