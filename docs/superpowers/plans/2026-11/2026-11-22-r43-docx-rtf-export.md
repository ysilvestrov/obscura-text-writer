# R-43 — Експорт DOCX і RTF: план реалізації

> **Для агентів:** обов'язковий підскіл — superpowers:subagent-driven-development або superpowers:executing-plans. Кроки позначено `- [ ]`.

**Мета:** два нові формати експорту книги — рукописний DOCX з мітками сцен для імпорту R-46 і RTF.

**Архітектура:** два нові рендерери поруч із FB2/EPUB/PDF у `src/storygen/publication/`, що отримують уже захоплений `Book` і повертають байти; `application/exports.py` вибирає рендерер, пише маніфест; маршрут, MCP і діалог лише доповнюють переліки форматів.

**Технології:** Python, `zipfile`, `xml.sax.saxutils.escape`; без нових залежностей.

**Специфікація:** `docs/superpowers/specs/2026-11/2026-11-22-docx-rtf-export-design.md` (затверджено 22.11.2026). Виконавець читає її розділ «Технічний опис» — там значення стилів, сторінки, імен закладок і властивостей.

## Глобальні обмеження

- Без нових залежностей (`pyproject.toml` не змінюється).
- Закладка сцени: ім'я `_os` + `scene_id` (32 hex), послідовні `w:id` від 1.
- Властивості `custom.xml`: `ObscuraStoryId`, `ObscuraExportId`, `ObscuraManuscript`=`1`.
- Сторінка A4: `pgSz` 11906×16838, `pgMar` 1417; Times New Roman, `sz` 24; `line` 360 auto; `firstLine` 709.
- Сцена — `Heading2`, частина — `Heading1`, обидві з `pageBreakBefore`; назва книги — `Title`.
- Недопустимий для XML 1.0 символ у тексті → `ValueError` з тим самим текстом, що `book.xml_bytes` («Текст містить недопустимий символ XML 1.0; його не вилучено автоматично»), для DOCX і RTF.
- Маніфест: `validation` — `'docx':'OOXML structure + scene bookmarks'`, `'rtf':'RTF 1.9 text'`; `format_details` = `{'profile':PROFILE}`.
- Версія плагіна не піднімається: за SPEC вона дорівнює версії проєкту.
- Gate: `python scripts/check_docs.py && python -m pytest -q` (venv основної теки, `PYTHONIOENCODING=utf-8`); pytest `--basetemp` у `C:\tmp\<name>`.

## Фокус рев'ю

1. Проза з `\t`, `\r\n`, порожніми рядками на початку/в кінці сцени → `w:tab`, `w:br`, порожні абзаци як у PDF, хвостові відкинуто. Тест у задачі 1.
2. Назва сцени чи книги з `<&>"` і кирилицею → коректний XML, текст без змін. Тест у задачі 1.
3. Структурована книга, де частина не має назви → заголовок «Частина N» / «Part N» з `part_starts`. Тест у задачі 1.
4. Книга без сцен або сцена без прози з `allow_incomplete` → валідний DOCX (титул, заголовок сцени й закладка без тексту), без службових слів. Тест у задачі 1.
5. RTF з `\`, `{`, `}` і емодзі в тексті → екрановано, емодзі — сурогатна пара. Тест у задачі 2.

---

### Задача 1: `Chapter.language` і DOCX-рендерер з перевіркою

**Files:**
- Modify: `src/storygen/publication/book.py` (`Chapter`, `capture`)
- Create: `src/storygen/publication/docx.py`
- Test: `tests/authoring/test_docx_exports.py`

**Interfaces:**
- Produces: `Chapter.language: str = 'uk'` (ефективна мова прози сцени, `language.prose_language(snapshot.story, scene)`); `docx.PROFILE: dict`; `docx.render(book) -> bytes` (викликає `validate` перед поверненням); `docx.validate(content: bytes, book) -> None` (`ValueError` при порушенні).

- [ ] **Крок 1: тести** (фікстура за зразком `seeded` з `tests/authoring/test_ebook_exports.py`; рендер через `capture(repo, story.id, 'docx', allow_incomplete)` + `docx.render`, бо `export_story` ще не знає формату):
  - `test_docx_parts_and_styles` — zip містить 8 частин зі специфікації; `document.xml` має `Title` з назвою, `Heading2` на кожну сцену в порядку книги; `styles.xml` — `Heading1`/`Heading2` з `pageBreakBefore`, `pgSz w:w="11906"`.
  - `test_docx_scene_bookmarks_and_custom_properties` — імена закладок `== ['_os'+id for id in scene_ids]`; `custom.xml` має story id, export id, `ObscuraManuscript`=`1`.
  - `test_docx_trash_scene_absent` — сцена в кошику відсутня в тексті й закладках.
  - `test_docx_markdown_runs_and_controls` — Markdown `*курсив* **жирний**` → `w:i`/`w:b`; plain `ліва\tправа\nрядок` → `w:tab`, `w:br`; `<&>"` у назві та прозі розбираються як текст.
  - `test_docx_language_document_and_scene` — `card.language='en'`, сцена з `prose_language=None` у творі `uk` → фрагменти сцени з `w:lang w:val="uk-UA"`; `docDefaults` — `en`.
  - `test_docx_untitled_part_and_title_page` — структурована книга з частиною без назви → `Heading1` «Частина 1»; титул містить «Слів: N» з сумою `word_count` маніфесту.
  - `test_docx_incomplete_without_service_words` — сцена без прози з `allow_incomplete=True` → закладка є, у `document.xml` немає «застар», «перегляд», «Немає завершеної».
  - `test_docx_invalid_xml_character_raises` — проза з `\x01` → `ValueError` з текстом глобального обмеження.
  - `test_docx_validate_rejects_foreign_ids` — `validate(content, other_book)` з іншим export id або іншим порядком сцен → `ValueError`.
