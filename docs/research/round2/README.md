# Другий раунд: дослідницький стенд

Стан: **основний harness заморожений** після незалежного рев’ю, виправлення6 важливих зауважень і167 офлайн-тестів. Погоджений набір48 прикладів незмінний; [frozen snapshot](frozen-primary.json) прив’язаний до code commit8f6dc5f. Усі6 native load profiles повторно точно збіглися з baseline без inference. Основний прогін завершено: **1152/1152**. [Повний звіт](../2026-10-29-local-planner-round-2-report.md) та [агрегати після авторського рев’ю](primary-summary-owner-reviewed.json) враховують 144 primary-відповіді та всі60 secondary-кандидатів; решта1008 зберігає executor labels. L5-контроль не пройдено, модельний висновок не дозволено. [Початкові агрегати](primary-summary-provisional.json) збережені без змін. Сліпі матеріали: ignored `artifacts/round-2/report/owner-review.md`. Цей код не змінює застосунок.

Чинне рішення: [prompt-freeze amendment](../2026-10-29-round-2-prompt-freeze-amendment.md). **Основний промпт — A для всіх; налаштування промпту припинене.** Усі8 учасників уже мають по8 початкових dev-відповідей, включно з L2/L4/L5; старий стан в §6 доповнення не є підставою повторювати їх. Technical dev qualification не означає проходження порогів якості.

Актуальне рішення про хмарні моделі, три повтори повних квартетів для ескалації та спільні $10: [доповнення 29.10](../2026-10-29-round-2-cloud-amendment.md). C1/C2 пройшли по 8 старих dev-прикладів; це перевірка сумісності, а не результати на holdout. Спільна розрахована вартість цих 16 викликів — $0,0054546. Dev завершено для всіх восьми учасників: [підсумок і обмеження](../2026-10-29-round-2-dev-results.md). Після згоди власника завершено решту прикладів L1/L3/L6 без повтору старих відповідей. Невалідні результати збережені; допуск усіх8 учасників з основним A погоджений prompt-freeze amendment.

Окремо після dev виконано погоджені12 повторів L3: обидва проблемні тексти дали `complete=false` у3/3 нових повторів кожен, чисті контролі пройшли6/6. [Умови, таблиця та межі висновку](../2026-10-29-L3-dev-repeatability.md). Початкові dev-агрегати не змішуються з цією вибірковою діагностикою; holdout0.

Перевірка формулювання промпту: [A/B і дослідницький C,36 викликів](../2026-10-29-L3-complete-prompt-probe.md). B не усунув complete=false; C пройшов валідатор12/12, але дав3 хибні зауваження на6 clean. Кандидати неактивні, продукт і основний дослідницький промпт не змінено; сумарно112 inference, holdout0.

## Що читати власнику зараз

Файл `docs/research/round2/holdout-review.md` містить усі 48 прикладів із розміткою та відміткою погодження. D1/D2 після незалежного рев’ю перероблено на суперечливі записи канону без пріоритету, а не просто пропущене уточнення; clean містить явне авторське розв’язання конфлікту. Власник погодив цей набір; це не доводить універсальність такого трактування question для звичайної оповідної неоднозначності. Дорослі приклади тут — легке неграфічне ню; висновки про значно відвертіший контент потребують іншого набору. Генератор не дозволяє перезапис після погодження.

Автор: GPT 6.1 Sol, thinking medium — за даними власника. Цю модель не можна обирати як C1. Незалежної перевірки фактичного runtime ID немає.

