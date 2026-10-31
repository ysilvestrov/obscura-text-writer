# Holdout 2b — етап сліпої перевірки

Поточний стан: **L3 допущено власником; offline input-freeze пакет створено. STOP. Quality не активований.**

- [Сліпа панель](oracle-blind.md): позначте один `clean / issue / question` у кожному прикладі. Для `issue` потрібна цитата й пояснення; незалежні суперечності перелічіть окремо. Для `question` поясніть, яке рішення бракує.
- У редакції 4 заповнюйте лише **«Повторно оцінити» — №13, 15, 25, 40**. Інші 44 приклади нижче збережені з попередніми відповідями. Номери незмінні. [Завершена розмітка редакції 2](oracle-blind-v2-annotated.md), [перша розмітка](oracle-blind-v1-annotated.md), [історія попередніх виправлень](../2026-10-30-round-2b-oracle-revision2.md).
- [Manifest](manifest.json) фіксує автора `gpt-6.1-sol` за підтвердженням власника, SHA промпту, даних, панелі, приватного ключа й генератора. Oracle завершено; dataset/harness freeze очікує dev.
- [Рішення й виконання етапу 3](../2026-10-30-round-2b-stage3-execution.md). Власник затвердив A′ v1 попри технічний тригер L6; primary invalid не ремонтуються. A′ змінює правило суперечливого канону **і** загальну область `issue`.

## Приватні дані до завершення oracle

`oracle-key.json` та `holdout-draft.json` лежать поруч із панеллю, але виключені з Git, щоб не показати авторський gold до незалежної розмітки. Вихідні 12 шаблонів зберігаються локально в `artifacts/round-2b/holdout-authoring/templates.json`. Не відкривайте ключ до завершення розмітки. Публічні SHA фіксують ці файли до розмітки; після неї їх можна буде додати до дослідницького snapshot окремим етапом. Після закриття oracle канонічний `holdout-reviewed.json` з gold додано до Git; приватний ключ потрібен для історичного перемішування, а не для відтворення текстів та розмітки набору.

## Перевірки без inference

За `PYTHONPATH=src;docs/research`:

```powershell
.venv/Scripts/python.exe -m round2b.author_holdout --self-check
.venv/Scripts/python.exe scripts/verify.py docs/research/round2b/test_author_holdout.py -q
```

Self-check перевіряє початковий snapshot **до авторської розмітки**. Після проставлення галочок SHA панелі закономірно зміниться; не регенеруйте її. Звіряння розмітки з ключем та аналіз розбіжностей ще не реалізовані цим етапом. Генератор відмовляється перезаписувати наявні виходи. Для іншого набору потрібен новий окремий каталог/цикл, а не видалення результатів oracle.

Механічні перевірки не доводять вивідність gold або літературну якість. На новому наборі не виконано жодного виклику моделі; платні виклики, GPU-профілі та дослідницький budget ledger не змінювалися. Рев’ю коду бачило лише механізм і штучні unit-fixtures.

## Звіряння з gold

За окремим дорученням власника виконано [офлайн-звіряння всіх 48 рішень](../2026-10-30-round-2b-oracle-comparison.md):45збігів класу, розбіжності №13,15,16. [Пофактовий результат](oracle-comparison-revision3.json). Авторські класи й оцінки власника незмінні, model calls0. Набір не frozen; інструкція переглянути чотири приклади вище описує завершений попередній крок. Наступні зміни/повторний перегляд лише після рішення щодо відкритих розбіжностей.

### Уточнення власника після звіряння

№16: власник підтвердив випадкову clean-позначку, замінено на issue з окремим provenance-записом. [Сира розмітка редакції3 збережена](oracle-blind-v3-annotated.md). Для чобіт тепер явно встановлено повністю шкіряний чорний верх включно з халявами; змінено спільну передумову всіх чотирьох відповідних прикладів. Авторський gold і target незмінні. Перегляд лише першого розділу, оцінки решти44збережені з явною owner-корекцією16. Попередній звіт порівняння є історією до цієї корекції; повторного зіставлення редакції4 ще немає.

## Oracle завершено

