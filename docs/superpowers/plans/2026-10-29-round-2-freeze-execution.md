# Раунд 2: коди відхилень, вторинна метрика та freeze

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Виконання в цьому чаті, у чинній гілці; окремий worktree не потрібний. Новий план деталізує погоджене доповнення й не потребує повторного погодження вже визначених вимог.

**Goal:** Підготувати незмінний research harness для основного прогону з промптом A й окремою описовою вторинною метрикою, не послаблюючи первинний валідатор.

**Architecture:** Незмінні product builder/validator залишаються джерелом запитів і строгого статусу. Research-only діагностика додає коди причин і закритий allowlist для вторинного людського оцінювання; freeze фіксує код, дані, wire contracts і provenance, prepare перевіряє їх без inference.

**Tech Stack:** Python, чинні pydantic/httpx, hashlib/sqlite3/pathlib; нових залежностей продукту немає.

**Spec:** [погоджене доповнення](../../research/2026-10-29-round-2-prompt-freeze-amendment.md), [бріф](../../research/2026-10-28-round-2-codex-brief.md), [початковий план виконання](2026-10-28-local-planner-round-2-implementation.md).

## Global Constraints

- `src/**`, product roles/configs/tokenizers/SPEC не змінюються: це суто дослідницька реалізація.
- Промпт A — єдиний основний для L1–L6/C1/C2 і senior escalation; B/C неактивні. Погоджений C2 schema suffix лишається явною provider-deviation; окремо фіксуються base A і фактичні wire hashes.
- Первинний `invalid` не ремонтується, не стає TP й не зникає зі знаменників. Діагностична копія для доказу eligibility не передається в основний runner/storage як прийнятий результат.
- Вторинний allowlist закритий до holdout: незавершеність `complete=false`; допустимі дублікати джерел. Вузьке поле/комбінація уточнюються власником до freeze. Інші помилки завжди виключають eligibility.
- Вторинні оцінки позначають виконавця, містять окреме рішення власника для КОЖНОГО кандидата й не впливають на пороги або первинне L5-порівняння.
- Бюджет хмари $10 сукупно; збережений ledger продовжується, витрати dev не обнуляються. Ключі/рукописи/raw replies не комітяться.
- Holdout0 до завершення freeze й погодженого resource/budget preview. Подальших prompt probes немає. B7 — лише після основного звіту й рішення власника, перший серед бонусів.
- §6 доповнення містить старий стан L2/L4/L5: actual artifacts/dev-summary вже підтверджують8викликів кожної. Перевіряємо докази й hashes; нові повтори не є потрібними для цього пункту.
- Сторонній `tests/web/browser/save-and-run.spec.mjs` не змінювати/не комітити. Зміни власника в бріфі та нове доповнення зберегти й явно включити до погодженого research набору.

## Review Focus

- `complete=false` разом із невідомим ref/перевищенням бюджету не має маскувати другу помилку.
- Видалення дублів не може приховати schema maxItems, неправильний тип або вихідний бюджет.
- Вторинний правильний зміст не повинен змінити primary outcome, valid count, success threshold або L5.
- Owner review потрібний і для secondary FN/FP, а не лише «правильних» secondary TP; усі кандидати потрапляють у форму.
- Freeze guard має ловити prompt/schema/code/model drift, а resume — зберігати вже отримані відповіді й не викликати їх знову.

## Task 1. Механічна діагностика та вторинна класифікація

**Files:** create `docs/research/round2/validation.py`, `test_validation.py`, `test_secondary.py`; modify `scoring.py`, `transports.py`, `runner.py`, `report.py`, research README/manifest.

**Interfaces:** `diagnose(raw,request) -> {codes,secondary_eligible,contract_defects}`; `validate_response` зберігає strict status і додає `rejection_codes`; `classify_secondary(response,gold,executor_adjudication,owner_adjudication=None)` повертає окремий measurement, provisional до owner review.

- [ ] RED: complete-only, duplicate-source-only, their combination; unknown/missing/wrong-kind refs, other duplicates, malformed JSON/types, length/refusal, concern/schema/budget overflow.
- [ ] RED: input/raw/primary result immutable; shadow eligibility ніколи не приймається як основний текст.
- [ ] GREEN: primary validation незмінна; stable reason codes, full remaining validation on isolated diagnostic copy; fail-closed fallback.
- [ ] RED→GREEN: вторинні TP/FP/FN/TN/question за спільним classifier, executor provenance, усі owner reviews, correction history, secondary records rejected by primary metrics.
- [ ] Додати коди для malformed provider envelopes і transport attempts; не виводити секретні exception strings.
- [ ] Перевірити офлайн, повторно діагностувати збережені dev replies без inference як окремий audit; початкові artifacts не переписувати.
- [ ] Окремий локальний коміт з документацією й фактичним verify/check_docs.

## Task 2. Freeze та prepare без inference

**Files:** create `docs/research/round2/freeze.py`, `test_freeze.py`, frozen snapshots; modify CLI/manifest/README.

**Interfaces:** `freeze(root,...)` створює інвентар snapshots/code commit/hashes без cyclic self-hash; `prepare(root,...)` перевіряє frozen identity й друкує calls/resource/budget preview; не торкається моделей чи платних API.

- [ ] RED→GREEN: mismatch у holdout/A/C/adapter/source/schema/settings/model SHA/dev evidence блокує prepare/resume.
- [ ] Перевірити всі8dev учасників зі збережених slot replies та змінних reasoning/VRAM/load; зберегти підтвердження для L2/L4/L5 замість зайвих викликів.
- [ ] Зафіксувати A і C bonus SHA, provider wire deviations, per-case schema/request hashes, paired L3/L4 load й hardware/runtime/power limitations.
- [ ] Зафіксувати закриті reason/secondary policies, B7-first bonus policy, post-round holdout→dev rule.
- [ ] Зафіксувати явну політику scoring/спільної20%TP panel і transport uncertainty; нерозв’язані рішення не приховувати у freeze.
- [ ] Підготувати immutable run plan на1152primary calls, K1/K2 offline, timing48+warmup6; cloud reserves з actual ledger і тарифами, без неправдивої обіцянки ціни.
- [ ] Коміт freeze/prepare tooling. Фактичний freeze НЕ активувати до завершення Task3 і його рев’ю: інакше реалізація runner змінила б уже frozen code. Після цього — commit harness, окремий manifest freeze і concrete resource/budget preview перед quality.

## Task 3. Основний runner, review forms і звіт

**Files:** create research `experiment.py`/tests і review export/report helpers; modify CLI.

- [ ] RED→GREEN: block rotation, owned model lifecycle/restore, frozen dispatch/resume, no content retry, durable ledger на кожну платну спробу, technical failures explicit.
- [ ] Запис slot reason codes, raw/usage/finish/seconds/VRAM; qualification guards збережені.
- [ ] Сліпі primary adjudication forms; окремо всі secondary candidates для executor й owner. Не видавати pending за правильність.
- [ ] Primary per-draw/aggregate thresholds, FP/miss/flip/neutral-adult, K1/K2/L5; окремий secondary descriptive column без threshold.
- [ ] Провести quality, timing і owner review за погодженими gates; B7 не запускати до рев’ю основного звіту.
- [ ] Незалежне рев’ю всього frozen harness один раз перед основним inference; review не повторюється без нової підстави. Локальні коміти, без push.

**Verification:** `python scripts/verify.py docs/research/round2 -q`, `python scripts/check_docs.py`; повний продукт не змінюється, його UA/EN інструкції не потребують змін. Результати дослідницьких тестів не доводять якість моделей.
