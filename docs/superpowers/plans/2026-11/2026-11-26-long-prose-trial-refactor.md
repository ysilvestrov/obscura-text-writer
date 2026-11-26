# Довга проза для книги, а не для збірки — рефакторинг (R-47, PR 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Перевірки довгої прози питають про конкретну книгу чи серію, а не про збірку загалом, без зміни поведінки.

**Architecture:** Нові предикати в `book/guard.py` поки що повертають `build_edition.current().long_prose`. Усі місця, де книга чи серія відома, переходять на них. Місця без книги (створення серії, імпорт рукопису, сторінка `/series`, `app-info`, шаблони й JS) не змінюються: їх змінять PR 2 і PR 3.

**Tech Stack:** Python 3.12, FastAPI, SQLite, pytest.

**Spec:** [2026-11-26-long-prose-trial-design.md](../../specs/2026-11/2026-11-26-long-prose-trial-design.md), §3.2 (абзац «PR 1»), ключове рішення 5.

## Global Constraints

- Рефакторинг без зміни поведінки: наявні тести MUST проходити без жодної правки (pr-slicing: «Refactoring goes in its own PR»). Нові тести дозволені.
- Видання з довгою прозою MUST NOT читати базу в перевірці (BUILD-EDITION-001, «У виданнях із довгою прозою перевірка не читає БД»).
- Тексти відмов `NO_LONG_PROSE`, `READ_ONLY`, `READ_ONLY_SERIES` не змінюються (на них точно зіставляє `mcp/edition.py`).
- Неіснуючий твір чи серія у виданні без довгої прози дає ту саму відповідь, що й зараз: 400 з `NO_LONG_PROSE` (а не 404), бо `require_long_prose()` викликається до читання.
- Команди Python: `PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest …` з кореня робочої копії.

## Review Focus

- Маршрут із неіснуючим `story_id` чи `series_id` у Store: відповідь 400 `NO_LONG_PROSE`, як до зміни, а не 404 чи 500.
- Видання `full`: жоден новий предикат не відкриває з'єднання з базою (тест із підміненим `repo.db`).
- `blocked` у middleware: порядок перевірок не змінився — для `full` ранній вихід до розбору тіла запиту.
- Імпорт плану з рядками серії й частинами у Store: як і раніше, частини й серія ігноруються.
- `replace_plan_preamble` у Store з рядками серії: як і раніше, без відмови «Серію змінюють у налаштуваннях».

---

### Task 1: Предикати довгої прози для книги й серії

**Files:**
- Modify: `src/storygen/book/guard.py`
- Test: `tests/book/test_long_prose_for.py` (новий)

