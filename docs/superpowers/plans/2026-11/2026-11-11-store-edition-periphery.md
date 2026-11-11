# Видання збірки: інтерфейс, посилання й інструкції — план реалізації (PR 1, периферія)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Мета:** у виданні `store` автор не бачить рівня рейтингу, який сервер відхилить, бачить посилання «Подякувати», «Повідомте про платну версію» й «Поскаржитися на результат», а сайт інструкцій пояснює обмеження.

**Архітектура:** ядро вже є (гілка `claude/store-edition`): `storygen/build_edition.py`, межа на збереженні й перед створенням тексту моделлю, `GET /api/app-info`. Периферія лише читає `max_rating` і три адреси: форми рейтингу фільтрують рівні в браузері, посилання малює сервер у шапці `base.html`. Нових даних і маршрутів немає.

**Стек:** Python 3.12, FastAPI + Jinja2, ES-модулі без фреймворку, pytest, тести JS через `node` (як `tests/web/js/*.mjs`).

**Специфікація:** `docs/superpowers/specs/2026-11/2026-11-11-store-build-design.md` (розділи «Видання», «Обмеження рейтингу», «Документація»); чинна вимога — `SPEC.MD`, BUILD-EDITION-001.

**Наскрізне рев’ю ядра (11.11.2026), з якого виходить цей план:** критичних знахідок немає; виправлено блокування пропозиції метаданих публікації, письма зовнішнього клієнта й позначки-теки. Сюди перенесено відкладене: суворішу перевірку адрес (до того, як інтерфейс почне їх показувати) і тести маршруту рейтингу сцени та повідомлень інших осей. Відкладене для інших PR: перевірка позначки командами `fsck`/`backup`/`restore` і журнал причини (PR 3), перевірка наявності позначки в пакеті (план пакування).

## Загальні обмеження

- Усі обмеження плану ядра (`2026-11-11-store-edition-core.md`, «Загальні обмеження») чинні: назви `build_edition`, межа `store` — `sexual=1`, запуск тестів із worktree через `PYTHONPATH`, нейтральні приклади.
- Поведінка й розмітка видання `full` не змінюються: у шапці немає нових елементів, у формах рейтингу — ті самі три рівні. Наявні тести й браузерні специфікації проходять без правок.
- Посилання відкриваються в новій вкладці з `rel="noopener noreferrer"`; застосунок нічого на них не надсилає й не додає параметрів до адрес.
- Тексти інтерфейсу — ключі в `i18n.json` для `uk` і `en`; сторінки сайту — парою `docs/site/uk` і `docs/site/en` з `python scripts/check_site.py --rehash content-rating`.
- Нові Scenario — у `SPEC.MD` із записами в `docs/verification/traceability.json`; `python scripts/check_docs.py` проходить.

## Фокус рев’ю

1. Твір або сцена вже мають рівень 2 (дані з повного видання): форма показує справжнє значення, а не мовчки підміняє його на 1; зберегти можна лише нижчий рівень (Задача 2).
2. `GET /api/app-info` не відповів (сервер перезапускається): форми рейтингу лишаються робочими з трьома рівнями, а межу однаково тримає сервер (Задача 2).
3. Адреса з пробілом, керівним символом або без хоста (`https://`): позначка відхиляється, посилання не малюється (Задача 1).
4. Перемикання мови інтерфейсу без перезавантаження: підписи посилань і підказка про межу перекладаються разом з рештою сторінки (Задачі 2 і 3).
5. Видання `full` з порожніми адресами: у шапці немає порожнього `<nav>` чи посилань без `href` (Задача 3).

---

### Задача 1: Сувора перевірка адрес і добір тестів ядра

**Файли:**
- Змінити: `src/storygen/build_edition.py` (`load_build_edition`)
- Тест: `tests/test_build_edition.py`, `tests/web/test_rating_routes.py`, `tests/generation/test_content_rating_context.py`

**Інтерфейси:**
- Дає: гарантію для задачі 3 — кожна непорожня адреса в `BuildEdition` має схему `https`, непорожній хост і не містить пробілів чи керівних символів.

- [ ] **Крок 1: Написати тести, що падають**

```python
@pytest.mark.parametrize('url',['https://','https:// example.test','https://example.test/a b','https://exa\nmple.test','HTTPS://example.test/x y'])
def test_link_must_be_a_clean_https_url(tmp_path,url):
    with pytest.raises(ValueError,match='build_edition.json'):
        load_build_edition(write(tmp_path,{'edition':'store','report_url':url}))


def test_clean_https_url_with_path_and_query_is_kept(tmp_path):
    url='https://example.test/form?src=obscura#top'
    assert load_build_edition(write(tmp_path,{'edition':'store','report_url':url})).report_url==url
```

