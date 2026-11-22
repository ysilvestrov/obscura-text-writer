# Reasoning для ролей з провайдером OpenRouter

Дата: 2026-11-22
Статус: чернетка
Spec-review: —

## Для власника

### Мета

Автор може вимкнути або зменшити reasoning для будь-якої ролі з провайдером OpenRouter, як уже може для Venice і локальних моделей. Тоді «думаючі» моделі на кшталт Qwen чи GLM не витрачають увесь вихідний ліміт на роздуми й повертають текст.

### Що зміниться для тебе

- У формі ролі з провайдером OpenRouter з'явиться поле «Reasoning». Його варіанти залежать від вибраної моделі: «за замовчуванням», «вимкнено» (лише якщо модель дозволяє) і рівні, які модель приймає. Варіанти беруться з каталогу OpenRouter, коли завантажуєш список моделей.
- MCP `update_settings` приймає нове поле, а `get_settings` у списку моделей показує, що кожна модель дозволяє з reasoning. Скіл `setup-models` використовує це для редактора (див. «Питання до власника»).
- Наявні ролі, сцени й перевірки впливу не змінюються й не стають застарілими, доки поле не задано.
- Нічого незворотного: поле можна скинути на «за замовчуванням».
- Рецепти з моделями, які прибрав тест редакторів, сам код не повертає: це окреме рішення після повторного тесту.

### На чому стоїть рішення

- Для OpenRouter у коді немає способу передати `reasoning`: перемикачі є лише для Venice (`venice_disable_thinking`, `venice_reasoning_effort`) і local (`local_disable_thinking`). `[проба]` П1
- OpenRouter приймає `reasoning: {effort}`, де effort — `max`, `xhigh`, `high`, `medium`, `low`, `minimal` або `none`. `none` «вимикає reasoning повністю», effort і `max_tokens` не передаються разом. `[проба]` П2
- Моделі мають три різні режими. Каталог `GET /api/v1/models` для кожної моделі повідомляє об'єкт `reasoning` із `mandatory`, `supported_efforts`, `supports_max_tokens`, `default_enabled`, `default_effort`. З 476 моделей 354 мають reasoning, з них у 151 він обов'язковий. `[проба]` П3
  - `z-ai/glm-5.3-flash`: обов'язковий, за замовчуванням `max`, приймає лише `max`, `high`, `low`.
  - `qwen/qwen3.7-plus`: вимикається, рівнів не приймає.
  - `qwen/qwen3.8-flash`: вимикається, приймає `max_tokens`.
- Для моделі з `mandatory: true` OpenRouter відхиляє `effort: "none"`. Якщо `supported_efforts` немає, модель «не дає вибору рівня». `[проба]` П2
- `reasoning.exclude` лише ховає роздуми з відповіді: токени «все одно оплачуються й зараховуються в max_tokens». Для нашої проблеми це не допомагає. `[проба]` П2
- Нове поле в налаштуваннях провайдера без окремих заходів ламає збережені маніфести перевірки впливу: падає `test_legacy_wire2_raw_proof_without_counter`. `[проба]` П4
- Для трьох моделей із тесту редакторів вимкнення чи зниження reasoning дає текст у межах 512 токенів виходу. `[проба]` П5 — **чекає на запуск**; до запуску це `[виведення]`.
- Якщо роутер OpenRouter відправить запит провайдерові моделі, який не підтримує `reasoning`, той параметр мовчки ігнорує. `provider.require_parameters` у документації про `reasoning` не згадано. `[виведення]` з П2

### Ключові рішення