## Офлайн-команди (PowerShell, корінь репозиторію)

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONPATH='src'
.venv/Scripts/python.exe docs/research/r28l-round-2-probe.py --self-check
.venv/Scripts/python.exe docs/research/r28l-round-2-probe.py --audit-dataset docs/research/round2/holdout.json
.venv/Scripts/python.exe scripts/verify.py docs/research/round2/test_round2.py -q
.venv/Scripts/python.exe scripts/check_docs.py
```

Self-check запускає тести із забороною мережевого з’єднання. HTTP-адаптери перевіряються тільки через `httpx.MockTransport`; ключі в цих тестах — синтетичні canary. Corpus authoring script до тестованих моделей не звертається. Нових залежностей немає.

## Реалізовано

- Незмінні product protocol3 builder/validator, `current_consistency`, local temp 0,1 / output 4096 / thinking none. Research-only result cap 4096 дає три concerns.
- Відокремлення gold від request: model input містить лише premise/target; ID case, gold verdict і gold contradictions не надсилаються.
- Строга перевірка типів без boolean coercion, ремонту JSON, обрізання чи виправлення refs; незавершений текст не повторюється.
- Семантичний результат залишається pending до людського adjudication. TP/FN на рівні кожного gold contradiction, дубль не дає другого TP, зайві concerns рахуються окремо.
- Додаткове question отримує окреме людське рішення; поки його немає, результат pending. Обґрунтоване питання не оголошується автоматично хибним.
- Seeded block schedule із ротацією конфігурацій; seed рандомізує порядок, не гарантує детермінізм моделі.
- Atomic checkpoint, hashes і збережені attempts; uncertain in-flight після аварії потребує звірки. Перший змістовий результат остаточний. Транспортна помилка — максимум три спроби; HTTP error зупиняє без прихованого retry.
- Local/Google/Anthropic HTTP-адаптери без SDK retries (старий OpenAI adapter лишається лише офлайн-покритим, у погоджених учасниках його немає). Native Google schema та Messages C2 проходять спільну локальну перевірку.
- Спільний SQLite dollar ledger: резерв до HTTP, атомарна перевірка залишку, збереження відповіді, розрахунок usage за зафіксованим тарифом, повний резерв за невизначеності. Невизначений платний виклик не повторюється автоматично. Перевищення резерву провайдером блокує нові виклики до звірки.
- Тимчасові hardlink-імпорти й native model lifecycle: відмова, якщо GPU вже зайнята, перевірка фактичного load config, unload лише власного інстансу в finally. Не змінюємо product roles.
- Usage/finish/raw provider finish/seconds; відсутній reasoning usage — unknown, а не 0. Anthropic output_tokens не видається за reasoning_tokens.
- K1/K2 без inference. Підсумковий звіт блокується за pending scoring.

## Ще не реалізовано / не дозволено до наступних етапів

Немає live `quality/timing`, freeze-команди, blind adjudication UI/forms і фінального порівняльного report. Продуктові ролі не перемикалися. L1 native load/unload та dev фактично перевірені на локальному сервері; інші моделі потребують власної кваліфікації. Після dev UI-профілі L3/L4 вирівняно: UI38, engine log39 для обох; load-only контроль пройдено. Незавершений/невалідний dev не дає автоматичного дозволу на holdout.

Дослідницький dev (це справжні виклики, не self-check):

```powershell
$env:PYTHONPATH='src;docs/research'
.venv/Scripts/python.exe -m round2.dev --label L1 --model l1 --run
.venv/Scripts/python.exe -m round2.dev --label C1 --run
.venv/Scripts/python.exe -m round2.dev --label C2 --run
```

Без `--run` немає inference. Ці команди використовують лише 8 старих прикладів з round 1; cloud dev — максимум $0,40 резерву на модель із загальних $10, фактичні витрати за usage звільняють залишок. Повторний запуск використовує збережені платні відповіді, не надсилає їх заново. Local checkpoint перевіряє request/load identity; його невідповідність потребує звірки. Типово після invalid/refusal/невідомого local reasoning або short 12B >60с серія зупиняється для аналізу. Погоджений власником `--complete-dev` дозволяє завершити лише ще не виконані старі приклади після invalid; refusal/reasoning/resource gates зберігаються, cached результати не повторюються. Не передавайте ключі в чат або manifest.

Підготовка ваг: [публічний provenance](weights-provenance.json) містить pinned revisions, SHA вихідних файлів, чотирьох власних Q4_K_M і рецепт F16→Q4_K_M. L6 завантажена та перевірена; `weights_prepared=true`. Конвертація F16 — окреме Windows Python-середовище, квантизація — CPU Ubuntu WSL2 з тим самим llama.cpp commit для обох пар, без imatrix. Windows DLL заблоковано політикою; захист не змінювали. Шлях WSL погоджено власником.

`r28l-prepare-weights.py --run` завантажує pinned вихідні ваги й перевірені архіви інструментів, **не виконує квантизацію**. Для download потрібен isolated `huggingface_hub==0.36.2`: у випробуваному 2.3.0 невдалий L6 download видалив process-unique partial. Версія 0.36.2 перевірена на persistent resume; цей вибір не змінює залежності продукту. Public metadata вже в репозиторії, ignored preflight не є передумовою відтворення download. Конкретні conversion/build commands та залежності — у provenance; автоматизація повного WSL build ще не входить у CLI.

## Погоджене відхилення C2

Нативний Messages API використовує `output_config.format`, не OpenAI-сумісний endpoint. За документацією Anthropic частина length/item обмежень не підтримується в constrained schema. Власник 28.10 погодив прибрати їх лише з переданої C2 schema, дописати точні правила в system instruction і перевіряти первісним локальним валідатором. Wire schema і suffix промпту відрізняються від локальних — це явно звітується, а не називається однаковим контрактом decoding.

Джерела, прочитані 28.10.2026: [Anthropic Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs), [OpenAI Chat Completions reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create). Зміна моделі потребує повторної перевірки її конкретних можливостей; доступність і ціни тут не стверджуються.

## Артефакти й коміти

Публічні: скрипт, корпус, schema/prompt під час freeze, manifest, агрегати, звіт. Сирі запити/відповіді та reasoning — тільки `artifacts/round-2/` (ignored). Ключі лише environment; adapter не зберігає auth headers, error body або credential-bearing URL. Не передавайте секрети в `identity`/case text.

Користувацькі UA/EN інструкції продукту не потребують змін: це окреме дослідження без зміни його поведінки. Архітектурна SPEC залишається незмінною.

## Вторинна описова метрика до freeze

`validation.py` додає stable `rejection_codes` для кожної відповіді та safe codes в attempts. Основний валідатор не послаблено. Повний вихідний schema/result budget перевіряється до будь-якої діагностичної копії. До secondary допускаються лише `incomplete_processing` та `duplicate_source_reference` всередині `source_refs`, разом або окремо, якщо всі інші перевірки пройдено. Дублі target/carry, невідомі/неправильні/відсутні обов’язкові докази, JSON/type/limit/length/refusal виключають допуск.

Для доказу «в іншому проходить валідатор» створюється ізольована копія з complete=true та унікальними source_refs. Вона не повертається як прийнятий result, не замінює raw reply і не впливає на первинні лічильники. `secondary_candidate` містить саме оригінальні поля, включно з false і дублями. Повторна діагностика також очищає застарілі derived поля, щоб старий accepted result не потрапив у новий invalid.

Дублі `change_refs` чинний продуктовий валідатор самі по собі не відхиляє; це не змінено. Для вже невалідної відповіді такий дубль дає окремий secondary exclusion, зберігаючи первинну причину відхилення. Це консервативне виконання погодженого source-only винятку, не нове primary правило.

`classify_secondary` застосовує ті самі змістові TP/FP/FN/TN/question правила, але має marker `measurement=secondary`, actor executor, provisional labels та окреме рішення owner. Власник перевіряє кожного кандидата, зокрема executor FN/FP і випадки виявленої змістової відмови; обидві версії рішення зберігаються. `secondary_metrics(require_owner=True)` блокується, поки щось не перевірено; `metrics` відхиляє secondary records. Вторинні результати не беруть участі в порогах або L5 criterion.

[Офлайн-аудит початкового dev](secondary-dev-audit.json): primary статус незмінний у64/64;3 кандидати (L1 duplicate,2 L3 incomplete), усі owner reviews pending. Збережені відповіді не повторювалися й не переписувалися. Review-файл із текстами — ignored `artifacts/round-2/secondary-dev-audit/owner-review.json`. Цей provisional audit не є верифікованою вторинною оцінкою holdout.

B7 — перший бонус після основного звіту та owner review: C на L1/L3,48×1 на кожній. C SHA фіксується зараз, але кандидат не активний. Після основного раунду поточний holdout стає dev; підтвердження подальшого налаштованого промпту потребує нового відкладеного набору. Спостереження3/3 у попередніх повторах не доводить математичної детермінованості sampling.

## Freeze/prepare й основний прогін

Власник погодив спільну TP-панель: фіксований seed перемішує одиниці case/draw/gold-факт; відбір триває до покриття `ceil(TP/5)` кожної моделі. Для кожної одиниці показуються всі моделі, включно з пропусками; назви замінені на M01…M08. Seed відбору публічний; новий незалежний seed назв зберігається лише в ignored artifact, а manifest містить його SHA commitment. Форму не можна використати для відновлення відповідності назв за seed. Ключ відповідності зберігається окремо від форми й не відкривається до завершення adjudication. Первинні оцінки виконавця не є підтвердженням власника; всі secondary candidates потребують окремого повного перегляду.

`freeze.py` читає початкові64 dev replies, перевіряє hashes local checkpoints, відтворює native запити й суворі статуси, звіряє summary та фактичний нуль reasoning. Заморожуються інвентар коду й ресурсів, A/C, holdout, provenance, native system/schema/wire hashes, seeded1152-slot schedule, обрані налаштування, версії Python/бібліотек і baseline записів спільного dollar ledger. SHA ваг перевіряються перед підготовкою/запуском, а не перед кожним HTTP. Додавання чи видалення коду також порушує freeze. Сам snapshot і змінні лічильники не входять до циклічного self-hash.

Кандидат **не дозволяє inference**. Активація потребує окремого запису рев’ю саме його SHA, відсутності Critical/Important і успішних тестів. Відтворюваність runtime обмежена: native REST не показує GPU layers; збережено paired UI38/engine39, binary hashes і попередній hardware snapshot. Поточний вибір runtime в GUI та хмарні backend weights не оголошуються криптографічно незмінними.

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONPATH='src;docs/research'
.venv/Scripts/python.exe docs/research/r28l-experiment.py candidate
.venv/Scripts/python.exe docs/research/r28l-experiment.py prepare
```

