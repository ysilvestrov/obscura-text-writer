# R-44 PR 2b — Пам'ять і картки у валідності зв'язків: план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Пам'ять сцени отримує власні рішення автора й механічний перенос у пізніші журнали, а зміна карток і локацій за згодою автора знімає валідність зв'язків залежних сцен.

**Architecture:** Будується на ядрі 2a (`storage/links.py`, `link_records.py`, `link_decisions.py`). Нові append-only записи `ProseEquivalence` і `LinkInvalidation` — у `app_settings` поруч із `LinkVerdict` і в `ContextView`. Перенос пам'яті — новий безмодельний режим черги `memory_carry`, що пересобирає журнали пізніших сцен із нового журналу попередника та їхніх власних подій. Стан переносу виводиться з журналів (власні події поверх поточного журналу попередника), а не зберігається окремо.

**Tech Stack:** Python 3.12, Pydantic v2, SQLite (`app_settings`), FastAPI, vanilla JS, pytest, Playwright.

**Spec:** [docs/superpowers/specs/2026-11/2026-11-23-book-validation-design.md](../../specs/2026-11/2026-11-23-book-validation-design.md) — розділи 3 (`_candidate`), 4, 7, 8, 10, 13.

**Межі.** Другий план PR 2 (та сама гілка `claude/r44-validity-core`, один PR після нього). Вхід — фінальне рев'ю 2a (рішення в журналі виконання 2a, рядки `Final:`): пам'ять без знімка блокує наступну сцену без рішення автора; загальна помилка «Контекст містить застарілий матеріал» не називає сцени; перенумерація знімає З1. Ревізор, перевірка сцени й валідація книги — PR 3/4.

## Global Constraints

- Записи — у `app_settings`, append-only, без міграції SQLite (спека, розділ 7): `prose_equivalence:{story}:{id}`, `link_invalidation:{story}:{id}`.
- `memory_digest` не змінюється від переносу: перенесена пам'ять має ті самі власні події, тож відбитки сцен k+2… лишаються (розділ 4).
- Перенос без моделі й бюджету; кожен крок — окрема транзакція з CAS за ревізією сцени; поки перенос не дійшов до сцени, модельні етапи цієї й пізніших сцен відмовляють «Пам'ять переноситься» (розділ 4).
- `carry_failed` знімає лише нова пам'ять цієї сцени (етап пам'яті чи ручна правка), не рішення автора й не Ревізор (розділ 4).
- Картки й локації змінюють валідність лише за явним «Так» автора; збереження без автора (MCP, перерахунок складу) — ні (розділ 10).
- Мова документації українська; маркери OpenSpec англійські; кожен Scenario — у `docs/verification/traceability.json`; сайт uk/en парами з `check_site.py --rehash`.
- Гейт: `python scripts/check_docs.py && python -m pytest -q` (venv, `PYTHONUTF8=1`, `--basetemp=C:/tmp/r44p2/...`).

## Review Focus

1. **Легасі-журнали, що вже розійшлися з попередником** (дані власника: `journal_for_read` відмовляє в 33 сценах): виведений `carry_failed` не має масово з'явитися на старій книзі без жодної нової пам'яті. Проба на копії даних власника до вибору правила.
2. **Злиття гілок і початок серії** як попередник у переносі: перенос не падає; злиття, яке треба підтвердити, зупиняє перенос із зрозумілою причиною.
3. **Гонка переносу з правкою автора**: автор змінює пам'ять раніше за точку переносу — запуск починає з неї; ручна правка сцени під переносом — CAS-відмова кроку, не втрата правки.
4. **Сцена без прози чи без пам'яті посеред книги**: перенос проходить її, не створюючи порожньої пам'яті.
5. **Відмова модельних етапів під час переносу** діє і для чату (`save_stage_result`, `save_draft`), а читання й ручні правки дозволені.

---

### Task 1: Рішення автора для З3 і рівноцінність прози

**Files:**
- Modify: `src/storygen/storage/link_records.py` (модель `ProseEquivalence`, `write_equivalence`, `load_equivalences`, fsck), `src/storygen/storage/context_view.py` (`self.prose_equivalences`), `src/storygen/storage/integrity.py`
- Modify: `src/storygen/storage/link_decisions.py` (`DECIDABLE` + `memory`), `src/storygen/web/routes_versions.py` (прибрати 422 для `memory`)
- Modify: `src/storygen/memory/reuse.py::_candidate` (пари з ланцюжка рівноцінностей сцени вважаються підтвердженими)
- Test: `tests/storage/test_link_records.py`, `tests/web/test_link_decisions.py`, `tests/memory/test_prose_equivalence.py` (новий)

