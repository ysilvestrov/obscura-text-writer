# Скіли в пакеті й провідник у MCP (PR 1) — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Скіли Obscura дістаються до Claude Code (плагін зі сталої копії), Claude Desktop (ZIP-и) та інших клієнтів (`get_guide`) з одного джерела `integrations/claude/obscura/`.

**Architecture:** Чистий модуль `skill_bundles.py` читає плагін і будує ZIP-и та тексти провідника. `claude_connect.py` отримує сталу копію маркетплейсу і встановлення плагіна через фіксовані argv `claude`. Міст MCP читає плагін із диска поруч зі своїм exe або з робочої копії. Пакет Store (PR 2) лише кладе ту саму теку поруч з `Obscura.exe`.

**Tech Stack:** Python 3.12, FastAPI, MCP Python SDK (`MCPServer`), pytest, Playwright (браузерні тести), vanilla JS.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-17-store-release-design.md`, розділи 1–5, 8 (`mcp`), 9, 11.

## Global Constraints

- Процеси лише з фіксованими argv, без оболонки, з `cc.TIMEOUT` і `cc.NO_WINDOW`, через ін’єкцію `run`.
- Тести ніколи не торкаються справжніх `~/.claude`, `%APPDATA%\Claude` чи `%USERPROFILE%\Obscura`; лише `tmp_path`.
- Запит моста (`X-Obscura-Client: mcp`) до `/api/connect/*` → 403 (уже в `app.py`; новий маршрут мусить потрапити під ту саму перевірку).
- Файли для користувача — лише `.claude-plugin/` і `obscura/{.claude-plugin,shared,skills}/`; `tools/` і `evals/` не копіюються.
- Нові Scenario: `STORE-MCP-S14`…, `MCP-BRIDGE-S53`, `CLAUDE-SKILLS-S10`…; `STORE-MCP-S12/S13` зарезервовані за Codex.
- Тексти інтерфейсу uk/en в `static/i18n.json`; серверні відмови — українською, через `diagnostic()`.
- Скіли плагіна не згадують `get_guide`.

## Review Focus

1. Тека `claude\marketplace` існує, але без `obscura-version.txt` (автор створив свою) — нічого не змінюється, відмова з шляхом.
2. Збій посеред копіювання (диск повний, файл зайнятий) — стара копія лишається цілою; тимчасова тека прибирається.
3. `get_guide(task='../shared/rules')`, `reference='..\\x'` чи невідомі назви — відмова з переліком, без читання поза плагіном.
4. `claude plugin marketplace list --json` повертає не JSON / код ≠ 0 / `claude` зависає — `skills: false` і команди для копіювання, а не виняток.
5. Плагіна немає поруч (стара збірка, видалена тека) — `get_guide` і prompt `start_story` працюють із запасним текстом/відмовою, міст не падає на старті.

---

### Task 1: Генерація з плагіна (`skill_bundles.py`)

**Files:**
- Create: `src/storygen/skill_bundles.py`
- Test: `tests/test_skill_bundles.py`
- Modify: `tests/test_claude_plugin.py` (версія плагіна = версія проєкту; скіли не згадують `get_guide`)

**Interfaces:**
- Produces:
  - `USER_FILES: tuple[str, ...] = ('.claude-plugin/', 'obscura/.claude-plugin/', 'obscura/shared/', 'obscura/skills/')`
  - `user_files(source: Path) -> list[str]` — відносні POSIX-шляхи файлів маркетплейсу під `USER_FILES`, за абеткою.
  - `marketplace_source(*, frozen: bool, executable: Path, checkout: Path) -> Path | None` — `executable.parent/'claude'` або `checkout/'integrations'/'claude'`; `None`, якщо немає `.claude-plugin/marketplace.json`.
  - `plugin_root(source: Path | None) -> Path | None` — `source/'obscura'`, якщо є `.claude-plugin/plugin.json`.
  - `skill_names(plugin: Path) -> list[str]`
  - `class BundleError(ValueError)`
  - `bundle_files(plugin: Path, skill: str) -> dict[str, str]`
  - `desktop_zip(plugin: Path, skill: str) -> bytes`
  - `guide_text(plugin: Path, skill: str) -> str`; `guide_references(plugin, skill) -> list[str]`; `guide_reference(plugin: Path, skill: str, name: str) -> str`

- [ ] **Step 1: Failing tests** (`tests/test_skill_bundles.py`, усі `@pytest.mark.req('CLAUDE-SKILLS')`), на синтетичному плагіні в `tmp_path` і на справжньому `integrations/claude/obscura`:
  - `test_bundle_rewrites_plugin_root`: SKILL.md з `${CLAUDE_PLUGIN_ROOT}/shared/rules.md` і `${CLAUDE_PLUGIN_ROOT}/skills/a/references/x.md` → ключі `{'a/SKILL.md','a/references/x.md','a/references/rules.md'}`, у тексті `references/rules.md` і `references/x.md`, `'${CLAUDE_PLUGIN_ROOT}' not in` жоден текст.
  - `test_reference_to_another_skill_is_an_error`: `${CLAUDE_PLUGIN_ROOT}/skills/b/references/y.md` у скілі `a` → `BundleError`, повідомлення містить `a/SKILL.md`.
  - `test_unknown_skill_is_an_error`: `bundle_files(plugin, '../shared')` і `'nope'` → `BundleError`.
  - `test_desktop_zip_is_one_folder_named_after_skill`: усі імена в `ZipFile.namelist()` починаються з `a/`; два виклики дають однакові байти.
  - `test_every_real_skill_bundles`: для кожного з `skill_names(PLUGIN)` `bundle_files` без помилок; `skill_names` == `['draft-scene','publish','series-bible','setup-models','start-story']`.
  - `test_guide_points_to_get_guide`: `guide_text(PLUGIN,'draft-scene')` містить `get_guide(task="draft-scene", reference="chat-pipeline")` і `reference="rules"`, не містить `${CLAUDE_PLUGIN_ROOT}`; `guide_reference(PLUGIN,'draft-scene','rules')` == текст `shared/rules.md`; `guide_reference(..., '../SKILL')` → `BundleError`.
  - `test_user_files_skip_tools_and_evals`: `user_files(MARKET)` містить `obscura/skills/publish/SKILL.md`, не містить жодного шляху з `tools/` чи `evals/`.
  - `test_sources`: `marketplace_source(frozen=True, executable=tmp/'Obscura.exe', ...)` → `tmp/'claude'` лише коли там є `marketplace.json`; `frozen=False` → `checkout/'integrations/claude'`.
  - У `tests/test_claude_plugin.py`: `test_plugin_version_is_project_version` (`plugin.json['version'] == tomllib pyproject['project']['version']`); `test_skills_never_mention_get_guide`.
- [ ] **Step 2:** `python -m pytest tests/test_skill_bundles.py tests/test_claude_plugin.py -q` → FAIL (модуля немає).
- [ ] **Step 3:** Реалізувати. Заміна — один regex `\$\{CLAUDE_PLUGIN_ROOT\}/([^\s`)]+)`; дозволено лише `shared/rules.md` і `skills/<skill>/references/<name>.md`. Назви скіла й довідки перевіряти проти `skill_names`/`guide_references` (не з’єднувати шлях із вводу). ZIP: `ZipInfo` з фіксованою датою `(1980,1,1,0,0,0)`, `ZIP_DEFLATED`, UTF-8. У провіднику `references/x.md` → `` `get_guide(task="<skill>", reference="x")` ``.
- [ ] **Step 4:** Ті самі тести → PASS.
- [ ] **Step 5:** Commit `feat(skills): generate Desktop ZIPs and guide text from the plugin`.

### Task 2: Провідник у мосту

**Files:**
- Modify: `src/storygen/mcp/bridge.py` (`TOOLS`, `INSTRUCTIONS`, prompt `start_story`, новий tool, docstring «двадцять сім»)
- Modify: `tests/mcp/test_bridge.py:46` (перелік інструментів), `tests/mcp/test_bridge_prompt.py`
- Create: `tests/mcp/test_bridge_guide.py`

**Interfaces:**
- Consumes: Task 1 `marketplace_source`, `plugin_root`, `skill_names`, `guide_text`, `guide_references`, `guide_reference`, `BundleError`.
- Produces: `bridge.guide_plugin() -> Path | None` (через `marketplace_source(frozen=getattr(sys,'frozen',False), executable=Path(sys.executable), checkout=Path(__file__).resolve().parents[3])`); `build_server(..., plugin: Path | None | object = DEFAULT)` — тести передають `plugin=` явно.

- [ ] **Step 1: Failing tests** (`@pytest.mark.req('MCP-BRIDGE')` / `'STORE-MCP-001'`):
  - `test_get_guide_returns_skill_and_reference_names`: `call_tool('get_guide', {'task':'start-story'})` → `text` починається з frontmatter скіла, `references` містить `'rules'` і `'interview'`.
  - `test_get_guide_reference`: `{'task':'draft-scene','reference':'continuity'}` → текст `continuity.md`.
  - `test_get_guide_refuses_unknown`: `{'task':'../shared'}` і `{'task':'publish','reference':'..\\rules'}` → помилка інструмента з переліком допустимих.
  - `test_get_guide_without_plugin`: `build_server(..., plugin=None)` → помилка «Провідник недоступний у цій збірці».
  - `test_instructions_name_get_guide`: `'get_guide' in INSTRUCTIONS` і всі п’ять назв скілів у ньому.
  - У `test_bridge_prompt.py`: `test_start_story_prompt_keeps_the_idea_and_follows_the_skill` — текст містить `маяк на острові` і рядок із `guide_text(PLUGIN,'start-story')`; `test_start_story_without_plugin_uses_the_short_path` — `plugin=None` → старі кроки `create_story…next_steps` у порядку; тест «спитайте людину» лишається.
  - `test_bridge.py:46` — перелік із `'get_guide'`.
- [ ] **Step 2:** `python -m pytest tests/mcp -q` → FAIL у нових тестах.
- [ ] **Step 3:** Реалізувати: tool `get_guide(task: str, reference: str | None = None) -> dict`; prompt: `START_STORY_IDEA = 'Задум автора: {idea}\n\n'` + `guide_text`, без плагіна — старий `START_STORY`. До `INSTRUCTIONS` додати речення: «Якщо скіл Obscura (start-story, draft-scene, publish, series-bible, setup-models) у вас не підключено, спершу викличте get_guide з назвою задачі й дотримуйтеся отриманих кроків; якщо підключено — не викликайте». `--self-check` додатково викликає `guide_text(guide_plugin(), 'start-story')`, коли плагін є, і друкує `guide: ok|absent`.
- [ ] **Step 4:** `python -m pytest tests/mcp tests/test_claude_plugin.py -q` → PASS (S03 знає `get_guide` через `TOOLS`).
- [ ] **Step 5:** Commit `feat(mcp): get_guide serves Obscura skills to clients without them`.

### Task 3: Стала копія маркетплейсу і плагін у Claude Code

**Files:**
- Modify: `src/storygen/claude_connect.py`, `src/storygen/web/routes_connect.py`, `src/storygen/desktop.py` (`_run`: після `write_server_record`)
- Test: `tests/test_claude_connect.py`, `tests/web/test_connect_routes.py`, `tests/test_desktop.py`

**Interfaces:**
- Consumes: Task 1 `user_files`, `marketplace_source`.
- Produces:
  - `VERSION_MARKER = 'obscura-version.txt'`, `MARKETPLACE = 'obscura'`
  - `class MarketplaceConflict(Exception)` з `.path`
  - `marketplace_target(data_dir: Path) -> Path` = `data_dir/'claude'/'marketplace'`
  - `sync_marketplace(source: Path, target: Path, version: str) -> Literal['created','updated','unchanged']`
  - `refresh_marketplace(source: Path | None, target: Path, version: str, log=logger) -> None` — лише якщо `target` існує; винятки (`OSError`, `MarketplaceConflict`) у журнал.
  - `connect_claude_plugin(claude: Path, target: Path, run=subprocess.run) -> bool`
  - `plugin_commands(target: Path) -> list[str]` — рядки для копіювання (`claude plugin marketplace add "<target>" --scope user`, `claude plugin install obscura@obscura --scope user`).

- [ ] **Step 1: Failing tests:**
  - `test_sync_creates_copy_with_marker` (`created`, файли == `user_files(source)`, маркер = версія); повторно → `unchanged`; інша версія → `updated` і зайвий файл старої копії зник.
  - `test_sync_refuses_foreign_folder`: `target` з `notes.txt` без маркера → `MarketplaceConflict`, `notes.txt` цілий.
  - `test_sync_failure_keeps_old_copy`: monkeypatch `shutil.copy2` кидає `OSError` на другому файлі → стара копія незмінна, тимчасових тек поруч немає.
  - `test_refresh_only_when_copy_exists`: немає `target` → нічого не створено; є стара версія → оновлено; конфлікт → лише запис у журнал.
  - `test_plugin_sequence_new` (Runner: `marketplace list --json` → `[]`): виклики `[claude,'plugin','marketplace','list','--json']`, `[...,'marketplace','add',str(target),'--scope','user']`, `[...,'install','obscura@obscura','--scope','user']` → `True`.
  - `test_plugin_sequence_other_path`: list повертає `obscura` з іншим `path` → `remove obscura`, `add`, `install`.
  - `test_plugin_sequence_same_path`: той самий шлях → лише `list` і `install`.
  - `test_plugin_failures`: list не JSON / код 1 / `install` код 1 / `run` кидає `TimeoutExpired` → `False`.
  - Маршрут: `test_code_route_reports_mcp_and_skills` — відповідь `{'found','connected','skills','command','plugin_commands'}`, `target` створено в `data_dir/claude/marketplace`; `test_code_route_conflict` → `skills: False`, `conflict: <шлях>`; запит із `X-Obscura-Client: mcp` → 403.
  - `tests/test_desktop.py`: `_run` викликає `refresh_marketplace` (через ін’єкцію/monkeypatch) після запису `server.json`, у фоновому потоці; виняток у ньому не змінює код повернення.
- [ ] **Step 2:** `python -m pytest tests/test_claude_connect.py tests/web/test_connect_routes.py tests/test_desktop.py -q` → FAIL.
- [ ] **Step 3:** Реалізувати. Копіювання: `tempfile.mkdtemp(dir=target.parent, prefix='.marketplace-')` → файли + маркер → якщо `target` є: `os.replace(target, old)`, `os.replace(tmp, target)`, `shutil.rmtree(old)`; при помилці повернути `old` і прибрати `tmp`. Порівняння шляху маркетплейсу — `Path(...).resolve()` без урахування регістру (`os.path.normcase`). Маршрут: `connected` (MCP) як зараз; далі `sync_marketplace` → `connect_claude_plugin`; версія — `build_manifest.project_version()`; джерело — `marketplace_source(...)` з `checkout=Path(__file__).resolve().parents[3]`; джерела немає → `skills: False`, `reason: 'no_plugin'`.
- [ ] **Step 4:** Ті самі тести → PASS.
- [ ] **Step 5:** Commit `feat(connect): Claude Code gets the Obscura plugin from a stable copy`.

### Task 4: Скіли для Claude Desktop і інтерфейс

**Files:**
- Modify: `src/storygen/claude_connect.py` (`write_desktop_skills`), `src/storygen/web/routes_connect.py` (новий маршрут), `src/storygen/web/static/claude-connect.js`, `src/storygen/web/templates/library.html`, `src/storygen/web/static/i18n.json` (uk, en)
- Test: `tests/test_claude_connect.py`, `tests/web/test_connect_routes.py`, `tests/web/browser/claude-connect.spec.mjs`

**Interfaces:**
- Consumes: Task 1 `skill_names`, `desktop_zip`, `plugin_root`; Task 3 відповідь `/api/connect/claude-code`.
- Produces: `write_desktop_skills(plugin: Path, folder: Path) -> list[Path]`; `POST /api/connect/claude-desktop/skills` → `{'folder': str, 'files': [str]}`; 409 `NO_PLUGIN = 'Скілів Obscura немає поруч із цією збіркою'`.

- [ ] **Step 1: Failing tests:**
  - `test_desktop_skills_written_and_foreign_kept`: у `folder` є `custom.zip` → після виклику п’ять `<skill>.zip` + `custom.zip`; кожен ZIP читається й має `<skill>/SKILL.md`.
  - Маршрут: `test_desktop_skills_route` (шлях = `data_dir/claude/skills`, п’ять файлів, `_open_folder` викликано з цією текою); без плагіна (monkeypatch джерела → `None`) → 409; мостовий заголовок → 403.
  - Браузер (`claude-connect.spec.mjs`, маршрути замокано як у наявних тестах): кнопка `data-connect="skills"` показує кроки (`connect.skills_steps` з шляхом теки); відповідь Claude Code з `skills:true` → `connect.code_connected_skills`; `skills:false` + `plugin_commands` → блок команд для копіювання.
- [ ] **Step 2:** `python -m pytest tests/test_claude_connect.py tests/web/test_connect_routes.py -q` і `npx playwright test tests/web/browser/claude-connect.spec.mjs` → FAIL.
- [ ] **Step 3:** Реалізувати. Кнопка «Скіли для Claude Desktop» (`connect.skills`) у `library.html` поруч із Desktop. Тексти i18n uk/en: `connect.skills`, `connect.skills_steps` («ZIP-и скілів у {p0}, теку відкрито. У Claude: Settings → Capabilities — увімкніть Code execution and file creation; Customize → Skills → «+» → Create skill → Upload a skill, по одному файлу. Після оновлення Obscura завантажте їх знову.»), `connect.code_connected_skills` («Claude Code підключено разом зі скілами Obscura. Відкрийте нову сесію.»), `connect.code_skills_failed` («Міст підключено, а скіли — ні. Виконайте в терміналі:»), `connect.no_plugin`.
- [ ] **Step 4:** Ті самі тести → PASS.
- [ ] **Step 5:** Commit `feat(connect): Claude Desktop skills as ZIP uploads`.

### Task 5: Специфікація, traceability, сайт

**Files:**
- Modify: `SPEC.MD` (STORE-MCP-001: S06 оновлено, нові S14 копія, S15 Claude Code зі скілами, S16 ZIP Desktop; MCP-BRIDGE: «двадцять сім», S53 `get_guide`; CLAUDE-SKILLS: S10 генерація з одного джерела й заборона чужих посилань, S11 версія плагіна = версія проєкту і без `get_guide`), `docs/verification/traceability.json`, `docs/site/{uk,en}/mcp.md`, `docs/verification/manual.md` (крок завантаження ZIP у Desktop — ручна процедура для S16), журнал `docs/superpowers/plans/2026-10-20-remediation-progress.md`.

- [ ] **Step 1:** `python scripts/check_docs.py` → FAIL (нові тести без traceability).
- [ ] **Step 2:** Внести SPEC, traceability (кожен новий тест), сторінку `mcp` uk/en: розділ скілів — Claude Code через кнопку (і в Store), Desktop — ZIP-и, інші клієнти — `get_guide`; прибрати «у версію з Microsoft Store вони ще не входять». `python scripts/check_site.py --rehash mcp`.
- [ ] **Step 3:** `python scripts/check_docs.py` → «узгоджено»; `python -m pytest -q` → green.
- [ ] **Step 4:** `python scripts/verify.py` з окремого worktree в `C:\tmp`, результат у `docs/STATUS.md`.
- [ ] **Step 5:** Commit `docs: skills in Store build, get_guide, Desktop ZIPs (SPEC, site)`.