Це офлайн-команди: немає читання ключів, завантаження в GPU або API inference. Кандидат пишеться в ignored artifacts; наявний файл не перезаписується. Після завершення всього коду й незалежного рев’ю — окремий freeze. `quality` вимагає activated snapshot, погодженого exclusive window й обмежує кількість нових configuration/block groups (`--max-groups`, типово1). `timing` окремо вимагає performance window, використовує8 старих dev прикладів і один окремо позначений warmup для кожної локальної моделі. Warmup не змішується з якісним або виміряним набором.

`experiment.py` перевіряє freeze перед групами/відправленням, фактичний wire перед HTTP, зберігає checkpoint і звільняє власну модель у finally. Змістовий invalid/refusal/length не повторюється. Платна transport uncertainty зупиняє вже після першої спроби й утримує ledger reserve до звірки. Збережені slots відновлюються без inference й без зайвого завантаження GPU. GPU before/after — лише вибіркові спостереження, не безперервно виміряний пік.

`review.executor_form` експортує сліпі відповіді для початкового людського adjudication; `adjudicate_form` перевіряє відповідність оригіналам і блокується за відсутніх рішень. `shared_tp_panel`/`blind_export` створюють погоджену панель власника, `secondary_form` містить усіх secondary candidates. Ці helpers не запускають додаткову модель-оцінювача. Review-форми з текстами та ключ відповідності зберігайте в ignored artifacts.

