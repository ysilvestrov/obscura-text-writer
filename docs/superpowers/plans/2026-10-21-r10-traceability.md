# R-10 — План реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Реалізація в цьому чаті за раніше наданою згодою власника без додаткового підтвердження.

**Goal:** перевірні зв’язки сценаріїв SPEC та чесний статус фактичних тестів.

**Architecture:** два незалежні інструменти розробки: статичний валідатор структури/посилань і runner pytest із результатом за свіжим XML. SPEC залишається контрактом, JSON — індексом перевірок, STATUS — датованим свідченням.

**Tech Stack:** Python 3.10+, stdlib AST/JSON/XML/subprocess, pytest; нових залежностей немає.

**Spec:** docs/specs/changes/R-10-spec-traceability.md.

## Global Constraints

- Документація українською, OpenSpec markers English.
- Без платних викликів, міграцій, читання авторських даних або запуску моделей.
- Нові інструменти не імпортуються runtime-застосунком.
- SPEC та відповідний код в одному наборі змін/коміті; current checkout.

## Review Focus

- Матриця не видає опис ручного кроку або AST-наявність тесту за успіх.
- Параметризовані/async/class tests і помилкові marker не губляться.
- Старий XML або exit≠0 не дають зеленого STATUS.
- Фрагменти Markdown/anchors/шляхи перевіряються без виходу за repository.
- Історичні цифри лишаються датованими, current статус має точний command/snapshot.

## Task 1 — Валідатор і стабільні ID

- [x] Тести tests/test_spec_traceability.py: негативні synthetic documents, markers, links, tests.
- [x] RED до появи scripts/check_docs.py; реалізувати AST і Markdown checker, GREEN.
- [x] SPEC ID/зміст, конкретна матриця всіх сценаріїв, ручні процедури; перевірити актуальне дерево.

## Task 2 — Звіт виконання

- [x] Тести tests/test_verification_report.py: XML/result/collect-only/stale output.
- [x] RED; scripts/verify.py, актуальний STATUS, GREEN.
- [x] ADR, історичні позначки, README/CONTRIBUTING/правила й журнал.

## Task 3 — Приймання

- [x] Повний послідовний pytest через verify.py; check_docs; git diff --check.
- [ ] Незалежне рев’ю цілого пакета; Important/Critical виправити RED→GREEN.
- [ ] Записати evidence й зробити локальний коміт без push.

## Журнал

Початок: HEAD c7dcf62, чисте дерево. R-10 — перший незавершений пакет беклогу. Власник обрав помилку документаційної перевірки за missing mapping. Питання повторного погодження плану не ставиться: власник раніше явно доручив імплементувати підготовлений план у цій сесії.

Task 1–2: RED→GREEN для checker та runner; 61 passed у цільовому наборі (.pytest-tmp/r10-focused). Наявні 75 вимог/112 сценаріїв, конкретні automated mapping і 6 ручних mapping з причинами. Перший частковий verify створив справжній STATUS, не collection. Фінальне свідчення повного suite записується runner у docs/STATUS.md; незалежне review ще триває.


Final review: незалежне рев’ю розпочато; reviewer повідомив про два підтверджені ризики (суперечливі JUnit counters та fake anchor у не-Markdown процедурі), але завершення рев’ю перерване лімітом використання сервісу. Фінальну перевірку решти пакета проведено автором; це не повне незалежне рев’ю.

Final: fixed JUnit counters та non-document manual anchor — RED→GREEN у test_contradictory_suite_outcomes_are_not_success/test_manual_procedure_cannot_use_non_document_with_fake_anchor. Додатковий статичний контроль явно noncollected __test__=False/fixture — RED→GREEN. 51 passed у tests/test_spec_traceability.py + tests/test_verification_report.py (.pytest-tmp/r10-review-green). Жодних minor або відхилених findings не зафіксовано. Статичний AST-check не замінює фактичну pytest collection/виконання; довільні динамічні зміни pytest через plugins не інтерпретуються.

Реалізація й документація завершені. Фінальний повний прогін виконує scripts/verify.py; фактичний результат, команда, commit і hash — у docs/STATUS.md, а не передбачений у цьому плані. Локальний коміт робиться лише після exit=0 та check_docs.py. Push не виконується.

Task 3: повний verify.py завершився exit=0: 733 passed, 1 skipped (artifacts/verification-3e_5v8bc/result.json). Check_docs.py GREEN. Незалежне рев’ю лишається неповним через сервісний ліміт, як зазначено вище. Зміна цього запису після прогону не переписує свідчення попереднього вихідного hash у STATUS.
