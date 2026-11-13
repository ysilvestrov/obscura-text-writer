# Протагоніст арки, обв'язка (проєкт 2, PR 2) — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** автор задає протагоніста арки рядком `Протагоніст:` у плані або полем у панелі «Структура книги»; блок знайомств і перевірка `introduced` беруть героя сцени; сайт описує нове.

**Architecture:** спирається на ядро (`docs/superpowers/plans/2026-11/2026-11-13-arc-protagonist-core.md`, коміти до `6a856b5`): `Arc.protagonist_id`, `book/protagonists.py::scene_tracked`, перевірка картки в `PUT /structure`, буфер панелі вже переносить `protagonist_id`. Імпорт розв'язує ім'я за `name_key` під час публікації плану, а нерозв'язані імена — ще раз наприкінці пакета, бо файл карток може йти після плану (як склад сцени, #103).

**Tech Stack:** Python 3.12, FastAPI, pytest, ванільний JS, node-тести, Playwright.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-12-parallel-arcs-design.md` — «Структура» (рядок імпорту, поле панелі), поправка 1 п. 4 (герой знайомств), сценарій BOOK-LINEAGE-S04.

## Global Constraints

- Рядок `Протагоніст: Ім'я` / `Protagonist: Name` (регістр неважливий, після зняття Markdown, як `Арка:`) вирізається з плану сцени; розбір — лише у виданні з довгою прозою, інакше рядок лишається текстом.
- Ім'я розв'язується за `name_key` картки; невідоме ім'я — попередження імпорту `Протагоніст «{name}» не знайдений серед карток; протагоніста арки не задано.`, протагоніст не задається.
- Рядок задає протагоніста арки сцени, лише якщо в арки його ще немає; інше ім'я для арки з протагоністом — попередження `Арка вже має протагоніста; рядок «Протагоніст: {name}» пропущено.`
- Книга без явних протагоністів: блок знайомств, `introduced` і стан зв'язку brief не змінюються.
- Тексти інтерфейсу — `i18n.json` (uk/en); сайт — пара `docs/site/{uk,en}/book-structure.md`, підтверджена `check_site.py --rehash`.

## Review Focus

- План і файл карток в одному пакеті, картки — другим файлом: протагоніст задається наприкінці пакета, без попередження.
- Повторний імпорт плану, що продовжує арку з протагоністом, і той самий рядок: тиша, без попередження.
- Панель у книзі без карток: поле показує лише «Герой книги» і не ламає збереження.
- Сцена, герой якої — протагоніст арки, що не входить у склад сцени: блок знайомств порожній, як для героя книги поза складом зараз.
- Видання без довгої прози: рядок `Протагоніст:` лишається текстом плану.

---

### Task H1: рядок `Протагоніст:` в імпорті

**Files:**
- Modify: `src/storygen/plan_sections.py` (`PROTAGONIST_LINE`, `BookSection.protagonist_name`, `_cut_arc_lines`), `src/storygen/import_models.py` (`ImportedScene.protagonist_name`, `ImportPublicationResult.pending_protagonists`), `src/storygen/authoring/imports.py` (`_plan`, кінець `import_sources`), `src/storygen/storage/book_structure.py` (`place_imported`, нова `bind_pending_protagonists`), `src/storygen/storage/import_store.py`
- Test: `tests/storage/test_import_protagonist.py`, `tests/authoring/test_plan_sections_protagonist.py`

**Interfaces:**
- Produces:
  - `BookSection.protagonist_name: str | None = None` (останній рядок у секції; `[:200]`);
  - `ImportedScene.protagonist_name: str | None = Field(default=None, max_length=200)`;
  - `place_imported(story, active, created, structured, cards=()) -> (Story, list[tuple[str, str]], list[str])` — `created` елементи отримують п'ятий член `protagonist_name`; повертає твір, нерозв'язані `(arc_id, name)` і попередження про арку з іншим протагоністом;
  - `ImportPublicationResult.pending_protagonists: list[tuple[str,str]]`, `warnings: list[str]`;
  - `bind_pending_protagonists(repo, story_id, pending) -> list[str]` — одна транзакція з поточною ревізією: розв'язує імена проти поточних карток, задає протагоніста арк без нього, повертає попередження про невідомі імена; нічого не пише, якщо задавати нічого.

- [ ] **Step 1: тести:**
  - `test_protagonist_line_is_cut_from_the_plan` — `split_book_plan` секції з `Арка: Дорога\nПротагоніст: **Богдан**\nТекст` → `protagonist_name == 'Богдан'`, у тексті сцени немає рядка;
  - `test_import_sets_the_protagonist_of_a_new_arc` — картки A «Анна», B «Богдан» опубліковані; імпорт плану з двома арками, рядок у першій сцені другої → `protagonist_id == 'B'` у другої арки, перша — `None`, попереджень про протагоніста немає;
  - `test_unknown_name_warns_and_sets_nothing` — `Протагоніст: Ніхто` → точний текст попередження з Global Constraints, `protagonist_id is None`;
  - `test_cards_file_after_the_plan_resolves_at_the_end` — один пакет `[план, картки]` → протагоніст заданий, без попередження;
  - `test_other_name_for_an_arc_with_a_protagonist_warns` — друга сцена арки з іншим ім'ям → точне попередження, протагоніст перший;
  - `test_edition_without_long_prose_keeps_the_line` — `build_edition` store: рядок лишається в beats.