- [ ] **Крок 2:** запустити `pytest tests/authoring/test_docx_exports.py -q` — FAIL (модуля немає).
- [ ] **Крок 3:** `Chapter.language` + заповнення в `capture`; `docx.py` за специфікацією (абзаци з `markup.chapter_paragraphs`, частини з `part_starts`, мова документа — `card.language`, сцени з основним підтегом, відмінним від підтегу картки, — `w:lang` `uk-UA`/`en-US` у `rPr` фрагментів).
- [ ] **Крок 4:** тести задачі й `tests/authoring` — PASS (наявні тести PDF/EPUB не змінюються).
- [ ] **Крок 5:** коміт `feat(export): DOCX-рукопис з мітками сцен (R-43)`.

### Задача 2: RTF-рендерер

**Files:**
- Create: `src/storygen/publication/rtf.py`
- Test: `tests/authoring/test_rtf_exports.py`

**Interfaces:**
- Consumes: `Book`, `Chapter.language`, `markup.chapter_paragraphs`, `part_starts` (задача 1).
- Produces: `rtf.PROFILE: dict` (те саме оформлення, що `docx.PROFILE`; можна імпортувати звідти); `rtf.render(book) -> bytes` (ASCII).

- [ ] **Крок 1: тести:**
  - `test_rtf_header_and_page` — починається з `{\rtf1\ansi`, має `\paperw11906`, `\margl1417`, `\fs24`, таблицю стилів `heading 1`/`heading 2`, `{\footer`, `\chpgn`; байти декодуються як ASCII.
  - `test_rtf_escaping` — текст `a\b{c}` → `a\\b\{c\}`; «Ї» → `\u1031?`; «😀» → `\u-10179?\u-8704?`.
  - `test_rtf_runs_and_scene_order` — `{\i …}`, `{\b …}`, `\line` для `\n`, `\tab` для `\t`; заголовки сцен у порядку книги з `\pagebb`; сцени з кошика немає.
  - `test_rtf_language` — картка `uk-UA` → `\deflang1058`; картка `fr` → без `\deflang`; сцена `en` у книзі `uk` → `\lang1033` в її абзацах.
  - `test_rtf_invalid_xml_character_raises` — `\x01` → `ValueError` з тим самим текстом.
- [ ] **Крок 2:** FAIL.
- [ ] **Крок 3:** `rtf.py` за специфікацією; `\uc1`; знакове 16-бітне N; сурогатні пари для символів поза BMP.
- [ ] **Крок 4:** PASS.
- [ ] **Крок 5:** коміт `feat(export): RTF-рукопис (R-43)`.

### Задача 3: підключення форматів

