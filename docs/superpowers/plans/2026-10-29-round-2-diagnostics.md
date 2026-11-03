# Діагностика другого раунду — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** окремо перевірити провенанс speculative decoding, поведінку старших моделей на проблемних шаблонах і причину FP L1 без переписування результатів раунду 2.

**Architecture:** окремий дослідницький контур із власним manifest та checkpoints; повторне використання незмінних pure-функцій frozen harness. Первинний звіт, gold, raw results і `src/**` не редагуються. Платна ескалація, локальний спайк та звіт мають окремі точки зупинки.

**Tech Stack:** Python із `.venv/Scripts/python.exe`, чинні native Google/Anthropic adapters, Bionic API, SQLite research ledger, SHA-256, pytest.

**Spec:** [діагностичне доповнення](../../research/2026-10-29-round-2-diagnostics-amendment.md), [бріф](../../research/2026-10-29-round-2-diagnostics-codex-brief.md), [хмарний контракт](../../research/2026-10-29-round-2-cloud-amendment.md).

**Стан:** рішення власника29.10 зафіксовані: бюджет$10 без підвищення, ескалацію відкладено; спайк має cap4096 усюди й лише maxItems1/3. Власник обрав наразі тільки оновлення плану: імплементацію/запуски не починати, порядок етапів не міняти. Офлайн-розвідка виконана; inference0.

## Global Constraints

- Первинний звіт `docs/research/2026-10-29-local-planner-round-2-report.md` не змінювати.
- Лише погоджені синтетичні тексти; ключі не записувати в artifacts, логи чи Git.
- Сирі дані — ignored `artifacts/round-2/diagnostics/`; у Git — код, manifest, документація й агрегати.
- Немає ремонту, content retry чи відкидання invalid/refusal зі знаменника. Для local transport — чинна обмежена політика спроб; для paid uncertainty — зупинка й звірка, без автоматичного повтору.
- Той самий промпт A, temperature 0.1 / output 4096 для local, reasoning none; cloud provider defaults і погоджене schema-relaxation Anthropic зберігаються.
- Старші моделі отримують однакові повні квартети × 3 повтори; не скорочувати вибірку через бюджет.
- Argon tariff snapshot чинний до 05.11.2026 включно; пізніше — перевірити офіційні тарифи й повторно розрахувати резерв.
- Не змінювати продукт, ролі, tokenizer bindings, `SPEC.MD`, первинний frozen harness або його snapshot.
- Ніякого inference до успішних офлайн-перевірок; B7, timing та нові дослідницькі умови не запускати автоматично.
- Локальні коміти по етапах, без push. Перед кожним комітом перевірити потребу оновити документацію; користувацькі UA/EN інструкції продукту тут не змінюються.

## Review Focus

1. Помилкове трактування відсутнього draft-лічильника як нуля — тестувати `missing`, `zero`, `positive` окремо.
2. Втрата контрольних квартетів або пропуск partial miss / extra finding при відборі — перевіряти точний набір і знаменники.
3. Випадкове послаблення frozen guard через додавання нового research-коду — перевіряти старий snapshot і новий manifest окремо, дрейф старих файлів завжди відхиляти.
4. Підміна історичної schema поточною через імпорти `r28k` — перевіряти історичний commit, actual request і per-case hashes.
5. Хибне «покращення» FP завдяки invalid/refusal або виправленню D-b — зберігати машинний статус, початковий gold і окремі описові лічильники.

## Виявлене до імплементації

### 1. Speculative decoding

Для кожної L1–L6 прочитано 20 load records: dev, final-load-only і 18 quality-сесій. Усередині кожної моделі speculative-поля однакові; налаштування L1/L2 збігаються, L3/L4 також збігаються.

- L1/L2: `speculative_draft_mtp=true`, `speculative_draft_simple=false`, `speculative_draft_model=""`, max draft tokens 3, min 0, min continue probability 0.
- L3–L6: MTP false, simple false, зовнішню draft-модель не задано; решта цих полів ті самі.
- L1 та L2 мають позитивні draft counters у всіх 8 dev і 144 quality відповідях кожна. L3–L6 цих counters не мають; це відсутня телеметрія, а не доказ виміряного нуля.
- Збережені metadata вказують MTP, а не іменовану зовнішню draft-модель. Точну внутрішню реалізацію runtime не припускати. Підстав для парного stop за наявними записами немає.

### 2. Ескалація й бюджет

