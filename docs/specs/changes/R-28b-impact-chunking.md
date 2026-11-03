# R-28b — Бюджетовані частини перевірки впливу

Погоджений дизайн: [26.10.2026](../../superpowers/specs/2026-10-26-impact-chunking-design.md). План: [inline implementation](../../superpowers/plans/2026-10-26-impact-chunking.md).

Чинний контракт: SPEC.MD Requirement IMPACT-CHUNKS, scenarios S01…S05. Окремий manifest/proof protocol2 активується за overflow нового protocol1 preview; старі run/records лишаються за старим контрактом. Розбиття measured request, deduplicated wire docs, exact ranges, direct child coverage й обов’язковий синтез; жодного обрізання чи автоматичних повторів. Hard story/run caps і тариф збережені. Native PartResult schema і planner; нових залежностей/SQL-міграції немає.

Структура: impact/chunk_models, chunking, chunk_requests, chunk_validation — versioned wire/proof контракт; generation/impact_chunk_context, impact_chunk_readiness, impact_chunk_runner — планування/черга та accounting. Storage зберігає schema2 proofs і перевіряє фактичні raw/API bodies; не імпортує generation. UI показує parts/syntheses, phase/proof count UA/EN.

Обмеження: source summary має fixed cap; якщо модель не може зберегти зміст у ньому, має повернути uncertain. Позитивні висновки не є гарантією модельного розуміння. При >10000 tasks або мінімальній службовій оболонці поза межами — явна відмова preflight. Фактична відповідь поза cap/вхідною межею зупиняє серію, а не додає непогоджені виклики. Журнал пам’яті не переприв’язується. Optional memory failure зберігає завершені частини без публікації незавершеного поточного звіту. Реальні API/витрати не тестувалися.

## Виправлення видимого очікування preview

IMPACT-UI-S02: loading/elapsed/cancel видимі до відповіді, старий preview очищено, start прихований, cancel aborts fetch, timeout120с розблоковує retry. Лише frontend; backend/API/SQL/модельні виклики незмінні. Скасування очікування не заявляє про server CPU abort.
