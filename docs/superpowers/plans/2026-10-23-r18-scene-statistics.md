# R-18 — План реалізації статистики

> Виконання в цьому чаті через superpowers:executing-plans; погоджені продуктові рішення — у специфікації.

**Мета:** прозоро показати обсяг матеріалів, префікс пам’яті та витрати контексту без моделі.
**Архітектура:** чисті підрахунки й metadata-only вимірювання реального побудовника; read-only facade/API; окремий ES module UI.
**Стек:** Python/FastAPI, stdlib, ES modules, чинні CSS tokens.
**Специфікація:** docs/specs/changes/R-18-scene-statistics.md.

- [x] RED pure/server тести Unicode, heads, chronology та exact body partition/overflow.
- [x] context_metrics.py + ContextBundle metadata/overflow, application/statistics.py + routes_statistics.py.
- [x] RED frontend: text-statistics.js + scene-statistics.js, async guard/dirty/history, потім мінімальна панель у story.html/app.css.
- [x] SPEC R18 requirements/scenarios/traceability, інструкція; focused/full verify, independent review, desktop/mobile synthetic smoke.
- [x] Застосувати сервер без active calls, звірити авторські дані, commit і журнал; R-14/R-15 — лише після виміряної потреби.
