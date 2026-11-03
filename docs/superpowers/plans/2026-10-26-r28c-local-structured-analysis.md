# R-28c Local Structured Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Кваліфікований local9B профіль виконує structured impact без переписування машинних ID/quotes моделлю.
**Architecture:** Explicit local_disable_thinking plus wire_schema_version2 for local structured chunks; versioned raw wire→PartResultV2 normalization. Manifest owns exact registry/aliases; legacy wire1 hashes/API proofs retained.
**Tech Stack:** Existing Pydantic/FastAPI/ES modules/SQLite4, no new deps.
**Spec:** docs/specs/changes/R-28c-local-structured-analysis.md, user approved spec+integration26.10.2026.

## Global Constraints

- Inline existing checkout; no PR/push/cloud calls. Separate final reviewer only.
- Role change only planner after tests; preserve texts, raw attempts, old proofs and other roles. No automatic book run.
- Native none only when explicit local flag; default false backward-compatible. Context matches loaded32768.
- Exact coverage/evidence/chronology/budgets/CAS remain; schema is not content filtering.
- SPEC+traceability+UA/EN guide and actual verify/check_docs results in same changes.

## Review Focus

- New default bool/wire field must not alter legacy hashes or replay: Task2 legacy fixture.
- Quote aliases cannot cross source/target kinds or ownership: Task2 wrong-reference tests.
- Child uncertainty and inherited findings survive normalization: Task2 reducer tests.
- Registry/schema overhead included before packing, unknown child placeholders conservative: Task3 measured requests.
- Browser save retains flag and affects only current role: Task1/4 route/UI tests.

### Task1 — Local transport/configuration

Files: providers/models.py, requests.py; evaluation/models.py; web/app.py, static/settings-connection.js/settings.js/i18n.json; tests/providers/test_local_reasoning.py.
Interfaces: local_disable_thinking bool false in provider/evaluator; requests emit reasoning_effort=none only local true. Existing connection component controls both schemas. Legacy settings proof equality normalizes defaults.
- [x] RED transport defaults/explicit local/other providers/evaluator roundtrip.
- [x] Implement flag, serialization, UI/checks; GREEN tests.

### Task2 — Exact reference wire contract and legacy proofs

Files: impact/chunk_models.py/chunk_requests.py/chunk_validation.py/chunking.py; create impact/reference_wire.py; tests/impact/test_reference_wire.py; legacy fixture tests/impact/fixtures/legacy-part-wire1.json.
Interfaces: settings_for_manifest(m), manifest_stamp(m) legacy-aware; build_wire(m,payload,planning)->(wire_payload,registry,maps); wire_schema(...); normalize_wire(raw,m,task,results)->PartResultV2. PartResultV2 target_quotes typed, original PartResult remains immutable wire1 model. New manifests choose version2 for local+json_schema or local flag, old absent version1 retained. Provider fragments select exact wire schema only when supplied.
- [x] RED legacy fixture validation/hash/API replay; disallowed refs; quote windows cover text; aliases stable; new findings and inherited preservation; uncertainty.
- [x] Implement pure helpers and proof version dispatch, keep direct original validation gates; GREEN tests.

### Task3 — Context/queue measured integration

Files: generation/impact_chunk_context.py/stages.py/impact_chunk_runner.py; prompt impact_part_uk_v2.txt; tests/impact/test_reference_runner.py and prior native legacy test.
Interfaces: request_for(m,payload) versioned wire/schema; parser stages/proof reader both decode via same normalizer; planning reserves full unknown child registry and enum overhead; raw and canonical caps enforced. New prompt explains aliases, no long-ID rewriting.
- [x] RED measured native body limits, complete run, stop/cancel/refusal/recovery, artifact raw/API matching and wire1 native backward compatibility.
- [x] Implement; GREEN targeted tests and local smoke on isolated inputs, no production publication.

### Task4 — Documentation, verification and deployment

Files: SPEC.MD, traceability.json, docs/local-models.md, progress/backlog, browser tests and UI preview wire version.
- [x] Document requirements/scenarios and UA/EN instructions, legacy compatibility and limits.
- [x] Browser local control/read-save plus reference run; scripts/verify.py full suite/check_docs; one final fresh review + one fix batch.
- [x] Local commit; fresh safe-state/0active restart; CAS update planner only, role context32768/output4096/temp0.1/json_schema/local thinking off. Verify read-only preflight, no automatic model run. Record actual smoke metrics and limits, no claims of literary quality.

## Rulings

- User authorized spec and integration; no further plan confirmation.
- Raw new wire uses evidence IDs rather than literal quote alternatives, normalized exact quotes retain the existing canonical audit contract. This avoids large oneOf schema duplication and makes budgeting feasible on32K.
- Known coverage is owned by delivered immutable tasks, not a model self-report. V2 still requires complete proof DAG/stop before any overlay.
- Existing child findings are copied by code; model returns only additional findings. New references must be from actually delivered registry; no fuzzy fallback.


Виконання: targeted impact/providers106PASS; після review3 RED→GREEN, фінальний fullverify1205PASS/1skip, source_stable (artifacts/verification-7pcpawtj). Browser14 desktop/mobile PASS. Документація вимірів доповнена після fullverify без зміни runtime коду. Task4 restart/CAS профілю ще виконується; позначка виконаних перевірок не є підтвердженням завершеної поставки.

Поставку завершено: hidden restart35808, CAS planner175→176,131072/4096/json_schema/local thinking off; інші ролі/промпти незмінні. Live preview557calls/20,66с, нових model runs0. R-28c закрито; вимірювання скорочення викликів — окреме продовженняR-28d, без непогодженої зміни proof contract.
