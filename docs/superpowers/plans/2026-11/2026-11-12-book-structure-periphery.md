# Структура книги — периферія: план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Режим лише для читання структурованої книги у виданні без довгої прози, `long_prose` в `app-info` і `--edition paid` у скрипті збирання; частини в експорті MD/TXT/FB2/EPUB/PDF; згрупований список сцен, панель «Структура книги» й поле «Арка»; користувацька документація uk/en.

**Architecture:** Запобіжник — одна перевірка в наявному HTTP-middleware (`web/app.py::local_requests`): у виданні без довгої прози для маршрутів запису й генеративних GET визначає твір (параметр шляху або `story_id` у тілі), і для структурованої книги відповідає 400. Маршрути поза перевіркою — явний список із причиною; тест обходить таблицю маршрутів. Експорт отримує частини з `effective_structure` у `publication/book.py::capture`; пласка книга не змінюється байт у байт. Інтерфейс читає `book_structure` і `arc_id` з `GET /api/stories/{id}`.

**Tech Stack:** Python 3.12, FastAPI/Starlette middleware, ElementTree, ReportLab; vanilla JS ES modules, node:test, Playwright.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-12-book-structure-design.md` (розділи «Експорт», «Інтерфейс», «Видання», сценарії S05, S06, BUILD-EDITION-001-S08/S09).

## Global Constraints

- Повідомлення сервера українською з ключами в `i18n.json` для інтерфейсу (uk/en).
- Пласка книга: експорт усіх форматів і інтерфейс — без змін (наявні тести без правок).
- Частина без назви — «Частина N» (uk) / «Part N» (en) за мовою твору; арки не експортуються.
- Видання `full`/`paid` — запобіжник не діє (жодного додаткового читання БД).
- Документація сайту — пари `docs/site/{uk,en}`, `python scripts/check_site.py --rehash <slug>`; нейтральні приклади.

## Review Focus

1. Новий маршрут запису без запису в списку дозволених і без перевірки — тест обходу має впасти.
2. `POST /api/runs` без твору в шляху — твір береться з тіла, тіло потім читається обробником без втрат.
3. Пласка книга в `store` працює повністю (одна частина й одна арка з назвами — теж).
4. EPUB/FB2 зі структурою проходять власні перевірки (XSD FB2, структурна перевірка EPUB), а PDF узгоджує зміст із двома рівнями.
5. Інтерфейс: `selectScene` і нумерація сцен не ламаються від заголовків груп (заголовки — не `.scene-item`).

---

### Task 1: Запобіжник видання, app-info, скрипт збирання

**Files:** Create `src/storygen/web/long_prose_guard.py`; Modify `src/storygen/book/structure.py` (`structure_kind`), `src/storygen/book/guard.py`, `src/storygen/web/app.py`, `src/storygen/web/routes_app_info.py`, `scripts/build_store.py`; Test `tests/web/test_long_prose_guard.py`, `tests/web/test_app_info.py`, тест скрипта збирання.

**Interfaces:**
- `book.structure.structure_kind(story, scenes) -> Literal['flat','structured']`.
- `book.guard.enforce_long_prose(story, scenes)` — `ValueError(READ_ONLY)` для `structured` у виданні без довгої прози.
- `web.long_prose_guard.ALLOWED: dict[tuple[method, path], reason]`, `GENERATIVE_GET: set[path]`, `async blocked(app, request) -> str | None`.
- `GET /api/app-info` → `long_prose: bool`.

- [ ] Тест обходу: застосунок у `store`, структурована книга (структура записана сховищем), для кожного маршруту з не-GET методом або в `GENERATIVE_GET`: якщо `(метод, шлях)` у `ALLOWED` — пропуск із непорожньою причиною; інакше запит із підставленими ID твору/сцени/запуску й порожнім тілом `{}` (для тіла з `story_id` — `{"story_id": ...}`) повертає 400 з текстом запобіжника. Пласка книга в `store`: `PATCH /api/stories/{id}` працює. Видання `full`: структурована книга — `PATCH` працює.
- [ ] `app-info`: `long_prose` true/false; `build_store --edition paid` приймається.
- [ ] Реалізація, PASS, commit `feat(edition): read-only structured books without long prose`.

### Task 2: Частини в експорті

**Files:** Modify `src/storygen/publication/book.py`, `src/storygen/application/exports.py`, `src/storygen/publication/{fb2,epub,pdf}.py`; Test `tests/authoring/test_export_parts.py`.

**Interfaces:** `Chapter.part_index: int | None = None`; `Book.parts: tuple[str, ...] = ()` (ефективні назви, «Частина N» для порожніх).

- [ ] Тести: структурована книга з двома частинами: MD — `#` книга, `## Перша`, `### Сцена`; друга частина без назви — `## Частина 2`; TXT — назва частини окремим абзацом; FB2 — вкладені `section` і валідна XSD; EPUB — документ частини в spine і вкладений `ol` у змісті, структурна перевірка проходить; PDF — рендер успішний (якщо ReportLab є). Пласка книга — MD ідентичний до зміни (наявні тести).
- [ ] Реалізація, PASS разом з `tests/authoring/test_*exports*.py`, commit `feat(export): book parts in all formats`.

### Task 3: Інтерфейс

**Files:** Modify `src/storygen/web/static/editor.js` (список сцен), сторінка налаштувань твору (панель), `scene-settings.js` (поле «Арка»), `src/storygen/web/static/i18n.json`; Create `src/storygen/web/static/book-structure.js`; Test node-тести в `tests/web/js/`, Playwright-сценарій.

- [ ] `book-structure.js`: чисті функції `groupScenes(structure, scenes)` (заголовки частин/арок перед першою сценою групи; для `flat` — без заголовків), `arcOptions(structure)` («Частина › Арка»), `editBuffer` (додати/перейменувати/перемістити/видалити з правилами специфікації). Node-тести на них.
- [ ] Список сцен: заголовки груп `<li class="scene-group">` не кнопки; мобільний select — `<optgroup>`. Панель «Структура книги» на сторінці налаштувань: `PUT /structure`, «Розформувати» — `DELETE` після підтвердження; помилка сервера показується, буфер лишається. Поле «Арка» в параметрах сцени — `PUT .../arc`. У виданні без довгої прози (`app-info.long_prose=false`) панелі й поля немає, структурована книга показує банер лише для читання.
- [ ] Playwright: структурована книга — заголовки груп видно, зміна арки зберігається; пласка — без заголовків.
- [ ] Commit `feat(ui): book structure list, panel and scene arc field`.

### Task 4: Документація

- [ ] SPEC.MD: S05, S06, BUILD-EDITION-001-S08 (+ S05 `app-info` з `long_prose`), технічний опис (експорт, інтерфейс, запобіжник); traceability; `check_docs.py`.
- [ ] Сайт: сторінка імпорту/структури uk+en (частини й арки в плані, панель, експорт, видання), `check_site.py --rehash <slug>`.
- [ ] Commit `docs: book structure periphery in SPEC and site`.