Автор працює в читабельному `artifacts/round-2/report/owner-review.md`: один `[x]` біля «Перевірено, валідне» достатній для придатної відповіді; для «Перевірено, невалідне» додається пояснення своїми словами. Обидві порожні галочки означають неперевірену відповідь. Джерела й текст мають фактичні S/T-адреси з надісланого запиту (включно з T3/T4); C біля джерела пояснює згадки C у відповіді. Технічний статус контракту показується окремо від людської оцінки змісту. Автор не зобов’язаний вручну зіставляти gold ID або редагувати JSON: рішення переносить виконавець із збереженням оригіналів. Наявну панель із позначками автора не перегенеровувати поверх; перед зміною оформлення робити повну копію.

`report.primary_summary` рахує кожний draw, neutral/adult, K1/K2, пороги FP≤7/60, miss≤10/84, valid≥137/144 та окреме Pareto L5. Flip — частка case зі зміною між трьома вердиктами clean/issue/question/mixed/invalid/refusal/transport; TP/FN не підміняють вердикт моделі. Secondary описується окремо, без порогів. Числа до завершення owner review лишаються попередніми.

Результат `primary_summary` завжди provisional і не дозволяє фінальний висновок. `apply_owner_panel` приймає саме відтворену seeded-панель; повтори одного слота для двох gold-фактів допустимі лише за однакового авторського рішення. Історія містить початкову класифікацію виконавця, рішення автора та виправлену класифікацію. `final_primary_summary` вимагає всі8 моделей, точну завершену панель/остаточні записи та owner review кожного secondary-кандидата, включно з FN/FP/відмовами.

