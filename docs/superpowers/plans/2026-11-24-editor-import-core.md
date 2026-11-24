# R-46 Імпорт редакції з DOCX — ядро (PR 1): план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Сервер приймає DOCX, правлений редактором, показує зведення по сценах і за підтвердженням записує для кожної сцени нову чернетку, пропозицію редактури без моделі й коментарі з приміток Word.

**Architecture:**
- **Читач** `publication/docx_import.py`: `zipfile` + `ElementTree` розбирає DOCX на абзаци, закладки, два погляди тексту (редактор / оригінал) і примітки.
- **Текст** `publication/docx_text.py`: серіалізує абзаци в текст сцени й нормалізує прозу через `chapter_paragraphs`.
- **Служба** `application/editor_import.py`:
  - розпізнає сцени;
  - будує зведення з тимчасовим файлом;
  - записує результат: чернетку з коментарями через розширений `save_draft_with_comments` і синтетичну спробу `edit` у тій самій транзакції.
- **API** — новий `web/routes_editor_import.py`.

**Tech Stack:** Python 3.12, FastAPI/Starlette multipart, SQLite, pytest; без нових залежностей.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-24-editor-docx-import-design.md` (затверджено 24.11.2026). Розділ 6 спеки (інтерфейс), сайт і знімки — PR 2, окремий план після рев'ю ядра.

## Global Constraints

**Залежності й файли**
- Нових залежностей немає; `lxml` і `python-docx` заборонені.
- Читаються лише частини `word/document.xml`, `word/comments.xml`, `docProps/custom.xml`, `[Content_Types].xml`.

**Межі й відмови**
- Файл до 20 МіБ (`MAX_FILE=20*1024*1024`); сумарний розпакований розмір прочитаних частин до 100 МіБ (`MAX_UNPACKED=100*1024*1024`).
- Відмова з `ValueError`: не ZIP; OLE `EncryptedPackage`; немає `word/document.xml`; будь-який `<!DOCTYPE`.

**Нормалізація**
- Markdown: абзац — один рядок; абзаци через `\n`; порожній абзац — порожній рядок; `*курсив*`, `**жирний**`; екранування `\ ` * _ [ ] < > #` зворотною скісною.
- Plain: видимий текст абзаців через `\n`.

**Статуси зведення**
- `changed | comments_only | unchanged | changed_since_export | over_limit | unknown_base | no_prose | unsupported_markup | pending_review`.
- `needs_choice: true` мають `changed_since_export` і `unknown_base` (без маніфесту й з оригінальним поглядом ≠ `normalized(prose)`).
- Збереження: `changed_scenes ∈ {skip, replace}`, обов'язкове при `choice_required`, інакше 400.

**Тимчасове сховище**
- Файл: `<data_dir>/editor-import/{import_id}.docx`, живе 24 год.
- Прибирання: під час кожного зведення й у `lifespan` при старті сервера.
- `fingerprint` = sha256 від JSON `{file_sha256, export_id, scenes:[[scene_id, prose_head, prose_head_revision], …]}` (sort_keys, `ensure_ascii=False`, `separators=(',',':')`).

**Спроба й чернетка**
- Спроба: `StageAttempt(stage='edit', state='needs_review', run_id=None)`, `context['copyedit_proposal']={protocol_version:2, draft_id, proposal}`, `context['editor_import']={import_id, export_id, scene_index}`, без `edit_loop_summary`, `usage={}`.
- Чернетка: позначка походження — нове поле `VersionRef.editor_import: EditorImportOrigin | None` (`export_id: str | None`, `import_id: str`); лише метадані, як `external_origin`, не входить у sha256 і залежності.

**Коментарі**
- Межі R23-COMMENTS: 100 коментарів, `general` ≤ 12 000, інструкція ≤ 8 000, разом ≤ 50 000. Надлишок не імпортується й рахується в `dropped_comments`.
- Рядок загального коментаря: `Редактор ({author}) до «{quote}»: {text}`.
- Цитата до 200 символів з `…`. Для вставленого тексту додається позначка «вставлено редактором».
- Інструкція фрагментного коментаря: `Редактор ({author}): {text}`.

**Тексти**
- Тексти помилок і попереджень — українською.
- Документація українською; маркери OpenSpec англійською.

## Review Focus

