# R-16c — FB2 та EPUB

Виконання в поточній гілці й сесії за погодженими рішеннями R-16, без додаткового підтвердження. Base9b2b9d3, чистий checkout. Специфікація: docs/specs/changes/R-16-publication-formats.md; чинна SPEC R16-META/COVER/SUGGEST, EXPORT-001. PDF лишається R-16d.

## Послідовність

1. RED→GREEN: спільний captured snapshot, перевірка повноти/ресурсів, plain-text paragraphs, FB2 stdlib XML + локальна XSD з optional lxml; EPUB stdlib XML/ZIP + структурний validator. Контроль усіх полів, довільного тексту, обкладинки, семи сцен і15k слів, помилок/незмінності snapshot.
2. Фасад exports: нові формати, manifest v2 і SHA-256, bytes-first/manifest-last через чинні atomic writes; download MIME/hash guard і legacy manifests. Регресія MD/TXT. Одна форма вибору формату замість prompt/confirm, explicit allow_incomplete, збереження попередніх посилань при помилці, busy/dirty guards.
3. Офіційний EPUBCheck5.4.0 + portable Java як локальний dev tool з версіями/хешами в ignored artifacts; XSD acceptance, незалежне review всього пакета; SPEC/traceability/інструкція, UI desktop/mobile й повний scripts/verify.py; локальний коміт без push.

## Рішення

- Рендерери отримують захоплені дані й не читають author blobs/БД/мережу/ключі; FB2 validator читає лише комплектні XSD ресурси. Manifest містить точні resolved card/signatures/cover і хеш файла; читачевий XML не містить внутрішніх story/version IDs. UUIDv5 видання стабільний, окремий export UUID.
- Параграф — фізичний непорожній рядок прози; кожен порожній рядок — empty-line у FB2 / порожній p з br у EPUB. CRLF/CR нормалізуються лише як роздільники рядків; текст/пробіли всередині рядків не редагуються. Непридатні XML1.0 control/surrogate symbols дають явну помилку, не мовчазне вилучення.
- Неповний експорт має видиме маркування у книзі та manifest. allow_incomplete не обходить metadata/schema/hash/cover помилки. EPUB дозволяє необраного автора, FB2 — ні.
- Залежності optional publication з lazy import. Java/EPUBCheck не є runtime-залежністю сервера. Жодних платних/модельних запитів і змін робочих авторських даних.

## Журнал

- [x] Рендерери/валідація
- [x] Фасад/API/UI
- [x] Приймання/документація/review; локальний коміт цього набору змін

Фактичне приймання: artifacts/verification-tqjuq_ib/result.json — 891 passed, 1 skipped, 0 failures/errors, source_changed=false. Офіційні шість форматних контролів — artifacts/r16c-official/acceptance/result.json, усі exit0; незалежне review no findings. Edge headless desktop1440/mobile390: artifacts/r16c-ui/result.json/screenshots, без JS errors/горизонтального переповнення. Детектор Impeccable: лише advisory щодо наявних стилів/статичного HTML без CSS; нових literal tokens не додано. Читачі FB2/EPUB і PDF — окреме спільне приймання R-16d; не оголошені пройденими. Після повного прогону змінені лише README/PRODUCT й цей запис приймання, журнал; runtime/tests незмінні.
