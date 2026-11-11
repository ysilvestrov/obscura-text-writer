# Ключ провайдера в налаштуваннях і сховище Windows — план реалізації (#30, PR 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Мета:** автор вводить ключ провайдера в налаштуваннях підключення, ключ лежить у сховищі облікових даних Windows і діє без перезапуску; `.env` і змінні середовища працюють, як і раніше.

**Архітектура:** один модуль `storygen/providers/secrets.py` відповідає на питання «який ключ для цієї назви змінної»: спершу змінна середовища, потім сховище. Усі п’ять місць, що сьогодні читають `os.environ` для ключа, переходять на нього. Три маршрути `/api/provider-keys/{name}` дають стан, запис і видалення; значення ключа сервер ніколи не повертає. Форма підключення показує стан і поле введення.

**Стек:** Python 3.12, FastAPI, бібліотека `keyring` (Windows Credential Manager) як необов’язкова залежність, ES-модулі, pytest, Playwright.

**Специфікація:** `docs/superpowers/specs/2026-11/2026-11-11-store-build-design.md`, розділ «Ключі провайдерів» і ключове рішення 4. Чинна вимога, яку розширюємо, — `SPEC.MD`, SECURITY-002.

**Проба (висновок 11 специфікації, виконано 11.11.2026):** у `C:\tmp\frz` `keyring` 25.7.0 із бекендом `keyring.backends.Windows.WinVaultKeyring` записав, прочитав і видалив тестовий запис як із вихідного коду, так і з замороженої PyInstaller-збірки (`frozen True`, `roundtrip True`, `after-delete None`), без додаткових прихованих імпортів. Не перевірено: робота зі збірки, упакованої в MSIX (немає Windows SDK); це лишається висновком до плану пакування.

## Загальні обмеження

- Значення ключа ніколи не повертається з API, не пишеться в журнал, базу, контекст спроби, резервну копію чи повідомлення про помилку. Тести це перевіряють прямо.
- Порядок пошуку: змінна середовища (включно з `.env`) → сховище → немає. Робоча копія розробника з `.env` поводиться, як і раніше.
- Сховище: служба `Obscura`, ім’я запису — назва змінної (`key_env` / `api_key_env`). Ключі спільні для всіх тек даних одного користувача Windows.
- Назва запису для API: `^[A-Z][A-Z0-9_]{2,63}$`. Інша назва — 400; читання ключа з середовища для довільного наявного `key_env` не змінюється.
- `keyring` — необов’язкова залежність (extra `keys`). Без неї або без бекенда сховища застосунок працює зі змінними середовища, а запис ключа дає авторську помилку.
- Тести ніколи не торкаються справжнього сховища Windows: автоматична фікстура підставляє сховище в пам’яті.
- Видання `full` і `store` поводяться однаково.
- Мова документації — українська; нові Scenario мають записи в `docs/verification/traceability.json`; `python scripts/check_docs.py` проходить; сторінки сайту оновлюються парою з `python scripts/check_site.py --rehash <slug>`.
- Запуск тестів із worktree, як у плані `2026-11-11-store-edition-core.md`; повний `verify.py` — з короткої теки, не міняючи коміт під час прогону.

## Фокус рев’ю

1. Ключ із сховища потрапляє в текст помилки провайдера (провайдер повертає ключ у відповіді 401): редагування секретів має прибирати й ключ зі сховища, не лише зі середовища (Задача 2).
2. Ключ є і в середовищі, і в сховищі: діє середовище; форма каже, що ключ із середовища, і пояснює, що збережений у сховищі не використовується (Задачі 1 і 4).
3. Сховище недоступне або кидає виняток під час читання (заблокований профіль, немає бекенда): генерація з ключем із середовища працює; без ключа — наявна помилка «Ключ провайдера відсутній», а не трасування (Задача 1).
4. Ключ із пробілами чи переведенням рядка по краях (вставка з буфера): зберігається обрізаним; порожній після обрізання відхиляється (Задача 3).
5. Запит запису ключа з чужого сайту: відхиляється наявною перевіркою `Origin` (SECURITY-001); тест це закріплює (Задача 3).

---

### Задача 1: Модуль секретів

**Файли:**
- Створити: `src/storygen/providers/secrets.py`
- Змінити: `pyproject.toml` (extra `keys = ["keyring>=25,<26"]`), `tests/conftest.py` (автофікстура сховища)
- Тест: `tests/providers/test_secrets.py`