1. **Одне поле `openrouter_reasoning_effort`** (порожнє або `none` / `minimal` / `low` / `medium` / `high` / `xhigh` / `max`) поруч із полями Venice. Відкинуто: спільне для всіх провайдерів поле reasoning, бо воно вимагає міграції збережених ролей Venice та local і змінює їхні відбитки. Відкинуто: окремий бюджет `reasoning.max_tokens`, бо рівень OpenRouter сам перераховує у частку від `max_tokens` (`low` ≈ 20 %), а друге поле подвоює форму й валідацію.
2. **Варіанти показуються з каталогу, сервер каталог не перевіряє.** Форма й MCP бачать, що дозволяє модель, і не пропонують «вимкнено» для моделі з обов'язковим reasoning. Під час збереження ролі сервер перевіряє лише допустимість значення й не ходить у мережу. Якщо модель змінилась, а значення лишилось неприйнятним, OpenRouter поверне помилку, і запуск її покаже. Відкинуто: перевіряти каталог під час збереження, бо тоді збереження ролі залежить від мережі.
3. **Порожнє поле не потрапляє ні в запит, ні у відбитки.** Тому старі ролі, контексти сцен і маніфести перевірки впливу лишаються дійсними. Задане поле входить у запит і у відбиток, тож зміна reasoning робить контекст сцени новим, як зміна моделі. Відкинуто: ще один точковий виняток у кожному місці відбитка (уже є три такі латки), бо наступне місце знову зламається.
4. **Без `provider.require_parameters`.** Запит з reasoning не обмежує роутинг. Відкинуто: вмикати його, бо в документації він не пов'язаний з `reasoning`, а вимагає підтримки всіх параметрів запиту (зокрема `response_format`). Це звузить або зламає роутинг ролей, які зараз працюють.

Розглянуто стандартне: `reasoning.exclude` / `include_reasoning: false` — відкинуто, бо токени все одно рахуються в ліміт (П2).

### Що стане гірше

- Ще одне поле у формі ролі OpenRouter. Його варіанти залежать від завантаженого списку моделей: без списку форма показує лише «за замовчуванням» і вже збережене значення.
- Якщо OpenRouter відправить запит провайдерові, що не підтримує `reasoning`, поле мовчки не спрацює, і помилка вихідного ліміту лишиться (рішення 4).
- Вимкнений чи знижений reasoning може погіршити якість ролі. Що це дає для редагування української, видно лише з повторного тесту редакторів, а цей тест платний і в цю зміну не входить.
- Каталог описує модель загалом, а не кожного провайдера за нею. Хтось із провайдерів може поводитися інакше.

### Оцінка

- Власник: S. Автор: M. Розбіжність в один розмір, тож обов'язкової зупинки немає. Автор оцінює більше через периферію: каталог → форма → MCP → скіл → сайт uk/en.
- Розподіл: поле, запит і виключення з відбитків ≈ 20 %; можливості моделі з каталогу, поле у формі, i18n ≈ 30 %; MCP, скіл `setup-models`, тести встановлення ≈ 15 %; SPEC.MD, traceability, сайт uk/en ≈ 25 %; тести ≈ 10 %.
- Дешевший варіант (S): поле й запит, у формі всі рівні без каталогу, скіл без змін. Що втрачаємо: форма пропонуватиме «вимкнено» для моделі з обов'язковим reasoning (GLM), і OpenRouter відхилятиме такий запит. Скіл не зможе сам підібрати reasoning для редактора.

### Питання до власника

1. Чи має `setup-models` сам налаштовувати reasoning для **редактора**, якщо модель має його ввімкненим за замовчуванням: вимикати, коли модель дозволяє, інакше ставити найнижчий доступний рівень, і казати про це автору? Чи лише пропонувати, а вирішує автор? Для планувальника, автора тексту й пам'яті скіл reasoning не чіпає.

## Тіло

### Проби

**П1. Код (22.11.2026, origin/main a134ffd9).**
- `src/storygen/providers/models.py`: `ProviderSettings` має `local_disable_thinking`, `venice_disable_thinking`, `venice_reasoning_effort`.
- `src/storygen/providers/requests.py`: `generation_request` додає `reasoning` лише для Venice (`venice_reasoning`) і `reasoning_effort=none` для local. `sdk_arguments` уже переносить `reasoning` в `extra_body`.
- `evaluation_request` для OpenRouter ставить лише `provider.require_parameters` за json_schema.
- Повідомлення `output_limit_message` (`providers/streaming.py`) радить «вимкніть або зменште reasoning», але для OpenRouter такого перемикача немає.

**П2. Документація OpenRouter (прочитано дослівно 22.11.2026).** Сторінки: `docs/use-cases/reasoning-tokens`, `docs/guides/routing/provider-selection`, схема `list-all-models-and-their-properties`.
- "`"effort": "none"` - Disables reasoning entirely"; рівні: max, xhigh, high, medium, low, minimal, none; effort і max_tokens — "One of the following (not both)".
- mandatory: "When true, reasoning cannot be disabled and effort "none" is rejected."
- supported_efforts: "When omitted, the model does not expose effort selection"; null — "no allowlist — all gateway effort values are accepted".
- Відсотки від max_tokens: max/xhigh ≈ 95 %, high 80 %, medium 50 %, low 20 %, minimal 10 %.
- exclude: "The tokens are still billed and count against max_tokens."
- require_parameters: провайдери без підтримки параметра "will ignore unknown parameters"; про `reasoning` у розділі нічого немає.
- `reasoning: {enabled: false}` для Chat Completions окремо не описано, є лише мапінг із Messages API.
- Рівень, якого модель не підтримує: для Gemini OpenRouter "will map your requested effort to the nearest supported level". Загального правила не знайдено.