Відбір із `primary-owner-reviewed.json`: `FP`, `FN`, `question-missed`, будь-який `fn_ids` або `extra_findings > 0`. C1/C2 не мають технічних invalid/refusal/transport; за їх появи потрібна окрема оцінка, а не автоматичний semantic failure.

**Шаблони: B1, C1, D1, D2.** По чотири приклади кожного: neutral/adult × a/b. Разом 16 прикладів × 3 повтори × 2 senior-моделі = **96 викликів** (48 на модель).

| Модель | Максимальний резерв USD |
| --- | ---: |
| `gemini-4-argon` | 3.279180 |
| `claude-opus-5-5` | 6.673944 |
| Разом | **9.953124** |

Резерв розраховано незмінним `reserve_for_wire`: фактичний native wire в UTF-8 + 8192 запасу входу й усі 4096 output tokens за чинним tariff snapshot. Це верхня межа, не прогноз рахунку. Read-only залишок ledger — **9.8717129 USD**, бракує **0.0814111 USD**. Жодного резервування/HTTP під час планування не зроблено.

**Рішення власника:** ліміт залишається$10; ескалацію поки не запускати. Варіант$11 відхилено. Ledger contract і frozen `cloud.LIMIT` не змінювати. Не скорочувати квартети/повтори/output і не звільняти резерви штучно. Task2/3 відкладені до окремого рішення; порядок етапів не змінювати мовчки. Виконання Task4 перед ними власник також наразі не дозволив.

### 3. Ваги й фактор спайку

Unsloth-файл знайдено: `C:/Users/yuriy/.lmstudio/models/unsloth/Qwen3.5-9B-GGUF/Qwen3.5-9B-Q4_K_M.gguf`. SHA перевірено повністю: `03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8`.

Історичний `r28k` у commit `16ed9f2` задає `result_cap=2048`; `wire.py` обчислює maxItems як `max(1,min(4,(result_cap-256)//1100))`: це **максимум 1**, а не обов’язково одне зауваження. Раунд 2 має cap 4096 і максимум 3; мінімум 3 ніде не вимагається.

**Рішення власника:** cap4096 в обох стовпцях; змінювати лише `concerns.maxItems`1/3. Інші поля schema та повідомлення мають бути однаковими для того самого прикладу: message/ref/carry limits не зменшуються разом із maxItems. Порівняння schema diffs повинно дозволяти лише цей шлях. Max1 при cap4096 не називати повторенням історичного режиму раунду1. Наперед задані межі інтерпретації ≥8/20 зберігаються. Фактичні per-case hashes фіксуються при майбутній підготовці, до inference.

Це рішення про дизайн, не дозвіл на запуск. Власник окремо обрав «Поки лише зафіксувати рішення в плані»; коду/запусків зараз немає.

## Карта файлів і межі

- Створити `docs/research/round2_diagnostics/` із вузькими модулями `audit.py`, `contracts.py`, `selection.py`, `execution.py`, `reporting.py` та відповідними `test_*.py`.
- Створити `docs/research/r28m-diagnostics.py` — CLI prepare / run-escalation / run-spike / report із явними opt-in прапорцями для HTTP.
- Створити `docs/research/round2_diagnostics/manifest.json` — нові умови, рішення, SHA, paths, selection, reserve, статус. Не переписувати primary manifest задля зміни frozen умов.
- Створити `docs/research/2026-10-29-round-2-diagnostics-report.md` — окремий діагностичний звіт.
- Оновити research README та журнал виконання; користувацькі інструкції застосунку не зачіпати.
- Original `docs/research/round2/*.py` використовувати без редагування. Вони динамічно включають весь research-код у inventory: нові файли вимагають **додаткового diagnostic snapshot**, а не перезапису primary freeze. Новий guard перевіряє всі 404 original paths проти старого snapshot, окремо точний allowlist/SHA нових diagnostic files; невідомий доданий файл або змінений старий файл — стоп. Тести повинні довести обидві заборони. Старий `workspace_inputs` не оголошувати сумісним із розширеним inventory без цієї перевірки.

## Task 1: Зафіксувати офлайн-аудит і рішення

**Files:** `audit.py`, `test_audit.py`, diagnostic manifest, окремий diagnostic report.

**Interfaces:** `audit_saved_provenance(root: Path) -> dict`; `verify_original_and_diagnostic_snapshot(root: Path, original: dict, diagnostic: dict) -> None`.