Перед кожним native load перевіряються незмінені hardlink imports і catalogue key/розмір; після load — повний echo-профіль проти збереженого dev/paired load, включно з chat template, stop strings і speculative settings. HTTP dispatch прив’язаний до повернутого owned instance ID; canonical wire hash і фактичний instance записуються окремо. Native API не надає криптографічного digest ваг у пам’яті, тому це перевірка файлової тотожності й API metadata, а не доказ SHA завантаженої VRAM.

Після повторного завантаження timing-групи виконується новий виключений warmup з окремим ID; завершені виміри не повторюються. Некоректний успішний HTTP envelope лишається `invalid` без content retry, але зберігаються первинні bytes у base64, parsed envelope та доступні usage/model metadata для аудиту й звірки витрат. Headers і credentials не зберігаються.

Попередній резерв1152 primary slots:864local +288cloud;48timing +6warmup окремо. Conservative reserve для хмари (весь4096 output + wire-byte upper bound із запасом) — близько $2,563 на одну спробу кожного слота або $7,689 за три; це **не прогноз рахунку**. Dev уже врахований у спільних $10; senior subset ще невідомий і до цього резерву не включений. Prepare перерахує доступний залишок і перевірить строк тарифів перед запуском. Нових inference під час цієї підготовки немає.


## Діагностика після основного звіту

[Діагностичне доповнення](../2026-10-29-round-2-diagnostics-amendment.md) і [бріф](../2026-10-29-round-2-diagnostics-codex-brief.md) опрацьовані; [план](../../superpowers/plans/2026-10-29-round-2-diagnostics.md) та [проміжний офлайн-звіт](../2026-10-29-round-2-diagnostics-report.md) збережені. Speculative settings однакові всередині L1/L2 і L3/L4; MTP увімкнено лише L1/L2, зовнішню draft-модель не задано. Unsloth round-1 SHA підтверджено.

Для senior відібрано B1/C1/D1/D2: 96 викликів, максимальний reserve $9,953124 проти доступних $9,8717129. Власник залишив ліміт$10 і відклав ескалацію. Для спайку погоджено cap4096 усюди й зміну лише maxItems1/3. Наразі лише фіксація плану, без імплементації, запусків чи зміни порядку етапів. Нових inference немає; primary report/frozen inputs не змінені. B7 відкладено.


## Раунд2b: перший stop-gate