1. **Редактор правив без режиму виправлень і повністю замінив назву сцени.** Закладка зникає. Людина чекає, що сцену знайде розпізнавання за місцем з попередженням «назву змінено редактором», а не покладе в «нерозпізнані» (тест у Task 3).
2. **Дві примітки Word на ту саму фразу або вкладені одна в одну.** Людина чекає, що імпорт не впаде: перша лишиться прив'язаною, друга стане загальним коментарем (тест у Task 4).
3. **Між зведенням і збереженням автор змінив прозу однієї сцени в іншій вкладці.** Людина чекає 409 «Твір змінився після зведення», а не часткового запису (тест у Task 5).
4. **Той самий файл імпортують двічі.** Людина чекає, що друга спроба не дублює пропозицій: сцени отримають `pending_review` (тест у Task 5).
5. **Прийняття правок імпорту через чинний перегляд редактури.** Людина чекає, що `select_copyedits` прийме синтетичну спробу й змінить прозу на вибрані правки (тест у Task 5, перший тест задачі).

---

### Task 1: Читач DOCX

**Files:**
- Create: `src/storygen/publication/docx_import.py`
- Test: `tests/authoring/test_docx_import.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True)
  class Run: text: str; bold: bool = False; italic: bool = False
  @dataclass(frozen=True)
  class DocxParagraph:
      style: str | None            # 'Heading1' | 'Heading2' | 'Title' | None
      bookmarks: tuple[str, ...]   # імена w:bookmarkStart у абзаці
      editor: tuple[Run, ...]      # w:ins лишається, w:del вилучено
      original: tuple[Run, ...]    # w:del лишається, w:ins вилучено
      changed: bool                # є w:ins/w:del в абзаці
  @dataclass(frozen=True)
  class DocxComment:
      id: str; author: str; text: str
      start: tuple[int, int] | None  # (індекс абзацу, зсув у '' .join(original)) — None, якщо меж немає
      end: tuple[int, int] | None
  @dataclass(frozen=True)
  class DocxManuscript:
      story_id: str | None; export_id: str | None
      paragraphs: tuple[DocxParagraph, ...]; comments: tuple[DocxComment, ...]
      warnings: tuple[str, ...]      # кожне з індексом абзацу
  def read_docx(content: bytes) -> DocxManuscript   # ValueError на відмову
  MAX_FILE: int; MAX_UNPACKED: int
  ```

- [ ] **Step 1: Write the failing tests.** Вихідний файл будують через `rendered()` з `tests/authoring/test_docx_exports.py` (і `flat_book`/`seeded`), зміни вносять через `_rewrite`.
  - `test_reads_exported_manuscript`: після експорту `read_docx` повертає `story_id`/`export_id` з `custom.xml`. Закладки `'_os'+scene_id` стоять на абзацах `Heading2` у порядку сцен. `editor == original` і `changed is False` для всіх абзаців. Пробіги курсиву й жирного з `test_docx_markdown_runs_and_controls` збігаються.
  - `test_tracked_changes_two_views`: абзац `<w:r><w:t>Він </w:t></w:r><w:del><w:r><w:delText>швидко</w:delText></w:r></w:del><w:ins><w:r><w:t>повільно</w:t></w:r></w:ins><w:r><w:t> пішов</w:t></w:r>`. Очікується `editor` → `'Він повільно пішов'`, `original` → `'Він швидко пішов'`, `changed is True`.
  - `test_comment_ranges_in_original_view`: `commentRangeStart`/`End` навколо слова «швидко» (у `w:del`). Очікується `start=(i, 4)`, `end=(i, 10)`. Автор і текст беруться з `comments.xml`.
  - `test_rejects`, параметризований:
    - не ZIP;
    - байти OLE (`b'\xd0\xcf\x11\xe0'+…`);
    - ZIP без `word/document.xml`;
    - `document.xml` з `<!DOCTYPE`;
    - файл понад `MAX_FILE`;
    - частина, що розпаковується понад `MAX_UNPACKED`: перевірка за `ZipInfo.file_size` і фактичним читанням блоками.

    Кожен випадок дає `ValueError`.
  - `test_unsupported_content_warns`: `w:drawing`, `w:tbl`, `w:footnoteReference` і `w:rPrChange` дають попередження з номером абзацу. Текст абзаців поруч читається.
- [ ] **Step 2: Run:** `.venv/Scripts/python -m pytest tests/authoring/test_docx_import.py -q`. Expected: FAIL (ImportError).
- [ ] **Step 3: Implement `read_docx`.**
  - Простори імен — як у `publication/docx.py` (`W`).
  - `w:br` → `'\n'`, `w:tab` → `'\t'`.
  - Таблиці не обходяться (лише попередження), абзаци в них пропускаються.
  - Сусідні пробіги з однаковими ознаками зливаються.
