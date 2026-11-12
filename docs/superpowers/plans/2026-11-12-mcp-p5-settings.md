# MCP, пакет 5: налаштування письма й моделей з чату — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** чат читає налаштування твору (профіль письма, чотири ролі, стан ключів, пресети, список моделей), частково змінює один розділ поверх прочитаного й застосовує пресет ролей; відкрита сторінка налаштувань помічає зміни ззовні.

**Architecture:** змін сервера немає. Клієнт `storygen-mcp` додає три інструменти: відбитки розділів рахує сам із `GET /api/stories/{id}/settings` і `GET /api/stories/{id}/evaluator`, зливає поля й надсилає наявні `PUT`/`preview`/`apply` зі свіжою `story.revision`. Рішення сторінки про оновлення — чиста функція в `static/settings-sync.js` з node-тестом.

**Tech Stack:** Python 3.12, FastAPI, httpx, `mcp==2.3.0`, ES modules, pytest, node.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-12-mcp-p5-settings-design.md` (затверджено 2026-11-12: промпти лише читаються; список моделей — так; нового механізму історії немає).

## Global Constraints

- Нічого платного: жоден інструмент не викликає модель; `POST /api/providers/discover` — лише список моделей.
- `key_env` від чату не надсилається ніколи: `fields.key_env` → помилка без запиту; при зміні `provider` клієнт прибирає `key_env` і `base_url` (крім `base_url`, переданого чатом для `local`).
- Пресет із назвою ключа поза {назви ключів поточних ролей твору, `OPENROUTER_API_KEY`, `VENICE_API_KEY`} → `confirm` відхиляється без `apply`.
- Відбиток розділу — SHA-256 `json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)`: `writing` = `{profile, target_words}`; роль = `{settings, prompt, prepare (лише planner), contract}` (як `roleScope` у `settings.js`); `preset_fingerprint` = чотири ролі + налаштування оцінювача без `block`.
- Відповіді не містять значень ключів і змінних середовища.
- Тексти сторінки — `i18n.json` uk/en, лише `textContent`.

## Review Focus

1. Зміна провайдера `local → openrouter` і назад: адреса й ключ — стандартні, запис проходить серверну перевірку endpoint.
2. `update_settings` для ролі, якої ще немає, без `provider`/`model` → відмова без запиту; з ними — роль створена з типовими значеннями решти полів.
3. Нова сцена між `get_settings` і `update_settings` не блокує запис (відбиток розділу не змінився).
4. Сторінка: власне збереження не вважається зміною ззовні; брудна форма не перезавантажується.
5. `models_for_role` для ролі без ключа хмарного провайдера → помилка інструмента з текстом сервера, без значення ключа.

---

### Task 1: Сторінка налаштувань помічає зміни ззовні

**Files:** Create `src/storygen/web/static/settings-sync.js`; Modify `src/storygen/web/static/settings.js` (або `settings-workspace.js`, де живе стан сторінки), `src/storygen/web/static/i18n.json`; Test `tests/web/js/settings_sync.mjs`, обгортка `tests/web/test_settings_sync.py`.

**Produces:** `settingsContentKey(settings, evaluator) -> string` (ролі, профіль, промпти, промпт підготовки, контракти, `target_words`, `language`, `content_rating`, оцінювач без `block`; без `revision`/`config_revision`); `externalSettingsChange({loadedKey, freshKey, unsaved, busy}) -> {reload, warn}`.

- [ ] Тести node: однаковий вміст → нічого; різні `revision` при однаковому вмісті → нічого (нова сцена); інший рейтинг чи мова → `reload` при чистій сторінці; `unsaved` чи `busy` → `warn`; порядок ключів не важить.
- [ ] RED; реалізація; у сторінці обробник `visibilitychange`/`focus` (≥ 2 с, без паралельних): читає налаштування й оцінювача, `reload` → `location.reload()`, `warn` → повідомлення `settings.changed_elsewhere`; після власного збереження (`settingsSaved`) завантажений ключ оновлюється.
- [ ] GREEN `pytest tests/web -q`; commit `feat(settings): the page notices outside changes`.

### Task 2: Клієнт — три інструменти налаштувань

**Files:** Modify `src/storygen/mcp/bridge.py`; Test `tests/mcp/test_bridge_settings.py`, `tests/mcp/test_bridge.py` (21 інструмент, перейменувати тест і рядок traceability).

**Interfaces:** `get_settings(story_id, include_prompts=False, models_for_role=None, models_query=None)`, `update_settings(story_id, section, expected_fingerprint, fields)`, `apply_role_preset(story_id, profile_id, version, expected_fingerprint, confirm=False)`.

- [ ] Тести через справжній застосунок (S32–S36, S38): `get_settings` нового твору — `configured: false` для всіх ролей, відбитки, `key.source is None`, пресетів немає, промптів без `include_prompts` немає; `update_settings('writer', …, {provider:'local', model:'m'})` створює роль; повторне з `{temperature: 0.9}` лишає модель; нова сцена між читанням і записом не заважає; зміна розділу після читання → помилка без `PUT` (шпигун `http.request`); `key_env`, `prompt_version_id`, `classification`, невідоме поле, порожній `fields` → без запиту; `local → openrouter` → `key_env == 'OPENROUTER_API_KEY'`, `base_url` офіційний; пресет: зберегти через `POST …/role-profiles/capture`, змінити роль, `apply_role_preset` без `confirm` нічого не змінює, з `confirm` повертає роль; пресет із `key_env='HOME_SECRET_X'` (записаний напряму в роль перед capture) → відмова без `apply`; зміна оцінювача після читання → відмова; `models_for_role` — `discover_models` підмінено (`monkeypatch`) на 250 моделей: межа 200, `models_total`, фільтр `models_query`; роль поза переліком — без запиту.
- [ ] RED; реалізація за таблицею специфікації; GREEN `pytest tests/mcp -q`; commit `feat(mcp): settings tools`.

### Task 3: Контракт і документація

- [ ] SPEC: MCP-BRIDGE (21 інструмент, S06, S32–S38, зняті заборони, обмеження), R21-SETTINGS (оновлення сторінки ззовні, S37 у MCP-BRIDGE), SECURITY-002 (правило про `key_env` моста); traceability; сайт `mcp` і `models` uk/en, `check_site.py --rehash`; `check_docs.py`; commit.
