# MCP, пакет 3: режим «пише чат» повністю — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** чат отримує завдання етапів `brief`, `edit`, `memory` і інструкції чернетки такими, як їх бачить модель Obscura, а його відповідь розбирається й зберігається тим самим `execute_stage`.

**Architecture:** новий модуль `application/chat_stages.py` будує контекст через `build_context` з налаштуваннями ролі (або типовими для чату), віддає `system_text`/`user_text` частинами й зберігає відповідь через `execute_stage` зі шлюзом `ExternalTextGateway`; перед записом порівнює відбиток заново побудованого контексту. Системний текст етапу виноситься з `make_context` у `stage_system_text`, яку також викликає `writing-context`. Міст додає два інструменти.

**Tech Stack:** Python 3.12, FastAPI, httpx, `mcp==2.3.0`, pytest.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-12-mcp-p3-chat-writes-design.md` (затверджено 2026-11-12; ліміту спроб на сервері немає).

## Global Constraints

- Жодного виклику провайдера: `ExternalTextGateway` не має `bind_accounting`; `api_request` контексту не пишеться в спостереження токенів.
- Етап → роль: `brief` → `planner`, `edit` → `editor`, `memory` → `memory` (`generation.pipeline.STAGE_ROLES`). Ненастроєна роль → `RoleSettings(provider=ProviderSettings(model='external-chat'), context_tokens=131072, max_output_tokens=8192)`; для `memory` ще `memory_mode='evidence_delta'`.
- `task_fingerprint` = `ContextBundle.fingerprint`; розбіжність → 409 «Завдання застаріло — візьміть його знову (get_stage_task)» до будь-якого запису.
- `external_origin {client, model?}` обов'язковий у `chat-result` (модель `ExternalOrigin` з `routes_versions`).
- Частина матеріалу: `offset ≥ 0`, `1000 ≤ max_chars ≤ 50000` (як `GET …/text/{material}`), `content_sha256` — SHA-256 усього `user_text`.
- `MemoryApprovalRequired` → 409 з текстом «Попередня пам’ять потребує вашого підтвердження в Obscura: відкрийте сцену й підтвердьте використання пам’яті».
- Спроба `alternative` після `execute_stage` → 409 «Сцену змінено під час запису; версія збережена в історії непоточною».
- Тексти помилок українською, як решта моста; сайт `mcp` uk/en.
- Нейтральні тексти в тестах; жодних матеріалів із `data/`.

## Review Focus

1. Власний промпт письменника, несумісний за контрактом: `writing-context` не повинен ламати `get_scene_context` — `instructions` тоді `null` і `instructions_error` з текстом (тест у задачі 1).
2. Редактура в режимі `patches` з `edit_review='review'`: результат іде в «Правки редактора», проза не змінюється, відповідь 200 `needs_review` (тест у задачі 2).
3. Обгортка ```json для `brief` і `memory`: знімається з попередженням, як для моделі (тест у задачі 2).
4. Повторний `save_stage_result` з тим самим відбитком після успішного запису: контекст змінився (нова голова) → 409, другої версії немає (тест у задачі 2).
5. Сцена без прози для `memory` / без чернетки для `edit`: `get_stage_task` → 400 з текстом попереднього етапу, без падіння (тест у задачі 2).

---

### Task 1: `stage_system_text` і `instructions` чернетки

**Files:**
- Modify: `src/storygen/generation/context.py` (`make_context`: системна частина)
- Modify: `src/storygen/application/writing_context.py` (`_content`, `writing_context`)
- Create: `src/storygen/application/chat_stages.py` (лише `chat_role_settings` у цій задачі)
- Test: `tests/application/test_chat_stages.py`

**Interfaces:**
- Produces: `stage_system_text(view, story, scene, stage: str, settings: RoleSettings, fragments: dict, refs: list[str]) -> str` у `generation/context.py` — рівно та логіка, що зараз між `prompt_id=` і `rating_text` у `make_context` (власний промпт або `role_prompt`, контракт `introduced` для brief, `output_content_format` і збереження Markdown, мовна вказівка, інструкції рейтингу); мутує `fragments` і `refs`, як зараз.
- Produces: `chat_role_settings(repo, story_id: str, stage: str) -> RoleSettings` у `application/chat_stages.py`.
- Produces: `writing-context` → нові поля `instructions: str | None`, `instructions_error: str | None`, обидва в `content` (входять у `context_fingerprint`).

