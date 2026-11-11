# Видання збірки й межа рейтингу — план реалізації (PR 1, ядро)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Мета:** застосунок знає своє видання (`full` або `store`), і у виданні `store` сервер не дає зберегти рівень 2 сексуального змісту та блокує генерацію для сцен із таким рейтингом.

**Архітектура:** один модуль `storygen/build_edition.py` читає файл-позначку з пакета й віддає незмінний `BuildEdition` з межею рейтингу. Збереження рейтингу (`storage/authoring.py`) і запобіжник перед генерацією (`rating/guard.py`) питають межу в цього модуля. `GET /api/app-info` віддає видання, межу й адреси посилань інтерфейсу. Без файла-позначки все працює, як тепер.

**Стек:** Python 3.12, pydantic 2, FastAPI, pytest.

**Специфікація:** `docs/superpowers/specs/2026-11/2026-11-11-store-build-design.md` (розділи «Видання» та «Обмеження рейтингу»).

**Поза цим планом (план периферії PR 1, пишеться після наскрізного рев’ю ядра):** інтерфейс рейтингу, що ховає недоступні рівні; посилання «Подякувати», «Повідомте про платну версію», «Поскаржитися на результат»; сторінки сайту `docs/site/{uk,en}/`. `instance_id` в `/api/app-info` належить PR 3.

## Загальні обмеження

- Назви: модуль `storygen/build_edition.py`, файл-позначка `storygen/build_edition.json`. Слово `edition` у коді вже означає видання книги (`edition_id` у публікації), тому для збірки завжди `build_edition`.
- Межа видання `store`: `sexual=1`, `violence=2`, `themes=2`. Межа видання `full`: усі осі 2.
- Файла-позначки немає в репозиторії; у цьому PR його ніхто не створює, окрім тестів у тимчасових теках.
- Поведінка видання `full` не змінюється: усі наявні тести проходять без правок.
- Нові авторські повідомлення мають ключі в `src/storygen/web/static/i18n.json` для `uk` і `en`.
- Мова документації — українська; маркери OpenSpec англійською. Кожен новий Scenario має запис у `docs/verification/traceability.json`; перевірка — `python scripts/check_docs.py`.
- Запуск тестів із worktree: `PYTHONPATH="<корінь worktree>/src;<корінь worktree>"` (Windows-шляхи, `pwd -W`), інтерпретатор `C:\Projects\text-generator\.venv\Scripts\python.exe`, `--basetemp` у `C:\tmp\<назва>`. Повний `scripts/verify.py` — з короткого worktree на кшталт `C:\tmp\<назва>`.
- У тестах і прикладах лише нейтральні тексти.

## Фокус рев’ю

1. Файл-позначка пошкоджений, з невідомим виданням або зайвими ключами: застосунок не стартує з авторським повідомленням, а не стає мовчки повним виданням (Задача 1).
2. Твір із рейтингом 2, створений у повному виданні й відкритий у виданні `store`: читається й редагується вручну, рейтинг можна знизити, генерація заблокована (Задачі 2 і 3).
3. Сцена без власного рейтингу успадковує рівень 2 від твору: генерація заблокована за чинним рейтингом (Задача 3).
4. Етап без сцени (підготовка плану твору) для твору з рівнем 2: теж заблокований (Задача 3).
5. Адреса посилання не `https://` (наприклад `javascript:`): файл-позначка відхиляється (Задача 1).

---

### Задача 1: Модуль видання збірки

**Файли:**
- Створити: `src/storygen/build_edition.py`
- Тест: `tests/test_build_edition.py`
- Змінити: `tests/conftest.py` (фікстура `store_edition`)

**Інтерфейси:**
- Дає:
  - `class BuildEdition(DomainModel)`: `edition: Literal['full','store']='full'`, `support_url: str=''`, `waitlist_url: str=''`, `report_url: str=''`; властивість `max_rating -> ContentRating`.
  - `load_build_edition(path: Path | None = None) -> BuildEdition` — `None` означає файл `build_edition.json` у пакеті `storygen`.
  - `current() -> BuildEdition` — кешований результат `load_build_edition()`.
  - `over_limit(rating: ContentRating) -> list[str]` — осі, де `rating` перевищує `current().max_rating`, у порядку `AXES`.
  - Фікстура pytest `store_edition`: підміняє `storygen.build_edition.current` на видання `store` з `report_url='https://example.test/report'`.
