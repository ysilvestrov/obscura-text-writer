# MCP, пакет 1: читання текстів сцени — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** чат читає план, завдання, чернетку, прозу й пам'ять сцени з ідентифікатором поточної версії, а `save_draft` пише лише поверх прочитаної чернетки (#108).

**Architecture:** новий маршрут `GET /api/scenes/{id}/text/{material}` у `application/writing_context.py` (один знімок, межа рейтингу, частини, `content_sha256`); `DraftChange.expected_draft_version_id` перевіряється в `save_manual_draft` до `save_version`; `storygen-mcp` отримує сьомий інструмент і обов'язковий `draft_version_id`.

**Tech Stack:** Python 3.12, FastAPI, pydantic, `mcp==2.3.0`, httpx, pytest.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-11-mcp-p1-scene-texts-design.md`

Поділ (detent:pr-slicing): один PR; рефакторингу немає, зміна поведінки одна (обов'язкове поле для зовнішнього клієнта) — ядро й периферія не розділяються.

## Global Constraints

- `material ∈ {plan, brief, draft, prose, memory}`; `max_chars` 1000…50000, типово 20000; `offset ≥ 0` і `≤ total_chars`, інакше 400.
- Відповідь читання: `scene_id, story_id, material, revision, version_id, kind, content_format, stale, external_origin, text, offset, total_chars, next_offset, content_sha256`; без `relative_path`, знімків і промптів.
- `content_sha256` — SHA-256 усього тексту матеріалу (UTF-8), однаковий для всіх частин одного стану.
- Межа видання — `enforce_rating_limit(effective_rating(story, scene))` для всіх матеріалів.
- Текст 409: «Чернетку змінено після того, як її прочитали — прочитайте її знову (get_scene_text)»; текст 400 без поля: «Чернетка із зовнішнього клієнта потребує ідентифікатора прочитаної чернетки».
- Порядок перевірок запису: межа видання → ревізія → `expected_draft_version_id` → відбиток.
- Нові сценарії: `MCP-BRIDGE-S12`…`S16`; S06 — сім інструментів.
- Документація українською; сайт `mcp` uk/en парою з `check_site.py --rehash mcp`.

## Review Focus

1. Сцена без чернетки: `get_scene_text(material='draft')` → `version_id=null`, і `save_draft(draft_version_id=None)` приймається — тест у задачі 2 і 3.
2. Пам'ять, змінена вибором «передавати далі» між частинами: `content_sha256` змінюється при тій самій `version_id` — тест у задачі 1.
3. Кирилиця й символи поза BMP: зріз за символами Python, не байтами; склеєні частини дорівнюють цілому — тест у задачі 1.
4. Запис інтерфейсу (без `external_origin`) з `expected_draft_version_id` → 400; без поля — як раніше — тест у задачі 2.
5. `material` поза переліком у клієнті відхиляється без HTTP-запиту — тест у задачі 3.

---

### Task 1: Маршрут читання тексту сцени

**Files:**
- Modify: `src/storygen/application/writing_context.py`
- Modify: `src/storygen/web/routes_versions.py` (маршрут поруч із `writing-context`)
- Test: `tests/web/test_scene_text.py` (новий)

**Interfaces:**
- Produces: `scene_text(repo, scene_id: str, material: str, offset: int = 0, max_chars: int = 20000) -> dict` з полями Global Constraints; маршрут `GET /api/scenes/{scene_id}/text/{material}` з query `offset`, `max_chars` (FastAPI `Query(ge=..., le=...)`; `material` — `Literal`).

- [ ] **Step 1: Тести** (`@pytest.mark.req('MCP-BRIDGE')`):
  - `test_each_material_returns_text_and_current_version` — сцена з планом (через `PATCH /api/scenes/{id}` beats), завданням (валідний `WritersBrief` JSON через `repo.save_version`+`set_head`), чернеткою, прозою, пам'яттю (`save_scene_memory` з мінімальним журналом, як у наявних тестах пам'яті); для кожного `version_id == scene.heads[material]`, `text` збігається з `read_text` (для `memory` — `json.loads(text)` є списком із `claim_id`); `revision == scene.revision`.
  - `test_missing_material_is_empty_not_404` — сцена без чернетки: `version_id is None`, `text == ''`, `total_chars == 0`, `next_offset is None`.
  - `test_plan_without_head_falls_back_to_beats` — сцена, створена з `beats`, без голови `plan`: `text == beats`, `version_id is None`.
  - `test_long_text_comes_in_parts_with_one_hash` — чернетка 2500 символів із кирилицею й емодзі, `max_chars=1000`: три частини, `''.join == full`, `next_offset` 1000/2000/None, `content_sha256` однаковий і дорівнює `sha256(full.encode()).hexdigest()`.
  - `test_memory_hash_changes_with_forwarding_choice` — після `PUT /api/scenes/{id}/memory-view` зі зміною вибору `version_id` той самий, `content_sha256` інший.
  - `test_bad_offset_or_size_is_400` — `offset=total+1`, `max_chars=999`, `max_chars=50001` → 400 (422 від FastAPI теж приймається, якщо так відповідає наявна обробка: зафіксувати фактичний код у тесті).
  - `test_store_edition_blocks_text_above_limit` — фікстура `store_edition` з `tests/web/test_writing_context.py`; рейтинг твору понад межу → помилка з текстом межі для `draft` і `memory`.
  - `test_response_has_no_paths_or_snapshots` — у JSON немає `relative_path`, `dependency_snapshot`, `prompt_contract`.
- [ ] **Step 2:** `pytest tests/web/test_scene_text.py` — FAIL (404 маршруту).
- [ ] **Step 3:** реалізувати `scene_text`: один `repo.context_view(story_id)`; `memory` — `rows` з `memory_view_from_view(view, scene_id)`, лише поля `claim_id, category, text, source_scene, source_title, quote, supporting_quotes, forward, closed`, `json.dumps(..., ensure_ascii=False, sort_keys=True)`; інакше `view.read_text(head)`; межа рейтингу до формування; хеш від повного тексту, зріз `text[offset:offset+max_chars]`.
- [ ] **Step 4:** тести PASS; `pytest tests/web/test_writing_context.py` PASS.
- [ ] **Step 5:** commit `feat(mcp): read any scene material with its current version (#108)`.

### Task 2: Запис чернетки поверх прочитаної

**Files:**
- Modify: `src/storygen/web/routes_versions.py` (`DraftChange`, `manual_draft`)
- Modify: `src/storygen/generation/dependencies.py` (`save_manual_draft`)
- Modify: `tests/web/test_external_draft.py` (хелпер `save` передає `expected_draft_version_id`)
- Test: `tests/web/test_external_draft.py`

**Interfaces:**
- Produces: тіло `POST /api/scenes/{id}/draft` приймає `expected_draft_version_id: str | None`; `save_manual_draft(..., expected_draft_version_id=MISSING)` (сентинел, щоб відрізнити явний `None`).

- [ ] **Step 1: Тести:** хелпер `save(..., draft_id=<поточна голова>)` — наявні тести лишаються зеленими; нові:
  - `test_external_draft_over_stale_draft_is_409` — прочитано голову A, автор зберіг B (`POST /draft` без origin); запис зі свіжими ревізією й відбитком, але `expected_draft_version_id=A` → 409 з текстом Global Constraints; голова B, кількість версій чернетки не змінилася.
  - `test_external_draft_without_draft_id_is_400` → 400 з текстом Global Constraints.
  - `test_external_draft_with_null_on_scene_without_draft` → 200.
  - `test_author_draft_with_draft_id_is_400` — без `external_origin`, з полем → 400; без поля → 200.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** у `DraftChange` поле + валідатор (поле без `external_origin` → помилка); маршрут передає значення лише якщо поле в `model_fields_set`; у `save_manual_draft` перевірка після ревізії й до відбитка, до `save_version`.
- [ ] **Step 4:** `pytest tests/web/test_external_draft.py tests/mcp` — PASS для web; тести MCP впадуть (save_draft без поля) — це задача 3.
- [ ] **Step 5:** commit `feat(mcp): external draft must name the draft it was written over (#108)`.

### Task 3: Клієнт `storygen-mcp`

**Files:**
- Modify: `src/storygen/mcp/bridge.py`
- Test: `tests/mcp/test_bridge.py`

**Interfaces:**
- Consumes: маршрут задачі 1, поле задачі 2.
- Produces: `TOOLS` із сімома назвами (додано `get_scene_text`); `get_scene_text(scene_id, material, offset=0, max_chars=20000)`; `save_draft(scene_id, text, expected_revision, context_fingerprint, draft_version_id: str | None, content_format='markdown', model=None)` — `draft_version_id` без типового значення.

- [ ] **Step 1: Тести:** `test_tool_list_is_exactly_the_seven_tools`; наявний тест `save_draft` бере `draft_version_id` з `get_scene_text`; нові:
  - `test_get_scene_text_reads_the_current_draft` — `version_id` дорівнює голові, текст збігається.
  - `test_save_draft_over_stale_draft_reaches_the_chat_as_409` — сценарій #108: читання A, автор зберігає B, `save_draft` з A → `is_error`, `'409'` у тексті, голова B.
  - `test_save_draft_requires_draft_version_id` — виклик без поля → `is_error` (помилка схеми), запиту до сервера немає.
  - `test_material_outside_the_list_is_refused_without_request` і `get_scene_text` у параметризації `test_identifiers_cannot_reach_other_endpoints`.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** реалізувати; `MATERIALS = ('plan','brief','draft','prose','memory')`; непорожній `draft_version_id` — через `identifier()`; описи: читання «нічого не змінює й не коштує грошей; порівнюйте content_sha256 частин»; `INSTRUCTIONS` і `next_steps` — порядок `get_scene_context` → `get_scene_text(material='draft')` → `save_draft` з `draft_version_id`.
- [ ] **Step 4:** `pytest tests/mcp tests/web` PASS.
- [ ] **Step 5:** commit `feat(mcp): get_scene_text tool and draft_version_id in save_draft (#108)`.

### Task 4: Контракт, сайт, приймання

**Files:**
- Modify: `SPEC.MD` (MCP-BRIDGE), `docs/verification/traceability.json`, `docs/verification/manual.md`, `docs/site/uk/mcp.md`, `docs/site/en/mcp.md`, `docs/site/site.json` (через `--rehash`)
- Позначки `@pytest.mark.req` уже стоять у тестах задач 1–3.

- [ ] **Step 1:** MCP-BRIDGE: сім інструментів, маршрут читання, поле запису, порядок перевірок, межа видання для читання; S06 (сім), S07 (читання чернетки в прийманні); нові S12–S16 за специфікацією; відомі обмеження (незбережене в редакторі, частини, без історії); усунене відхилення #108; рядок «Obscura … промптів клієнту не віддає» лишається.
- [ ] **Step 2:** traceability: S12–S16 → тести задач 1–3; S07 — ручна процедура.
- [ ] **Step 3:** `manual.md`: процедура приймання пакета 1 (нейтральна сцена, довга нейтральна сцена для частин, сценарій #108).
- [ ] **Step 4:** сайт uk/en; `python scripts/check_site.py --rehash mcp`; `python scripts/check_docs.py` — без помилок.
- [ ] **Step 5:** commit `docs(mcp): scene texts in MCP-BRIDGE, site and acceptance procedure`.
