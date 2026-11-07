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


Уточнення06.11 після фактичного запуску: configured context_tokens — верхня межа, а не довжина запиту. До provider context cap порівнюється estimated input_tokens за зафіксованим body + фактичний max_completion_tokens/max_tokens (резерв відповіді); role window не підміняє цей обсяг. Вихідний cap перевіряється окремо. Налаштування/тіло не переписуються. Помилка пояснює перевищення суми оцінки входу й резерву; оцінка може бути conservative UTF-8, не точний tokenizer. Регресія синтетична: input101778 + output8192 при configured262144 і model256000 SHALL пройти до POST; на самій межі256000 також; справжнє перевищення SHALL зупинити POST. Приватні матеріали не копіюються.

Cross-review corrections: no-retry suffix локалізується рекурсивно й без HTTP; невідомий non-API exception має нейтральний generation category technical без довільного exception text; warning зовнішньої обгортки не називає апострофи Markdown.


Cross-review: claude/default @ 3e8cec8 (author: codex) — 10 findings: 10 fixed, 0 rejected

Рецензент читав очищений commit3e8cec8, який відповідає codef1a35b9; package0.5.0/81 files integrity підтверджено,629→643 allowlisted files,0 credential matches. Оригінальні .git/config/env/user data/research/raw responses виключено.

| № | Рішення | Перевірена зміна |
|---|---|---|
| 1 | fixed | No-retry wrapper рекурсивно локалізується на сервері/JS і без HTTP; timeout/connection UA↔EN tests. |
| 2 | fixed | Non-API exception має нейтральний technical без raw exception; окрема регресія. |
| 3 | fixed | Точні незалежні очікування для output/context cap. |
| 4 | fixed | HTTP400/401/429 ×12 stages ×3 providers; точний текст і рівно один completion POST. |
| 5 | fixed | Missing caps, точна межа та завелике configured window з fitting request; окремо відсутній OpenRouter alias. Venice missing ID далі блокується чинною uncensored policy. |
| 6 | fixed | Прямий fingerprint тест protocol3 й відмінність від protocol2, додано до traceability. |
| 7 | fixed | Усі raw proof bytes порівнюються з точними captured outputs; replay/backup/tamper перевіряються для кожної обгортки. |
| 8 | fixed | Точний ImportBatchFailure із підтвердженням виклику injected failure; окремий stale revision ImportBatchConflict без sources/scenes/counts. |
| 9 | fixed | Перевірено незмінний prose head; окремий configured-secret scrub без Bearer/echo та точний echo diagnostic. |
| 10 | fixed | Warning називає зовнішню JSON-обгортку без неточного Markdown; UA/EN і збережений historical словник. |


Фінальний post-review gate: **541 passed,0 failed/errors/skipped**, source_changed_during_run=false, artifacts/verification-qxf5vqkl/result.json. Покрито provider/billing, усі web/API/Node, evaluator, planner/editor/JSON, durable failure, counts/CAS, exact raw proof/replay/backup. Попередній широкий набір1244passed/1skipped збережено окремо. Production code після цього gate не змінюється. check_docs.py перевіряється перед фінальним комітом.