- Правило для споживачів: викликати `build_edition.current()` через атрибут модуля (`from .. import build_edition`), не імпортувати `current` іменем, інакше фікстура не діє.

- [ ] **Крок 1: Написати тести, що падають**

```python
import json
import pytest
from storygen import build_edition
from storygen.build_edition import BuildEdition, load_build_edition
from storygen.domain import ContentRating

REPORT='https://example.test/report'


def write(tmp_path,data):
    path=tmp_path/'build_edition.json';path.write_text(json.dumps(data),encoding='utf-8');return path


def test_no_marker_file_is_full_edition(tmp_path):
    loaded=load_build_edition(tmp_path/'absent.json')
    assert loaded==BuildEdition() and loaded.edition=='full'
    assert loaded.max_rating==ContentRating(sexual=2,violence=2,themes=2)


def test_repository_ships_without_marker():
    assert build_edition.current().edition=='full'


def test_store_edition_caps_only_sexual(tmp_path):
    loaded=load_build_edition(write(tmp_path,{'edition':'store','report_url':REPORT,'support_url':'https://example.test/s'}))
    assert loaded.max_rating==ContentRating(sexual=1,violence=2,themes=2)
    assert (loaded.support_url,loaded.waitlist_url)==('https://example.test/s','')


def test_store_edition_requires_report_url(tmp_path):
    with pytest.raises(ValueError,match='report_url'):
        load_build_edition(write(tmp_path,{'edition':'store'}))


@pytest.mark.parametrize('data',[{'edition':'pro'},{'edition':'store','report_url':REPORT,'extra':1},
    {'edition':'store','report_url':'javascript:alert(1)'},{'edition':'full','support_url':'http://example.test'},[]])
def test_invalid_marker_is_rejected_not_ignored(tmp_path,data):
    with pytest.raises(ValueError,match='build_edition.json'):
        load_build_edition(write(tmp_path,data))


def test_broken_json_is_rejected(tmp_path):
    path=tmp_path/'build_edition.json';path.write_text('{',encoding='utf-8')
    with pytest.raises(ValueError,match='build_edition.json'):
        load_build_edition(path)


def test_over_limit_lists_axes(store_edition):
    assert build_edition.over_limit(ContentRating(sexual=2,violence=2,themes=2))==['sexual']
    assert build_edition.over_limit(ContentRating(sexual=1,violence=2,themes=2))==[]
```

- [ ] **Крок 2: Запустити й побачити падіння**

`python -m pytest tests/test_build_edition.py -q` — очікувано: помилка імпорту `storygen.build_edition`.

- [ ] **Крок 3: Реалізувати `src/storygen/build_edition.py` і фікстуру**

Рішення, яких тести не визначають:
- Усі помилки файла — `ValueError` з текстом `Некоректний файл видання build_edition.json: <причина>`; причина для відсутньої адреси скарг — `видання для Store потребує report_url`. У тексті немає вмісту файла.
- Адреса або порожня, або починається з `https://`.
- `current()` кешується `functools.lru_cache(maxsize=1)`; `over_limit` використовує наявну `rating.levels.higher_axes(rating, current().max_rating)`.
- Фікстура `store_edition` у `tests/conftest.py` робить `monkeypatch.setattr(build_edition,'current',lambda: BuildEdition(edition='store',report_url='https://example.test/report'))`.

- [ ] **Крок 4: Запустити тести**

`python -m pytest tests/test_build_edition.py -q` — очікувано: усі проходять.

- [ ] **Крок 5: Коміт**

`git add src/storygen/build_edition.py tests/test_build_edition.py tests/conftest.py` і коміт `feat(edition): build edition marker with rating limit (#30)`. У повідомленні: «User docs: no change needed, no visible behaviour yet».

---

### Задача 2: Межа під час збереження рейтингу

**Файли:**
- Змінити: `src/storygen/storage/authoring.py` (`update_story_rating`, `update_scene_rating`)
- Змінити: `src/storygen/web/static/i18n.json` (ключ `rating.edition.save_limit`, `uk` і `en`)
- Тест: `tests/storage/test_content_rating.py`, `tests/web/test_rating_routes.py`