- [x] Прочитати dev/preflight/quality load configs і counters без API; перевірити паритет налаштувань у парах.
- [x] Перевірити Unsloth SHA; зберегти офлайн-дані в ignored `artifacts/round-2/diagnostics/planning-audit.json`.
- [x] Рішення власника щодо бюджету й фактора спайку зафіксовані в §6 діагностичного доповнення; також записано обмеження «лише план», без дозволу на імплементацію.
- [ ] Написати RED-тести `test_pair_draft_mismatch_stops`, `test_missing_counter_is_unknown`, `test_original_file_drift_rejected`, `test_unlisted_new_code_rejected`.
- [ ] Реалізувати аудит/guard; записати діагностичне відхилення провенансу: параметри були у raw/load configs, але не описані в primary report. Primary report не змінювати.
- [ ] Запустити тести через `.venv/Scripts/python.exe scripts/verify.py docs/research/round2_diagnostics/test_audit.py -q`; очікується PASS. Окремо `check_docs.py`.
- [ ] Локальний коміт етапу. За розбіжності draft у парі — стоп і питання власнику до інших запусків.

## Task 2: Підготувати точну ескалацію без HTTP

**Files:** `selection.py`, `contracts.py`, `test_selection.py`, `test_contracts.py`, diagnostic manifest.

**Interfaces:** `select_senior_cases(cases: list[dict], primary: list[dict]) -> list[str]`; `prepare_senior_schedule(root: Path, day: str) -> dict` (cases, slots, native request hashes, per-model reserve, ledger balance, eligibility).

- [ ] RED-тести на partial miss, extra finding, question-missed, точні квартети B1/C1/D1/D2, 48 слотів на модель / 96 разом, незмінений D-b gold; technical failure не включати мовчки.
- [ ] Реалізувати відбір через frozen `escalation_cases`; request/envelope будувати через існуючі frozen adapters і A, Anthropic deviation зберегти.
- [ ] Повторно прочитати ledger у режимі read-only; перевірити строк тарифів і повний reserve. За недостатнього залишку — стоп, без скорочення квартетів/повторів/output.
- [ ] **Відкладено:** власник залишив$10 і заборонив запуск ескалації наразі. Не реалізовувати підвищення ліміту чи обхід наявного budget guard. Відновлення потребує окремого рішення.
- [ ] Зафіксувати максимальний резерв у manifest; показати вибірку й суму власнику й отримати дозвіл на запуск згідно точки STOP бріфу. Наявне погодження моделей/ліміту не підміняє цю точку.
- [ ] Тести через `scripts/verify.py`, `check_docs.py`, локальний коміт prepare-етапу.

## Task 3: Виконати ескалацію та зберегти окремі оцінки

**Files:** `execution.py`, `test_execution.py`, CLI, ignored `diagnostics/escalation/`.

**Interfaces:** `run_senior_schedule(prepared: dict, *, authorized: bool) -> dict`; `score_senior_results(results: list[dict], adjudications: list[dict]) -> dict`.

- [ ] RED-тести: без authorized немає HTTP; reserve до send; uncertain paid call не повторюється; completed checkpoint використовується без HTTP; invalid/refusal не ремонтуються; original snapshot перевіряється перед dispatch.
- [ ] Реалізувати послідовний запуск, progress, checkpoints, safe errors та usage settlement у спільному ledger. Кожна спроба має унікальну identity; конфігураційна помилка — стоп для з’ясування.
- [ ] Після дозволу виконати рівно 96 перших спроб; невизначені/транспортні випадки не повторювати без звірки. Не запускати новий dev чи warmup у хмарі мовчки.
- [ ] Розмітити frozen-правилами за gold; partial misses, extra findings, invalid/refusal зберігати окремо. За спірного змісту — авторське рішення, без видавання виконання валідатора за змістову якість.
- [ ] Окремо прочитати D-b: чи модель вказує на відсутність author priority в передумовах. Навести це як причину зауваження, не як новий gold/перерахунок primary.
- [ ] Окремий локальний коміт результатів етапу й витрат. Первинних 48×3 таблиць не змінювати.

## Task 4: Підготувати й виконати локальний FP-спайк

**Files:** `contracts.py`, `execution.py`, `test_contracts.py`, `test_spike.py`, ignored `diagnostics/spike/`.

**Interfaces:** `build_spike_request(case: dict, model: str, profile: str) -> dict`; `prepare_spike_schedule(cases: list[dict], seed: int) -> list[dict]`; `run_spike(prepared: dict, *, authorized: bool) -> dict`.

