# R-48 Імпорт рукопису — ядро (PR 1): план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Сервер розбирає рукопис DOCX/Markdown/TXT на частини, глави й сцени, пропонує межі для задовгих сцен, віддає перегляд через API і одним атомарним записом створює нову книгу з авторською прозою; SPEC MANUSCRIPT-IMPORT.

**Architecture:** Розбір складається з двох чистих шарів:
- `publication/manuscript_read.py` — файл → абзаци;
- `publication/manuscript_structure.py` — абзаци → сцени й частини, межі.

Служба `application/manuscript_import.py` тримає тимчасовий файл (як імпорт редакції) і будує перегляд. Збереження виконує нова `storage/manuscript_store.py::publish_manuscript` в одній транзакції. Маршрути `web/routes_manuscript_import.py` працюють на рівні бібліотеки. Інтерфейс, побудова пам'яті з вартістю, MCP і сайт — у PR 2, окремим планом після рев'ю ядра.

**Tech Stack:** Python 3.12, FastAPI, SQLite, pytest; `zipfile` + `xml.etree` (читач DOCX R-46).

**Spec:** `docs/superpowers/specs/2026-11/2026-11-25-manuscript-import-design.md` (§3, §4.1–4.3, §8; проби §2).

## Global Constraints

**Вхід і ліміти**
- Формати: `.docx`, `.md`, `.txt`. MD і TXT — UTF-8, з BOM чи без; інше кодування — 400.
- Файл до 20 МіБ (413); розпакований DOCX до 100 МіБ (константи R-46 `MAX_FILE`, `MAX_UNPACKED`).
- Тимчасовий файл: `<data_dir>/manuscript-import/{import_id}.<ext>`, TTL 24 год. Він поза резервною копією й fsck (додати до `storage/integrity.py::NOT_DATA`) і прибирається під час запуску застосунку та кожного перегляду.

**Розбір**
- Типові маркери глав: «Глава», «Розділ», «Chapter». Типові маркери частин: «Частина», «Книга», «Part», «Book». Маркер частини діє лише з номером: арабським, римським чи порядковим словом.
- Абзац-маркер — до 120 символів.
- Розділювач — абзац лише з символів `* # — – ~ ⁂ • ·` і пробілів, від 1 до 12 непробільних символів. Порожні рядки розділювачами не є.
- Пролог — текст перед першою главою, якщо він довший за 50 слів. Коротша передмова за замовчуванням не імпортується; перегляд пропонує її приєднати до першої сцени (`include_front_matter`).
- Поріг поділу — 2 500 слів. Крім того, межі пропонуються, якщо сцена не вміщується в ліміти ролі пам'яті: і `max_input_chars`, і бюджет токенів (контекст мінус резерв виходу).

**Збереження й межі видання**
- Проза зберігається як `kind='manual'`, `complete=True`. `content_format='markdown'` для DOCX і MD, `'plain'` для TXT. Знімок залежностей — `_manual_snapshot`.
- Позначка походження — `VersionRef.manuscript_import: ManuscriptImportOrigin{file_name, file_sha256, imported_at}`. `ExternalOrigin` не використовується.
- Безкоштовне видання (`build_edition.current().long_prose == False`): `parts` або `series` дають 400 з `book.guard.NO_LONG_PROSE` (через `require_long_prose()`) до будь-якого запису.

**Тексти**
- Тексти сервера для автора — українською, з англійськими ключами в `static/i18n.json` за правилом каталогу (`web/localization.py`).

## Review Focus

1. **Локалізований Word.** `styleId` заголовка перекладено («1», «Заголовок1»), а `w:name = heading 1`. Глави мають розпізнатися (Task 1).
2. **Рукопис без заголовків і маркерів.** Увесь текст — одна глава з попередженням, а якщо вона довга — запропоновані межі. Розбір не падає (Task 2).
3. **Збій посередині збереження**, наприклад на 40-й сцені з 60. У БД не лишається ні книги, ні сцен, а записані файли версій прибрано (Task 4).
4. **Межі, що не відповідають файлу.** Межа всередині абзацу, неспадний порядок, порожня сцена або застарілий відбиток дають 400/409 без запису (Task 4).
5. **Безкоштовне видання з частинами в рукописі.** Перегляд пропускає частини з попередженням, а запит із `parts` чи `series` відхиляється до запису (Task 3, Task 4).

