# Послідовна перевірка книги — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline. Tasks use checkbox steps. Owner approved design and continuation; execute in this chat without another implementation-method question. One fresh final review.

**Goal:** chronological best-effort review with automatic clean acceptance, author decisions, memory maintenance and durable continuation.
**Architecture:** mode=impact/protocol3 orchestrates one scene at a time; fresh per-scene snapshots and versioned refs-only model parts. Typed reports/acceptances/dispositions in app_settings and phase/checkpoints in Run.impact; legacy1/2 untouched.
**Tech Stack:** Python/Pydantic/SQLite/FastAPI, existing OpenAI accounting/token-budget/worker, vanilla JS UA/EN, pytest/Playwright.
**Spec:** docs/superpowers/specs/2026-10-27-sequential-book-review-design.md (approved27.10.2026).

## Global Constraints

- Valid complete no-concerns automatically accepts and advances; model questions pause as concerns. No confirmation of clean output.
- Author rejects all or explicitly finishes repairs; author authority does not rewrite model evidence. No mandatory re-search after author finish.
- Memory auto after edits and when required for a current prefix; exact sources/evidence/forwarding/chronology preserved. Failure retains acceptance/text.
- No automatic paid retries, real book dispatch, scope narrowing, input truncation or frozen legacy proof rewrite. Explicit story/run budgets apply.
- All model outputs/payloads bounded; no E1…E100 receipt or canonical quote inflation. Full delivered interval/DAG proof, live CAS, settings snapshots.
- SQL4 retained using typed JSON records, unless implementation demonstrates a required migration (record ruling first). SPEC/traceability and UA/EN docs updated with code.

## Review Focus

1. Reject-all then crash before memory/advance: same decision/acceptance reused, no duplicate call. Task3 recovery test.
2. Clean first scene then editing second must use live source state; no all-book frozen continuation. Task3 fresh-next test.
3. Many proofs/concerns: output stays references, no hidden truncation; invalid/incomplete cannot clean. Task2 bounds test.
4. Late externally changed heads, reorder or different story request:409 and preserved author buffer. Task4 API and Task5 browser.
5. Historical/invalid memory or manual forwarding: never silently consent/rewrite evidence. Task3 memory tests and Task6 verification.

## File structure / interfaces

New src/storygen/review/{models,planning,wire,proofs,store,readiness,runner,decisions}.py: pure types/planning, transport contracts, proof replay, atomic persistence, preflight, executor and author commands respectively. Small helpers may be split further by responsibility; record exact interfaces in ledger. No generic rewrite of old impact modules.
New generation resource review_part_uk_v3.txt. Existing generation/stages.py adds isolated review_part output validator. Provider request constructed through impact_part native schema so existing local counter admission can be qualified without broadening it.
Existing RunRequest gains optional impact_protocol (legacy default retained). Web impact preview/start select3 explicitly. ContextView/freshness adds separate review acceptance overlay; old impact readers remain versioned.

### Task1: durable reports and acceptance

Files: review/models.py, review/store.py, storage/context_view.py, storage/snapshots.py, impact/planning.py; tests/review/test_store.py; SPEC/traceability.
Interfaces: `capture_scene(repo,scene_id)` returns exact targets/binding; `current_acceptance(view,version_id)` checks saved target/source binding and proof/authority; `publish_scene(repo,run_id,report,authority,operation_id)` atomically publishes per-material acceptances and checkpoint. No long transaction during inference.
- [x] RED `test_clean_acceptance_is_bound_to_exact_sources`, `test_author_acceptance_does_not_rewrite_model_report`, `test_operation_id_is_idempotent_and_rejects_payload_collision`, `test_foreign_or_changed_head_cannot_accept`.
- [x] Implement typed scene report/part/concern/decision/acceptance records, immutable IDs, scoped prefix load, CAS and explicit author/model authority. Add overlay only after integrity checks; baseline id visible to dependent review snapshots. Legacy values unmodified.
- [x] GREEN target tests; run old impact storage/validity tests. Expected all pass.
- [x] Add OpenSpec REVIEW-SESSION scenarios/traceability for completed Task1 behavior, commit.

### Task2: bounded wire3 search and proofs

Files: review/planning.py, review/wire.py, review/proofs.py, review/context.py (if needed), generation/stages.py, resource; tests/review/test_parts.py.
Interfaces: `prepare_scene(repo,scene_id)` freezes targets, documents/passages and planner snapshots; `next_part(repo,session,results)` constructs deterministic delta/check/synthesis task and ContextBundle; `validate_part(raw,part)` returns references-only normalized output; `verify_part(repo,attempt,part)` validates owner/run/body/raw/result. Task result limits are explicit and replayed.
- [x] RED `test_parts_cover_all_source_and_target_intervals`, `test_current_only_check_and_scoped_refs`, `test_no_quote_expansion_in_output`, `test_incomplete_or_unknown_ref_cannot_accept`, `test_replay_requires_exact_api_body`.
- [x] Implement separate delta/check/synthesis schemas, code-owned global addresses and model short aliases; current-only rules for check, carried exact refs for synthesis. Immutable task identities; multi-part construction under actual input/token/schema budgets. Concerns inherited by code, not recopied by model.
- [x] Integrate `review_part` with stage persistence/accounting, refusal/error/raw result saving. Provider JSON schema built through existing request builder; no registry receipt.
- [x] GREEN plus legacy wire1/2 replay/token tests. Expected all pass. SPEC/traceability+commit.

