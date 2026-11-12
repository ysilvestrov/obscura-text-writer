# Фільтри моделей Venice, PR 3 з 3: модель письменника для сцен 0–1 — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Дати письменнику необов'язкову другу модель для сцен, де жодна вісь ефективного рейтингу не дорівнює 2, зі спільним промптом і власними лімітами.

**Architecture:** Варіант — підоб'єкт `RoleSettings.low_rating_variant`. Маршрут вибирає одна функція `generation/role_routing.py::settings_for`, яку викликають `build_context` і `make_context` для етапів письменника (`draft`, `rewrite`). Контекст несе вже маршрутизовані налаштування, тож шлюз, облік, згода й позначка відмови з PR 2 працюють для моделі варіанта без окремого коду; виклики, що будують шлюз з налаштувань ролі, переходять на `context.settings.provider`.

**Tech Stack:** Python 3.12, FastAPI, pydantic, SQLite (JSON у `role_settings`), vanilla JS ES modules, node-тести через pytest-обгортки, Playwright.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-12-venice-model-filters-design.md` (розділ «Друга модель письменника (PR 3)», ключове рішення 3, вимога власника 5, Scenario MODEL-001-S02; затверджений прототип — блок «Окрема модель для сцен рівня 0–1»).

## Global Constraints

- `RoleSettings.low_rating_variant: RoleVariant | None = None`; `RoleVariant` — `provider: ProviderSettings`, `context_tokens`, `max_output_tokens`, `max_input_chars`, `temperature`, `timeout` (обмеження як у `RoleSettings`: `context_tokens ≥ 512`, `max_output_tokens ≥ 1` і менше за `context_tokens`, `max_input_chars ≥ 1`, `0 ≤ temperature ≤ 2`, `timeout > 0` або `None`).
- Варіант дозволений лише для ролі `writer`; запис варіанта для іншої ролі відхиляється з повідомленням «Окрема модель для сцен 0–1 доступна лише письменнику.»
- Маршрут: варіант, якщо роль `writer`, варіант задано і жодна вісь ефективного рейтингу сцени (`scene.content_rating or story.content_rating`) не дорівнює 2. Рейтинг не задано (`None`) → основна модель. Навпаки (основна для 0–1, варіант для 2) не буває.
- Промпт спільний: варіант не має власного промпту.
- Згода й позначка відмови діють для пари «writer + модель варіанта» так само, як для основної моделі.
- Міграції SQLite немає: поле в JSON-payload `role_settings` з типовим `None`; наявні налаштування працюють без змін.
- Комплекти ролей: `schema_version` 2 допускає `low_rating_variant`; версія 1 імпортується без змін; експорт пише 2 лише тоді, коли письменник має варіант.
- Документація українською, маркери OpenSpec англійською; сторінки сайту uk/en синхронно + `scripts/check_site.py --rehash <slug>`; Scenario у `docs/verification/traceability.json`; `scripts/check_docs.py` проходить.
- Коміти англійською, кожен закінчується `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Рішення плану (не зі специфікації)

- **Маршрут у двох точках, ідемпотентно.** `build_context` рахує бюджети пам'яті й контексту до `make_context`, тому маршрут застосовується на початку обох функцій. `settings_for` повертає налаштування з полями варіанта і `low_rating_variant=None`, тож повторний виклик нічого не змінює.
- **Етапи письменника** — `draft` і `rewrite` (assisted writing). Інші етапи не маршрутизуються.
- **Шлюз з контексту.** `worker.py` (обидва виклики `execute_stage`) і `pipeline.generate_scene` будують шлюз і подію `stage_started` з `context.settings.provider`, а не з налаштувань ролі. Шляхи impact і review уже так роблять.
- **Readiness:** якщо письменник має варіант і в запуску є етап письменника, перевіряється, що модель варіанта задана, а провайдер варіанта входить у перевірку явного ліміту бюджету. Поле `roles` відповіді readiness отримує запис `writer_low_rating` з `provider` і `model` варіанта, якщо хоча б одна ціль піде до варіанта.
- **Спільний провайдер** (`save_shared_provider`) варіант не змінює: варіант — власний вибір автора.
- **MCP-інструменти налаштувань** показують і змінюють варіант як звичайне поле розділу ролі; окремої роботи немає (перевіряється тестом, що `update_settings` для письменника не губить варіант).

## Review Focus

1. Рейтинг сцени не задано, а твору задано 0/1/1 — ефективний рейтинг береться з твору й сцена йде до варіанта; рейтинг твору й сцени не задано — основна модель. Тест — задача 1.
2. Зміна рейтингу сцени з 0/1/1 на 0/2/0 між двома запусками дає новий відбиток контексту й виклик основної моделі, а не повторне використання результату варіанта. Тест — задача 1.
3. Варіант має менший `context_tokens`, ніж основна модель: бюджет пам'яті й перевірка переповнення рахуються з лімітів варіанта. Тест — задача 1.
4. Вимкнення варіанта у формі (галочка знята) зберігає `low_rating_variant: null`, а не порожній об'єкт, що не пройде перевірку. Тест — задача 3.
5. Імпорт комплекту версії 1 і експорт комплекту без варіанта дають `schema_version` 1 — старі версії застосунку їх читають. Тест — задача 2.