[Новий бріф](../2026-10-29-round-2b-codex-brief.md) дозволив спайк64localcalls безD перед іншими етапами. [Аудит старого holdout](../2026-10-29-round-2-holdout-audit.md) і [план2b](../2026-10-29-round-2b-holdout-rebuild-plan.md) — джерела нового контракту, primary report не змінюється. Research CLI `docs/research/r28m-spike.py` і13нових тестів готові; повний офлайн-набір180PASS. [Поточний результат підготовки](../2026-10-29-round-2-diagnostics-report.md): **блокування до inference** — Unsloth не має bundled MTP head і не завантажується з MTPtrue основного профілю. 0/64 генерацій; чекаємо рішення власника щодо однакового MTPoff. A′/новий holdout не починали.


### Спайк2b завершено; очікуємо рев’ю власника

Погоджене [MTPoff/anchor доповнення](../2026-10-29-round-2b-spike-mtp-amendment.md) зняло попереднє блокування. **64/64localcalls завершені**,182offlineтестиPASS; cap4096, MTPoff і спільнийchattemplate. FP:own3/own1=16/16та16/16,Unsloth3/Unsloth1=15/16та14/16;invalid/refusal0. Якірα16/16≥14/16пройдено, schema/weight різниці нижче7/16. [Звіт§7](../2026-10-29-round-2-diagnostics-report.md) і [агрегати](../round2b/spike-status.json). За правиломплану2b даліL3/L5/L6/C1/C2+K1/K2;L1/L2/L4непереходять. **STOPдо відповіді власника**,A′/newholdout/cloudне запускалися. Ledgerне змінено,GPUвивантажено.


### A′: початкова dev-ітерація

Після рев’ю спайку власник дозволив продовжити. Research CLI `docs/research/r28n-aprime-dev.py` готує/виконує лише одну A′v1-ітерацію:40старихnonD+4новихD, C1/C2/L3/L5/L6,220відповідей(88cloud). НовіD назавжди excluded ізholdout2b. [Текст кандидата](../round2b/prompts/check-aprime-v1-uk.txt), [журнал](../round2b/aprime-iterations.json), [devD](../round2b/dev-d-cases.json). Це не promptfreeze; новийholdout не створено. Верхнійreserve$0,793366 у спільному$10, передHTTP durable per-call ledger reservation; старі й нові completed paid calls перевіряються на continuity.192offlineтестиPASS після незалежного рев’ю3budget/parserfindingsRED→GREEN. Після результатів—STOPдлявласника.


### A′ v1: dev завершено, чекаємо власника

[Звіт](../2026-10-29-round-2b-aprime-dev-report.md):220/220,196valid/24invalid,refusal0. C2виконав4Dконтролі; C1пропустивD-time; локальнімаютьпомилкикатегорії/пропуски. Clean/invalidрозділені,issue-recallнесфабрикованоізнаявностіconcerns. [Журнал](../round2b/aprime-iterations.json) і [кандидат](../round2b/prompts/check-aprime-v1-uk.txt). Actualcost$0,0369756,held0,залишок$9,8347373,GPUпорожній. **STOPдоownerfreezeабонаступноїdevітерації. Новийholdout/оракулнестворені.**


### Recall A′: офлайн-аудит30.10

[Звіт](../2026-10-30-aprime-recall-audit-report.md) і [протоколдо labels](../2026-10-30-aprime-recall-review-protocol.md):24issue/28фактів,0новихвикликів. C1/C2=28,L3=14,L5=21,L6=19. L6втратив4протисередньогоA23черезinvalid,поріг≥2спрацював. Це не доведення семантичної надобережності. [Пофактові агрегати](../round2b/aprime-recall-audit.json). Рекомендованагілкаv2scope-only; **v1неapproved,v2нестворено,STOP**. A′семантичнозвужуєissueзагалом,не тількиD.


### Етап 3 завершено — oracle власника

30.10 власник затвердив A′ v1 для підготовки holdout, явно відхиливши рекомендовану v2-гілку через технічну природу тригера L6. Попередні STOP вище — історичні. [48 сліпих прикладів](../round2b/oracle-blind.md), [manifest та інструкція](../round2b/README.md). Gold/ключ приватні до розмітки; жодного inference на новому наборі. **STOP перед звірянням oracle, dev, freeze та quality.**
