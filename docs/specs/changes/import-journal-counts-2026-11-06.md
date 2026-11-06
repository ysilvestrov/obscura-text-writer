# Кількості створених матеріалів у журналі імпорту

Прямий погоджений запит власника: біля кожного імпортованого файла показувати кількість імпортованих сцен/персонажів. Це доповнення вже погодженого additive import: дублі пропускаються, тому рахуються реально створені матеріали, не заголовки файла й не розмір поточного твору.

## Механізм

source_files вже містить JSON payload: нові created_scene_count і created_character_count додаються без SQL/schema migration. Значення невід’ємні й обчислюються сервером із publication.scenes та різниці ID нових/попередніх карток у тій самій BEGIN IMMEDIATE, що публікує source row/selectors/матеріали. Вхідні metadata counters не є доказом, caller не може підмінити підрахунок. Failed/CAS rollback не створює запису або лічильників. Рядки source_files історично незмінні, старі імпорти без полів не backfill-яться з теперішніх heads: GET лишає невідомість. Схема SQLite5, backup/restore й збережені сирі bytes незмінні.

Journal UI бере тільки збережені counts: «Нові сцени: N. Нові картки персонажів: M.» обома мовами. Для старих/некоректних відсутніх значень явне «Кількість для цього імпорту невідома», не0. Дати, filenames, active marker, scene/material не змінюються. Разовий per-file результат зберігається окремо, не використовується як нестійкий кеш журналу.

## План і приймання

RED real imports new/duplicate/zero/reload/rollback/legacy і crafted metadata → серверний atomic підрахунок → RED browser persistence/UA/EN/unknown → короткий journal renderer → SPEC/traceability/UA/EN guides/screenshots → storage/import/web gate через verify.py і cross-review. Без inference, нової SQL migration або переписування production даних.


Реалізовано без SQL migration: metadata INSERT перенесено всередині тієї самої транзакції після створення сцен, тож scene count =len(created IDs), cards =new-minus-old ID sets. RED2 failed/1 rollback passed →10 import/storage/API passed; UI RED2 → combined metadata/counts6 passed, додатковий reload/legacy/shared test8 passed. Не переписувалися production дані або старі counts.


Фінальний спільний gate model/import metadata та global MODEL-JSON: **1244 passed,1 skipped,0 failures/errors**, source_changed_during_run=false, artifacts/verification-smi5njs9/result.json. check_docs.py пройшов. Раніше UI110 browser passed2.7m,8 додаткових metadata/counts/shared passed,6 фінальних pricing/accessibility passed; фінальні screenshots перевірено візуально, detector[]. Без реального inference або зміни production матеріалів.


Cross-review: claude/default @ 3e8cec8 (author: codex) — 10 findings: 10 fixed, 0 rejected

Рецензент читав очищений commit3e8cec8, який відповідає codef1a35b9; package0.5.0/81 files integrity підтверджено,629→643 allowlisted files,0 credential matches. Оригінальні .git/config/env/user data/research/raw responses виключено.

| № | Рішення | Перевірена зміна |
|---|---|---|
| 1 | fixed | No-retry wrapper рекурсивно локалізується на сервері/JS і без HTTP; timeout/connection UA↔EN tests. |
| 2 | fixed | Non-API exception має нейтральний technical без raw exception; окрема регресія. |
| 3 | fixed | Точні незалежні очікування для output/context cap. |
| 4 | fixed | HTTP400/401/429 ×12 stages ×3 providers; точний текст і рівно один completion POST. |
| 5 | fixed | Missing caps, точна межа та завелике configured window з fitting request; окремо відсутній OpenRouter alias. Venice missing ID далі блокується чинною uncensored policy. |
| 6 | fixed | Прямий fingerprint тест protocol3 й відмінність від protocol2, додано до traceability. |
| 7 | fixed | Усі raw proof bytes порівнюються з точними captured outputs; replay/backup/tamper перевіряються для кожної обгортки. |
| 8 | fixed | Точний ImportBatchFailure із підтвердженням виклику injected failure; окремий stale revision ImportBatchConflict без sources/scenes/counts. |
| 9 | fixed | Перевірено незмінний prose head; окремий configured-secret scrub без Bearer/echo та точний echo diagnostic. |
| 10 | fixed | Warning називає зовнішню JSON-обгортку без неточного Markdown; UA/EN і збережений historical словник. |


Фінальний post-review gate: **541 passed,0 failed/errors/skipped**, source_changed_during_run=false, artifacts/verification-qxf5vqkl/result.json. Покрито provider/billing, усі web/API/Node, evaluator, planner/editor/JSON, durable failure, counts/CAS, exact raw proof/replay/backup. Попередній широкий набір1244passed/1skipped збережено окремо. Production code після цього gate не змінюється. check_docs.py перевіряється перед фінальним комітом.
