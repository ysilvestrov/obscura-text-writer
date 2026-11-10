# Мова твору й промптів — ядро (PR 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** твір має мову `uk`/`en`, сцена — необов'язкову мову прози; англійський твір отримує англійські промпти й заголовки контексту, англійська проза захищена від зміни чисел і заперечень і не оцінюється.

**Architecture:** новий модуль `storygen/language.py` — єдине місце для мови: ефективна мова, реєстр промптів і їх завантаження. Заголовки контексту — таблиця `storygen/generation/context_labels.py`. Мова прози сцени — селектор залежностей `scene/prose_language` за шаблоном `memory_kind_overrides` (#60).

**Tech Stack:** Python 3.10+, Pydantic 2, FastAPI, SQLite (payload JSON), pytest.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-10-story-language-design.md` (затверджено 10.11.2026), розділи «Обсяг → Ядро», «Нарізка».

## Global Constraints

- Мови: лише `uk` і `en`; тип `Language = Literal['uk','en']`.
- Наявні payload без нових полів читаються як `language='uk'`, `prose_language=None`; міграції SQL немає.
- Мова твору змінюється лише без версій із `source_run_id` (створених запуском моделі); інакше `RevisionConflict`-подібна відмова → HTTP 409.
- Ефективна мова прози сцени = `scene.prose_language or story.language`.
- Мова інструкцій моделі = мова твору (не сцени).
- Англійські промпти адаптовані: без українських правил типографіки (довге тире в репліках, український апостроф), діалог в англійських лапках; JSON-контракти, ключі, ліміти й заборони — ті самі.
- Код і коментарі англійською, повідомлення для інтерфейсу — українською через наявну локалізацію, як у сусідньому коді.
- Тимчасові каталоги поза репозиторієм — під `C:\tmp\`.

## Review Focus

1. Старий твір без поля `language` відкривається, генерує й експортується як раніше — байт у байт ті самі запити для `uk` (тест «запит українського твору не змінився» у Task 2).
2. Англійська сцена в українському творі: бриф і пам'ять лишаються свіжими після перемикання мови сцени, чернетка — застаріла (Task 4).
3. Власний промпт автора в англійському творі використовується як є, без підміни стандартним англійським (Task 2).
4. Повторний виклик зміни мови з тим самим значенням на зафіксованому творі не дає 409 (ідемпотентність, Task 1).
5. Українська сцена англійського твору оцінюється, англійська сцена українського — ні; автоматичний `edit_pair` для англійської сцени не ставиться, а не падає (Task 5).

---

### Task 1: Мова твору й сцени, фіксація, API

**Files:**
- Create: `src/storygen/language.py`
- Modify: `src/storygen/domain.py` (`StoryCreate`, `SceneCreate`)
- Modify: `src/storygen/storage/authoring.py` (нова `update_story_language`), `src/storygen/storage/repository.py` (обгортка)
- Modify: `src/storygen/web/routes_stories.py` (`ScenePatch.prose_language`), `src/storygen/web/routes_rating.py` або новий маршрут поруч із рейтингом
- Test: `tests/storage/test_story_language.py`

**Interfaces:**
- Produces:
  - `Language = Literal['uk','en']` у `storygen/language.py`
  - `story_language(story) -> Language` (повертає `story.language`)
  - `prose_language(story, scene) -> Language` (`scene.prose_language or story.language`; `scene=None` → мова твору)
  - `StoryCreate.language: Language = 'uk'`; `SceneCreate.prose_language: Language | None = None`
  - `Repository.update_story_language(story_id: str, language: Language, expected_revision: int) -> Story`
  - `PUT /api/stories/{story_id}/language` тіло `{"language": "en", "expected_revision": N}`
  - `ScenePatch.prose_language: Literal['uk','en','story'] | None` — `'story'` скидає до `None` (успадкування), `None` — без зміни.

- [ ] **Step 1: Failing tests** у `tests/storage/test_story_language.py`:
  - `test_story_defaults_to_ukrainian`: `create_story(StoryCreate(title='T'))` → `.language == 'uk'`; payload без ключа `language` (вставлений вручну JSON старого твору) читається як `'uk'`.
  - `test_language_changes_before_generation`: `update_story_language(id,'en',rev)` → `.language=='en'`, `revision==rev+1`.
  - `test_language_locked_after_model_version`: створити версію з `source_run_id='run-1'` у творі → `update_story_language(...,'en',...)` піднімає помилку, яку маршрут перетворює на 409; через `TestClient` перевірити код 409.
  - `test_same_language_is_idempotent_when_locked`: на зафіксованому `uk`-творі `update_story_language(id,'uk',rev)` повертає твір без зміни ревізії.
  - `test_scene_prose_language_patch`: `PATCH` сцени з `prose_language='en'` → `'en'`; з `'story'` → `None`; без поля → не змінюється; бриф сцени після зміни не позначено застарілим (на відміну від `beats`).
  - `test_prose_language_helper`: `prose_language(story_en, scene_none_lang) == 'en'`, `prose_language(story_uk, scene_en) == 'en'`.
- [ ] **Step 2:** `pytest tests/storage/test_story_language.py -q` → FAIL (немає поля/функції).
- [ ] **Step 3:** реалізація. `update_story_language` — `BEGIN IMMEDIATE`, CAS на `revision` (`RevisionConflict`), перевірка `SELECT 1 FROM versions WHERE story_id=? AND json_extract(payload,'$.source_run_id') IS NOT NULL LIMIT 1` → `ValueError('Мову твору зафіксовано: у творі вже є матеріал, створений моделлю')` (маршрут → 409; додати текст до каталогу локалізації EN). `update_scene_metadata` для `prose_language` не викликає `invalidate_in_transaction` (застарілість дає селектор із Task 4); для решти полів поведінка без змін.
- [ ] **Step 4:** тести PASS; `pytest tests/storage tests/web -q -x` без регресій.
- [ ] **Step 5:** commit `feat(language): story language and scene prose language with lock (#32)`.

### Task 2: Реєстр промптів і англійські промпти

**Files:**
- Modify: `src/storygen/language.py` (реєстр і `load_prompt`)
- Modify: `src/storygen/generation/prompts.py`, `generation/context.py:139-144` (асистоване переписування), `generation/impact_context.py:17`, `impact/chunking.py:57`, `review/planning.py:80`, `review/planning4.py:22`, `generation/publication_metadata.py:19`, `evaluation/prompting.py:42` (лише через реєстр, `uk`), `prompt_contracts.py` (`MARKDOWN_PRESERVATION`, `BRIEF_INTRODUCED_CONTRACT` → словники за мовою), `rating/instructions.py` (тексти за мовою), `web/routes_settings.py` (стандартний промпт за мовою твору)
- Create: `src/storygen/generation/resources/*_en_v*.txt` — по одному на кожен запис реєстру, крім оцінювача
- Test: `tests/generation/test_prompt_language.py`

**Interfaces:**
- Consumes: `Language`, `story_language` (Task 1).
- Produces:
  - `PROMPTS: dict[str, tuple[str, str, frozenset[Language]]]` — ключ `'<name>_<version>'` (напр. `'brief_v2'`), значення `(package, name, languages)`; оцінювач `'evaluator_v1'` лише `{'uk'}`.
  - `load_prompt(key: str, language: Language) -> str` — читає `resources/{name}_{language}_{version}.txt`; невідомий ключ або мова поза набором → `ValueError`.
  - `default_prompt(stage: str, language: Language = 'uk') -> str`; `role_prompt(stage, settings, language: Language = 'uk') -> str`.
  - `markdown_preservation(language) -> str`, `brief_introduced_contract(language) -> str` у `prompt_contracts.py`; старі константи лишаються як `uk`-значення.
  - `rating_instructions(repo, story, scene, stage, settings)` бере мову з `story_language(story)`.

- [ ] **Step 1: Failing tests:**
  - `test_registry_parity`: для кожного ключа реєстру з `'en'` у наборі існують обидва файли; кожен файл `*_uk_v*.txt`, на який посилається реєстр, має пару; файли `*_en_*` не містять кирилиці.
  - `test_ukrainian_requests_unchanged`: для українського твору системне повідомлення `make_context` етапів `prepare, brief, draft, edit, memory, rewrite` дорівнює рядку, зібраному старим способом (зафіксувати SHA-256 поточних системних повідомлень на синтетичному творі до зміни — записати хеші в тест на першому кроці).
  - `test_english_story_gets_english_prompts`: англійський твір, ті самі етапи → системне повідомлення починається з тексту відповідного `*_en_*` файла й не містить кирилиці (автор­ський матеріал синтетичний латиницею).
  - `test_custom_prompt_kept_in_english_story`: власний промпт ролі письменника (будь-якою мовою) в англійському творі — системне повідомлення містить його, а не стандартний англійський.
  - `test_evaluator_english_rejected`: `load_prompt('evaluator_v1','en')` → `ValueError`.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** реалізація; англійські файли адаптувати з українських за глобальним обмеженням про типографіку. Зберегти ті самі розділи, ключі JSON і числові ліміти; українські приклади замінити англійськими еквівалентами.
- [ ] **Step 4:** PASS; `pytest tests/generation tests/review tests/impact -q -x`.
- [ ] **Step 5:** commit `feat(language): prompt registry and English prompt set (#32)`.

### Task 3: Заголовки контексту й вказівка мови прози сцени

**Files:**
- Create: `src/storygen/generation/context_labels.py`
- Modify: `generation/context.py` (усі заголовки секцій для моделі), `memory/story_time.py::day_label`, збирачі секцій у `generation/impact_context.py`, `impact/chunking.py`, `review/planning.py`, `review/planning4.py`, `generation/publication_metadata.py` і `memory/*`, що формують текст для моделі
- Test: `tests/generation/test_context_language.py`

**Interfaces:**
- Consumes: `story_language`, `prose_language` (Task 1), `load_prompt` (Task 2).
- Produces:
  - `LABELS: dict[str, dict[Language, str]]`; `label(key: str, language: Language, **params) -> str` (`str.format`).
  - `day_label(key, language: Language = 'uk')` → «день N» / «day N».
  - `prose_language_directive(story, scene, language_of_instructions) -> str | None` — `None`, якщо мова прози = мова твору; інакше одна фраза мовою твору: `uk` → «Пиши прозу цієї сцени англійською мовою.», `en` → «Write this scene's prose in Ukrainian.» Додається до системного повідомлення етапів `draft`, `edit`, `rewrite`.

- [ ] **Step 1: Failing tests:**
  - `test_label_tables_have_same_keys`: усі ключі `LABELS` мають обидві мови; англійські значення без кирилиці.
  - `test_english_request_has_no_cyrillic`: англійський синтетичний твір (2 сцени, план, персонажі, прийнята проза й пам'ять латиницею) → для етапів `brief, draft, edit, memory, rewrite` жодне повідомлення запиту не містить кирилиці.
  - `test_impact_review_publication_english`: ті самі перевірки для запитів аналізу впливу, послідовної перевірки й метаданих публікації англійського твору (на синтетичних даних наявних тестів цих модулів).
  - `test_directive_for_foreign_scene`: український твір, сцена `prose_language='en'` → системне повідомлення `draft` закінчується (до інструкцій рейтингу) фразою «Пиши прозу цієї сцени англійською мовою.»; бриф і пам'ять цієї сцени без фрази.
  - `test_day_label_english`: `day_label('day:3','en') == 'day 3'`.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** реалізація; діагностичні повідомлення для інтерфейсу не чіпати — лише текст, що йде в запит моделі.
- [ ] **Step 4:** PASS; тест «запит українського твору не змінився» з Task 2 далі зелений.
- [ ] **Step 5:** commit `feat(language): localized context labels and scene prose directive (#32)`.

### Task 4: Селектор `scene/prose_language` і сумісність старих знімків

**Files:**
- Modify: `src/storygen/dependency_models.py` (дозволене поле), `src/storygen/storage/snapshots.py` (запис селектора, `selector_value`, правило для старих знімків у `compare_snapshot` поруч із `memory_projection_policy`)
- Test: `tests/storage/test_prose_language_staleness.py`

**Interfaces:**
- Consumes: `prose_language` (Task 1).
- Produces: селектор `DependencySelector(kind='scene', owner_id=scene.id, field='prose_language', expected=<Language>)`, записаний для scope `draft`, `prose_edit`, `patches`, `author_rewrite`; `selector_value` повертає `prose_language(story, scene)`.

- [ ] **Step 1: Failing tests:**
  - `test_switching_scene_language_stales_draft_not_brief`: сцена з брифом, чернеткою й прозою → `prose_language='en'` → чернетка й проза застарілі, бриф і пам'ять ні.
  - `test_switch_back_restores_freshness`: повернення `'story'` (= `uk`) → чернетка знову свіжа.
  - `test_legacy_snapshot_without_selector_treated_as_uk`: знімок scope `draft` без селектора (зібраний вручну, як у старих даних) → свіжий при `uk`, застарілий після перемикання сцени на `en`.
  - `test_author_text_without_snapshot_not_checked`: авторська версія `manual` без знімка лишається свіжою після перемикання.
  - `test_story_language_change_irrelevant_after_lock`: (захист інваріанту) селектор не записується для scope `brief`/`memory`.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** реалізація.
- [ ] **Step 4:** PASS; `pytest tests/storage tests/generation -q -x`.
- [ ] **Step 5:** commit `feat(language): scene prose language dependency selector (#32)`.

### Task 5: Захист редактури й вимкнення оцінювання для англійської

**Files:**
- Modify: `src/storygen/copyediting.py:30-38`, `src/storygen/evaluation/story_adapter.py::build_evaluation_case`, `src/storygen/generation/worker.py:116-126`
- Test: `tests/generation/test_english_guards.py`, `tests/evaluation/test_evaluation_language.py`

**Interfaces:**
- Produces: `protected_numbers(text)` і `protected_negations(text)` — без зміни сигнатур, словники доповнені англійськими.
- Produces: `evaluation_language_error(repo, story, scenes) -> str | None` у `story_adapter.py` — повідомлення, якщо хоч одна сцена випадку має ефективну мову прози `en`.

Рішення плану (уточнення тіла специфікації, розділ власника не змінюється): словники захисту — **об'єднання** українських і англійських слів незалежно від мови сцени, а не вибір за мовою. Це строгіше (англійське заперечення в українській прозі теж захищене), не потребує передавати мову в `apply_copyedits`/`rewrite_diff` і не послаблює жодної наявної перевірки. Записати як поправку в специфікації.

- [ ] **Step 1: Failing tests:**
  - `test_english_number_change_rejected`: `apply_copyedits` на англійському тексті з правкою `three`→`four` → `ValueError('Точкова редактура змінила числовий факт')`.
  - `test_english_negation_removed_rejected`: `did not go`→`did go` і `didn't`→`did` → відмова «змінила заперечення».
  - `test_rewrite_diff_warns_english_negation`: наявна функція попереджень `rewrite_diff.py` повертає попередження про заперечення для тієї самої пари.
  - `test_ukrainian_guards_unchanged`: наявні українські приклади з `tests/` дають той самий результат (запустити наявні тести).
  - `test_english_scene_evaluation_rejected`: `build_evaluation_case` для сцени з ефективною мовою `en` → `ValueError` з причиною; для `uk`-сцени англійського твору — успіх.
  - `test_worker_skips_edit_pair_for_english_scene`: запуск `scene`/`remaining` з політикою оцінювання не `off` → у задачах немає `evaluate` для англійської сцени, а для української є.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** реалізація. Англійські числівники: `zero…twenty`, `thirty…ninety`, `hundred`, `thousand`, `million`, `first…tenth`; заперечення: `not`, `no`, `never`, `nothing`, `nobody`, `none`, `neither`, `nor`, `nowhere` і форма `\w+n[’']t\b`.
- [ ] **Step 4:** PASS; `pytest tests/generation tests/evaluation -q -x`.
- [ ] **Step 5:** commit `feat(language): English editing guards, no evaluation for English prose (#32)`.

### Task 6: SPEC, traceability, журнал

**Files:**
- Modify: `SPEC.MD` (новий Requirement STORY-LANGUAGE зі сценаріями S01 фіксація, S02 англійські промпти, S03 мова прози сцени й застарілість, S04 сумісність старих знімків, S05 захист редактури англійською, S06 оцінювання англійської прози; оновити PROMPT-CONTRACT, EDIT-001, EVAL-003), `docs/verification/traceability.json`, `docs/superpowers/specs/2026-11/2026-11-10-story-language-design.md` (поправка про об'єднані словники; посилання на #93), `docs/superpowers/plans/2026-10-20-remediation-backlog.md` (статус R-27), `docs/superpowers/plans/2026-10-20-remediation-progress.md`
- Test: `python scripts/check_docs.py`

- [ ] **Step 1:** SPEC + traceability (кожен сценарій → тести Task 1–5); `@pytest.mark.req('STORY-LANGUAGE')` на тестах.
- [ ] **Step 2:** `PYTHONIOENCODING=utf-8 python scripts/check_docs.py` → «узгоджені».
- [ ] **Step 3:** commit `docs(spec): STORY-LANGUAGE core (#32)`.

Користувацька документація — у PR 2 разом з інтерфейсом: у PR 1 мову можна задати лише через API; PR опис це пояснює.
