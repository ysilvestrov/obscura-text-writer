# План реалізації: ядро доповнювального імпорту

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Реалізувати серверне ядро погодженого доповнювального імпорту й атомарне збереження обсягу твору.

**Architecture:** Чистий розбір секцій готує зміни без запису. Repository публікує один файл транзакційно: журнал, явний selector активного джерела, нові сцени/картки та їхні голови. HTTP-оркестрація повертає результат кожного файла. Інтерфейс і налаштування письма отримають окремий план після наскрізного рев’ю цього ядра.

**Tech Stack:** Python, Pydantic, SQLite, FastAPI, pytest; без нових залежностей.

**Spec:** docs/specs/changes/additive-imports-writing-target-2026-11-05.md — затверджено власником у цьому чаті.

## Global Constraints

- Дубль сцени — явний номер, незалежно від назви;02 і2 збігаються. Позиція не є номером. Без номера кожна секція нова.
- Дубль персонажа — чинний name_key; наявні IDs/entries/citations не перезаписуються.
- Нові сцени додаються наприкінці; попередні beats/heads/цілі зберігаються. Новий орієнтир при доповненні —1000; початковий імпорт розподіляє story.target_words.
- Сирі bytes незмінні. Активний план накопичує тільки прийняті нові секції; імпорт лише дублів не змінює selector та не інвалідує матеріали.
- Один файл публікується атомарно з CAS. Multipart проходить повну попередню валідацію; після runtime-помилки подальші файли не застосовуються.
- Обсяг твору — ціле число від5000 без верхньої межі15000; profile+target зберігаються атомарно. Немає модельних викликів.
- Архітектурні зміни відразу відбиваються в SPEC.MD та traceability. Документація українською; UI UA/EN готується в наступному плані.
- Сторонній docs/research/2026-11-01-local-planner-round-2-summary.md не змінювати й не включати до комітів.

## Review Focus

1. Старі імпорти з однаковим timestamp: зберегти саме попередній активний вибір, не переплутати порядок журналу з selector.
2. Збій після створення першої сцени: відкотити всі SQL-зміни файла, зберегти інший успішний файл; дозволені лише неопубліковані blobs.
3. Legacy fallback «Сцена 1» без авторського заголовка: не перетворювати автоматичну назву на номер1.
4. Ручна правка картки після часткового імпорту: prepare читає чинні картки, а не останній сирий файл.
5. Збереження лише обсягу: не створити style-версію та не змінити цілі сцен; CAS-конфлікт не публікує половину письмового профілю.

## Поділ роботи

Це поведінкова зміна з необхідними новими storage-операціями, не окремий косметичний рефакторинг. Не перебудовувати сторонні модулі в цьому PR. Якщо під час реалізації знадобиться винесення чинного коду без зміни поведінки, оформити його окремим PR із незмінними очікуваннями тестів перед поведінковою зміною.

Ядро — чотири задачі нижче, один окремий PR після попереднього PR#5. План інтерфейсу не пишеться наперед: він залежить від фактичних API та результату наскрізного рев’ю ядра. Інтерфейсний PR охопить поле «Письмо», журнал, результати імпорту, UA/EN та desktop/mobile. Публікація ядра має чітко пояснювати тимчасову відсутність нових UI-полів.

## Task 1: Секції плану та авторський номер

**Files:** новий `src/storygen/authoring/import_sections.py`; `src/storygen/scene_description.py`, `src/storygen/domain.py`, `src/storygen/storage/scene_metadata.py`, `src/storygen/storage/authoring.py`; новий `tests/authoring/test_import_sections.py`, тести ручного збереження плану в `tests/authoring/`.

**Interfaces:** `PlanSection(title: str, text: str, author_scene_number: int | None)`; `split_plan(text: str) -> tuple[str, list[PlanSection]]` повертає преамбулу й дослівні секції; `explicit_scene_number(text: str) -> int | None`. `Scene`/`SceneCreate` мають optional `author_scene_number`, default null; номер не виводиться з position. Legacy backfill належить Task2.