---

### Task 1: Читання рукопису в абзаци

**Files:**
- Modify: `src/storygen/publication/docx_import.py` — `DocxParagraph` отримує `heading_level: int | None`. Рівень береться з `w:outlineLvl` абзацу, інакше зі стилю за ланцюжком `basedOn` у `word/styles.xml`; інакше з `w:name` стилю `heading N` (дає N−1). `DocxManuscript` отримує `title_paragraphs: tuple[int, ...]` — індекси абзаців зі стилем, чий `w:name` = `title`.
- Create: `src/storygen/publication/manuscript_read.py`
- Create: `tests/publication/manuscript_fixtures.py` — генератори DOCX (zip + XML), MD і TXT
- Test: `tests/publication/test_manuscript_read.py`

**Interfaces:**
- Produces:
  - `ManuscriptParagraph(index: int, text: str, runs: tuple[Run, ...], heading_level: int | None, after_break: bool, is_title: bool)`. Тут `after_break` означає, що перед абзацом у файлі був порожній рядок чи порожній абзац.
  - `ReadManuscript(paragraphs: tuple[ManuscriptParagraph, ...], warnings: tuple[str, ...], tracked_changes: int)`
  - `read_manuscript(content: bytes, file_name: str) -> ReadManuscript`, яка кидає `ManuscriptError(message)`, де `message` — текст для автора: розширення, кодування, битий DOCX.
- Consumes: `read_docx` (R-46). Його погляд редактора — текст рукопису. `tracked_changes` — кількість абзаців з `changed=True`.

- [ ] **Step 1: Write the failing tests.** Фікстури будуються кодом, без бінарних файлів у репозиторії.
  - `test_docx_heading_by_name_when_style_id_localized` — `styleId="1"`, `w:name="heading 1"` → `heading_level == 0`.
  - `test_docx_heading_by_outline_level` — стиль без імені `heading`, але з `w:outlineLvl=1` → `heading_level == 1`.
  - `test_docx_title_style` — абзац стилю `Title` → `is_title`.
  - `test_docx_tracked_changes_counted` — дві правки Word → `tracked_changes == 2`, текст — погляд редактора.
  - `test_markdown_headings_and_emphasis` — `# Частина 1`, `## Глава 1`, `*курсив*` → рівні 0 і 1, run з `italic`.
  - `test_txt_paragraphs_by_blank_lines` і `test_txt_lines_when_no_blank_lines`.
  - `test_after_break_marks_blank_line`.
  - `test_bom_accepted_and_non_utf8_rejected` — cp1251-байти → `ManuscriptError`.
  - `test_unknown_extension_rejected`.
- [ ] **Step 2: Run** `PYTHONUTF8=1 .venv/Scripts/python -m pytest tests/publication/test_manuscript_read.py -q`. Expected: FAIL (module not found).
- [ ] **Step 3: Implement.** Зміни в `docx_import.py` не повинні ламати тести R-46: `tests/publication/test_docx_import.py`, `test_editor_import*.py`.
- [ ] **Step 4: Run** новий тест і тести R-46. Expected: PASS.
- [ ] **Step 5: Commit** `feat(manuscript): читання рукопису DOCX, Markdown і TXT в абзаци`.

### Task 2: Структура рукопису й механічні межі

**Files:**
- Create: `src/storygen/publication/manuscript_structure.py`
- Test: `tests/publication/test_manuscript_structure.py`

**Interfaces:**
- Consumes: `ManuscriptParagraph` з Task 1.
- Produces:
  - `ParseSettings(chapter_markers: tuple[str, ...] = ('Глава','Розділ','Chapter'), part_markers: tuple[str, ...] = ('Частина','Книга','Part','Book'), chapter_source: Literal['auto','markers',1,2,3] = 'auto', parts_allowed: bool = True)`
  - `ProposedScene(start: int, end: int, title: str, words: int, part_index: int | None, proposed: bool, warnings: tuple[str, ...])`. Діапазон `start`/`end` — індекси абзаців прози (включно), без абзаців-заголовків і розділювачів; `proposed=True` — межу на початку поставила механічна пропозиція.
  - `Structure(title_suggestion: str | None, chapter_source: str, parts: tuple[tuple[int, str], ...], scenes: tuple[ProposedScene, ...], front_matter: tuple[int, ...], dropped: tuple[tuple[int, str], ...], warnings: tuple[str, ...])`
  - `detect(paragraphs, settings, fits: Callable[[str], bool] = lambda text: True) -> Structure`. Тут `fits(text)` повертає, чи вміщується проза сцени в ліміти ролі пам'яті; служба Task 3 передає справжню перевірку.
  - `split_points(paragraphs, start: int, end: int, parts: int) -> list[int]` — механічні межі за правилами spec §3.5.
  - `words(text: str) -> int`

