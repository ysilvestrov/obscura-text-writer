# Раунд 2b: qualification-dev перед freeze

Дата: 30.10.2026. Статус: **40/40 завершено; STOP перед holdout через L3:systematic_invalid**. Новий holdout не викликався; dataset/harness quality ще не frozen.

## Умови до першого виклику

[План](../superpowers/plans/2026-10-30-round2b-dev-freeze.md), [публічний preflight](round2b/qualification-preflight.json), code commit `d2dd73e` до inference. Manifest SHA: `391085810b5598bdedac680245f674274c5f0f6f3cdbb4c272e3c747143157d3`. Повний manifest, exact source bytes, requests/replies і checkpoints: ignored `artifacts/round-2b/qualification/`. Це окремий прогін, не повтор tuning44×5.

8 опублікованих dev-прикладів раунду1,4clean/4issue × C1,C2,L3,L5,L6 =40викликів:24local,16cloud. Жоден із48нових holdout-прикладів у requests не входить. Prompt A′v1, SHA `55fe4d840642b93c69d01d1b2a4d5d421282b99e51bf6ac054d27028593a9088`; protocol3, current_consistency, temperature0.1, output4096токенів, result cap4096символів, concerns.maxItems3. Для C2 збережено явне native-schema відхилення раунду2, локальний валідатор не послаблено.

L3: Gemma3-12B ownQ4_K_M,32K; L5: HuihuiQwen3.5-4B Q5_K_M,128K; L6: Gemma4-E4B Q4_K_M,128K. GGUF перевірено за frozen SHA; native load-профілі всіх трьох дослівно збігаються зі збереженими primary/A′dev. Reasoning вимкнено, actual reasoning tokens/chars=0 у24/24localвідповідях. MTP-настроювання не змінювалися. C1 `gemini-3.5-flash-lite`, C2 `claude-haiku-5-5`, відповіді повернули очікувані model IDs.

До викликів:13нових synthetic qualification tests /231research tests PASS, незалежний code-only review без читання нового holdout. Виявлений autoretry локального timeout усунуто RED→GREEN. Старі frozen helpers не змінювали. Систематичність зафіксовано до dispatch:≥2/8invalid — gate перед holdout; за попереднім рішенням власника решта old dev завершується без ремонту/повторів. Timeout/refusal/невідомийreasoning/L3>60с — негайний STOP.

## Результати

Прочитано зміст усіх40відповідей виконавцем; нового модельного суддю не викликали. Визначення «знайдено» нижче вимагає valid `issue`, який справді називає очікуваний конфлікт. Непорожній список не є автоматично правильним результатом.

| Модель | Valid /8 | Invalid /8 | Refusal | Зауваження на clean /4, raw | Із них у valid | Правильні valid issue /4 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| C1 | 8 | 0 | 0 | 0 | 0 | 4 |
| C2 | 8 | 0 | 0 | 0 | 0 | 4 |
| L3 | 6 | 2 | 0 | 0 | 0 | 2 |
| L5 | 7 | 1 | 0 | 1 | 1 | 1 |
| L6 | 7 | 1 | 0 | 2 | 1 | 4 |

Разом36valid/4invalid/0refusal;40слотів,40спроб, автоматичних повторів0. Це малий старий dev, не результати якості на новому holdout і не доказ придатності моделей до продукту.

### L3: спрацював gate систематичних invalid

- `nude-issue`: `complete=false`, код `incomplete_processing`; текст правильно називає11:00проти14:00, але primary лишається invalid.
- `intimacy-issue`: `complete=false`, `incomplete_processing`; пояснення бачить конфлікт першого знайомства зі спільним медовим місяцем торік, проте concern має kind=`question` і пропонує обирати між передумовою та target. Це також змістова помилка категорії, її не слід зводити лише до технічного прапорця complete.
- Усі4clean без зауважень; letter/violence issue правильні й valid.