- [ ] **Step 4: Run** той самий pytest. Expected: PASS.
- [ ] **Step 5: Commit** `feat(import): читач DOCX редактора`.

### Task 2: Текст сцени й нормалізація

**Files:**
- Create: `src/storygen/publication/docx_text.py`
- Test: `tests/authoring/test_docx_text.py`

**Interfaces:**
- Consumes: `Run` з Task 1; `chapter_paragraphs` (`publication/markup.py:13`), `InlineRun`.
- Produces:
  ```python
  @dataclass(frozen=True)
  class SceneText:
      text: str
      offsets: tuple[tuple[int, ...], ...]  # для абзацу p: offsets[p][k] = позиція в text k-го видимого символу; offsets[p][len] = кінець абзацу
      def position(self, paragraph: int, offset: int) -> int
  def serialize(paragraphs: Sequence[Sequence[Run]], content_format: Literal['plain','markdown']) -> SceneText
  def normalized(prose: str, content_format) -> SceneText   # serialize(chapter_paragraphs(prose))
  def visible(paragraphs) -> list[list[tuple[str, bool, bool]]]
  def roundtrip_ok(prose: str, content_format) -> bool      # visible(chapter_paragraphs(prose)) == visible(chapter_paragraphs(normalized(prose).text))
  ```

- [ ] **Step 1: Write the failing tests.**
  - `test_markdown_canonical`: `normalized('_так_ і __це__', 'markdown').text == '*так* і **це**'`.
  - `test_blank_lines_are_empty_paragraphs`: `normalized('а\n\nб', 'markdown').text == 'а\n\nб'`; `serialize([[Run('а')],[],[Run('б')]],'markdown').text == 'а\n\nб'`.
  - `test_escaping_and_offsets`: `serialize([[Run('a*b')]],'markdown')` дає `text == 'a\\*b'` і `position(0,2) == 3`.
  - `test_plain_keeps_lines`: 44 рядки plain дають 44 рядки, `roundtrip_ok` True. Курсив у `Run` для plain не дає розмітки.
  - `test_roundtrip_idempotent`: для кожного фрагмента зі списку (курсив усередині слова, жирний курсив, `\*`, рядок `# ` на початку, `<`, `[x]`) виконується `normalized(normalized(p).text).text == normalized(p).text`. `roundtrip_ok` дає True або False, без винятку.
- [ ] **Step 2: Run** `pytest tests/authoring/test_docx_text.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Рядок `#`, `-`, `+`, `=`, `N.` на початку абзацу екранується, як у `escape_plain_markdown` (`markdown_document.py:183`): інакше кругообіг ламає абзац у заголовок чи список.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(import): серіалізація й нормалізація тексту сцени`.

### Task 3: Розпізнавання сцен

**Files:**
- Create: `src/storygen/application/editor_import_match.py`
- Test: `tests/publication/test_editor_import_match.py`

**Interfaces:**
- Consumes: `DocxManuscript` з Task 1.
- Produces:
  ```python
  @dataclass(frozen=True)
  class Fragment:
      scene_id: str | None; heading: str; first: int; last: int   # абзаци тексту сцени [first, last)
      how: Literal['bookmark','title','position'] | None
  def match_scenes(doc: DocxManuscript, order: Sequence[tuple[str, str]]) -> tuple[list[Fragment], list[str]]
      # order — (scene_id, title) у порядку маніфесту, а без маніфесту — у порядку плану;
      # повертає фрагменти в порядку документа й попередження
  ```