- [x] Написати параметризовані тести: однаковий номер із різними назвами/роздільниками;02/2; TXT і Markdown; змішаний `## Сцена 2`, `## Інтерлюдія`, `### Спогад` дає дві секції; CR/LF/CRLF секції зберігають текст; fallback без заголовків має номер null.
- [x] Виконати `.venv/Scripts/python.exe -X utf8 -m pytest tests/authoring/test_import_sections.py -q`; зафіксувати RED через відсутній модуль.
- [x] Реалізувати чистий розбір за правилами розділу5 специфікації. Рівень Markdown береться з нумерованих сцен, інакше з найменшого не-контейнерного заголовка. TXT-нумерована секція завжди є межею; глибший ненумерований заголовок залишається описом.
- [x] Додати тести manual save: зміна номера2→3 синхронізує поле, видалення заголовка очищає його; display rename/reorder не змінюють; зайнятий номер відхиляється атомарно. Реалізувати в чинному транзакційному шляху ручного збереження плану.
- [x] Запустити нові тести та `tests/authoring/test_imports.py`; оновити SPEC/traceability для номера й зафіксувати коміт.

## Task 2: Явні активні джерела та атомарна публікація файла

**Files:** нові `src/storygen/storage/migrations/005_import_sources.sql`, `src/storygen/storage/import_store.py`; `storage/database.py`, `storage/repository.py`, `storage/context_view.py`, `storage/integrity.py`, `storage/snapshots.py`; новий `tests/storage/test_import_publication.py`, чинні backup/restore тести.

**Interfaces:** `Repository.list_source_files(story_id) -> list[dict]` повертає журнал з name/kind/version_id/created_at. `Repository.publish_import(story_id, expected_revision, publication: ImportPublication) -> ImportPublicationResult`. Строгі `ImportPublication`/`ImportPublicationResult` у незалежному `src/storygen/import_models.py` містять metadata сирого файла, nullable active_plan_version_id, nullable character_cards_version_id, підготовлені нові scene payloads і plan refs; storage не імпортує generation або HTTP. `active_source` зберігає попередню сигнатуру.

- [x] Написати RED-тести: selector не залежить від останнього журналу; CAS не змінює журнал/голови; fault injection після першої сцени відкочує всю SQL-публікацію; повтор дублів з незміненими selectors не робить версії stale.
- [x] Міграція створює `active_sources(story_id, kind, version_id)` із ключем story_id/kind та власністю refs. Backfill копіює попередній вибір останнього source_files rowid для кожного типу; timestamp не підміняє цей порядок. Nullable номер старої сцени визначається за правилами специфікації; fallback/неоднозначні випадки лишаються null.
- [x] Реалізувати publish_import через один BEGIN IMMEDIATE, expected_revision і перевірку власності/complete/hash всіх підготовлених refs. Спочатку всі перевірки, потім публікація журналу, selectors, карток і сцен. Інвалідація — лише за зміною активного змісту/карток, не при додаванні запису журналу. Синхронізація cast у тій самій транзакції.
- [x] Repository і ContextView читають однаковий selector. У контекстному знімку додати journal metadata; похідні версії не входять до list_source_files. Перевірити залежності snapshots без зміни історичних refs.
- [x] Fsck перевіряє ownership/kind selectors і формат author_scene_number, дозволяє історичні snapshots. Backup/restore включає нову таблицю; читання старого backup у підтримуваному порядку міграцій не втрачає активного вибору.
- [x] Запустити `.venv/Scripts/python.exe -X utf8 -m pytest tests/storage/test_import_publication.py tests/storage -q`, оновити storage SPEC/traceability та зробити коміт.

## Task 3: Доповнювальний імпорт і HTTP-результат кожного файла

**Files:** `src/storygen/authoring/imports.py`, `src/storygen/import_models.py`, `src/storygen/characters/service.py`, `src/storygen/generation/pipeline.py`, `src/storygen/web/routes_stories.py`; `tests/authoring/test_imports.py`, `tests/authoring/test_character_import.py`, новий `tests/web/test_additive_imports.py`.

**Consumes:** split_plan/PlanSection з Task1; publish_import/list_source_files/active_source з Task2.

**Produces:** сумісний ImportResult із `created_scene_ids`, `skipped_character_names`, `skipped_scene_numbers`, `files`, `partial`; елемент files має client_index/name/kind/status/source_id/version_id/created_scene_ids/created_character_cards/skipped_character_names/skipped_scene_numbers/warnings/error. Статуси imported/failed/not_processed, IDs за відсутності null. Клієнтський індекс не береться з назви файла.

