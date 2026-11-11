# Локальний аналіз впливу / Local impact analysis

## Українська

Для перевіреного Bionic-профілю на 8 GB GPU завантажте **Huihui-Qwen3.5-9B-abliterated Q4_K_M** із контекстом **131072**. У контрольному вимірюванні GPU займала 7762 MiB (7,58 GiB) під час контрольного виклику при128K; початковий профіль32K займав6332 MiB (6,18 GiB); інші програми та конфігурація KV cache можуть змінити витрати пам’яті. Модель уже встановлена на цьому комп’ютері, завантаження у пам’ять виконує Bionic.

У налаштуваннях оповідання відкрийте **Моделі → Планувальник**. Вкажіть local endpoint `http://localhost:1235/v1`, model ID `huihui-qwen3.5-9b-abliterated`, контекст131072, резерв відповіді8192, температуру0,1, ліміт входу500000 символів і JSON Schema. У додаткових параметрах увімкніть **Вимкнути thinking (reasoning_effort=none)**. Збережіть лише цю роль. Цей параметр перевірено з поточним Bionic; він не гарантує підтримки всіма локальними серверами.

На сторінці «Редагування книги» (меню ☰ «Дії твору») спершу сформуйте попередній перегляд: новий локальний профіль покаже **Контракт JSON2**, кількість частин і зведень. Генерація почнеться лише після явного запуску. Попередній перегляд не викликає модель. Великі книги потребують багатьох локальних викликів: відсутність плати не усуває витрат часу. Контекст розраховується консервативно; збільшення символьного ліміту не збільшує фізичний контекст.

Модель повертає короткі посилання на точні докази. Код розкриває їх і звіряє з текстом; невідома цитата, неповна відповідь чи перевищення резерву зупинять етап зі збереженням успішних частин. Автоматичних повторів немає. `uncertain` означає потребу в рішенні автора; коректний JSON не доводить відсутність сюжетних суперечностей. Інші ролі можуть продовжувати працювати через Venice/OpenRouter.

## English

For the tested Bionic profile on an 8 GB GPU, load **Huihui-Qwen3.5-9B-abliterated Q4_K_M** with a **131072** context. The measured GPU peak was7762 MiB (7.58 GiB) during the128K control call; the initial32K profile used6332 MiB (6.18 GiB); other applications and KV-cache settings may change memory use. The model is already installed on this computer; Bionic loads it into memory.

Open **Settings → Models → Planner**. Select the local endpoint `http://localhost:1235/v1`, model ID `huihui-qwen3.5-9b-abliterated`, context131072, output reserve8192, temperature0.1, input character limit500000 and JSON Schema. Under advanced settings enable **Disable thinking (reasoning_effort=none)**. Save only this role. This option was verified with the current Bionic runtime; support by other local servers is not guaranteed.

On the **Book revision** page (☰ Story actions menu), preview the impact check first. The new local profile displays **JSON contract2**, the number of parts and synthesis calls. Inference starts only after explicit dispatch; preview never calls the model. Large books still require many local calls and processing time. Context estimates are conservative; increasing a character limit does not increase physical context capacity.

The model returns short references to exact evidence. Code expands and validates them against the text. Unknown evidence, incomplete output or an exceeded reserve stops the stage while preserving successful parts. There are no automatic retries. `uncertain` requires author review; valid JSON does not prove narrative consistency. Other roles can keep using Venice/OpenRouter.


## Кваліфікований tokenizer / Qualified tokenizer

Українська: optional CPU-компонент встановлюється через `pip install -e ".[web,local-tokens]"`. Він не завантажує GPU-модель і не ходить в інтернет під час підрахунку. Лічильник застосовується лише до відповідного local impact профілю; інші ролі/провайдери не змінюються.

Реєстрація виконується локально адміністратором:

```powershell
python -m storygen.token_budget.local_cli --data-dir data register --endpoint http://localhost:1235/v1 --tokenizer C:/models/tokenizer.json --template C:/models/chat-template.txt --evidence C:/private/qualification.json
python -m storygen.token_budget.local_cli --data-dir data activate --id PROFILE_SHA256
python -m storygen.token_budget.local_cli --data-dir data deactivate --id PROFILE_SHA256
```

`qualification.json` — масив `[{"request": {повний збережений API body}, "observed_tokens":13590}]`; це приклад структури, а не готовий JSON. Файл містить авторські матеріали: зберігайте локально й не додавайте до Git. Tokenizer/template беруться саме від завантаженої моделі. CLI перевіряє точний збіг usage, зберігає у профілі тільки hashes/counts. Register не активує профіль; --activate або окрема activate — явне рішення. Не підставляйте вигадане usage. Не міняйте файли зареєстрованого профілю вручну. За оновлення бібліотек/шаблону/моделі виконайте restart і повторну qualification.

