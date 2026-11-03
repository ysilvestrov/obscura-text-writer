# R-28i — Reasoning і пошук→суддя: погоджений дослід

Статус: автор27.10.2026 погодив локальне порівняння reasoning за якістю/часом і запропонував окремі пошук/суддю/код-посилання. Лише нейтральний spike, не production контракт. Робочі roles/settings/tokenizer bindings/запуски не змінюються; немає cloud/авторських матеріалів.

## Гіпотези

1. Фактично ввімкнений reasoning може зменшити false positives/пропуски, але подовжити виклики. Model catalogue дає лише on/off; не називати підтриманими low/medium без підтвердження. Для OpenAI-compatible probe effort=none є вимкненням, відсутній effort використовує advertised default=on. Перевірити reasoning_tokens або наявність окремого reasoning_content; HTTP200 сам по собі не є доказом.
2. Пошук формує гіпотези, суддя перевіряє їх за оригінальними уривками. Код призначає H1…Hn, перевіряє exact addresses і підставляє оригінальні уривки у посилання. Суддя не генерує offsets/адреси/літерали, не додає кандидатів, не пропускає/дублює ID. Порожній пошук на позитивному контролі — пропуск, а не доказ чистоти.
3. Та сама модель в окремих stateless викликах — окремі ролі, не незалежні джерела істини: помилки можуть корелювати. Друга роль не доводить валідність, а може емпірично поліпшити precision. Не перетворювати accept на твердження про гарантовану правильність.

## Схеми досліду

Однопрохідна оцінка: complete/findings/uncertainties. Пошук: complete/hypotheses/uncertainties; кандидат має change,target_refs,source_refs,problem,required_change. Суддя: decisions з candidate_id, decision accept/reject/uncertain, reason. Детермінований gate вимагає рівно один decision на кожен переданий candidate ID. Структурна валідація — окремо від людської перевірки змісту.

Для судді передаються ті самі original current rules/passages та явно недовірені hypotheses. Не давати gold labels, не називати findings підтвердженими, не показувати confidence пошуку. Усі references мусять бути реально переданими. Code links гарантують відповідність уривку за адресою, а не логічну достатність доказу.

## Фіксовані контролі та виміри

Чотири нейтральні випадки: правильний час зустрічі; старий час після перенесення; одне дозволене використання одноразового коду; два успішні використання одного назавжди одноразового коду. Expected labels не передаються моделі. У всіх порівнюваних гілках один і той самий оригінальний input без хибних model-generated child findings; це ізольована перевірка рішень, не повний DAG/пам’ять/production replay. Не порівнювати кількість успіхів напряму з попереднім R-28h, де input/schema були іншими.

План: capability smoke reasoning; свіжі paired off/on одиночні виклики, чергування порядку для зменшення warm-cache bias; search→judge без reasoning для розмежування ефектів. max_tokens4096, temperature0.1, context131072 незмінні. Для reasoning окремий completion limit охоплює думання та answer; length/empty/timeout не повторюються автоматично, є окремими результатами. Якщо reasoning не підтверджується, решта reasoning-гілки пропускається, не підміняється іншим параметром непомітно.

Записати actual wall time, input/output/reasoning tokens, finish reason, JSON/ref validity, false positives, false negatives та abstentions. Одна проба на контроль/гілку — не оцінка статистичної надійності; чотири прості випадки не кваліфікують модель для книги. Judge може виконуватись лише для наявних гіпотез; вартість двопрохідного режиму — фактична сума обох викликів, не обов’язково рівно2×. Довгий вхід книги не екстраполювати з цих коротких даних.

Production SPEC.MD лишається чинною; для інтеграції потрібне окреме рішення після результатів. Жодного автоматичного очищення dirty чи застосування правок як наслідку spike.


## Зміна обсягу за результатом capability-контролю

Реальний default-on контроль (той самий нейтральний R-28h clean input/schema, limit4096) завершився за434,12с finish=length, input498, output4096, reasoning4096, content0. На цій конфігурації немає відповіді для оцінки змісту. Після цього решту4paired-on проб пропущено явно (`--skip-on`), щоб не повторювати завідомо дорогий невдалий шлях. Це не відсутність підтримки reasoning і не доказ його загальної неефективності. Нова керована межа reasoning або більший output потребуватиме окремого випробування; його не підміняти непідтвердженим low/medium.

Далі: один свіжий off-контроль того самого capability body з єдиною зміною effort=none;4fresh single-off +4search-off та judge-off лише за наявних hypotheses. Прямі fresh single-off/search/judge arms мають однакові originals/output4096; capability має іншу response schema й не підмішується до їхньої метрики точності.


## Результат

[Звіт](../../research/2026-10-27-r28i-reasoning-and-judge.md):18local calls. Default reasoning434,12с/4096reasoning/length/no answer проти fresh off23,78с/225output/stop, але off мав false positive у старій GroundedCheck формі. Fresh simpler Single4контролі класифіковані правильно за46,98с, без гарантії пояснень/редактури. Search→judge198,02с/4,21×, judge v1 всі uncertain; уточненийv2 прийняв усі4, включно з2false hypotheses. Саме зниження невизначеності не є покращенням істинності. Поки не інтегрувати; потрібні атомарні hypotheses, достатні code-resolved evidence, обмеження anchoring, scoped uncertainty та незалежні holdout/repeat контроли.
