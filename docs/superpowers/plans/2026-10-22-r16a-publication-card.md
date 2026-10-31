# R-16a — Картка публікації: план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Виконання в поточній гілці й чаті, без нового погодження за прямим рішенням власника.

**Goal:** Картка всіх метаданих, спільні публічні підписи, безпечна обкладинка й узгоджений snapshot.

**Architecture:** data-only publication_models; storage/publication_store через Repository; локальний publication/covers; HTTP та окрема форма в чинному стилі settings. Міграція 003. Без нових рендерерів або модельних викликів.

**Tech Stack:** Python3.10/Pydantic/SQLite/FastAPI/ES modules; Pillow як optional publication extra.

**Spec:** docs/specs/changes/R-16-publication-formats.md, частина R-16a.

## Global Constraints

- Одразу весь погоджений набір полів; defaults без backfill, old payload незмінні.
- CAS окремо картки й підписів; metadata не інвалідовує прозу.
- PNG/JPEG <=10MiB, <=20MP, без EXIF/GPS, без довіри до клієнтського шляху; hashes/owner.
- fsck/backup схем2/3, невідома схема відхиляється; незмінні старі exports.
- «Запропонувати» й нові формати — наступні частини, не показувати робочу кнопку до реалізації.

## Review Focus

- Старий readonly schema2 backup не мігрується fsck; перевірити справжній fixture2.
- CAS підпису після завантаження картки та чужий cover id; перевірити транзакційно без часткового запису.
- Помилка upload/збереження не втрачає dirty форму, дві вкладки дають 409.
- Знімок фіксує підписи, metadata, порядок і prose refs однією read transaction; тест зміни після snapshot.
- Pillow optional: без пакета MD/TXT/server/fsck без cover продовжують працювати, помилка cover зрозуміла.

## Task 1: дані та збереження

- [x] RED tests/storage/test_publication.py: defaults/schema2 migration, field limits/ISBN, CAS, archive/restore/signature links, metadata without prose invalidation, foreign cover, coherent snapshot.
- [x] models + 003 migration + Repository.publication(action, **data), publication_snapshot(story_id); typed PublicationView/PublicationSnapshot.
- [x] GREEN цільових тестів.

## Task 2: обкладинка й integrity

- [x] RED tests/storage/test_publication.py: upload normalization/EXIF, invalid/oversize/multi-frame, hash/owner/corruption; tests/storage/test_publication_backup.py: schema2/3 cold backup/restore.
- [x] Pillow lazy decoder, immutable assets, register/assign CAS у різних явних операціях; publication checks у fsck; schema2/3 readonly support.
- [x] GREEN storage/backup/integrity + старі export тести.

## Task 3: HTTP та форма

- [x] RED tests/web/test_publication_api.py: CRUD, CAS/404, archived story/foreign asset, multipart bounds, page/all fields. JS dirty/async merge/CAS test.
- [x] publication routes, form у стилі settings, лінк із workbench; вибір/порядок підписів і перекладачів, редагування/архівація довідника, всі додаткові поля, cover preview/replace/remove. Не додавати нову бренд-палітру.
- [x] GREEN HTTP/JS; браузер desktop/mobile на синтетичному творі без робочого сервера.

## Task 4: приймання

- [x] SPEC.MD: тільки реалізована R-16a, нові Scenario і traceability; docs publication-card.md, backlog/progress.
- [x] Detector один раз, незалежне рев’ю всього пакета; важливі findings виправити RED→GREEN.
- [x] Повний scripts/verify.py, scripts/check_docs.py, diff --check; результати/обмеження в журналі.
- [x] Один локальний коміт R-16a, без push; далі R-16b.

## Журнал

22.10.2026: база6bb9ec7; робоче дерево чисте. Ruling: окрема сторінка картки повторює наявне компонування settings, нова візуальна система не створюється. Підписи live для наступного export; snapshots фіксують значення. Обкладинка спочатку реєструється, потім призначається при Save картки — dirty форма зберігається при upload. Структура інтерфейсів storage→models, routes→Repository узгоджена; generation не залучається.

22.10.2026: data/storage/cover/API/UI реалізовані. RED: відсутній publication_models, HTTP404; GREEN: storage/legacy/export64+1skip, HTTP/backup5, JS+storage22. Окремий RED→GREEN захист вводу під час завантаження. Повний перший прогін: 824 passed/1 failed/1 skipped, verification-rx5s15o9: старий trash migration assertion очікував2, тепер3. Додано й виправлено RED→GREEN legacy story_id=old, 34 storage/trash пройшли.

Незалежне source-review без важливих findings; reviewer не заявляє web test pass через sandbox TestClient hang. Наші HTTP виконані escalated. Браузер синтетичний: назва/анотація/псевдонім Save+reload; desktop і viewport390px в iframe, знімки artifacts/r16a-desktop.png і r16a-mobile.png. Не є перевіркою фізичного мобільного пристрою. Тестові сервери8884/8885 і вкладки закриті; робочий сервер/дані не змінені. Detector23:18 font-size,2 radius,2 успадковані чорні кольори Jinja,1 hidden img без src до вибору cover; правила/ignore не змінені, новий доведений UI дефект не встановлено.

Фінальне приймання: 826 passed, 1 skipped, exit0; artifacts/verification-86bsirau/result.json, source_changed_during_run=false. Після прогону змінено лише записи приймання. scripts/check_docs.py та diff --check пройшли. Пакет комітиться локально без push. Наступна частина — R-16b.

Фінальна перевірка пакування: resource-local .gitattributes задає *.xsd -text, щоб Windows checkout не змінював pinned SHA-256. Усі4 хеші та git check-attr перевірені; це зміна пакування після suite, Python/JS/SQL код після suite незмінний.
