# Підсумки хронології (#68) — периферія: план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** панель «Підсумки хронології» в панелі пам'яті сцени, статистика «Підсумки в запиті», SPEC MEMORY-SUMMARY, traceability, сайт двома мовами.

**Architecture:** ядро (`docs/superpowers/plans/2026-11/2026-11-12-timeline-summaries-core.md`) дає API `GET/PUT /api/stories/{id}/timeline-summaries…` і запуск `timeline_summary`. Панель — окремий модуль поверх `#memory-view`, як `book-structure-ui.js` поверх параметрів сцени; чисті функції — окремо для node-тестів.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-12-timeline-summaries-design.md`

## Global Constraints

- Тексти — лише `i18n.json` (uk/en); серверні попередження перекладає `diagnostic()`.
- Перед запуском — перегляд готовності й моделі ролі «Пам'ять» і підтвердження; запуск — `POST /api/runs` з `mode='timeline_summary'`.
- Редагування не стирає буфер при конфлікті (409).
- Знімки й приклади — нейтральні; приватні історії не використовуються.

## Review Focus

1. Відкрита панель під час зміни сцени — список перечитується для нового твору/сцени, буфер редагування не переноситься (Task 6).
2. Запуск у процесі — кнопки блоку вимкнені до завершення (Task 6).

---

### Task 6: Панель і статистика

**Files:** Create `src/storygen/web/static/timeline-summaries.js` (чисті `summaryRows(blocks)`), `src/storygen/web/static/timeline-summaries-panel.js`; Modify `templates/story.html` (script), `static/i18n.json`, `static/app.css`, `application/statistics.py::memory_summary` (`summaries`), `static/scene-statistics.js`; Test `tests/web/js/timeline_summaries.mjs`, `tests/web/test_timeline_summaries_ui.py`, `tests/web/browser/timeline-summaries.spec.mjs`.

- `summaryRows(blocks) -> [{key, label: {key, params}, state, action: 'create'|'rebuild'|null, highlighted, editable, reason}]`; `action` null, коли блок не готовий (причина з сервера).
- Статистика: `memory_selection.summaries` — кількість підсумків у запиті; рядок «Підсумки в запиті: N» лише коли N > 0; шар `summary` має підпис `memory.layer.summary`.
- Тести: node — рядки для `none/fresh/stale`, неготовий блок без дії, виділення рекомендованого; pytest — сторінка підключає модуль, ключі i18n обома мовами, `memory_summary` рахує підсумки; Playwright — список блоків, редагування з конфліктом (буфер лишається), успішне збереження.

### Task 7: SPEC, traceability, сайт

**Files:** `SPEC.MD` (нова вимога MEMORY-SUMMARY, S01–S07, технічний опис, інваріанти; MEMORY-SELECT — шар `summary`), `docs/verification/traceability.json`, `docs/verification/manual.md` (браузерна перевірка панелі), `docs/site/{uk,en}/memory*.md` (розділ про підсумки), `python scripts/check_site.py --rehash <slug>`, `python scripts/check_docs.py`.
