# Пам’ять: зовнішні апострофи й Markdown-обгортка JSON

Дата06.11.2026. Прямий запит власника: відкидати апострофи навколо JSON пам’яті. Дослідження збереженої відповіді підтвердило повний блок ```json … ```; приватний вміст не копіюється до документації/тестів і не передається зовнішнім рецензентам.

Межі: лише модельний вхід parse_memory_result, до decode_memory. Прибирається одна повна парна зовнішня обгортка: потрійні backticks/апострофи з необов’язковим json і окремими рядками; або одинарні backtick/апостроф навколо JSON-об’єкта. Усередині JSON нічого не замінюється. Супровідна проза, непарні/кілька блоків, duplicate keys, схема, evidence/scope й публікація залишаються строгими. Manual/load_memory незмінні. Оригінальний partial зберігається, без нового inference. Нормалізація має безпечне UA/EN попередження через чинний memory_warnings/run.warning.

Один малий fix inline, base33130e0: RED tests модельної обгортки/строгості/оригіналу → мінімальний helper в journal.py та UA/EN warning → SPEC MEMORY-004/traceability й інструкції → memory/generation gate через verify.py → review/commit/push/PR поверх UI. Нової схеми даних, провайдерів, залежностей або зміни ручних контрактів немає.


Реалізовано inline. RED12 failures/6 passes до helper; GREEN18 passed. Додано ще invalid-schema випадок і reload warning регресію. Gate verify.py tests/memory tests/generation tests/integration:498 passed,0 failed/errors/skipped,110.36с, source_changed_during_run=false (artifacts/verification-qyjkzeev/result.json). Збережений production partial перевірено локально лише на JSON syntax після unwrap без друку/копіювання приватного тексту або зміни даних.

Locale gate:7 passed, source_changed_during_run=false, artifacts/verification-k4_hfwwa/result.json; check_docs.py пройшов. UI layout не змінено, нові screenshots не потрібні.
