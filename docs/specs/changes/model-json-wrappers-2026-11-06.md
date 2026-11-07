# Зовнішня обгортка всіх модельних JSON-відповідей

Пряме рішення власника06.11.2026: прибирати зовнішні апострофи не лише в пам’яті, а й у перевірках та інших структурованих відповідях моделей.

Причина дефекту: impact/review decoder передавав модельний текст безпосередньо до json.loads; нормалізація пам’яті не поширювалася на інші межі протоколу.

Один спільний чистий helper знімає лише одну повну парну зовнішню обгортку JSON-об’єкта: одинарні апострофи/backticks або потрійний блок з окремими рядками й необов’язковим json. Без витягування JSON із пояснень, без ремонту вмісту та без заміни апострофів усередині рядків. Непарні/вкладені/кілька блоків залишаються помилкою. Чинні schema, duplicate-key, evidence, scope та publication guards зберігаються. Сирий partial і звіт оцінювання залишаються оригінальними.

Межі застосування: planner brief/prepare, editor patches, classifier, publication suggestions, memory, impact/review (також replay/fsck), evaluator model response. Ручні JSON, конфігурація, збережені доменні об’єкти й CLI event protocol залишаються строгими. Текстова генерація draft/rewrite/edit diff не нормалізується. Fingerprint evaluator protocol збільшується: попередня калібрація не дає автоматичного допуску новому parser contract; історичні результати не переписуються.

Реалізація inline: регресії RED → helper та підключення лише на модельних межах → SPEC/traceability/UA+EN інструкції → verify.py та check_docs.py → cross-review/commit/push/PR. Нових запитів до моделей або повтору невдалого запуску немає.


Фінальний спільний gate model/import metadata та global MODEL-JSON: **1244 passed,1 skipped,0 failures/errors**, source_changed_during_run=false, artifacts/verification-smi5njs9/result.json. check_docs.py пройшов. Раніше UI110 browser passed2.7m,8 додаткових metadata/counts/shared passed,6 фінальних pricing/accessibility passed; фінальні screenshots перевірено візуально, detector[]. Без реального inference або зміни production матеріалів.

RED4 failures/8 passes → GREEN41 wrappers/memory;65 targeted parser/evaluation/review replay tests passed. Read-only перевірка останньої невдалої review_part підтвердила повний Markdown JSON-блок; після нормалізації проходять decoder і frozen schema/evidence. Оригінальний partial/статус запуску не змінено; приватний вміст не копіюється й не передається рецензенту.


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