**Interfaces:**
- Produces: `ProseEquivalence(DependencyModel)` — `id`, `story_id`, `scene_id`, `old_prose_id`, `new_prose_id`, `verdict_id`, `created_at`; `equivalent_pairs(view, scene_id) -> set[tuple[str, str]]` (транзитивне замикання пар сцени) у `link_records.py`.
- `decide_link(repo, scene_id, 'memory', 'approve', fingerprint)`: у тій самій транзакції — `LinkVerdict(source='author', outcome='valid')` і, якщо проза, з якої зроблено поточну пам'ять (останнє джерело журналу), ≠ поточній голові прози, — `ProseEquivalence(old=джерело журналу, new=голова прози, verdict_id)`. `unavailable/carry_failed` → 409 (Task 3).

- [ ] **Step 1:** Тести (падають):
  - `test_author_keeps_memory_after_prose_edit` — згенерована сцена, `save_manual_prose` → З3 `unchecked`; рішення `memory` з поточним відбитком → З3 `valid/author`, записано `ProseEquivalence(old, new)`.
  - `test_kept_memory_unblocks_the_next_scene` — після рішення `build_context(scene2, 'brief')` не кидає «Спершу оновіть пам'ять попередньої сцени»; без рішення — кидає.
  - `test_memory_without_snapshot_can_be_kept` (рев'ю 2a, Important 3) — пам'ять сцени 1 без знімка: З3 `unchecked`, рішення автора → `valid`, наступна сцена не блокується.
  - `test_equivalence_chain_is_transitive` — дві правки прози поспіль, два рішення → пара (перша, третя проза) підтверджена в `_candidate`.
  - `test_fsck_reports_foreign_equivalence` — запис для чужої сцени → `invalid_prose_equivalence`.
  - У `test_link_decisions.py` тест `test_memory_link_decision_is_refused_for_now` замінити на `test_author_keeps_memory_through_the_api` (200, `source='author'`).
- [ ] **Step 2:** Run — FAIL.
- [ ] **Step 3:** Реалізація за Interfaces; `_candidate`: `needs_confirmation = ref.stale or any(old != selected and (old, selected) not in approved_source_pairs(provenance) | equivalent_pairs(view, ancestor.id))`.
- [ ] **Step 4:** Run `tests/storage/test_link_records.py tests/web/test_link_decisions.py tests/memory/test_prose_equivalence.py tests/memory` — PASS.
- [ ] **Step 5: Commit** `feat(R-44): рішення автора для пам'яті й рівноцінність прози`.

### Task 2: Ідентичність плану без номера сцени та точна причина застарілості

**Files:**
- Modify: `src/storygen/storage/links.py` (`plan_identity`, `_plan_matches`, вхід `plan` у відбитку З1)
- Modify: `src/storygen/generation/context.py` (`add()` ~331: текст помилки)
- Test: `tests/storage/test_links.py`, `tests/generation/test_stale_context_message.py` (новий)

**Interfaces:**
- Produces: `plan_identity(view, scene) -> str | None` — `'plan:' + sha256(текст плану з порожнім номером у першому непорожньому рядку)` (через `plan_renumber.renumber_plan`/`scene_description.explicit_scene_number`), для сцени без голови плану — `'beats:' + sha256(beats)`. Мемо `('plan_identity', plan_id)`.
- `_plan_matches` порівнює ідентичність плану зі знімка (`head/plan` → версія → текст) з поточною.
- Це змінює визначення входу `plan` у відбитку З1 зі спеки (ID голови → хеш тексту без номера): Ruling у журналі виконання й рядок в описі PR. Старі рішення автора для З1 після цього не збігаються за відбитком — сцени з ними знову «Не перевірено» (на даних власника рішень автора ще немає).

- [ ] **Step 1:** Тести (падають):
  - `test_renumber_keeps_the_brief_link` — дві згенеровані нумеровані сцени, вставка сцени перед ними: З1 обох лишається `valid/construction`, а рішення автора для З1 переживає перенумерацію.
  - `test_real_plan_edit_still_unchecks_the_brief` — зміна тексту плану (не номера) → З1 `unchecked`.
  - `test_stale_context_names_the_scene_and_action` — проза сцени 1 автора під завданням автора (З2 `unchecked`), `build_context(scene2, 'draft')` → помилка містить назву сцени 1 і «затвердьте або прийміть прозу».
- [ ] **Step 2:** Run — FAIL.
- [ ] **Step 3:** Реалізація. Текст помилки для голови з невалідним зв'язком: «Сцена «{title}»: {матеріал} не перевірено — затвердьте зв'язок або прийміть прозу як авторську» (ключ каталогу uk/en; для решти — як було).
- [ ] **Step 4:** Run `tests/storage tests/generation` — PASS; оновити тести, що чекали старий текст.
- [ ] **Step 5: Commit** `feat(R-44): перенумерація не знімає З1; помилка називає сцену`.

### Task 3: Перенос пам'яті `memory_carry`

**Files:**
- Create: `src/storygen/memory/carry.py` (чисті функції переносу), `src/storygen/generation/memory_carry.py` (виконання запуску)
- Modify: `src/storygen/run_models.py` (`mode='memory_carry'`, `scene_id` = сцена, з якої почати), `src/storygen/generation/worker.py` (enqueue/дублікати/диспетчер без провайдера), `src/storygen/generation/readiness.py` (відмова модельних етапів «Пам'ять переноситься»), `src/storygen/memory/service.py` і `src/storygen/storage/repository.py::commit_stage_result` (поставити перенос у чергу при новій голові пам'яті), `src/storygen/storage/links.py` (З3 `unavailable/carry_failed` | `carry_pending`), MCP (`save_stage_result`, `save_draft` — та сама відмова)
- Test: `tests/memory/test_memory_carry.py` (новий), `tests/generation/test_memory_carry_run.py` (новий)

**Interfaces:**
- Produces: `carry_journal(previous: MemoryJournal, journal: MemoryJournal) -> MemoryJournal` у `memory/carry.py` — новий журнал = `previous` + власне джерело сцени + власні події `own_events(journal)` без змін; `CarryFailed(reason)`, якщо подія посилається (`update`/`retire`/`resolves_claim_id`) на твердження, якого немає в `previous`, або `validate_memory_journal` проти прози не проходить.
- `carry_state(view, scene_id) -> Literal['current', 'pending', 'failed'] | None` у `memory/carry.py`: `current`, якщо успадкована частина журналу сцени дорівнює журналу поточної П₀; інакше `pending` за активного запуску `memory_carry` твору, що ще не пройшов сцену, інакше `failed`. Мемо на view.
- `Run.mode='memory_carry'`: завдання — сцени від `scene_id` у порядку читання; крок: `carry_journal` → `save_version('memory', …, dependency_snapshot=знімок скоупу memory поточних голів)` + `set_head` з CAS за ревізією; невдача → сцена лишається, запуск завершується `completed` з `checkpoint.failed_scene_id`; зміна пам'яті раніше за точку → наступний запуск від неї (supersede).

**Рішення, зафіксовані до тестів:**
- **Хто ставить перенос.** Лише нова голова пам'яті від автора чи етапу (`publish_memory_journal`, `commit_stage_result` для `memory`, `save_stage_result` чату), і лише коли пізніше в лінії книги є сцена з пам'яттю. Крок переносу сам перенос не ставить (без самозапуску).
- **Багатоетапний запуск.** Запуск `remaining`/`scene`/`rebuild_memory`, що сам записав пам'ять сцени k, не відмовляє собі: відмова «Пам'ять переноситься» діє лише для сцен, до яких перенос ще не дійшов, і лише коли в тих сцен є пам'ять, яку треба перенести. Сцена без пам'яті (ще не згенерована) не блокується: її пам'ять буде збудовано з нового журналу.
- **Перенос невидимий для валідності.** Крок пише версію пам'яті з тим самим знімком залежностей, що й попередня голова сцени, замінивши лише селектор `head/memory` попередника (і `refs` журналу); `head/prose` не оновлюється. Тож неперевірений З3 лишається неперевіреним, затверджений автором — валідним (той самий відбиток: проза й `memory_digest` не змінилися).
- **Стан у view.** `carry_state` читає запуски через `ContextView` (завантаження активних запусків `memory_carry` твору разом із рештою), щоб `pending` не залипав після завершення запуску.

- [ ] **Step 1 (проба, до правила):** скрипт `C:/tmp/r44p2/probe_carry.py` на копії `C:/tmp/r44p2/data`: (а) скільки сцен мають `carry_state != 'current'` без жодних змін (Review Focus 1); (б) замінити пам'ять однієї ранньої сцени (змінити текст одного власного запису) і порахувати частку сцен, де `carry_journal` сходиться до кінця книги. Результат — у журнал виконання. Якщо (а) > 0, Ruling: легасі-розбіжність показується як `carry_pending`/`failed` лише після першої нової пам'яті попередника (виводити від запису запуску переносу), щоб стара книга не позначилася масово.
- [ ] **Step 2:** Тести (падають):
  - `test_carry_keeps_own_events_and_digest` — нова пам'ять сцени 1 (інший текст запису) → після переносу журнал сцени 2 = новий журнал 1 + власні події 2, `memory_digest` сцени 2 незмінний, З1/З2 сцени 3 лишаються `valid`.
  - `test_carry_fails_on_missing_claim` — сцена 2 оновлює твердження сцени 1, якого в новому журналі 1 немає → `carry_failed`, пам'ять сцени 2 не змінена, перенос далі не йде; рішення автора для З3 → 409.
  - `test_new_memory_clears_carry_failed_and_continues` — ручна пам'ять сцени 2 на новому журналі → `current`, перенос іде до сцени 3.
  - `test_model_stages_refused_while_carrying` — запуск `memory_carry` у черзі: readiness етапу `draft` сцени 3 → «Пам'ять переноситься»; ручне збереження прози сцени 3 — дозволене; MCP `save_draft` → відмова.
  - `test_carry_restarts_from_an_earlier_change` і `test_carry_step_respects_scene_revision` (Review Focus 3).
  - `test_carry_skips_scene_without_memory` (Review Focus 4).
  - `test_carry_through_merge_and_series_start` (Review Focus 2).
  - `test_one_run_generates_three_scenes_without_refusal` — запуск `remaining` на три сцени поспіль завершується без «Пам'ять переноситься».
  - `test_carry_does_not_launder_memory_links` — після переносу неперевірений З3 сцени 2 лишається `unchecked`, затверджений автором — `valid/author`, а голова чернетки сцени 3 не застаріла.
  - `test_carry_step_enqueues_no_carry` — після кроку переносу в черзі немає нового запуску.
- [ ] **Step 3:** Run — FAIL.
- [ ] **Step 4:** Реалізація за Interfaces. Перенос ставить у чергу та сама транзакція, що змінює голову пам'яті (`set_head` для `memory` і `commit_stage_result` для етапу `memory`): INSERT запуску в тій самій транзакції (`run_store` з'єднання), ідемпотентно за `request_id = 'carry:' + memory_id`.
- [ ] **Step 5:** Run `tests/memory tests/generation tests/mcp` — PASS.
- [ ] **Step 6: Commit** `feat(R-44): механічний перенос пам'яті в пізніші сцени`.

