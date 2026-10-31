# R-28d — Qualified Local Token Counting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Зменшити локальну перевірку поточного знімка книги з557 до приблизно142calls без втрати джерел, за кваліфікованим tokenizer і незмінного proof contract.
**Spec:** docs/specs/changes/R-28d-qualified-local-token-counting.md (реалізацію й активацію після тестів власник погодив26.10).
**Architecture:** Optional offline CPU counter, hash-qualified local profile, frozen manifest estimator snapshot; conservative fallback. No SQL migration, no provider/API response change, no automatic book run.
**Scope:** local9B/loopback/impact_part/json_schema/reasoning none/system-user text only. Existing128K planner remains active throughout research; no paid calls.
**Baseline:**7652f9d,1205PASS/1skip,14browserPASS. R-28c source complete and deployed. Experiments documented in docs/research/2026-10-26-local-token-counting.md.

## Review focus

- Exact request-template binding, special tokens and no reasoning/template drift.
- Hash/path/symlink/oversized-file handling; no arbitrary HTTP filesystem path; offline sandboxed template.
- Actual known payload count +512; unknown children UTF-8 worst-case, not optimistic repeated emoji tokenization.
- Frozen counter metadata affects new manifest identity; legacy wire1 and wire2 fixtures replay unchanged when metadata absent.
- Missing/mutated files or unsupported shape fallback to conservative estimate, old proofs remain readable offline.
- No output cap/coverage/CAS weakening; registration/qualification metadata contains no text or secrets; backup retains profile artifacts.

### Task1 — Pure counter and qualified profile store

Files: create src/storygen/token_budget/local_counter.py and local_profiles.py; pyproject.toml optional local-tokens dependency; tests/token_budget/test_local_counter.py.
Interfaces: count_known(body,profile)->int; predict_body(body,profile)->estimate; profile fingerprint from model/endpoint/tokenizer/template/system hashes/revision. Scope checker rejects unsupported stages/tools/images/reasoning. Use optional tokenizers + sandboxed Jinja; no network. Profiles under repo.root/local_tokenizers, immutable content-addressed artifacts, safe atomic metadata write; explicit active flag.
- [x] RED fixture known counts, shape/hash mismatch, missing deps/files, unsafe template/path and admission; no inference/network.
- [x] Implement CPU counter/store with bounded cache; GREEN. Unknown-child reserve tested adversarially and actual dispatch count rechecked.

### Task2 — Registration CLI and qualification

Files: create src/storygen/token_budget/local_cli.py, project script storygen-local-tokens, tests/token_budget/test_local_counter_cli.py.
Interfaces: register local tokenizer/template files + saved request/observed_usage evidence; verify exact reproduction, save only evidence hashes/counts/version, no manuscript. Activation separate explicit flag/command. Only local administrator CLI accepts paths; copy into controlled data root and validate before replacing active metadata. Existing empirical profile activation unchanged.
- [x] RED wrong usage/hash/model/shape blocks qualification/activation; inactive profile stays inactive; qualified registration roundtrip and backup/restore.
- [x] Implement; GREEN. Prepare real profile from saved request13590/usage13590 and neutral controls, no new paid requests.

### Task3 — Versioned impact budget integration

Files: impact/chunk_models.py/chunking.py, generation/impact_chunk_context.py; tests/impact/test_local_token_counting.py. Use repo.root for profile lookup.
Interfaces: optional manifest counter snapshot; None excluded from legacy fingerprint for both wire versions. New plans select only activated matching profile. measure_payload uses pinned qualified counter, otherwise current estimator with reason; complete exact body measured immediately before dispatch. Read/proof replay unchanged and does not require tokenizer. No new response schema.
- [x] Capture neutral legacy wire2 fixture BEFORE source changes (already artifacts/r28d-legacy-wire2-fixture.json); copy to tests fixture and RED replay bothwire1/wire2.
- [x] RED qualified/fallback context boundaries, complete source/target coverage, cancellation/recovery, synthetic proof replay; small context not silently exceeded.
- [x] Implement; GREEN. Compare actual book preflight with root role overridden only in isolated process; compare calls and total input work.

### Task4 — Docs, review, verification, activation

Files: SPEC.MD+traceability, docs/local-models.md UA/EN, progress/backlog, STATUS through verify.
- [x] Document qualification/activation/fallback/backup/limits and full-coverage invariant. Counter correctness is not semantic model quality.
- [x] One final fresh review and one RED→GREEN fix batch; appropriate regression suite/check_docs/verify with stable source.
- [x] After explicit owner answer, activate qualified profile and CAS-change only planner max_input_chars100000→500000; context131072/other roles unchanged; output8192 after measured canonical-cap failure, as recorded below. Fresh safe-state for any required restart.
- [x] Read-only live preview, runs count unchanged; no automatic book run; logical local commit, no push unless requested.

## Rulings from measurements

- Larger output reserve684calls is worse and was not activated.
- Removing derived coverage yields only533; leave proof/output caps unchanged.
- Exact tokenizer rendering matched one actual API request exactly13590vs13590; qualification must bind files/template/shape before production activation.
-142calls is a measured geometry, not a promised fixed value or faster latency for every call; future edits/model changes may change it.

Виконано26.10.2026: fullverify1228PASS/1skip/source_stable, check_docsPASS, review1finding fixedRED→GREEN. Counter controls859/13590/24602 exact. Фінальний output reserve8192 (замість початкового4096) після реального canonical2782>2048; поточні guards не змінені. Native8192 stop/fullvalidatorPASS/0reasoning/7762MiB. Active counter +planner500000chars/8192output/131072context; інші ролі незмінні. Live78calls/91,19с/0newruns. Жодного book dispatch/cloudcall/SQLmigration.
