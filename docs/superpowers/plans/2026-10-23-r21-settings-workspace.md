# R-21 Settings Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Виконання мною в цьому чаті, поточна гілка/папка за попереднім рішенням власника; новий worktree не потрібний. Дизайн погоджено 23.10.2026; повторного підтвердження плану не запитуємо відповідно до доручення власника реалізовувати після підготовки плану.

**Goal:** зрозумілі налаштування за розділами, одна форма та Evaluator/Classification без обов’язкового JSON.

**Architecture:** реєстр DOM-буферів і навігація розділів незалежні від API. Чинні role/profile/budget API лишаються, UI має окремі адаптери ProviderSettings/ClassificationSettings/EvaluatorConfig та явний raw JSON Apply/Discard. Серверні калібрування й refusal block не підміняються формою.

**Tech Stack:** FastAPI/Jinja, ES modules/CSS, Node harness/pytest; без нового фреймворку чи міграції.

**Spec:** [R-21](../../specs/changes/R-21-settings-page-design.md).

## Global Constraints

- Письмо/Моделі/Оцінювач/Бюджет/Комплекти; одна відкрита форма ролі; mobile select.
- Dirty буфери не стираються від переходу чи Save сусіда; scope Save, no hidden Save all.
- Негайний off працює з невалідними pending полями; кандидат не дозволяє pause, calibrated/fingerprints read-only.
- Зміна конфігурації/порогів каліброваного pause вимагає явного report/off перед Save.
- Raw JSON не застосовується мовчки; до Apply/Discard Save і звичайні поля заблоковані, off лишається доступним.
- Повернення R-20 role/scene/material, секрети лише env-назви, без автоматичних API-моделей/discovery.

## Review Focus

- Save однієї ролі змінює story revision, але не перезаписує dirty сусіда; зовнішня зміна цього scope відхиляє перезапис.
- Подвійний Save, ввід під час API, async GET/помилка не підміняють буфер/defaults.
- Null temperature/timeout/model CLI, legacy advanced поля та калібрування переживають GET→form→PUT.
- Негайний off з raw JSON або невалідним input не відновлює старе увімкнення на наступному Save.
- Apply shared provider/profile за dirty інших форм потребує рішення та не приховує втрату буферів.

## Task 1 — Реєстр буферів і маршрутизація

Files: static/settings-state.js (pure), settings-workspace.js (DOM), templates/settings.html, CSS; tests/web/js/settings_workspace.mjs, tests/web/test_settings_workspace.py.

Interfaces: registerSettingsForm(key,{form,label,section,reset?}), settingsSaved(key), withSettingsSave(key,work), confirmSettingsReplacement(keys,fields?), showSettingsRole(role), hasUnsavedSettings(), allowSettingsNavigation(). Реєстр фіксує поля включно з disabled, busy/error/raw-dirty; перемикання тільки hidden/active.

- [x] RED: scope dirty/save/reset, neighbor preservation, busy/double dispatch, allowlist/deep link.
- [x] Реалізувати стан, sidebar/select, role tabs і sticky scope actions; invalid відкриває details перед фокусом; beforeunload.
- [x] GREEN Node harness, чинні workspace navigation/buffer regressions.

## Task 2 — Ролі, підключення та класифікатор

Files: settings.js, settings-connection.js, classification-settings.js; Node adapters tests; чинні routes/settings tests.

Interfaces: mountConnection(form,{adapter:'role'|'evaluator',value,onChange}), read()/write()/update(); mountClassification(form,value) read()/validate(). Нормальний save зберігає початкові object поля; untouched nulls не стають zero. Класифікатор має окремий toggle і поля, входить у Save editor.

- [x] RED/GREEN: role vs evaluator provider names, null/default round-trip. Classifier disabled/cache/enabled перевірено кодом; повний браузерний round-trip ще не підтверджено.
- [x] Згрупувати існуючі role fields, context reserve hint, prompts/contracts та additional settings. Прив’язати registry, зберігати тільки поточну роль; preflight GET порівнює baseline цього scope, потім чинний CAS.
- [x] Shared provider: explicit affected dirty provider fields; update provider baseline без скидання решти чужих полів. Profile Save не перебудовує ролі.
- [x] GREEN adapters/role API/prompt contract/horizon regressions.

## Task 3 — Evaluator form і technical JSON

Files: evaluator-form-state.js (pure), evaluator-settings.js (DOM), evaluation.js; tests/web/js/evaluator_settings.mjs, tests/web/test_settings_workspace.py; evaluation API tests.

Interfaces: evaluatorDraft(saved) read/patch/rawApply/rawDiscard/policy/candidate/validate; snapshot clone як джерело всіх полів. UI редагує exact supported config і ScoringProfile, calibrated metadata readonly. Off через чинний policy endpoint окремо від full Save. GET errors не показуються як успішно завантажений fallback, крім реального «не налаштовано».

- [x] RED: config/profile round-trip, raw invalid/pending protects fields, off survives raw/invalid, calibrated edit/pause requires explicit policy and candidate for thresholds.
- [x] Реалізувати provider-specific звичайні поля, state/block/quality display, profile thresholds, JSON Apply/Discard, env names та CLI options.
- [x] GREEN pure form tests + чинні refusal/calibration/policy API tests.

## Task 4 — Інтеграція, документація й приймання

Files: role-profiles.js, budget.js, workspace-navigation.js, DESIGN.md, SPEC.MD, traceability/manual/runbook/evaluator docs, журнал/STATUS.

- [x] Реєстр для budget subforms і capture; профіль apply з explicit discard дозволяє reload без подвійного beforeunload; deep links відкривають роль до фокусу.
- [x] OpenSpec scenarios і concrete traceability; виправити інструкцію Evaluator JSON на звичайну форму/optional JSON, без зміни старих API прикладів.
- [x] Synthetic desktop/mobile, scope Save, raw/off/classifier перевірені; blocker зняв автор. Повний keyboard/provider matrix лишається ручною процедурою, не заявлений виконаним. Detector один раз,0 primary.
- [x] Фінальний scripts/verify.py -q:998 passed,1 skipped,0 failed/errors. check_docs/diff та незалежний review виконані, обидва confirmed findings виправлені з RED/GREEN.
- [x] Локальний commit без push. JS/template зміни не потребують перезапуску; якщо виявиться backend change — захист буфера й active runs перед застосуванням.

План перевірено проти погодженого дизайну. Деталі DOM композиції й назви допоміжних функцій можуть уточнюватися з ruling у `.superpowers/sdd/r21/progress.md`; продуктові межі лишаються незмінними.
