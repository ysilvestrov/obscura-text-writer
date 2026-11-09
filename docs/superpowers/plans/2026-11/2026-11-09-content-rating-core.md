# Віковий рейтинг — ядро (PR 1) — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** рейтинг твору й сцени в моделі даних, несиметрична застарілість, запобіжник щодо неповнолітніх, інструкції рейтингу в запитах генерації, API та поле рейтингу твору в налаштуваннях, SPEC і traceability.

**Architecture:** `ContentRating` у `domain.py`; чисті функції рейтингу в новому пакеті `storygen/rating/`; розбір віку в `characters/age.py`; перевірки й інструкції вбудовано в `generation/context.py::make_context`, єдину точку збирання запиту генерації; застарілість — новий селектор `scene.content_rating` з порівнянням «не нижче».

**Tech Stack:** Python 3.10+, pydantic (strict), FastAPI, SQLite payload JSON, ванільний JS + `i18n.json`, pytest.

**Spec:** `docs/superpowers/specs/2026-11/content-rating.md` (затверджено 2026-11-09). Виконавці читають її разом із планом.

## Global Constraints

- Рівні осей: `0`, `1`, `2`; осі: `sexual`, `violence`, `themes` — саме ці англійські імена полів.
- `Story.content_rating is None` = «не задано»; повернути `None` для твору API не дозволяє.
- Вік дорослий: найменше ціле в значенні ≥ 18, або значення повністю (без регістру, пробілів, кінцевої крапки) одне з `дорослий`, `доросла`, `дорослі`, `доросле`, `adult`. Регулярний вираз рядка: `(?im)^[ \t]*\W*(вік|age)[ \t]*:[ \t]*([^\r\n]*)$`.
- Помилки, які бачить автор, — українською, з EN-перекладом через наявний механізм `web/localization.py::diagnostic` / `i18n.json`.
- Робоча база `data/storygen.sqlite3` не використовується тестами й не змінюється; тексти творів не друкуються.
- Формат карток персонажів (`CharacterRecord`) не змінюється.
- Кожна архітектурна зміна — у SPEC.MD того самого PR; кожен Scenario має запис у `docs/verification/traceability.json`.
- Команди запуску: `.venv/Scripts/python -m pytest …` з кореня worktree (Windows, venv основної теки: `C:/Projects/text-generator/.venv/Scripts/python`).

## Review Focus

1. Відомість картки `Вік:` без значення, за якою йде `Зріст: 160` — має бути «невказаний», не дорослий (тест у Task 2).
2. Старий матеріал без селектора рейтингу після пониження нижче початкового рейтингу твору має стати застарілим, а ручний текст автора (`author_text`) — ні (тест у Task 3).
3. Сцена з рейтингом сексуального змісту 0 у творі з рейтингом 2 і дитиною серед учасників — генерація дозволена (тест у Task 4).
4. Редактура в режимі `diff`: текст користувача лишається точно документом, блок рейтингу лише в system (тест у Task 4).
5. Повторне збереження того самого рейтингу не змінює ревізію і нічого не інвалідує (тест у Task 1).

---

### Task 1: Модель рейтингу й збереження

**Files:**
- Modify: `src/storygen/domain.py` (`ContentRating`, поля `Story`, `Scene`)
- Create: `src/storygen/rating/__init__.py`, `src/storygen/rating/levels.py`
- Modify: `src/storygen/storage/authoring.py` (нові функції), `src/storygen/storage/repository.py` (обгортки)
- Test: `tests/storage/test_content_rating.py`

**Interfaces:**
- Produces:
  - `class ContentRating(DomainModel): sexual: Literal[0,1,2]; violence: Literal[0,1,2]; themes: Literal[0,1,2]` у `domain.py`.
  - `Story.content_rating: ContentRating | None = None`, `Story.initial_content_rating: ContentRating | None = None`, `Scene.content_rating: ContentRating | None = None`.
  - `rating/levels.py`: `AXES = ('sexual','violence','themes')`; `effective_rating(story: Story, scene: Scene) -> ContentRating | None` (перевизначення сцени або рейтинг твору); `is_lower(current: ContentRating | None, expected: ContentRating | None) -> bool` (True лише коли обидва задані й хоча б одна вісь current < expected); `to_wire(r: ContentRating | None) -> list[str] | None` (`['1','0','2']`); `from_wire(v: list[str] | None) -> ContentRating | None`; `higher_axes(other: ContentRating, base: ContentRating) -> list[str]` (осі, де other > base).
  - `Repository.update_story_rating(story_id: str, rating: ContentRating, expected_revision: int) -> Story`
  - `Repository.update_scene_rating(scene_id: str, rating: ContentRating | None, expected_revision: int) -> Scene`