- [ ] Відновити historical r28k/wire contract із commit `16ed9f2`, перевіривши його залежності й збережені round-1 requests. Поточний імпорт r28k сам собою не відтворює історичні залежності.
- [ ] RED-тести на max1/max3 за cap4096 в обох профілях; schema diff лише `$.properties.concerns.maxItems`; per-case schema SHA та request SHA; достатність refs; max0 empty list дозволено; 20 clean і рівно 80 слотів, без issue. Якщо ліміт однаковий, max1 schema перевіряти як max1 також локально, а не через мовчазне відновлення max3 із result_cap.
- [ ] Зберегти schema hashes для кожного прикладу/профілю (enum refs залежать від прикладу), system/payload/wire hashes та історичний source SHA у manifest.
- [ ] Зафіксувати seed порядку до запусків, чергувати чотири клітинки блоками; один слот case/cell без content retry. Обидва файли ваг перевірити за SHA, включно з Unsloth ще раз перед load.
- [ ] До зміни GPU зберегти стан Bionic; перевірити, що він доступний дослідженню. Для всіх клітинок вимагати однакові speculative settings L1 з аудиту: MTP true, external draft empty, max draft3. Якщо Unsloth не підтримує цей профіль — стоп, не вимикати MTP в одній клітинці.
- [ ] Після офлайн-тестів і погодження плану виконати 80 викликів. Reasoning0 перевіряти за telemetry, local transport attempts відділяти від першої змістової відповіді. Відновити попередній стан GPU навіть після помилки.
- [ ] Показати FP/20 разом із invalid/refusal/transport і кількістю повернутих concerns. Не трактувати invalid як TN; окремо показати непорожні concerns навіть у invalid, щоб не сховати вигадане зауваження.
- [ ] Застосувати наперед записану межу ≥8/20 в обох рядках або стовпцях. Фактор стовпців — лише maxItems1/3 за незмінного cap4096; напрямок різниці теж показати. Менші/суперечливі різниці — описові, не причинний висновок. Не оцінювати recall на clean-only наборі.
- [ ] `scripts/verify.py` для diagnostic тестів, локальний коміт етапу.

## Task 5: Підсумковий діагностичний звіт і зупинка

**Files:** `reporting.py`, `test_reporting.py`, `2026-10-29-round-2-diagnostics-report.md`, diagnostic manifest/README, журнал виконання.

**Interfaces:** `build_diagnostics_report(audit: dict, senior: dict, spike: dict) -> str`.

- [ ] RED-тести на всі знаменники, окремі primary/senior/spike джерела, відсутність зміни primary report, відсутність inference при побудові звіту, рівно один post-hoc рядок чутливості.
- [ ] Побудувати окремий звіт: provenance, senior по шаблонах/моделях, D-b reasoning, FP-таблиця 2×2, витрати, відхилення, обмеження. Не створювати загального рейтингу старших моделей на 48 прикладах.
- [ ] Додати **один** явно post-hoc рядок «без D-b» з усіма модельними значеннями поруч з оригіналами; знаменники перерахувати явно (clean60→48, issue84 незмінний, calls144→132 для основного набору), пороги не перевіряти повторно. Gold і первинні числа лишити без змін.
- [ ] Аудит raw/checkpoint SHA, відсутності секретів у tracked files, незмінності primary report та всіх original frozen files; виконати diagnostic і frozen offline tests через `scripts/verify.py`, перевірити `check_docs.py`.
- [ ] Вказати фактично виконані перевірки й невиконані етапи; локальний коміт. Передати звіт власнику й **зупинитися**. B7 лишається відкладеним до його рішення.

## Подальші рішення власника

1. Наразі лише збереження плану — виконано. Не починати імплементацію/запуски до наступного явного доручення.
2. Ескалацію відкладено; ліміт$10 лишається чинним. Для її відновлення потрібне окреме рішення з огляду на повний reserve.
3. Якщо власник захоче виконати локальний спайк перед ескалацією, це має бути явна зміна порядку §5. Наразі такий порядок не погоджено.
4. Перед майбутніми локальними вимірами потрібне доступне для дослідження Bionic/GPU; профілі під час серії не змінювати.
5. Завершений діагностичний звіт має пройти рев’ю власника; B7 — окреме наступне рішення.

## Самоперевірка плану

Кожний етап бріфу має окрему задачу; точки STOP збережені. Два рішення дизайну закриті, але дозвіл на виконання не наданий. Фактор спайку однозначний: лише maxItems1/3, cap4096 усюди. П'ять ризиків Review Focus закріплені тестами Tasks1–5. Виконані лише офлайн-пункти Task1 та розрахунок Task2; імплементації й нових inference немає.
