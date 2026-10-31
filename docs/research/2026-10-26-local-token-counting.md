# Локальний tokenizer: виміри26.10.2026

R-28c baseline7652f9d, local9B/131072/4096/json_schema/thinking off, оповідання перевірялося лише через read-only preflight. Runtime й активний профіль не змінені.

| Експеримент | Виклики | Результат |
|---|---:|---|
| UTF-8 conservative, maxchars100000 |557| Поточний живий preview |
| Резерв8192 |684| Гірше; не застосовано |
| Гіпотетично не рахувати derived coverage у cap |533| Лише4,3%; не застосовано |
| Tokenizer +512 та unknown-child worst-case, maxchars500000 |142| Повний manifest validatorPASS;75,92с; поки spike |

Для першого фактичного API body: сервер13590input, локальний tokenizer13590, чинна оцінка62710; count зайняв0,032с. Це контроль одного запиту, не атестація всіх форматів. Native SDK tokenize через ws://localhost:1235/llm недоступний (HTTP200 замість upgrade); inference не викликався.

Завантажені локальноTokenizer.json12807982bytes SHA2565f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42; tokenizer_config.json16710bytes SHA256316230d6a809701f4db5ea8f8fc862bc3a6f3229c937c174e674ff3ca0a64ac8. Вихідний репозиторій [huihui-ai/Huihui-Qwen3.5-9B-abliterated](https://huggingface.co/huihui-ai/Huihui-Qwen3.5-9B-abliterated); правила [LM Studio tokenization](https://beta.lmstudio.ai/docs/python/tokenization). Tokenizer CPU-бібліотека та SDK ізольовані в ignored artifacts; не додані до runtime requirements. Авторські тексти не надсилалися назовні, платні API0, нові book runs0.

Наступний контракт запропоновано в docs/specs/changes/R-28d-qualified-local-token-counting.md. Потрібні profile/hash/shape admission, explicit activation, fallback, frozen manifest metadata і реальні regression tests до production.

## Реалізація та кваліфікація R-28d

Власник погодив реалізацію й активацію після успішних qualification/tests. Збережені API controls859/13590 відтворені обидва точно; нових modelcalls0. Профіль поки лише в artifacts, model/tokenizer/template/system/runtime-version binding. Native helper також142calls/full DAG/interval coverage. Preview до кешування159,56с, потім142,28с; manifest-scoped validated handle та відсутність empirical DB probe знизили до94,44с. Actual dispatch повністю перевіряє hashes знову.

Порівняння однаковим counter (known+512+worst-case unknown children):557tasks — planned13454769input/max39806;142tasks —4847029/max112852. Зменшення planned input work близько64%, calls74,5%. Це не фактичний billing usage і не лінійний прогноз часу. Full book inference не запускався.

Незалежне рев’ю знайшло serialized truncation: backend міг рахувати10замість10001. RED відтворено й усунено через no_truncation/no_padding перед qualification/runtime; hashfile лишається незмінним. Final suite і production activation ще виконуються.

## Перевірена конфігурація8192

Actual local25K: input24602==counter24602/0reasoning/GPUpeak7762MiB. Output4096 давав canonical2782приcap2048, тому жодного звіту не публікували. Output reserve8192 піднімає cap4096 за незмінною формулою. Контроль нового профілю: stop/повний validatorPASS, input24602/output164/reasoning0,6exact evidence,295,47с. Це delta-частина, не висновок про узгодженість усього твору.

Counter-aware8192 preview:78calls/94,97с/fullcoverage. Live після qualification/tests/restart/activation:78calls/91,19с/HTTP200, жодного нового run. Baseline557→78 — приблизно86% менше викликів. Частини мають більше input, тому зменшення latency не обіцяється пропорційним. На бібліотекахtokenizers0.23.3/Jinja2 3.1.6 профіль4737c351…bdbc4 активний, model9B/context131072/maxchars500000/output8192.