- [ ] **Step 1: Write failing tests** у `tests/storage/test_content_rating.py` (фікстури репозиторію — як у сусідніх `tests/storage/*`):
  - `test_old_payload_reads_unrated` — твір і сцена, збережені без нових полів, читаються з `content_rating is None`, `initial_content_rating is None`.
  - `test_first_story_rating_sets_initial_once` — `update_story_rating(…, R(1,0,0))` → `initial == R(1,0,0)`; потім `update_story_rating(…, R(2,2,2))` → `content_rating == R(2,2,2)`, `initial == R(1,0,0)`.
  - `test_same_rating_is_noop` — повтор того самого значення повертає твір із тією самою `revision`.
  - `test_revision_conflict` — неправильна `expected_revision` → `RevisionConflict`.
  - `test_story_lowering_invalidates_only_inheriting_scenes` — дві сцени з головами й залежним матеріалом (версія з ребром `dependency_edges` від голови); сцена B має власний рейтинг. Пониження рейтингу твору: залежні матеріали сцени A позначені `stale=True`, сцени A `needs_review=True`; у сцени B — без змін.
  - `test_raising_and_first_set_invalidate_nothing` — перше задання і підвищення не змінюють жодного `stale` чи `needs_review`.
  - `test_scene_override_and_reset` — `update_scene_rating(…, R(0,0,0))`, потім `None`; ефективний рейтинг повертається до рейтингу твору; пониження відносно попереднього ефективного (і лише воно) інвалідує залежні матеріали так само, як `update_scene_metadata`.
  - `test_levels_helpers` — `is_lower(R(1,2,2), R(2,0,0))` True; `is_lower(R(2,2,2), R(1,1,1))` False; `is_lower(None, R(0,0,0))` False; `to_wire`/`from_wire` взаємно обернені; `higher_axes(R(2,0,1), R(1,0,1)) == ['sexual']`.
- [ ] **Step 2: Run** `.venv/Scripts/python -m pytest tests/storage/test_content_rating.py -q` → FAIL (немає імен).
- [ ] **Step 3: Implement.** Поля з типовим `None` (strict-моделі читають старі payload без міграції). `update_story_rating` / `update_scene_rating` у `storage/authoring.py` за зразком `update_scene_metadata`: `BEGIN IMMEDIATE`, перевірка ревізії, no-op при рівності, `revision+1`, збереження; `initial_content_rating` заповнюється лише коли він `None`. Після збереження: для кожної активної сцени, чий ефективний рейтинг став нижчим (`is_lower(new_eff, old_eff)`), викликати `invalidate_in_transaction(repo, db, list(scene.heads.values()))`, як у `update_scene_metadata`. `update_story_rating(…, None)` → `ValueError('Рейтинг твору не можна скинути')`.
- [ ] **Step 4: Run** той самий файл → PASS; потім `.venv/Scripts/python -m pytest tests/storage -q` → PASS.
- [ ] **Step 5: Commit** `feat(rating): content rating model and storage (#28)`.

### Task 2: Розбір віку учасників

**Files:**
- Create: `src/storygen/characters/age.py`
- Test: `tests/characters/test_character_age.py`

**Interfaces:**
- Consumes: `CharacterRecord`, `CharacterEntry` (`characters/models.py`), `Scene`.
- Produces:
  - `AgeVerdict = Literal['adult','minor','unknown']`
  - `parse_age_value(value: str) -> AgeVerdict`
  - `entry_age(text: str) -> AgeVerdict | None` (None — у тексті немає рядка віку; кілька рядків в одному тексті — найгірший вердикт)
  - `scene_ages(cards: list[CharacterRecord], scenes: list[Scene], scene_id: str) -> dict[str, AgeVerdict]` — для кожного id із `scene.character_ids`; картки немає → `'unknown'`.