За невідповідності або відсутності компонента система повертається до консервативного підрахунку; старі звіти не губляться. Число викликів може зрости або continuation зупиниться на бюджеті. Після погодженої активації для цього оповідання max_input_chars планувальника500000, context131072/output8192. Резерв8192 потрібен для розкритих доказів: початковий cap2048 був замалим; перевірки не послаблено. Зменшення числа викликів потребує активованого counter нижче; без нього fallback безпечний, але дорожчий за часом. Перед запуском завжди зробіть новий preview. Повний прогін не стартує автоматично. Збережіть теку local_tokenizers разом із резервом data.

English: install the optional CPU component with `pip install -e ".[web,local-tokens]"`. Counting performs no inference, GPU loading or runtime downloads. It applies only to the matching local impact profile. Use the same register/activate/deactivate commands above; other roles/providers remain unchanged.

`qualification.json` is an array of objects containing a saved full API `request` and its actual `observed_tokens`. The structural example above is not executable JSON. It contains manuscript data: keep it local and out of Git. Obtain tokenizer/template files from the actual loaded model. CLI qualification requires exact usage reproduction and stores only hashes/counts in the profile. Registration alone does not activate; use --activate or the explicit activate command. Never invent usage or edit registered artifacts manually. Restart and requalify after changing libraries, templates or models.

Missing or mismatched artifacts/dependencies cause a conservative fallback. Saved reports remain readable, but call counts may increase and continuation may fail a context gate. After approved activation, only this story’s planner character limit is500000 with context131072/output8192. The output reserve was increased after expanded evidence exceeded the earlier2048-character result cap; validation was retained. Call reduction requires the activated counter; fallback remains safe but can require more time. Always request a fresh preview; the book run never starts automatically. Include local_tokenizers in your data backup.


## Відновлення після помилкового обліку покриття / Recovery after coverage accounting error

У wire2 службові ID покриття додає код, тому вони не витрачають резерв модельної відповіді. Докази, цитати й модельний текст усе ще перевіряються за лімітом. Якщо попередній запуск зупинився з «Відповідь частини перевищила погоджений резерв», після оновлення натисніть **«Повторити перерваний етап»** у цьому запуску: придатна збережена stop-відповідь спочатку перевіриться локально без повторного виклику моделі. Успішні попередні частини збережуться; після відновлення запуск продовжить решту частин. Якщо відповідь справді завелика або джерела змінилися, цей механізм її не прийме. Саме оновлення сервера не запускає перевірку книги.

In wire2, code adds coverage IDs, so these IDs do not consume the model response reserve. Evidence, quotes and model text still count. If an earlier run failed with “The part response exceeded the agreed reserve”, after updating use **“Repeat interrupted stage”** in that run: a valid saved stop response is first revalidated locally without another model call. Earlier successful parts remain saved; resuming then processes the remaining parts. Genuinely oversized responses or changed sources are not accepted through this recovery. Updating the server never starts the book check automatically.


## Суперечливі правки / Inconsistent findings

«Підтверджені правки не дозволяють позитивний висновок» означає, що модель поєднала no_impact з новими чи успадкованими правками. Це помилка відповіді, а не наказ переписати сцену. Оновлений промпт відносить спостереження про узгодженість до summary, а findings — лише до конкретних необхідних змін. Для нового промпту створіть новий preview/запуск: повтор старого етапу використовує його зафіксований старий промпт. Новий запуск не успадковує успішні частини старого. Немає автоматичного виправлення verdict або гарантії безпомилкового аналізу.

“Confirmed findings do not permit a positive verdict” means the model combined no_impact with new or inherited findings. It is an inconsistent response, not an instruction to rewrite the scene. The updated prompt puts consistency observations in summary and reserves findings for concrete required changes. Create a new preview/run to use it: repeating an old stage uses its frozen old prompt. A new run does not inherit successful parts from the old one. Verdicts are not repaired automatically; model accuracy is not guaranteed.


## Резерв відповіді та кнопка повтору / Response reserve and retry button

Розкриті точні цитати можуть бути довшими за короткий JSON із E-посиланнями. Для поточного погодженого planner-профілю context131072/output12288/maxchars500000 межа результату становить5939 символів за чинною формулою; попередня межа була4096. Зміна резерву зменшує доступний вхід і може збільшити кількість частин. Створіть новий preview/run: старий manifest зберігає старий cap і промпт. Текст не обрізається. Після повернення з налаштувань кнопка повтору не зникає: під час перевірки або за перешкоди вона вимкнена з поясненням; зміна налаштувань може вимагати нового запуску.

Expanded exact quotes may be longer than the short JSON containing E references. For the approved planner profile context131072/output12288/maxchars500000, the current formula gives a5939-character result cap; the previous cap was4096. Increasing the response reserve reduces input space and may increase the part count. Create a new preview/run: an old manifest retains its old cap and prompt. Text is never truncated. After returning from settings, retry remains visible: it is disabled with a reason while prerequisites are checked or blocked; changed settings may require a new run.
