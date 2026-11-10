# Мова твору: периферія (#32, R-27, PR 2) — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** автор обирає мову твору й мову прози сцени в інтерфейсі, а розбір плану, мовні підказки, профілі ролей і картка публікації працюють для англійських творів.

**Architecture:** ядро (PR #94) дало `Story.language`, `Scene.prose_language`, `prose_language(story, scene)` у `storygen/language.py` і PUT `/api/stories/{id}/language`. Цей PR лише споживає ці механізми: двомовні регулярні вирази розбору, параметр мови в `language_warnings`, поля інтерфейсу, мова профілю й картки, англійські підписи жанрів. Нових механізмів залежностей чи сховища немає.

**Tech Stack:** Python 3.10+, FastAPI, Jinja2, ванільний JS (ES-модулі), pytest, Playwright (наявні браузерні тести).

**Spec:** `docs/superpowers/specs/2026-11/2026-11-10-story-language-design.md` (розділ «Периферія (PR 2)» і «Поправки»).

## Global Constraints

- Підтримуються лише `uk` і `en`; відсутнє поле читається як `uk` / `None`.
- Ефективна мова прози визначається лише `prose_language(story, scene)` у `storygen/language.py`.
- Розбір заголовків і маркерів двомовний **незалежно від мови твору** (спека: «приймають «Сцена N:» і «Scene N:» … незалежно від мови твору»).
- Українські запити й поведінка для українських творів побайтно незмінні: тести `tests/generation/test_prompt_language.py` (UK_BASELINE, UK_COMPOSED) мають лишатися зеленими без змін.
- Діагностика інтерфейсу — в i18n-каталозі (`src/storygen/web/static/i18n.json` або наявне місце ключів), обидві мови UA/EN.
- Кожен новий тест має `@pytest.mark.req('<REQUIREMENT>')` і запис у `docs/verification/traceability.json`; `python scripts/check_docs.py` зелений.
- Тести: `PYTHONIOENCODING=utf-8 ../../../.venv/Scripts/python.exe -m pytest -q <paths> -p no:cacheprovider`.

## Review Focus

1. Заголовок «Scene 3: …» в українському творі і «Сцена 3: …» в англійському — обидва розпізнаються, і повторний імпорт не дублює сцену з тим самим номером.
2. Маркер «Knows: …» / «Protagonist» в українському творі розпізнається так само, як українські; українські маркери не змінили поведінки.
3. `language_warnings` для англійської сцени в українському творі не видає `non_ukrainian_letters`/`dialogue_dash`/`known_regression`, а для української сцени в англійському творі — видає.
4. Поле мови твору в налаштуваннях після фіксації вимкнене з причиною; спроба через API все одно отримує 409 (UI не обходить сервер).
5. Картка публікації англійського твору без збереженої картки показує `en`; збережена картка зі значенням `uk` не перезаписується.

---

### Task 1: Двомовний розбір плану, учасників і маркерів карток

**Files:**
- Modify: `src/storygen/scene_description.py` (`SCENE_HEADING`, `explicit_scene_number`, рядок учасників у `parse_scene_description`)
- Modify: `src/storygen/plan_sections.py:31,35` (заголовок за замовчуванням)
- Modify: `src/storygen/memory/story_time.py:4` (`START`; і `END`, якщо є поруч)
- Modify: `src/storygen/characters/acquaintance.py:11-13` (`PROTAGONIST`, `ROLE`, `KNOWN`)
- Create: `src/storygen/web/static/templates/story-plan-en.md`, `src/storygen/web/static/templates/characters-en.md`
- Test: `tests/test_scene_description_language.py`, `tests/characters/test_acquaintance_language.py` (нові)

**Interfaces:**
- Produces: `explicit_scene_number(text) -> int | None` і `SCENE_HEADING` приймають `Сцена|Scene`; `split_plan(text, default_title='Сцена')` — назва за замовчуванням для сцени без заголовка береться з параметра (виклик з мовою твору: `'Scene'` для `en`).

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.req('STORY-LANGUAGE')
def test_english_scene_headings_split_plan_with_author_numbers():
    preamble, sections = split_plan('Scene 1: Arrival\nAnna arrives.\n\nScene 2: Departure\nAnna leaves.')
    assert [(s.title, s.author_scene_number) for s in sections] == [('Arrival', 1), ('Departure', 2)]

@pytest.mark.req('STORY-LANGUAGE')
def test_scene_number_accepts_both_languages_regardless_of_story():
    assert explicit_scene_number('## Scene 3. Pier') == 3
    assert explicit_scene_number('**Сцена 4:** Маяк') == 4

@pytest.mark.req('STORY-LANGUAGE')
def test_english_participants_and_start_line():
    assert parse_scene_description('Scene 1: A\nCharacters: Anna, Bob').participants == ['Anna', 'Bob']
    assert parse_scene_description('Scene 1: A\nParticipants: Anna').participants == ['Anna']
    assert START.match('Start: day 2, 23:40')

@pytest.mark.req('STORY-LANGUAGE')
def test_english_protagonist_and_acquaintance_markers():
    assert is_protagonist_line('Protagonist') and is_protagonist_line('Role: Main character, sailor')
    assert known_names_line('Knows: Bob, Clara') == ['Bob', 'Clara']
    assert known_names_line('Acquainted with: Bob') == ['Bob']
    assert is_protagonist_line('Протагоністка') and known_names_line('Знайома з: Анна') == ['Анна']
```

Назви полів `PlanSection` (`title`, `author_scene_number` чи як вони названі) звірити з `plan_sections.py` і використати наявні.

- [ ] **Step 2: Run tests to verify they fail**

Run: `… -m pytest -q tests/test_scene_description_language.py tests/characters/test_acquaintance_language.py -p no:cacheprovider`
Expected: FAIL (англійські форми не розпізнаються).

- [ ] **Step 3: Implement**

`Сцена` → `(?:Сцена|Scene)` у `SCENE_HEADING` і `explicit_scene_number`; учасники — `(?:Хто\s+бере\s+участь|Персонажі|Characters|Participants|Cast)`; `START` — `(?:початок|start)` і `(?:день|day)` (вже є); `PROTAGONIST` додає `protagonist|main\s+character|lead`; `ROLE` — `(?:роль(?:\s+у\s+творі)?|role(?:\s+in\s+the\s+story)?)`; `KNOWN` додає `knows|acquainted\s+with`. `split_plan` отримує `default_title`; виклик в `authoring/import_sections.py` передає `'Scene'` для англійського твору. Шаблони `*-en.md` — переклад українських шаблонів з англійськими маркерами.

- [ ] **Step 4: Run tests to verify they pass + suite of the touched areas**

Run: `… -m pytest -q tests/test_scene_description_language.py tests/characters tests/web/test_additive_imports.py tests/memory -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 5: Commit** `feat(language): bilingual plan, participant and card markers (#32)`

### Task 2: Мовні підказки за мовою прози й відкладені дрібниці

**Files:**
- Modify: `src/storygen/generation/language.py:16` (`language_warnings(text, language='uk')`)
- Modify: `src/storygen/generation/stages.py:298,305`, `src/storygen/generation/copyedit_review.py:61`, `src/storygen/web/routes_versions.py:126-133` (передати ефективну мову прози)
- Modify: `src/storygen/copyediting.py:39` (`cannot` у словнику заперечень)
- Modify: `src/storygen/storage/authoring.py:12,93,116`, `src/storygen/storage/memory_kinds.py:15` + i18n-каталог (ключі для «Твір уже змінено…»)
- Test: `tests/generation/test_language_warnings_language.py` (новий), доповнити `tests/generation/test_english_guards.py`

**Interfaces:**
- Produces: `language_warnings(text: str, language: Literal['uk','en']='uk') -> list[dict]`.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.req('LANGUAGE-WARNINGS')
def test_english_prose_gets_only_language_neutral_hints():
    codes = {w['code'] for w in language_warnings('- Hello the the world ыы', 'en')}
    assert codes == {'repeated_word'}  # ні non_ukrainian_letters, ні dialogue_dash, ні known_regression

@pytest.mark.req('LANGUAGE-WARNINGS')
def test_ukrainian_default_unchanged():
    text = '- Привіт ы'
    assert language_warnings(text) == language_warnings(text, 'uk')

@pytest.mark.req('LANGUAGE-WARNINGS')
def test_version_language_check_uses_scene_prose_language(client_with_english_scene):
    # GET /api/versions/{id}/language-warnings для прози англійської сцени в українському творі
    assert 'dialogue_dash' not in {w['code'] for w in response.json()['warnings']}

@pytest.mark.req('EDIT-001')
def test_cannot_is_protected_negation():
    assert 'cannot' in protected_negations('She cannot go.')
```

Плюс тест: `RevisionConflict` з «Твір уже змінено» повертає локалізований `detail` для `Accept-Language: en` (за зразком наявних тестів i18n помилок).

- [ ] **Step 2: Run to verify they fail** — Expected: FAIL (`language_warnings` не приймає мову; `cannot` не захищене; англійського `detail` немає).

- [ ] **Step 3: Implement** — для `en` пропустити `non_ukrainian_letters`, `dialogue_dash`, `known_regression`; виклики передають `prose_language(story, scene)`; `cannot` у регулярний вираз; повідомлення конфліктів — ключі каталогу за наявним механізмом локалізації помилок (`web/localization.py`).

- [ ] **Step 4: Run** `… tests/generation tests/web/test_language*.py tests/storage -p no:cacheprovider` — Expected: PASS.

- [ ] **Step 5: Commit** `feat(language): warnings follow prose language; cannot guard; conflict i18n (#32)`

### Task 3: Інтерфейс мови твору й сцени

**Files:**
- Modify: `src/storygen/web/routes_stories.py` (`GET /api/stories/{id}` додає `language_locked: bool`; створення твору приймає `language`)
- Modify: `src/storygen/storage/authoring.py` (функція `story_language_locked(story_id) -> bool` з наявного SQL фіксації, повторно використана в `update_story_language`)
- Modify: `src/storygen/web/templates/library.html` (select «Мова твору» у формі створення) і відповідний JS (`library.js` або наявний модуль форми)
- Modify: `src/storygen/web/templates/settings.html` (розділ «Письмо»: select мови твору, вимкнений з поясненням при `language_locked`) і `settings-workspace.js`/наявний модуль
- Modify: `src/storygen/web/static/scene-settings.js` («Мова прози»: «Як у творі» / українська / англійська; PATCH з `prose_language: 'story'|'uk'|'en'`)
- Modify: `src/storygen/web/templates/story.html` (посилання на шаблони плану й персонажів за мовою твору)
- Modify: `src/storygen/web/static/evaluation.js:13` (кнопки оцінювання вимкнені з причиною `evaluation.english_not_evaluated` для сцени з ефективною мовою `en`; «Оцінити твір» — якщо будь-яка сцена англійська)
- Test: `tests/web/test_story_language_ui.py` (новий), браузерний тест у `tests/web/browser/` за наявним зразком

**Interfaces:**
- Consumes: PUT `/api/stories/{id}/language` (ядро), PATCH `/api/scenes/{id}` з `prose_language` (ядро), i18n-ключі `language.locked`, `language.run_active`, `evaluation.english_not_evaluated` (ядро).
- Produces: `story_language_locked(repo_or_db, story_id) -> bool`; поле `language_locked` у відповіді GET story.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.req('STORY-LANGUAGE')
def test_story_view_reports_language_lock(client):
    story = create_story(client, language='en')
    assert client.get(f'/api/stories/{story["id"]}').json()['language_locked'] is False
    save_model_version(...)  # версія з source_run_id
    assert client.get(...).json()['language_locked'] is True

@pytest.mark.req('STORY-LANGUAGE')
def test_create_story_with_language(client):
    assert client.post('/api/stories', json={'title': 'Pier', 'language': 'en'}).json()['language'] == 'en'
```

Браузерний тест: створити твір з мовою «English» → у налаштуваннях select показує English і активний; після появи модельної версії (seed) select вимкнений і причина видима; у картці сцени «Мова прози» = English → кнопка «Оцінити сцену» вимкнена з причиною; посилання шаблону плану веде на `story-plan-en.md`.

- [ ] **Step 2: Run to verify they fail** — Expected: FAIL (`language_locked` відсутнє, поля в UI немає).

- [ ] **Step 3: Implement** — поля й обробники за наявними зразками форм; збереження мови твору через PUT `/language` з `expected_revision`; 409 показується як звичайна помилка форми. Нові i18n-ключі UA/EN.

- [ ] **Step 4: Run** `… tests/web/test_story_language_ui.py tests/web/test_*_ui.py tests/storage/test_story_language.py -p no:cacheprovider` і браузерний тест — Expected: PASS.

- [ ] **Step 5: Commit** `feat(language): story and scene language in the interface (#32)`

### Task 4: Профілі ролей, картка публікації й англійські жанри

**Files:**
- Modify: `src/storygen/role_profiles.py` (`ProfileDocument.language: Literal['uk','en'] | None = None`; `export_profile` записує мову твору-джерела, якщо профіль має її; `apply_profile` повертає `warnings` при розбіжності)
- Modify: `src/storygen/web/static/role-profiles.js` (показ попередження)
- Modify: `src/storygen/storage/publication_store.py:22` (картка без збереженого запису: `language = story.language`)
- Modify: `src/storygen/publication/genres.py` (`genre_catalog(language='uk')` з англійськими підписами `LABELS_EN` для всіх 186 кодів) і `src/storygen/generation/publication_metadata.py:12` (`catalog_for` бере англійські підписи замість кодів)
- Modify: сторінка публікації (`publication.js`) — підписи жанрів за мовою інтерфейсу
- Test: `tests/test_role_profiles_language.py`, `tests/publication/test_genres_language.py` (нові)

**Interfaces:**
- Produces: `genre_catalog(language: str = 'uk') -> tuple[tuple[str, str], ...]`; `apply_profile(...)` повертає наявний результат плюс `warnings: list[str]`.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.req('STORY-LANGUAGE')
def test_english_genre_labels_cover_every_code():
    uk, en = dict(genre_catalog('uk')), dict(genre_catalog('en'))
    assert set(uk) == set(en) and all(en[c] and en[c] != uk[c] for c in en if c not in {'sf'} )

@pytest.mark.req('R16-META')
def test_unsaved_card_defaults_to_story_language(repo):
    story = repo.create_story(StoryCreate(title='Pier', language='en'))
    assert repo.get_publication(story.id).language == 'en'

@pytest.mark.req('STORY-LANGUAGE')
def test_applying_profile_of_other_language_warns(repo):
    # профіль з language='uk' до англійського твору → застосовано, warnings непорожні
```

Також: експорт профілю з англійського твору містить `"language": "en"`; імпорт старого профілю без поля працює (`None`, без попередження).

- [ ] **Step 2: Run to verify they fail** — Expected: FAIL.

- [ ] **Step 3: Implement** — англійські підписи 186 кодів FB2 (переклад українських); `catalog_for('en')` → `dict(genre_catalog('en'))`. Перевірити, що українські складені повідомлення в `test_prompt_language.py` не змінились.

- [ ] **Step 4: Run** `… tests/publication tests/test_role_profiles*.py tests/web/test_role_profiles*.py tests/generation/test_prompt_language.py -p no:cacheprovider` — Expected: PASS.

- [ ] **Step 5: Commit** `feat(language): profile language, card default and English genre labels (#32)`

### Task 5: SPEC, traceability, документація UA/EN, STATUS

**Files:**
- Modify: `SPEC.MD` — STORY-LANGUAGE (нові Scenario: інтерфейс і фіксація в UI, двомовний розбір, профіль, картка), LANGUAGE-WARNINGS (мова прози), IMPORT-NUMBER (англійський заголовок), R16-META (мова за замовчуванням), EDIT-001 (`cannot`); `docs/verification/traceability.json`
- Create: `docs/story-language.md`, `docs/en/story-language.md` (нейтральні приклади; знімки у `docs/images/story-language-*.png`)
- Modify: `README.md` (рядок про мову твору UA/EN), `docs/superpowers/plans/2026-10-20-remediation-backlog.md` (R-27), `docs/superpowers/plans/2026-10-20-remediation-progress.md`, `docs/superpowers/specs/2026-11/2026-11-10-story-language-design.md` (поправки, якщо були рішення)
- Modify: `docs/STATUS.md` (запуск `python scripts/verify.py` у detached worktree)

- [ ] **Step 1:** оновити SPEC і traceability; `python scripts/check_docs.py` — Expected: «узгоджені».
- [ ] **Step 2:** документація й знімки (нейтральний твір «Pier lighthouse» / «Маяк на пристані»).
- [ ] **Step 3:** повний `python -m pytest -q` — Expected: PASS.
- [ ] **Step 4: Commit** `docs(language): SPEC, traceability and UA/EN guide for story language (#32)`

Після рев'ю гілки — `verify.py` у detached worktree і запис у STATUS.
