# R-40, пакет 1, обв'язка: скіл `revise` у контрактах, документації й PR — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** скіл `revise`, збудований і перевірений у ядрі (`claude/r40-core`, план `2026-11-25-revise-skill-core.md`), стає частиною контрактів Obscura: міст і провідник знають шість скілів, SPEC.MD описує скіл і сценарії S12–S15, traceability зелена, користувацька документація uk/en описує скіл, а гілка йде в PR на `main`.

**Architecture:** сервер не змінюється, крім тексту `INSTRUCTIONS` і опису `get_guide` у мості. Перевірки стенду посилюються за вхідними даними фінального рев'ю ядра. Codex лишається на п'яти скілах (`CHAT_ONLY = ('revise',)`): спека R-40 охоплює Claude Code, Claude Desktop і провідник `get_guide`, а не Codex. Це рішення записується в CODEX-SKILLS як чинний контракт.

**Tech Stack:** Python 3.12, pytest, `claude -p` (stream-json), MCP-міст Obscura, `scripts/check_docs.py`, `scripts/check_site.py`, `scripts/verify.py`.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-25-revise-skill-design.md` (затверджено 2026-11-25), §6, §8, §9. Вхід: фінальне рев'ю ядра — розділ «Harness-plan inputs (17)» нижче переписано в задачі; номери `h1…h17` посилаються на нього.

## Global Constraints

- Тексти скіла англійською; документація, SPEC.MD і журнал — українською; маркери OpenSpec англійською (`AGENTS.md`).
- Скіл: посилання лише на `${CLAUDE_PLUGIN_ROOT}/shared/rules.md` і `${CLAUDE_PLUGIN_ROOT}/skills/revise/references/<назва>.md`; лише інструменти з `TOOLS` моста; `get_guide` у тексті скіла не згадувати; без слів `Claude`, `subagent`, `advisor`, `AskUserQuestion`.
- Жодного запису до згоди на показану таблицю; змінена таблиця — нова згода (spec §8).
- Кожен Scenario має сталий ID і запис у `docs/verification/traceability.json`; `python scripts/check_docs.py` — exit 0.
- Змінена сторінка сайту — обидві мовні версії й `python scripts/check_site.py --rehash <slug>`.
- Стенд, повний pytest і `scripts/verify.py` — лише з короткого шляху `C:/tmp/<коротка-назва>` (WinError 206).
- Робочого екземпляра Obscura автора не чіпати.
- PR лише на `main`; `docs/STATUS.md` не комітити.

## Review Focus

1. Скіл із довідкою `fact-change.md`, яку `local-edit.md` згадує (§6/§7/§10): через `get_guide` клієнт мусить отримати другу довідку — текст `INSTRUCTIONS`/опис `get_guide` має це дозволяти (тест у Task 3).
2. Стара назва в преамбулі плану («Задум») після S13 — перевірка має її бачити (Task 1).
3. Запис, якого немає в `REVISE_WRITES` (наприклад `update_story`), до згоди — перевірка має його ловити (Task 1).
4. Додане речення в сцені, якого не було у фікстурі, — перевірка має його ловити (Task 1).
5. Codex: інвентар `NAMES ∪ CHAT_ONLY` і текст SPEC/сайту «п'ять скілів Codex» мають збігатися (Task 4).

---

### Task 1: Перевірки стенду й фікстура

**Files:**
- Modify: `integrations/claude/tools/run_scenarios.py`, `integrations/claude/tools/revise_setup.py`, `scripts/skills_stand.py`
- Test: `tests/test_run_scenarios.py`, `tests/test_skills_stand.py`

Вхід h3, h5, h6, h7, h9, h10, h14.

- [ ] **Step 1 (h6):** `REVISE_WRITES` → `WRITES - {'start_run'}` плюс наявне правило `start_run` з `confirm`. Тест `test_revise_preconsent_flags_any_bridge_write` (виклик `update_story` до згоди → проблема).
- [ ] **Step 2 (h7):** розбиття на речення з урахуванням рядків (рядок плану без крапки — окреме «речення»), без нормалізації пробілів усередині, і виявлення доданих речень. Тести `test_revise_text_header_line_is_separate`, `test_revise_text_added_sentence_is_a_problem`.
- [ ] **Step 3 (h9):** `revise_chain_problems` перевіряє порядок: перший запис сцени 2 після останнього запису сцени 1. Тест `test_revise_chain_scene_order_is_checked`.
- [ ] **Step 4 (h5):** `check_s13` додає `get_story.plan_preamble` до перевірки тексту (немає `Одес`, є `Херсон`); `ctx['originals']` зберігає преамбулу. Тест на чисту функцію.
- [ ] **Step 5 (h3):** ядро пам'яті фікстури за правилом зміни дня (сцена 2: `unknown` з причиною для clothing/carried/body), і перевірка S13 збереження пам'яті: claims/цитати старої пам'яті з заміною основи `Одес→Херсон` мусять бути в новій (порівняння множин текстів). Тест `test_revise_memory_preserved_with_stem_replaced` (позитив і негатив).
- [ ] **Step 6 (h10):** `skills_stand.py` не дописує текст події `result`, якщо він дорівнює останньому повідомленню асистента. Тест у `test_skills_stand.py`.
- [ ] **Step 7 (h14):** `run_turns` підсумовує `usage` ходів; бюджет `--max-budget-usd` — на хід, це записати в `--help`. Тест на підсумок.
- [ ] **Step 8:** `pytest tests/test_run_scenarios.py tests/test_skills_stand.py -q -p no:cacheprovider --basetemp C:/tmp/r40h1` → PASS. Commit `fix(tools): R-40 перевірки revise за фінальним рев'ю`.

