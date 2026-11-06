# Тариф при виборі моделі та безпечна провайдерська діагностика

Прямі погоджені задачі власника з найближчого беклогу: тариф моделі при виборі; перевірка її реальних лімітів до запиту; конкретна безпечна причина відмови на всіх генеративних етапах. Реалізація — наступний пакет після UI controls. Початкові записи32000/24000 лишаються діагностикою, не підставою hardcode для будь-якої моделі.

## Межі й рішення

GET каталогу через чинний явний «Отримати моделі» не є inference. ModelOption доповнюється nullable max_output_tokens і tariff: використати чинний Tariff/from_catalog для USD/1M input/output та request fee, source/fetched/expires/kind. Поточний manual tariff із billing має перевагу; прострочений позначається, не замінюється нулем або новою ціною мовчки. Local/Codex без грошового тарифу — явно невідомо. Показувати тариф у datalist і в рядку під model input; UA/EN, textContent, без зміни dirty author fields. Provider/baseURL change очищує попередні metadata; stale async response не приписує іншій моделі тариф. До явного завантаження каталогу або для довільного ID показується невідомість і спосіб отримати дані, не вигадана ціна.

Для cloud generation known availableContextTokens/context_length і maxCompletionTokens/top_provider.max_completion_tokens перевіряються до POST; конфігурацію/тіло не обрізати й не переписувати. Невідомі caps не вигадувати. Чинна Venice online/uncensored/schema policy збережена. Local нестандартний API не отримує вимоги обов’язкового нового каталогу. Generation error зберігає safe FailureDetail (category/HTTP status/provider code/очищена причина), використовуючи чинний api_failure без headers/body/raw exception. Всі stages, зокрема memory, отримують generic generation_failure у attempt context; чинні classification/publication/rewrite семантики не послаблюються. Без auto retry, fallback, prompt echo або нової генерації від перегляду metadata.

## План і приймання

1. RED backend metadata/ціна/ліміти та HTTP400/401/429/timeout/connection/secret+echo; мінімальне розширення моделей/discovery/streaming/stages без storage migration.
2. RED UA/EN browser/Node модельного select, unknown/stale/manual й provider race; спільний metadata view для role settings і connection widget.
3. SPEC/OpenSpec/traceability, UA/EN instructions/neutral screenshots; цільові pytest через verify.py, browser regressions і privacy-filtered cross-review перед PR. Ізольований від counts механізм, але може йти в одному наступному перевіреному пакеті найближчих задач.


Реалізація: поточний cached official також узгоджено з billing; Невідомі caps/alias у успішному каталозі лишаються unknown, але HTTP/transport failure cloud каталогу блокує completion POST. Початкові MockTransport fixtures двох usage-snapshot тестів і zero-budget test повертали completion-відповідь на будь-який GET; доповнено правильний synthetic catalog response для нової preflight-фази, самі перевірки budget/usage збережено. Нові18 backend RED → GREEN; nested HTTP localization RED →9 locale tests passed. UI RED4 → combined6 passed, додатковий shared classifier/unknown/reload8 passed. Full browser110 passed2.7m; фінальна screenshot/accessibility confirmation й broad pytest gate тривають.


Фінальне правило cloud preflight: HTTP/transport failure каталогу завершує спробу без completion POST; success без окремого cap/alias лишає його unknown. Нові503 tests для обох cloud провайдерів фіксують0 POST. Старі MockTransport fixtures тепер відділяють GET models від POST completion, не послаблюючи budget/usage assertions. Local metadata лишаються advisory, нестандартний models endpoint не стає обов’язковим. Ціна UI — чинний billing snapshot або fresh catalog при expired official/відсутності cache; expiry manual видимий.


Фінальний спільний gate model/import metadata та global MODEL-JSON: **1244 passed,1 skipped,0 failures/errors**, source_changed_during_run=false, artifacts/verification-smi5njs9/result.json. check_docs.py пройшов. Раніше UI110 browser passed2.7m,8 додаткових metadata/counts/shared passed,6 фінальних pricing/accessibility passed; фінальні screenshots перевірено візуально, detector[]. Без реального inference або зміни production матеріалів.