- [ ] **Step 1: Write the failing tests** (документ будується з `DocxParagraph` напряму):
  - `test_bookmarks`: три `Heading2` з `_osA`, `_osB`, `_osC` розпізнаються з `how='bookmark'`. Межі тексту сцени закінчуються на наступному `Heading1` або `Heading2`.
  - `test_title_fallback`: без закладок назви збігаються з `order`, `how='title'`.
  - `test_position_fallback`: `_osA`, далі заголовок «Зовсім нова назва» без закладки, далі `_osC`. Порядок `[A,B,C]` дає B з `how='position'` і попередженням «назву змінено редактором».
  - `test_position_ambiguous`: два нерозпізнані заголовки між A і D при двох пропущених сценах → обидва `scene_id=None`.
  - `test_duplicate_bookmark_or_unknown_id`: дубль `_osA` або `_osZ` (немає в `order`) дає нерозпізнаний фрагмент.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** за §3.4 спеки: закладки, потім точна назва з тим самим порядком серед розпізнаних, потім місце (рівно одна пропущена сцена між сусідами або на краю).
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(import): розпізнавання сцен за закладками, назвою й місцем`.

### Task 4: Зведення імпорту

**Files:**
- Create: `src/storygen/application/editor_import.py`
- Modify: `src/storygen/storage/repository.py:599` — `'editor_import'` у `ATTEMPT_CONTEXT_KEYS`
- Test: `tests/publication/test_editor_import.py`

**Interfaces:**
- Consumes: Task 1–3; `export_download`-подібне читання маніфесту (власна функція `load_manifest(repo, story_id, export_id) -> dict | None`, бо `export_download` читає ще й вихідний файл, якого не треба: перевірити `schema_version==2`, `story_id`, `export_id`; пошкоджений маніфест → `None` з попередженням); `build_rewrite_diff`; `repo.list_attempts(..., context_key='editor_import')`.
- Produces:
  ```python
  class ScenePreview(DomainModel):
      scene_id: str; title: str; status: str; needs_choice: bool = False
      edits: int = 0; comments: int = 0; general_comments: int = 0; dropped_comments: int = 0
      replace_status: str | None = None   # що станеться при changed_scenes='replace'
      warnings: list[str] = []
  class ImportPreview(DomainModel):
      import_id: str; export_id: str | None; fingerprint: str; choice_required: bool
      scenes: list[ScenePreview]; unmatched: list[str]; warnings: list[str]
  def preview_import(repo, story_id: str, content: bytes, *, now: datetime | None = None) -> ImportPreview
  def plan_scene(repo, story_id, scene, fragment, doc, manifest_entry, *, base: Literal['export','current']) -> ScenePlan
      # ScenePlan: status, normalized: SceneText, editor_text: str, proposal: RewriteDiff | None,
      #            general: str, comments: list[InputComment], dropped: int, warnings
  def sweep_temp(repo, *, now: datetime | None = None) -> int
  ```

- [ ] **Step 1: Write the failing tests** (книга через `seeded(tmp_path, count=3)` → `export_story(...,'docx')`, файл правлять через `_rewrite`):
  - `test_unchanged_file`: усі сцени мають `unchanged`, `choice_required` False. Файл лежить у `<data_dir>/editor-import/{import_id}.docx`.
  - `test_changed_scene_counts_edits`: заміна слова в другій сцені через `w:del`/`w:ins` дає `changed`, `edits == 1`.
  - `test_plain_edit_without_tracking`: те саме прямою заміною тексту дає `changed`.
  - `test_comments_only`: лише примітка дає `comments_only`, `comments == 1`.
  - `test_changed_since_export`: після експорту `save_manual_prose` змінює сцену → `changed_since_export`, `needs_choice`, `choice_required`, `replace_status=='changed'`.
  - `test_unknown_base`: маніфест видалено. Сцена з виправленнями Word і оригінальним поглядом == normalized дає `changed`. Пряма правка дає `unknown_base` з `needs_choice`.
  - `test_over_limit`: заміна, що дає понад 400 правок (кожне друге слово в сцені з 900 слів), → `over_limit`.
  - `test_no_prose_and_unsupported_markup`: сцена без прози дає `no_prose`. Для `unsupported_markup` `roundtrip_ok` підмінено monkeypatch'ем на False.
  - `test_pending_review`: синтетична спроба `editor_import` у `needs_review` для сцени дає `pending_review`.
  - `test_overlapping_comments`: дві примітки на ту саму фразу дають `comments == 1` і `general_comments == 1`. Вкладена примітка теж стає загальною. `validate_comment_set` на `normalized` проходить.
  - `test_comment_on_inserted_text_is_general`: примітка до `w:ins` стає загальною з цитатою з варіанта редактора і позначкою «вставлено редактором».
  - `test_comment_limits`: 105 приміток дають `comments+general_comments <= 100` і `dropped_comments == 5`.
  - `test_foreign_story_rejected`: інший `ObscuraStoryId` дає `ValueError('Файл з іншого твору')`.
  - `test_draft_comments_warning`: якщо в чинної чернетки є коментарі, сцена отримує попередження з їхньою кількістю.
  - `test_sweep`: файл, старший за 24 год (`now` зсунуто), видаляється, свіжий лишається.
  - `test_fingerprint_changes_with_prose_head`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** Статуси й `replace_status` — за §4 спеки.
  - Сцена `over_limit`: `proposal=None`, а `general` збирає всі примітки.
  - Фрагментні коментарі: примітка цілком в одному абзаці, без `w:ins`/`w:del` у діапазоні. Позиції рахуються через `normalized.position(p, offset)`, тоді `source_quote == display_quote`-перевірка відповідає `validate_comment_set` (для markdown `display_quote` = `source_range_text(...)`).
  - Перетини розводяться за порядком початку.
  - Тимчасовий файл пишеться через `repo.files.write('editor-import/…')`.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(import): зведення імпорту редакції`.

