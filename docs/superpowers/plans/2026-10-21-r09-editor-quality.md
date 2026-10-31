# R-09: план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Виконання автором у поточній сесії; одна незалежна фінальна перевірка.

**Goal:** Перевіряти контракт промпту до виклику та дозволити безпечно вибирати точкові редакторські правки.

**Architecture:** Незмінний контракт у VersionRef, очікуваний контракт у generation/prompts; пропозиція і рішення у StageAttempt.context. Окремий storage-сервіс атомарно публікує вибрану підмножину з CAS і початковим snapshot. Детерміновані попередження не блокують текст.

**Tech Stack:** Python/Pydantic/SQLite/FastAPI, ES modules, pytest/Node; без нових залежностей.

**Spec:** [R-09](../../specs/changes/R-09-editor-quality.md).

## Global Constraints

- auto типово, review чекає автора; режим prose незмінний.
- Legacy-промпти не отримують контракт мовчки; нова версія після явного призначення.
- Guards повного набору, snapshot, CAS, no retry/fallback збережені; мережевих витрат немає.
- SPEC.MD змінюється разом із кодом; документація українська.

## Review Focus

- Перемикання режиму зі старим власним промптом; перевірка майбутніх етапів до API.
- Конкурентна заміна прози або чернетки, включно з поверненням тієї самої голови.
- Чужа спроба, дублікати індексів, порожній вибір, непридатний повний набір.
- Refresh під час dirty-буфера та переходу до іншої сцени.
- Нормативний дієприслівник і доросла тема без хибних попереджень/каліброваного допуску.

## Task 1: Контракти промптів

Files: domain.py, prompt_contracts.py (новий спільний контракт), generation/prompts.py, generation/context.py, generation/readiness.py, storage/repository.py, storage/settings_store.py, web/routes_settings.py, web/static/settings.js; tests/generation/test_prompt_contracts.py.

Interfaces: `PromptContract(stage,mode,schema_version)`, `expected_contract(stage,settings)`, `validate_role_prompt(repo,story_id,stage,settings)`; settings `confirm_prompt_contract` і окремий `confirm_prepare_prompt_contract` для явно призначеної нової версії.

- [x] RED: власний prose-промпт блокує patches; legacy блокує запуск, explicit confirm створює іншу версію; future-stage preflight блокує до gateway; builtin працює.
- [x] GREEN: ввести контракт, resolver і серверну перевірку; UI показує призначення та явне підтвердження/скидання.
- [x] Перевірити сфокусовані тести, оновити SPEC та зафіксувати логічний коміт.

## Task 2: Пропозиції, підмножини й публікація

Files: providers/models.py, copyediting.py (спільний контракт і guards), generation/copyediting.py (compatibility exports), generation/stages.py, generation/copyedit_review.py (новий), storage/copyedit_store.py (новий), storage/repository.py, web/routes_versions.py; tests/generation/test_copyedit_review.py.

Interfaces: `copyedit_preview(repo,scene_id,attempt_id) -> dict`, `select_copyedits(repo,scene_id,attempt_id,selected_indices,expected_revision,proposal_fingerprint) -> dict`; repository `commit_copyedit_selection(...)`; GET/POST copyedits зі специфікації. Proposal fingerprint: SHA-256 канонічних draft_id/proposal/protocol.

- [x] RED: auto зберігає пропозицію/рішення; review не публікує, subset/empty створюють точний текст, повторний вибір зберігає історію; original draft залишається.
- [x] RED: чужа спроба/невалідний список/змінений fingerprint/джерело/ціль/ревізія не публікуються; зупинений run продовжує memory без inference редактора.
- [x] GREEN: валідована пропозиція до публікації, ручний storage CAS з початковим snapshot, журнал автоматичного й ручного рішень; API.
- [x] Перевірити сценарії та оновити SPEC, зафіксувати логічний коміт.

## Task 3: Мовні попередження та UI перегляду

Files: generation/language.py (новий), generation/resources/language_regressions_v1.json (новий), evaluation/runner.py, web/static/copyedits.js і copyedits-workspace.js (нові), web/static/versions.js, web/static/settings.js, web/static/app.css, web/templates/story.html; tests/generation/test_language_warnings.py, tests/web/test_copyedit_review_api.py, tests/web/js/copyedit_review.mjs.

Interfaces: `language_warnings(text) -> list[dict]`, `language_suite_hash() -> str`; GET language-warnings; review panel отримує API snapshot і не змінює dirty-буфер.

- [x] RED: точні цитати/позиції, чисті контрприклади, hash у evaluator fingerprint; API чужих версій/непрозових kind не проходить.
- [x] GREEN: локальні попередження, збереження в спробі, UI вибору/перевірки та disable при dirty/saving; settings auto/review.
- [x] Node/API/браузер перевіряють вибір/empty/помилки, текст як textContent і збереження буфера; оновити інструкцію редактора.
- [x] Повний послідовний pytest із унікальним basetemp; незалежне review всього diff, виправити Important через RED→GREEN; SPEC/журнал/план актуалізувати та закомітити. Не push/merge.

## Уточнення виконання

Спільні перевірки винесено з generation у незалежні prompt_contracts.py/copyediting.py після RED архітектурного тесту; вимога меж шарів збережена, тест не послаблено. Task 1–3 утворюють один інтегрований кодовий коміт R-09 разом із SPEC.MD; окремий попередній коміт містить лише замовлене доповнення беклогу R-18.

Незалежне review знайшло два Important: асинхронне застосування A під час завантаження B і resume після скасування review без явного повтору. Обидва відтворені RED та виправлені GREEN; геометрія checkbox 710px→16px підтверджена браузером. Реальні провайдери/літературна якість не перевірялися; нових платних викликів немає.

Фінальне приймання: 567 passed, 1 skipped, 84.84s; artifacts/r09-final-verified.log. Незалежне review завершено, Important виправлені; desktop browser/Node API перевірені, mobile viewport не перевірено. SPEC та інструкція актуальні.