**Інтерфейси:**
- Дає:
  - `resolve_key(name: str | None) -> str | None` — значення ключа або `None`; ніколи не кидає.
  - `key_source(name: str) -> Literal['env','store'] | None` — звідки візьметься ключ.
  - `stored(name: str) -> bool` — чи є запис у сховищі (незалежно від середовища).
  - `store_key(name: str, value: str) -> None`, `delete_key(name: str) -> None` — кидають `SecretStoreUnavailable(ValueError)` з текстом `Сховище ключів недоступне на цьому комп’ютері. Задайте ключ змінною середовища.`; `delete_key` для відсутнього запису нічого не робить.
  - `valid_name(name: str) -> bool` за шаблоном із «Загальних обмежень»; `store_key`/`delete_key` для недійсної назви кидають `ValueError('Некоректна назва ключа')`.
  - `set_backend(backend) -> None` для тестів; бекенд — об’єкт із `get(name) -> str | None`, `set(name, value)`, `delete(name)`. Типовий бекенд ліниво імпортує `keyring`; `None` від `keyring.get_keyring()` класу `fail.Keyring` або помилка імпорту означає «недоступне».
  - Автофікстура `secret_store` у `tests/conftest.py`: перед кожним тестом ставить бекенд-словник у пам’яті й повертає його.

- [ ] **Крок 1: Написати тести, що падають**

```python
def test_environment_wins_over_store(monkeypatch,secret_store):
    secret_store.set('OPENROUTER_API_KEY','from-store')
    assert (resolve_key('OPENROUTER_API_KEY'),key_source('OPENROUTER_API_KEY'))==('from-store','store')
    monkeypatch.setenv('OPENROUTER_API_KEY','from-env')
    assert (resolve_key('OPENROUTER_API_KEY'),key_source('OPENROUTER_API_KEY'))==('from-env','env')
    assert stored('OPENROUTER_API_KEY') is True


def test_missing_everywhere(secret_store):
    assert resolve_key('VENICE_API_KEY') is None and key_source('VENICE_API_KEY') is None and resolve_key(None) is None


def test_store_and_delete_roundtrip(secret_store):
    store_key('VENICE_API_KEY','  secret-value\n')
    assert secret_store.get('VENICE_API_KEY')=='secret-value'      # обрізано
    delete_key('VENICE_API_KEY');delete_key('VENICE_API_KEY')      # повторне видалення без помилки
    assert stored('VENICE_API_KEY') is False


@pytest.mark.parametrize('name',['path','A','lower_case_KEY','WITH-DASH','X'*65,''])
def test_invalid_names_are_rejected_for_writes(secret_store,name):
    with pytest.raises(ValueError,match='Некоректна назва ключа'):store_key(name,'v')


def test_blank_value_is_rejected(secret_store):
    with pytest.raises(ValueError,match='Ключ не може бути порожнім'):store_key('VENICE_API_KEY',' \n')


def test_unavailable_store_reads_as_missing_and_refuses_writes(monkeypatch):
    set_backend(None)                                # немає бекенда
    assert resolve_key('VENICE_API_KEY') is None and stored('VENICE_API_KEY') is False
    with pytest.raises(SecretStoreUnavailable):store_key('VENICE_API_KEY','v')
    monkeypatch.setenv('VENICE_API_KEY','from-env')
    assert resolve_key('VENICE_API_KEY')=='from-env'


def test_store_that_raises_on_read_is_treated_as_missing(secret_store,monkeypatch):
    def boom(name):raise RuntimeError('locked profile')
    monkeypatch.setattr(secret_store,'get',boom)
    assert resolve_key('VENICE_API_KEY') is None and key_source('VENICE_API_KEY') is None


def test_real_keyring_adapter_with_memory_keyring():
    keyring=pytest.importorskip('keyring')
    # власний клас keyring.backend.KeyringBackend у пам’яті; через типовий бекенд модуля: запис, читання, видалення,
    # служба 'Obscura', видалення відсутнього запису без помилки
```

- [ ] **Крок 2: Запустити й побачити падіння** — `python -m pytest tests/providers/test_secrets.py -q`: помилка імпорту модуля.

- [ ] **Крок 3: Реалізувати модуль, extra і фікстуру.** Порожня змінна середовища (`''`) вважається відсутньою. Адаптер `keyring` перетворює `keyring.errors.KeyringError` і `PasswordDeleteError` відсутнього запису на поведінку з інтерфейсу.

- [ ] **Крок 4: Запустити тести** — той самий файл: усі проходять (останній пропускається, якщо `keyring` не встановлено; встановити `keyring` у `.venv` і побачити його зеленим).

- [ ] **Крок 5: Коміт** — `feat(keys): provider secret resolver with the OS credential store (#30)`.

---

### Задача 2: Усі читання ключа — через модуль

**Файли:**
- Змінити: `src/storygen/providers/client.py`, `src/storygen/providers/streaming.py`, `src/storygen/evaluation/gateway.py`, `src/storygen/generation/worker.py`
- Тест: `tests/providers/test_secret_consumers.py`

