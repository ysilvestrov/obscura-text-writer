# Виправлення планувальника: одна Markdown-обгортка JSON і конкретна діагностика

Read-only діагностика останнього brief run0926111: finish_reason=stop, complete JSON усередині одного зовнішнього ```json блоку; модель WritersBrief внутрішній JSON приймає. Немає переповнення, відмови або помилки змісту. Сирий partial лишається приватним artifacts і stage attempt.

Поведінка: brief/prepare дозволяють plain JSON або одну повну зовнішню Markdown-обгортку json/без мови; лише whitespace поза нею. Не шукаємо JSON у довільному тексті, не ремонтуємо поля/коми, не вилучаємо зайві поля. Duplicate keys/nonfinite/надмірна рекурсія відхиляються, Pydantic strict schema лишається. Внутрішній JSON зберігається як result; оригінальний stream partial незмінний, warnings у attempt/run. JSON/schema/publication failures мають окрему безпечну причину без відлуння значень/секретів, максимум3 структурні помилки. Ніяких автоматичних повторів/нових платних викликів/зміни профілю. Історичні failed attempts і голови робочих сцен автоматично не змінюються.

RED→GREEN: fencebrief перестає падати, proposed_changes все ще needs_review; malformed/plain wrongtype/extra/duplicate/multiple objects не публікуються. Prepare використовує той самий parser із власною схемою. Root SPEC/traceability/full verify/незалежне review, локальний коміт. Сервер застосувати після перевірок, якщо немає активного inference.

Реалізовано:13нових контрольних кейсів, independent review no findings, full verify918passed/1skipped (artifacts/verification-a6s1ej1f/result.json). Робочу відповідь перевалідовано без генерації/публікації. Сервер застосував новий parser, heads/revisions незмінні. SPEC PLANNER-JSON/traceability/check_docs узгоджені; останні зміни після full verify — тільки цей запис і журнал.