Редакція4 повністю розмічена; повторно заповнювати панель не потрібно. [Остаточний snapshot](oracle-blind-v4-annotated.md), [підсумкове зіставлення](oracle-comparison-revision4.json), [вичитаний набір із gold](holdout-reviewed.json). Після завершення власницької розмітки заборона відкривати gold більше не потрібна; seed лишається приватним. Канонічні дані тепер доступні з Git, але quality-harness і набір ще не frozen. Старий self-check перевіряє початкову панель до галочок, тому очікувану зміну SHA розмітки не приховували; завершення засвідчує окремий completion JSON. [Наступний план](../../superpowers/plans/2026-10-30-round2b-dev-freeze.md).

## Qualification-dev harness

Новий CLI `docs/research/r28o-round2b-qualification.py prepare` готує40слотів лише зі старих8dev-прикладів; `run --authorized-dev` виконує24localта16cloud у окремій папці `artifacts/round-2b/qualification/`. Це не44×5 tuning-ітерація. Manifest/hash/ledger drift зупиняють dispatch. Timeout не повторюється автоматично ні local, ні cloud. Invalid лишаються результатами без ремонту, ≥2/8invalid або ≥3/4dev-clean із зауваженнями — gate до holdout. Refusal/reasoningневідомийчи>0/L3короткийвиклик>60с зупиняють dev негайно. Після gate потрібне рішення власника, quality ніколи не стартує цим CLI. Профілі моделей та продуктові ролі не змінюються.

### Qualification-dev завершено

[Звіт](../2026-10-30-round2b-qualification-report.md), [строгі результати та checkpoint SHA](qualification-results.json), [змістовий перегляд усіх40відповідей](qualification-content-review.json).36valid/4invalid/0refusal,безповторів. L3має2/8invalid; допускдоholdout потребуєрішеннявласника. Фактичнацінасеріїзаusage$0.0058398,залишок$9.8288975,held0. Новийholdout/freeze/quality/timing/seniorне запускали.

### Допуск L3 і offline freeze-пакет

[Власник залишив L3](../2026-10-30-round2b-freeze-admission.md) з незмінними A′/schema. Invalid лишаються primary invalid, secondary описова й поза порогами. Лише complete=false і дубль source_refs за решти валідного контракту; kind=question на однозначному issue не виправляється.

CLI `docs/research/r28p-round2b-freeze.py prepare --owner-l3-admission --environment PATH` створює offline пакет вхідних даних і native-запитів; `verify` перевіряє snapshot, інвентар коду, зовнішні ваги/бінарні файли, версії Python-залежностей і ledger. Обидві дії не створюють API-клієнта й не запускають модель. Наявні пакети та приватні seeds не перезаписуються.

Це **input freeze**, без активації quality; execution-harness ще не оголошений завершеним. Перед першим holdout-викликом потрібні адаптер A′/round2b замість legacy A/round2, його рев’ю та оновлений execution freeze. Після створення пакета — STOP за прямою вказівкою власника.

### Freeze-пакет створено — STOP

[Звіт і межі готовності](../2026-10-30-round2b-freeze-report.md), [snapshot](frozen-quality.json), [аудит](freeze-audit.json). Зафіксовано240nativeконтрактів і720слотів; резерв$2.6183472,доступно$9.8288975. Ніяких нових генерацій/витрат. Це input freeze, не активований execution freeze: окремий A-prime/round2b dispatch-адаптер ще не реалізовано, legacyA-runner не підходить. Перед запуском потрібні його реалізація/рев’ю, оновлений execution freeze й підтвердження backend/бюджету. До нового доручення зупинено.

### Execution freeze завершено — STOP

[Адаптер, перевірки й окремий execution freeze](../2026-10-30-round2b-execution-report.md): 240 frozen wire, 720/720 offline byte matches, 264 passed; Bionic echo L3/L5/L6 підтверджено load-only. Quality не активовано. Попередні описи незавершеного harness вище є історичними. `r28q-round2b-execution.py verify` перевіряє новий execution snapshot; старий input-only verifier після додавання execution source inventory не застосовується напряму.

### Quality завершено — STOP для рев’ю

[Звіт 2b](../2026-10-30-round2b-quality-report.md): 720/720, 598 strict valid / 122 invalid, без транспортних повторів. Змістові результати provisional до [сліпої панелі](quality-owner-blind.md): 17 спільних TP-позицій × 5 моделей і всі 27 secondary-кандидатів. Поставте одну галочку на відповідь; для невалідної додайте пояснення. Quality cost $0.1372275, спільний залишок $9.6916700. Timing, escalation, B7 не запускалися. Не перезапускати worker чи змінювати frozen harness.