- [x] RED: повторний файл персонажів із новою карткою та дублем; збережені ручні entries/IDs/citations; нормалізовані імена; опублікований порожній набір; файл лише з дублями не створює character_cards версію.
- [x] RED: сцени за номером; дублі в одному файлі; одна назва з різними номерами; повтор ненумерованих секцій додає нові; збереження старих heads/вступу/обсягів; нова сцена наприкінці має1000. Повтор нумерованого файла не змінює active source й freshness.
- [x] Реалізувати підготовку на captured view: поточні картки плюс прийняті нові; поточний план плюс точні нові секції. Нові immutable blobs готуються до publish_import; input_refs містять їхні реальні джерела. Не використовувати послідовні незалежні repo.create_scene/register_source/save_character_material для однієї файлової публікації.
- [x] Prepare читає поточні картки з усіма entries/мітками та ref character_cards, сирий опис — лише legacy fallback. Тест ручної зміни після імпорту перевіряє, що старий сирий текст не підміняє чинне значення.
- [x] Додати HTTP-тести: весь multipart prevalidation до запису400/413; перший runtime CAS409 з files; успішний перший/невдалий другий/необроблений третій —200 partial=true з точними підсумками. Не відлунювати приватні bytes у помилках. Старі поля result зберегти; structured lists не залежать від мови warnings.
- [x] GET story додає `source_files` та `active_sources`, зберігаючи старе поле sources на час переходу UI. `source_files` містить реальні назви та created_at версій, newest-first зі стабільним ID tie-break; без похідних версій.
- [x] Запустити `.venv/Scripts/python.exe -X utf8 -m pytest tests/authoring tests/web/test_additive_imports.py tests/generation/test_character_context.py -q`; оновити DATA-001/CHARACTER-IMPORT у SPEC, traceability й коміт.

## Task 4: Атомарний серверний scope «Письмо» і наскрізне приймання ядра

**Files:** `src/storygen/web/routes_settings.py`, `src/storygen/authoring/blueprints.py`, `src/storygen/storage/authoring.py`, `src/storygen/storage/repository.py`; новий `tests/web/test_writing_target_settings.py`, новий `tests/integration/test_additive_import_flow.py`.

**Interfaces:** SettingsChange.target_words — optional int ge5000. `update_story_profile(repo, story_id, profile, expected_revision, target_words=None)` зберігає сумісність старих викликів. `Repository.publish_writing_settings(story_id, expected_revision, target_words, style_version_id)` атомарно оновлює змінені поля. Параметр target_words відхиляється для role/shared-provider; GET settings повертає story як раніше.

- [x] RED: story25000, незмінні цілі сцен; profile+target один CAS; stale revision не змінює жодного поля; запит без target залишає старий обсяг; target у role/shared-provider відхиляється.
- [x] Реалізувати валідований server save; якщо profile не змінився, не створювати зайвої style-версії. Тест чистої зміни target перевіряє сталий style_version_id і кількість style refs; активні generation attempts не змінюються.
- [x] Наскрізний тест: початковий план/персонажі → ручні зміни → частковий імпорт нових і дублів → prepare без gateway → snapshot → fsck → backup/restore → перевірка активного плану, цитат, карток і номерів. Окремо два captured views з одною revision: лише одна публікація проходить.
- [x] Внести лише реалізовані контракти в SPEC.MD/traceability, додати UA/EN API-примітки про ще не оновлений UI. Не оголошувати інтерфейс завершеним.
- [x] Виконати check_docs.py і scripts/verify.py з усіма новими та відповідними authoring/storage/settings/context tests; записати фактичний результат у docs/STATUS.md.
- [x] Виконати наскрізне рев’ю всього ядра, зафіксувати findings і усунути суттєві. Після цього скласти окремий план UI на основі реальних контрактів, а не цього попереднього переліку.
- [x] Перевірити сторонні зміни основної теки, коміт/push/PR; залишити C:\Projects\text-generator на перевіреному результаті. Не merge без окремого дозволу. Вказати PR/коміт/стан теки у підсумку.

## Самоперевірка плану

Розділи2–7 специфікації покрито ядром. Інтерфейсна частина розділів2–4 та UA/EN повідомлення/знімки навмисно винесені в наступний план після рев’ю ядра. Не вводиться нова продуктова семантика дублів. Найбільший ризик — атомарна публікація й відділення selectors від журналу; вони отримують окремі storage та інтеграційні перевірки перед UI.

## Статус