У `tests/web/test_rating_routes.py` — `test_store_edition_put_scene_level_two_is_400`: `PUT /api/scenes/{id}/content-rating` з `sexual=2` у виданні `store` дає 400 з текстом межі; `content_rating: null` дає 200.

У `tests/generation/test_content_rating_context.py` — `test_edition_messages_translate_for_every_axis`: для кожної осі з `AXIS_NAMES` текст `EDITION_LIMIT.format(...)` і `SAVE_LIMIT.format(...)` перекладається `diagnostic(text,'en')` у рядок, що не збігається з українським і містить англійську назву осі (`sexual content`, `violence`, `hard themes`).

- [ ] **Крок 2: Запустити й побачити падіння**

`python -m pytest tests/test_build_edition.py -q -k "clean_https or link_must"` — очікувано: параметри з пробілом, переведенням рядка й порожнім хостом падають (адреса приймається). Два інші тести можуть пройти одразу: вони закріплюють наявну поведінку ядра; якщо проходять — так і записати в журналі.

- [ ] **Крок 3: Реалізувати**

У `load_build_edition`: адреса або порожня, або `urllib.parse.urlsplit(url)` має `scheme == 'https'`, непорожній `hostname`, і в рядку немає символів із `str.isspace()` чи кодом менше 0x20. Причина помилки лишається `адреси мають починатися з https://` з уточненням `і містити хост без пробілів`.

- [ ] **Крок 4: Запустити тести**

`python -m pytest tests/test_build_edition.py tests/web/test_rating_routes.py tests/generation/test_content_rating_context.py -q` — очікувано: усі проходять.

- [ ] **Крок 5: Коміт** — `fix(edition): strict link validation and missing core tests (#30)`.

---

### Задача 2: Форми рейтингу показують лише дозволені рівні

**Файли:**
- Створити: `src/storygen/web/static/app-info.js`
- Змінити: `src/storygen/web/static/rating-settings.js`, `src/storygen/web/static/scene-settings.js`
- Змінити: `src/storygen/web/static/i18n.json` (ключ `rating.edition.hint`)
- Тест: `tests/web/js/app_info.mjs`, `tests/web/test_app_info_ui.py`

**Інтерфейси:**
- Споживає: `GET /api/app-info` → `max_rating: {sexual, violence, themes}`.
- Дає (`app-info.js`):
  - `export function appInfo(): Promise<{edition,max_rating,version,support_url,waitlist_url,report_url}>` — один запит на сторінку (кешований проміс); у разі помилки запиту повертає `{edition:'full',max_rating:{sexual:2,violence:2,themes:2},version:'',support_url:'',waitlist_url:'',report_url:''}` і не показує повідомлення про помилку.
  - `export function allowedLevels(max: number, current: number|null): number[]` — рівні `0..max`, а якщо `current > max` — ще й `current` останнім (щоб форма показувала справжнє значення).
  - `export function limited(maxRating): boolean` — чи є вісь із межею нижче 2.

- [ ] **Крок 1: Написати тести, що падають**

`tests/web/js/app_info.mjs` (запуск як у `tests/web/test_budget_format_ui.py`: `node tests/web/js/app_info.mjs <корінь>`, код виходу 0):

```js
import assert from 'node:assert/strict';
const {allowedLevels,limited}=await import(new URL('src/storygen/web/static/app-info.js',base));
assert.deepEqual(allowedLevels(2,null),[0,1,2]);
assert.deepEqual(allowedLevels(1,0),[0,1]);
assert.deepEqual(allowedLevels(1,1),[0,1]);
assert.deepEqual(allowedLevels(1,2),[0,1,2]);   // наявний рівень 2 лишається видимим
assert.equal(limited({sexual:1,violence:2,themes:2}),true);
assert.equal(limited({sexual:2,violence:2,themes:2}),false);
```

Перед написанням подивитися в сусідньому `.mjs`, як підмінюються `./api.js` та `./i18n.js` для модулів, що їх імпортують; `allowedLevels` і `limited` мають бути чистими й не вимагати підмін.

`tests/web/test_app_info_ui.py`: обгортка pytest для цього `.mjs` за зразком `tests/web/test_budget_format_ui.py`, плюс перевірка джерел: `rating-settings.js` і `scene-settings.js` імпортують `./app-info.js`.

