# R-28e — Derived coverage budget fix

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline. Owner reported error; bugfix authorized. No new model calls or automatic book dispatch.

Spec: docs/specs/changes/R-28e-derived-coverage-budget.md.
- [x] RED real-shape wire2 derived IDs overflow vs model-owned cap; wire1 unchanged; evidence/target/raw overflow still fail.
- [x] Shared result_budget helper for validator/packing, detailed size error; no wire/body/schema change, frozen proofs remain compatible.
- [x] RED failed/stop reuse on explicit Continue, strict original body/context/owner validation, audit history, unchanged partial/usage, no duplicate API; no recovery for refusal/length/other failure.
- [x] Implement copy-verify-save recovery; offline validate real failed response without production mutation.
- [x] SPEC/traceability/UA+EN docs; one final reviewer/fix batch; appropriate tests+verify/check_docs.
- [x] Fresh safe-state restart; preserve current run as failed until author Continue; local commit, no push/bookrun.

Final review: Important — перевірки чинних джерел/цілі/налаштувань до recovery save; виправлено, два тести source/settings RED→GREEN. Targeted12PASS. Фінальний verify:1240PASS/1skip, source_changed=false, artifacts/verification-y9fm51fo/result.json. Після явної згоди hidden server14144/4448, HTTP200;0active/schema4; production run лишився failed/cursor1of78, друга відповідь перевірена offline без mutation/inference.
