# R-16d — PDF A5 та спільне приймання

Base306720a. Реалізація в поточній гілці за погодженою R-16 специфікацією, без нового підтвердження. Root SPEC R16-EBOOK/EXPORT-001 — спільний snapshot/manifest/download, PDF ще відсутній.

1. RED→GREEN: тести PDF A5/український extractable text/embedded Noto/cover/title/TOC/page numbers/неповнота/unsupported glyph/довгі слова й заголовки/7 сцен >15k. `publication/pdf.py` lazy ReportLab Platypus, bundled4 static Noto TTF+OFL+commit/hash manifest, local font lock. Перевіряти metadata і prose glyphs до верстки, не змінювати Unicode/тире. Register fonts під process lock; рендер працює тільки з captured Book.
2. Інтеграція facade/manifest/API/MIME/одна форма; optional publication ReportLab4.x, dev pypdf. PDF має окремий format/font/library descriptor у manifest. Чинні guards/bytes-first/download не послаблюються. SPEC/traceability/інструкція.
3. Синтетичні acceptance fixtures: minimal/full/incomplete/long headings, 7 сцен >15k, image/text bounds і візуальний огляд rendered pages через локальний PDF renderer; regression FB2/EPUB/MD/TXT. Читачі FB2/EPUB: використати доступний локальний інструмент або явно зафіксувати невиконану зовнішню reader-перевірку, не підміняти її валідатором. Independent final review, full verify/check_docs/diff, локальний commit без push.

Ruling: стилі PDF задані R-16, нових продуктових опцій немає. Plain text фізичний рядок→абзац як R16c; пусті рядки→вертикальний пропуск, не форматування markup. Cover вписується у printable area без crop на білому. Немає штучних парних сторінок. Надмірні назви можуть займати кілька сторінок; keepWithNext лише для заголовка розділу нормального розміру. Не використовувати користувацький текст як ReportLab XML.

- [x] Renderer/fonts + RED→GREEN
- [x] Integration/spec
- [x] Acceptance/review; локальний коміт цього пакета

Фактичне приймання: scripts/verify.py -q →900 passed/1 skipped,0failed/errors, source_changed=false; artifacts/verification-or17aici/result.json. check_docs/diff --check/PIP check пройшли. Poppler/pdfplumber4PDF безboundsviolations, full15463words/59pages. MuPDF1.28.2 відкрив FB2/EPUB, сім сцен і literal text; screenshots у artifacts/r16d-reader. Edge desktop/mobile: artifacts/r16d-ui/result.json,0JSerrors; власний тимчасовий сервер зупинено. Wheel9945a3ae… зібраний у artifacts/r16d-wheel, усі6 font resources/хеші перевірено, fonts не системні. Independent review no blocking findings; maxPasses10 узгоджено. Impeccable advisory — статичний HTML без CSS; legacy PRODUCT schema запропоновано оновити окремим init, не включено до цього пакета. Після повного verify — лише записи приймання й уточнення PRODUCT про вже реалізований PDF, runtime/tests незмінні. Без push, моделей, реальних авторських даних. Далі R-18.
