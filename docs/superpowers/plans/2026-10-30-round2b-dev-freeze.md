# Раунд 2b: dev та підготовка freeze — план виконання

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Перевірити transport/schema/content на старому dev, не торкаючись нового holdout викликами, і підготувати відтворюваний freeze для окремо дозволеного quality.

**Architecture:** Новий research-адаптер повторно використовує незмінні protocol3 request/transport/validator/ledger helpers раунду2. Нові manifests та slots живуть окремо; старі frozen inventory не послаблюються. Адаптер не імпортує holdout до dev-викликів.

**Tech Stack:** Python, pytest, наявні native Google/Anthropic transports, Bionic local API, read-only preflight та durable SQLite ledger для платних викликів.

**Spec:** [план2b](../../research/2026-10-29-round-2b-holdout-rebuild-plan.md), §§4–7, [бріф2b](../../research/2026-10-29-round-2b-codex-brief.md), [план раунду2](../../research/2026-10-28-local-planner-round-2-plan.md), [підсумок oracle](../../research/round2b/oracle-comparison-revision4.json).

## Стан перед реалізацією

Oracle завершено:48/48класи,28/28авторськіфакти явно відображені; відкритих розбіжностей0. Набір після повторних виправлень не є новим незалежним blind-дослідом. Канонічні вичитані дані: `docs/research/round2b/holdout-reviewed.json`; dataset/harness ще **не frozen**. Наявний `round2b/dev.py` виконує іншу, вже завершену A′ tuning-ітерацію44×5 — не запускати її замість нового qualification-dev.

## Global Constraints

- Новий holdout не застосовувати для prompt/schema tuning, dev, ремонту або підбору моделей.
- Учасники: L3 Gemma3-12B ownQ4_K_M, L5 HuihuiQwen3.5-4B Q5_K_M, L6 Gemma4-E4B Q4_K_M, C1 `gemini-3.5-flash-lite`, C2 `claude-haiku-5-5`; K1/K2 без inference. L1/L2/L4 виключені за погодженим результатом спайку.
- A′ v1 SHA `55fe4d840642b93c69d01d1b2a4d5d421282b99e51bf6ac054d27028593a9088`; native protocol3/schema `concerns.maxItems=3`, result cap4096символів, temperature0.1, output4096токенів. Звірити ці значення з actual wire, не покладатися на назви налаштувань.
- Local reasoning off з actual telemetry0; профілі/GGUF/template — з успішних A′dev/primary для відповідної моделі. L3 має32K, L5/L6 —128K. MTPoff для цих трьох; нових MTP-експериментів немає. Відхилення load/config — STOP, не мовчазна оптимізація.
- Cloud thinking/default та C2 schema-relaxation лишаються як у погодженому раунді2/A′dev. Для C2 native schema не має maxLength/maxItems, але ті самі межі залишаються в інструкції й незмінному локальному валідаторі. Не змінювати schema за підсумками holdout.
- Загальний cloud ліміт $10 незмінний. Read-only звірка30.10: charged$0.1652627, held$0, available$9.8347373. Перед кожною новою серією перевірити ledger continuity, актуальні підтверджені тарифи й повний резерв; не скидати ledger. Консервативна стеля dev —16платнихвикликів×$0.05=$0.80, придатна лише якщо кожний actual wire відповідає перевіреним межам старого dev-reserve. Якщо тариф/вхід перевищує цю оцінку — STOP до нового розрахунку, без HTTP.
- Invalid/length/complete=false/refusal — результати без ремонту й повторів. Підтверджений транспортний збій відрізняти від невизначеного платного виклику: останній не повторювати автоматично. Продовження решти dev-прикладів не стирає помилок.
- Старі `round2/*.py`, frozen-primary, результати, продуктовий код/SPEC, модельні секрети й старий план2b не змінювати. Ключі/seed/raw не друкувати.

## Review Focus

- Зміна corpus/prompt/config після preflight зупиняє відправлення до API.
- Dev IDs відокремлені від нового holdout; вичитаний набір не може потрапити у dev через спільний loader.
- Resume не дублює змістові чи невизначені платні виклики й не обнуляє бюджет.
- Formal valid не підміняє content-аудит чотирьох dev-clean; invalid L6 показано окремо.
- Відсутня/зайнята local GPU або невідповідний native-профіль зупиняє local dispatch, не змінюючи продуктових ролей.

### Task 1: Окремий qualification harness і offline gates

**Files:** Create `docs/research/round2b/qualification.py`, `docs/research/round2b/test_qualification.py`, CLI `docs/research/r28o-round2b-qualification.py`. Read-only consume `round2.dev.old_cases`, `round2.requests`, `round2.transports`, `round2.runner`, `round2.freeze`, `round2.cloud`, попередні native load-профілі та `oracle-comparison-revision4.json`.

**Interfaces:** `prepare(root: Path, folder: Path) -> dict` без inference; `verify(manifest: dict) -> None` fail-closed; `run(manifest: dict, *, authorized: bool) -> dict`; дані й model settings передаються як окремі підписані snapshot, не підміняються глобальним старим manifest.