**Інтерфейси:** споживає `resolve_key`; публічних інтерфейсів не додає.

- [ ] **Крок 1: Написати тести, що падають**

- `build_openai_client` для `provider='openrouter'` без змінної середовища, з ключем у `secret_store`: клієнт створюється, `client.api_key` дорівнює збереженому значенню; без ключа ніде — наявна `ProviderConfigurationError`.
- Оцінювач (`evaluation/gateway.py`) так само бере ключ зі сховища.
- Редагування секретів: помилка провайдера, що містить ключ зі сховища, після `api_failure`/`safe_message` у шляхах `streaming.py` і `worker.py` не містить цього значення (використати наявні тести редагування як зразок і повторити їх із ключем лише в сховищі).
- Статична перевірка: у `src/storygen` немає `os.environ.get(` поруч зі словами `key_env`/`api_key_env` поза `providers/secrets.py`.

- [ ] **Крок 2: Запустити й побачити падіння** — `python -m pytest tests/providers/test_secret_consumers.py -q`.

- [ ] **Крок 3: Замінити п’ять читань** (`client.py:15`, `streaming.py:159`, `gateway.py:42`, `worker.py:441` і `:452`) на `resolve_key(...)`. Гілки `local`/`codex_cli` без ключа не змінюються.

- [ ] **Крок 4: Запустити** `python -m pytest tests/providers tests/evaluation tests/generation -q` — усі проходять.

- [ ] **Крок 5: Коміт** — `feat(keys): provider and evaluator read keys through the resolver (#30)`.

---

### Задача 3: Маршрути `/api/provider-keys/{name}` і SECURITY-002

**Файли:**
- Створити: `src/storygen/web/routes_provider_keys.py`
- Змінити: `src/storygen/web/app.py` (реєстрація), `src/storygen/web/static/i18n.json` (тексти помилок), `SPEC.MD`, `docs/verification/traceability.json`
- Тест: `tests/web/test_provider_keys.py`

**Інтерфейси:**
- Дає:
  - `GET /api/provider-keys/{name}` → `{"name": str, "source": "env"|"store"|null, "stored": bool, "store_available": bool}`.
  - `PUT /api/provider-keys/{name}` з тілом `{"value": str}` (1…4096 символів після обрізання) → той самий об’єкт стану.
  - `DELETE /api/provider-keys/{name}` → той самий об’єкт стану.
  - Недійсна назва — 400; недоступне сховище на запис — 400 з текстом `SecretStoreUnavailable`.
- Споживає: модуль задачі 1.

- [ ] **Крок 1: Написати тести, що падають**

- Стан: без ключа `source=None, stored=False`; після `PUT` — `source='store', stored=True`; зі змінною середовища — `source='env', stored=True`.
- Після `PUT` значення `"sk-test-12345"` не трапляється в тілі жодної відповіді (`GET`, `PUT`, `DELETE`, `/api/stories/{id}/settings`), у файлах теки даних (обійти всі файли й базу як байти) і в записах `caplog`.
- `PUT` з `Origin: https://evil.example` — 403 (SECURITY-001), сховище не змінено.
- `PUT` порожнього значення, значення з одних пробілів, довшого за 4096 і з недійсною назвою (`path`, `../X`, `lower`) — 400/422, сховище не змінено.
- Після `PUT` запит генерації з провайдером `openrouter` доходить до клієнта з цим ключем без перезапуску застосунку (перевірити через `build_openai_client` на тому ж `app`).
- `set_backend(None)`: `GET` дає `store_available=False`, `PUT` — 400 з авторським текстом українською й англійською.

- [ ] **Крок 2: Запустити й побачити падіння** — `python -m pytest tests/web/test_provider_keys.py -q`: 404.

- [ ] **Крок 3: Реалізувати маршрути.** Тіло запиту не потрапляє в текст помилки валідації (перевірити наявний обробник `RequestValidationError`: він повертає загальний текст). Ключі i18n: `keys.store_unavailable`, `keys.invalid_name`, `keys.blank`.

- [ ] **Крок 4: SPEC і traceability.** SECURITY-002 переписати: налаштування зберігають назву змінної, а не значення; значення може надійти від інтерфейсу до сервера й зберігається лише у сховищі ОС; у зворотному напрямку значення не передається ніколи; порядок пошуку; поведінка без сховища. Нові Scenario `SECURITY-002-S02` (запис і застосування без перезапуску), `-S03` (значення ніде не з’являється), `-S04` (середовище має перевагу), `-S05` (сховище недоступне). Технічний опис у розділі Architecture. `python scripts/check_docs.py` — код 0.

- [ ] **Крок 5: Запустити** `python -m pytest tests/web tests/providers -q` і закомітити — `feat(keys): provider key endpoints and SECURITY-002 (#30)`.

