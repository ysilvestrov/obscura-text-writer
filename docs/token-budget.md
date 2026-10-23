# Оцінка токенів і перевірені профілі

До відправлення запиту система враховує весь API body, включно з JSON schema,
і додає резерв відповіді. Без профілю використовується консервативна евристика
UTF-8 bytes body +256; це не точний tokenizer. Обсяг доступного контексту
задається реальною моделлю, збільшення context_tokens не змінює її можливості.

Нові спроби автоматично зберігають observation, якщо usage містить додатний
цілий prompt_tokens. Для generation увімкніть «Запитувати usage потоку» лише
якщо endpoint це підтримує. Відсутня usage не є нульовим споживанням.
Codex CLI не отримує Chat Completions body і не калібрує API-профіль.

Керування локальне, без платних викликів. З кореня проєкту:

```powershell
.\.venv\Scripts\python.exe -m storygen.token_budget.cli --data-dir data collect
.\.venv\Scripts\python.exe -m storygen.token_budget.cli --data-dir data list
.\.venv\Scripts\python.exe -m storygen.token_budget.cli --data-dir data build --identity HASH
.\.venv\Scripts\python.exe -m storygen.token_budget.cli --data-dir data activate --identity HASH
.\.venv\Scripts\python.exe -m storygen.token_budget.cli --data-dir data deactivate --identity HASH
```

Після перевстановлення пакета доступний також `storygen-tokens`.
`collect` повторно читає лише нові спроби з exact api_request; дедуплікація
не створює нових спостережень для повторного body. Старі спроби без body
не домислюються. `list` показує identities, кількість і звіти профілів без прози.

Для допуску потрібні ≥40 різних запитів, train≥30/holdout10, діапазон byte
sizes≥4× та кириличні/ASCII/JSON content classes (≥5 кожного типу, кожен тип
у train і holdout). Коефіцієнт береться за найбільшим train ratio tokens/bytes,
запас20%+256; на holdout не повинно бути недооцінок. Неоднорідність чи мала
вибірка відображаються в reasons звіту, а не замовчуються.

Після build профіль **не активний**, навіть за eligible=true. Перегляньте
звіт і лише потім виконайте activate. Інша модель, schema, system prompt,
provider options або endpoint мають окрему identity. У першій версії revision
tokenizer невідома й явно позначена unknown. Профіль діє лише в перевіреному
діапазоні і протягом7 днів; фактична недооцінка стійко його деактивує.
Змінені observations потребують нового build перед activate.

Дані R-17 не надають автоматичного допуску: 48 викликів — лише18 різних
коротких запитів у вузькому діапазоні. Додаткові навчальні модельні виклики
ця функція не запускає. За браку даних лишається fallback, без clipping.
Великі запити він може відхилити раніше за реальний tokenizer; явно збільшувати
ліміт можна лише відповідно до реальної конфігурації провайдера.
