# Віковий рейтинг: перевизначення сцени, позначка експорту й документація (#28, PR 2) — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Автор перевизначає віковий рейтинг сцени в інтерфейсі, експорт FB2/EPUB отримує вікову позначку, а користувацька документація й Умови описують рейтинг і запобіжник.

**Architecture:** Ядро (PR #46, злито в main 36e7ab2) уже має моделі, `PUT /api/scenes/{id}/content-rating`, `rating/levels.py` і запобіжник. Цей PR додає чисту функцію `age_label` у `rating/levels.py` і поле `Book.age_rating` у знімку експорту, яке FB2/EPUB записують у метадані. Відповідь `GET /api/stories/{id}` віддає ефективний рейтинг кожної сцени з джерелом, а панель «Параметри сцени» отримує окрему форму рейтингу. Документація та SPEC оновлюються останньою задачею.

**Tech Stack:** Python 3 / FastAPI / pydantic, ElementTree (FB2 з XSD, EPUB OPF), ванільний JS-модуль з `i18n.js`, pytest, Playwright (`frontend/playwright.config.mjs`, проєкти desktop і mobile).

**Spec:** `docs/superpowers/specs/2026-11/content-rating.md` (затверджено 09.11.2026): розділи «Експорт», «Інтерфейс», «Документація користувача», «API» (останній пункт).

## Global Constraints

- Вікова позначка: найвищий рівень серед рейтингу твору та ефективних рейтингів сцен експорту, за всіма осями: 0 → `0+`, 1 → `16+`, 2 → `18+`. Рейтинг твору не задано → позначки немає.
- FB2: `<custom-info info-type="age-rating">18+</custom-info>` у `description`; EPUB: `<meta property="obscura:age-rating">18+</meta>` у `metadata`.
- Попередження експорту без рейтингу: «Віковий рейтинг твору не задано; позначку не додано». Воно MUST NOT зупиняти експорт і MUST NOT робити `manifest.complete` хибним (поправка під час планування: експорт працює без рейтингу).
- Перевизначення сцени: `null` означає «як у твору»; запис лише через наявний `PUT /api/scenes/{scene_id}/content-rating` з `{story_id, content_rating, expected_revision}`.
- Нові рядки інтерфейсу — у `src/storygen/web/static/i18n.json`, UA та EN, з точними текстами з таблиці в Task 2.
- Робоча база `data/storygen.sqlite3` не використовується; тексти творів не друкуються. Формат карток персонажів не змінюється.
- Кожен новий Scenario має сталий ID і запис у `docs/verification/traceability.json`; `python scripts/check_docs.py` без помилок.
- Тести: `PYTHONPATH=src C:/Projects/text-generator/.venv/Scripts/python -m pytest` з кореня worktree. Повний `scripts/verify.py` запускається з абсолютним `PYTHONPATH=<worktree>\src` (підпроцеси інакше імпортують основну теку) і з короткого шляху (MAX_PATH).

## Review Focus

1. Твір без рейтингу експортується як раніше: файл є, `complete` не змінюється, позначки немає (Task 1: `test_unrated_story_exports_without_label_and_stays_complete`).
2. Сцена з власним рейтингом вищим за твір піднімає позначку всього експорту (Task 1: `test_scene_override_raises_export_label`).
3. Повернення сцени до «як у твору» надсилає `null`, а не копію рейтингу твору: інакше подальша зміна твору сцену не зачепить (Task 2: перевірка тіла PUT у Playwright).
4. Сцена, рейтинг якої змінено в іншій вкладці, отримує 409 і не перезаписує його мовчки (Task 2: `test_story_view_reports_effective_ratings` перевіряє ревізію; Playwright — notice помилки після застарілої ревізії).
5. Твір без рейтингу: у параметрах сцени варіант «як у твору» показує «не задано», а форма зберігає власний рейтинг сцени (Task 2, Playwright).

---

### Task 1: Вікова позначка експорту FB2/EPUB

**Files:**
- Modify: `src/storygen/rating/levels.py`
- Modify: `src/storygen/publication/book.py` (`Book`, `capture`)
- Modify: `src/storygen/publication/fb2.py` (блок `custom-info`, ~рядок 59)
- Modify: `src/storygen/publication/epub.py` (`render`, після `obscura:source-language`)
- Modify: `src/storygen/application/exports.py` (`manifest`)
- Test: `tests/storage/test_content_rating.py` (для `age_label`), `tests/authoring/test_ebook_exports.py`

**Interfaces:**
- Consumes: `effective_rating(story, scene) -> ContentRating | None`, `AXES` з `rating/levels.py`; `PublicationSnapshot.story`, `.scenes: list[tuple[Scene, VersionRef | None]]`.
- Produces: `age_label(story: Story, scenes: Iterable[Scene]) -> str | None` у `rating/levels.py`; `Book.age_rating: str | None` (нове поле з типовим `None`, останнім у dataclass); `RATING_UNSET_EXPORT = 'Віковий рейтинг твору не задано; позначку не додано'` у `publication/book.py`.

- [ ] **Step 1: Write the failing tests**

У `tests/storage/test_content_rating.py`:

```python
def test_age_label_takes_highest_level_over_story_and_scenes():
    story = Story(title='T', content_rating=R(0, 0, 0))
    assert age_label(Story(title='T'), []) is None
    assert age_label(story, []) == '0+'
    assert age_label(story, [Scene(story_id=story.id, title='a', position=0, content_rating=R(0, 1, 0))]) == '16+'
    assert age_label(story.model_copy(update={'content_rating': R(0, 0, 2)}), [Scene(story_id=story.id, title='a', position=0)]) == '18+'
```

(побудуйте `Story`/`Scene` так, як це вже роблять тести цього файла; `R` — наявний або локальний помічник `ContentRating(sexual=, violence=, themes=)`).

У `tests/authoring/test_ebook_exports.py` (`seeded()` дає твір R(0,0,0) через autouse-фікстуру conftest):

```python
@pytest.mark.parametrize('format', ['fb2', 'epub'])
def test_scene_override_raises_export_label(tmp_path, format):
    repo, story = seeded(tmp_path, count=2, cover=False)
    scene = repo.list_scenes(story.id)[1]
    repo.update_scene_rating(scene.id, ContentRating(sexual=2, violence=0, themes=0), scene.revision)
    path = export_story(repo, story.id, format)
    assert age_rating_of(path, format) == '18+'
    manifest = json.loads(path.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    assert manifest['age_rating'] == '18+' and manifest['complete']

@pytest.mark.parametrize('format', ['fb2', 'epub'])
@pytest.mark.unrated_stories
def test_unrated_story_exports_without_label_and_stays_complete(tmp_path, format):
    repo, story = seeded(tmp_path, count=1, cover=False)
    path = export_story(repo, story.id, format)
    assert age_rating_of(path, format) is None
    manifest = json.loads(path.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    assert manifest['complete'] and manifest['age_rating'] is None
    assert manifest['warnings'] == ['Віковий рейтинг твору не задано; позначку не додано']
```

`age_rating_of(path, format)` — помічник у цьому тестовому файлі: для FB2 шукає `f:description/f:custom-info[@info-type="age-rating"]`, для EPUB — `meta[@property="obscura:age-rating"]` у `EPUB/package.opf`; повертає текст або `None`. До наявного `test_seven_scene_ebooks_metadata_plaintext_and_manifest` додайте `assert age_rating_of(path, format) == '0+'`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src C:/Projects/text-generator/.venv/Scripts/python -m pytest tests/storage/test_content_rating.py tests/authoring/test_ebook_exports.py -q`
Expected: FAIL (`age_label` не існує; позначки немає в метаданих).

- [ ] **Step 3: Implement**

- `age_label`: повертає `None`, якщо `story.content_rating is None`; інакше бере максимум рівнів за `AXES` серед `story.content_rating` і `effective_rating(story, scene)` кожної сцени та відображає `{0: '0+', 1: '16+', 2: '18+'}`.
- `capture`: `age_rating=age_label(snapshot.story, [scene for scene, _ in snapshot.scenes])`. Позначка не впливає на `warnings` і на зупинку `allow_incomplete`.
- FB2: після циклу `publisher/isbn/rights` додайте `custom-info` з `info-type="age-rating"`, якщо `book.age_rating`. XSD-валідація `validate(result)` має проходити.
- EPUB: `add(metadata, 'meta', book.age_rating, property='obscura:age-rating')`, якщо `book.age_rating`.
- `exports.py`: у `manifest` додайте `'age_rating': book.age_rating`; `'warnings'` дорівнює `list(book.warnings) + ([RATING_UNSET_EXPORT] if book.age_rating is None else [])`. `'complete'` лишається `not book.warnings`.

- [ ] **Step 4: Run tests to verify they pass**

Run: та сама команда, плюс `tests/authoring` повністю.
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/storygen/rating/levels.py src/storygen/publication/book.py src/storygen/publication/fb2.py src/storygen/publication/epub.py src/storygen/application/exports.py tests/storage/test_content_rating.py tests/authoring/test_ebook_exports.py
git commit -m "feat(rating): age label in FB2/EPUB exports (#28)"
```

---

### Task 2: Ефективний рейтинг у відповіді твору й перевизначення в параметрах сцени

**Files:**
- Modify: `src/storygen/web/routes_stories.py` (`story_view`)
- Modify: `src/storygen/web/static/scene-settings.js`
- Modify: `src/storygen/web/static/i18n.json` (UA-блок біля `rating.*` ~рядок 2082, EN-блок ~рядок 4164)
- Modify: `tests/web/browser/server.py` (фікстура, якщо наявних не вистачає)
- Test: `tests/web/test_rating_routes.py`, нова `tests/web/browser/scene-rating.spec.mjs`

**Interfaces:**
- Consumes: `effective_rating` з `rating/levels.py`; `PUT /api/scenes/{scene_id}/content-rating`; `state.view`, `state.scene`, `refresh()` з `editor.js`; `t`, `msg`, `uiText`, `uiHTML` з `i18n.js`.
- Produces: поле відповіді `GET /api/stories/{id}` `scene_ratings: {scene_id: {"effective": ContentRating | None, "source": "scene" | "story" | None}}`. Тут `source` має значення `"scene"`, коли в сцени є власний рейтинг, `"story"`, коли успадковано заданий рейтинг твору, і `None`, коли обидва не задані.

Тексти інтерфейсу (ключі й значення — точно):

| Ключ | UA | EN |
|---|---|---|
| `rating.scene.legend` | Віковий рейтинг сцени | Scene age rating |
| `rating.scene.inherit` | Як у твору ({p0}) | Same as the story ({p0}) |
| `rating.scene.own` | Власний рейтинг | Own rating |
| `rating.scene.summary` | сексуальний зміст {p0}, насильство {p1}, жорсткі теми {p2} | sexual content {p0}, violence {p1}, hard themes {p2} |
| `rating.scene.hint` | Пониження рейтингу позначає матеріали сцени застарілими; підвищення — ні. | Lowering the rating marks the scene’s materials as outdated; raising it does not. |
| `rating.scene.save` | Зберегти рейтинг сцени | Save scene rating |
| `rating.scene.saved` | Рейтинг сцени збережено | Scene rating saved |

Для твору без рейтингу `{p0}` у `rating.scene.inherit` — наявний `rating.level.unset` («не задано»). Списки рівнів беруть наявні `rating.axis.*` і `rating.level.0/1/2`.

- [ ] **Step 1: Write the failing API test**

У `tests/web/test_rating_routes.py`:

```python
def test_story_view_reports_effective_ratings(tmp_path):
    client, story, scene = make(tmp_path)          # наявний помічник файла
    other = <друга сцена того самого твору>
    put_story(client, story, R(1, 0, 0))            # через наявні запити файла
    put_scene(client, scene, R(0, 2, 0))
    view = client.get(f'/api/stories/{story.id}').json()
    assert view['scene_ratings'][scene.id] == {'effective': {'sexual': 0, 'violence': 2, 'themes': 0}, 'source': 'scene'}
    assert view['scene_ratings'][other.id] == {'effective': {'sexual': 1, 'violence': 0, 'themes': 0}, 'source': 'story'}
    stale = client.put(f'/api/scenes/{scene.id}/content-rating', json={'story_id': story.id, 'content_rating': None, 'expected_revision': 0})
    assert stale.status_code == 409
```

Додайте `@pytest.mark.unrated_stories`-варіант: твір без рейтингу й сцена без перевизначення → `{'effective': None, 'source': None}`.

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=src C:/Projects/text-generator/.venv/Scripts/python -m pytest tests/web/test_rating_routes.py -q`
Expected: FAIL (`KeyError: 'scene_ratings'`).

- [ ] **Step 3: Implement `scene_ratings` у `story_view`**

Словник будується з тих самих сцен, що й поле `scenes`.

- [ ] **Step 4: Write the Playwright spec `scene-rating.spec.mjs`** (локаль `uk-UA`, один тест без розгалужень асерцій для desktop і mobile)

Сценарій:
1. Твір R(1,0,0) зі сценою (наявна фікстура з рейтингом або нова `/test-scene-rating` у `server.py`).
2. Відкрити сцену; у панелі «Параметри сцени» вибрано «Як у твору (сексуальний зміст 1, насильство 0, жорсткі теми 0)», списки вимкнені.
3. Вибрати «Власний рейтинг», задати 0/2/0, «Зберегти рейтинг сцени» → notice «Рейтинг сцени збережено»; `GET /api/stories/{id}` дає `source: 'scene'`.
4. Перезавантажити: вибрано «Власний рейтинг», значення 0/2/0.
5. Повернути «Як у твору», зберегти. Перехоплене тіло PUT має `content_rating: null`; `source: 'story'`.
6. Застаріла ревізія: змінити рейтинг сцени через `request.put` поза сторінкою, потім зберегти зі сторінки → notice помилки, рейтинг із запиту поза сторінкою не перезаписано.

Окремий тест з `/test-unrated`: «Як у твору (не задано)», збереження власного рейтингу сцени працює.

- [ ] **Step 5: Implement the form in `scene-settings.js`**

- Окрема `<form id="scene-rating">` у тій самій панелі після `#scene-settings`: `fieldset` з легендою `rating.scene.legend`, двома radio (`inherit`/`own`), трьома `select` (`sexual`, `violence`, `themes`) з рівнями 0–2, підказкою `rating.scene.hint` і кнопкою `rating.scene.save`.
- Стан береться з `state.scene.content_rating` і `state.view.story.content_rating`. Списки вимкнені, поки вибрано `inherit`. За `inherit` у списках показано рейтинг твору, а якщо його немає — 0.
- Збереження: якщо `state.dirty`, кинути наявне `t("m_7b803d601f5d")`. Далі `PUT /api/scenes/{id}/content-rating` з `{story_id, content_rating: inherit ? null : {…}, expected_revision: state.scene.revision}`, потім `state.scene = відповідь`, `await refresh()`, `notice(msg('rating.scene.saved'))`. Помилка → `notice(e.message, 'error')`.
- Малювання тими самими подіями, що й `draw()` (`scene-selected`, `story-refreshed`), з видаленням попередньої форми.

- [ ] **Step 6: Run tests**

Run: `PYTHONPATH=src C:/Projects/text-generator/.venv/Scripts/python -m pytest tests/web -q`; з `frontend/`: `node node_modules/@playwright/test/cli.js test scene-rating.spec.mjs rating-settings.spec.mjs characters-page.spec.mjs --reporter=line`.

Worktree не має `.venv` і `frontend/node_modules`. Тимчасово створіть junction-и на основну теку і приберіть їх після прогону командою `cmd /c rmdir`, яка видаляє лише посилання, а не цільову теку. `PYTHONPATH` має вказувати на `<worktree>\src`.
Expected: PASS на desktop і mobile.

- [ ] **Step 7: Commit**

```bash
git add src/storygen/web/routes_stories.py src/storygen/web/static/scene-settings.js src/storygen/web/static/i18n.json tests/web/test_rating_routes.py tests/web/browser/scene-rating.spec.mjs tests/web/browser/server.py
git commit -m "feat(rating): scene rating override in scene parameters (#28)"
```

---

### Task 3: SPEC, traceability, документація користувача й Умови

**Files:**
- Modify: `SPEC.MD` (RATING-001, технічний опис RATING-001/002, Source map)
- Modify: `docs/verification/traceability.json`
- Create: `docs/content-rating.md`, `docs/en/content-rating.md`
- Modify: `README.md` (рядки-посилання на інструкції UA/EN, біля посилання на інтерфейс персонажів)
- Modify: `docs/prototype-runbook.md` (розділ часової доступності персонажів), `docs/en/characters.md` (одне речення з посиланням на нову сторінку про рядок `Вік:`)
- Modify: `docs/terms-of-use.md`, `docs/en/terms-of-use.md` (п. 5.3 і примітка для юриста)
- Modify: `docs/superpowers/specs/2026-11/content-rating.md` (позначки «уточнення під час планування PR 2»)
- Modify: `docs/superpowers/plans/2026-10-20-remediation-progress.md` (запис PR 2)
- Modify: `docs/STATUS.md` (результат `scripts/verify.py`)

**Interfaces:**
- Consumes: назви тестів Task 1–2 (читати з коду, не з плану).

- [ ] **Step 1: SPEC**

- Нові сценарії в RATING-001:
  - `RATING-001-S04 — Вікова позначка експорту`. GIVEN твір і сцени з рейтингами WHEN експорт FB2/EPUB THEN позначка за найвищим рівнем (0+/16+/18+) у `custom-info`/`obscura:age-rating`. AND без рейтингу твору позначки немає, у маніфесті є попередження, а `complete` і зупинка неповного експорту від нього не залежать.
  - `RATING-001-S05 — Перевизначення рейтингу сцени`. GIVEN твір із рейтингом WHEN автор у параметрах сцени вибирає власний рейтинг або «як у твору» THEN зберігається об’єкт або `null`, а `GET /api/stories/{id}` віддає `scene_ratings` з ефективним рейтингом і джерелом. AND застаріла ревізія відхиляється.
- У технічному описі прибрати пункт «Поза цим набором змін (PR 2)» і описати експорт та `scene_ratings`. Додати рядок Source map для `publication/` за потреби.

- [ ] **Step 2: traceability**

Записи для S04 і S05 з фактичними назвами тестів Task 1–2, включно з Playwright-spec. Run: `PYTHONIOENCODING=utf-8 PYTHONPATH=src C:/Projects/text-generator/.venv/Scripts/python scripts/check_docs.py`. Expected: «Структура SPEC, матриця, тести, markers і локальні посилання узгоджені.»

- [ ] **Step 3: Документація користувача UA/EN** (`docs/content-rating.md`, `docs/en/content-rating.md`, однакова структура)

Розділи:
1. Навіщо рейтинг: три осі, рівні 0–2.
2. Рейтинг твору в налаштуваннях («Письмо»): без нього генерація не запускається, повернути «не задано» не можна.
3. Рейтинг сцени в «Параметрах сцени»: «Як у твору» або «Власний рейтинг»; пониження позначає матеріали застарілими, підвищення — ні.
4. Вік персонажів: рядок `Вік: 34` або `Вік: дорослий` на початку рядка картки; правило найменшого числа; повідомлення блокування й три способи розблокувати.
5. Вікова позначка FB2/EPUB.
6. Обмеження: запобіжник спирається на записаний автором вік і не є гарантією.

Знімків інтерфейсу не додавати. Посилання: README (UA та EN-рядок), `prototype-runbook.md`, `docs/en/characters.md`.

- [ ] **Step 4: Умови використання** (тексти — на погодження власником разом із цим планом)

UA п. 5.3: «5.3. Застосунок містить технічні запобіжники: віковий рейтинг твору й сцен і перевірку вказаного віку персонажів перед генерацією сцен із сексуальним змістом. Вони допомагають дотримуватися цих Умов, але не гарантують відповідності законодавству і не перекладають відповідальності на автора проєкту.»

EN п. 5.3: «5.3. The Application includes technical safeguards: story and scene age ratings and a check of the characters’ stated age before generating scenes with sexual content. They help users comply with these Terms but do not guarantee legal compliance and do not shift responsibility to the project author.»

Примітку для юриста про те, що «запобіжників ще немає в коді» (UA рядок 71, EN рядок 71), замінити.

UA: «- Пункт 5.3: запобіжники реалізовано (#28). Генерація не запускається без рейтингу твору; сцену із сексуальним змістом не генерують, якщо в картці учасника не вказано вік від 18 років. Вік береться з запису автора й не перевіряється, тож запобіжник обходиться неправдивими даними. Перевірити з юристом, чи достатньо формулювання 5.3.»

EN: «- Clause 5.3: the safeguards are implemented (#28). Generation does not start without a story rating; a scene with sexual content is not generated unless every participant’s card states an age of 18 or more. The age comes from the author’s record and is not verified, so false data bypasses the safeguard. Review with a lawyer whether the wording of 5.3 is sufficient.»

- [ ] **Step 5: Специфікація зміни й журнал**

У розділах «Експорт», «Інтерфейс» і «API» специфікації позначте уточнення під час планування PR 2:
- попередження без рейтингу не зупиняє експорт і не робить його неповним;
- `scene_ratings` у відповіді твору;
- окрема форма рейтингу в параметрах сцени.

Додайте запис PR 2 у журнал виконання.

- [ ] **Step 6: Повна перевірка**

Запустити `scripts/verify.py` з короткого шляху (окремий detached worktree, наприклад `C:/w28`) з абсолютним `PYTHONPATH=C:\w28\src` і `PYTHONIOENCODING=utf-8`, через PowerShell. Перед запуском погодити час із батьківською сесією: спільний `.venv`. Скопіювати `docs/STATUS.md` у гілку. Expected: `"state": "passed"`, 0 failed.

- [ ] **Step 7: Commit**

```bash
git add SPEC.MD docs/verification/traceability.json docs/content-rating.md docs/en/content-rating.md README.md docs/prototype-runbook.md docs/en/characters.md docs/terms-of-use.md docs/en/terms-of-use.md docs/superpowers/specs/2026-11/content-rating.md docs/superpowers/plans/2026-10-20-remediation-progress.md docs/STATUS.md
git commit -m "docs(rating): SPEC, user guide UA/EN and terms 5.3 for content rating (#28)"
```