**Інтерфейси:**
- Споживає: `build_edition.over_limit(rating) -> list[str]`, `build_edition.current().max_rating`, фікстуру `store_edition`; `rating.instructions.AXIS_NAMES` для назви осі.
- Дає: текст відмови `SAVE_LIMIT='У цьому виданні Obscura рівень {n} для осі «{axis}» недоступний: найвищий дозволений — {max}.'` (константа в `storage/authoring.py`), де `axis` — назва з `AXIS_NAMES`, перша вісь зі списку `over_limit`.

- [ ] **Крок 1: Написати тести, що падають**

У `tests/storage/test_content_rating.py` (допоміжні функції створення твору й сцени взяти з цього файла):

```python
LIMIT='У цьому виданні Obscura рівень 2 для осі «сексуальний зміст» недоступний: найвищий дозволений — 1.'


def test_store_edition_rejects_story_level_two(tmp_path,store_edition):
    repo,story=...  # наявний помічник файла, твір без рейтингу
    with pytest.raises(ValueError) as error:
        repo.update_story_rating(story.id,ContentRating(sexual=2,violence=0,themes=0),story.revision)
    assert str(error.value)==LIMIT
    assert repo.get_story(story.id).revision==story.revision and repo.get_story(story.id).content_rating is None


def test_store_edition_rejects_scene_level_two_and_allows_inherit(tmp_path,store_edition):
    # сцена: рівень 2 відхилено тим самим текстом; None («як у твору») і sexual=1 приймаються
    ...


def test_store_edition_keeps_other_axes_at_two(tmp_path,store_edition):
    # ContentRating(sexual=1,violence=2,themes=2) зберігається


def test_store_edition_lets_lower_an_existing_level_two(tmp_path,store_edition):
    # твір із sexual=2, записаний напряму в базу (як rated_stories_by_default у conftest):
    # повторне збереження того самого рейтингу повертає твір без помилки й без зміни revision;
    # зниження до sexual=1 приймається


def test_full_edition_still_accepts_level_two(tmp_path):
    # без фікстури ContentRating(sexual=2,violence=2,themes=2) зберігається
```

У `tests/web/test_rating_routes.py`:

```python
def test_store_edition_put_level_two_is_400_with_translation(tmp_path,store_edition):
    client,repo,story,_=make(tmp_path)
    body={"content_rating":{"sexual":2,"violence":0,"themes":0},"expected_revision":story.revision}
    response=client.put(f"/api/stories/{story.id}/content-rating",json=body)
    assert response.status_code==400 and response.json()["detail"]==LIMIT
    english=client.put(f"/api/stories/{story.id}/content-rating",json=body,headers={"accept-language":"en"})
    assert english.json()["detail"]=="In this edition of Obscura, level 2 is not available for “sexual content”: the highest allowed is 1."
```

Перед написанням перевірити в `web/app.py`, що `ValueError` маршруту дає 400; якщо код інший, у тесті стоїть фактичний код наявного обробника.

- [ ] **Крок 2: Запустити й побачити падіння**

`python -m pytest tests/storage/test_content_rating.py tests/web/test_rating_routes.py -q -k "edition"` — очікувано: нові тести `store_edition` падають, бо рейтинг зберігається.

- [ ] **Крок 3: Реалізувати**

- В обох функціях перевірка стоїть після порівняння `revision` і після раннього повернення «рейтинг не змінився», до запису: якщо `rating is not None` і `build_edition.over_limit(rating)` непорожній — `ValueError(SAVE_LIMIT.format(...))`.
- У `i18n.json`: `"rating.edition.save_limit"` — `uk`: `У цьому виданні Obscura рівень {p0} для осі «{p1}» недоступний: найвищий дозволений — {p2}.`; `en`: `In this edition of Obscura, level {p0} is not available for “{p1}”: the highest allowed is {p2}.`. Назва осі в англійській відповіді має бути англійською: перевірити, як `diagnostic` перекладає параметр-назву осі в `rating.guard.*`, і зробити так само (за потреби — запис у `_LIST_PARAMS` або окремі ключі назв осей).

- [ ] **Крок 4: Запустити тести**

`python -m pytest tests/storage tests/web/test_rating_routes.py -q` — очікувано: усі проходять.

- [ ] **Крок 5: Коміт**

`fix`-коміт не потрібен; коміт `feat(rating): edition limit when saving a rating (#30)`.

---

### Задача 3: Межа перед генерацією

**Файли:**
- Змінити: `src/storygen/rating/guard.py` (`enforce_rating`)
- Змінити: `src/storygen/web/static/i18n.json` (ключ `rating.edition.guard_limit`)
- Тест: `tests/generation/test_content_rating_context.py`

