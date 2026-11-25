# R-40, пакет 1, ядро: скіл `revise` і його сценарії — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** скіл `revise` у плагіні Obscura з маршрутами «зміна факту» і «локальна правка», перевірений сценаріями CLAUDE-SKILLS-S12…S15 на ізольованому стенді.

**Architecture:** скіл — Markdown (`SKILL.md` + дві довідки) поверх наявних інструментів MCP; сервер не змінюється. Стенд отримує фікстуру книги з двома написаними сценами (план, проза, пам'ять) і підтримку сценаріїв із кількох ходів однієї сесії `claude -p --resume`. Перевірки сценаріїв — чисті функції в `run_scenarios.py` з юніт-тестами.

**Tech Stack:** Python 3.12, pytest, `claude -p` (stream-json), MCP-міст Obscura (`scripts/skills_stand.py`).

**Spec:** `docs/superpowers/specs/2026-11/2026-11-25-revise-skill-design.md` (затверджено 2026-11-25). Обв'язка — окремий план після ревю ядра: текст `INSTRUCTIONS`/`get_guide`, SPEC.MD (CLAUDE-SKILLS S12–S15, MCP-BRIDGE), traceability, `docs/verification/manual.md#claude-skills`, сайт `mcp` uk/en, рішення щодо Codex (CODEX-SKILLS генерує рівно п'ять скілів), `scripts/verify.py`, PR.

## Global Constraints

- Тексти скіла англійською; `description` — з фразами наміру українською й англійською; відповіді — мовою автора (CLAUDE-SKILLS).
- Frontmatter `SKILL.md` — лише `name`, `description` (дозволені ще `license`, `compatibility`, `metadata`, `allowed-tools`); `name` = назва теки `revise`.
- Посилання лише на `${CLAUDE_PLUGIN_ROOT}/shared/rules.md` і `${CLAUDE_PLUGIN_ROOT}/skills/revise/references/<назва>.md`; на файли іншого скіла — ніколи (`BundleError`). Інший скіл називати лише в бектиках (`` `draft-scene` ``).
- Згадувати лише інструменти з `TOOLS` моста (CLAUDE-SKILLS-S03); `get_guide` не згадувати (S11).
- Щоб пізніше додати скіл до Codex без переписування: у текстах скіла немає слів `Claude`, `subagent`, `advisor`, `AskUserQuestion` (`codex_skills.py:215`); питання — «one question at a time, as the shared rules say».
- Жодного запису до згоди на показану таблицю; змінена таблиця — нова згода (spec §8).
- Стенд лише в `C:/tmp/<коротка-назва>`; робочий екземпляр Obscura автора не чіпати.
- Повний pytest і стенд — з короткого шляху (`AGENTS.md`, WinError 206).

## Review Focus

1. Місто у відмінках («Одеси», «Одесі», «Одесою»): перевірка шукає основу `Одес`, а не точне слово — тест у Task 2 (`test_revise_text_old_stem_in_any_case_is_a_problem`).
2. Речення без старого факту мають лишитися байт у байт (там можуть бути правки автора) — тест у Task 2 (`test_revise_text_changed_unrelated_sentence_is_a_problem`).
3. Неінтерактивна сесія без відповіді на картку не повинна нічого записати — S12 і тест `test_revise_preconsent_any_write_is_a_problem` у Task 2.
4. Сцена 2 після зміни сцени 1: brief має бути збережено перед draft, і сцена має закінчити `prose`/`valid` — перевірка `revise_chain_problems` у Task 2, сценарій S13.
5. Твір «obscura»: план змінювати можна, текст — ні — тест `test_obscura_revise_plan_write_is_allowed` у Task 2.

---

### Task 1: Фікстура книги з двома написаними сценами

**Files:**
- Create: `integrations/claude/tools/fixture/revise/plan.md`, `prose-1.md`, `prose-2.md`
- Create: `integrations/claude/tools/revise_setup.py`
- Test: `tests/test_run_scenarios.py`