- [ ] **Step 1: Write the failing tests:**
  - `test_markers_win_over_styles` — два абзаци «Глава 1», «Глава 2» стилем Normal і Heading 2 усередині → главами є маркери.
  - `test_chapter_level_is_highest_repeated` — два Heading 1 з Heading 2 усередині → главами є Heading 1, а Heading 2 лишаються абзацами прози.
  - `test_part_heading_excluded_from_level` — Heading 1 «Part One» + Heading 2 глави → частина й глави.
  - `test_part_marker_needs_number` — «Книга пам'яті» не є частиною, «Книга друга» є.
  - `test_parts_skipped_when_not_allowed` — `parts_allowed=False` → `parts == ()` і попередження.
  - `test_separator_splits_chapter` — `* * *` і `⁂` ділять главу й не потрапляють у прозу; назви «<глава> (1)», «<глава> (2)».
  - `test_blank_line_is_not_separator`.
  - `test_prologue_over_50_words`, `test_short_front_matter_kept_aside` — `front_matter` непорожній, сцени не містять цих абзаців.
  - `test_title_from_title_style`.
  - `test_no_headings_one_chapter_with_warning`.
  - `test_long_scene_gets_proposed_split` — 6 000 слів → 2 межі (k = ⌈6000/2500⌉ − 1), кожна на межі абзаців у вікні ±20%.
  - `test_split_prefers_break_then_non_dialogue` — кандидат після порожнього рядка виграє в ближчого кандидата без нього; абзац, що починається з тире, не стає першим.
  - `test_single_long_paragraph_warns` — один абзац на 3 000 слів → без меж, з попередженням «довгий абзац без меж».
  - `test_fits_false_triggers_split` — 2 000 слів і `fits` повертає False для цілої сцени → межа, після якої кожна частина `fits`.
  - `test_chapter_source_override` — `chapter_source=2` дає главами Heading 2.
- [ ] **Step 2: Run** `PYTHONUTF8=1 .venv/Scripts/python -m pytest tests/publication/test_manuscript_structure.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Розпізнавання номерів:
  - арабські цифри;
  - римські `I…MMM`;
  - порядкові слова uk/en від 1 до 20 («перша», «перший», «друга»… / «one»… «twenty», «first»… «twentieth»), без урахування регістру.

  Назва сцени — текст після маркера й номера, без провідних `.:—-` і пробілів, а якщо після номера нічого немає — весь абзац.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(manuscript): глави, частини, розділювачі й механічні межі сцен`.

### Task 3: Служба перегляду й API

**Files:**
- Create: `src/storygen/application/manuscript_import.py`
- Create: `src/storygen/web/routes_manuscript_import.py`
- Modify: `src/storygen/web/app.py` — роутер і прибирання тимчасової теки в lifespan (поруч з `editor_import.sweep_temp`)
- Modify: `src/storygen/storage/integrity.py` — `MANUSCRIPT_IMPORT_DIR = 'manuscript-import'` у `NOT_DATA`; перевірити, що backup теж його пропускає (як `editor-import`, коміт `17958693`)
- Modify: `src/storygen/web/long_prose_guard.py::ALLOWED` — нові маршрути з причиною «книги ще немає / не змінює книгу»
- Modify: `src/storygen/web/static/i18n.json` — тексти сервера (uk + en)
- Test: `tests/application/test_manuscript_import_preview.py`, `tests/web/test_routes_manuscript_import.py`