---

### Задача 4: Форма підключення й інструкції

**Файли:**
- Створити: `src/storygen/web/static/provider-key.js`
- Змінити: `src/storygen/web/static/settings-connection.js`, `src/storygen/web/static/i18n.json`, `src/storygen/web/static/app.css`
- Змінити: `docs/site/uk/install.md`, `docs/site/en/install.md`, `docs/site/uk/models.md`, `docs/site/en/models.md`, `docs/site/uk/evaluator.md`, `docs/site/en/evaluator.md`, `docs/verification/manual.md`
- Тест: `tests/web/browser/provider-key.spec.mjs`, `tests/web/js/provider_key.mjs` з обгорткою `tests/web/test_provider_key_ui.py`; тестовий маршрут у `tests/web/browser/server.py`

**Інтерфейси:**
- Споживає: три маршрути задачі 3.
- Дає (`provider-key.js`): `export function keyStatusText(state, t) -> string` (чиста функція для п’яти станів) і `export function mountProviderKey(host, {nameField, providerField})` — блок під полем «Змінна середовища з ключем»: рядок стану, поле `type="password"` з `autocomplete="off"`, кнопки «Зберегти ключ» і «Видалити збережений ключ».

Стани й тексти (`uk` / `en`):
- немає ключа: «Ключ не задано.» / `No key set.`
- сховище: «Ключ збережено у сховищі Windows.» / `The key is saved in the Windows credential store.`
- середовище: «Ключ задано змінною середовища.» / `The key comes from an environment variable.`
- середовище і сховище: «Ключ задано змінною середовища; збережений у сховищі не використовується.» / `The key comes from an environment variable; the saved one is not used.`
- сховище недоступне: «Сховище ключів недоступне; задайте ключ змінною середовища.» / `The credential store is unavailable; set the key in an environment variable.`

- [ ] **Крок 1: Написати тести, що падають**

- `provider_key.mjs`: `keyStatusText` для п’яти станів.
- `provider-key.spec.mjs` (сервер специфікацій уже має сховище в пам’яті через тестовий маршрут `/test-secret-store` зі скиданням): для провайдера OpenRouter блок видно, стан «Ключ не задано.»; після введення й «Зберегти ключ» — «Ключ збережено у сховищі Windows.», поле порожнє, значення немає в DOM і в жодній відповіді мережі; «Видалити збережений ключ» повертає «Ключ не задано.»; для локального провайдера блоку немає; зміна назви змінної оновлює стан; перемикання мови перекладає тексти. Перевірити також форму оцінювача й допоміжної класифікації, бо всі три використовують `mountConnection`.

- [ ] **Крок 2: Запустити й побачити падіння** — pytest-обгортка й `cd frontend && npx playwright test provider-key` (з основної теки після локального злиття гілки, як для `build-edition`).

- [ ] **Крок 3: Реалізувати.** Блок монтується з `mountConnection` для провайдерів `openrouter` і `venice`; для `local` і `codex_cli` прихований. Збереження ключа не залежить від збереження форми налаштувань і не позначає її зміненою; поле очищується одразу після запиту незалежно від результату. Недійсна назва змінної в полі — стан не запитується, кнопки вимкнені, підказка «Назва має складатися з великих латинських літер, цифр і підкреслень».

- [ ] **Крок 4: Інструкції.** `install` (uk/en): розділ про ключі — два способи: поле в налаштуваннях (сховище Windows) або `.env`; що має перевагу. `models` і `evaluator`: посилання на новий спосіб замість «лише `.env`». `manual.md`: процедура зі справжнім сховищем Windows (ввести тестовий ключ, побачити запис `Obscura` в «Диспетчері облікових даних», перезапустити застосунок, видалити). `check_site.py --rehash install`, `--rehash models`, `--rehash evaluator`; `check_docs.py` — код 0.

- [ ] **Крок 5: Ручна перевірка зі справжнім сховищем** за процедурою з кроку 4 на тимчасовій теці даних із тестовим значенням; запис після перевірки видалити. Результат — у повідомленні коміту.

- [ ] **Крок 6: Повна перевірка й коміти** — `verify.py` з короткої теки (`state: passed`), Playwright `provider-key`, `settings`-специфікації без регресій; коміти `feat(keys): provider key in connection settings (#30)`, `docs(site): provider key in settings`, `docs(status): …`.

---

## Після задач

1. Наскрізне рев’ю гілки окремим рев’юером із наголосом на «Фокус рев’ю» й на витік значення ключа.
2. Крос-рев’ю (`npx -y @ysilvestrov/detent cross-review --author claude`), таблиця рішень в описі PR.
3. PR на `main` без `Closes #30`; запис у журнал виконання; оновити основну теку.
