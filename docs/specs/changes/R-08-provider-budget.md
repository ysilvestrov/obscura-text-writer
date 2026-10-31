# R-08 — Спільний облік викликів і бюджет

Дата: 21.10.2026. Рішення власника: платний API лише після явного ліміту;
ручний тариф дозволений із джерелом/строком дії; повна usage звільняє зайвий
резерв за зафіксованим тарифом, без видавання розрахунку за підтверджений рахунок.
За чинною вказівкою план реалізується в цьому чаті без повторного погодження.

## Межі та підхід

Єдиний accounting envelope для generation, integrated/standalone evaluation
і calibration, спільні provider client/capabilities/usage normalization.
Літературні доменні schemas і нормалізація stream/nonstream лишаються окремими.
Нових моделей, платних тестів, retries, fallback чи обходу refusal blocks немає.
Каталожні GET не містять авторських текстів. Тарифи не підставляються зі старих
звітів. Локальні та підпискові виклики мають usage без вигаданого USD=0.

Обрано транзакційний ledger у поточному app_settings замість незалежних
JSON-лічильників (гонки/збої) або нового зовнішнього сервісу (зайва залежність).
SQLite лишається schema2, backup/restore включає ledger; індексація — R-14.

## Requirement BUDGET-001: Явні ліміти

Cloud-виклик SHALL мати scope із явно заданим невід’ємним USD-лімітом.
Для твору scope — його story ID; для standalone CLI — явно заданий scope.
Необов’язковий нижчий run limit фіксується на запуск. Історичний дозвіл $1
не створює налаштувань. Local/Codex обліковуються як unpriced, без dollar-ціни.
Ліміти накопичувальні для scope; кошик/перезапуск не скидають витрати.
Зміни лімітів мають незалежну ревізію та не змінюють freshness прози.

### Scenario: Немає дозволеного бюджету
- GIVEN cloud API і scope без явного ліміту
- WHEN готується виклик
- THEN completion POST не надсилається, причина показується користувачу.

## Requirement BUDGET-002: Чинний тариф

Тариф SHALL містити provider/model/endpoint, input/output USD per1M,
request USD, джерело, fetched_at/expires_at й вид official/manual.
Значення — скінченні невід’ємні Decimal; суми ledger зберігаються цілими
нанодоларами з округленням резерву вгору. Null, negative sentinel і невідома
ціна не стають безкоштовними. Офіційний cache чинний24h; ручний тариф має
явний майбутній expires_at і непорожнє джерело. Прострочення блокує до refresh
або нового ручного підтвердження. Автоматична зміна моделі не допускається.

### Scenario: Ручний тариф
- GIVEN офіційні дані непридатні, автор задав ставки, джерело й строк
- WHEN вони валідовані та явно збережені
- THEN нові виклики можуть використати цей snapshot; старі ledger-записи
  зберігають власні ставки.

## Requirement BUDGET-003: Атомарний резерв до POST

Кожний виклик SHALL мати унікальний call ID, scope/run/attempt IDs,
request hash, provider/model і snapshot тарифу. Перед мережевим completion
створюється reserve у BEGIN IMMEDIATE; total exposure scope/run після резерву
не може перевищити cap. Прогноз R-07 і грошовий резерв розділені: для резерву
використовується консервативна повна body-byte оцінка +256 та весь output cap,
а не знижений емпіричний прогноз. Відсутній скінченний output cap блокує cloud.
Сам резерв є евристичною верхньою оцінкою вартості запиту, не договором
про обмеження рахунку в зовнішнього провайдера при зміні його тарифів/правил.

### Scenario: Конкурентні виклики
- GIVEN залишку вистачає лише на один із двох резервів
- WHEN вони створюються одночасно
- THEN лише один резерв успішний і лише він може перейти до POST.

### Scenario: Повтор того самого call ID
- GIVEN попередній запис уже існує
- WHEN код знову намагається зарезервувати/надіслати цей call ID
- THEN повторного completion немає; тотожні записи можна прочитати,
  але інша спроба потребує нового ID та власного резерву.

## Requirement BUDGET-004: Reconcile і невизначеність

Стани: reserved → sent → settled або unresolved; pre-send cancellation
може бути released. До зовнішньої операції sent фіксується стійко.
Стан і append-only events зберігають історію. Crash/restart не звільняє
reserved/sent/unresolved автоматично. Retry з новим ID не знімає старий резерв.

Пріоритет settle: валідна provider-reported cost, інакше повна фінальна usage
× snapshot тарифу, інакше unresolved із повним резервом. Неповна usage,
timeout/cancel/disconnect без фінального обліку не дають нуль. Ідемпотентне
settle не рахує виклик двічі. Факт понад резерв зберігається чесно та блокує
наступні резерви за перевищення cap; історію не обрізають до ліміту.

### Scenario: Usage без рахунку
- GIVEN завершений API response/stream має обидва цілі token counts
- WHEN provider cost відсутня
- THEN counted exposure зменшується до priced_usage_estimate, а actual лишається
  null. UI не називає цей розрахунок підтвердженим списанням.

### Scenario: Невизначений запит
- GIVEN POST міг відбутися, але завершення невідоме
- WHEN застосунок перезапускається
- THEN резерв лишається; автор може явно звірити суму з джерелом через
  окрему операцію, яка додає audit event і не змінює текстів.