### Task 4: Інвалідація за картками й локаціями

**Files:**
- Modify: `src/storygen/storage/link_records.py` (`LinkInvalidation`, `write_invalidation`, `load_invalidations`, fsck), `context_view.py`, `src/storygen/storage/links.py` (правило (г): інвалідація з поточним відбитком, новіша за останній валідний висновок, скасовує (а)–(в) → `unchecked`)
- Modify: `src/storygen/characters/service.py::save_character_material` (+ `changed_character_ids`, `dependent_scene_ids`), `src/storygen/storage/locations.py` (дії повертають `dependent_scene_ids`), новий маршрут `POST /api/stories/{id}/links/invalidate {scene_ids, reason: {kind: 'character'|'location', ids}}`
- Modify: `src/storygen/web/static/characters.js`, `locations-panel.js` (діалог `confirmDialog`), i18n uk/en
- Test: `tests/storage/test_link_invalidation.py` (новий), `tests/web/test_card_invalidation.py` (новий), `tests/web/browser/card-invalidation.spec.mjs` (новий)

**Interfaces:**
- Produces: `LinkInvalidation(DependencyModel)` — `id`, `story_id`, `scene_id`, `links` (`['brief','prose']`), `fingerprints` (`{link: fingerprint}` на момент запису), `reason {kind, ids}`, `created_at`.
- Порядок записів інвалідації й висновків — порядок вставки (`rowid` у `app_settings`), не `created_at`: рішення автора, записане в той самий момент після інвалідації, перемагає.
- `dependent_scene_ids(view, character_ids)` — активні сцени з цими ID у `character_ids` або `narrator.character_id`; для локацій — сцени з канонічною локацією серед змінених (`canonical`).

