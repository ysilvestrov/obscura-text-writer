# Пам’ять: зовнішні апострофи й Markdown-обгортка JSON

Дата06.11.2026. Прямий запит власника: відкидати апострофи навколо JSON пам’яті. Дослідження збереженої відповіді підтвердило повний блок ```json … ```; приватний вміст не копіюється до документації/тестів і не передається зовнішнім рецензентам.

Межі: лише модельний вхід parse_memory_result, до decode_memory. Прибирається одна повна парна зовнішня обгортка: потрійні backticks/апострофи з необов’язковим json і окремими рядками; або одинарні backtick/апостроф навколо JSON-об’єкта. Усередині JSON нічого не замінюється. Супровідна проза, непарні/кілька блоків, duplicate keys, схема, evidence/scope й публікація залишаються строгими. Manual/load_memory незмінні. Оригінальний partial зберігається, без нового inference. Нормалізація має безпечне UA/EN попередження через чинний memory_warnings/run.warning.

Один малий fix inline, base33130e0: RED tests модельної обгортки/строгості/оригіналу → мінімальний helper в journal.py та UA/EN warning → SPEC MEMORY-004/traceability й інструкції → memory/generation gate через verify.py → review/commit/push/PR поверх UI. Нової схеми даних, провайдерів, залежностей або зміни ручних контрактів немає.


Реалізовано inline. RED12 failures/6 passes до helper; GREEN18 passed. Додано ще invalid-schema випадок і reload warning регресію. Gate verify.py tests/memory tests/generation tests/integration:498 passed,0 failed/errors/skipped,110.36с, source_changed_during_run=false (artifacts/verification-qyjkzeev/result.json). Збережений production partial перевірено локально лише на JSON syntax після unwrap без друку/копіювання приватного тексту або зміни даних.

Locale gate:7 passed, source_changed_during_run=false, artifacts/verification-k4_hfwwa/result.json; check_docs.py пройшов. UI layout не змінено, нові screenshots не потрібні.


## Дозволений cross-review

Пакет0.5.0 звірено з npm integrity й81 файлами архіву. Незалежний privacy-filtered знімок625 файлів HEAD: original7cf4029→filtered1dcaa7c, base33130e0; без original .git, .env/config/credentials, production data/partials, research, diagnostics/progress/STATUS, backups/artifacts та binary images. Claude safe/restricted Read/Grep/Glob; Google/agy не запускався, credential literal scan0. Повний звіт не комітиться.

Cross-review: claude/default @ 1dcaa7c (author: codex) — 5 findings: 5 fixed, 0 rejected

|№|Зауваження|Рішення й доказ|
|---|---|---|
|1|Wrapper warning перед decode/schema/evidence.|Fixed: додавання після успішного parse result; invalid JSON/schema/evidence не має цього warning.|
|2|Слабкі rejection assertions/multi-block.|Fixed: точні причини, порожній warnings; helper лишає multi-block raw незмінним і parser відхиляє його.|
|3|Не перевірений справжній manual path.|Fixed: wrapped input перевіряється через normalize_manual_memory і load_memory, JSONDecodeError для всіх пар/режимів.|
|4|Немає boundary coverage.|Fixed: empty/quote-only/mismatched/non-object/one-line/multi-block лишаються незмінними; uppercase tag і CRLF проходять у v1 snapshot/v2 tests.|
|5|Умови й неточні warning assertions.|Fixed: параметризовані mode/data та opening/closing/expected_warnings без if; exact warning lists, стійкі warnings після reload.|

Твердження перевірено локально за receiving-code-review; посилені тести дали6 expected RED /23 passed, після виправлень wrappers+diagnostics40 passed. Фінальний gate після цих змін записується окремо.


Після review gate:514 passed/1 failed через10с timeout synthetic seven-scene flow на cursor27/28 без error; isolated повтор дав той самий timeout. Контроль з оригінальним parser33130e0 пройшов за10.19с загалом, тобто тест працює біля довільної часової межі. Для перевірки completion/export (не latency SLA) harness wait збільшено до30с; production timeout/worker не змінено. Попередні невдалі звіти збережено: artifacts/verification-48_qgjv3/result.json, artifacts/verification-vwxqc4eh/result.json; контроль artifacts/memory-wrapper-baseline.log. Фінальний весь набір повторюється після цієї test-only поправки.


Фінальний gate після всіх review/harness виправлень: **515 passed,0 failed/errors/skipped**, source_changed_during_run=false, artifacts/verification-9k5sjzus/result.json; STATUS оновлено verify.py. check_docs.py пройшов.
