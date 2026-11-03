# Контракт доказової перевірки — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Реалізувати погоджений контракт4 без зміни старих доказів і дослідницьких результатів.

**Architecture:** Версійний контракт у наявній послідовній review-сесії. Модель пропонує точні пари, код застосовує авторські рішення та обліковує придатність/покриття; storage зберігає authority атомарно.

**Tech Stack:** Python/Pydantic/SQLite, FastAPI, наявний JavaScript UI, pytest/Playwright; нових залежностей немає.

**Spec:** [Погоджена специфікація](../specs/2026-11-03-review-evidence-contract-design.md).

## Global Constraints

- `impact_protocol=3`, `review_contract_version=4`; пропущене поле зберігає контракт3.
- Exact Unicode offsets/quotes, no fuzzy repair, повне парне покриття i≤j і source×target.
- 10000 задач, фактичні бюджети/ліміти; нових платних викликів немає.
- Partial/unable/invalid не створюють model або author authority.
- Авторські пріоритети append-only, scene/material scope; authority_revision не скидається.
- Чинна SPEC і traceability оновлюються з реалізацією, UA/EN документація узгоджена.

## Review Focus

- CRLF, emoji та повторені цитати: адреси визначаються offsets, а не пошуком підрядка (Task 1).
- Внутрішній конфлікт одного інтервалу й конфлікт однакових уривків різного походження (Task 2).
- Partial кандидат поряд із валідним, вкладений synthesis та explicit repeat (Task 3).
- Зміна/скасування priority після acceptance3/native й після checkpoint (Task 4).
- Старий клієнт/сервер, перезавантаження й UA/EN без inference (Task 5).

## Task 1: Адреси, пріоритети й класифікація

Files: нові `review/evidence.py`, `review/contract4.py`, `tests/review/test_evidence_contract.py`.

Interfaces: `statement(registry, endpoint) -> dict`; `validate_priorities(decisions, statements) -> list[dict]`; `classify_candidates(candidates, registry, decisions) -> dict` із concerns/suppressed/rejected/statements/conflicts.

- [x] Написати тести exact offsets, ролей, пріоритетів/циклів/ланцюжків, ambiguity, information_gap і partial isolation; запустити RED.
- [x] Реалізувати чисті функції та версійні Pydantic envelope, caps; перевірити GREEN.

## Task 2: Версійний wire та геометрія

Files: `review/planning.py`, `wire.py`, нові `review/wire4.py`, `review/planning4.py`, prompt `review_part_uk_v4.txt`; `tests/review/test_contract4_planning.py`.

Interfaces: `prepare_scene(repo, scene_id, contract_version=3)`, `premise_specs`, version-aware `check_specs/synthesis_spec/validate_coverage`; новий wire з done/unable та candidates, без complete/kind.

- [x] RED: i≤j, source×target, task limit, prompt/schema replay, legacy body незмінний.
- [x] Реалізувати пакування та dependencies, authority metadata, scope endpoints, measured budgets; GREEN.

## Task 3: Runner, часткові результати та replay

Files: `review/runner.py`, `proofs.py`, `models.py`, generation review stage integration; `tests/review/test_contract4_runner.py`.

Interfaces: report4 зі execution_state/diagnostics/revisions, model4 normalization; verify report replay від raw; partial report зберігається, run failed без прийняття.

- [x] RED: clean/concern/partial/unable, synthesis inheritance, replay mutation, crash reuse та no auto repair.
- [x] Версійна інтеграція runtime і report, explicit repeat; GREEN.

## Task 4: Транзакції, пріоритети й актуальність

Files: новий `storage/review_authority.py`, `storage/review_store.py`, `repository.py`, `context_view.py`, `snapshots.py`, review decisions/readiness і integrity; `tests/review/test_authority4.py`.

Interfaces: Repository.review commands `priorities`, `priority_decide`; snapshot revisions, `review4` namespace, common freshness gate, legacy0; ідемпотентність operation ID.

- [x] RED: exact owner/hash/CAS, append-only replacement/revoke, stale native/review3, contract3 blocker, report4 backup/fsck.
- [x] Реалізувати транзакції й інтеграцію читання/authority, без SQL міграції; GREEN.

