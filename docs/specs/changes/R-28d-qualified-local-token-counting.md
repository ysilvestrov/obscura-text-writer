# R-28d — Кваліфікований локальний підрахунок токенів

Статус: власник26.10.2026 погодив реалізацію та активацію після успішних qualification/tests. R-28c уже поставлено в7652f9d; локальний128K профіль планувальника активний. Цей документ не оголошує новий estimator активним.

## Проблема та результати вимірів

Один фактичний запит мав13590input tokens за Bionic, але62710 за чинною UTF-8 оцінкою. Офіційний tokenizer моделі й фактичний chat template дали13590, різниця0. Native LM Studio SDK tokenizer недоступний у цьому Bionic (websocket upgrade200); залежності встановлювалися лише в ignored artifacts. Tokenizer-файли отримані з офіційного huihui-ai репозиторію без надсилання авторських текстів назовні.

Поточний128K/4096/100000chars preview:557calls. Output8192 дав684, відкинуто. Виключення code-owned coverage із response cap дало533, не виправдовує окремої зміни proof contract. Ізольований tokenizer-aware preview з512-token safety reserve, UTF-8 worst-case unknown-child reserve та max_input_chars500000 дав142calls за75,92с:6delta/0delta synthesis/68check/34text synthesis/34memory synthesis. Повний manifest validator підтвердив source/target/journal interval coverage й proof DAG. Нових модельних викликів для цих порівнянь не було. Розбиття142 — вимір конкретного знімка, не обіцянка сталої кількості після правок.

## Обраний підхід

Вузький opt-in local counter для поточного9B + endpoint + frozen impact prompt + JSON Schema + reasoning_effort=none, текстові system/user без tools/images. Інші моделі/провайдери/етапи зберігають чинний estimator. Не замінюємо джерела модельними конспектами й не пропускаємо пам’ять.

Профіль реєструється окремою локальною CLI-командою адміністратора: копіює tokenizer.json і chat-template до data/local_tokenizers, обчислює SHA256, перевіряє відтворення контрольного API usage, зберігає кваліфікаційні метадані без текстів і ключів. Активація — лише явна. HTTP не приймає довільних шляхів файлової системи. Optional CPU dependency tokenizers; GPU-модель додатково не завантажується. Runtime не завантажує файлів з інтернету.

Профіль зв’язаний із model ID, нормалізованим loopback endpoint, tokenizer/template SHA, impact system-prompt hash, request shape і версією лічильника. Hash mismatch, missing dependency/file, невідомий формат, інша модель/prompt/reasoning — conservative fallback із поясненням. Це прив’язка до оголошеної конфігурації й перевірених артефактів: зовнішня підміна моделі сервером під тим самим ID лишається обмеженням, як і ручний context_tokens.

## Manifest і підрахунок

Новий manifest може фіксувати metadata counter snapshot; відсутність означає старий estimator. Default-none поле виключається зі старих manifest fingerprints. Task/API/proof hashes та wire1/wire2 відповідей збережені; SQL4 без міграції. Зникнення профілю не робить старі звіти нечинними: proof replay не залежить від наявності tokenizer. Перед новим dispatch conservative fallback може зупинити продовження, якщо запит уже не проходить бюджети.

Лічильник локально рендерить той самий chat template у sandbox і рахує tokens без повторного додавання special tokens. Для фактичного body — точний count +512. Для planning unknown-child текст не токенізується як сприятлива повторювана emoji: placeholder вилучається, а на child додається worst-case4*result_cap +1024token/metadata reserve. Фактичний запит повторно рахується перед dispatch. Raw/canonical output caps, exact citation gates, full coverage, CAS, stop/refusal/cancel/recovery не змінюються.

Після явної активації тільки planner.max_input_chars підвищується100000→500000; context131072/output4096/model/temp/thinking зберігаються. Великий символьний ліміт сам не дозволяє перевищити токенний бюджет. Можливість більшого prompt не гарантує швидшу генерацію або кращу якість; порівнюємо також сумарний input work, а повний book run автор запускає окремо.

## Постачання й перевірки

Окремий пакет: optional dependency + чистий counter/profile store/CLI + versioned manifest metadata + budget integration; SPEC/traceability і UA/EN guide. RED→GREEN: exact known counts, wrong hashes/shape/model fallback, unsafe template/path handling, unknown-child worst case, legacy manifest/proof replay, no cloud calls, full synthetic run і контроль active settings. Один фінальний review, відповідні тести/check_docs, нове safe-state перед restart, без автоматичного book run.

Початкову кваліфікацію робимо на збереженому actual request/usage та нейтральних контрольних прикладах; матеріали залишаються локально. Перед активацією показуємо підтверджені результати. Локальна JSON/counter валідність не є підтвердженням літературної якості.

Реалізаційні уточнення: профіль також фіксує версії бібліотек; backend вимикає serialized truncation/padding; dispatch повторно хешує файли незалежно від timestamps. Process-version cache не послаблює file recheck. Нових продуктових опцій не додано.

Інтегрований native helper підтвердив142calls/full coverage. Первинний preview159,56с/142,28с перевищував UI120с; process-version cache та manifest-local verified handle (без серіалізації, з повною повторною перевіркою перед dispatch) зменшили його до94,44с. Pinned counter не читає empirical-profile DB на кожному probe. Planned input work за однаковим counter:13454769→4847029tokens, maxima39806/112852; це upper planning work із reserves, не actual usage чи latency guarantee. Production activation очікує повного regressionPASS.

## Фінальна поставка26.10.2026

Повний стабільний verify4z4awaet:1228PASS/1skip/0fail/errors/source_changed=false. Незалежне рев’ю:1critical truncation finding RED→GREEN; інших actionable findings немає. OptionalCLI встановлено й перевірено help. Кваліфікація CPU відтворила859/13590/24602input точно. Модельний25K контроль із output4096 завершився stop і правильним count, але canonical2782>cap2048; результат не публікувався. Тому в межах добору локальних параметрів підвищено тільки planner output8192 (старі output gates/formula збережені). Новий контроль: stop/повний validatorPASS/24602input164output/0reasoning/7762MiBpeak/295,47с.

За exactcounter output8192 повний coverage manifest має78calls (8delta/2delta synthesis/38check/15text synthesis/15memory synthesis), read-only preview94,97с. Активаціюprofile4737c351…bdbc4 виконано після tests/qualification;0active/schema4, exact server35808/44864→hidden45768. CAS story revision176→177 змінює лише planner.max_input_chars500000/output8192;інші ролі/промпти незмінні. Live previewHTTP200/ready78calls/91,19с, runs count незмінний. Full book run не запускався; cloudcalls0. Подальші документаційні підсумки не змінюють перевірений runtime код.
