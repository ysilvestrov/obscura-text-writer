# Родовід сцен (проєкт 2, PR 1) — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** одна функція родоводу `book/lineage.py` замість «усіх активних сцен вище» в пам'яті, контексті письма й знімках залежностей; поведінка книг, які зараз дозволені, не змінюється.

**Architecture:** чиста функція над `Story` і списком сцен обчислює для кожної активної сцени безпосередніх попередників (за правилами потоків зі специфікації), голови й транзитивних предків у порядку читання. Місця П1 зі специфікації замінюють вираз `s.position<scene.position` на `previous_scenes(...)`. Поки перевірка структури проєкту 1 забороняє перемішування арок і сцени зустрічі, предки дорівнюють усім сценам вище, тож PR — рефакторинг like-for-like: наявні тести проходять без змін.

**Tech Stack:** Python 3.12, pydantic, pytest.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-12-parallel-arcs-design.md` (розділи «Родовід», «Перевірки» BOOK-LINEAGE-S01/S02).

## Global Constraints

- Книга без арок і книга з послідовними арками дають ті самі запити, відбитки й знімки залежностей (BOOK-LINEAGE-S01).
- Не переходять на родовід: картки персонажів, інструкції рейтингу, оцінювання (`evaluation/story_adapter.py`), перевірка впливу, вхідні посилання brief у `web/routes_versions.py` (порядок читання).
- `Story.scene_arcs` у цьому PR лишається `dict[str,str]`; кілька арок сцени — PR 3.
- Без міграції SQLite; SPEC.MD оновлюється в тому самому коміті, що й код.

## Review Focus

- Сцена кошика або сцена без арки в структурованій книзі: родовід — попередня активна сцена й усі вище (як зараз).
- Арка в структурі без жодної сцени: не дає голови й не ламає початок частини.
- Перша сцена першої частини: без попередників, `heads=()`.
- Новий код з виразом `position<scene.position` поза `book/lineage.py` і списком винятків: тест-охоронець падає.
- Вибір перегляду: місця, що читають `view.peek_scenes`, і ті, що читають `list_scenes`, отримують ті самі предки.

---

### Task 1: функція родоводу

**Files:**
- Create: `src/storygen/book/lineage.py`
- Test: `tests/book/test_lineage.py`

**Interfaces:**
- Produces: `Lineage(heads: tuple[str,...], ancestors: tuple[str,...], needs_merge: bool)`; `lineage_map(story, scenes) -> dict[scene_id, Lineage]` (лише активні сцени); `lineage(story, scenes, scene_id) -> Lineage`; `previous_scenes(story, scenes, scene) -> list[Scene]` — предки як об'єкти сцен у порядку читання (сцена кошика або невідома → усі активні сцени вище, як зараз).

- [ ] **Step 1: тести** — `test_flat_book_is_every_scene_above`; `test_sequential_arcs_and_parts_are_every_scene_above` (частина 1: арки А, Б; частина 2: В — для кожної сцени `ancestors` = усі вище, `heads` = попередня); `test_interleaved_arcs_isolate_streams` (А1 Б1 А2 Б2 у частині: предки Б2 = (Б1); Б1 — початок частини, без попередників у першій частині); `test_first_scene_of_an_arc_after_ended_arcs` (А1 Б1 А2 В1, де Б закінчилася до В1, А — ні: голови В1 = (Б1)); `test_part_start_merges_heads_of_the_previous_part` (перемішані А, Б у частині 1, далі В: голови В1 = (А-остання, Б-остання), `needs_merge`); `test_empty_arc_and_unknown_arc_fall_back`. Перемішані випадки будуються прямо в `Story` без перевірки структури.
- [ ] **Step 2:** запуск — FAIL (модуля немає).
- [ ] **Step 3:** реалізація за розділом «Родовід» специфікації; плаский шлях (`effective_structure(...).kind=='flat'`) — ланцюжок без обчислення арок.
- [ ] **Step 4:** запуск — PASS.
- [ ] **Step 5:** коміт `feat(book): scene lineage`.

### Task 2: перехід місць П1

**Files:** `memory/service.py`, `memory/reuse.py`, `memory/forwarding.py`, `memory/kinds.py`, `memory/core_review.py`, `memory/story_time.py`, `generation/context.py`, `generation/dependencies.py`, `storage/snapshots.py`, `application/statistics.py`; Test: `tests/book/test_lineage_guard.py`.

**Interfaces:** Consumes `previous_scenes`, `lineage`.

- [ ] **Step 1: тест-охоронець** `test_no_position_prefix_outside_lineage`: регулярний вираз `\.position\s*<\s*\w+\.position` по `src/storygen` дозволений лише в `book/lineage.py` і явному списку винятків (`evaluation/story_adapter.py`, `rating/instructions.py`, `web/routes_versions.py`) з причиною в коментарі; плюс `test_snapshot_selectors_use_lineage` — селектори `prefix`/`narrative_window` перемішаної книги рахують предків, а не всі сцени вище.
- [ ] **Step 2:** запуск — FAIL зі списком місць.
- [ ] **Step 3:** заміна в кожному місці; `story_time.comparison_scene` — найпізніший предок із цим персонажем.
- [ ] **Step 4:** охоронець PASS; повний набір без змін наявних тестів PASS (доказ like-for-like).
- [ ] **Step 5:** коміт `refactor: earlier scenes come from the lineage`.

### Task 3: SPEC і traceability

- [ ] Нова вимога BOOK-LINEAGE (технічний опис, інваріант пласкої книги, винятки), сценарії S01–S02 із записами в `docs/verification/traceability.json`; `python scripts/check_docs.py`. Користувацька документація не змінюється: поведінка для автора та сама (причина — у PR).
- [ ] Коміт `docs(spec): BOOK-LINEAGE S01-S02`.