**Interfaces:**
- Produces: `revise_setup.REVISE_TITLE = 'Маяк на Ланжероні'`, `OLD_STEM = 'Одес'`, `NEW_CITY = 'Херсон'`, `NEW_STEM = 'Херсон'`; `prepare_revise(base: str, writing_mode: str = 'chat') -> tuple[str, list[str]]` — (story_id, [scene_1_id, scene_2_id]); `fixture_text(name: str) -> str`.

- [ ] **Step 1: Фікстура.** `plan.md` — формат `fixture/plan.md` (персонажі ті самі Анна й Петро, `characters.md` береться з `fixture/characters.md`), дві сцени; «Одеса» в преамбулі («Задум»), у рядку `Локація:` обох сцен і в `Що відбувається:` сцени 1. `prose-1.md` і `prose-2.md` — по 200–300 слів, діалоги з довгим тире, місто згадано у 2–3 реченнях кожної сцени різними відмінками, решта речень про місто не згадує.

- [ ] **Step 2: Failing test**

```python
@pytest.mark.req('CLAUDE-SKILLS')
def test_revise_fixture_has_old_city_in_plan_and_both_scenes():
    for name in ('plan.md', 'prose-1.md', 'prose-2.md'):
        assert OLD_STEM in fixture_text(name)
        assert NEW_STEM not in fixture_text(name)
    assert sum(1 for line in fixture_text('plan.md').splitlines() if line.startswith('Локація:') and OLD_STEM in line) == 2
```

Run: `pytest tests/test_run_scenarios.py::test_revise_fixture_has_old_city_in_plan_and_both_scenes -q` → FAIL (`ModuleNotFoundError: revise_setup`).

- [ ] **Step 3: `revise_setup.py`.** `prepare_revise` без моделі, через `scripts.skills_stand.obscura_call`: `create_story(REVISE_TITLE, 'uk', writing_mode='chat', content_rating 0/0/0)` → `import_plan_and_characters` → для кожної сцени по черзі brief (`SETUP_BRIEF` з `measure_models`) → `save_draft(prose-N)` → edit у форматі `prose` з тим самим текстом → memory. Відповідь пам'яті будується з матеріалу завдання, як `do_memory` у `docs/superpowers/specs/2026-11/2026-11-25-revise-skill-probe/ob.py`: `schema_version: 4`, ядро `unchanged` для всіх слотів, `facts.add` — одне твердження з містом («Анна живе на маяку під Одесою.») з `evidence_ids` фрагмента, що містить «Одес». Для `writing_mode='obscura'` — після заповнення `PUT /api/stories/{id}/writing-mode {writing_mode:'obscura', expected_revision}` прямим HTTP (з моста режим змінити не можна, `routes_stories.py:45`). Запуск як скрипт: `python integrations/claude/tools/revise_setup.py --work C:/tmp/<назва> [--mode obscura]` — стенд, `prepare_revise`, друк `get_story` (стан і `links` сцен), зупинка стенда.

- [ ] **Step 4:** `pytest tests/test_run_scenarios.py::test_revise_fixture_has_old_city_in_plan_and_both_scenes -q` → PASS.

- [ ] **Step 5: Перевірка на стенді.** `python integrations/claude/tools/revise_setup.py --work C:/tmp/r40fx` → обидві сцени `state= prose`, `validity= valid`; `get_scene_text(memory)` кожної сцени має `version_id` і містить «Одес». Те саме з `--mode obscura` → `writing_mode: obscura`.

- [ ] **Step 6: Commit** — `test(skills): R-40 фікстура книги для сценаріїв revise`.

### Task 2: Сценарії з кількох ходів і перевірки S12–S15

**Files:**
- Modify: `scripts/skills_stand.py` (`Result`, `parse_result`, `claude_command`)
- Modify: `integrations/claude/tools/run_scenarios.py`
- Test: `tests/test_skills_stand.py`, `tests/test_run_scenarios.py`