---

### Task 1: Модель варіанта й маршрутизація

**Files:**
- Modify: `src/storygen/providers/models.py` (`RoleVariant`, поле `RoleSettings.low_rating_variant`)
- Create: `src/storygen/generation/role_routing.py`
- Modify: `src/storygen/generation/context.py` (`build_context`, `make_context`)
- Modify: `src/storygen/generation/worker.py:520-535,555-630`, `src/storygen/generation/pipeline.py:9-20`
- Modify: `src/storygen/authoring/blueprints.py` (`save_role_settings`: заборона для не-writer)
- Test: `tests/generation/test_role_routing.py` (новий)

**Interfaces:**
- Produces:
  - `class RoleVariant(DomainModel)` з полями з Global Constraints.
  - `WRITER_STAGES = frozenset({'draft','rewrite'})` у `role_routing.py`.
  - `uses_low_rating_variant(settings: RoleSettings, story, scene) -> bool`.
  - `settings_for(role_settings: RoleSettings, role: str, story, scene) -> RoleSettings` — копія з `provider`, `context_tokens`, `max_output_tokens`, `max_input_chars`, `temperature` варіанта (`timeout` варіанта, якщо задано, іде в `provider.timeout`) і `low_rating_variant=None`; інакше повертає вхід без змін.
  - `VARIANT_WRITER_ONLY = 'Окрема модель для сцен 0–1 доступна лише письменнику.'`

- [ ] **Step 1: Write the failing tests** (`@pytest.mark.req('MODEL-001')`):

```python
def test_writer_scene_without_level_two_goes_to_variant():  # MODEL-001-S02
    s = writer_with_variant(main='venice/unc', low='openrouter/x')
    assert settings_for(s, 'writer', story(0,1,1), scene(None)).provider.model == 'openrouter/x'
    assert settings_for(s, 'writer', story(0,0,0), scene((0,2,0))).provider.model == 'venice/unc'
    assert settings_for(writer_without_variant(), 'writer', story(0,1,1), scene(None)).provider.model == 'venice/unc'

def test_unset_rating_uses_main_model(): ...           # Review Focus 1
def test_routing_is_idempotent_and_only_for_writer():
    routed = settings_for(s, 'writer', story(0,0,0), scene(None))
    assert routed.low_rating_variant is None and settings_for(routed, 'writer', story(0,0,0), scene(None)) == routed
    assert settings_for(s, 'editor', story(0,0,0), scene(None)) is s

def test_draft_context_uses_variant_limits_and_changes_fingerprint(repo): ...  # Review Focus 2, 3: build_context('draft') → context.settings.context_tokens == variant's; rating 0/1/1 → 0/2/0 gives another fingerprint and main model
def test_pipeline_calls_variant_model_for_low_scene(repo): ...  # gateway_factory receives the variant provider for draft, the main provider for a 0/2/0 scene
def test_variant_model_needs_its_own_consent(repo): ...  # openrouter variant, story 0/1/0, no consent → ModelPolicyBlocked naming the variant model; consent for writer+variant model lets it through
def test_variant_is_rejected_for_other_roles(client): ...  # PUT editor settings with low_rating_variant → 400 VARIANT_WRITER_ONLY
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/generation/test_role_routing.py -q` (з `PYTHONPATH=src`)
Expected: FAIL — немає `role_routing`.

- [ ] **Step 3: Implement** — блок Interfaces і «Рішення плану» (дві точки маршруту, шлюз з контексту).

- [ ] **Step 4: Run the touched suites**

Run: `.venv/Scripts/python -m pytest tests/generation tests/web tests/integration -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/storygen tests/generation/test_role_routing.py
git commit -m "feat(writer): optional model for scenes rated 0-1, routed by scene rating"
```

### Task 2: Readiness і комплекти ролей

**Files:**
- Modify: `src/storygen/generation/readiness.py` (перевірка моделі варіанта, провайдер у перевірці бюджету, `roles['writer_low_rating']`)
- Modify: `src/storygen/role_profiles.py` (`schema_version: Literal[1, 2]`, правило варіанта, експорт)
- Test: `tests/generation/test_readiness.py`, `tests/test_role_profiles.py`

**Interfaces:**
- Consumes: `uses_low_rating_variant`, `RoleVariant` (задача 1).
- Produces: `ProfileDocument.schema_version: Literal[1, 2]`; документ версії 1 з варіантом відхиляється «Комплект версії 1 не може містити окрему модель письменника.»; варіант у ролі, що не `writer`, — `VARIANT_WRITER_ONLY`.

