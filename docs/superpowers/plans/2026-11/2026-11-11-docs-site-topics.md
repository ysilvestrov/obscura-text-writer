# Сайт інструкцій: теми, знімки, перенаправлення (#29, R-25, PR 2) — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Повний набір користувацьких тем UA/EN на сайті, знімки інтерфейсу кожною мовою з нейтрального seed, старі файли інструкцій — посилання на сайт.

**Architecture:** Механізм PR 1 без змін (`build_site.py`, `check_site.py`, `sync.json`). Новий `scripts/capture_screenshots.py` створює нейтральні твори в тимчасовому каталозі, запускає сервер і знімає Playwright (extra `browser`) у `docs/images/site/{uk,en}/`.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-10-docs-site-design.md` (PR 2).

## Global Constraints

- Теми (сторінка UA/EN кожна): робочий простір і етапи сцени (`workspace`); персонажі (`characters`); імпорт матеріалів (`imports`); Ghost Mode (`ghost-mode`); пам’ять (`memory`); редактура й перевірка впливу (`revision`); вікові рівні (`content-rating`); моделі, ролі й бюджет, зокрема локальні моделі (`models`); оцінювач (`evaluator`); публікація й експорт (`publication`); мова твору (`story-language`); поширені помилки (`troubleshooting`); умови використання й політика назви (`legal`, посилання на наявні юридичні тексти).
- Сторінка — інструкція для автора: що робити й що побачите. Деталі API, схем і протоколів лишаються в SPEC.MD.
- Знімки лише з seed у `C:\tmp\…`, без ключів, особистих шляхів і авторських текстів; кожен знімок має alt; англійські сторінки — англійський інтерфейс і англійський твір.
- Старі користувацькі файли в `docs/` → один рядок з посиланням на сторінку сайту (UA-файл → UA-сторінка, `docs/en/*` → EN-сторінка). Юридичні тексти (`terms-of-use`, `trademark-policy`) лишаються повними: на них посилається ліцензія. Внутрішні звіти не змінюються.
- Посилання з SPEC.MD/README на перенаправлені файли з якорями переводяться на сторінки сайту.

## Review Focus

1. Інструкції збігаються з чинним інтерфейсом (#89: меню «Дії твору», рядок стану, сторінка «Редагування книги»).
2. UA і EN сторінки рівноцінні за змістом.
3. Жоден приватний шлях, ключ або авторський текст не потрапив у знімки.
4. Перенаправлення не ламає посилань із SPEC.MD, README, manual.md і тестів.
5. Скрипт знімків прибирає за собою сервер навіть при помилці.

---

### Task 1: Скрипт знімків і знімки

**Files:** Create `scripts/capture_screenshots.py`, `docs/images/site/{uk,en}/*.png`; Test `tests/test_capture_screenshots.py` (seed створює нейтральні твори обома мовами без мережі).

### Task 2: Сторінки тем

**Files:** Create `docs/site/{uk,en}/<slug>.md` для тем вище; Modify `docs/site/site.json`, `docs/site/sync.json` (`--rehash`), `docs/site/{uk,en}/index.md` (зміст).

### Task 3: Перенаправлення й документи

**Files:** Modify старі файли `docs/*.md`, `docs/en/*.md` (крім юридичних і внутрішніх); `README.md`; `SPEC.MD` (посилання, DOCS-SITE сумісність); журнал, беклог R-25, `Actual` у специфікації.
- [ ] `python scripts/check_docs.py`, повний pytest, verify.py.
