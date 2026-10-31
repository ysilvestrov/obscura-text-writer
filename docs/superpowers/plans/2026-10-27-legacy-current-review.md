# Перевірка legacy текстів — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans inline; один свіжий фінальний reviewer. Власник погодив режим, раніше обрав поточну гілку й виконання без додаткового підтвердження плану.

**Goal:** прибрати тупиковий missing-baseline blocker через чесну перевірку current consistency.
**Architecture:** окремий review capture adapter із явним mode; pure opt-in baseline override в impact capture, SQL/authority лишаються за Repository.review. Незмінні legacy wire1/2 й старі protocol3 bodies.
**Tech Stack:** Python/Pydantic/SQLite, існуючий protocol3 та vanilla JS UA/EN.
**Spec:** docs/specs/changes/R-28k-current-consistency-review.md.

## Обмеження й фокус рев’ю

- Не змінювати старі version snapshots; не обходити integrity/ownership/cycle/memory blockers.
- Current consistency має включати prior prose та чинні плани, без future prose; зміна source/head повертає stale.
- У змішаній сцені mode окремий для brief/prose; delta лише для historical targets.
- Old reports без mode map мають незмінні hash/body; нові report/proof/CAS перевіряють mode.
- Підготовка й reload не викликають модель; жодних paid/book calls без явної дії.

## Єдиний пакет реалізації

Files: review/capture.py, impact/planning.py (опційний baseline тільки для нового adapter), review/{planning,readiness,wire,proofs,runner,decisions}.py, storage/review_store.py, web routes/static/i18n; SPEC/traceability та UA/EN guides.

- [x] RED: legacy target без бази ready/current mode; current-only no-delta/end-to-end acceptance; source change/CAS; foreign/missing/invalid source не обходиться; old exact request replay; UI показує mode.
- [x] Implement adapter, mode map у нових plans; об’єднаний scene selector для planning/readiness; exact mode-aware recapture у storage/runner/decisions. Документувати й перевіряти mode у proof replay.
- [x] GREEN відповідні review/impact/storage/memory/API тести та browser desktop/mobile; check_docs та verify.py, без модельних витрат. One fresh review, важливі finding через RED→GREEN.
- [x] Read-only preview робочого твору: готовність/контекст або адресовані справжні blockers, no dispatch. Свіжий safe-state перед перезапуском, HTTP smoke й no bookrun. Local commit зі SPEC та документацією; без push/PR.

Підсумок: verification-v4p8q2ak1293PASS/1SKIP, source_changed=false;24browserPASS, build/check_docsPASS. Фінальне рев’ю1Important виправлено двома RED→GREEN шляхами,2діагностичні Minor у беклогу. Основний сервер оновлено після явного safe-state; HTTP200, preview більше не блокується missing baseline. Залишається справжній тарифний blocker memory; моделі книги не запускалися. Після verify змінювалися лише підсумкові документи, перевірений код незмінний.