**П3. Живий каталог (безкоштовно, без ключа, 22.11.2026).** `GET https://openrouter.ai/api/v1/models`: 476 моделей, 354 з `reasoning`, 151 `mandatory: true`. Ключі об'єкта: `mandatory`, `default_enabled`, `default_effort`, `supported_efforts`, `supports_max_tokens`.
- glm-5.3-flash: `{"mandatory": true, "default_enabled": true, "supported_efforts": ["max","high","low"], "default_effort": "max"}`.
- qwen3.8-flash: `{"mandatory": false, "default_enabled": true, "supports_max_tokens": true}`.
- qwen3.7-plus: `{"mandatory": false, "default_enabled": true}`.

**П4. Відбитки (безкоштовно).** У тимчасовій копії в `ProviderSettings` додано лише `openrouter_reasoning_effort: ... | None = None`. Прогін `pytest -x tests/impact tests/review tests/mcp tests/providers`: 35 passed, 1 failed — `tests/impact/test_local_token_counting.py::test_legacy_wire2_raw_proof_without_counter`, `ValueError: Невідповідний fingerprint маніфесту` (`impact/chunk_validation.py:40`). Причина: `settings_for_manifest` хешує `manifest.settings.model_dump()`. Ті самі `model_dump()` налаштувань ролі потрапляють у `generation/context.py:227` (відбиток контексту сцени), `review/planning.py:80` і `role_profiles.py`. Зміну відкочено.

**П5. Платна проба (погоджена власником 22.11.2026: ≤ 6 запитів, max_tokens 512).** Скрипт `C:\tmp\or-probe\or_probe.py`: короткий нейтральний текст для виправлення, по два варіанти reasoning на модель.
- glm-5.3-flash: `effort low` і `effort none` (очікується відмова).
- qwen3.7-plus: `effort none` і `enabled false`.
- qwen3.8-flash: `effort none` і `max_tokens 64`.

Записує статус, finish_reason, довжину тексту, reasoning_tokens і вартість. **Результат: чекає на запуск.** Від нього залежить wire-форма «вимкнено» (`{effort: "none"}` чи `{enabled: false}`).

### Технічний опис

**Модель.**
- `ProviderSettings.openrouter_reasoning_effort: Literal['none','minimal','low','medium','high','xhigh','max'] | None = None`.
- Валідатор: непорожнє значення дозволене лише для `provider == 'openrouter'`. Для інших провайдерів це помилка, щоб не зберегти значення, яке мовчки нічого не робить.
- Серіалізатор (`model_serializer(mode='wrap')`) не виводить поле, коли воно `None`. Це одне правило для всіх `model_dump()`: збереження ролі, відбиток контексту, штамп маніфесту впливу, план перевірки, профілі ролей.
- Те саме поле автоматично мають `ClassificationSettings.provider` і `RoleVariant.provider`, бо там теж `ProviderSettings`.
- `EvaluatorConfig` поза межами зміни.

**Запит.** `openrouter_reasoning(settings)` поруч із `venice_reasoning`:
- `None` → `{}`;
- рівень → `{'reasoning': {'effort': value}}`;
- `none` → wire-форма за П5.

Його викликає `generation_request` для `provider == 'openrouter'`. `evaluation_request` не змінюється. `sdk_arguments` уже переносить `reasoning` в `extra_body`.

**Каталог.**
- `ModelOption.reasoning: ReasoningCapability | None` (`mandatory: bool`, `efforts: list[str] | None`, `default_effort: str | None`).
- `catalog.model_option` заповнює його з об'єкта `reasoning` рядка OpenRouter. Відсутній `supported_efforts` → `efforts = []` (рівень вибрати не можна). `null` → `None` (усі рівні). Невідомі значення відкидаються.
- Для Venice і local `reasoning = None`.