- [ ] **Крок 2: Запустити й побачити падіння**

`python -m pytest tests/web/test_app_info_ui.py -q` — очікувано: модуля `app-info.js` немає.

- [ ] **Крок 3: Реалізувати**

- `rating-settings.js`: у `load()` після отримання твору й `await appInfo()` для кожної осі сховати (`hidden` + `disabled`) варіанти, яких немає в `allowedLevels(max[axis], поточне значення)`. Розмітку `settings.html` не міняти.
- `scene-settings.js`: у `drawRating` цикл рівнів `[0,1,2]` замінити на `allowedLevels(max[axis], значення, яке форма показує для осі)`; `max` береться з уже отриманого `appInfo()` (якщо проміс ще не завершився — три рівні, а після завершення форма перемальовується наявним `refresh`/`drawRating`).
- В обох формах, якщо `limited(max_rating)`, під осями з’являється підказка `rating.edition.hint` через `uiText`: `uk` — `У цьому виданні Obscura найвищий рівень сексуального змісту — {p0}.`; `en` — `In this edition of Obscura the highest sexual content level is {p0}.`. У виданні `full` елемента підказки немає.

- [ ] **Крок 4: Запустити тести**

`python -m pytest tests/web -q` — очікувано: усі проходять, включно з наявними тестами форм рейтингу.

- [ ] **Крок 5: Ручна перевірка у браузері (процедура для traceability)**

Запустити застосунок із тимчасовою позначкою `store` (файл `src/storygen/build_edition.json` у worktree, не комітити), відкрити налаштування твору й рейтинг сцени: рівень 2 сексуального змісту недоступний, підказка видна, інші осі мають три рівні. Вписати рівень 2 напряму в базу тестового твору, перезавантажити: форма показує 2, збереження 2 без змін не дає помилки, збереження 1 проходить. Видалити позначку. Результат записати в повідомлення коміту.

- [ ] **Крок 6: Коміт** — `feat(rating): rating forms follow the build edition limit (#30)`.

---

### Задача 3: Посилання в шапці

**Файли:**
- Змінити: `src/storygen/web/app.py` (глобальна функція шаблонів `app_links`)
- Змінити: `src/storygen/web/templates/base.html`, `src/storygen/web/static/app.css`
- Змінити: `src/storygen/web/static/i18n.json` (ключі `app.link.support`, `app.link.waitlist`, `app.link.report`)
- Тест: `tests/web/test_app_links.py`

**Інтерфейси:**
- Споживає: `build_edition.current()` (адреси вже перевірені задачею 1).
- Дає: глобальну функцію Jinja `app_links() -> list[dict]` з елементами `{'key': 'app.link.support'|'app.link.waitlist'|'app.link.report', 'url': str}` лише для непорожніх адрес, у цьому порядку. Викликається під час кожного рендера (не кешується в `create_app`), щоб фікстура `store_edition` діяла.

- [ ] **Крок 1: Написати тести, що падають**

```python
def page(tmp_path):
    app=create_app(AppSettings(data_dir=tmp_path/'data',env_file=tmp_path/'absent.env'))
    return TestClient(app,base_url='http://127.0.0.1').get('/').text


def test_full_edition_has_no_app_links(tmp_path):
    html=page(tmp_path)
    assert 'app-links' not in html and 'app.link.' not in html


def test_store_edition_shows_report_link_only_when_others_are_empty(tmp_path,store_edition):
    html=page(tmp_path)
    assert html.count('class="app-link"')==1
    assert 'href="https://example.test/report"' in html and 'data-i18n="app.link.report"' in html
    assert 'target="_blank"' in html and 'rel="noopener noreferrer"' in html


def test_all_three_links_in_fixed_order(tmp_path,monkeypatch):
    edition=BuildEdition(edition='store',support_url='https://example.test/s',waitlist_url='https://example.test/w',report_url='https://example.test/r')
    monkeypatch.setattr(build_edition,'current',lambda:edition)
    html=page(tmp_path)
    assert html.index('app.link.support')<html.index('app.link.waitlist')<html.index('app.link.report')


def test_link_labels_are_translated(tmp_path,store_edition):
    app=create_app(AppSettings(data_dir=tmp_path/'data',env_file=tmp_path/'absent.env'))
    english=TestClient(app,base_url='http://127.0.0.1').get('/',headers={'accept-language':'en'}).text
    assert 'Report a result' in english
```

- [ ] **Крок 2: Запустити й побачити падіння**

`python -m pytest tests/web/test_app_links.py -q` — очікувано: падають три тести видання `store` (посилань немає).