- [ ] **Step 1:** Тести (падають):
  - `test_invalidation_unchecks_construction_and_author_verdicts` — згенерована сцена й сцена з рішенням автора: інвалідація → З1, З2 `unchecked`, голови застарівають за правилом 2a; нове рішення автора після неї → `valid`.
  - `test_invalidation_with_old_fingerprint_is_inert` — зміна компонента після інвалідації: вона не діє (інший відбиток).
  - `test_character_save_reports_changed_and_dependent` — зміна опису картки → `changed_character_ids == [id]`, `dependent_scene_ids` — сцени з персонажем чи оповідачем; збереження без змін → порожні.
  - `test_location_change_reports_dependent` — опис/злиття/поділ.
  - `test_saving_cards_alone_changes_no_link` — без POST інвалідації (MCP, «Ні») валідність не змінюється.
  - `test_fsck_reports_foreign_invalidation`.
  - `test_approval_right_after_invalidation_wins` — інвалідація й рішення автора з однаковим `created_at`: діє пізніше вставлене.
  - Playwright: після збереження картки діалог «Змінено картки: … Позначити N залежних сцен як неперевірені?»; «Так» → бейдж сцени «Не перевірено»; «Ні» → «Валідна».
- [ ] **Step 2:** Run — FAIL.
- [ ] **Step 3:** Реалізація за Interfaces.
- [ ] **Step 4:** Run `tests/storage tests/web tests/characters` + Playwright spec — PASS.
- [ ] **Step 5: Commit** `feat(R-44): інвалідація зв'язків за картками й локаціями`.

