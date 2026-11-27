# Склеєні назви локацій — периферія: план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Мета:** кнопки «Склеїти з…» і «Розклеїти» на панелі «Локації», каталог uk/en, довідка сайту та SPEC S11 поверх ядра (`2026-11-27-location-glue-core.md`).

**Архітектура:**
- Чисті функції `glueOptions`/`glueRows` у `static/locations.js`.
- Дії в `static/locations-panel.js` через наявну `change()`: CAS, повідомлення, рішення щодо залежних сцен.
- Сервер не змінюється, окрім тестової фікстури.

**Технології:** ES modules, Node (JS-тести), Playwright, pytest.

**Специфікація:** `docs/superpowers/specs/2026-11/2026-11-27-location-glue-design.md`.

## Глобальні обмеження

- Тексти uk (точно; en — переклад):
  - `locations.glue` «Склеїти з…»;
  - `locations.glue_target` «Яку назву склеїти з «{p0}»»;
  - `locations.glue_do` «Склеїти»;
  - `locations.glue_confirm` «Склеїти «{p0}» в одну назву? Сцен: {p1}. План не зміниться: розбір рядка «Локація:» більше не різатиме цю фразу в жодній сцені. Версії зачеплених сцен стануть застарілими.»;
  - `locations.glued` «Назву склеєно.»;
  - `locations.glues` «Склеєні назви»;
  - `locations.unglue` «Розклеїти»;
  - `locations.unglue_confirm` «Розклеїти «{p0}»? Сцени знову ділитимуть цю фразу на кілька місць. Ваші злиття лишаться: щоб уламок знову став окремим, натисніть «Розділити».»;
  - `locations.unglued` «Назву розклеєно.».
- Помилки сервера як ключі каталогу (uk дослівно, як у `storage/locations.py`):
  - `locations.error.glue_slash`;
  - `locations.error.glue_length` «Фраза має бути від {p0} до {p1} знаків»;
  - `locations.error.glue_repeat`;
  - `locations.error.glue_no_cut`;
  - `locations.error.glue_limit` «Склеєних назв може бути не більше {p0}»;
  - `locations.error.glue_unknown`.
- Пропозиції фільтруються за довжиною 3–200 знаків. Це закриває відкладену дрібницю ядра.
- Документація сайту uk/en парна, підтвердження — `python scripts/check_site.py --rehash memory`. Знімок `locations-desktop.png` не переробляється: на ньому немає дій склеювання, і він лишається правдивим.

## На що дивитися в рев'ю

1. **Склеєна картка має `card_ids` однієї з пропозицій** (наприклад, «Бар, в якому…» після склеювання з «, вулиця»). Кнопку «Склеїти з…» має і вона. Перевіряє JS-тест.
2. **Розклеювання після злиття уламка.** Повідомлення про розклеювання з'являється, помилки немає. Покрито тестом сховища ядра, у панелі нічого особливого немає.
3. **Mobile.** Вибір фрази не виходить за ширину вікна. Перевіряє Playwright mobile, `scrollWidth` дорівнює `clientWidth`.

---

### Задача 1: Рядки й дії панелі

**Файли:**
- змінити `src/storygen/web/static/locations.js`, `src/storygen/web/static/locations-panel.js`;
- тест: `tests/web/js/locations.mjs`.

**Інтерфейси:**
- `glueOptions(data, id) -> [{key, phrase, cardIds, scenes}]`: пропозиції, `card_ids` яких містять `id`, з фразою довжиною 3–200 знаків;
- `glueRows(data) -> [{key, phrase}]`.

- [ ] **Крок 1. JS-тести.**
  - `glueOptions` для «bar» повертає пропозицію з `scenes === 2`.
  - Фраза довжиною 201 знак відсікається.
  - Картка поза `card_ids` нічого не отримує.
  - `glueRows(undefined)` дорівнює `[]`.
- [ ] **Крок 2.** Тести падають.
- [ ] **Крок 3. Реалізація.**
  - Кнопка «Склеїти з…» на незлитій картці з опціями відкриває вибір фраз: стан `gluing`, той самий вигляд, що в «Злити в…».
  - Розділ «Склеєні назви» стоїть після дерева, кожна фраза має «Розклеїти».
  - `change()` приймає `subject` як функцію від нових даних. Для розклеювання `ids` беруться з пропозиції цього ключа в новій відповіді, а якщо її немає — `['glue:'+key]`.
- [ ] **Крок 4.** Тести проходять.
- [ ] **Крок 5.** Коміт.

### Задача 2: Каталог, фікстура, Playwright і перевірка повідомлень сервера

**Файли:**
- змінити `src/storygen/web/static/i18n.json`, `tests/web/browser/server.py` (`/test-locations?glue=true` додає сцену «Кава» з «Локація: Бар, в якому пахне кавою, вулиця»), `tests/web/browser/locations.spec.mjs`, `tests/web/test_locations_ui.py`.

- [ ] **Крок 1.** `test_server_messages_match_the_catalog` розширити шістьма ключами `glue_*`. `{p0}`/`{p1}` замінюються на `{GLUE_MIN}`/`{GLUE_MAX}`/`{GLUE_LIMIT}`. Тест має впасти.
- [ ] **Крок 2.** Додати ключі uk/en, тест проходить.
- [ ] **Крок 3. Playwright-тест** «склеювання й розклеювання».
  - «Бар» → «Склеїти з…» → діалог містить «План не зміниться» → повідомлення «Назву склеєно.».
  - Рядок «Бар, в якому пахне кавою» має «Сцени: 3. Кава», а «Бар» — «Жодна сцена не називає її прямо».
  - «Склеєні назви» → «Розклеїти» → «Назву розклеєно.», після чого «Бар» знову має «Сцени: 3. Кава».
  - Немає горизонтального прокручування.
  - Запуск на desktop і mobile.
- [ ] **Крок 4.** Коміт.

### Задача 3: SPEC S11, traceability, manual.md, сайт

- [ ] **SPEC MEMORY-LOCATIONS:**
  - абзац «Панель» доповнити склеюванням;
  - з «Відомих обмежень» прибрати «Панель для склеювання ще не має кнопок — лише API»;
  - додати Scenario `MEMORY-LOCATIONS-S11`.
- [ ] **traceability S11:** `test_panel_rows`, `test_server_messages_match_the_catalog`; manual `locations-panel`.
- [ ] **`manual.md#locations-panel`:** додати опис нового Playwright-case.
- [ ] **`docs/site/{uk,en}/memory.md`:** пункт «Склеїти з…» / «Glue with…» і «Розклеїти» / «Unglue» з порадою злити уламок; речення про кому в першому абзаці. Потім `check_site.py --rehash memory` і `check_docs.py`.
- [ ] **Коміт.**
