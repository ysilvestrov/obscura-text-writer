# План: інтерфейс доповнювального імпорту та обсягу

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Завершити погоджені зміни в браузері: обсяг у «Письмо», журнал із часом і зрозумілі результати імпорту.

**Architecture:** Використати фактичні API перевіреного ядра. Письмовий scope охоплює profile+story.target_words; журнал читає source_files, активне джерело — active_sources; multipart UI читає files/partial. Нового storage немає.

**Tech Stack:** Jinja, ES modules, чинний i18n і дизайн Obscura, pytest/Node, Playwright.

**Spec:** docs/specs/changes/additive-imports-writing-target-2026-11-05.md

## Global Constraints

UA/EN, plain-text авторські поля та чинний дизайн зберігаються. Обсяг від5000, без max15000, підказка «Рекомендовано до 15 000 слів» / Recommended up to 15,000 words. Цілі сцен не перераховуються. Клієнт не визначає дублі самостійно й не повторює multipart автоматично. Немає нових залежностей або модельних/Cloudflare викликів. Нейтральні screenshots; сторонній research-файл не змінювати.

## Review Focus

1. Інший клієнт змінив тільки target_words: writing preflight помічає конфлікт.
2. Dirty/Save/Reset, UA/EN,409 і мережеві помилки зберігають введений обсяг.
3. Partial200 відрізняється від повного успіху;409 із files теж показує результат.
4. Null/invalid дата не стає1970 або поточним часом; timezone браузера явно показано.
5. Подвійний submit не дублює ненумеровані сцени; refresh не губить поточну сцену.

## Task 1: Обсяг у «Налаштування → Письмо»

**Files:** templates/settings.html, static/settings.js, static/i18n.json під src/storygen/web; tests/web/test_settings_workspace.py, tests/web/js/settings_controller.mjs; новий tests/web/browser/additive-imports.spec.mjs.

**Interfaces:** GET settings.story.target_words; PUT settings {expected_revision,profile,target_words}. Writing baseline — {profile,target_words}, target_words не входить до JSON profile.

- [x] RED: поле з поточним25000, min5000 без max; спільний Save; зміна лише target іншим клієнтом викликає preflight-конфлікт.
- [x] Додати поле «Обсяг твору, слів» з чинним recommendation key. load('writing') встановлює target і composite baseline перед registerSettingsForm; інші рольові scopes незмінні.
- [x] Збір profile виключає target_words; окреме Number-перетворення й штатна form validation. checkScope('writing') порівнює обидва актуальні значення.
- [x] Browser desktop/mobile: відкрити writing через data-settings-nav або mobile select, Save через #settings-save, reload25000, Reset, dirty-вихід,409/мережевий збій і UA/EN без втрати вводу. Цілі сцен незмінні.
- [x] Оновити WRITING-TARGET/settings UI у SPEC/traceability, UA/EN інструкції та нейтральний screenshot. Запустити відповідні Node/pytest і browser cases; коміт.

## Task 2: Журнал імпорту та per-file результати

**Files:** static/editor.js, static/api.js, templates/story.html, static/i18n.json, за потреби static/app.css; нові static/import-journal.js і static/import-results.js під src/storygen/web; tests/web/browser/additive-imports.spec.mjs, нові Node-тести в tests/web/js.

**Interfaces:** source_files має name/kind/version_id/created_at; active_sources — kind→version ID. files має client_index/name/kind/status/created_scene_ids/created_character_cards/skipped_*/warnings/error. api() зберігає Error.message і додає status/data до помилки для обробки files у409/400.

- [x] RED: однаковий тип має окремі назви/дати; похідний план не є третьою подією; null/invalid час явно невідомий; HTML-подібна назва лишається текстом.
- [x] Замінити цикл по sources на source_files. Intl.DateTimeFormat використовує getLocale(), numeric year/month/day/hour/minute/second та timeZoneName; не змішувати dateStyle із timeZoneName. time.datetime містить валідний UTC timestamp. Locale-switch оновлює labels/time без перебудови авторських полів.
- [x] Активний сирий файл позначається через version_id. Для похідного плану — окрема позначка об’єднаного джерела, без вигаданої події/назви файла.
- [x] RED: успішне додавання, пропущені імена/номери, partial200, failed409 та мережевий збій. Показувати кількість створених, пропущені імена/номери та статус кожного файла; біля дублів карток — посилання «Персонажі».
- [x] Постійний блок результатів біля форми; частковий успіх відрізняється текстом. Error.data.files доступний у catch. Summary/status UA/EN беруться зі структурованих полів; довільні назви й server warnings не вставляються як HTML.
- [x] Pending блокує повтор submit та файлові inputs; finally повертає стан відповідно до dirty/saving. Не скидати state.scene при вже відкритій сцені. Refresh після успіху/partial зберігає сцену та матеріал. Немає auto-retry. Біля імпорту пояснити: секції без номера завжди нові.
- [x] Desktop/mobile: послідовні імпорти нових і дубльованих персонажів, план із новим/зайнятим номером, повтор ненумерованого файла, журнал назв/часу, partial, повільний double-click, selection, UA/EN та відсутність горизонтального переповнення. Без моделей.
- [x] Оновити SPEC/traceability, український runbook та English guides, нейтральні screenshots. check_docs.py, цільові verify.py/Node/Playwright, один UI detector і пакет desktop/mobile visual QA; коміт.

## Завершення

- [x] Незалежне рев’ю обох задач, суттєві виправлення RED→GREEN; фактичні результати verify.py у STATUS і журналі.
- [ ] Push/PR поверх перевіреного ядра, основна тека на результаті зі збереженням сторонніх правок. Не merge без дозволу.

## Самоперевірка

Обидві задачі спираються на реалізовані контракти ядра; нових продуктових рішень не додають. Рекомендовано продовжувати inline з незалежним рев’ю всього UI. План підготовлено після завершення рев’ю ядра; затверджений власником; виконано inline із незалежним рев’ю.


## Виконання 06.11.2026

Task1 — commit7100c1e. Task2: журнал source_files/active_sources, APIError зі status/data, структурований результат files/partial, UA/EN, pending guard й збереження scene/material. Незалежний ui_review знайшов2 суттєві мережеві випадки: confirmed POST→failed GET та втрачений POST response. Обидва відтворено RED (4 desktop/mobile failures) і виправлено GREEN (4 passed): підтвердження не стирається; невідомий результат не заявляє нуль, очищує вибір файлів і пропонує GET журналу без повтору POST.

UI detector виконано один раз; попередження inherited Jinja black кольорів перевірено як false positives. Нейтральні screenshots desktop/mobile оновлено; фінальна візуальна перевірка й gate записуються нижче. Cross-review виконується окремо після чистого коміту.


Фінальний UI gate: verify.py tests/web — **185 passed,0 failed/errors/skipped**, source_changed_during_run=false, artifacts/verification-u3crjc8x/result.json. Browser **94 passed**,2.0m; шість screenshots desktop/mobile візуально підтверджені.