### Task 5: Дії панелі для пам'яті та недоступних зв'язків

**Files:**
- Modify: `src/storygen/web/static/link-decision.js` (З3 `unchecked`: «Залишити попередню пам'ять» → рішення; «Створити нову пам'ять» → `invokeWorkspaceCommand('run', {mode: 'stage', stage: 'memory'})`; `unavailable/no_previous_memory|no_memory|carry_failed` — пояснення й «Створити пам'ять» для відповідної сцени; `carry_pending` — «Пам'ять переноситься»), i18n uk/en
- Test: `tests/web/browser/link-decision.spec.mjs` (розширити), `tests/web/js/link_decision.mjs` + pytest-обгортка (новий, чисті функції `pendingLinks`)

- [ ] **Step 1:** Тести (падають): `pendingLinks` повертає дії для кожного статусу; браузер — «Залишити попередню пам'ять» знімає позначку пам'яті й розблоковує наступну сцену.
- [ ] **Step 2:** Run — FAIL. **Step 3:** Реалізація. **Step 4:** Run — PASS.
- [ ] **Step 5: Commit** `feat(R-44): дії панелі для пам'яті й недоступних зв'язків`.

### Task 6: SPEC, traceability, сайт

**Files:** `SPEC.MD`, `docs/verification/traceability.json`, `docs/verification/manual.md`, `docs/site/{uk,en}/{workspace,memory,characters}.md`, `docs/site/sync.json`, знімки за потреби.

- [ ] **Step 1:** SPEC: нові вимоги **VALID-MEMORY** (рівноцінність, рішення З3, перенос, `carry_failed`/`carry_pending`, відмова етапів; сценарії S01–S07 за тестами Task 1, 3, 5) і **VALID-CARDS** (S01–S04 за Task 4); змінити MEMORY-REUSE/MEMORY-003 (рівноцінні пари), VALID-LINKS (ідентичність плану без номера, правило (г), помилка з назвою сцени, рішення З3 замість 422), IMPORT-NUMBER (прибрати відоме обмеження перенумерації), MCP-BRIDGE (відмова під час переносу), RUN-модель (`memory_carry`).
- [ ] **Step 2:** traceability й маркери `@pytest.mark.req` на функціях.
- [ ] **Step 3:** Сайт uk/en: «Залишити попередню пам'ять», «Створити нову пам'ять», перенос пам'яті, діалог карток; `check_site.py --rehash` для кожної пари.
- [ ] **Step 4:** Run `python scripts/check_docs.py` — OK.
- [ ] **Step 5: Commit** `docs(R-44): VALID-MEMORY і VALID-CARDS у специфікації й документації`.

Фінальне рев'ю 2b (opus), повний гейт, verify.py, cross-review, PR 2 на `main`, самостійне злиття, оновлення основної теки.
