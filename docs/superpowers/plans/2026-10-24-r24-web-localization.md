# R-24 Web Localization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Inline виконання в поточній папці/гілці за вибором власника, без повторного погодження плану. Наприкінці один незалежний whole-change review.

**Goal:** повний UA/EN вебінтерфейс зі збереженням авторських даних і незбережених буферів.

**Architecture:** спільні пакетні каталоги, Python locale selection/Jinja rendering і JS translation/binding. Явні text/attribute bindings оновлюють лише presentation; без перекладу довільного DOM/API JSON. Серверна presentation-діагностика сумісна зі старими detail/reason та збереженою історією.

**Tech Stack:** Python/FastAPI/Jinja, ES modules, JSON catalogs; Node/pytest. Acorn лише ignored tooling для контрольованої міграції JS, не runtime dependency.

**Spec:** [R-24](../../specs/changes/R-24-english-localization.md), погоджено власником 24.10.2026.

## Global Constraints
- uk/en; cookie override → Accept-Language/browser → uk. Регіональні варіанти й q ваги враховуються.
- Live switch без reload, Save/API повтору, втрати value/selection/focus/dirty/busy чи SSE.
- Переклад лише власних підписів/помилок; рукописи/промпти/модельні відповіді/ID незмінні. CLI поза scope.
- Секрети й приватні історії не входять у каталоги. Невідома діагностика лишається оригінальною, не підміняє реальну причину.

## Review Focus
- Browser en-US та cookie uk; некоректний cookie, q=0, невідомі мови.
- Перемикання з dirty draft/settings, активним SSE; DOM value не переписується.
- Параметризовані помилки/числа й HTML-подібні авторські назви; відсутність XSS/втрати значень.
- Labels у module-scope об’єктах/динамічних innerHTML, старі error/reason, unknown/provider detail.
- Wheel включає catalog і працює поза checkout; старі Node harness без DOM/browser мають uk fallback.

## Task 1 — Locale і каталоги
- [x] RED Python/Node: selection, override/fallback, catalog parity/parameters, plain translation.
- [x] static/i18n.json як спільне джерело; web/localization.py: choose_locale/translate/catalog, без зміни DB.
- [x] static/i18n.js: t/setLocale/getLocale + точкові binding API; tests без browser мають uk.
- [x] GREEN targeted tests; package-data, SPEC/traceability сценарії разом із кодом.

## Task 2 — Всі поверхні та live bindings
- [x] RED: Jinja en/uk, switch з input value/selection/dirty, dynamic labels та markup.
- [x] Локалізувати templates і власні JS strings через keyed calls/bindings; не змінювати .value чи model prompts. Верхній UA/EN, html.lang/title, атрибути a11y.
- [x] Наповнити й перевірити повні англійські переклади, plural/count formats, дата/число за locale. Інвентар переносів збережено в artifacts/r24.
- [x] GREEN existing Node/UI tests і нові регресії, без фактичних моделей.

## Task 3 — Видимі серверні причини й історія
- [x] RED: app validation/readiness/error presentation обома мовами, параметри/unknown/provider diagnostics незмінні.
- [x] Сталі message keys/parameters або контрольована точна проєкція для відомих legacy patterns. Не переписувати storage чи машинні поля/enum.
- [x] UI показує локалізоване пояснення, лишає оригінальну невідому діагностику. Ніякого recursive translate JSON.
- [x] GREEN API/error/run regression tests, CLI без змін.

## Task 4 — Документація, whole-change review і приймання
- [x] SPEC/traceability/manual/runbook/PRODUCT/DESIGN/backlog/progress узгоджені; CLI R-26 і prompts/story language R-27 лишаються окремими.
- [x] Один незалежний review, confirmed fixes із RED/GREEN; повний verify/check_docs/diff.
- [x] Synthetic desktop/mobile обома мовами, dirty switch і no inference; один detector і максимум два visual rounds.
- [x] Wheel/resources; локальний commit без push, сервер не перезапускати до захисту незбережених буферів/active runs.

## Виконання

Каталоги/locale, усі п’ять шаблонів, власні JS написи й діагностика реалізовані. Один незалежний whole-change review: усі чотири підтверджені дефекти виправлено; додано регресії raw SSE, locale prefix, helper labels/placeholder/budget і незмінного suffix редактури. Свідчення повного прогону — docs/STATUS.md; browser-перевірки та пакування — журнал виконання. Погодження безпечного перезапуску отримано від власника.