**Форма ролі** (`settings.js`, `settings-connection.js`, `i18n.json`):
- блок `connection-openrouter` з селектом «Reasoning» видно лише для OpenRouter;
- варіанти: «за замовчуванням» завжди; «вимкнено», якщо модель не `mandatory`; рівні з `efforts` (усі, якщо `None`);
- без завантаженого списку моделей — «за замовчуванням» і збережене значення;
- значення, якого модель не дозволяє, показується з позначкою «модель не підтримує», а не мовчки скидається;
- `web/app.py` додає поле в `allowed`.

**MCP** (`mcp/bridge.py`):
- `PROVIDER_FIELDS` і docstring `update_settings` отримують поле;
- рядки моделей у `get_settings(models_for_role=…)` отримують ключ `reasoning`;
- зміна провайдера з OpenRouter на інший скидає поле так само, як `key_env`.

**Скіл `setup-models`** (`integrations/claude/obscura/skills/setup-models/SKILL.md`) — після відповіді власника на питання 1:
- для редактора з моделлю, де `reasoning` є і не `mandatory`, — `none`;
- для `mandatory` — найнижчий рівень з `efforts`;
- автору про це кажуть одним рядком;
- плюс тести встановлення скілів.

**Діагностика.** Текст `output_limit_message` / `empty_output_message` не змінюється: порада «вимкніть або зменште» тепер має відповідне поле й для OpenRouter.

### Інваріанти

- I1. Роль без `openrouter_reasoning_effort` дає байт-у-байт той самий запит, збережений JSON і відбитки, що й до зміни.
- I2. Поле впливає лише на запити провайдера OpenRouter. Venice, local і оцінювач не змінюються.
- I3. Форма і скіл не пропонують `none` для моделі з `mandatory: true`.
- I4. Зміна поля змінює відбиток контексту сцени, як і будь-яка зміна налаштувань ролі.

### Сумісність і міграції

Міграції немає: старі ролі читаються з типовим `None`, а серіалізатор не додає поле в збережений JSON, поки його не задано. Збережені маніфести перевірки впливу (wire 1 і 2) лишаються дійсними — регресійний тест П4.

### SPEC.MD, traceability, сайт

- SPEC.MD: розділ «A4. Конфігурація моделей і шлюз генерації» — абзац про OpenRouter reasoning поруч із Venice.
- Новий Requirement `OPENROUTER-REASONING` зі Scenario:
  - S01 — рівень у запиті;
  - S02 — вимкнення;
  - S03 — порожнє поле не змінює запит і відбитки (зокрема legacy-маніфест);
  - S04 — форма не пропонує вимкнення для обов'язкового reasoning;
  - S05 — MCP передає й показує можливості;
  - S06 — поле для не-OpenRouter відхиляється.
- Уточнення в технічному доповненні до `venice_reasoning_effort` (рядок про local/Venice/OpenRouter у IMPACT-LOCAL).
- `docs/verification/traceability.json`: тест на кожен Scenario.
- Сайт uk/en: сторінка налаштувань ролей / моделей — поле Reasoning для OpenRouter; `check_site.py --rehash`.

### Відомі обмеження

- Бюджету `reasoning.max_tokens` немає (рішення 1).
- Каталог описує модель, а не кожного провайдера за нею.
- Без `require_parameters` провайдер без підтримки може проігнорувати поле (рішення 4).
- Рецепти редакторів не змінюються без повторного тесту.

## Заявка → доказ

| Заявка | Де записано | Що доводить | Сила |
|---|---|---|---|
| Порожнє поле не змінює відбитки й маніфести | Інваріант I1, SPEC OPENROUTER-REASONING-S03 | Регресійний тест на legacy-маніфест wire2 і відбиток контексту з порожнім полем (П4 показав, що без заходів падає) | сильна після тесту |
| Модель з `mandatory` відхиляє `none` | Форма й скіл ховають «вимкнено» | Документація (П2, дослівно) + П5 для glm-5.3-flash | сильна після П5 |
| Вимкнення чи зниження reasoning повертає текст для трьох моделей | Мета, «На чому стоїть рішення» | П5 | **слабка до П5** |
| Можливості моделі в `ModelOption.reasoning` | Каталог, форма, MCP | Живий каталог (П3) — зовнішні дані, можуть змінитися | середня: читається щоразу з каталогу, не кешується як істина |

## Рев'ю спеки

Ще не запускалось.