- [ ] **Step 1: Write the failing tests**

```python
def test_make_context_system_text_is_stage_system_text(tmp_path): # для draft, brief, edit(prose)
    ctx = build_context(repo, scene.id, stage, role)
    assert ctx.system_text == stage_system_text(view, story, scene, stage, role, fragments, [])

def test_writing_context_has_draft_instructions(tmp_path):         # MCP-BRIDGE-S46
    data = writing_context(repo, scene.id)
    assert data['instructions'] == build-of-draft-system-text and data['instructions_error'] is None

def test_writer_prompt_change_changes_context_fingerprint(tmp_path):  # S46
    before = writing_context(...)['context_fingerprint']; <зберегти власний промпт письменника>
    assert writing_context(...)['context_fingerprint'] != before

def test_incompatible_writer_prompt_does_not_break_writing_context(tmp_path):  # Review Focus 1
    assert data['instructions'] is None and 'Несумісний' in data['instructions_error']

def test_chat_role_settings_defaults_and_configured(tmp_path):
    assert chat_role_settings(repo, story.id, 'edit').context_tokens == 131072  # ненастроєна
    assert chat_role_settings(repo, story.id, 'memory').memory_mode == 'evidence_delta'
    <налаштувати editor з edit_mode='patches'> → chat_role_settings(..., 'edit').edit_mode == 'patches'
```

- [ ] **Step 2:** `pytest tests/application/test_chat_stages.py -q` → FAIL (`ImportError`).
- [ ] **Step 3:** Винести `stage_system_text` (make_context викликає її, поведінка побайтово та сама); `writing_context._content` додає `instructions` для `draft` з `chat_role_settings(…, 'draft')` (роль `writer`) у `try/except ValueError` → `instructions_error`; написати `chat_role_settings`.
- [ ] **Step 4:** `pytest tests/application/test_chat_stages.py tests/generation tests/mcp -q` → PASS (наявні тести контексту — без змін).
- [ ] **Step 5: Commit** `feat(mcp): stage system text shared with writing context`

### Task 2: маршрути завдання й результату

**Files:**
- Modify: `src/storygen/application/chat_stages.py` (`ExternalTextGateway`, `stage_task`, `stage_result`)
- Modify: `src/storygen/generation/stages.py` (`execute_stage(..., external_origin=None)`)
- Modify: `src/storygen/web/routes_versions.py` (два маршрути)
- Test: `tests/application/test_chat_stages.py`, `tests/web/test_chat_stage_routes.py`

**Interfaces:**
- Consumes: `chat_role_settings` (задача 1).
- Produces: `GET /api/scenes/{id}/chat-task/{stage}` → `{scene_id, stage, revision, task_fingerprint, instructions, material, offset, next_offset, total_chars, content_sha256, result_format, warnings}`; `POST /api/scenes/{id}/chat-result/{stage}` з тілом `ChatStageResult{task_fingerprint: str (^[0-9a-f]{64}$), text: str (min_length=1), external_origin: ExternalOrigin}` → 200 `{state: 'completed'|'needs_review', version_id, revision, message?, warnings}`; 422 `{detail, violations?}`; 409.
- Produces: `execute_stage(..., external_origin: ExternalOrigin | None = None)`: передає в `save_version` і `attempt.context['external_origin']`.
- `result_format`: `brief`/`memory` → `json`; `edit` → `settings.edit_mode`.