## Requirement BUDGET-005: Спільний provider контракт

Спільний адаптер SHALL нормалізувати usage, request/response IDs, тривалість,
reported USD/DiEM, джерело ціни та стан розрахунку. Для OpenRouter використати
usage.cost; для Venice також top-level cost.usd/diem у stream і nonstream.
Неповна/невалідна cost не маскує відмову, технічну помилку або частковий текст.
R-04 refusal identity/blocks і R-07 exact request/body SHALL зберігатися.
Ключі й headers не входять до ledger/API/UI. Без наданого accounting context
cloud gateway відхиляє виклик; локальний backend лишається сумісним.

USD ledger — контроль тарифної USD-вартості; DiEM показується окремо.
Якщо USD cost=0, але витрачено DiEM, counted USD визначається тарифною usage,
а не видається за безкоштовний inference. Рахунок/валюта та еквівалент розділені.

## API, CLI та UI

- GET/PUT `/api/stories/{id}/budget`: ліміт, optional default_run_limit,
  незалежна budget revision, summary: available/reserved/estimated/actual/
  unresolved. Немає implicit reset або стирання ledger.
- GET `/api/stories/{id}/budget/calls`: ledger без текстів/ключів.
- POST `/api/stories/{id}/budget/prices`: ручний тариф або explicit catalog
  refresh для вибраної provider/model. Ліміт не змінюється разом із тарифом.
- POST `/api/stories/{id}/budget/calls/{call_id}/reconcile`: явна сума/джерело
  для невизначеного виклику; перевірка власності й очікуваного стану.
- RunRequest додає optional budget_limit_usd; default_run_limit копіюється на
  перший резерв цього run, наступна зміна defaults не переписує активний run.
- Standalone evaluate/calibrate: `--budget-data-dir`, `--budget-scope`,
  optional `--run-limit-usd`; scope налаштовується локальним budget CLI.
  Dry-run не резервує і не викликає платні моделі.
- Settings UI: явні ліміти й тарифи; workspace: summary і реальні причини
  зупинки; pending/невідоме не оформлюється як success. Existing style збережено.

Readiness не створює резервів і не надсилає completion. Фінальна перевірка
відбувається перед кожним POST, навіть якщо UI показав старі дані. Перевищення
бюджету — окрема технічна причина; автоматичного повтору/заміни моделі немає.

## Сумісність, безпека та приймання

Нові платні виклики legacy-творів потребують явного budget. Старі attempts
не отримують вигадану historical cost; UI вказує початок нового обліку.
Ledger посилається на IDs, не копіює авторську прозу. Backup/restore і fsck
перевіряють формат, стани, суми й приналежність scope/run/attempt де вони є.
Збій ledger після POST не знищує отриманий текст; резерв лишається counted
і warning зберігається, щоб не зобразити невідоме як безкоштовне.

Приймання offline: Decimal/invalid tariffs, concurrency, idempotency,
reconcile/missing usage, interrupted retry, refusal/cancellation, exact body,
Venice/OpenRouter cost parity, local/Codex, integrated/CLI calibration,
budget API ownership/revision, backup/fsck; desktop/mobile UI. Нові платні
тести або записи в рахунках провайдерів цією специфікацією не дозволені.

## Перевірені джерела контрактів (21.10.2026)

- [OpenRouter Usage Accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting): usage.cost — account charge; upstream cost окреме поле.
- [OpenRouter model catalog](https://openrouter.ai/docs/api/api-reference/models/list-all-models-and-their-properties): pricing prompt/completion/request.
- [Venice models](https://docs.venice.ai/api-reference/endpoint/models/list): catalog pricing USD/DiEM.
- [Venice completions](https://docs.venice.ai/api-reference/endpoint/chat/completions): top-level cost і usage; output cap включно з reasoning.


### Захист активного виклику та фінальна usage

Runtime утримує неблокувальний OS lease `billing-locks/<hash(call_id)>/worker.lock`
від резервування до завершення обліку. Ручна звірка SHALL захопити той самий
lease; для активного виклику вона відхиляється. Crash звільняє OS lock, але
не грошовий резерв. Standalone evaluation/calibration і budget CLI утримують
кореневий AppInstanceLock, сумісний із R-02 backup; dry-run його не потребує.
Local/Codex standalone без явного scope обліковуються у `cli:evaluator`.
Scope нових записів перевіряється до запису: `story:<id>` або `cli:<name>`;
для story scope потрібен чинний твір.

Невалідний usage container нормалізується до порожнього telemetry без втрати
тексту чи refusal. Лічильники stream SHALL братися з одного останнього usage
snapshot; поля з різних chunks не складаються в удавано повний фінальний usage.
Зберігаються лише дозволені числові лічильники/деталі та валідна cost.

#### Scenario: Ручна звірка під час активного standalone виклику
- GIVEN CLI вже відправив запит і тримає lease виклику
- WHEN інший клієнт намагається звірити його до нуля
- THEN операція відхиляється і доступний залишок не збільшується.

#### Scenario: Неповний останній usage
- GIVEN ранній chunk має обидва лічильники, а останній usage — лише один
- WHEN потік завершується без валідної reported cost
- THEN отриманий текст збережений, виклик unresolved, повний резерв лишається.