- [ ] **Step 1: Write the failing tests**

```python
def test_readiness_lists_variant_and_checks_its_budget(...): ...  # writer variant on openrouter, story 0/1/0: roles has writer_low_rating; no budget limit → 'Спершу задайте явний ліміт бюджету в налаштуваннях'
def test_readiness_skips_variant_for_level_two_targets(...): ...  # all targets 0/2/0 → no writer_low_rating entry
def test_profile_v1_imports_unchanged(...): ...
def test_profile_export_writes_v2_only_with_variant(...): ...  # Review Focus 5
def test_profile_v1_with_variant_is_rejected(...): ...
```

- [ ] **Step 2–4:** run → FAIL; implement; run `tests/generation tests/web` → PASS (і файл тестів комплектів).

- [ ] **Step 5: Commit** `feat(writer): readiness and role kits know the low-rating writer model`

### Task 3: Інтерфейс варіанта в налаштуваннях письменника

**Files:**
- Modify: `src/storygen/web/static/settings.js` (форма `writer`), за потреби новий модуль `src/storygen/web/static/writer-variant.js`
- Modify: `src/storygen/web/static/i18n.json` (uk, en), `src/storygen/web/static/app.css`
- Test: `tests/web/js/writer_variant.mjs` + обгортка, `tests/web/browser/writer-variant.spec.mjs`

**Interfaces:**
- Consumes: `mountModelPicker` (PR 1), `mountModelPolicy` (PR 2) — блок згоди для ролі `writer` і моделі варіанта.
- Produces: `variantPayload(form) -> object | null` — `null`, коли галочка знята (Review Focus 4).

Вигляд — за прототипом: під основною моделлю розділювач, галочка «Окрема модель для сцен рівня 0–1», пояснення, при увімкненні — провайдер, Base URL, список моделей, контекст, ліміт відповіді, ліміт символів входу, температура, timeout і блок згоди.

Тексти (uk / en):
- `writer.variant.toggle` — «Окрема модель для сцен рівня 0–1» / «Separate model for scenes rated 0–1»
- `writer.variant.hint` — «Необов’язково. Якщо не задано, всі сцени пише основна модель. Сцени, де хоч одна вісь рейтингу дорівнює 2, завжди пише основна модель.» / «Optional. If not set, the main model writes every scene. Scenes where any rating axis is 2 are always written by the main model.»
- `writer.variant.main_hint` — «Основна модель пише всі сцени, включно з рівнем 2.» / «The main model writes every scene, including level 2.»

- [ ] **Step 1: Write the failing tests** — node: `variantPayload` для знятої галочки дає `null`, для увімкненої — об'єкт із числовими полями; Playwright: увімкнути, вибрати модель, зберегти, перезавантажити — значення на місці; вимкнути й зберегти — `low_rating_variant` у відповіді `GET` налаштувань дорівнює `null`; блок згоди показується для моделі варіанта без Uncensored.
- [ ] **Step 2–4:** run → FAIL; implement; run `tests/web` і Playwright-спеки `writer-variant`, `model-policy`, `model-picker` (з `PYTHONPATH=<worktree>/src`) → PASS. PNG у `docs/images`, переписані браузерними тестами, не комітити.
- [ ] **Step 5: Commit** `feat(web): low-rating writer model in writer settings`

### Task 4: Документація

**Files:**
- Modify: `SPEC.MD` — MODEL-001 (варіант письменника, Scenario MODEL-001-S02), RATING-001 (зв'язок рейтингу сцени з маршрутом), технічний опис `role_routing.py` і поля, комплекти ролей версії 2.
- Modify: `docs/verification/traceability.json` (MODEL-001-S02 з тестами задач 1–3; Playwright — через ручну процедуру в `docs/verification/manual.md`).
- Modify: `docs/site/uk/models.md`, `docs/site/en/models.md` (і `content-rating.md` обома мовами, якщо там описано, хто пише сцени різних рівнів); rehash.
- Modify: журнал `docs/superpowers/plans/2026-10-20-remediation-progress.md` (без чисел verify).
- Modify: специфікація зміни — після злиття останнього PR рядок «Фактично: <розмір>, 3 PR, <n> задач» у «Оцінка» (детент `design-spec`, крок 9) — додає контролер після злиття, не в цій задачі.

- [ ] **Step 1:** оновити документи.
- [ ] **Step 2:** `PYTHONIOENCODING=utf-8 .venv/Scripts/python scripts/check_docs.py` → «Структура SPEC, матриця, тести, markers і локальні посилання узгоджені».
- [ ] **Step 3:** Commit `docs: MODEL-001 writer model for scenes 0-1, site pages`.
- [ ] **Step 4 (контролер):** `scripts/verify.py` з короткого шляху, запис у `docs/STATUS.md` і журнал.