- [ ] **Step 2:** запуск → FAIL.
- [ ] **Step 3:** реалізація; `place_imported` розв'язує за `{name_key(c.name): c.id}` поточних карток із транзакції публікації.
- [ ] **Step 4:** запуск → PASS; `pytest tests/storage tests/authoring -q` → PASS.
- [ ] **Step 5:** коміт `feat(book): import the arc protagonist line`.

### Task H2: поле «Протагоніст» у панелі

**Files:**
- Modify: `src/storygen/web/static/book-structure.js` (`setProtagonist(buffer, p, a, id)`), `src/storygen/web/static/book-structure-panel.js` (вибір у рядку арки), `src/storygen/web/static/i18n.json` (`book.panel.protagonist`, `book.panel.protagonist_auto`)
- Test: `tests/web/js/book_structure.mjs`, `tests/web/browser/book-structure.spec.mjs`

**Interfaces:**
- Consumes: `view.character_names` із `GET /api/stories/{id}` (`{id: name}`).
- Produces: `setProtagonist(buffer,p,a,id)` — `null` для порожнього значення; повертає `null`.

- [ ] **Step 1: тести:** node — `setProtagonist` задає й знімає поле, `payload` несе його; Playwright `arc protagonist is chosen and saved` — вибір картки, «Зберегти», перезавантаження, вибір лишився; `select` має `aria-label` з назвою арки.
- [ ] **Step 2:** запуск → FAIL.
- [ ] **Step 3:** у рядку арки — `select` з опцією «Герой книги» (`''`) і картками за іменем; протагоніст із карткою поза набором показується опцією з ID, щоб збереження не стирало вибір мовчки.
- [ ] **Step 4:** node і Playwright `book-structure.spec.mjs` → PASS.
- [ ] **Step 5:** коміт `feat(book): protagonist field in the book structure panel`.

### Task H3: герой знайомств — протагоніст арки сцени

**Files:**
- Modify: `src/storygen/book/protagonists.py` (`scene_hero`), `src/storygen/characters/acquaintance.py` (`acquaintances`, `acquaintance_material`), `src/storygen/characters/brief_link.py` (`_context`, `brief_link_state`, `confirm_brief_link`), `src/storygen/generation/stages.py:253`
- Test: `tests/characters/test_arc_hero_acquaintance.py`

**Interfaces:**
- Produces: `scene_hero(story, cards, scenes, scene) -> str | None` — перший із `scene_tracked`, `None` без карток.

- [ ] **Step 1: тести:**
  - `test_acquaintance_block_names_the_arc_protagonist` — сцена арки з протагоністом B і складом A, B: `acquaintance_material(...)[0]` починається заголовком для «Богдан»;
  - `test_flat_book_acquaintance_is_unchanged` — без структури блок той самий, що `acquaintances` до зміни (герой A);
  - `test_brief_link_state_uses_the_scene_hero` — `brief_link_state(...)['hero_id'] == 'B'` для сцени арки Y, `'A'` для сцени арки X.
- [ ] **Step 2:** запуск → FAIL.
- [ ] **Step 3:** кожне місце бере `scene_hero` для своєї сцени; попередження `protagonist(...)` (дубль позначки) лишаються.
- [ ] **Step 4:** нові тести PASS; `pytest tests/characters tests/generation -q` без змін наявних тестів → PASS.
- [ ] **Step 5:** коміт `feat(characters): acquaintance hero follows the scene's arc`.

### Task H4: SPEC, сайт, ручна процедура

- [ ] SPEC.MD: BOOK-STRUCTURE-S04 (рядок `Протагоніст:`), S06 (поле панелі), технічний опис імпорту й інтерфейсу; BOOK-LINEAGE-S04 — імпорт, панель, герой знайомств; PLANNER-ACQUAINTANCE — герой сцени (протагоніст її арки); прибрати з «Відомих обмежень» пункт про обв'язку. Traceability S04 і BOOK-STRUCTURE-S04/S06 — нові тести.
- [ ] Сайт: `docs/site/uk/book-structure.md` і `docs/site/en/book-structure.md` — розділ «Протагоніст арки» / «Arc protagonist» (рядок плану, поле панелі, що змінюється для ядра стану й знайомств, пізно заданий протагоніст робить застарілими лише сцени своєї арки); нейтральні приклади; `python scripts/check_site.py --rehash book-structure`; `python scripts/check_docs.py` → OK.
- [ ] Коміт `docs: arc protagonist — import line, panel field, site`.