**Інтерфейси:**
- Споживає: `build_edition.over_limit`, `build_edition.current().max_rating`, `store_edition`, `AXIS_NAMES`.
- Дає: `EDITION_LIMIT='Генерацію заблоковано: рейтинг «{axis}» тут {n}, а в цьому виданні Obscura найвищий дозволений рівень — {max}. Знизьте рейтинг сцени або твору.'` у `rating/guard.py`.

- [ ] **Крок 1: Написати тести, що падають**

Використати помічники файла (`R`, створення твору й сцени, `make_context`/`build_context`):

```python
EDITION='Генерацію заблоковано: рейтинг «сексуальний зміст» тут 2, а в цьому виданні Obscura найвищий дозволений рівень — 1. Знизьте рейтинг сцени або твору.'


def test_store_edition_blocks_scene_with_own_level_two(tmp_path,store_edition):
    # твір R(0,0,0), сцена R(2,0,0), записані напряму в базу; будь-який етап сцени -> ValueError(EDITION)


def test_store_edition_blocks_scene_inheriting_level_two(tmp_path,store_edition):
    # твір R(2,0,0), сцена без власного рейтингу -> ValueError(EDITION)


def test_store_edition_blocks_story_stage_without_scene(tmp_path,store_edition):
    # твір R(2,0,0), етап без сцени (той самий, що в наявному тесті незаданого рейтингу) -> ValueError(EDITION)


def test_store_edition_limit_comes_before_cast_checks(tmp_path,store_edition):
    # сцена R(2,0,0) з порожнім складом: текст EDITION, а не EMPTY_CAST


def test_store_edition_allows_level_one_and_other_axes(tmp_path,store_edition):
    # сцена R(1,2,2) з дорослим учасником: контекст будується


def test_store_edition_does_not_block_reading_or_manual_edit(tmp_path,store_edition):
    # твір R(2,0,0): repo.get_story, збереження ручної версії прози й list_scenes працюють


def test_full_edition_level_two_unchanged(tmp_path):
    # без фікстури сцена R(2,0,0) з дорослим учасником будує контекст, як і раніше
```

- [ ] **Крок 2: Запустити й побачити падіння**

`python -m pytest tests/generation/test_content_rating_context.py -q -k edition` — очікувано: тести `store_edition` падають (помилки немає або текст інший).

- [ ] **Крок 3: Реалізувати**

У `enforce_rating` одразу після перевірки `UNSET` і до повернення для несценових етапів: `rating = effective_rating(story,scene) if scene is not None else story.content_rating`; якщо `build_edition.over_limit(rating)` непорожній — `ValueError(EDITION_LIMIT.format(...))` для першої осі. Оновити docstring порядку перевірок. Ключ `rating.edition.guard_limit` в `i18n.json` для `uk` і `en` (`Generation is blocked: the “{p0}” rating here is {p1}, and the highest level allowed in this edition of Obscura is {p2}. Lower the rating of the scene or the story.`).

- [ ] **Крок 4: Запустити тести**

`python -m pytest tests/generation tests/storage -q` — очікувано: усі проходять.

- [ ] **Крок 5: Коміт**

`feat(rating): edition limit before generation (#30)`.

---

### Задача 4: `GET /api/app-info`, запуск із некоректною позначкою, SPEC

**Файли:**
- Створити: `src/storygen/web/routes_app_info.py`
- Змінити: `src/storygen/web/app.py` (реєстрація маршруту; виклик `build_edition.current()` на початку `create_app`)
- Змінити: `SPEC.MD`, `docs/verification/traceability.json`
- Змінити: `docs/superpowers/specs/2026-11/2026-11-11-store-build-design.md` (технічні назви, див. крок 5)
- Тест: `tests/web/test_app_info.py`

**Інтерфейси:**
- Споживає: `build_edition.current()`.
- Дає: `GET /api/app-info` → `{"edition": "full"|"store", "max_rating": {"sexual": int, "violence": int, "themes": int}, "version": str, "support_url": str, "waitlist_url": str, "report_url": str}`. `version` — `importlib.metadata.version('storygen')`, а якщо метаданих немає — `'0.0.0'`. План периферії читає саме ці поля.

- [ ] **Крок 1: Написати тести, що падають**