**Interfaces:**
- Consumes: `revise_setup.prepare_revise`, `OLD_STEM`, `NEW_STEM`, `fixture_text` (Task 1).
- Produces: `Result.session_id: str | None`; `claude_command(prompt, *, mcp_config, plugin_dir, model, budget_usd, resume: str | None = None)`; у `run_scenarios`: `REVISE_WRITES = {'save_draft', 'save_stage_result', 'update_scene', 'update_plan_preamble'}`, `revise_preconsent_problems(calls) -> list[str]`, `revise_text_problems(original: str, revised: str, old_stem: str, new_stem: str, label: str) -> list[str]`, `revise_chain_problems(calls, scene_ids: list[str]) -> list[str]`, `obscura_revise_problems(calls) -> list[str]`; ключ сценарію `'turns': list[str]` замість `'prompt'`.

- [ ] **Step 1: Failing tests (`tests/test_skills_stand.py`)**

```python
def test_session_id_from_init_event():
    lines = [json.dumps({'type': 'system', 'subtype': 'init', 'session_id': 'abc-1'}),
             json.dumps({'type': 'result', 'is_error': False, 'result': 'ok'})]
    assert parse_result(lines).session_id == 'abc-1'

def test_claude_command_resume(tmp_path):
    cmd = claude_command('далі', mcp_config=tmp_path/'m.json', plugin_dir=tmp_path, model='sonnet', budget_usd=1, resume='abc-1')
    assert cmd[cmd.index('--resume') + 1] == 'abc-1'
    assert '--resume' not in claude_command('x', mcp_config=tmp_path/'m.json', plugin_dir=tmp_path, model='sonnet', budget_usd=1)
```

- [ ] **Step 2: Failing tests (`tests/test_run_scenarios.py`)**, `@pytest.mark.req('CLAUDE-SKILLS')`:

```python
def test_revise_preconsent_any_write_is_a_problem():
    assert revise_preconsent_problems([('get_story', {}), ('update_scene', {})]) == ["до згоди записано: ['update_scene']"]
    assert revise_preconsent_problems([('start_run', {'confirm': True})]) == ["до згоди записано: ['start_run']"]
    assert revise_preconsent_problems([('start_run', {'action': 'audit'})]) == []

def test_revise_text_old_stem_in_any_case_is_a_problem():
    assert revise_text_problems('Жила в Одесі.', 'Жила в Одесі.', 'Одес', 'Херсон', 'сцена 1') == [
        'сцена 1: лишилося «Одес»', 'сцена 1: немає «Херсон»']

def test_revise_text_changed_unrelated_sentence_is_a_problem():
    original = 'Жила в Одесі. Пила чай.'
    assert revise_text_problems(original, 'Жила в Херсоні. Пила каву.', 'Одес', 'Херсон', 'сцена 1') == [
        'сцена 1: змінено речення без старого факту: «Пила чай.»']
    assert revise_text_problems(original, 'Жила в Херсоні. Пила чай.', 'Одес', 'Херсон', 'сцена 1') == []

def test_revise_chain_brief_before_draft_in_second_scene():
    s1, s2 = 'a', 'b'
    ok = [('save_stage_result', {'scene_id': s, 'stage': st}) if st != 'draft' else ('save_draft', {'scene_id': s})
          for s in (s1, s2) for st in ('brief', 'draft', 'edit', 'memory')]
    assert revise_chain_problems(ok, [s1, s2]) == []
    no_brief = [c for c in ok if not (c[1].get('scene_id') == s2 and c[1].get('stage') == 'brief')]
    assert revise_chain_problems(no_brief, [s1, s2]) == ['сцена 2: draft без нового brief']

def test_obscura_revise_plan_write_is_allowed():
    assert obscura_revise_problems([('update_scene', {}), ('update_plan_preamble', {})]) == []
    assert obscura_revise_problems([('save_draft', {})]) == ["у творі obscura записано текст: ['save_draft']"]
```