## Task 5: API, UA/EN UI та документація

Files: `run_models.py`, review/impact routes, `web/static/review-session.js`, `impact.js`, локалі й наявні templates; користувацькі UA/EN інструкції.

Interfaces: capability `[3,4]`, versioned preview/start, priority endpoint із цитатами/scope/expected_revision, report з allowed actions.

- [x] RED: API version validation, priority command/readback, partial read-only, no reload dispatch.
- [x] Реалізувати вибір нового формату, цитати/статуси/пріоритети, локалізацію, нейтральні browser checks; GREEN.

## Task 6: Специфікація, перевірки та рев’ю

Files: `SPEC.MD`, `docs/verification/traceability.json`, `docs/STATUS.md`, журнал remediation-progress.

- [x] Оновити чинні Requirements та конкретні test links, відокремити ще не активоване модельне оцінювання.
- [x] `python scripts/check_docs.py`; `python scripts/verify.py tests docs/research -q`; релевантні browser checks.
- [x] Незалежне whole-change review, виправлення важливих дефектів із RED/GREEN; повторити перевірки за потреби.
- [x] Підсумувати реалізоване, фактичні перевірки та обмеження; не запускати новий benchmark/платні виклики.

## Журнал виконання

03.11.2026: старт у managed worktree `review-evidence-contract` від `2716f303`. Вихідні авторські позначки й research-файли залишені у початковому checkout. До isolated checkout скопійовано лише SPEC, traceability та погоджений design. Реалізація inline за прямим запитом користувача; окремий плановий approval не потрібен. Коміти після перевірок, без сторонніх змін.

03.11.2026 — Task 1: complete. 8 RED→GREEN tests, exact CRLF/Unicode/refs, typed candidates, direct priorities and scope-aware classification.
03.11.2026 — Tasks 2–4 integrated: packed premise i≤j, partial reports, versioned raw replay, append-only priorities/replacement/revoke, common revision barrier. Baseline 50/50 passed after Windows short-temp correction; 72 relevant tests passed, expected nonexistent-story404 corrected separately.
Ruling: pack fitting source pairs together instead of one HTTP call per pair — 23 source intervals otherwise created 276 premise calls and quadratic replay work; all pair coverage remains explicit and verified. Preflight limits work to 100000 candidate pairs when splitting is needed, in addition to 10000 dispatched tasks.
Ruling: contract4 automatic model authority remains blocked until separately authorized semantic model qualification — complete reports are author-reviewable. No new benchmark, provider calls or budget activation.
03.11.2026 — Task 5: new UI/browser2 desktop/mobile passed, author priority selection with exact quotes, UA/EN reload. Whole-change independent code review dispatched; documentation and final verification remain.

03.11.2026 — Independent review found retry/raw authority/delta IDs/premise metadata/counts/unresolved IDs/schema-cap issues; corrected with targeted regression tests. Local4 counter now requires separate native-schema/no-thinking binding; synthetic integration fixtures activate an offline toy tokenizer only. Legacy50 baseline preserved. New wire uses existing impact_part native transport name with a different system hash, preserving qualified-counter scope rules.

03.11.2026 — Task 6: complete. scripts.check_docs та перевірка всіх нових Markdown links пройшли. Повний scripts.verify: 1599 passed,1 skipped,0 failed/errors,558.91s; artifacts/verification-_wo_qkr_/result.json, snapshot не змінювався під час прогону. Короткий basetemp передано штатному run_verification через runner, фактичний argv записано в STATUS/JUnit. Browser:72 попередні сценарії пройшли в широкому прогоні; два нові після виправлення test-fixture import пройшли desktop/mobile. Нейтральні знімки docs/images/review-evidence*.png перевірено візуально, mechanical detector []. Незалежне code review після виправлень: Critical/Important0, висновок artifacts/review-contract4-review.md. Код після повного прогону незмінний; фінальні позначки в плані/журналі — лише документація.
Ruling: локальну гілку зберігаємо для огляду, без merge/push і без перемикання початкового checkout. Існуюче авторське рев’ю/звіт збережено окремим docs commit10f2267; вихідні annotations скопійовано байт-у-байт, не редаговано. Нових model calls0.