### Task 5: Збереження імпорту

**Files:**
- Modify: `src/storygen/domain.py` — `EditorImportOrigin` і `VersionRef.editor_import` (за зразком `ExternalOrigin`, `domain.py:169`).
- Modify: `src/storygen/storage/comment_store.py:93` — `save_draft_with_comments(..., editor_import=None, attempt_factory=None)`.
  - `attempt_factory(draft_ref: VersionRef, scene) -> StageAttempt | None` викликається всередині тієї самої транзакції після вставки чернетки.
  - Спроба вставляється тим самим з'єднанням.
  - Якщо `Repository.save_attempt` відкриває власну транзакцію, винести його INSERT у функцію `insert_attempt(conn, attempt)` і викликати з обох місць.
  - Якщо текст чернетки не змінився, нова версія не створюється, а `attempt_factory` отримує чинну голову.
- Modify: `src/storygen/storage/repository.py:22` — обгортка передає нові параметри.
- Modify: `src/storygen/application/editor_import.py` — `apply_import`, `cancel_import`.
- Test: `tests/publication/test_editor_import.py` (ті самі фікстури).

**Interfaces:**
- Consumes: `plan_scene`, `preview_import`, `load_manifest` з Task 4; `make_context` (`generation/context.py:130`); `chat_role_settings(repo, story_id, 'edit')` (`application/chat_stages.py:12`); `select_copyedits` (`generation/copyedit_review.py:44`).
- Produces:
  ```python
  class ImportResult(DomainModel):
      imported: list[str]; draft_only: list[str]; skipped: list[dict]   # {scene_id, status}
      warnings: list[str]
  def apply_import(repo, story_id: str, import_id: str, fingerprint: str,
                   changed_scenes: Literal['skip','replace'] | None) -> ImportResult
      # RevisionConflict('Твір змінився після зведення; перегляньте його ще раз') при іншому fingerprint
      # ValueError, якщо choice_required і changed_scenes is None; KeyError, якщо файла імпорту немає
  def cancel_import(repo, story_id: str, import_id: str) -> None
  ```

- [ ] **Step 1: Write the failing test first** — `test_imported_proposal_is_selectable`:
  1. Змінена сцена.
  2. `apply_import`.
  3. Спроба з `context['editor_import']`, `run_id is None`, `state=='needs_review'`.
  4. `copyedit_preview` і `select_copyedits` з усіма індексами проходять.
  5. Голова прози має текст редактора, спроба `completed`.

  Якщо `compare_snapshot` відмовляє, контекст спроби будується так, як `build_context` для `edit` у diff-режимі (`context.py:457-463`). Перевірку не послаблювати; якщо інакше не виходить — STOP і питання власнику (спека §5).
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement `apply_import`.**
  - Файл читається заново, зведення перебудовується, `fingerprint` звіряється.
  - Для кожної сцени, яку записуємо, — `save_draft_with_comments(text=normalized.text або editor_text для over_limit, content_format=проза, expected_revision=scene.revision, expected_comments_revision=чинна ревізія коментарів, payload={general, comments}, expected_source_version_id=heads['draft'], editor_import=EditorImportOrigin(...), attempt_factory=...)`.
  - Для `changed` `attempt_factory` будує спробу:
    - `make_context(repo, story, scene, 'edit', chat_role_settings(...), [draft_text], [draft_id], {'copyedit_draft_id': draft_id})`;
    - `partial_path=f'stories/{story_id}/runs/{id}/partial.txt'` з текстом редактора;
    - `editor_warnings=rewrite_warnings(...)`.
  - Для `comments_only` і `over_limit` фабрика повертає `None`.
  - При `replace` статус сцени з `needs_choice` переобчислюється з `base='current'`.
  - Після запису тимчасовий файл видаляється.
