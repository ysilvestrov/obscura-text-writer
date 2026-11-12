# MCP, пакет 2: початок твору — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** чат створює й налаштовує твір через `storygen-mcp`: п'ять нових інструментів, рейтинг при створенні, запис плану сцени лише поверх прочитаного.

**Architecture:** сервер отримує два необов'язкові поля (`StoryCreate.content_rating`, `ScenePatch.expected_plan_version_id`) і перевірку всього `PATCH /api/scenes/{id}` до першої зміни; клієнт `storygen-mcp` додає п'ять інструментів, що мапляться на наявні маршрути, і розширює `get_story`.

**Tech Stack:** Python 3.12, FastAPI, pydantic (strict), SQLite, `mcp==2.3.0`, httpx, pytest.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-11-mcp-p2-story-start-design.md` (затверджено 2026-11-12); загальний дизайн `2026-11-11-mcp-full-toolset-design.md`.

## Global Constraints

- Нові поля сервера необов'язкові; інтерфейс їх не передає, його поведінка не змінюється.
- План і властивості з чату не позначаються `external_origin` і не фіксують мову твору.
- Чат не видаляє, не переносить у кошик і не переставляє сцен; у переліку 12 інструментів.
- Ідентифікатори перед вставкою в шлях проходять `identifier()` (`[A-Za-z0-9_-]{1,64}`), зокрема кожен із `character_ids`.
- Повідомлення про застарілий план: `План сцени змінено після того, як його прочитали — прочитайте його знову (get_scene_text)`.
- Тести клієнта йдуть через справжній FastAPI-застосунок (`TestClient`), без моків маршрутів.
- Тести, що створюють твір без рейтингу, мають `@pytest.mark.unrated_stories` (інакше autouse-фікстура додає R(0,0,0)).

## Review Focus

1. План із чату, ідентичний поточному, але з чужим `expected_plan_version_id` — має бути 409, а не тихе «без змін» (`unchanged_scene_text` повертає раніше за перевірку).
2. Помилка властивості сцени (порожня назва, `target_words=0`) разом із планом — нічого не змінює й не лишає версії плану в історії.
3. `update_story` з мовою після фіксації: назва застосована, мова `rejected`, рейтинг `not_attempted`; таймаут кроку — `unknown`.
4. `create_story` з рейтингом понад межу Store-збірки — твору не стає в `GET /api/stories`.
5. `get_templates('de')` і `character_ids` з `../` — відмова без HTTP-запиту.

---

### Task 1: Сервер — рейтинг при створенні й запис плану поверх прочитаного

**Files:**
- Modify: `src/storygen/domain.py` (`StoryCreate`), `src/storygen/storage/repository.py:395` (`create_story`), `src/storygen/storage/authoring.py:42` (`update_scene_plan`), `src/storygen/storage/repository.py:52`, `src/storygen/authoring/service.py:9`, `src/storygen/web/routes_stories.py` (`ScenePatch`, `patch_scene`)
- Test: `tests/web/test_story_start.py`

**Interfaces:**
- Produces: `POST /api/stories` приймає `content_rating`; `PATCH /api/scenes/{id}` приймає `expected_plan_version_id`; 409 гонитви між планом і властивостями — JSON `{'detail', 'detail_original', 'plan_applied': true, 'revision': <int>}`.
- `update_scene_plan(repo, scene_id, text, expected_revision, expected_plan_version_id=_NOT_READ) -> Scene`.

- [ ] **Step 1: Тести (усі `@pytest.mark.req('MCP-BRIDGE')`)**
  - `test_create_story_with_rating_sets_current_and_initial` (`unrated_stories`): `POST /api/stories {'title','content_rating':{0,1,0}}` → 200; `story.content_rating == initial_content_rating == {0,1,0}`.
  - `test_create_story_without_rating_stays_unrated` (`unrated_stories`): `content_rating is None`.
  - `test_store_edition_refuses_rating_over_limit_and_creates_nothing` (`unrated_stories`, `store_edition`): `sexual=2` → 400; `GET /api/stories` порожній.
  - `test_stale_plan_is_409_and_saves_no_version`: план записано (голова A), потім автор переписав (голова B, свіжа ревізія); `PATCH` з `expected_plan_version_id=A` → 409 з `get_scene_text` у тексті; кількість версій `scene_plan` не змінилася.
  - `test_identical_plan_with_stale_id_is_409`: текст = поточний, id = старий → 409.
  - `test_plan_with_current_id_is_saved` і `test_plan_with_null_id_when_no_plan_version`: голова збігається / голови немає і `null` → 200, нова голова `plan`, версія без `external_origin`.
  - `test_plan_version_id_without_beats_is_400`.
  - `test_bad_field_with_plan_changes_nothing` (параметризація `{'title': ''}`, `{'target_words': 0}`, `{'prose_language': 'de'}` — останній 422 від FastAPI, решта 400): сцена й версії без змін.
  - `test_race_after_plan_reports_plan_applied`: `monkeypatch` `storygen.web.routes_stories.update_scene` кидає `RevisionConflict` → 409, `plan_applied is True`, `revision` = ревізія після плану.
  - `test_plan_from_chat_does_not_lock_language`: після `PATCH` з планом `PUT /language` → 200.
- [ ] **Step 2:** `pytest tests/web/test_story_start.py -q` → FAIL (поля невідомі, 422).
- [ ] **Step 3: Реалізація**
  - `StoryCreate.content_rating: ContentRating | None = None` (перенести `ContentRating` вище `StoryCreate`; з `Story` дубль прибрати). `create_story`: `_require_edition_limit(data.content_rating)` до вставки; `initial_content_rating = content_rating`.
  - `update_scene_plan`: якщо `expected_plan_version_id` передано — перевірка ревізії й голови `plan` **до** `unchanged_scene_text` і `save_version`, і повторно в `BEGIN IMMEDIATE`. Розбіжність → `RevisionConflict(STALE_PLAN)`.
  - `ScenePatch.expected_plan_version_id: str | None = Field(default=None, max_length=64)`; у `model_fields_set` без `beats` → `ValueError` (400).
  - `patch_scene`: зібрати `changes`, перевірити їх на копії до плану: `Scene.model_validate({**scene.model_dump(), **changes})` (pydantic `ValidationError` — `ValueError` → 400). Після плану `RevisionConflict` кроку властивостей → `JSONResponse(409, {..., 'plan_applied': True, 'revision': scene.revision})`.
- [ ] **Step 4:** тести пакета й наявні `tests/web` для сцен і творів → PASS.
- [ ] **Step 5:** commit `feat(mcp): story rating at creation and plan written over the read plan`.

### Task 2: Клієнт — п'ять інструментів і розширений `get_story`

**Files:**
- Modify: `src/storygen/mcp/bridge.py`
- Test: `tests/mcp/test_bridge_story_start.py`; `tests/mcp/test_bridge.py` (перелік 12 інструментів)

**Interfaces:**
- Consumes: маршрути Task 1; `GET /static/templates/{story-plan,characters}[-en].md`.
- Produces: `TOOLS` із 12 назв; `create_story`, `get_templates`, `update_story`, `add_scene`, `update_scene` за таблицею специфікації.

- [ ] **Step 1: Тести**
  - `test_tool_list_is_exactly_the_twelve_tools` (заміна старого) — серед назв немає `delete`, `trash`, `order`.
  - `test_create_story_returns_id_revision_language_rating`; `test_create_story_over_store_limit_is_error_and_nothing_created` (`store_edition`).
  - `test_templates_match_static_files` для `uk` і `en`; `test_templates_unknown_language_is_refused_without_request` (MockTransport, що падає на будь-який запит).
  - `test_get_story_has_revision_rating_target_and_characters`.
  - `test_update_story_applies_title_language_rating_in_order`; `test_update_story_stops_on_locked_language` (мова зафіксована зовнішньою чернеткою): помилка містить `applied: ['title']`, `rejected: 'language'`, `not_attempted: ['content_rating']`; `test_update_story_timeout_is_unknown` (транспорт, що проксює в застосунок і кидає `ReadTimeout` на `PUT …/language`); `test_update_story_needs_a_field`.
  - `test_add_scene_without_plan_gets_previous_plan_and_characters`: сцена з планом, `add_scene(position=1, character_ids=[id Анни])` → план попередньої сцени, персонаж призначений.
  - `test_update_scene_plan_needs_version_id_and_vice_versa` (без запиту); `test_update_scene_stale_plan_is_error` (план змінено після `get_scene_text`); `test_update_scene_plan_and_title`; `test_update_scene_bad_character_id_is_refused`.
  - `test_plan_from_chat_keeps_language_unlocked` (S22).
- [ ] **Step 2:** `pytest tests/mcp -q` → FAIL.
- [ ] **Step 3: Реалізація** за таблицею специфікації. `update_story`: кроки `title` → `PATCH /api/stories/{id}`, `language` → `PUT …/language`, `content_rating` → `PUT …/content-rating`; ревізія наступного кроку з відповіді попереднього; відмова → `ToolError` з JSON `{applied, rejected, error, not_attempted}`; `httpx.TransportError` → `{applied, unknown, not_attempted}` і порада перечитати `get_story`. Для `update_scene` 409 з `plan_applied` — текст помилки каже, що план записано, і радить перечитати сцену. `INSTRUCTIONS` доповнити порядком `create_story → get_templates → import_plan_and_characters → get_story`; описи інструментів кажуть, що змінюють і що грошей не коштують.
- [ ] **Step 4:** `pytest tests/mcp tests/web/test_story_start.py -q` → PASS.
- [ ] **Step 5:** commit `feat(mcp): tools to start a story from the chat`.

### Task 3: Контракт і документація

**Files:** `SPEC.MD` (MCP-BRIDGE), `docs/verification/traceability.json`, `docs/site/uk/mcp.md`, `docs/site/en/mcp.md`, `docs/site/sync.json`, специфікація пакета 2 (поправки за рішеннями виконавця).

- [ ] MCP-BRIDGE: 12 інструментів, `content_rating` у `POST /api/stories`, `expected_plan_version_id` і порядок перевірок, `plan_applied`; S06 (12 інструментів, без видалення/кошика/перестановки), нові S17–S22; відомі обмеження (частковий `update_story`, гонитва плану й властивостей).
- [ ] traceability: S06, S17–S22 → тести Task 1–2.
- [ ] Сайт uk/en: розділ «Почати твір із чату» / «Start a story from the chat»; `python scripts/check_site.py --rehash mcp`.
- [ ] `PYTHONIOENCODING=utf-8 python scripts/check_docs.py` → узгоджено.
- [ ] commit `docs(mcp): story start in MCP-BRIDGE and on the site`.