**Interfaces:**
- Consumes: `read_manuscript` (Task 1), `detect`, `ParseSettings` (Task 2).
- Produces:
  - `memory_fits(repo) -> Callable[[str], bool]`. Оцінює запит пам'яті для прози: прозу враховано двічі (прямо й фрагментами-доказами) плюс верхню межу попередньої пам'яті й налаштувань. Перевіряються `max_input_chars` і бюджет токенів ролі пам'яті через чинний `token_budget`. Межу попередньої пам'яті беріть з налаштувань контексту пам'яті, а не вгадуйте.
  - `preview(repo, content: bytes, file_name: str, settings: ParseSettings, import_id: str | None = None, *, now=None) -> ManuscriptPreview`. З `import_id` файл береться з тимчасової теки, а `content` ігнорується.
  - `ManuscriptPreview{import_id, fingerprint, file_name, title_suggestion, chapter_source, scenes: list[ProposedScene], parts, front_matter: list[int], dropped, warnings, tracked_changes, edition: {parts_allowed, series_allowed}}`. `fingerprint` = sha256 файла + канонічний JSON `ParseSettings`.
  - `paragraphs(repo, import_id, start, end) -> list[{index, text_head (≤160), words, heading_level, after_break}]`, до 2 000 за запит.
  - `discard(repo, import_id)`, `sweep_temp(repo, *, now=None) -> int`, `load(repo, import_id) -> tuple[bytes, str]`.
  - HTTP:
    - `POST /api/manuscript-import/preview` (multipart `file`, або форма з `import_id`; поля `chapter_markers`, `part_markers`, `chapter_source`);
    - `GET /api/manuscript-import/{import_id}/paragraphs?start=&end=`;
    - `DELETE /api/manuscript-import/{import_id}` → 204.
    - Помилки: 413 розмір; 400 формат або кодування; 404 невідомий чи прострочений `import_id`. `import_id` — 32 hex, інше → 404.

- [ ] **Step 1: Write the failing tests:**
  - `test_preview_keeps_temp_file_and_fingerprint`.
  - `test_repreview_with_markers_changes_fingerprint`.
  - `test_paragraphs_range_and_cap`.
  - `test_sweep_removes_old_files`.
  - `test_temp_dir_outside_backup_and_fsck`.
  - `test_store_edition_skips_parts_with_warning` — `build_edition` у режимі `store`, як у чинних тестах видання.
  - `test_memory_fits_uses_tokens_and_chars` — роль пам'яті з малим контекстом токенів → сцена 2 000 слів не вміщується.
  - Маршрути: 413, 400 для cp1251 TXT, 404 для чужого `import_id`, 204 для DELETE.
  - `tests/web/test_long_prose_guard.py` має проходити з новими маршрутами.
- [ ] **Step 2: Run** обидва тестові файли. Expected: FAIL.
- [ ] **Step 3: Implement** за зразком `application/editor_import.py` (тимчасова тека, `sweep_temp`) і `web/routes_editor_import.py` (multipart, перевірка `import_id`).
- [ ] **Step 4: Run** нові тести, `tests/web/test_long_prose_guard.py`, `tests/web/test_localization.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(manuscript): перегляд імпорту рукопису й тимчасовий файл`.

### Task 4: Атомарне збереження книги

**Files:**
- Modify: `src/storygen/domain.py` — `ManuscriptImportOrigin(file_name: str, file_sha256: str, imported_at: datetime)` і необов'язкове `VersionRef.manuscript_import`
- Modify: `src/storygen/repository.py` — додати `manuscript_import` до ключів збереження payload, якщо там є перелік, як для `editor_import`
- Create: `src/storygen/storage/manuscript_store.py`
- Modify: `src/storygen/application/manuscript_import.py` — `apply_import`
- Modify: `src/storygen/web/routes_manuscript_import.py` — `POST /api/manuscript-import/{import_id}`
- Test: `tests/storage/test_manuscript_store.py`, `tests/application/test_manuscript_import_apply.py`

**Interfaces:**
- Consumes: `preview`/`load` (Task 3), `detect` (Task 2), `_manual_snapshot` (`generation/dependencies.py`), `place_imported` (`storage/book_structure.py`), `set_story_series` (`storage/series.py`), `require_long_prose` (`book/guard.py`).
- Produces:
  - `ManuscriptApply(fingerprint: str, title: str (1..300), language: Literal['uk','en'], content_rating: ContentRating | None, scenes: list[{start: int, title: str (1..200), part_index: int | None}], parts: list[{index: int, title: str}], include_front_matter: bool = False, series: {series_id: str, number: int} | None)`.
  - `apply_import(repo, import_id, body) -> {story_id, scene_ids, warnings}`.
  - `publish_manuscript(repo, story: StoryCreate, scenes: list[(title, text, content_format, part_title|None, target_words)], origin: ManuscriptImportOrigin, structured: bool) -> tuple[Story, list[Scene]]`. Він пише файли версій, далі одна транзакція `BEGIN IMMEDIATE`: книга, сцени, рядки версій, голови `prose`, `place_imported`, порядок сцен. На помилці — відкат і прибирання записаних файлів версій.

