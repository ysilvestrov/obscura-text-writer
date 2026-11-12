# MCP, пакет 4: публікація з чату — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** чат читає й частково оновлює картку публікації, додає підпис, завантажує обкладинку з локального файла й експортує книгу; відкрита сторінка публікації помічає зміни ззовні.

**Architecture:** сервер отримує лише маршрут каталогу жанрів; решта — наявні маршрути. Клієнт `storygen-mcp` додає п'ять інструментів (злиття картки поверх прочитаної ревізії, перевірка локального шляху обкладинки). Рішення сторінки про оновлення — чиста функція `static/publication-sync.js` з node-тестом.

**Tech Stack:** Python 3.12, FastAPI, httpx, `mcp==2.3.0`, ES modules, pytest, node.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-12-mcp-p4-publication-design.md` (затверджено 2026-11-12; обкладинка — файлом, експорт — посилання).

## Global Constraints

- Нічого платного; `publication_suggest` не викликається.
- Обкладинка: мережеві шляхи (UNC `\\host\share`, `//host/share`, `\\?\`, `\\.\`, шлях без літери диска на Windows) відхиляються до звернення до файлової системи; після `os.path.realpath` — знову без UNC і на Windows `GetDriveTypeW(корінь) != 4` (`DRIVE_REMOTE`); звичайний файл, `.png`/`.jpg`/`.jpeg` (без урахування регістру), ≤ `10*1024*1024` байт.
- Відповіді інструментів не містять `relative_path` чи інших внутрішніх шляхів.
- `update_publication`: невідоме поле чи порожній `fields` → помилка без запиту; ревізія ≠ прочитаній → помилка без `PUT`.
- Експорт повертає повну адресу `download_url` на базі `--url` і підсумок manifest; шляху до файла немає.
- Тексти сторінки — `i18n.json` uk/en, лише `textContent`.

## Review Focus

1. `update_publication` з `author_ids`, де підпис архівований і новий для картки → сервер 400; помилка доходить до чату.
2. `fields` з `cover_id` чужого твору → сервер 400, картка не змінена.
3. Шлях обкладинки з `..` чи символьним посиланням на мережевий диск → відмова.
4. Сторінка: брудна форма й зміна ззовні — текст автора не перезаписується.
5. Експорт незавершеного твору без `allow_incomplete` → помилка з текстом сервера.

---

### Task 1: Сервер — каталог жанрів; сторінка помічає зміни ззовні

**Files:** Modify `src/storygen/web/routes_publication.py`, `src/storygen/web/static/publication.js`, `src/storygen/web/static/i18n.json`; Create `src/storygen/web/static/publication-sync.js`; Test `tests/web/test_publication_genres.py`, `tests/web/js/publication_sync.mjs` (обгортка в `tests/web/test_publication_genres.py`).

**Produces:** `GET /api/publication/genres?language=uk|en` → `{"genres": [{"code","label"}]}` (невідома мова → 422); `externalPublicationChange({loadedRevision, freshRevision, formDirty, busy, loadedLibrary, freshLibrary, libraryDirty}) -> {reloadCard, warnCard, reloadLibrary}` (бібліотеки — списки `{id, revision, archived_at}`; порівняння за набором і ревізіями).

- [ ] Тести: маршрут для `uk` і `en` збігається з `genre_catalog`; `de` → 422. Node: однакова ревізія й бібліотека → усе `false`; інша ревізія, чиста форма → `reloadCard`; інша ревізія, брудна форма чи `busy` → `warnCard`; новий підпис при нередагованому довіднику → `reloadLibrary`; при редагованому → `false`.
- [ ] RED; реалізація; у `publication.js` обробник `visibilitychange`/`focus` (≥ 2 с, без паралельних), що читає картку й довідник і діє за рішенням: `load()` / повідомлення `publication.changed_elsewhere` / `library=fresh; renderLibrary(); renderPeople()`.
- [ ] GREEN, `pytest tests/web -q`; commit `feat(publication): genres route; the page notices outside changes`.

### Task 2: Клієнт — п'ять інструментів публікації

**Files:** Modify `src/storygen/mcp/bridge.py`; Test `tests/mcp/test_bridge_publication.py`, `tests/mcp/test_bridge.py` (18 інструментів).

- [ ] Тести через справжній застосунок: `get_publication` (поля, ревізія, підписи, обкладинка без `relative_path`, жанри з `genres_language`); `update_publication` лишає інші поля, застаріла ревізія без `PUT`, невідоме поле без запиту; `add_signature` → FB2 без жанру 400, з автором і жанром → `download_url`; `upload_cover` PNG → `cover_id`, прив'язка `update_publication`; відмови: UNC, `\\?\`, відносний, `.gif`, понад 10 MiB (sparse-файл), не-зображення (400 сервера); `export_book` незавершеного твору → помилка, `allow_incomplete=True` → `complete: false`; ідентифікатори з `..` — без запиту.
- [ ] RED; реалізація за таблицею специфікації; GREEN `pytest tests/mcp -q`; commit `feat(mcp): publication tools`.

### Task 3: Контракт і документація

- [ ] SPEC: MCP-BRIDGE (18 інструментів, S06, S26–S30, обмеження), R16-META (маршрут жанрів, оновлення сторінки, S31 у MCP-BRIDGE); traceability; сайт `mcp` і `publication` uk/en, `check_site.py --rehash`; `check_docs.py`; commit.