- [ ] **Крок 3: Реалізувати**

- У `base.html` усередині `<header class="topbar">` перед `<nav class="locale-switch">`: `{% set links=app_links() %}{% if links %}<nav class="app-links" …>` з `<a class="app-link" href="{{ link.url }}" target="_blank" rel="noopener noreferrer" data-i18n="{{ link.key }}">{{ t(link.key) }}</a>` на кожне посилання. `aria-label` навігації — ключ `app.link.group`.
- Тексти: `app.link.support` — «Подякувати авторові» / `Support the author`; `app.link.waitlist` — «Повідомте про платну версію» / `Notify me about the paid version`; `app.link.report` — «Поскаржитися на результат» / `Report a result`; `app.link.group` — «Посилання застосунку» / `App links`.
- `app.css`: посилання в один рядок із наявним перемикачем мови, на вузькому екрані переносяться під бренд; використати наявні змінні кольорів і відступів шапки, без нових кольорів.

- [ ] **Крок 4: Запустити тести**

`python -m pytest tests/web -q` — очікувано: усі проходять.

- [ ] **Крок 5: Коміт** — `feat(edition): support, waitlist and report links in the header (#30)`.

---

### Задача 4: SPEC, сайт інструкцій, перевірка

**Файли:**
- Змінити: `SPEC.MD`, `docs/verification/traceability.json`
- Змінити: `docs/site/uk/content-rating.md`, `docs/site/en/content-rating.md` (і хеш пари)

**Інтерфейси:** споживає поведінку задач 1–3; нового коду немає.

- [ ] **Крок 1: `SPEC.MD` і traceability**

До BUILD-EDITION-001 додати:
- `BUILD-EDITION-001-S06 — Форми рейтингу`: GIVEN видання `store`; WHEN автор відкриває рейтинг твору чи сцени; THEN рівні вище за межу недоступні й видно підказку про межу; AND наявне значення вище за межу лишається видимим і його можна лише знизити; AND якщо `/api/app-info` недоступний, форма показує всі рівні, а межу тримає сервер. Тести: `tests/web/test_app_info_ui.py` (вузли), ручна процедура з кроку 5 задачі 2 з причиною «браузерна специфікація не запускає сервер у виданні `store`».
- `BUILD-EDITION-001-S07 — Посилання застосунку`: GIVEN позначка з адресами; WHEN рендериться сторінка; THEN у шапці є посилання лише для непорожніх адрес у порядку подяка, запис, скарга, у новій вкладці; AND у виданні `full` без адрес шапка не змінюється; AND адреса не `https`, без хоста чи з пробілами зупиняє запуск. Тести: `tests/web/test_app_links.py`, нові вузли `tests/test_build_edition.py`.
- У технічному описі: `app-info.js`, `app_links()`, правило перевірки адрес, ключі i18n.
- У S02/S03 дописати вузли тестів із задачі 1.

Перевірка: `python scripts/check_docs.py` — код виходу 0.

- [ ] **Крок 2: Сторінка сайту «Віковий рейтинг» (uk і en)**

Новий розділ перед «Обмеження»: «Збірка з Microsoft Store» / “Microsoft Store build”. Зміст: у цій збірці найвищий рівень сексуального змісту — 1; рівні насильства й жорстких тем не обмежено; твір із рівнем 2, перенесений з іншої збірки, можна читати, редагувати вручну й експортувати, а щоб модель писала далі — знизити рейтинг; оцінювання й перевірки наявного тексту працюють; посилання «Поскаржитися на результат» у шапці. Без знімків екрана: у повному виданні інтерфейс не змінюється.

Перевірка: `python scripts/check_site.py --rehash content-rating`, потім `python scripts/check_docs.py` — код виходу 0.

- [ ] **Крок 3: Повна перевірка й коміт**

`python scripts/verify.py` з короткого worktree на коміті гілки (не міняти коміт у теці перевірки, поки прогін триває) — очікувано `state: passed`. Скопіювати `docs/STATUS.md`; коміти `docs(spec): BUILD-EDITION-001 interface scenarios and Store section of the rating guide (#30)` і `docs(status): …`. У повідомленні: оновлено `docs/site/{uk,en}/content-rating.md`.

---

## Після периферії

1. Наскрізне рев’ю гілки окремим рев’юером.
2. Крос-рев’ю (`npx -y @ysilvestrov/detent cross-review --author claude`, у фоні), таблиця рішень в описі PR.
3. PR на `main` без `Closes #30` (це не останній PR задачі); оновити основну теку.