- [x] Написати synthetic тести: тільки8старихdev(4clean/4issue)×5моделей=40slots; new holdout loader не викликається; authorization до side effects; tamperedwire/config/inventory блокуються; shared ledger anchor не скидається; uncertain paid resume не дублюється; invalid зберігаються.
- [x] Запустити їх, зафіксувати RED; реалізувати мінімальний адаптер без змін frozen helpers; отримати GREEN.
- [x] Записати actual prompt/schema/wire/config/GGUF/load/source hashes у новий manifest та усі відхилення cloud schema. Нові code inventory не змінюють старі snapshot.
- [x] Перевірити вихідні передумови:48reviewedданих, завершенийoracle, hashes та повнота; підготувати dry-run таблицю40слотів і верхнійcloudрезерв до HTTP.
- [x] Виконати незалежне code-only review і цільові offline-тести через `scripts/verify.py`; дані holdout до reviewer не надсилати.
- [x] Коміт коду/умов до inference. Research інструкції оновити; пояснити відсутність змін продуктових UA/EN інструкцій/SPEC.

### Task 2: Qualification-dev — 40 нових викликів

**Files:** artifacts окремо `artifacts/round-2b/qualification/`, новий звіт `docs/research/2026-10-30-round2b-qualification-report.md`. Не писати у completed A′dev папку.

**Interfaces:** Consume перевірений manifest Task1, produce raw requests/replies/slot hashes/usage та content mappings. Holdout не викликається.

- [ ] До dispatch підтвердити фактичний доступ до Bionic і тарифи/ledger; зберегти starting GPU state. Не завантажувати/витісняти сторонню модель без авторизації дослідницької GPU-сесії.
- [ ] Виконати24local і16cloud на старих8випадках з A′; одна спроба на змістовий результат. За transport/resource/невідомим reasoning state — STOP з точним діагнозом і durable checkpoint.
- [ ] Для кожної моделі прочитати зміст усіх4clean-відповідей; зауваження на≥3/4clean — STOP до рішення власника **також для негативного контролю L5**, без мовчазного виключення.
- [ ] Систематичні порушення JSON/контракту — окремий gate до holdout. Для прозорого обліку показати кожен invalid і лічильник; не оголошувати модель придатною лише через валідні відповіді. Межу систематичності зафіксувати до dispatch; якщо немає однозначної чинної домовленості — уточнити її у власника на основі сухого manifest.
- [ ] Перевірити actual reasoning0local, native profile таVRAM/offload; короткийL3>60с — окремий STOP за первинним бріфом, не мовчки прийнятий успіх.
- [ ] GPU привести до погодженого starting state; звести actual cost/held/available. Звіт і результати власнику, STOP до відповідей на спрацьовані gates.

### Task 3: Freeze-пакет, без автоматичного quality

**Files:** Create окремий `docs/research/round2b/frozen-quality.json` тільки після виконання gates Task2; майбутній quality adapter і його тести — окреме доповнення до цього плану, якщо їхній контракт не покривається чинним runner.

- [ ] Зафіксувати source commit, canonical corpus/gold/prompt/schema/wire hashes, GGUF hashes, actual native profiles, Bionic/backend/GPU-driver та power metadata; seed приватний, у публічних звітах лише fingerprint. Не оголошувати відсутні metadata відомими.
- [ ] Зберегти всі predeclared метрики й пороги: FP≤7/60, miss≤10/84, valid≥137/144 на модель; question-missed split описово; L6 invalid окремо. K1/K2 — константні baselines. Після виключення L1/L2/L4 негативнийконтрольL5 порівнюється з L3 за трьома погодженими показниками окремо, без довільної суми.
- [ ] План quality:48×3×5=720викликів (432local,288cloud), блокове чергування та записаний seed. Це **не дозволяє** запуск без окремо підготовленого/погодженого freeze і повного розрахунку резерву.
- [ ] Підготувати без викликів спільну blinded20%TPпанель/secondary-аудит за погодженими правилами: фактична генерація панелі лише після quality. Не міняти метрики після результатів.
- [ ] Timing, senior/escalation, reasoning experiments іB7 не запускати автоматично. Перед quality — підсумковий dry manifest, бюджет і явний перехід власника через gate.

## Поточна межа

Цей файл — конкретизація наступного етапу після закриття oracle, **не запис успішного dev/freeze й не дозвіл на автоматичний quality**. Стан виконання фіксувати в remediation-progress та дослідницькому звіті. На момент створення плану code Task1 ще не реалізовано, модельних викликів нового етапу0.

## Виконання Task1 — до inference

231offline research tests PASS (`artifacts/verification-jglvs3u1/result.json`),13новихqualificationтестів. Незалежний code-only reviewer не читав корпус і виявив локальний autoretry timeout; виправлено RED→GREEN. Fixtures тепер не читають старий holdout, лише8опублікованихround1dev. Старі frozen helpers не змінювалися. Bionic inventory read-only:12записів,0loaded. Owner увімкнув API й підтвердив вільнуGPU. Інтерпретація систематичності зафіксована до викликів:≥2/8invalid; виконати решту старогоdevбезремонту згідно з попереднім ownerрішенням, але holdout не запускати до розгляду gates.
