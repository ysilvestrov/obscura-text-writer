# R-07 — Перевірні профілі оцінки токенів

Дата: 21.10.2026. Рішення власника: збір usage автоматичний, активація
перевіреного профілю лише явною дією після звіту. Виконання в цьому чаті
після підготовки плану, без додаткового підтвердження за чинною вказівкою.

## Межі та підхід

Спільна чиста оцінка для generation та evaluation замінює два незалежні
розрахунки bytes/2+64. Облік ціни й спільний transport залишаються R-08.
Додаткових платних викликів, tokenizer-download або прихованого clipping немає.
Порівняно з локальним tokenizer (не завжди доступний/ідентичний серверу)
та єдиним середнім коефіцієнтом (небезпечна екстраполяція) обрано перевірені
емпіричні профілі з консервативним fallback.

## Requirement TOKEN-001: Повний запит і походження

Оцінка SHALL використовувати той самий JSON body, який отримує API:
messages, response_format/schema та provider options, без auth headers/ключів.
Generation SHALL будувати body до preflight й передавати саме його gateway;
evaluation SHALL використовувати спільний builder між preflight і transport.
Exact body зберігається у спробі/звітi; observation містить digest, розміри,
identity, usage та provenance, без копії авторського тексту.

### Scenario: Схема займає контекст
- GIVEN ті самі messages та більша response schema
- WHEN оцінюється запит
- THEN враховується збільшений body; max output резервується окремо.

## Requirement TOKEN-002: Консервативний fallback

Без активного придатного профілю оцінка SHALL дорівнювати UTF-8 byte count
канонічного body + 256 overhead. Це явно позначена консервативна евристика,
не математична гарантія для невідомого tokenizer чи server-side prompt.
Ліміт символів messages і context-output перевіряється без clipping.
Відомі tokenizer revision не підміняються здогадками; unknown позначається явно.

### Scenario: Немає usage
- GIVEN провайдер не повернув додатний цілий prompt_tokens
- WHEN завершено спробу
- THEN вона зберігає usage як є, але не є навчальним спостереженням;
  нуль/відсутність не інтерпретуються як безкоштовний або нульовий вхід.

## Requirement TOKEN-003: Профіль та незалежна перевірка

Identity SHALL включати provider, нормалізований endpoint, model,
tokenizer revision (unknown, якщо не надано), формат messages/response schema
та hash system prompt/provider options, що впливають на вхід. Режими/schema різних ролей не
змішуються. Секрети й transport-only параметри не входять у body/hash profile.

Допуск потребує щонайменше 40 різних body digests: 30 train та 10 holdout.
Дублікати й повтори одного body не збільшують вибірку. Детермінований поділ
за digest відтворюваний. Повний діапазон byte sizes має різнитися ≥4 рази;
кириличний, ASCII і JSON-орієнтований content мають ≥5 спостережень кожний,
з представленням кожного типу в train і holdout. Class визначається по user
content: валідний JSON → json, інакше ≥20% кириличних літер серед літер →
cyrillic, решта → ascii. Суміш не означає точну лінгвістичну класифікацію.

Коефіцієнт — max(prompt_tokens/body_bytes) у train, не середній.
Оцінка = ceil(body_bytes × coefficient × 1.20) + 256. Допуск вимагає
нуль недооцінок на holdout; звіт містить точність, запас і діапазон.
Це емпіричний допуск, не гарантія tokenizer.

### Scenario: Повтори короткого набору
- GIVEN 48 результатів R-17 лише для 18 різних коротких body
- WHEN формується профіль
- THEN допуск відхиляється як недостатня вибірка/діапазон;
  поточні пороги не змінюються для отримання успіху.

## Requirement TOKEN-004: Явна активація та інвалідація

Навіть eligible-профіль SHALL залишатися неактивним до явного activate.
У першій версії керування — локальний CLI list/build/activate/deactivate;
публічний Python service використовується CLI й runtime. Зміна identity,
вихід за перевірені min/max bytes, вік профілю >7 днів або нове спостереження
з фактичними prompt_tokens понад оцінку повертає fallback. Недооцінка
стійко деактивує профіль до нового build/acceptance; жодної автозаміни.

### Scenario: Автор не активував
- GIVEN сформований профіль пройшов усі перевірки
- WHEN запускається наступна сцена до activate
- THEN використовується fallback, а не знижений резерв.

## Дані, інтеграція, сумісність

Нейтральний пакет token_budget: request measurements/identity, estimator,
profile builder/service/CLI. Repository надає предметні read/write/list
операції поверх app_settings для observations і profiles, без SQL у generation.
ContextView фіксує профілі разом із read snapshot. Схема SQLite лишається 2;
backup/restore включають app_settings. Legacy attempts без exact body не
використовуються для автоматичної калібровки; старі bundles читаються.

ContextBundle та evaluation metadata SHALL показувати method, confidence,
profile ID/reasons, input/output budget. Прогноз не змінює freshness готового
тексту; спроба фіксує свою оцінку. Додавання observation не торкається
story/config revision. Збій запису telemetry не знищує вже отриману прозу:
дані спроби лишаються джерелом повторного offline збору, warning доступний.
include_usage не вмикається потай для непідтримуваних backend.

## Приймання

RED→GREEN: exact builder/transport parity, schema overhead, Cyrillic/ASCII/JSON,
нуль/відсутня usage, dedup, min samples, train/holdout, різні моделі/режими,
manual activation, expiry/range/drift, snapshot/backup, legacy readers.
Offline тести та повний suite без нових модельних витрат. Чинні SPEC Context
requirements і технічні описи оновлюються разом із реалізацією.