- [ ] **Step 1: Write failing tests:**
  - `parse_age_value`: `'27.'`→adult; `'17'`→minor; `'на вигляд 16, насправді 300'`→minor; `'18-20'`→adult; `'Дорослий.'`→adult; `' доросла '`→adult; `'adult'`→adult; `'ще не дорослий'`→unknown; `'not an adult'`→unknown; `'майже доросла'`→unknown; `''`→unknown; `'невідомо'`→unknown.
  - `entry_age('Вік:\nЗріст: 160 см.')` → `'unknown'` (Review Focus 1); `entry_age('Зовнішність: висока.\nВік: 34.')` → adult; `entry_age('- **Вік:** 15')` → minor; `entry_age('Чоловік: Петро')` → None; `entry_age('Age: 40')` → adult.
  - `scene_ages`:
    - немає жодного рядка віку → unknown;
    - `timeless` «Вік: 17» + `from_scene` «Вік: 18» з якорем на сцені 2: на сцені 3 → adult, на сцені 1 → minor;
    - два `timeless` «Вік: 30» і «Вік: 16» → minor (пріоритет minor > unknown > adult);
    - id учасника без картки → unknown;
    - відомість `from_scene` із пізнішим якорем ігнорується.
- [ ] **Step 2: Run** `.venv/Scripts/python -m pytest tests/characters/test_character_age.py -q` → FAIL.
- [ ] **Step 3: Implement.** Регулярний вираз і правило слів — з Global Constraints. Вибір групи: серед доступних відомостей із рядком віку — якщо є `from_scene`, береться група з найбільшою позицією якоря (позиція сцени-якоря ≤ позиції поточної); інакше всі `timeless`/`unclassified`. Правила доступності (активні сцени, якір тієї самої історії) — ті самі, що в `characters/projection.py::project_characters`; помилкові якорі тут не піднімають винятку, а відомість просто пропускається (проєкція окремо повідомить про помилку). Чисті функції, без IO.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(rating): parse character age lines (#28)`.

### Task 3: Несиметрична застарілість

**Files:**
- Modify: `src/storygen/dependency_models.py` (дозволене поле), `src/storygen/storage/snapshots.py` (`build_dependency_snapshot`, `selector_value`, `compare_snapshot`; перевірити інші будівники знімків у тому самому файлі біля рядків ~300–330), за потреби `src/storygen/impact/planning.py`
- Test: `tests/storage/test_rating_freshness.py`

**Interfaces:**
- Consumes: `effective_rating`, `is_lower`, `to_wire`, `from_wire` (Task 1).
- Produces: селектор `DependencySelector(kind='scene', field='content_rating', expected=list[str] | None)`.

- [ ] **Step 1: Write failing tests** (матеріали створюються через реальні шляхи збереження з `dependency_snapshot`, як у `tests/storage/test_snapshots*` / `tests/generation/test_dependencies.py`):
  - `test_rating_selector_recorded_for_generation_scopes` — знімки областей `brief`, `draft`, `prose_edit`, `patches`, `author_rewrite` містять селектор `content_rating` з ефективним рейтингом; `author_text` і `memory` — ні.
  - `test_lowering_makes_stale_raising_keeps_fresh` — після пониження будь-якої осі `freshness(...).stale` True з `reason='selector_changed'`; після підвищення — False.
  - `test_old_snapshot_uses_initial_rating` — знімок області `draft` без селектора рейтингу: до задання рейтингу свіжий; після першого задання R(2,1,1) свіжий; після пониження до R(1,1,1) — застарілий; після повернення до R(2,1,1) — знову свіжий.
  - `test_author_text_never_stale_from_rating` — ручна проза (знімок `author_text`) лишається свіжою після пониження (Review Focus 2).
  - `test_impact_preview_tolerates_rating_selector` — побудова перевірки впливу (`impact/planning.py`) для сцени з матеріалом, що має селектор рейтингу, не падає.
- [ ] **Step 2: Run** `.venv/Scripts/python -m pytest tests/storage/test_rating_freshness.py -q` → FAIL.
- [ ] **Step 3: Implement.** У `finite_selector` додати `'content_rating'` до поля `scene`. У `build_dependency_snapshot` для перелічених областей — `select('scene', scene.id, 'content_rating', to_wire(effective_rating(story, scene)))`. `selector_value` → `to_wire(effective_rating(view.peek_story(story_id), view.peek_scene(owner)))`. У `compare_snapshot`: для `field=='content_rating'` зміна лише коли `is_lower(from_wire(current), from_wire(expected))`. Для знімків областей `brief`/`draft`/`prose_edit`/`patches`/`author_rewrite` без селектора рейтингу — якщо `story.initial_content_rating` задано, додати синтетичний селектор з `expected=to_wire(initial)`; власника сцени взяти так само, як наявний запасний селектор `memory_projection_policy` (селектор `title`; для `patches` — власник голови `draft`).
- [ ] **Step 4: Run** → PASS; потім `.venv/Scripts/python -m pytest tests/storage tests/impact tests/generation/test_dependencies.py -q` → PASS.
- [ ] **Step 5: Commit** `feat(rating): asymmetric staleness for rating changes (#28)`.

### Task 4: Запобіжник та інструкції в запиті

**Files:**
- Create: `src/storygen/rating/guard.py`, `src/storygen/rating/instructions.py`
- Modify: `src/storygen/generation/context.py::make_context`, `src/storygen/web/localization.py` / `src/storygen/web/static/i18n.json` (EN для нових повідомлень)
- Test: `tests/generation/test_content_rating_context.py`

**Interfaces:**
- Consumes: Task 1 (`effective_rating`, `higher_axes`), Task 2 (`scene_ages`), `load_characters`, `selected_plan_scenes`.
- Produces:
  - `rating/guard.py`: `enforce_rating(view, story: Story, scene: Scene | None, stage: str) -> None` — піднімає `ValueError` із текстами нижче.
  - `rating/instructions.py`: `rating_block(rating: ContentRating) -> str`; `higher_scenes_block(items: list[tuple[int, list[str]]]) -> str` (номер сцени, осі); `rating_instructions(view, story, scene, stage, settings) -> str` (порожній рядок, якщо інструкції не потрібні).

Тексти (точні):
- рейтинг твору не задано: `Задайте віковий рейтинг твору в налаштуваннях, щоб запустити генерацію.`
- порожній склад: `Сцена має рейтинг сексуального змісту {n}, але склад сцени порожній. Укажіть учасників, щоб перевірити їхній вік.`
- немає карток: `Сцена має рейтинг сексуального змісту {n}. Підготуйте картки персонажів із рядком «Вік:», щоб перевірити вік учасників.`
- учасники: `Генерацію заблоковано: сцена має рейтинг сексуального змісту {n}, а {список}. Допишіть у картку рядок «Вік: …» (число від 18 або «дорослий»), приберіть персонажа зі складу сцени або позначте сцену рейтингом «сексуальний зміст 0».` де елемент списку — `персонаж «{name}» молодший за 18` або `персонаж «{name}» не має вказаного віку`, до 5 елементів через `; `.

Блок рейтингу (рядки описів — фіксовані, рішення автора плану в межах «тексти — ресурси застосунку»):

```
ВІКОВИЙ РЕЙТИНГ СЦЕНИ — МЕЖА, ЯКУ НЕ МОЖНА ПЕРЕВИЩУВАТИ
Сексуальний зміст: рівень {n} — {опис}.
Насильство: рівень {n} — {опис}.
Жорсткі теми: рівень {n} — {опис}.
Межа не вимагає досягати рівня: пиши так, як потребує сцена.
```

| Вісь | 0 | 1 | 2 |
|---|---|---|---|
| sexual | без сексуального змісту; романтика без еротичних подробиць | дорослий сексуальний зміст без графічних подробиць | відвертий сексуальний зміст допустимий |
| violence | без детального насильства й крові | насильство без графічних подробиць | графічне насильство допустиме |
| themes | жорсткі теми лише згадуються, без зображення | жорсткі теми без детального зображення | відверте зображення жорстких тем допустиме |

Блок вищих сцен: `СЦЕНИ З ВИЩИМ РЕЙТИНГОМ: 5, 9 (сексуальний зміст); 7 (насильство).` + новий рядок `Не переказуй і не згадуй їхніх подробиць понад межу цієї сцени; можна посилатися лише на події, важливі для сюжету.` Групування за однаковим набором осей, назви осей у родовому/називному як у таблиці заголовків: «сексуальний зміст», «насильство», «жорсткі теми».

- [ ] **Step 1: Write failing tests** (контекст будується через `build_context`/`make_context` з тестовим репозиторієм, як у `tests/generation/test_context.py` і `test_character_context.py`):
  - `test_unrated_story_blocks_all_stages` — `prepare`, `brief`, `memory` → `ValueError` з текстом «Задайте віковий рейтинг твору…».
  - `test_minor_blocks_sexual_scene` — твір R(1,0,0), учасник «Вік: 15» → `ValueError`, у тексті `персонаж «…» молодший за 18`; учасник без рядка віку → `не має вказаного віку`; обидва в одному повідомленні.
  - `test_child_allowed_when_scene_sexual_zero` — твір R(2,0,0), сцена R(0,0,0), учасник «Вік: 10» → контекст будується (Review Focus 3).
  - `test_empty_cast_and_missing_cards_block` — два окремі тексти.
  - `test_adult_cast_builds_with_rating_block` — у `system_text` є блок із рівнями сцени; для `memory` і `prepare` блоку немає.
  - `test_higher_rated_scenes_listed` — сцени 1–3, сцена 2 має R(2,0,0), поточна сцена 3 R(1,0,0) → `СЦЕНИ З ВИЩИМ РЕЙТИНГОМ: 2 (сексуальний зміст)`; без вищих сцен рядка немає.
  - `test_diff_edit_user_text_untouched` — для `edit` у режимі `diff` `user_text` дорівнює тексту чернетки, блок лише в `system_text` (Review Focus 4).
  - `test_rating_change_changes_fingerprint` — підвищення рейтингу сцени дає інший `fingerprint`.
  - `test_guard_message_has_english_translation` — `diagnostic(<повідомлення>, 'en')` повертає англійський текст з ім'ям персонажа.
- [ ] **Step 2: Run** `.venv/Scripts/python -m pytest tests/generation/test_content_rating_context.py -q` → FAIL.
- [ ] **Step 3: Implement.** У `make_context` одразу після повторного читання `story`/`scene` викликати `enforce_rating(repo, story, scene, stage)`; перевірка віку лише коли `scene` не `None` і ефективний `sexual >= 1`; картки — `load_characters(view.read_text(story.characters_version_id))`, сцени — `view.list_scenes(story.id)`. Після формування `system` (і вказівки Markdown) додати `rating_instructions(...)` через `\n\n`, лише для `stage in {'brief','draft','edit','rewrite'}`. Сцени матеріалу запиту для блоку вищих сцен: усі активні сцени з позицією < поточної плюс `selected_plan_scenes(scenes, scene, settings)`; для `edit` у режимах `patches`/`diff` — блок вищих сцен не додається (ці режими не несуть матеріалів інших сцен). EN-переклади: додати ключі до каталогу, яким користується `diagnostic`, з параметрами для чисел і списку імен.
- [ ] **Step 4: Run** → PASS; потім весь набір `.venv/Scripts/python -m pytest -q` — наявні тести, що будують контекст на творі без рейтингу, тепер падають: оновити їхні фікстури, задавши рейтинг твору R(0,0,0) у спільній фікстурі (`tests/conftest.py` або фабриці твору), а не послабленням перевірки. Повторити до PASS.
- [ ] **Step 5: Commit** `feat(rating): minors safeguard and rating instructions (#28)`.

### Task 5: API рейтингу і поле в налаштуваннях твору

**Files:**
- Create: `src/storygen/web/routes_rating.py` (і реєстрація роутера в `web/app.py`)
- Modify: `src/storygen/web/templates/settings.html`, `src/storygen/web/static/settings.js` (або окремий модуль `rating-settings.js`, підключений у шаблоні), `src/storygen/web/static/i18n.json`
- Test: `tests/web/test_rating_routes.py`; браузерна перевірка — як у наявних browser-тестах `tests/web` (якщо є Playwright-набір) або ручна процедура в Task 6

**Interfaces:**
- Consumes: `Repository.update_story_rating`, `Repository.update_scene_rating` (Task 1).
- Produces: `PUT /api/stories/{story_id}/content-rating` (`{content_rating: ContentRating, expected_revision: int}` → `Story`), `PUT /api/scenes/{scene_id}/content-rating` (`{story_id: str, content_rating: ContentRating | None, expected_revision: int}` → `Scene`; сцена іншого твору → 404/ValueError як у `patch_scene`).

- [ ] **Step 1: Write failing tests:** `test_put_story_rating_roundtrip` (відповідь містить `content_rating` і `initial_content_rating`); `test_put_story_rating_null_rejected` (422); `test_put_scene_rating_and_reset`; `test_scene_rating_wrong_story_rejected`; `test_rating_conflict_returns_409` (той самий код, що наявні конфлікти ревізій).
- [ ] **Step 2: Run** `.venv/Scripts/python -m pytest tests/web/test_rating_routes.py -q` → FAIL.
- [ ] **Step 3: Implement** роутер. Інтерфейс: у розділі «Письмо» налаштувань — `fieldset` «Віковий рейтинг твору» з трьома `select` (`sexual`, `violence`, `themes`), варіанти `0 — звичайне`, `1 — доросле без графічних подробиць`, `2 — відверте`; поки твір без рейтингу — перший пункт `не задано` (disabled після першого збереження), підказка `Без рейтингу генерація не запускається.`; окрема кнопка `Зберегти рейтинг`, запит із `expected_revision` твору, оновлення ревізії після відповіді, повідомлення через наявний `notice`. Усі рядки — з `data-i18n` і EN-перекладом у `i18n.json` за наявним шаблоном.
- [ ] **Step 4: Run** → PASS; запустити застосунок (скіл `run`) на тимчасовому каталозі даних, задати рейтинг новому твору в налаштуваннях, перевірити, що повідомлення блокування зникає в екрані готовності.
- [ ] **Step 5: Commit** `feat(rating): rating API and story settings control (#28)`.

### Task 6: SPEC, traceability, журнал і перевірка

**Files:**
- Modify: `SPEC.MD`, `docs/verification/traceability.json`, `docs/superpowers/plans/2026-10-20-remediation-progress.md`, `docs/STATUS.md` (через `scripts/verify.py`), за потреби `docs/verification/manual.md`

- [ ] **Step 1:** У `SPEC.MD` додати `Requirement: RATING-001 — Віковий рейтинг твору й сцени` зі сценаріями `RATING-001-S01` (не задано → блок усіх етапів, включно з підготовкою), `RATING-001-S02` (блок рейтингу й вищих сцен у system; diff не змінює user), `RATING-001-S03` (пониження → застаріле, підвищення → свіже, старий знімок проти `initial_content_rating`, ручний текст не застаріває); і `Requirement: RATING-002 — Запобіжник щодо неповнолітніх` зі сценаріями `RATING-002-S01` (неповнолітній / без віку / порожній склад / без карток блокують), `RATING-002-S02` (правила розбору віку: заперечення, порожній рядок, найменше число, найпізніша відомість), `RATING-002-S03` (сцена з сексуальним змістом 0 і дитиною дозволена). Формат — як у сусідніх Requirement (GIVEN/WHEN/THEN, SHALL/MUST англійською). Оновити розділи: схема даних (нові поля, без міграції), залежності/інвалідація (селектор `content_rating`, «не нижче», `initial_content_rating`), збирання контексту (перевірки в `make_context`, блок у system), API (два ендпоінти), відомі обмеження (аналітичні виклики поза `make_context` не перевіряють рейтинг; legacy-версії без знімка не інвалідуються пониженням; підготовка плану без інструкції рейтингу; запобіжник обходиться неправдивими даними) і «Зміст».
- [ ] **Step 2:** У `traceability.json` — записи для кожного нового Scenario з конкретними тестами Tasks 1–5.
- [ ] **Step 3: Run** `.venv/Scripts/python scripts/check_docs.py` → без помилок.
- [ ] **Step 4: Run** `.venv/Scripts/python scripts/verify.py` (у фоні, може бути довгим) → зафіксований результат у `docs/STATUS.md`; усі тести PASS.
- [ ] **Step 5:** Запис у журналі виконання (#28: спека, PR 1 ядро, перевірки, що лишилося для PR 2).
- [ ] **Step 6: Commit** `docs(rating): SPEC, traceability and status for content rating core (#28)`.

## Поза цим планом (PR 2, окремий план після рев'ю ядра)

Перевизначення рейтингу в параметрах сцени та показ ефективного рейтингу, вікова позначка FB2/EPUB з попередженням, користувацька документація UA/EN (налаштування, параметри сцени, рядок `Вік:` у картках), п. 5.3 Умов використання, сценарій SPEC для експорту.
