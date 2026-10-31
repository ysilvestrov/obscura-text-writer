# Раунд 2b: freeze-пакет входів і контрактів — STOP

Дата: 30.10.2026. [Рішення власника щодо L3](2026-10-30-round2b-freeze-admission.md) записане до holdout. **Генерацій у цьому етапі — 0. Quality не активовано.**

## Пакет

- [Frozen snapshot](round2b/frozen-quality.json): SHA `ce1b4068175e470d3671c93bf1c23c7d568643992638306b0ec6cbe8734f291d`.
- [Аудит пакета](round2b/freeze-audit.json), джерельний коміт `5268a2a`.
- 363 файли у snapshot: код, ресурси, вичитаний набір/gold, oracle й dev-докази, нормативні рішення, збережені запити та приватні schedule/seed файли за SHA. Ваги й зовнішні backend-бінарні файли перевіряються окремими SHA/розмірами з metadata.
- 240 унікальних prebuilt native-запитів (48 × 5), відтворюваний розклад **720 слотів** (48 × 3 × 5):432local,288cloud. Кожна трійка модель/приклад/прогін унікальна, джерела не обрізалися. Перебудова всіх native-контрактів дала точний збіг.
- Повні матеріали й точні байти source-snapshot — ignored `artifacts/round-2b/quality/`. Seeds виконання, спільної TP-панелі й blind aliases окремі та приватні; у публічному пакеті лише SHA. Незакомічене власницьке доповнення плану збережено в приватному source archive без внесення сторонніх правок у Git; source commit сам по собі не замінює byte snapshot.

Усі запити зберегли A′v1 SHA `55fe4d840642b93c69d01d1b2a4d5d421282b99e51bf6ac054d27028593a9088`, temperature0.1, output4096токенів, result cap4096символів і concerns.maxItems3 у первинній схемі. Відоме C2-відхилення native schema і додані текстові обмеження збережені по кожному wire; нового послаблення немає. Вичитаний набір не використовували для додаткового prompt tuning.

## L3, primary та secondary

L3 залишається попри dev-gate2/8invalid. До freeze внесено **очікування власника**, що вона не пройде primary valid≥137/144 через complete=false. Це не результат ще не виконаного holdout і не зміна порога.

Primary: всі invalid у знаменнику, без ремонту й повторів змістових відповідей; FP≤7/60, miss≤10/84, valid≥137/144 однакові для учасників. Invalid L6 показується окремо. K1/K2 лишаються константними baseline без inference: always-issue дає60FP, always-clean84пропущені факти, тож обидві бази провалюють пороги. Порівняння негативного контролю L5 — з L3 за FP/miss/validity окремо, без довільної суми та без підмішування secondary.

Secondary: закритий список лише incomplete_processing і duplicate_source_reference (source_refs), їхня комбінація дозволена за проходження всіх інших перевірок. Дублі інших refs, missing evidence, unknown refs, JSON/length/refusal не нормалізуються. Лише описово, поза порогами й primary-порівняннями. Власник перевіряє всі secondary-кандидати, не тільки ті, що виконавець вважає правильними.

Помилка kind на однозначному issue — змістова. Тест прямо перевіряє: complete=false + question на issue може бути secondary-кандидатом, але дає FN і зберігає question; правильні слова в повідомленні не виправляють категорію. Це зафіксовано і в metadata, і в regression test.

## Бюджет і середовище

| Показник | USD |
| --- | ---: |
| Майбутній резерв C1,144виклики | 2.1047040 |
| Майбутній резерв C2,144виклики | 0.5136432 |
| Повний резерв quality, одна спроба | **2.6183472** |
| Доступно у спільному ліміті$10 | **9.8288975** |
| Невизначені резерви ledger | 0 |

Це верхня оцінка за чинним frozen тарифом, UTF8 wire bytes +8192input margin і4096output, не очікуваний рахунок. Нових ledger reservations/платежів немає: settled total лишився$0.1711025, held0. Пакувальник не створює API-клієнта; ledger відкрито read-only. Перед майбутнім dispatch потрібні повторна перевірка тарифів/бюджету та явна активація.

Point observation: Bionic.exe1.1.8.0, RTX5070Laptop8151MiB, драйвер582.05, ACOnline, WindowsBalanced. Три встановлені CUDA12backend2.66.0 DLL мають ті самі SHA, що й історичний runtime. **Поточний вибір backend у GUI не підтверджений**, source commit backend невідомий. Це не прирівнюється до доведеної поточної активної версії. Qualifying native load-профілі збережені та перевірені, їх не змінювали. Пік VRAM/температуру/живлення безперервно не вимірювали, timing не запускали.

## Перевірки та готовність

243offline research tests PASS (`artifacts/verification-zof9qsgy/result.json`), включно з12новими freeze-тестами. Незалежний code-only reviewer не читав holdout/seed. Дві важливі знахідки — довіра до stale dev-summary і відсутність повторної ledger-перевірки — виправлені RED→GREEN: gates перераховуються з40перевірених відповідей, ledger continuity та доступний резерв перевіряються при verify. Попередній широкий запуск мав240PASS/1WindowsWinError5 в незміненому synthetic resume-тесті; наступний повний запуск пройшов, workaround до frozen helpers не додавали.

Пакет успішно перевірено: source/file/GGUF/backend/package hashes,40devcheckpoints,16paidledgerзв’язків,240nativewires,720унікальнихслотів і відтворення schedule з приватного seed, відсутність числових seeds у публічному JSON, повний приватний byte archive.

**Готовність:** inputs_frozen=true, activated=false, quality_authorized=false, execution_harness_complete=false. Наявний legacy `round2.experiment.frozen_send` використовує A та output-папку round2. Окремого виконуваного адаптера A′/round2b ще немає. Він і його guard/review потребуватимуть оновленого execution freeze **до першого holdout-виклику**, а не мовчазної зміни цього snapshot. Цей пакет фіксує матеріали та контракти для такого наступного кроку й не є твердженням про готовність запуску.

За прямою вказівкою власника — **STOP**. Holdout, quality, timing, senior/escalation іB7 не запускалися. Продуктові API/схема/SPEC.MD не змінювалися; оновлено дослідницькі інструкції, зміни продуктових UA/EN інструкцій не потрібні.
