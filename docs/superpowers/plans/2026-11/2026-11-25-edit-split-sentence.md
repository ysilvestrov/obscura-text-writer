# Окреме прийняття правок одного речення — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** автор розділяє речення з кількома окремими правками й приймає лише частину; сервер дозволяє неповний вибір лише в розділених групах.

**Architecture:** `sentence_groups` додає групам неперетинні `units` і номери правок у змінених частинах; `validate_group_selection` отримує `split`; `split_groups` проходить від маршрутів через сервіси до перевірки у сховищі й зберігається в рішенні. `change-review.js` показує кнопку, копії речення й «Вийде так».

**Tech Stack:** Python (FastAPI, pydantic), vanilla JS, pytest, Playwright.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-25-edit-split-sentence-design.md` (затверджено 2026-11-25).

## Global Constraints

- Помилка нерозділюваної групи: «Розділити можна лише речення з кількома окремими правками; відкрийте перегляд знову».
- `split_groups: list[int] = []` — найменші номери груп; без поля поведінка як раніше.
- Markdown: частини — компоненти зв’язності `format_dependency_groups` у межах групи.
- Кнопка в заголовку пункту «Прийняти окремо (N)», «Разом», рядок «Вийде так: …»; uk/en у `i18n.json`.
- Розділена група відновлюється лише з `split_groups` останнього рішення.

## Review Focus

1. Старий клієнт без `split_groups` і неповна група → 400, як раніше.
2. Markdown-набори, що перетинаються, — одна частина без кнопки.
3. «Вийде так» = текст «Показати вибраний текст» для того самого вибору.
4. Повторна перевірка у сховищі (`copyedit_store`, `rewrite_store`) з тим самим `split`.
5. Мобільна ширина без горизонтального прокручування.

---

### Task 1: Частини груп і перевірка `split` (домен)

**Files:** Modify `src/storygen/sentence_groups.py`; Test `tests/test_sentence_groups_split.py`.

**Interfaces — Produces:** `sentence_groups(...)` → група з `units: list[list[int]]`, змінені частини з `index: int`; `validate_group_selection(original, proposal, indices, content_format='plain', split=())`; `SPLIT_ERROR` (текст із Global Constraints).

- [ ] Тести: два віддалені заміни в реченні → `units == [[0],[1]]`, `index` у змінених частинах; Markdown з наборами `{1,2}`,`{0,2}` → `units == [[0,1,2]]`; `validate_group_selection` з неповною групою без `split` → ValueError як раніше; з `split=[0]` → OK; у Markdown неповна частина в розділеній групі → ValueError; `split` з не-найменшим номером чи групою з однією частиною → ValueError(SPLIT_ERROR).
- [ ] Реалізація; тести зелені; коміт.

### Task 2: `split_groups` у сервісах, сховищі й маршрутах

**Files:** Modify `web/routes_versions.py`, `web/routes_rewrites.py`, `generation/copyedit_review.py`, `generation/rewrite_review.py`, `storage/copyedit_store.py`, `storage/repository.py`, `storage/rewrite_store.py`, `copyediting.py::record_decision`; Test `tests/web/test_edit_split_selection.py`.

**Interfaces — Consumes:** Task 1. **Produces:** тіла `CopyeditSelection`/`Selection` з `split_groups: list[int] = []`; рішення (`copyedit_decisions`, `rewrite_decisions`) з ключем `split_groups`.

- [ ] Тести через TestClient: copyedits `selection-preview` і прийняття — без поля 400 для неповної групи, з полем 200 і рішення має `split_groups`; те саме для rewrites; повторна перевірка у сховищі отримує `split`.
- [ ] Реалізація; тести зелені; коміт.

### Task 3: Інтерфейс

**Files:** Modify `web/static/change-review.js`, `web/static/i18n.json`, CSS за потреби; Test `tests/web/browser/edit-split.spec.mjs`, `tests/web/test_*` для ключів i18n, якщо є перелік.

- [ ] Playwright: пункт із двома частинами має кнопку «Прийняти окремо (2)»; після кліку дві копії й «Вийде так»; вибір лише другої частини → «Вийде так» дорівнює реченню з тексту «Показати вибраний текст»; прийняття створює версію з першою правкою невиконаною; «Разом» повертає один прапорець (невизначений); після перезавантаження останнє рішення відкриває групу розділеною; мобільна ширина без прокручування.
- [ ] Реалізація; тести зелені; коміт.

### Task 4: SPEC, traceability, сайт

- [ ] SPEC EDIT-SENTENCE-GROUPS: абзац про розділення, `-S04`, `-S05`; traceability; `manual.md` для Playwright; `docs/site/{uk,en}/revision.md` + `check_site.py --rehash revision`; `check_docs.py`; коміт.