### Task 2: Уточнення тексту скіла

**Files:**
- Modify: `integrations/claude/obscura/skills/revise/SKILL.md`, `references/fact-change.md`, `references/local-edit.md`
- Test: `tests/test_claude_plugin.py` (наявні структурні перевірки)

Вхід h4, h12, h13, h17 і підказка `max_chars` з фінального прогону.

- [ ] **Step 1 (h4):** у виклику аудиту з `confirm=true` назвати `plan_fingerprint` з перегляду.
- [ ] **Step 2 (h13):** біблія серії: `get_story.series` має лише `title`, `number`, `bible`; знайти біблію через `list_stories` (назва «<Серія>: біблія»), за неоднозначності — одне питання.
- [ ] **Step 3 (h17):** маршрут obscura: автор вносить заміни в прозу сцени (редактор прози у вікні Obscura); якщо змінено лише чернетку — пам'ять читатиме стару прозу, тож скіл каже це в таблиці.
- [ ] **Step 4 (h12):** рішення: повідомлення згоди містить одне питання (згоду); відкриті питання таблиці — окремим рядком таблиці «потребує рішення», без другого знака питання в тому самому повідомленні. Узгоджено з `shared/rules.md` (одне питання за раз).
- [ ] **Step 5:** у читанні режиму редактора — `get_stage_task(..., max_chars ≥ 1000)` (менше сервер відхиляє 422).
- [ ] **Step 6:** структурні тести (`tests/test_claude_plugin.py tests/mcp/test_bridge_guide.py tests/test_codex_skills.py tests/test_skill_bundles.py`) і grep заборонених слів → чисто. Commit `fix(skills): R-40 revise — уточнення за фінальним рев'ю`.

### Task 3: Міст: шість скілів

**Files:**
- Modify: `src/storygen/mcp/bridge.py` (`INSTRUCTIONS` ~104, опис `get_guide` ~336)
- Test: `tests/mcp/test_bridge_guide.py` (`SKILLS` → шість, з `revise`)

- [ ] **Step 1:** тест: `SKILLS` містить `revise`; `get_guide(task='revise')` повертає текст і перелік довідок `fact-change`, `local-edit`, `rules`; `get_guide(task='revise', reference='fact-change')` — текст довідки.
- [ ] **Step 2:** `INSTRUCTIONS` і опис `get_guide` називають шість скілів, з `revise`; одне речення: скіл `revise` — правка вже написаного твору (зміна факту, локальна правка).
- [ ] **Step 3:** `pytest tests/mcp -q -p no:cacheprovider --basetemp C:/tmp/r40h3` → PASS. Commit `feat(mcp): R-40 провідник знає скіл revise`.

### Task 4: SPEC.MD, traceability, ручна процедура

**Files:**
- Modify: `SPEC.MD` (CLAUDE-SKILLS ~5842, MCP-BRIDGE ~5253, CODEX-SKILLS ~8527), `docs/verification/traceability.json`, `docs/verification/manual.md#claude-skills`

