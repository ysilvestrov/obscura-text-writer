# R-28 — Перевірка впливу редактури книги

Погоджений дизайн: [R-28](../../superpowers/specs/2026-10-25-book-revision-impact-design.md). План: [реалізація](../../superpowers/plans/2026-10-25-r28-book-revision-impact.md). Власник дозволив реалізацію 25.10.2026 у поточному чаті.

Контракти першого пакета: ImpactTarget фіксує target ID/SHA/format, старі та нові selector inputs, повне охоплення, проєкцію персонажів/пам’яті, refs і бази. Повторно використовувати дельту можна лише за однаковим group fingerprint. Старі дані без бази, перестановка, missing/corrupt/incomplete не отримують no_impact. Модель planner; stages impact_delta/impact_check; strict schema за налаштуванням провайдера; окремі prompts. Часткові результати/usage і контроль бюджету спільні з рештою генерації.

ImpactRecord/ImpactApplication зберігаються в app_settings під impact:{story}:report|application:{id}; без нової SQL-міграції. Застосування перевіряє run/attempt/повну первинну JSON-відповідь/ownership/target fingerprint у write TX. Старі версії, snapshot і авторські acceptance не переписуються. Ефективна актуальність визнає чинний no_impact, але не покриває цілісність/неповноту/невідомі джерела. Зміна джерел або відхилення звіту скасовує дію. Стан джерельних перевірок входить у fingerprint залежних матеріалів; своя публікація не інвалідує сама себе.

Рішення реалізатора: один сценовий матеріал на check-виклик, щоб не змішувати coverage й контекст; preview рахує фактичні матеріали, не лише сцени. Під час одного запуску дозволено прийняти лише зміни review-basis від його власних попередніх no_impact без зміни текстів, selectors або hashes. Чужі зміни дають alternative. Memory status окремий: за наявного валідного префіксного журналу та достатнього контексту own_memory передається для semantic review. Optional journal при overflow явно пропускається без блокування прози; без нього модель мусить повернути unchecked. Журнал/цитати/forwarding не змінюються; чинність memory-висновку окрема від text fingerprint.

Виявлена передумова авторського сценарію: save_manual_prose/save_manual_draft раніше створювали незалежні версії без narrative snapshot. Нові фактичні ручні Save отримують author_text snapshot з власним планом/каноном/персонажами/стилем, префіксною прозою та попередньою пам’яттю. No-op Save зберігає старий ref, існуючі історичні версії не backfill. Це потрібне для подальшої перевірки впливу редагування; old missing baseline чесно показується як неперевірювана.

Queue mode impact фіксує погоджений plan fingerprint; дубль активного запуску заборонено. Для cloud обов’язковий story-limit та окремий run-limit. Preview вимагає чинний тариф; верхня оцінка використовує max_input_chars×4+256 байтів на виклик та output cap, не вигадує локальну USD-ціну. Actual reservation/usage — через чинний CallAccounting. Settings заморожуються на спробу, наступна бере нові, без обходу hard run-limit. Cancel/pause/recovery без автоматичних повторів; збережена completed/stop спроба повторно використовується локально. Refusal/empty/protocol/technical/output-limit відрізняються.

Backup/fsck перевіряють типи, ключі, ownership, refs, первинні спроби й coverage. Старі експорти й SQL4 незмінні. UI/API реалізовані окремою disclosure-панеллю під назвою твору; user guide docs/impact-review.md UA/EN. Paid тести та deployment ще не виконувалися.

Фінальне незалежне рев’ю усунуло два fail-closed відхилення: version-valued selectors тепер обов’язково знаходять версію правильного виду/власника; обидва prerequisite journals перевіряються за exact evidence до projection. Target order stamp — префікс, а ширший horizon задається явними selectors. Авторські source labels мають окрему ознаку й не перекладаються як application diagnostics. Шість RED репродукцій стали GREEN; жодного production виправлення даних не виконувалося.

## Виправлення діагностики лімітів

Усунуто відхилення: символьний ліміт повертав загальне повідомлення з токенами, навіть коли токени вміщувалися. Спільна діагностика тепер розрізняє токенну, символьну й одночасну причини, показує обидва обсяги/межі; автоматичного збільшення лімітів немає. Контракт IMPACT-INPUTS-S03.