### Task3: sequential executor and memory checkpoints

Files: review/readiness.py, review/runner.py, generation/worker.py, run_models.py; tests/review/test_runner.py.
Interfaces: `readiness(repo,request,run=None)` produces protocol3 preview; `execute(worker,run_id)` drives per-scene phases; author acceptance leaves pending_memory; memory uses existing build_context/execute_stage and verified result reuse.
- [x] RED `test_clean_advances_and_findings_pause`, `test_next_scene_prepared_after_author_edit`, `test_resume_after_memory_failure_keeps_author_acceptance`, `test_cancel_and_crash_do_not_repeat_completed_attempt`, `test_prefix_memory_uses_only_current_past_prose`, `test_order_change_pauses`.
- [x] Add protocol3 enqueue/resume/dispatch branch. Fixed scene order, fresh current-scene plan, skip missing/current material without calling model, durable search part checkpoint. No model dispatch from page load or author disposition alone.
- [x] Memory prerequisite walk uses current sequential prefix; no implicit historical consent. Failed stage stores pending_memory and halts; settings update applies at next stage, active immutable request remains pinned. Current tariff/story/session cap before every paid call; preview does not invent exact future call count.
- [x] GREEN targeted runner, accounting, cancellation, memory/legacy tests. SPEC/traceability+commit.

### Task4: author decisions and API

Files: review/decisions.py, web/routes_impact.py (or isolated routes_review.py), storage commands; tests/review/test_api.py.
Interfaces: decision preview returns report/scene/head/source fingerprint; decisions command accepts dispositions with operation_id + expected fingerprint; finish command validates current heads and schedules memory/next without same-scene model re-search.
- [x] RED `test_reject_all_accepts_and_queues_next`, `test_partial_dispositions_wait`, `test_finish_after_edits_queues_memory`, `test_stale_preview_and_foreign_run_rejected`, `test_repeated_decision_post_is_idempotent`.
- [x] Implement preview/decision/finish endpoints, durable author acceptance for current material heads and source basis. Prefer explicit bulk actions; reject/no-change/repair completion visible separately. Do not mutate completed model output into no_impact.
- [x] GREEN API tests and legacy impact API. SPEC/traceability+commit.

### Task5: review workspace UX

Files: web/static/review-session.js, impact.js, runs.js, workspace navigation, templates/styles/i18n resources; tests/web/browser/sequential-review.spec.mjs; browser server synthetic fixtures.
Interfaces: protocol3 preview/start returns session; scene report renders concern source/target excerpts and per-item decisions; workspace follows session SSE only when buffer safe; reload/settings return restores persistent phase/dispositions.
- [x] RED browser desktop/mobile tests: auto-clean progress, concern pause/reject-all, select fixes/edit/finish, dirty buffer protection, restart/settings return, failed memory retry, UA/EN.
- [x] Implement clear distinction between current scene acceptance and memory stage, no confirmation for clean result, explicit author finish for repaired prose; ordinary writer/editor operations remain available during author pause. No implicit generation on checkbox change.
- [x] GREEN browser and JS checks; neutral screenshots if layout needs documentation. SPEC/manual traceability/UA+EN guide+commit.

### Task6: final qualification, review and deployment

Files: SPEC, docs/verification/traceability/manual, docs/local-models or review guide, progress/backlog/STATUS; no unnecessary production changes.
- [x] Check SPEC requirement/scenario coverage, UA/EN documentation, backup/fsck of new record namespaces and legacy replay. Add missing meaningful tests.
- [x] One fresh whole-feature review per executing-plans; apply Critical/Important findings in one RED→GREEN batch, ledger rulings.
- [x] `python scripts/check_docs.py`, appropriate full `python scripts/verify.py tests -q` on frozen source, required frontend build/browser suites; no claim from collection alone.
- [x] Neutral local smoke of new response contract/scene workflow (no author book). Qualify new local tokenizer binding only against actual usage before explicit approved activation; preserve old profiles. Record scope and model quality limitations.
- [x] Fresh safe-state before main server restart; verify live HTTP/config and no automatic bookrun. No SQL migration or paid calls unless required/approved. Local commits, no unsolicited push/PR.

## Execution record

Implementation uses current feature checkout per existing user choice. No new worktree. Ruling: owner approved design and requested continuation; earlier instruction to implement after planning without repeated confirmation applies, so proceed inline rather than another plan-method question. Any new substantive product option still goes to owner. Plan self-review: all design sections mapped above; remaining helper names/layout are implementer choices, no new product policy.

Execution ruling: final storage-boundary regression moved SQLite implementation to storage/review_store.py behind Repository.review; review/store.py is a facade. No whitelist/test weakening. Final review fixes use regression tests for author memory/forwarding, unresolved transports, saved-answer/settings recovery and operation suffixes. Additional integration regressions cover capability gating, author source names, post-search external changes and progress/retry visibility.

Final evidence27.10: verification-bn4igijt1277PASS/1SKIP, source unchanged during full run;66browserPASS, frontend buildPASS; independent final review3Important+1Minor fixed with regression coverage, storage boundary fixed without relaxing tests. Local smoke3valid responses73.04s; qualified profile activated only after owner approval. Main server restarted after fresh safe-state, launcher33900/server26996, HTTP200/capabilities[1,2,3], no active/model bookrun. Post-verification edits are execution bookkeeping and trailing-blank cleanup in a test; implementation behavior unchanged.
