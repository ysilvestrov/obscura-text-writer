# Локальні моделі для структурованої перевірки впливу —26.10.2026

## Результат

Рекомендований кандидат для наступної інтеграції — **huihui-qwen3.5-9b-abliterated**, GGUF Q4_K_M. Встановлено в Bionic/LM Studio, завантажено з32768контексту, eval batch512, Flash Attention/KV GPU. На NVIDIA RTX5070Laptop8GB (nvidia-smi8151MiB) виміряно пік6332MiB≈6.18GiB. Це реальна локальна проба, не припущення за розміром ваг.

**Штатна інтеграція ще не зроблена:** planner оповідання поки залишається Dolphin. У застосунку немає окремого local reasoning_effort=none; універсальна JSON Schema не обмежує metadata конкретними ID/доказами. Ці зміни потребують окремої специфікації з сумісністю історичних proof. Для дослідження API bodies формувались окремо; жоден результат не прийнято як авторський текст, пам’ять чи assessment.

Контрольний профіль: native response_format=json_schema; temperature0.1; max_tokens4096; reasoning_effort=none; loaded context32768. Остання окрема проба з task-bound covered_ids і exact evidence choices завершилася stop за31.38с, prompt12078/output1303, JSON2305символів. Повний validate_part пройшов, coverage10/10, evidence4. Verdict uncertain: це НЕ підтвердження узгодженості сцени/якості аналізу, повний book workflow не запускався. Вхід — та сама перша невдала локальна частина, авторські дані лишалися на loopback.

## Порівняння

| Модель/режим | Пік GPU | Час контрольної частини | Результат |
|---|---:|---:|---|
| Dolphin2.9.3Nemo12B Q3_K_M, prompt_json | — | оригінальна невдала спроба | response_format не надсилався; stop, але не JSON |
| Dolphin native JSON Schema | — |126.60с| JSON/PartResult shape/coverage коректні; повний валідатор відхилив no_impact разом із findings |
| Huihui Qwen3.5-4B Q5_K_M, generic schema, thinking off |4444MiB|17.91с| JSON коректний, цитати exact, але замість source_id повернув document_id |
| Та сама4B +уточнення адрес |—|19.06с| Повний валідатор не пройшов |
| Та сама4B +allowed-ID enum |—|22.19с| ID вже допустимі, цитати неточні; повний валідатор не пройшов |
| Huihui Qwen3.5-9B Q4_K_M, thinking off/output2048 |6332MiB|44.15с| length, JSON незавершений |
| Та сама9B, default thinking/output8192 |—|155.80с|7402reasoning tokens; length, фінальний JSON незавершений |
| Та сама9B, thinking off/output4096 |6332MiB|54.98с| JSON коректний, coverage неповне |
| Та сама9B +bound IDs/output4096 |6332MiB|35.45с| JSON коректний, але цитати неточні |
| Та сама9B +код задає coverage і дозволені exact evidence |не перемірювався окремо; та сама loaded32K instance|31.38с| Повний валідатор PASS, uncertain; не літературна атестація |

Малий нейтральний JSON probe Dolphin пройшов за4.03с. Qwen4B із chat_template_kwargs.enable_thinking=false все одно витратив128токенів на reasoning без content: цей параметр поточний Bionic OpenAI endpoint не застосував. Документований native /api/v1/chat reasoning=off дав0reasoning; OpenAI-сумісний reasoning_effort=none теж дав0reasoning і валідний маленький JSON за2.68с. Це фактична перевірка поточного runtime, не універсальна гарантія інших серверів.

## Важливі висновки

- JSON Schema забезпечує форму лише завершеної відповіді; вона не гарантує правильних адрес, цитат чи змістових висновків, якщо значення не обмежені.
- У старому профілі Dolphin context_tokens128000 не відповідав реально завантаженим16384. Project context має узгоджуватися з model load config.
- Значна частина помилок виникла на відтворенні64-символьних hash ID та дослівних цитат. Пошук більшої моделі сам цю проблему не гарантує вирішити. Прототип задає known coverage як const та Evidence як oneOf допустимих source_id/quote; модель обирає докази, код не ремонтує довільні або fuzzy цитати.
- Allowed quote candidates у прототипі — точні відрізки речень/рядків до160символів, max4evidence. Це лише дослідницький режим однієї delta-частини, не новий виробничий контракт. Check/synthesis/recovery/історичні proof та вартість такої схеми потребують окремого дизайну/тестів.
- Моделі завантажено в каталог LM Studio під mradermacher; файли моделей не входять у Git. Бюджетних cloud API, надсилання авторського тексту назовні, змін heads/пам’яті/role settings не було. GPU наприкінці зайнятий новою9B, попередні моделі залишились на диску.

## Походження та відтворення

- [Базова Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B): режими reasoning та native context не тотожні доступному VRAM.
- [Huihui4B model card](https://huggingface.co/huihui-ai/Huihui-Qwen3.5-4B-abliterated), [Q5_K_M quant](https://huggingface.co/mradermacher/Huihui-Qwen3.5-4B-abliterated-GGUF).
- [Huihui9B model card](https://huggingface.co/huihui-ai/Huihui-Qwen3.5-9B-abliterated), [Q4_K_M quant](https://huggingface.co/mradermacher/Huihui-Qwen3.5-9B-abliterated-GGUF). Автор позиціонує їх як uncensored; це не гарантія відсутності будь-якої відмови й не окрема атестація на всіх дорослих матеріалах.
- [LM Studio structured output](https://lmstudio.ai/docs/developer/openai-compat/structured-output): grammar-based JSON для GGUF, завершення/ліміти важливі.
- [Load API](https://lmstudio.ai/docs/developer/rest/load), [Chat reasoning](https://lmstudio.ai/docs/developer/rest/chat).

Метрики без художнього тексту збережено в ignored artifacts/*-probe.json; raw responses там приватні, не для публічної документації. Контрольні проби — без модифікації production SPEC/runtime contract; pytest не перезапускався, оскільки код не змінювався. check_docs перевіряє лише документацію.

SHA256 завантажених GGUF, перевірені після download:

- 4B Q5_K_M: a93fe75df87619da6f28bef8faf895799a8bbda238c29bc0dbb40ae418054ad4 (3108758848bytes).
- 9B Q4_K_M: ea1858ef4dc4b648b8dbb44612962a0333e945060dd0545ac0f28d7c4416e4b3 (5627045248bytes).

## Інтеграційні виміри R-28c

Після погодження реалізовано versioned reference wire: модель обирає E IDs, код розкриває exact quotes; попередній literal прототип лишається дослідницьким. Нейтральний smoke нового контракту:5,09с/859input/155output/0reasoning, stop і повний validatorPASS (uncertain).

На фактичній книзі32K з консервативними оцінками перевищив10000parts. Перевірено ту саму9B з context131072:7752MiB idle,7762MiB peak (7,58GiB із7,96GiB доступних). Preview557calls/56,22с; один реальний delta за154,3с,13590input/148output/0reasoning,4exact evidence, stop/PASS. Delta no_impact означає опрацювання пакета, не висновок щодо сцени. Повний book run не запускався, звіти не публікувались, cloudcalls0. Власник погодив128K та подальше скорочення числа викликів. Малий запас VRAM і тривалий prefill лишаються практичними обмеженнями.