Вхід spec §6, h1, h2, h8, h11, h15, h16.

- [ ] **Step 1 (spec §6, h15):** CLAUDE-SKILLS: `revise` у переліку з обома маршрутами; рядок обмежень «скіл `revise` (переписування за коментарями) — окремий пакет R-40» замінити на «переписування в режимі `obscura` моделлю Obscura з чату — пакет 2 R-40»; нові Scenario S12–S15 за текстом spec §6, S13 THEN доповнено преамбулою плану (h5) і збереженням пам'яті (h3); відомі обмеження spec §9; немає сценарію chat + редактор `patches` (h2) — записати обмеженням із ручною процедурою.
- [ ] **Step 2:** MCP-BRIDGE: перелік скілів у `INSTRUCTIONS` і `get_guide` — шість.
- [ ] **Step 3 (h16):** CODEX-SKILLS: інвентар генератора — `NAMES ∪ CHAT_ONLY`, генеруються лише `NAMES` (п'ять); невідома тека — `source_skill_inventory_changed`; `revise` у Codex — лише через провідник. Звірити «п'ять скілів» у S04 і тексті.
- [ ] **Step 4 (h1, h8, h11):** `manual.md#claude-skills`: сценарії з кількох ходів (`--resume`), S15 «питає» — ручна перевірка змісту, YAML-перевірка frontmatter, повтор S12–S15 на коміті PR.
- [ ] **Step 5:** traceability: S12–S15 → `integrations/claude/obscura/evals/revise.json` через `manual.md#claude-skills`; нові тести ядра й Task 1–3 з маркерами `req` — до своїх Scenario. `python scripts/check_docs.py` → exit 0.
- [ ] **Step 6:** Commit `docs(spec): R-40 скіл revise у SPEC і traceability`.

### Task 5: Користувацька документація

**Files:**
- Modify: `docs/site/uk/mcp.md`, `docs/site/en/mcp.md` (розділ «Скіли Obscura»: шість скілів, приклад «перенеси дію в інше місто», `/obscura:revise`); за потреби `docs/site/{uk,en}/revision.md` — посилання на скіл
- Modify: `docs/site/site.json` (через `--rehash`)

- [ ] **Step 1:** uk і en: шостий скіл, що він робить (зміна факту через таблицю на погодження й показ першої сцени; локальна правка — варіанти місць), режим obscura (таблиця, заміни вносить автор), Codex — п'ять скілів, `revise` через провідник.
- [ ] **Step 2:** `python scripts/check_site.py --rehash mcp` (і `revision`, якщо змінено); `python scripts/check_docs.py` → exit 0. Commit `docs(site): R-40 скіл revise`.

### Task 6: Прогін, перевірка, PR

**Files:**
- Modify: `docs/superpowers/plans/2026-10-20-remediation-progress.md` (R-40), `docs/superpowers/plans/2026-10-20-remediation-backlog.md` (рядок R-40)

- [ ] **Step 1 (h11):** `run_scenarios.py --scenario S12 --scenario S13 --scenario S14 --scenario S15 --work C:/tmp/r40scn5 --model sonnet` на коміті після Task 1–5 → усі `passed: true`; ручна перевірка `text.md`.
- [ ] **Step 2:** detached worktree `C:/tmp/r40v` на коміт, junction `.venv` і `frontend/node_modules`; `python scripts/verify.py` → passed/failed/errors/skipped у журнал і опис PR. Прибрати junction через `cmd /c rmdir` перед `git worktree remove`.
- [ ] **Step 3:** журнал R-40 (коміт, моделі, `passed`/`cost_usd`, `verify.py`), статус R-40 у беклозі (пакет 1 — у PR; пакет 2 — далі). Commit `docs(progress): R-40 пакет 1 — підсумок`.
- [ ] **Step 4:** rebase на `origin/main`, `npx -y @ysilvestrov/detent cross-review --author claude` у фоні; розбір знахідок; PR на `main` з маркером, таблицею рішень, результатом `verify.py`, оновленими інструкціями (сайт `mcp` uk/en), `Closes`-рядком лише якщо є issue R-40.
- [ ] **Step 5:** оновити основну теку `C:\Projects\text-generator` до перевіреного коміту без `reset --hard`/`clean`, перевірити ревізію й наявність файлів скіла.