```python
def test_app_info_full_edition(tmp_path):
    info=client(tmp_path).get('/api/app-info').json()
    assert info['edition']=='full' and info['max_rating']=={'sexual':2,'violence':2,'themes':2}
    assert set(info)=={'edition','max_rating','version','support_url','waitlist_url','report_url'}
    assert info['support_url']==info['waitlist_url']==info['report_url']==''


def test_app_info_store_edition(tmp_path,store_edition):
    info=client(tmp_path).get('/api/app-info').json()
    assert info['edition']=='store' and info['max_rating']=={'sexual':1,'violence':2,'themes':2}
    assert info['report_url']=='https://example.test/report'


def test_app_does_not_start_with_invalid_marker(tmp_path,monkeypatch):
    def broken():raise ValueError('Некоректний файл видання build_edition.json: видання для Store потребує report_url')
    monkeypatch.setattr(build_edition,'current',broken)
    with pytest.raises(ValueError,match='report_url'):
        create_app(AppSettings(data_dir=tmp_path/'data',env_file=tmp_path/'absent.env'))
    assert not (tmp_path/'data').exists()
```

`client(tmp_path)` — як `make` у `tests/web/test_rating_routes.py`.

- [ ] **Крок 2: Запустити й побачити падіння**

`python -m pytest tests/web/test_app_info.py -q` — очікувано: 404 для маршруту; третій тест падає, бо `create_app` не читає видання.

- [ ] **Крок 3: Реалізувати маршрут і ранню перевірку**

`create_app` викликає `build_edition.current()` першим рядком, до створення `Repository`, щоб некоректна позначка не створювала теку даних.

- [ ] **Крок 4: Оновити `SPEC.MD` і traceability**

Нова вимога після RATING-002, з якорями й записом у змісті:

- `### Requirement: BUILD-EDITION-001 — Видання збірки й межа рейтингу`: без файла-позначки застосунок SHALL бути повним виданням із незмінною поведінкою; видання `store` SHALL обмежувати сексуальний зміст рівнем 1 під час збереження рейтингу й перед генерацією; некоректна позначка або `store` без `report_url` SHALL зупиняти запуск; `/api/app-info` SHALL віддавати видання, межу й адреси без секретів. Вказати, що читання, ручне редагування й експорт не обмежуються і що фільтра згенерованого тексту немає.
- Scenario: `BUILD-EDITION-001-S01` (немає позначки — повне видання), `-S02` (збереження рівня 2 у `store` відхилено, зниження наявного рівня 2 дозволено), `-S03` (генерацію для чинного рівня 2 заблоковано: власний рейтинг сцени, успадкований, етап без сцени), `-S04` (некоректна позначка зупиняє запуск), `-S05` (`/api/app-info`).
- Технічний опис у розділі Architecture поруч з абзацом «Збирання контексту й віковий рейтинг»: модуль, порядок перевірок у `enforce_rating`, ключі i18n.
- У `traceability.json` — по запису на кожен Scenario з тестами задач 1–4 (точні вузли pytest).

Перевірка: `python scripts/check_docs.py` — очікувано: повідомлення про узгодженість, код виходу 0.

- [ ] **Крок 5: Узгодити назви в специфікації зміни**

У `2026-11-11-store-build-design.md`, розділ «Видання»: `AppSettings.edition` і `storygen/edition.json` замінити на модуль `storygen/build_edition.py` і файл `storygen/build_edition.json` з приміткою про причину (слово `edition` зайняте публікацією). Розділ власника не змінюється, тож повторне затвердження не потрібне.

- [ ] **Крок 6: Повна перевірка й коміт**

`python scripts/verify.py` з короткого worktree на коміті гілки; очікувано: `state: passed`. Скопіювати `docs/STATUS.md`, коміт `feat(edition): app info endpoint and BUILD-EDITION-001 (#30)` і окремий `docs(status): …`. У повідомленні коміту: «User docs: site pages follow in the periphery plan of this PR».

---

## Після ядра

1. Наскрізне рев’ю ядра (гілка цілком, не по задачах); висновки записати.
2. План периферії PR 1: інтерфейс рейтингу за `max_rating`, три посилання, сторінки сайту `uk`/`en` з `python scripts/check_site.py --rehash <slug>`.
3. Крос-рев’ю гілки (`detent cross-review --author claude`) і PR на `main` — після периферії; у цьому PR `Closes #30` не ставити, бо це не останній PR задачі.
