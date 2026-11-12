# Фільтри моделей Venice, PR 2 з 3: згода й блокування після відмови — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Замінити жорстку вимогу `uncensored=true` для генерації на правило «каталожна перевірка + згода автора» і блокувати пару «роль + модель» після структурної відмови через зміст.

**Architecture:** Правило живе в одному модулі `providers/policy.py`, стан — у `app_settings` через `storage/model_policy_store.py`. Єдина точка перевірки й запису — `generation/stages.py::execute_stage`, через яку проходять усі етапи генерації (конвеєр, assisted writing, editor loop, impact, review, пам'ять, класифікація, публікація). Для Venice ознаку Uncensored знає лише каталог, тому згоду для Venice перевіряє `OpenAIGenerationGateway.stream` одразу після `validate_model`, до резервування бюджету. Readiness повторює офлайн-частину перевірки, щоб автор побачив блокування до запуску.

**Tech Stack:** Python 3.12, FastAPI, SQLite (`app_settings`), pydantic, vanilla JS ES modules, node-тести через pytest-обгортки, Playwright.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-12-venice-model-filters-design.md` (розділ «Згода й позначка відмови (PR 2)», ключові рішення 2, 4, 5, Scenario MODEL-003-S01…S05, MODEL-004-S01…S03).

## Global Constraints

- Згода потрібна, коли модель не локальна, `uncensored is not True`, а рейтинг запиту має хоча б одну вісь > 0 (рейтинг запиту — максимум за кожною віссю серед рейтингу твору й ефективних рейтингів сцен, матеріал яких входить у запит).
- Ключі `app_settings`: `model_consent:<role>:<endpoint>:<model>` і `model_refusal:<role>:<endpoint>:<model>`; `endpoint` — `base_url` без кінцевого `/`, схема й хост у нижньому регістрі.
- Згода: `{role, provider, base_url, model, consented_at}`. Позначка: `{role, provider, base_url, model, refusals:[{rating:[s,v,t], scene_id|null, story_id, attempt_id|null, at, category}]}`.
- Блокування: виклик блокується, якщо хоча б один збережений вектор за кожною віссю ≤ рейтингу запиту. Новий вектор прибирає з набору ті, що за кожною віссю ≥ нового.
- Відмова — це `finish_reason == 'content_filter'` (категорія `refusal_content`) або `terminal.refusal` (категорія `refusal_unknown`). Текстові відмови не розпізнаються.
- Ролі політики: `planner`, `writer`, `editor`, `memory`. Оцінювач поза зміною: він і далі вимагає `uncensored=true`.
- Автоматичного перемикання на іншу модель немає.
- Відповіді API не містять значень ключів чи тексту твору.
- Документація українською, маркери OpenSpec англійською; сторінки сайту uk/en синхронно, `python scripts/check_site.py --rehash <slug>`; кожен Scenario — у `docs/verification/traceability.json`; `python scripts/check_docs.py` проходить.
- Коміти англійською, кожен закінчується `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Рішення плану (не з специфікації)

- **Локальний провайдер завжди loopback.** `ProviderSettings.endpoint` уже відхиляє `local` з не-loopback адресою, тож `is_local(settings)` — це `provider == 'local'` плюс захисна перевірка хоста. Частина MODEL-003-S04 «той самий провайдер `local` з не-loopback URL — потрібна згода» недосяжна; хмарні адреси теж зафіксовані. Тому S04 перевіряє: локальна модель згоди не потребує; ключ згоди включає endpoint (тест на рівні сховища: інший `base_url` дає інший запис). Поправка до специфікації — у задачі 6.
- **Readiness не звертається до каталогу.** Для Venice згоду readiness не перевіряє (Uncensored знає лише каталог). Модель Venice без Uncensored і без згоди зупиняється на першому етапі перевіркою в шлюзі до будь-якого платного запиту. Позначку відмови readiness перевіряє для всіх провайдерів.
- **Багатосценні етапи.** Рейтинг запиту для `impact*` і `review_part` — максимум за рейтингом твору, сценою `context.scene_id` і сценами, яким належать версії з `context.input_refs` (`VersionRef.scene_id`).
- **Згода в інтерфейсі** — лише у формах ролей (`planner`, `writer`, `editor`, `memory`) і в налаштуваннях класифікації (роль `editor`). Галочка діє одразу через API для моделі, вибраної у формі, без збереження форми. Спільний віджет підключення згоди не показує, бо згода належить ролі.
- **Чат (`external_origin`)** не перевіряється й не записує позначок: модель там — чат-клієнт, а не провайдер Obscura.

## Review Focus

1. Рейтинг твору не задано (`None`), а сцена має власний рейтинг — рейтинг запиту бере сцену, вісь твору рахується як 0; блокування не падає з помилкою. Тест — задача 1.
2. Відмова на етапі, спроба якого інакше завершилася (чернетка з `terminal.refusal` і текстом), усе одно записує позначку. Тест — задача 3.
3. Відповідь чату через `execute_stage(..., external_origin=...)` не перевіряє згоду й не пише позначку. Тест — задача 3.
4. Зміна моделі у формі одразу показує стан згоди й позначки для нової моделі, а не стару галочку. Тест — задача 5.
5. Збій каталогу Venice у шлюзі не обходить перевірку згоди: діє наявна помилка `validate_model`, платний запит не надсилається. Тест — задача 2.

---

### Task 1: Політика й сховище

**Files:**
- Create: `src/storygen/providers/policy.py`
- Create: `src/storygen/storage/model_policy_store.py`
- Modify: `src/storygen/storage/repository.py` (метод `model_policy(action, **data)` поруч з `billing`/`impact`)
- Test: `tests/providers/test_model_policy.py`

**Interfaces:**
- Produces (`providers/policy.py`):
  - `class ModelPolicyBlocked(ValueError)` з атрибутом `kind: Literal['consent','refusal']`.
  - `POLICY_ROLES = ('planner','writer','editor','memory')`.
  - `STAGE_POLICY_ROLE: dict[str,str]` = `{'prepare':'planner','brief':'planner','impact_delta':'planner','impact_check':'planner','impact_part':'planner','review_part':'planner','publication_suggest':'planner','draft':'writer','rewrite':'writer','edit':'editor','classify':'editor','memory':'memory'}`.
  - `endpoint(settings: ProviderSettings) -> str`.
  - `is_local(settings: ProviderSettings) -> bool`.
  - `request_rating(view, story, scene_ids: Iterable[str]) -> tuple[int,int,int]` — `view` має `get_scene(id)`; сцени, яких немає, пропускаються.
  - `context_rating(repo, context) -> tuple[int,int,int]` — сцени: `context.scene_id` і `repo.get_version(ref).scene_id` для `context.input_refs` (невідома версія пропускається).
  - `needs_consent(settings, uncensored: bool | None, rating) -> bool`.
  - `blocking_refusal(refusals: list[dict], rating) -> dict | None` — перший запис, що блокує.
  - `check_refusal(repo, role, settings, rating) -> None` і `check_consent(repo, role, settings, rating, uncensored: bool | None) -> None` — піднімають `ModelPolicyBlocked`.
  - `record_refusal(repo, role, settings, rating, *, story_id, scene_id, attempt_id, category) -> None`.
- Produces (`repo.model_policy`): дії `get_consent`, `set_consent`, `delete_consent`, `get_refusal`, `add_refusal`, `delete_refusal`; аргументи `role, provider, base_url, model` (+ `entry` для `add_refusal`). `get_*` повертає dict або `None`. Запис — один `INSERT OR REPLACE` у транзакції репозиторію, як у `billing_store.write`.

- [ ] **Step 1: Write the failing tests** (`tests/providers/test_model_policy.py`, маркери `@pytest.mark.req('MODEL-003')` / `('MODEL-004')`):

```python
def test_cloud_model_without_uncensored_needs_consent_only_above_zero():
    s = ProviderSettings(provider='openrouter', model='x/y')
    assert needs_consent(s, None, (0, 1, 0)) is True
    assert needs_consent(s, None, (0, 0, 0)) is False
    assert needs_consent(ProviderSettings(provider='venice', model='v'), True, (2, 2, 2)) is False

def test_local_model_never_needs_consent():  # MODEL-003-S04
    assert is_local(ProviderSettings(provider='local', model='m')) is True
    assert needs_consent(ProviderSettings(provider='local', model='m'), None, (2, 2, 2)) is False

def test_consent_is_keyed_by_role_endpoint_and_exact_model(repo):  # MODEL-003-S03, S04
    s = ProviderSettings(provider='openrouter', model='x/y')
    repo.model_policy('set_consent', role='writer', provider='openrouter', base_url=s.base_url, model='x/y')
    check_consent(repo, 'writer', s, (2, 0, 0), None)          # passes
    with pytest.raises(ModelPolicyBlocked) as e:
        check_consent(repo, 'editor', s, (2, 0, 0), None)
    assert e.value.kind == 'consent'
    with pytest.raises(ModelPolicyBlocked):
        check_consent(repo, 'writer', ProviderSettings(provider='openrouter', model='x/z'), (2, 0, 0), None)
    assert repo.model_policy('get_consent', role='writer', provider='openrouter', base_url='https://other.example/v1', model='x/y') is None

def test_refusal_vectors_block_per_axis():  # MODEL-004-S02
    refusals = [{'rating': [2, 0, 0]}, {'rating': [0, 2, 0]}]
    assert blocking_refusal(refusals, (1, 1, 0)) is None
    assert blocking_refusal(refusals, (2, 1, 0)) is not None
    assert blocking_refusal(refusals, (0, 2, 2)) is not None
    assert blocking_refusal([{'rating': [0, 0, 0]}], (0, 0, 0)) is not None

def test_new_refusal_keeps_the_set_minimal(repo):
    s = ProviderSettings(provider='openrouter', model='x/y')
    for r in [(2, 2, 0), (2, 0, 0), (2, 1, 0)]:
        record_refusal(repo, 'writer', s, r, story_id='s', scene_id=None, attempt_id=None, category='refusal_content')
    stored = repo.model_policy('get_refusal', role='writer', provider='openrouter', base_url=s.base_url, model='x/y')
    assert [e['rating'] for e in stored['refusals']] == [[2, 0, 0]]

def test_unset_story_rating_counts_as_zero(repo_with_story):  # Review Focus 1, MODEL-003-S05
    # story.content_rating None, scene A own rating 2/0/0, scene B without own rating
    assert request_rating(view, story, [scene_a.id]) == (2, 0, 0)
    assert request_rating(view, story, [scene_b.id]) == (0, 0, 0)
    assert request_rating(view, story, []) == (0, 0, 0)
```

Точний текст повідомлень перевіряється в задачі 3; тут — `kind` і факт винятку.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/providers/test_model_policy.py -q` (з `PYTHONPATH=src`)
Expected: FAIL — `ModuleNotFoundError: storygen.providers.policy`.

- [ ] **Step 3: Implement `policy.py`, `model_policy_store.py`, `repository.model_policy`**

Повідомлення (`policy.py`, точний текст; рейтинг форматується `s/v/t`, назва ролі з `ROLE_LABELS = {'planner':'Планувальник','writer':'Письменник','editor':'Редактор','memory':'Пам’ять'}`):

```python
CONSENT_REQUIRED = ('Модель «{model}» не має позначки Uncensored, а рейтинг цього запиту {rating}. '
    'Підтвердьте в налаштуваннях ролі «{role}», що погоджуєтеся на виклики цієї моделі для дорослого змісту, або виберіть іншу модель.')
REFUSAL_BLOCKED = ('Модель «{model}» уже відмовила ролі «{role}» через зміст на запиті з рейтингом {seen}. '
    'Виклики з рейтингом {rating} заблоковано: зніміть позначку в налаштуваннях ролі або виберіть іншу модель.')
```

`endpoint`: `urlsplit`, схема й хост у нижньому регістрі, шлях без кінцевого `/`. `record_refusal` додає `at` (UTC ISO) і викликає `add_refusal`, який мінімізує набір у сховищі.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/providers/test_model_policy.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/storygen/providers/policy.py src/storygen/storage/model_policy_store.py src/storygen/storage/repository.py tests/providers/test_model_policy.py
git commit -m "feat(policy): model consent and refusal records with per-axis blocking"
```

### Task 2: Каталожна перевірка Venice без Uncensored і згода в шлюзі

**Files:**
- Modify: `src/storygen/providers/venice.py` (`validate_model`)
- Modify: `src/storygen/providers/streaming.py:93-100`
- Modify: `src/storygen/generation/context.py:53-75` (`ContextBundle`)
- Test: `tests/providers/test_venice.py`, `tests/providers/test_streaming_policy.py` (новий)

**Interfaces:**
- Consumes: `check_consent`, `ModelPolicyBlocked` (задача 1).
- Produces:
  - `validate_model(client, model_id, requires_schema, *, context_tokens=None, max_output_tokens=None, require_uncensored=True) -> dict` — повертає `model_spec`; шукає в `catalog_models`; з `require_uncensored=True` відхиляє модель без `uncensored is True` тим самим текстом, що й зараз. Оцінювач (`evaluation/gateway.py:62`) не змінюється й лишається з типовим `True`.
  - `ContextBundle.policy_role: str | None = None`, `ContextBundle.policy_rating: tuple[int,int,int] | None = None` — поза відбитком (`fingerprint` їх не включає; задача 3 заповнює їх через `model_copy`).
  - Шлюз: для `provider == 'venice'` викликає `validate_model(..., require_uncensored=False)`, потім, якщо `context.policy_role` задано, `check_consent(repo, context.policy_role, settings, context.policy_rating, spec.get('uncensored') is True)`. Блокування повертає подію `GenerationEvent(type='error', failure={'category':'model_policy','message':str(exc)}, message=str(exc))` до `accounting.before` і до `chat.completions.create`. Шлюзу потрібен `repo`: беріть його з `self.accounting.repo`; без `accounting` перевірка згоди в шлюзі пропускається (тести з фейковими шлюзами й локальні запуски без обліку).

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.req('MODEL-003')
def test_generation_accepts_catalog_model_without_uncensored():  # test_venice.py
    spec = validate_model(fake_client([model('plain', uncensored=False)]), 'plain', False, require_uncensored=False)
    assert spec['uncensored'] is False

def test_evaluator_still_requires_uncensored():
    with pytest.raises(VeniceModelUnavailable):
        validate_model(fake_client([model('plain', uncensored=False)]), 'plain', False)

@pytest.mark.req('MODEL-003')
def test_gateway_blocks_venice_model_without_consent_before_sending(repo):  # test_streaming_policy.py, MODEL-003-S02
    # MockTransport: /models returns 'plain' (uncensored false); /chat/completions must never be hit
    events = list(gateway.stream(context.model_copy(update={'policy_role':'writer','policy_rating':(2,0,0)}), threading.Event()))
    assert events[-1].type == 'error' and events[-1].failure['category'] == 'model_policy'
    assert completions_calls == [] and no billing reservation exists

def test_gateway_lets_uncensored_or_consented_venice_model_through(repo): ...
def test_gateway_catalog_failure_does_not_bypass_check(repo):  # Review Focus 5
    # /models returns 500 → existing failure path, completions never called
```

Додайте MODEL-003-S01 (наявний тест `test_venice_generation_cannot_bypass_catalog_filter_or_schema_support`) — оновіть його під нове правило: модель поза каталогом або `offline` усе одно не проходить.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/providers/test_venice.py tests/providers/test_streaming_policy.py -q`
Expected: FAIL (`require_uncensored` unexpected keyword; немає `policy_role`).

- [ ] **Step 3: Implement** — зміни з блоку Interfaces.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/providers tests/evaluation -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/storygen/providers/venice.py src/storygen/providers/streaming.py src/storygen/generation/context.py tests/providers/test_venice.py tests/providers/test_streaming_policy.py
git commit -m "feat(providers): Venice generation checks the catalog and consent, not the uncensored flag"
```

### Task 3: Перевірка й запис у `execute_stage`, перевірка в readiness

**Files:**
- Modify: `src/storygen/generation/stages.py` (`execute_stage`)
- Modify: `src/storygen/generation/readiness.py:124-128`
- Test: `tests/generation/test_model_policy_stages.py` (новий), `tests/generation/test_readiness.py` (додати)

**Interfaces:**
- Consumes: усе з задачі 1; `ContextBundle.policy_role/policy_rating` (задача 2).
- Produces: поведінка; нових публічних імен немає.

Поведінка `execute_stage`, коли `external_origin is None` і `stage in STAGE_POLICY_ROLE`:
1. `role = STAGE_POLICY_ROLE[stage]`, `rating = context_rating(repo, context)`.
2. `check_refusal(repo, role, context.settings.provider, rating)`; якщо `provider != 'venice'`, також `check_consent(..., uncensored=None)`. `ModelPolicyBlocked` піднімається з `execute_stage` до створення спроби — так само, як `enforce_rating` з `make_context`.
3. Шлюзу передається `context.model_copy(update={'policy_role': role, 'policy_rating': rating})`.
4. Після відповіді: якщо `attempt.finish_reason == 'content_filter'` або `terminal and terminal.refusal`, то `record_refusal(repo, role, context.settings.provider, rating, story_id=context.story_id, scene_id=scene_id, attempt_id=attempt.id, category='refusal_content' if finish_reason == 'content_filter' else 'refusal_unknown')` — незалежно від того, чи спроба завершилася. Збій запису не ламає спробу: `attempt.context['model_policy_warning']`.

Readiness: у циклі поруч з `enforce_rating` для кожної цілі й етапу — `check_refusal` і (не для Venice) `check_consent` з `request_rating(view, rated_story, [target.id])` і налаштуваннями `settings[STAGE_POLICY_ROLE[stage]]`; для `prepare` — `request_rating(view, story, [])` з `settings['planner']`.

- [ ] **Step 1: Write the failing tests** (фейковий шлюз, провайдер `openrouter`, щоб не потрібен був каталог):

```python
@pytest.mark.req('MODEL-003')
def test_draft_without_consent_is_blocked_with_author_text(repo, story_rated_1_0_0):  # S02
    with pytest.raises(ModelPolicyBlocked) as e:
        execute_stage(repo, scene.id, 'draft', ctx_openrouter, FakeGateway('text'), Event(), noop)
    assert 'не має позначки Uncensored' in str(e.value) and '1/0/0' in str(e.value)
    assert FakeGateway.calls == 0

def test_consent_lets_any_story_through_and_model_change_resets_it(repo): ...  # S03
def test_scene_rated_above_zero_story_needs_consent_only_for_that_scene(repo): ...  # S05: story 0/0/0, scene A 2/0/0, scene B none

@pytest.mark.req('MODEL-004')
def test_content_filter_records_refusal_and_blocks_same_or_higher(repo): ...  # S01: refuse on 1/1/0 → 1/1/0 and 2/1/0 blocked, 0/1/0 allowed; delete_refusal restores
def test_refusal_flag_on_completed_draft_still_records(repo): ...  # Review Focus 2
def test_impact_refusal_records_planner_with_max_scene_rating(repo): ...  # S03: input_refs from scenes 0/0/0 and 0/2/0 → refusal rating [0,2,0], role planner
def test_chat_answer_is_never_checked_or_recorded(repo): ...  # Review Focus 3: external_origin set, no consent, refusal record absent

def test_readiness_reports_missing_consent_before_run(client): ...  # readiness returns 400 with CONSENT_REQUIRED for openrouter writer, story rating 1/0/0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/generation/test_model_policy_stages.py -q`
Expected: FAIL (блокування немає).

- [ ] **Step 3: Implement** — поведінка вище.

- [ ] **Step 4: Run the touched suites**

Run: `.venv/Scripts/python -m pytest tests/generation tests/review tests/memory tests/web -q`
Expected: PASS. Наявні тести з `openrouter` і рейтингом > 0, що впадуть через нову вимогу згоди, оновіть фікстурою згоди (`repo.model_policy('set_consent', ...)`), а не послабленням правила; перелічіть їх у звіті.

- [ ] **Step 5: Commit**

```bash
git add src/storygen/generation/stages.py src/storygen/generation/readiness.py tests/generation
git commit -m "feat(generation): consent and refusal block in execute_stage and readiness"
```

### Task 4: API політики моделі

**Files:**
- Create: `src/storygen/web/routes_model_policy.py`
- Modify: `src/storygen/web/app.py` (підключення роутера, як інші `routes_*`)
- Test: `tests/web/test_model_policy_api.py`

**Interfaces:**
- Consumes: `repo.model_policy`, `POLICY_ROLES`, `endpoint` (задача 1).
- Produces (для задачі 5):
  - `GET /api/model-policy?role=&provider=&model=&base_url=` → `200 {"consent": {"consented_at": str} | null, "refusals": [{"rating":[s,v,t], "at": str, "category": str, "story_id": str, "scene_id": str|null}]}`.
  - `PUT /api/model-policy/consent` body `{"role","provider","model","base_url"?}` → `200` з тим самим тілом, що GET.
  - `DELETE /api/model-policy/consent?role=&provider=&model=&base_url=` → `200` (те саме тіло).
  - `DELETE /api/model-policy/refusal?…` → `200` (те саме тіло).
  - `base_url` необов'язковий: типовий береться з `ProviderSettings(provider=…, model=…)`. Невідома роль або невалідні налаштування провайдера → `400` з повідомленням (наявний обробник `ValueError`).

- [ ] **Step 1: Write the failing tests**

```python
def test_consent_roundtrip(client):
    q = {'role': 'writer', 'provider': 'openrouter', 'model': 'x/y'}
    assert client.get('/api/model-policy', params=q).json() == {'consent': None, 'refusals': []}
    assert client.put('/api/model-policy/consent', json=q).json()['consent']['consented_at']
    assert client.delete('/api/model-policy/consent', params=q).json()['consent'] is None

def test_refusal_is_listed_and_cleared(client): ...
def test_unknown_role_is_rejected(client):
    assert client.get('/api/model-policy', params={'role': 'evaluator', 'provider': 'venice', 'model': 'm'}).status_code == 400
def test_response_carries_no_secret_or_text(client): ...  # серіалізована відповідь не містить key_env-значень і тексту сцени
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/web/test_model_policy_api.py -q`
Expected: FAIL (404).

- [ ] **Step 3: Implement** — маршрути з блоку Interfaces.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/web/test_model_policy_api.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/storygen/web/routes_model_policy.py src/storygen/web/app.py tests/web/test_model_policy_api.py
git commit -m "feat(web): model policy API for consent and refusal marks"
```

### Task 5: Інтерфейс згоди й позначки відмови

**Files:**
- Create: `src/storygen/web/static/model-policy.js`
- Modify: `src/storygen/web/static/model-picker.js` (прибрати `venice_uncensored_pending`; додати `selected()` у повернений об'єкт)
- Modify: `src/storygen/web/static/settings.js` (форми ролей), `src/storygen/web/static/classification-settings.js` (роль `editor`)
- Modify: `src/storygen/web/static/i18n.json` (uk, en), `src/storygen/web/static/app.css`
- Test: `tests/web/js/model_policy.mjs` + обгортка в `tests/web/test_model_policy_ui.py`; оновити `tests/web/js/model_picker.mjs`; `tests/web/browser/model-policy.spec.mjs`

**Interfaces:**
- Consumes: API задачі 4; `mountModelPicker(...)` з PR 1, тепер з `selected() -> ModelOption | null`.
- Produces:
  - `consentVisible(option, provider) -> boolean` — `provider !== 'local' && option?.uncensored !== true` (модель поза каталогом → показувати).
  - `mountModelPolicy({host, role, modelInput, providerInput, baseUrlInput, picker}) -> {refresh(): Promise<void>}` — на `change` поля моделі чи провайдера робить `GET` для нової пари й перемальовує блок.

Тексти (ключі i18n, uk / en):
- `policy.consent_label` — «Я погоджуюся, що ця модель отримуватиме запити для творів із рейтингом вище 0, і відповідаю за наслідки.» / «I agree that this model will receive requests for works rated above 0, and I take responsibility for the consequences.»
- `policy.consent_hint` — «Модель без позначки Uncensored може відмовити або пом’якшити відвертий зміст. Згода діє для цієї ролі й моделі в усіх творах.» / «A model without the Uncensored mark may refuse or soften explicit content. Consent applies to this role and model in all works.»
- `policy.refused` — «Модель відмовила через зміст на запиті з рейтингом {rating}. Виклики з таким самим або вищим рейтингом заблоковано.» / «The model refused on content for a request rated {rating}. Calls with the same or a higher rating are blocked.»
- `policy.clear_refusal` — «Зняти позначку» / «Clear the mark»; `policy.choose_other` — «Вибрати іншу модель» / «Choose another model» (відкриває панель списку).
- Прибрати `models.blocked_venice_uncensored_pending` з обох мов і з тесту перекладів.

- [ ] **Step 1: Write the failing tests**

```js
// tests/web/js/model_policy.mjs
assert.equal(consentVisible({uncensored:true},'venice'),false);
assert.equal(consentVisible({uncensored:false},'venice'),true);
assert.equal(consentVisible(null,'openrouter'),true);
assert.equal(consentVisible({uncensored:null},'local'),false);
// model_picker.mjs: Venice model without Uncensored is now selectable
assert.deepEqual(selectable(tee,{provider:'venice',responseMode:'prompt_json'}),{ok:true,reason:null});
```

Playwright (`model-policy.spec.mjs`, фікстурний сервер `tests/web/browser/server.py`): вибір моделі OpenRouter показує галочку; клік робить `PUT` і після перезавантаження галочка стоїть; вибір іншої моделі — галочка знята (Review Focus 4); записана відмова показує червоний блок, «Зняти позначку» прибирає його.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/web/test_model_policy_ui.py tests/web/test_model_picker.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement** — блок під рядком вибраної моделі за затвердженим прототипом: попередження з галочкою; червоне повідомлення з двома кнопками. Помилка API показується в блоці, галочка повертається до попереднього стану.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/web -q` і `node frontend/node_modules/@playwright/test/cli.js test tests/web/browser/model-policy.spec.mjs tests/web/browser/model-picker.spec.mjs --config frontend/playwright.config.mjs` (з `PYTHONPATH=<worktree>/src`)
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/storygen/web/static tests/web
git commit -m "feat(web): consent checkbox and refusal mark under the selected model"
```

### Task 6: Документація, traceability, перевірка

**Files:**
- Modify: `SPEC.MD` — MODEL-003 (нове формулювання «каталожна перевірка + згода», Scenario S01…S05), нова Requirement MODEL-004 (S01…S03) з якорями й записом у змісті, MODEL-005-S01 (прибрати «вибрати її до оновлення правил виклику не можна»), технічний опис `providers/policy.py` і ключів `app_settings`, відомі обмеження (текстові відмови не розпізнаються; readiness не перевіряє згоду для Venice; оцінювач вимагає uncensored).
- Modify: `docs/verification/traceability.json` — S01…S05, MODEL-004-S01…S03 з тестами задач 1–5; Playwright-спека — через ручну процедуру в `docs/verification/manual.md` (як `#model-picker-browser`).
- Modify: `docs/site/uk/models.md`, `docs/site/en/models.md`, `docs/site/uk/content-rating.md`, `docs/site/en/content-rating.md`; `python scripts/check_site.py --rehash models` і `--rehash content-rating`.
- Modify: специфікація зміни — розділ «Поправки»: поправка про локальний провайдер (див. «Рішення плану») і про readiness без каталогу.
- Modify: `docs/superpowers/plans/2026-10-20-remediation-progress.md` (запис PR 2), `docs/STATUS.md` через `python scripts/verify.py`.

- [ ] **Step 1:** Оновити SPEC.MD, traceability, manual, сторінки сайту, поправку.
- [ ] **Step 2:** Run: `python scripts/check_docs.py` — Expected: «Структура SPEC, матриця, тести, markers і локальні посилання узгоджені».
- [ ] **Step 3:** Commit `docs: MODEL-003 consent, MODEL-004 refusal block, site pages`.
- [ ] **Step 4:** Run: `python scripts/verify.py` (з короткого шляху, напр. `C:/tmp/<name>`, якщо довгий шлях падає) — Expected: `failed: 0`; записати в журнал і закомітити `docs/STATUS.md`.