- [ ] **Step 1: Write the failing tests:**
  - `test_publish_creates_story_scenes_and_manual_prose` — у кожної сцени голова `prose` виду `manual`, `complete`, `manuscript_import.file_sha256` дорівнює sha256 файла; `target_words` = слова сцени.
  - `test_publish_rolls_back_on_failure` — збій, вставлений на N-й сцені (monkeypatch `_insert_version_row`), не лишає ні книги, ні сцен, ні файлів версій.
  - `test_markdown_format_for_docx_and_md_plain_for_txt` — DOCX з курсивом → `*…*` у прозі.
  - `test_apply_rejects_stale_fingerprint` (409), `test_apply_rejects_boundary_inside_paragraph_or_unsorted_or_empty` (400). Межа — лише індекс абзацу прози з `detect`, і лише в межах тих самих абзаців.
  - `test_apply_scene_boundaries_from_author` — автор прибрав запропоновану межу й додав свою → сцени за запитом.
  - `test_front_matter_included_when_requested`.
  - `test_store_edition_rejects_parts_and_series_before_write` — 400 `NO_LONG_PROSE`, кількість книг незмінна.
  - `test_series_number_and_start` — платне: книга в серії з номером; номер зайнятий → 400 без книги. Якщо `set_story_series` іде окремим кроком після транзакції, його збій видаляє щойно створену книгу (компенсація), і тест це перевіряє.
  - `test_plan_written_later_does_not_stale_prose_or_memory` — проба spec §2.5: після імпорту зберегти план сцени → `scene_links(...)['memory']` і голова прози не стають застарілими. Сцену без пам'яті перевіряйте на голові прози.
  - `test_temp_file_removed_after_apply`.
  - `test_integrity_ok_after_import` — `check_integrity` на теці після імпорту дає `ok`.
- [ ] **Step 2: Run** обидва файли. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** нові тести, `tests/storage/`, `tests/publication/`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(manuscript): атомарне створення книги з рукопису`.

### Task 5: SPEC, traceability, журнал

**Files:**
- Modify: `SPEC.MD` — новий `### Requirement: MANUSCRIPT-IMPORT — Імпорт рукопису` (технічний опис за spec §3–4, інваріанти §8, відомі обмеження §9) зі сценаріями:
  - S01 — читання DOCX/MD/TXT і кодування;
  - S02 — глави за маркерами й стилями, локалізований `styleId`;
  - S03 — частини й межі видання;
  - S04 — розділювачі, пролог, передмова;
  - S05 — механічні межі, зокрема за лімітом пам'яті;
  - S06 — перегляд, тимчасовий файл, абзаци частинами;
  - S07 — атомарне збереження й походження прози;
  - S08 — перевірка меж і відбитка;
  - S09 — серія;
  - S10 — план, дописаний пізніше, не застарює прозу й пам'ять.

  У розділі цілісності й резервування згадати теку `manuscript-import`. У відомих обмеженнях MANUSCRIPT-IMPORT записати: інтерфейс, вартість пам'яті й MCP — у наступному PR.
- Modify: `docs/verification/traceability.json` — кожен сценарій → тести Task 1–4
- Modify: `docs/superpowers/plans/2026-10-20-remediation-progress.md` — запис R-48 PR 1

- [ ] **Step 1: Write SPEC and traceability.**
- [ ] **Step 2: Run** `PYTHONUTF8=1 .venv/Scripts/python scripts/check_docs.py`. Expected: OK.
- [ ] **Step 3: Full suite** з короткого шляху (AGENTS.md: detached worktree у `C:/tmp/<коротка>`, junction на `.venv`): `PYTHONUTF8=1 .venv/Scripts/python -m pytest -q -p no:cacheprovider`. Expected: PASS.
- [ ] **Step 4: Commit** `docs(manuscript): SPEC MANUSCRIPT-IMPORT S01–S10 і журнал`. У тілі коміту — сайт не змінюється до PR 2, бо інтерфейсу ще немає.