- [ ] **Step 4: Add the remaining tests, run, make them pass:**
  - `test_comments_only_saves_draft_and_comments_without_attempt`.
  - `test_over_limit_saves_editor_text_as_draft`: голова чернетки — текст редактора, коментарі лише `general`, спроби немає, сцена в `draft_only`.
  - `test_fingerprint_conflict`: зміна прози між зведенням і збереженням дає `RevisionConflict`, нічого не записано.
  - `test_choice_required`: без `changed_scenes` → `ValueError`. З `skip` сцена в `skipped`. З `replace` сцена імпортується, а `proposal` порівнює з поточною прозою.
  - `test_second_import_is_pending_review`: повторне зведення того самого файла дає `pending_review`.
  - `test_draft_version_marked`: `VersionRef.editor_import.import_id == import_id`, sha256 версії не залежить від поля.
  - `test_cancel_removes_temp`.

  Run: `pytest tests/publication/test_editor_import.py tests/generation/test_copyedit_review.py tests/storage -q`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(import): збереження чернетки, пропозиції й коментарів`.

### Task 6: API, прибирання при старті, SPEC

**Files:**
- Create: `src/storygen/web/routes_editor_import.py`; include у `web/app.py:137-185`
- Modify: `src/storygen/web/app.py:27-33` — `sweep_temp(app.state.repo)` у `lifespan` до `coordinator.start()`, помилка прибирання лише журналюється
- Modify: `SPEC.MD` — новий `Requirement: EDITOR-IMPORT` поруч з EDIT-REVIEW і посилання в змісті; доповнити EDIT-REVIEW рядком про синтетичну спробу без `run_id`
- Modify: `docs/verification/traceability.json`
- Test: `tests/web/test_editor_import_api.py`

**Interfaces:**
- Consumes: `preview_import`, `apply_import`, `cancel_import`.
- Produces:
  - `POST /api/stories/{story_id}/editor-import/preview`:
    - тіло — multipart, рівно один файл `file`;
    - понад `MAX_FILE` → 413;
    - відповідь — `ImportPreview`.
  - `POST /api/stories/{story_id}/editor-import/{import_id}`:
    - тіло — JSON `{fingerprint: str, changed_scenes: 'skip'|'replace'|null}`;
    - відповідь — `ImportResult`;
    - 409 через глобальне відображення `RevisionConflict`.
  - `DELETE /api/stories/{story_id}/editor-import/{import_id}` → 204.
  - `import_id` перевіряється на `[0-9a-f]{32}`.

- [ ] **Step 1: Write the failing tests** (TestClient за зразком `tests/authoring/test_docx_exports.py:211-225`):
  - `test_preview_and_apply_roundtrip`;
  - `test_preview_too_large_413`;
  - `test_two_files_400`;
  - `test_apply_conflict_409`;
  - `test_bad_import_id_404`;
  - `test_startup_sweeps_old_temp`: старий файл у `editor-import/` зникає після входу в `with TestClient(...)`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement routes.** Multipart обмежується, як у `routes_publication.py:105-130` (`MultiPartParser` з `max_files=1, max_fields=0`, читання `MAX_FILE+1`).
- [ ] **Step 4: SPEC.MD.**
  - `Requirement: EDITOR-IMPORT` з технічним описом за спекою §3–§5, інваріантами (проза не змінюється без вибору автора; модель не викликається) і відомими обмеженнями (§3.2 втрати, без UI до PR 2).
  - Сценарії `EDITOR-IMPORT-S01…S10`:
    - S01 читач і відмови;
    - S02 нормалізація-кругообіг;
    - S03 розпізнавання, зокрема за місцем;
    - S04 статуси зведення;
    - S05 вибір автора skip/replace;
    - S06 запис і прийняття через EDIT-REVIEW;
    - S07 `comments_only`;
    - S08 `over_limit` як чернетка;
    - S09 коментарі (перетин, вставлений текст, межі);
    - S10 тимчасове сховище, fingerprint, прибирання.
  - Для кожного сценарію запис у traceability з конкретними тестами Task 1–6.
  - Додатково ручна процедура до S03: «файл, правлений у Word з режимом виправлень і без нього (повна заміна назви сцени)», причина — поведінку Word автотест не відтворює.
- [ ] **Step 5: Run:**
  - `PYTHONUTF8=1 .venv/Scripts/python scripts/check_docs.py`
  - `PYTHONUTF8=1 .venv/Scripts/python -m pytest -q`

  Expected: обидва без помилок.
- [ ] **Step 6: Commit** `feat(import): API імпорту редакції, SPEC EDITOR-IMPORT`. У повідомленні: користувацька документація й сайт — у PR 2 разом з інтерфейсом, бо в PR 1 немає видимої автору зміни.
