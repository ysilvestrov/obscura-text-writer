# Структура книги — ядро: план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Частини, арки й прив'язка сцен у даних, сховищі й API, перевірка послідовності, розбір частин і арок під час імпорту, ознака довгої прози у виданні збірки.

**Architecture:** Структура — два поля payload твору (`book_structure`, `scene_arcs`); чистий модуль `book/structure.py` рахує ефективну структуру й перевіряє послідовність; `storage/book_structure.py` — CAS-операції; наявні операції сцен (створення, перестановка, відновлення, імпорт) підтримують `scene_arcs` у тій самій транзакції. У контекст і знімки залежностей структура не входить.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLite (JSON payload), pytest.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-12-book-structure-design.md`

## Global Constraints

- Без міграції SQLite; старі payload читаються з `book_structure=None`, `scene_arcs={}`.
- Межі: до 200 частин, до 1000 арок, назва до 200 символів, порожня назва допустима.
- Видання: `Literal['full','store','paid']`; `LIMITS['paid']` = рівень 2 за всіма осями; `long_prose = edition != 'store'`; `paid` не вимагає `report_url`.
- Повідомлення користувачу — українською (як решта сервера), без даних твору в логах.
- Тести без платних викликів; запуск: `W=$(pwd -W); PYTHONPATH="$W/src;$W" /c/Projects/text-generator/.venv/Scripts/python.exe -m pytest -q <тести> --basetemp=/c/tmp/bs -p no:cacheprovider`.
- SPEC.MD і `docs/verification/traceability.json` оновлюються в тому самому PR; `python scripts/check_docs.py` (з `PYTHONIOENCODING=utf-8`).

## Review Focus

1. Книга без структури: `GET /api/stories/{id}` додає лише нові поля, а запити, відбитки й знімки — ті самі (наявні тести мають проходити без змін).
2. Сцени в кошику: ні перевірка послідовності, ні неявна структура їх не враховують; відновлення ніколи не відмовляє через структуру.
3. Імпорт у твір з явною структурою, що вже має сцени: нові сцени додаються в кінець і не ламають послідовність; конфлікт — відмова без часткового запису.
4. Видання `store`: імпорт не розбирає частин, рядки `Арка:` лишаються текстом, маршрути структури — 400.
5. Конкурентні зміни: зміна структури й створення сцени конкурують через ревізію твору; 409 не пише нічого.

---

### Task 1: Модель, чистий модуль структури, видання

**Files:**
- Modify: `src/storygen/domain.py` (поля `Story`), `src/storygen/build_edition.py`
- Create: `src/storygen/book/__init__.py`, `src/storygen/book/structure.py`
- Test: `tests/book/test_structure.py`, `tests/test_build_edition.py`

**Interfaces:**
- Produces:
  - `domain.Arc{id: str, title: str = ''}`, `domain.Part{id: str, title: str = '', arcs: list[Arc]}`, `domain.BookStructure{parts: list[Part]}`; `Story.book_structure: BookStructure | None = None`, `Story.scene_arcs: dict[str,str] = {}` (max_length 100000).
  - `book.structure.IMPLICIT_PART='implicit-part'`, `IMPLICIT_ARC='implicit-arc'`.
  - `effective_structure(story, scenes) -> EffectiveStructure{parts: list[Part], arc_of: dict[scene_id, arc_id], kind: Literal['flat','structured'], explicit: bool}` — активні сцени лише; неявна — одна частина/арка з ID-константами.
  - `check_sequential(structure: BookStructure, scene_arcs: dict, active_scenes: list[Scene]) -> list[str]` — порожній список = гаразд; повідомлення називають сцени (номер і назву) та арки.
  - `validate_shape(structure) -> None` — `ValueError` на частину без арок, дублікати ID, межі.
  - `arc_before(structure, scene_arcs, active_scenes, position) -> str` — арка активної сцени перед `position`, інакше перша арка першої частини.
  - `arc_order(structure) -> dict[arc_id, tuple[int,int]]`.
  - `BuildEdition.long_prose: bool`.

- [ ] **Step 1: Тести** у `tests/book/test_structure.py`: неявна структура для `book_structure=None` (`kind='flat'`, усі активні сцени в `IMPLICIT_ARC`); явна з однією частиною й аркою — `flat`; дві арки — `structured`; `check_sequential` повертає порушення для А,Б,А і для сцени без арки, порожньо для А,А,Б і для арки без сцен; сцени в кошику ігноруються; `validate_shape` відхиляє частину без арок, 201 частину, назву з 201 символу; `arc_before` для позиції 0, середини й кінця. У `tests/test_build_edition.py`: `paid` без `report_url` приймається, `max_rating` — 2/2/2, `long_prose` true для `full`/`paid`, false для `store`.
- [ ] **Step 2: Запустити — FAIL** (модуля немає).
- [ ] **Step 3: Реалізувати** поля, модуль, видання.
- [ ] **Step 4: Запустити — PASS**, плюс `tests/test_build_edition.py tests/storage/test_integrity.py` без змін.
- [ ] **Step 5: Commit** `feat(book): structure model, sequential check and paid edition`.

### Task 2: Сховище й наявні операції сцен

**Files:**
- Create: `src/storygen/storage/book_structure.py`
- Modify: `src/storygen/storage/repository.py` (`create_scene`), `src/storygen/storage/authoring.py` (`reorder_scenes`, `set_scene_trashed`), `src/storygen/storage/integrity.py`
- Test: `tests/storage/test_book_structure.py`

**Interfaces:**
- Consumes: Task 1.
- Produces:
  - `put_structure(repo, story_id, parts: list[dict], scene_arcs: dict, expected_revision) -> Story` — нові ID для `id=None`; `validate_shape`; кожна активна сцена має арку; `check_sequential`; прив'язки сцен у кошику до видалених арок прибираються; CAS → `RevisionConflict`; порушення → `ValueError` з переліком.
  - `assign_scene(repo, story_id, scene_id, arc_id, expected_revision) -> Story`.
  - `clear_structure(repo, story_id, expected_revision) -> Story` — обидва поля скидаються.
  - Хуки: `create_scene` при явній структурі пише `scene_arcs[new]=arc_before(...)`; `reorder_scenes` при явній структурі викликає `check_sequential` і відмовляє до запису; `set_scene_trashed(restore=True)` при явній структурі перепризначає арку (якщо арки немає або порушилася б послідовність — `arc_before`); видалення в кошик прив'язку лишає.
  - Fsck: `book_structure_not_sequential` (limitation) і `book_structure_unknown_arc` (limitation для прив'язки активної сцени до відсутньої арки).

- [ ] **Step 1: Тести:** CAS (409 нічого не пише); put з перемішаними арками — 400 і без змін; put з частиною без арок — 400; створення сцени в кінці й посередині отримує арку попередньої; перестановка, що перемішує, — 400 без зміни позицій; відновлення сцени, чию арку видалено, — отримує арку попередньої й структура послідовна; clear повертає `flat`; fsck на зіпсованому payload дає limitation.
- [ ] **Step 2: FAIL.**
- [ ] **Step 3: Реалізувати.**
- [ ] **Step 4: PASS** плюс `tests/storage/test_authoring_transactions.py tests/storage/test_integrity.py tests/web/test_trash_api.py`.
- [ ] **Step 5: Commit** `feat(storage): book structure CAS and scene operation hooks`.

### Task 3: API і MCP

**Files:**
- Create: `src/storygen/web/routes_structure.py` (підключити в `web/app.py`)
- Modify: `src/storygen/web/routes_stories.py` (`story_view`), `src/storygen/mcp/bridge.py` (`get_story`)
- Test: `tests/web/test_structure_api.py`, `tests/mcp/` (наявний тест `get_story` доповнити)

**Interfaces:**
- Consumes: Task 2.
- Produces: `PUT /api/stories/{id}/structure` `{expected_revision, parts, scene_arcs}`; `DELETE /api/stories/{id}/structure` `{expected_revision}`; `PUT /api/stories/{id}/scenes/{scene_id}/arc` `{arc_id, expected_revision}`; усі три — 400 у виданні без довгої прози. `GET /api/stories/{id}` → `book_structure: {kind, explicit, parts:[{id,title,arcs:[{id,title}]}]}`, кожна сцена — `arc_id`. MCP `get_story`: `part_id`, `part_title`, `arc_id`, `arc_title` у кожній сцені.

- [ ] **Step 1: Тести** маршрутів (успіх, 409, 400 послідовності, 400 у `store` через monkeypatch `build_edition.current`), поля `GET`, MCP.
- [ ] **Step 2: FAIL.** - [ ] **Step 3: Реалізувати.** - [ ] **Step 4: PASS** плюс `tests/web/test_story_api*.py tests/mcp`.
- [ ] **Step 5: Commit** `feat(web): book structure API and story view fields`.

### Task 4: Імпорт частин і арок

**Files:**
- Modify: `src/storygen/plan_sections.py` (нова `split_book_plan`), `src/storygen/authoring/imports.py` (`_plan`), `src/storygen/import_models.py`, `src/storygen/storage/import_store.py`
- Test: `tests/authoring/test_import_book_structure.py`

**Interfaces:**
- Produces:
  - `plan_sections.BookSection{section: PlanSection, part_title: str | None, arc_title: str | None}`; `split_book_plan(text, default_title) -> tuple[str, list[BookSection], bool]` — третій елемент: чи знайдено хоч одну межу частини або рядок арки. Заголовок частини: рівень менший за рівень пронумерованих заголовків сцен (або будь-який, якщо сцени без заголовків), назва після `clean_title` відповідає `^(частина|part)\b` (без регістру); рядок вирізається, а секції після нього до наступного — у цій частині. Рядок арки: `plain_line(line)` відповідає `^(арка|arc)\s*:\s*(.*)$` — вирізається з тексту секції; арка діє до наступного рядка в тій самій частині; перша секція частини без рядка — арка `''`. Назва частини — текст після `Частина N:`/`Part N:` або весь заголовок, якщо двокрапки немає.
  - `ImportedScene.part_title: str | None = None`, `arc_title: str | None = None`; `ImportPublication.structured: bool = False`.
  - `publish_import`: якщо `structured` — додає частини/арки за правилом специфікації (продовження останньої частини за назвою, арки — за назвою в частині), пише `scene_arcs` нових сцен; якщо твір мав неявну структуру й активні сцени — вони йдуть у першу частину, першу арку (нова частина з назвою `''`, якщо план починається з іншої частини); `check_sequential` → порушення — `ValueError` (вся публікація відкочується).
  - `_plan` використовує `split_book_plan` лише якщо `build_edition.current().long_prose`; інакше — чинний `split_plan` без змін.

- [ ] **Step 1: Тести:** план з `# План`, `# Частина 1: А`, двома сценами, `Арка: Ранок` у першій, `# Частина 2: Б`, однією сценою → дві частини, арки, тексти планів сцен без заголовків частин і рядка `Арка:`; сцена без рядка — в арці попередньої; повторний імпорт з `# Частина 2: Б` продовжує частину 2; `store` — тексти як раніше (рядки лишаються); план без маркерів — неявна структура; номери сцен і `IMPORT-NUMBER`/`IMPORT-ADDITIVE` тести без змін.
- [ ] **Step 2: FAIL.** - [ ] **Step 3: Реалізувати.** - [ ] **Step 4: PASS** плюс `tests/authoring/test_import_sections.py tests/authoring/test_imports.py tests/storage/test_import_publication.py`.
- [ ] **Step 5: Commit** `feat(import): parts and arcs from the plan`.

### Task 5: Інваріант пласкої книги й документація ядра

**Files:**
- Test: `tests/book/test_structure_invariants.py`
- Modify: `SPEC.MD` (нова вимога BOOK-STRUCTURE із S01–S04; BUILD-EDITION-001 — видання `paid` і S09), `docs/verification/traceability.json`

- [ ] **Step 1: Тест S02:** у структурованій книзі контекст brief сцени 2 (`build_context` з підставною моделлю, як у `tests/generation/test_context*.py`), потім `put_structure` з іншим поділом і перейменуванням → той самий текст запиту й відбиток, `compare_snapshot` свіжий. Тест S01: пласка книга — те саме до й після `put_structure` + `clear_structure`.
- [ ] **Step 2: PASS** (поведінка вже має бути правильною; якщо FAIL — це знахідка, systematic-debugging).
- [ ] **Step 3: SPEC.MD і traceability**, `check_docs.py`.
- [ ] **Step 4: Commit** `docs: BOOK-STRUCTURE core in SPEC and traceability`.
