# R-20 — Реалізація видимого маршруту сцени

> Виконання: superpowers:executing-plans у цьому чаті, відповідно до прямого доручення власника «до реалізації» та попереднього дозволу реалізувати план без додаткового підтвердження. Наприкінці — незалежне review.

**Goal:** ручний маршрут із шести етапів та однією безпечною основною дією.

**Architecture:** існуючий Repository/черга/версії залишаються авторитетними. UI використовує спільну межу текстового віджета й реєстр команд save/show/run/review; сервер фіксує явне джерело standalone редактури. Схема БД незмінна.

**Tech Stack:** Python/FastAPI/Pydantic, ES modules, Jinja/CSS, pytest та Node regression harness.

**Spec:** [погоджений R-20](../../specs/changes/R-20-editor-page-design.md).

## Global Constraints

- Шість видимих етапів, включно з планом; навігація не викликає моделей.
- Save→readiness→явний запуск, без дублювання/втрати буфера; невдалий Save блокує inference.
- Джерело редактури draft/prose визначає автор, фіксуються head та version ID.
- Редактура не є новим VersionKind; історія/актуальність/прийняття зберігаються.
- Markdown source round-trip без нормалізації; rich editor/експорт форматування — майбутня R-22.
- Без платних тестів, SQL-міграцій, R-15 або редизайну R-21. Робочий сервер не перезапускати за наявності active runs/незбереженого буфера.

## Review Focus

- Обидва тексти існують: draft запуск не редагує prose; stale/чужа/змінена голова відхиляється.
- Подвійний клік/зміна сцени/введення під час Save чи readiness не створюють зайвого запуску.
- Порожній або частково успішний editor-loop не дає прихованого прийняття.
- Відсутній usage не стає 0; legacy дані не отримують вигаданих токенів/вартості.
- Безпечне повернення з налаштувань, без довільного redirect або автоматичного inference.

## Task 1 — Явне джерело редактури та preview

Files: run_models.py, generation/editor_loop.py, worker.py, web/routes_runs.py, application/statistics.py, routes_statistics.py; tests/generation/test_editor_source.py.

Interfaces: optional editor_source_head=draft|prose + editor_source_version_id у RunRequest для edit_loop; source() перевіряє ownership/kind/head/freshness. Legacy default і pipeline draft незмінні. Readiness та statistics приймають той самий вибір.

- [x] RED: обидві голови, зміна після enqueue, чужа версія, неповна пара полів/неправильний mode, preview джерела.
- [x] Реалізувати capture/перевірки до виклику та перед initialize; зберегти версію в run.request.
- [x] GREEN: нові тести + чинні editor-loop API/workflow/statistics.

## Task 2 — Межа редактора та команди

Files: static/text-editor.js, workspace-commands.js, editor.js, versions.js, runs.js, memory-table.js, copyedits-workspace.js; Node tests.

Interfaces: textEditor.read/write/onInput/focus/readOnly; registry invokeWorkspaceCommand(name, payload), registerWorkspaceCommand(name, handler). Save current material повертає Promise; show/run/review не обходять чинні guards. Новий маршрут не звертається до textarea.value.

- [x] RED: source MD unchanged, Save failure/typing/scene switch, no-op, duplicate dispatch.
- [x] Адаптувати editor/loadBuffer/saveBuffer й expose чинні show/save/run/accept дії через команди; не змінювати JSON/plain text.
- [x] GREEN: buffer/copyedit/memory regression harness.

## Task 3 — Маршрут, композиція й статуси

Files: templates/story.html, static/workspace-route.js, versions.js, runs.js, CSS; tests/web/test_workspace_route.py + js/workspace_route.mjs.

- [x] RED: порядок шести вкладок, dirty→Save→readiness, active guards, primary labels/re-generation, next scene/final publication.
- [x] Sticky tabs/actions, окрема review вкладка, primary над текстом; локальний стан кроків від серверних версій; історія/службові/automatic згруповані; conditional run controls.
- [x] Показувати editor preview без дублювання кнопок, зберегти чинне subset/prose/history прийняття та no-changes маршрут без прихованої публікації.
- [x] GREEN: route й чинні branding/export/copyedit/editor-loop тести.

## Task 4 — Налаштування за помилкою та usage

Files: static/workspace-navigation.js, settings.js, runs.js, budget.js; templates/settings.html; tests/web/test_workspace_navigation.py.

- [x] RED: allowlist ролі/scene/mode, dirty navigation, missing/zero usage.
- [x] Рольовий deep link і повернення з чинних settings; окремі причини errors зберігаються. Usage з останніх attempts, без вигаданих нулів; компактні витрати з чинного ledger.
- [x] GREEN: navigation/usage та budget/settings регресії.

## Task 5 — Контракт і приймання

Files: SPEC.MD, docs/verification/traceability.json, docs/prototype-runbook.md, журнал/STATUS; synthetic artifacts.

- [x] Оновити OpenSpec/traceability, документацію й журнал.
- [x] Незалежний review, виправити підтверджені дефекти з регресіями.
- [x] scripts/check_docs.py, повний scripts/verify.py -q; відокремити фактичні тести від ручної процедури.
- [x] Desktop/mobile synthetic UI, наскільки дозволяє browser tool; не обходити відмови policy. Detector один раз і не більше двох bounded UI rounds.
- [x] Узгоджені локальні коміти без push/merge. Підготувати застосування до робочого сервера лише після захисту буфера й перевірки active runs.

## Фактичне приймання

Реалізовано всі п’ять пакетів; незмінена схема БД, без платних викликів. Незалежне рев’ю: виправлено повторну перевірку active run після readiness, обробку списку запусків до followed run, видимість активної вкладки та клавіатурний вхід з історії. Регресії пройшли RED/GREEN. Браузер: синтетичний маршрут створення завдання/чернетки, прийняття diff, оновлення пам’яті, forwarding і наступна сцена; desktop/mobile, console errors відсутні. Повний прохід усіх семи сцен та production restart не виконувалися. Повернення з settings перевірене Node-контрактами; браузерний прогін не підтвердив query round-trip через редагування ідентифікатора інструментом. Підсумковий verify — docs/STATUS.md; коміти локальні, без push.
