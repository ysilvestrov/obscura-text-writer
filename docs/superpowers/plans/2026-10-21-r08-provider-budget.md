# R-08: реалізація обліку провайдерів і бюджету

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans.

**Goal:** Усі cloud completion проходять явний бюджет, атомарний резерв і чесний reconcile.
**Architecture:** billing models/service + storage ledger; спільний provider
accounting runtime під наявними streaming/evaluation gateway, без змішування
літературних схем. UI/CLI керують тим самим контрактом.
**Tech Stack:** Python/Pydantic/Decimal/SQLite app_settings/FastAPI/vanilla JS.
**Spec:** docs/specs/changes/R-08-provider-budget.md.

## Global Constraints
- Явний scope cap; optional run cap. Немає постійного історичного $1.
- Ручний тариф із джерелом/expires; official cache24h.
- Повна usage може зменшити reserve; estimate не є provider actual.
- Unknown залишає reserve; retry не звільняє попередній виклик.
- Local/Codex unpriced; no retries/fallback; R-04 blocks збережені.
- Ledger у SQL2 app_settings; SPEC.MD з кодом у тому самому коміті.
- Жодних платних тестів або налаштувань живого авторського scope.

## Review Focus
- POST або CLI-шлях, що обійшов accounting; повтор одного call ID.
- Скасування/збій між reserve, sent і settle; втрата отриманого тексту.
- Конкурентні резерви, дробові ціни, invalid/expired тариф.
- Venice DiEM/USD0, missing/partial usage і провайдерський overrun.
- Власність API, dirty settings, refresh/restart та випадкова зміна ліміту.

### Task 1: Дані й атомарний ledger
- [x] RED tests/billing/test_ledger.py: limits, manual tariff, invalid Decimal,
  concurrent reserves, duplicate call, estimate/actual/unresolved, retry.
- [x] GREEN billing/models.py і storage/billing_store.py, Repository facade.
- [x] SPEC data/requirements, targeted tests.

### Task 2: Price та спільний provider accounting
- [x] RED tests/billing/test_runtime.py: офіційні catalog units/expiry,
  manual precedence, top-level Venice cost, OpenRouter cost, no context fail.
- [x] GREEN billing/pricing.py, billing/service.py, providers/accounting.py;
  client/capability reuse і no-post-on-denial.

### Task 3: Generation/Evaluator/standalone/calibration
- [x] RED gateway/worker/CLI tests на blocked-before-POST, normalized cost,
  release/reconcile, transport failure, no retry, refusal block.
- [x] GREEN gateway accounting binding per attempt/case; CLI budget args,
  budget CLI setup. Legacy local/Codex працюють без USD policy.
- [x] Update exact request/metadata та diagnostics без витоку.

### Task 4: API/UI та підтримка даних
- [x] RED API revision/ownership, summary/price/reconcile, fsck/backup tests.
- [x] GREEN routes_budget, settings/workspace budget panel, readiness guards.
- [x] Browser desktop/mobile без авторських даних; docs і SPEC.

### Task 5: Приймання
- [x] Цільові та повний offline suite (loopback TestClient потребує дозволеного
  середовища; sandbox socketpair може зависати).
- [x] Незалежне read-only review, Important fixes RED→GREEN.
- [x] Wheel, SPEC/tests/документація, окремий локальний коміт і журнал.

## Журнал

21.10.2026: власник обрав усі три бюджетні політики. Специфікація та план
підготовлені; виконання у цьому чаті за чинною вказівкою без додаткової згоди.


## Докази й обмеження

- Offline RED→GREEN: явний cap, конкурентний резерв, Decimal/строк тарифу,
  run cap, DiEM, невідома usage, backup/restore. Нові cloud tests отримують
  справжній ізольований ledger; виробничого bypass немає.
- Незалежне review виявило й відтворило три Important: активну CLI-звірку до
  нуля, знищення відповіді malformed usage, змішування часткових snapshots.
  Усі виправлено та перевірено regression tests; повторне review без Important.
  Minor неправильного unpriced scope також відтворено RED і виправлено.
- OS per-call lease перевірено також аварійним виходом дочірнього процесу:
  lock звільняється, sent reserve лишається. CLI root lock зберігає R-02 exclusion.
- Desktop1440 і mobile390: збереження cap/default run cap/manual tariff,
  порожня history, поле наступного запуску; без JS errors/overflow.
  Скріншоти синтетичного інтерфейсу перевірені. Власний сервер8879 зупинено.
- Wheel зібрано bundled setuptools; перевірено billing package, budget.js та
  storygen-budget entrypoint. Встановлення wheel окремо не виконувалося.
- У venv немає setuptools; pip також натрапив на обмеження temp sandbox.
  Збірка напряму на наявному bundled build backend не потребувала мережі.
- Платних модельних викликів не виконано; авторський data-dir і сервер не
  змінювалися. Консервативний грошовий reserve залишається евристикою,
  а розрахунок usage — оцінкою, не підтвердженням зовнішнього рахунку.

- Фінальний повний прогін: **489 passed, 1 skipped, 73.98s**;
  artifacts/r08-verified.log. Пропуск — Windows symlink privileges.
