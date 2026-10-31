# Часткова пропозиція метаданих публікації

## Причина та погоджене рішення (23.10.2026)

Остання спроба завершилась stop, повернула JSON із анотацією/ключовими словами, але genres=[]. parse_suggestions відхиляв цілий результат через одне порожнє поле. Власник погодив зберігати коректні поля з явним попередженням, жанр обирати вручну.

## Межі та план

1. RED: parser та реальний offline coordinator для часткового результату, відсутності запису картки й warning; UI текстове відображення warning без HTML.
2. Після всіх чинних schema/eligible/PublicationData перевірок вилучати лише порожні нормалізовані значення. Якщо коректних полів немає — failed із конкретним поясненням. Непорожні недопустимі значення, зайві/чужі поля, дублікати/невалідний JSON лишаються помилками. Null як раніше означає відсутність пропозиції, а не нове значення.
3. publication_warnings зберігаються у спробі, передаються run/event та suggestions API/UI. Fingerprint/acceptance source/CAS/empty guards незмінні; warnings не входять до прийнятих полів. Промпт уточнює непорожню пропозицію.
4. SPEC/traceability/інструкція, цільові й повні перевірки. Стару failed спробу не переписувати, модель не викликати, картку не заповнювати автоматично. Нової міграції немає.

Уточнення read-only знімка: eligible_fields були annotation/keywords, жанр уже заповнений. genres=[] було порожнім відомим незапитаним полем. Окрема регресія RED→GREEN: порожнє відоме поле поза eligible пропускається з warning «збережене значення не змінено»; непорожні незапитані й будь-які невідомі поля відхиляються. Промпт версії2 уточнює непорожність/null. Саме робочу відповідь повторно перевірено без виклику моделі/публікації: artifacts/partial-publication-revalidation.json — annotation/keywords придатні, genres пропущені, історична спроба лишається failed. Жодної прихованої зміни авторських даних.

Приймання: scripts/verify.py -q — **954 passed, 1 skipped**, 0 failed/errors; artifacts/verification-mlslyo99/result.json, source_changed_during_run=false. Незалежне read-only рев’ю: blocking findings немає. Detector publication.js: []. Після перевірки відсутності active runs перезапущено точний server8765; HTTP200, publication cards та story/scene revisions/heads обох творів незмінні (artifacts/partial-publication-restart-before.json / partial-publication-restart-result.json). Авторські дані/старий failed run не переписані, платних викликів немає. Відкритій сторінці потрібне оновлення JS після збереження ручних правок. Після suite змінені лише пояснення й записи приймання; runtime/tests незмінні. Локальний коміт без push; R-18 наступна планова задача.