Частка invalid2/8=25% перетнула наперед записаний поріг. Ремонт complete, заміна question на issue, повтори чи підлаштування промпту не виконувалися. Невдалий dev не є мовчазним виключенням L3 зі складу учасників.

### L5: негативний контроль має змістові пропуски

На `letter-issue` та `intimacy-issue` повернуто valid порожній concerns — два змістові пропуски. `nude-issue` правильний valid. На `violence-clean` помилково поставлено issue: робота здоровою правою рукою не суперечить травмі лівої. `violence-issue` invalid із `duplicate_source_reference` і `missing_evidence`; target_refs порожні. Тексту недостатньо, щоб перетворити цю відповідь на valid.

L5 не досяг технічних порогів зупинки(1/8invalid,1/4cleanзауважень), але це не затвердження його змістової якості.

### L6: invalid і хибні зауваження показані окремо

Invalid **1/8=12.5%**: `nude-clean`, `missing_evidence`, source_refs порожні. При цьому повідомлення є хибним зауваженням: повторне погодження меж зйомки сумісне з попереднім погодженням; відсутність згадки повтору в S1 не доводить суперечність.

Другий clean-concern — valid `violence-clean`: модель сама пише, що суперечності немає, але вимагає підтвердження можливості діяти здоровою правою рукою. Це хибний issue. Тому raw-зауважень2/4, valid-хибних1/4, invalidclean1/4; ці числа не змішуються. Усі4issue знайдені правильно й valid. Пороги≥2invalid і≥3clean-concerns для L6 не спрацювали.

## Контракт, ресурси й витрати

- [Машинні результати й checkpoint SHA](round2b/qualification-results.json). Повторно виконано строгий валідатор на40збережених відповідях, перевірено identities та result hashes,40attempts, зв’язок16paidслотів із durable ledger.
- L3 short-call максимум31.515с, поріг60с не порушено. Це telemetry dev, не окремий контрольований timing-прохід. Пік VRAM не виміряно; його значення не вигадуємо. Native load-профілі й успішне виконання перевірені, фактичне розміщення в пам’яті не переоцінюємо як незалежний вимір піку.
- Перед стартом GPU був порожній за read-only native inventory; після трьох model sessions він знову порожній. Чужі моделі не витісняли, продуктові ролі не змінювали.
- До HTTP резерв C1$0.1147424+C2$0.0278072=**$0.1425496**, нижче погодженої стелі$0.80 і спільного ліміту$10. Тарифи — чинний короткостроковий frozen snapshot, не новий довільний ручний тариф.
- За usage та зафіксованими тарифами ця серія коштувала **$0.0058398**. Сукупно settled charged$0.1711025, held$0, доступно **$9.8288975** із$10. Це тарифний розрахунок, не банківська квитанція провайдерів.

## Рішення перед наступним етапом

Єдиний admission gate — **L3:systematic_invalid**. Пропозиція виконавця: залишити L3 в запланованому вимірюванні з незмінним A′/schema та чесно рахувати invalid, як у попередньому раунді. Так не відбиратимемо тільки успішні моделі за результатом dev. Це потребує явного рішення власника до holdout; альтернативне рішення — зупинити L3, з окремо записаною зміною складу та негативного контролю.

Freeze і720qualityвикликів не запускалися. Timing, senior/escalation іB7 також не запускалися. Після рішення щодо L3 наступний дозволений крок — підготувати freeze-пакет із фактичними умовами й перевірками; дозвіл на автоматичний quality цей звіт не створює.

## Наступне рішення власника: L3 допущено без ремонту

Власник залишив L3 у holdout2b з незмінними A-prime/schema, strictinvalid і secondary лише за закритим списком. Gate2/8 не стерто й не перетворено на успішну qualification; це явний author override для вимірювання. Очікуваний провал valid-порога черезcompletefalse зафіксований як прогноз до holdout. [Рішення](2026-10-30-round2b-freeze-admission.md), [input-freeze пакет і STOP](2026-10-30-round2b-freeze-report.md). Жодного нового model call.