**Interfaces:**
- Produces:
  - `long_prose_for(repo, story: Story) -> bool`
  - `story_long_prose(repo, story_id: str) -> bool` — False для невідомого твору у виданні без довгої прози;
  - `series_long_prose(repo, series_id: str) -> bool`
  - `require_long_prose_for(repo, story_id: str) -> None` — `ValueError(NO_LONG_PROSE)`, якщо `story_long_prose` False;
  - `require_series_long_prose(repo, series_id: str) -> None` — те саме для серії.
  - У PR 1 усі повертають/перевіряють `build_edition.current().long_prose` і **не читають базу**. PR 2 додасть відмітку проби лише в гілку «видання без довгої прози».

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.req('BUILD-EDITION-001')
def test_full_edition_answers_without_the_database(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    repo.db = None  # будь-яке звернення до бази впаде
    assert long_prose_for(repo, story) and story_long_prose(repo, story.id) and series_long_prose(repo, 'x')
    require_long_prose_for(repo, 'missing'); require_series_long_prose(repo, 'missing')

@pytest.mark.req('BUILD-EDITION-001')
def test_store_edition_refuses_with_the_same_text(tmp_path, store_edition):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    assert not long_prose_for(repo, story) and not story_long_prose(repo, story.id) and not series_long_prose(repo, 'x')
    for call in (lambda: require_long_prose_for(repo, 'missing'), lambda: require_series_long_prose(repo, 'missing')):
        with pytest.raises(ValueError, match=NO_LONG_PROSE):
            call()
```

- [ ] **Step 2: Run, expect FAIL** — `PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest tests/book/test_long_prose_for.py -q` → ImportError.
- [ ] **Step 3: Implement** the five functions in `book/guard.py` with the docstring «PR 2 adds the trial marker here».
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** `refactor(R-47): предикати довгої прози для книги й серії`.

### Task 2: Місця з відомою книгою чи серією питають предикат

**Files:**
- Modify: `src/storygen/web/routes_structure.py:48,55,62` → `require_long_prose_for(request.app.state.repo, story_id)`
- Modify: `src/storygen/web/routes_memory_merges.py:44` → те саме
- Modify: `src/storygen/web/routes_series.py`:
  - `series_rename`, `series_delete`, `series_new_book`, `series_new_bible` → `require_series_long_prose(repo, series_id)`;
  - `story_series`, `story_series_refresh`, `story_series_facts`, `story_series_decisions` → `require_long_prose_for(repo, story_id)`;
  - `series_page(series_id)` → 404, якщо не `series_long_prose(repo, series_id)`;
  - `series_create`, `series_index_page` — без змін (книги ще немає; PR 2/3).
- Modify: `src/storygen/web/long_prose_guard.py::blocked` — ранній вихід за `build_edition.current().long_prose` лишається; після `structured_story` повертає `None`, якщо `long_prose_for(app.state.repo, found[0])`.
- Modify: `src/storygen/authoring/imports.py:83` (`_plan`) → `long_prose_for(repo, story)`; `:142` (`_enter_series`) → `story_long_prose(repo, story_id)`.
- Modify: `src/storygen/storage/plan_preamble.py:22` — `_series_lines(repo, story_id, text)` → `story_long_prose(repo, story_id)`; виклик у `replace_plan_preamble`.
- Modify: `SPEC.MD`, BUILD-EDITION-001 «Технічний опис», пункт «Довга проза»: перевірки, де відома книга чи серія, питають `long_prose_for` / `story_long_prose` / `series_long_prose` (`book/guard.py`); `require_long_prose()` лишається там, де книги ще немає (створення серії, імпорт рукопису).

**Interfaces:**
- Consumes: функції Task 1.

- [ ] **Step 1: Write the failing test** у `tests/web/test_long_prose_guard.py` (новий тест, наявні не змінюються):

```python
@pytest.mark.req('BUILD-EDITION-001')
def test_guards_ask_the_book_predicate(tmp_path, store_edition, monkeypatch):
    """R-47 PR 1: a predicate that says yes for this book lets its writes through; PR 2 makes the trial say yes."""
    client, app, repo, story, scene = setup(tmp_path)
    from storygen.book import guard
    monkeypatch.setattr(guard, 'long_prose_for', lambda repo, item: item.id == story.id)
    monkeypatch.setattr(guard, 'story_long_prose', lambda repo, story_id: story_id == story.id)
    response = client.put(f'/api/stories/{story.id}/structure', json={'parts': PARTS, 'scene_arcs': {}, 'expected_revision': story.revision})
    assert response.status_code != 400 or READ_ONLY not in response.text
    assert client.patch(f'/api/stories/{story.id}', json={'title': 'Нова', 'expected_revision': story.revision}).status_code == 200
```

(Тіла запитів — за чинними моделями маршрутів; мета — показати, що і маршрут структури, і middleware питають предикат.)

- [ ] **Step 2: Run, expect FAIL** — `PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest tests/web/test_long_prose_guard.py -q`.
- [ ] **Step 3: Implement** the call-site changes above. Імпорт предикатів — через модуль (`from ..book import guard` → `guard.long_prose_for(...)`), щоб підміна в тестах діяла, як із `build_edition.current()`.
- [ ] **Step 4: Run** the new test → PASS; then the related suites unchanged → PASS:
  `PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest tests/web/test_long_prose_guard.py tests/series tests/authoring tests/web/test_memory_merges_api.py tests/web/test_book_structure_ui.py tests/application/test_manuscript_import_apply.py tests/mcp/test_bridge_edition.py tests/test_build_edition.py -q`
- [ ] **Step 5:** `git diff --stat origin/main -- tests` показує лише нові тести (жоден наявний тест не змінено). `PYTHONUTF8=1 .venv/Scripts/python.exe scripts/check_docs.py` → узгоджено.
- [ ] **Step 6: Commit** `refactor(R-47): перевірки довгої прози питають про книгу чи серію`. У повідомленні: «Користувацька документація не змінюється: поведінка та сама».

## Завершення

Повний `scripts/verify.py` з `C:/tmp/r47a`, cross-review, PR на `main` (без «Closes #287»).
