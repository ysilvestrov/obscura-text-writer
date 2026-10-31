# R-13 Maintainability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Виконання в поточному чаті та гілці, як обрав власник.

**Goal:** Читабельні переходи виконання, публікації та залежностей без зміни поведінки.

**Architecture:** Межі компонентів незмінні. Чотири існуючі модулі отримують розгорнуті statements і анотації відомих типів; ті самі with/try/умови/SQL/call order.

**Tech Stack:** Чинний Python3.10+, ast/tokenize, pytest. Без нових бібліотек чи форматерів у залежностях.

**Spec:** docs/specs/changes/R-13-maintainability.md.

## Global Constraints

- Рівно generation/worker.py, generation/stages.py, storage/snapshots.py, storage/copyedit_store.py.
- AST виконуваного коду до/після тотожний, анотації — окремі дозволені метадані.
- Повний suite до/після; тексти/SQL/коментарі/блокування/транзакції збережені.
- Без продуктового функціоналу, міграцій, API/UI-змін чи платних викликів.

## Review Focus

- Inline if із кількома діями: усі дії лишаються під умовою (AST body).
- continue/return після checkpoint не змінює with/try меж (AST nested structure).
- Cancellation/recovery лишає порядок save/event/notify (AST statement order).
- Анотації не вимагають нових імпортів і не змінюють defaults (AST normalization + імпорт/pytest).
- Рядки SQL/діагностики й safety comments не переписуються (constants/comment token comparison).

## Task 1: базове свідчення

- [x] Запустити python scripts/verify.py до runtime-правок; зафіксувати exit/counts/artifact.
- [x] Зберегти оригінали чотирьох файлів у artifacts/r13-maintainability та підрахувати inline/semicolon OP, довгі рядки. Артефакти не містять авторських даних.

## Task 2: механічний рефакторинг

- [x] Розгорнути прості statements у чотирьох файлах. Не виділяти нові функції/класи, не переносити імпорти чи SQL.
- [x] Оформити довгі сигнатури, виклики та складні умови без зміни AST.
- [x] Додати анотації тільки там, де тип і return доведені поточним кодом, без нових імпортів.
- [x] Перевірити нормалізований AST, константи й коментарі проти базового знімка; звіт у artifacts/r13-maintainability/equivalence.json. Відхилити будь-яку нетотожність виконуваного AST.

## Task 3: приймання

- [x] Незалежне рев’ю чотирьох diff на дотримання механічних меж.
- [x] SPEC: запис супроводу без нових runtime-вимог; оновити беклог і журнал.
- [x] check_docs.py, git diff --check і повний verify.py після runtime-правок.
- [x] Окремий локальний коміт R-13; без push. Наступна задача за чергою — R-19.

## Журнал

22.10.2026: обрано модулі за щільністю переходів і наслідками помилки в locking/CAS. Ruling: не вводити форматер у залежності; використовувати tokenize/AST для одноразового механічного проходу й доказу тотожності. Нові зміни архітектури не виводяться з цього пакета.

22.10.2026: baseline повний suite — 798 passed/1 skipped, artifacts/verification-48fd0ju1/result.json. Оригінали й метрики в artifacts/r13-maintainability/before/. Механічний tokenize-прохід прибрав35 semicolons і18 inline bodies, далі вручну оформлено критичні умови/сигнатури/виклики. Long lines понад120: 61→24; відомі типи додані без імпортів. Точний normalized AST і коментарі тотожні для кожного файла; наявні анотації не змінювалися, нові перелічено в equivalence.json. Цільові регресії залежностей, горизонту й редакторського прийняття: 48 passed. Нових runtime-тестів на форматування не додано: поведінку перевіряє чинний suite, структурну тотожність — окремий артефактний аудит.

22.10.2026: незалежне рев’ю проти Git HEAD підтвердило тотожність executable AST і коментарів, коректність анотацій та сумісність із граматикою Python 3.10; actionable findings немає. Повний після-прогін: 798 passed, 1 skipped, exit 0; artifacts/verification-6g3fgrhj/result.json, source_changed_during_run=false. Документаційні зміни приймання внесено після прогону; runtime-код після нього не змінювався.
