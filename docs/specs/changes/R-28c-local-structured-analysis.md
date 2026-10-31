# R-28c — Локальний структурований аналіз

Статус: власник26.10.2026 погодив підготовку специфікації й інтеграцію в поточній сесії. Окремого повторного погодження реалізації не потрібно.

## Мета та рішення

Профіль лише planner: local/Bionic localhost1235, Huihui-Qwen3.5-9B-abliterated Q4_K_M, context32768 (як реально завантажено), temperature0.1, JSON Schema, max_output4096, явне вимкнення local thinking. GPU у контрольній пробі6332MiB із8151MiB. Вхідний символьний ліміт не збільшує фізичний контекст. Інші ролі/тексти/збережені спроби не змінюються. Повний запуск книги не стартує автоматично.

ProviderSettings/EvaluatorConfig отримують local_disable_thinking=false; лише для local true передається reasoning_effort=none. UI має окремий локальний checkbox UA/EN. Legacy false не додає API поля. Це не content filter і не зміна Venice settings.

## Versioned wire2 поверх chunk protocol2

Нові local+json_schema або local_disable_thinking manifest отримують wire_schema_version=2, legacy відсутнє поле означає1. Старі manifest/task hashes/settings/API proofs відтворюються без нового поля за default false. Нова flag і wire version входять до нових fingerprints. Native schema/normalizer/packing/proof reader версійні; SQL4 без міграції.

Код визначає coverage з immutable delivered task і terminal stop; модель не переписує known64hexIDs. У модельному вході unit/source/change/document/child addresses мають короткі aliases, локальне відображення детерміноване. Усі original source/target діапазони лишаються в manifest і не обрізаються.

Для direct sources/target код будує повне покриття exact quote windows (до160символів, overlap32), для child results — лише передані source evidence, findings та target_quotes. Вхід має evidence registry з короткими E IDs. Native schema обмежує IDs допустимими значеннями. Модель повертає summary/verdict/new_findings із target_evidence_id, change aliases, поясненням, source evidence IDs; source evidence IDs, target evidence IDs та uncertainty окремі. Код розкриває refs у точні quotes/source IDs, перевіряє kind/scope/changed owners та нормалізує в PartResultV2 (PartResult+typed target_quotes). Fuzzy repair/вигадані докази відсутні.

Existing child findings переносяться кодом при reduction, не переписуються моделлю. Наявні findings не дають no_impact; unresolved child uncertainty також не дає no_impact. Source/target selections — лише допоміжні докази, не заміна повної доставки матеріалів. Модельні summaries можуть помилятися, no_impact не є доказом літературної якості. Виробничі валідація, exact original quote gates, hard caps, CAS, cancel/recovery збережені.

Measured preflight враховує реальний wire payload/schema/registry. Для невідомих child results резервується доказова registry і кількість допустимих alias values у межах зафіксованого canonical result_cap. Відповідь wire й розгорнутий canonical result мають вміщуватися у cap; перевищення дає partial failure, без обрізання й додаткових платних викликів. У preview показується wire version; немає зовнішніх сервісів для local.

## Перевірки/поставка

Реальний legacy wire1 fixture зафіксовано ДО змін. RED→GREEN локальний параметр/маршрути/native schema, aliases/registry/full validator, uncertainty/findings carry, legacy proof/hash/recovery, measured budgets. Browser UA/EN збереження лише planner, synthetic queue й API. Повний verify/check_docs, один незалежний review/fix batch. Короткі реальні локальні smoke без cloud і без публікації результатів; потім CAS-зміна тільки planner. Fresh safe-state перед restart,0active; модельний load уже32K, без SQL міграції.


Уточнення реалізації: wire2 використовує максимум12 typed target_quotes. Child payload передає references замість повторних цитат; preflight резервує canonical UTF-8 cap +1024 bytes registry/schema metadata на child, потім перевіряє actual body перед dispatch. Новий local native профіль використовує wire2 також за коротких матеріалів: інакше він залишився б у старому literal-ID контракті. Стара історія з wire1 незмінна. Ці уточнення не зменшують source/target coverage; при переповненні зберігається явна невдача.


Поставка/виміри26.10: початковий32K профіль пройшов нейтральний JSON smoke, але повний preflight книги перевищив10000 задач. Та сама модель завантажена з context131072:7752 MiB idle/7762 MiB peak із8151 MiB. Повний preview готовий за56,22с,557calls (22delta/22delta synthesis/253check/72text synthesis/188memory synthesis). Одна фактична delta пройшла повний валідатор за154,3с, prompt13590/output148/reasoning0,4evidence, stop. Це не scene no_impact assessment і не кваліфікація повного book run. Власник явно обрав128K local профіль і попросив зменшувати кількість викликів. Наступний read-only експеримент — більший output reserve, без модельних викликів.

Статус: реалізовано, перевірено й поставлено26.10.2026; активний погоджений профіль131072/4096/local9B. Планувальник оновлено через CAS, інші ролі/тексти/історія незмінні. Подальше скорочення557викликів не оголошено завершеним.