**Files:**
- Modify: `src/storygen/application/exports.py` (`FORMATS`, `Literal`, вибір рендерера, `validation`, `format_details`, регулярний вираз `export_download`)
- Modify: `src/storygen/web/routes_exports.py` (`ExportRequest.format`, MIME)
- Modify: `src/storygen/mcp/bridge.py` (`EXPORT_FORMATS`, опис `export_book`)
- Modify: `src/storygen/web/templates/story.html` (опції `docx`, `rtf` після `pdf`), `src/storygen/web/static/i18n.json` (`export.docx_option`: «Рукопис Word (.docx)» / «Word manuscript (.docx)»; `export.rtf_option`: «Рукопис RTF (.rtf)» / «RTF manuscript (.rtf)»)
- Test: `tests/authoring/test_docx_exports.py`, `tests/authoring/test_export_filename.py`, тест MCP формату поруч із наявним тестом `export_book`, тест шаблону поруч із наявним тестом опцій експорту

**Interfaces:**
- Consumes: `docx.render`, `docx.PROFILE`, `rtf.render`, `rtf.PROFILE`.
- Produces: `export_story(repo, story_id, 'docx'|'rtf', allow_incomplete)`; маршрут `GET /api/stories/{id}/exports/<id>.docx|.rtf`.

- [ ] **Крок 1: тести:**
  - `test_export_story_docx_and_rtf_manifest` — `export_story` для обох форматів пише файл і маніфест з `format`, `validation`, `format_details.profile`, `output_sha256` = SHA файлу.
  - `test_download_docx_rtf_mime_and_name` — TestClient: MIME `application/vnd.openxmlformats-officedocument.wordprocessingml.document` і `application/rtf`; `Content-Disposition` з `filename="<id>.docx"` і `filename*` з читабельним іменем `.docx`.
  - MCP: `EXPORT_FORMATS` містить `docx`, `rtf`; `export_book(format='docx')` повертає посилання.
  - Шаблон: `#export-format` має опції `docx`, `rtf`; i18n має обидва ключі в uk і en.
- [ ] **Крок 2:** FAIL.
- [ ] **Крок 3:** доповнити переліки й вибір рендерера; повідомлення про недоступний формат — «Доступні MD, TXT, FB2, EPUB, PDF, DOCX і RTF».
- [ ] **Крок 4:** `pytest -q tests/authoring tests/mcp tests/web` — PASS.
- [ ] **Крок 5:** коміт `feat(export): DOCX і RTF у діалозі, маршруті й MCP (R-43)`.

### Задача 4: SPEC, traceability, сайт, скіл

**Files:**
- Modify: `SPEC.MD` (EXPORT-001 — перелік форматів; EXPORT-CLEAN — DOCX/RTF і уточнення про мітки імпорту, S01 доповнено; нова вимога `EXPORT-DOCX` з `EXPORT-DOCX-S01…S05` і якорями `<a id>`; зміст на початку файлу)
- Modify: `docs/verification/traceability.json` (S01–S04 → тести задач 1–3; S05 → `manual.procedure` `docs/verification/manual.md#docx-word`, причина «Word недоступний у CI»)
- Modify: `docs/verification/manual.md` (розділ `docx-word`: процедура з «Проби Word» специфікації)
- Modify: `docs/site/{uk,en}/publication.md` і пари `mcp`, `index`, `first-story`, `book-structure`, `content-rating`, `series`, де перелічено формати; `README.md`, `PRODUCT.md`, `integrations/claude/obscura/skills/publish/SKILL.md`

- [ ] **Крок 1:** внести зміни; формулювання вимоги — зі специфікації («Технічний опис»), українською, маркери OpenSpec англійською.
- [ ] **Крок 2:** `python scripts/check_site.py --rehash <slug>` для кожної зміненої пари.
- [ ] **Крок 3:** `python scripts/check_docs.py` — «…узгоджені».
- [ ] **Крок 4:** коміт `docs(export): DOCX і RTF у SPEC, traceability, сайті й скілі (R-43)`.

### Завершення (поза задачами)

- Gate з глобальних обмежень; `python scripts/verify.py` і запис у `docs/STATUS.md`.
- Ручна процедура `docx-word` на експорті тестової книги у Word (як у пробі).
- Cross-review гілки, PR на `main` з `Closes #268`, оновлення основної теки.