- [ ] **Step 1: Write the failing tests** (нейтральний твір, рейтинг 0/0/0; відповіді пам'яті — з проби П1, `C:\tmp\p3probe\two\a1.json`, вбудовані в тест як рядок):

```python
def test_memory_task_matches_pipeline_context(...)          # S40: instructions == ctx.system_text, '\n'.join(parts) == ctx.user_text, sha
def test_memory_result_becomes_head_with_origin(...)        # S41: state completed, heads['memory'] == version_id, external_origin.client == 'claude-ai'
def test_memory_result_with_violations_saves_nothing(...)   # S41: 422, violations має 'core.marta.body', голова memory без змін, версій memory не додалось
def test_fenced_json_is_unwrapped_with_warning(...)         # S41, RF3
def test_brief_without_proposed_changes_becomes_head(...)   # S42
def test_brief_with_proposed_changes_needs_review(...)      # S42: needs_review, голова brief без змін
def test_edit_prose_mode_saves_edited_version(...)          # S43: kind == 'edited', heads['prose']
def test_edit_patches_review_goes_to_editor_proposals(...)  # S43, RF2: GET /copyedits містить спробу, проза без змін
def test_stale_task_is_rejected(...)                        # S44: зміна плану сцени або налаштувань editor після task → 409, версій немає
def test_same_fingerprint_twice_is_rejected(...)            # S44, RF4
def test_memory_reuse_approval_is_required(...)             # S45: змінена проза попередньої сцени → task 409 з текстом підтвердження
def test_missing_previous_stage_is_400(...)                 # RF5
def test_no_provider_call_and_no_token_observation(...)     # провайдер-шлюз не створюється; repo.list_token_observations() порожній
```

- [ ] **Step 2:** `pytest tests/application/test_chat_stages.py tests/web/test_chat_stage_routes.py -q` → FAIL.
- [ ] **Step 3:** Реалізувати: `ExternalTextGateway(text).stream(context, cancel)` → `GenerationEvent(type='delta', text=text)`, `GenerationEvent(type='terminal', finish_reason='stop')`; `stage_task` — `build_context` + нарізка; `stage_result` — `build_context`, порівняння відбитка, `context.model_copy(update={'api_request': {}})`, `execute_stage(repo, scene_id, stage, ctx, gateway, threading.Event(), lambda _: None, external_origin=origin)`, розбір стану спроби у відповідь (`failed` → 422 з `attempt.error`, `memory_violations`, `editor_failure`). Маршрути ловлять `MemoryApprovalRequired` → 409.
- [ ] **Step 4:** ті самі тести + `pytest tests/generation -q` → PASS.
- [ ] **Step 5: Commit** `feat(mcp): chat stage task and result routes`

### Task 3: інструменти моста

**Files:**
- Modify: `src/storygen/mcp/bridge.py` (`get_stage_task`, `save_stage_result`, `INSTRUCTIONS`, `next_steps`, `STAGES = ('brief', 'edit', 'memory')`)
- Test: `tests/mcp/test_bridge_chat_stages.py`, `tests/mcp/test_bridge.py` (S06 → 23)

**Interfaces:**
- Consumes: маршрути задачі 2.
- Produces: `get_stage_task(scene_id: str, stage: str, offset: int = 0, max_chars: int = 20000) -> dict`; `save_stage_result(scene_id: str, stage: str, task_fingerprint: str, result: str | dict, model: str | None = None, ctx) -> dict`.

- [ ] **Step 1: Write the failing tests** (через справжній застосунок, `obscura(tmp_path)`):

```python
def test_tool_list_is_exactly_the_twenty_three_tools(...)   # S06 (перейменувати чинний)
def test_unknown_stage_is_refused_without_request(...)      # spy_writes порожній, ToolError
def test_memory_round_trip_through_bridge(...)              # S41: result як dict → completed; external_origin.client з ctx
def test_violations_reach_the_chat(...)                     # текст помилки містить шлях порушення
def test_scene_context_carries_instructions(...)            # S46
def test_next_steps_suggests_memory_after_prose(...)
```

- [ ] **Step 2:** `pytest tests/mcp -q` → FAIL.
- [ ] **Step 3:** Реалізувати; опис `save_stage_result` каже: грошей не коштує; після трьох відмов поспіль зупиніться й покажіть порушення авторові. 422 з `violations` → `ToolError` з текстом і переліком.
- [ ] **Step 4:** `pytest tests/mcp -q` → PASS.
- [ ] **Step 5: Commit** `feat(mcp): get_stage_task and save_stage_result tools`

### Task 4: контракт і документація

**Files:**
- Modify: `SPEC.MD` (MCP-BRIDGE: 23 інструменти, абзац про етапи з чату, `writing-context.instructions`, S06, сценарії S40–S46, обмеження; DATA-007/MEMORY — посилання на походження)
- Modify: `docs/verification/traceability.json` (S40–S46 після S39)
- Modify: `docs/site/uk/mcp.md`, `docs/site/en/mcp.md` (+ `check_site.py --rehash mcp`)

- [ ] **Step 1:** Оновити тексти за специфікацією (розділ «Контракт і документація»).
- [ ] **Step 2:** `PYTHONIOENCODING=utf-8 python scripts/check_docs.py` → «узгоджені».
- [ ] **Step 3: Commit** `docs(mcp): package 3 contract and site pages`