Run: `pytest tests/test_skills_stand.py tests/test_run_scenarios.py -q` → нові тести FAIL (ImportError / AttributeError).

- [ ] **Step 3: `skills_stand.py`.** `Result.session_id` з першої події `type: system, subtype: init`; `claude_command(..., resume=None)` додає `--resume <id>` після `-p <prompt>`.

- [ ] **Step 4: Перевірки в `run_scenarios.py`.** Речення — розбиття за `(?<=[.!?…])\s+` після злиття рядків; `revise_text_problems` повертає проблеми в порядку: стара основа, нова основа, змінені речення. `revise_chain_problems`: для кожної сцени збережені етапи мають іти в порядку brief → draft → edit → memory (відсутній brief у сцени 2 — проблема; у сцени 1 brief необов'язковий, якщо план не змінювався). `start_run` — запис лише з `confirm=True`.

- [ ] **Step 5: Кілька ходів у `run()`.** Сценарій із `'turns'` запускає перший хід як зараз, кожен наступний — `claude_command(turn, …, resume=prev.session_id)`, вивід у `run-<n>.jsonl`; `tool_calls`, `errors`, `text` склеюються по ходах, `ctx['turn_calls']` — список викликів кожного ходу; хід без `session_id` — помилка сценарію. `setup: 'revise'` / `'revise-obscura'` → `prepare_revise`, а `ctx['originals']` = прози й плани сцен до сесії.

- [ ] **Step 6: Сценарії** (`SCENARIOS`):
  - `S12`: setup `revise`; prompt «Перенеси дію твору «Маяк на Ланжероні» з Одеси в Херсон.»; check — `revise_preconsent_problems(calls)` + у тексті є назви обох сцен.
  - `S13`: setup `revise`; turns: [«Перенеси дію твору «Маяк на Ланжероні» з Одеси в Херсон. Змінюється лише назва міста, нових деталей не шукай і не питай. Покажи таблицю правок і першу сцену.», «Ок, застосовуй усю таблицю.»]; check — `revise_preconsent_problems(ctx['turn_calls'][0])`; для кожної сцени `revise_text_problems` прози (`get_scene_text(prose)`) і плану (`get_scene_text(plan)`) проти `ctx['originals']`; `revise_chain_problems(ctx['turn_calls'][1], scenes)`; пам'ять кожної сцени має новий `version_id`, без «Одес» і з «Херсон»; `get_story`: обидві сцени `prose`.
  - `S14`: setup `revise-obscura`; prompt S12 + « Я погоджуюсь із таблицею.»; check — `obscura_revise_problems(calls)` + «Херсон» у тексті.
  - `S15`: setup `revise`; prompt «Зроби першу сцену твору «Маяк на Ланжероні» смішнішою.»; check — `revise_preconsent_problems(calls)` + `asked(calls, text)`.

- [ ] **Step 7:** `pytest tests/test_skills_stand.py tests/test_run_scenarios.py -q` → PASS, старі тести без змін.

- [ ] **Step 8: Commit** — `test(skills): R-40 сценарії revise з кількома ходами`.

### Task 3: Скіл `revise`

**Files:**
- Create: `integrations/claude/obscura/skills/revise/SKILL.md`, `references/fact-change.md`, `references/local-edit.md`
- Create: `integrations/claude/obscura/evals/revise.json`
- Test: `tests/test_claude_plugin.py`, `tests/mcp/test_bridge_guide.py`, `tests/test_codex_skills.py` (наявні, без змін)

**Interfaces:**
- Consumes: сценарії S12–S15 (Task 2) — їхні промпти й перевірки задають, що скіл мусить витримати.
- Produces: скіл `revise` з довідками `fact-change`, `local-edit` (назви, які побачать ZIP і провідник).

- [ ] **Step 1: `SKILL.md`** — spec §3: перше рядок «Read `${CLAUDE_PLUGIN_ROOT}/shared/rules.md` first and follow it throughout.» (його шукає генератор Codex); твір і режим; вибір маршруту одним рядком; передумови (`needs_review` не блокує, блокують відмови сервера); підсумок. `description`: «Use when the author wants to change something in an already written Obscura story: move the setting, change a date or an event's format, fix a character, or make a scene funnier, slower, shorter. Triggers include "перенеси дію", "виправ у творі", "зміни факт у книжці", "цей персонаж не такий", "зроби сцену смішнішою", "change a fact in the story", "move the story to another city", "make scene 3 funnier".»
- [ ] **Step 2: `references/fact-change.md`** — spec §4.1–§4.5 дослівно за змістом: картка зміни; перевірка фактів із джерелами (без пошуку — сказати й питати); пошук наслідків (прямі, похідні, побут); таблиця з наслідковими записами й рядками «на твій вибір»; ланцюжок сутностей сцени від першої, що потребує правки; залежність між сценами (тотожне завдання й чернетка, Ревізор, «Я перевірив сам», `carry_failed`); перейменування персонажа спершу в картці; `patches`/`diff` і `obscura` — таблиця замін і §4.5; перша сцена з показом «було → стало» і «ок»; підсумок. Порядок викликів для кожної сутності — як у spec §4.4 кроки 1–5, з полями `plan_version_id`, `draft_version_id`, `expected_revision`, `context_fingerprint`, `task_fingerprint`.
- [ ] **Step 3: `references/local-edit.md`** — spec §5: 3–6 місць цитатами, по одній картці на місце (2–3 варіанти + «лишити як є»), без зміни фактів, застосування ланцюжком від чернетки або таблиця замін.
- [ ] **Step 4: `evals/revise.json`** — формат `evals/draft-scene.json`, `skill_name: revise`, записи S12, S13, S14, S15 з промптами з Task 2 і твердженнями (автоматичні + «(manual)» для одного питання за раз і показу «було → стало»).
- [ ] **Step 5:** `pytest tests/test_claude_plugin.py tests/mcp/test_bridge_guide.py tests/test_codex_skills.py tests/test_skill_bundles.py -q` → PASS. Перевірити, що `skill_bundles` будує ZIP `revise.zip` з `references/rules.md`, `fact-change.md`, `local-edit.md`.
- [ ] **Step 6: Commit** — `feat(skills): R-40 скіл revise`.

### Task 4: Прогін сценаріїв на стенді

**Files:**
- Modify (лише за провалом поведінки): `integrations/claude/obscura/skills/revise/**`
- Modify: `docs/superpowers/plans/2026-10-20-remediation-progress.md` (розділ R-40)

- [ ] **Step 1:** `python integrations/claude/tools/run_scenarios.py --scenario S12 --scenario S13 --scenario S14 --scenario S15 --work C:/tmp/r40scn --model sonnet` → у кожному рядку `"passed": true`.
- [ ] **Step 2:** Вручну за `C:/tmp/r40scn/<сценарій>/text.md`: одне питання за раз (S12, S15), таблиця з наслідковими записами (S12, S14), показ першої сцени «було → стало» в першому ході S13, мова відповіді українська.
- [ ] **Step 3:** Провал поведінки скіла — виправити текст скіла (не перевірку) і повторити Step 1–2; правило провалу — `docs/verification/manual.md#claude-skills`.
- [ ] **Step 4:** Записати в журнал R-40: коміт, модель, `passed` і `cost_usd` кожного сценарію, ручні спостереження.
- [ ] **Step 5: Commit** — `docs(progress): R-40 прогін сценаріїв revise`.

Після Task 4 — ревю всієї гілки ядра (кінцеве ревю subagent-driven-development); його висновки — вхід плану обв'язки.