Ядро реалізовано inline за погодженням власника. Незалежне рев’ю gpt-6-astra завершено; findings щодо цитат, інвалідації, змішаних заголовків та преамбули відтворені RED і виправлені GREEN. Повний verify.py:1356 passed,1 skipped,0 failed/errors; source_changed_during_run=false,451.21s, artifacts/verification-1bwf62t1/result.json. [UI-план](2026-11-06-additive-imports-ui.md) підготовлено після рев’ю; UI ще не реалізовано.

Рішення: спільний parser перенесено в чистий plan_sections із сумісними authoring exports; storage не залежить від authoring. Нейтральна примітка fixture оформлена bold-текстом, щоб не стати ненумерованою сценою. Гілка залежить від відкритого PR#5, main не зливався. Завершальні зміни задач3/4 фіксуються одним інтеграційним комітом після повного gate, бо охоплюють спільні шляхи публікації. Користувацькі дані під час тестів не мігрувалися — лише тимчасові fixtures.


Початкова спроба додаткової зовнішньої detent cross-review, до окремої згоди власника, не запускалася: автоматична перевірка дозволів відхилила npx-виконання стороннього пакета через ризик невідомого коду й передачі вмісту репозиторію. Обхід не застосовувався. Звичайне незалежне рев’ю gpt-6-astra завершено; його findings виправлені й повний gate пройшов.


## Дозволений cross-review06.11.2026

Власник явно дозволив завантаження/виконання @ysilvestrov/detent і передачу коду/документації Anthropic через Claude, із резервним Google/agy, заборонивши секрети й приватні матеріали. Перевірено npm0.5.0, SHA-512 архіву збігся з dist.integrity. Виконано саме перевірений локальний пакет без install-скриптів і runtime dependencies. Claude2.1.317, restricted Read/Grep/Glob, strict MCP та CLAUDE_CODE_SAFE_MODE=1. Середовище очищене від key/token/secret/password/credential/proxy і provider overrides.

Рецензент отримав окремий Git-знімок:615 head-файлів коду, синтетичних тестів і технічних документів. Не включено.env/config, оригінальну.git, data/backups/artifacts/research, приватні матеріали, STATUS і журнал виконання. Перевірено склад і SHA-256 кожного файла; пошук типових credential literals не знайшов збігів. Маніфест у artifacts/detent-review/materials-manifest.json (не комітиться). Очищений head de5d525 відповідає оригінальному ec26f2b; base828b1cf — оригінальному32c2cbc. Це приватнісно обмежене рев’ю, а не перевірка виключених матеріалів. Резервне рев’ю agy не запускалося; перевірено лише його локальні help/version. Матеріали передано лише дозволеному Claude CLI.

Cross-review: claude/default @ de5d525 (author: codex) — 8 findings: 6 fixed, 2 rejected

| № | Рішення | Доказ / зміна |
| --- | --- | --- |
| 1 | Виправлено | Failed-файл очищає warnings/skipped lists і створені результати; регресія partial з CAS. |
| 2 | Виправлено | При доповненні плану чинні canon/cards з історичними цитатами лишаються fresh; обхід до generated descendants збережено. |
| 3 | Відхилено | Starlette MultiPartParser.max_part_size перевіряє лише не-файлові поля; реальні file parts понад2MiB+1 і+1025 повертають413. Обидва тести пройшли до виправлень. |
| 4 | Виправлено | Явний author_scene_number при створенні не губиться; суперечність із заголовком відхиляється400. |
| 5 | Відхилено | Затверджений розділ5 специфікації явно допускає історичні збіги після відновлення з кошика; нове присвоєння зайнятого номера все ще відхиляється. |
| 6 | Виправлено | Додано перший runtime409/files,413, перевірки stale при повторі та точну кількість style refs. |
| 7 | Виправлено | Точний статус400, повний текст combined plan, повні IDs/errors підсумку partial. |
| 8 | Виправлено | Повернуто fallback-назву для порожнього очищеного заголовка; параметризовані тести numbered/unnumbered. |

Підтверджені дефекти спочатку відтворено RED, потім виправлено GREEN; цільовий набір26 passed. Фінальний verify.py після змін записує актуальний результат у STATUS. Початковий сирий report.md не комітиться відповідно до detent-cross-review.


Фінальна перевірка після виправлень cross-review: 1365 passed,1 skipped,0 failed/errors; 512.80s; source_changed_during_run=false; artifacts/verification-i1djlcvi/result.json. Усі суттєві підтверджені findings виправлені; повторної зовнішньої передачі коду не було.
