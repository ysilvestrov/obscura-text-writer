# Проба для скіла `revise` — результати (25.11.2026)

Ізольований стенд `scripts/skills_stand.py serve --work C:/tmp/<dir>` (власна тека даних, без ключів провайдерів). Інструменти мосту викликано в процесі (`obscura_call`), дії інтерфейсу — прямим HTTP. Запуск: `OB_BASE=http://127.0.0.1:<port> python <ця тека>/a.py` із робочої теки в `C:/tmp`.

Скрипти: `s1–s7` — підготовка (твір chat, 3 сцени); `q1–q6c` — питання 1–7 першої проби; `a.py`, `b.py`/`b2.py`, `c.py` — додаткові проби A–C. Скрипти `q2d–q4d` налаштовують роль редактора (локальний провайдер), тож зміни лише на стенді.

## Перша проба

- Мінімальний `target_words` твору — 5000 (`domain.py:37`).
- Q1. `save_draft` на готовій сцені приймається; сцена лишається `prose`/`valid`, але голова прози — стара (`get_scene_text(prose)` → «…в Житомирі…»). Сцена 2 без змін, запусків немає.
- Q2. Прозу змінює лише етап edit. Після edit: `state= needs_review … memory: unchecked`; після memory — `prose`/`valid`. Типовий `result_format` — `prose` (`providers/models.py:101`). Проза, ідентична чернетці, приймається (`completed`). У режимі `patches` порожні правки → `422: Помилка редактора: Редактор не запропонував змін; прийняття недоступне… {"category":"no_changes"}`. Налаштована роль редактора обмежує й завдання чату (`context_tokens` 8192 → 400 «Перевищено токенний ліміт входу»).
- Q3. Повтор memory сцени 1 → запуск `memory_carry` для сцени 2 (`completed`), сцена 2 `needs_review` (brief/prose `unchecked`). Автор розв'язує `POST /api/scenes/{id}/links/{brief|prose}/decision {action:"approve", fingerprint}`; `accept-version` не розв'язує. Поки пам'ять сцени 1 застаріла: `get_scene_context(сцена 2)` → `400: Спершу оновіть пам’ять попередньої сцени`.
- Q4. Відкладена пропозиція patches (`edit_review: review`, `save_stage_result` → `state: needs_review`, `get_story` показує `prose`) не блокує `save_draft`; стара пропозиція далі → `400: Джерела пропозиції змінилися; створіть нову редакторську пропозицію`.
- Q5. `update_scene` з планом працює в обох режимах; у творі «obscura» `save_draft` і `get_stage_task` → `409: Твір у режимі «пише Obscura»: запустіть етап через start_run`.
- Q6. Повторний імпорт персонажів картку не перезаписує: `skipped_character_names: ["Олена"]`, «Наявні картки не перезаписано…».
- Q7. Пам'ять містить дослівний `quote` прози й текст твердження; стара назва міста лишається до повтору memory, а також у плані, брифі й списку локацій.

## A. Записи за неперевірених зв'язків (`a.py`)

Після зміни прози сцени 1 і повтору її пам'яті сцена 2: `brief: unchecked, prose: unchecked`.

- A1 (brief → draft → edit → memory, без рішення автора): усе `completed`; сцена 2 → `state= prose validity= valid`, усі зв'язки `valid`.
- A2 (без brief): `save_draft` приймається, але `get_stage_task(edit)` → `400: Некоректні дані: Сцена «С2»: завдання не перевірено проти плану й пам’яті попередньої сцени — затвердьте завдання або оновіть його`. Етап memory приймається (на старій прозі); сцена лишається `needs_review`.

## B. Перенос після нових ID тверджень (`b.py`, `b2.py`)

Сцена 1 додає `character_states` «Олена тримає валізу.»; сцена 2 робить `update` цього `claim_id`; сцена 3 має пам'ять. Потім змінено прозу сцени 1 і повторено її пам'ять із новим текстом.

- `memory_carry` для сцени 2: run `state: completed`, `error: null`, але `warning: "Перенос пам’яті зупинено на сцені «С2»: її записи посилаються на твердження, яких немає в новій пам’яті попередньої сцени — створіть нову пам’ять цієї сцени"`; подія `carry_step {"result":"failed","reason":"carry_failed","detail":"Записи сцени посилаються на твердження, яких немає в новій пам’яті попередньої сцени"}`.
- Сцена 2: `memory: {status: unavailable, reason: carry_failed}`, brief/prose `unchecked`. Сцена 3: `memory: unavailable, reason: carry_pending`, `carry_failed_scene_id` = сцена 2; `get_scene_context(сцена 3)` → `400: Сцена «С2»: пам’ять не вдалося перенести на нову пам’ять попередньої сцени — створіть нову пам’ять цієї сцени`.
- Чат може переробити пам'ять сцени 2 за `carry_failed`: `get_stage_task(memory)` ok, `save_stage_result` → `completed`. Далі автоматично запускається `memory_carry` для сцени 3 (`completed`), пам'ять сцени 3 `valid`, але brief/prose сцени 3 стають `unchecked` (каскад). `get_stage_task(edit)` сцени 2 за неперевіреного брифа відмовляє (див. A2).

## C. Чернетка автора й відбиток пам'яті (`c.py`)

1. Редактор зберігає чернетку `POST /api/scenes/{id}/draft {text, expected_revision, content_format}` без `external_origin` (`static/versions.js:72`). Результат: `kind: draft`, `external_origin: null`. Редактура з неї (чат) → зв'язок прози `unchecked` (ручна чернетка розриває ланцюжок, VALID-LINKS-S03).
2. Дві пам'яті сцени 1 з тими самими твердженнями після зміни лише в `f000002` відрізняються лише `claim_id` (`mc_8c6c…` → `mc_f147…`). `claim_id = stable_id('mc_', [category, text, prose_id, quote, occurrence, …])` (`memory/journal.py:221-226`): ID версії прози входить у `claim_id`, тож будь-яка нова проза дає нові `claim_id`, змінює `memory_digest` і робить З1/З2 наступної сцени `unchecked`, а `update`/`retire` наступних сцен посилаються на зниклі ID → `carry_failed`.
