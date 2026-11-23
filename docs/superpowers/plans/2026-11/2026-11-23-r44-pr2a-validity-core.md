# R-44 PR 2a — Ядро валідності зв'язків: план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Позначка «застаріле» для поточних голів завдання, прози й пам'яті рахується за валідністю трьох зв'язків сцени, а автор може затвердити зв'язки З1/З2 вручну.

**Architecture:** Чиста функція `storage/links.py` обчислює ідентичності компонентів, відбитки й статус зв'язку з `ContextView` (без `freshness`/`.stale`, тож без рекурсії). Висновки — append-only записи `link_verdict:` у `app_settings`, завантажені в `ContextView` як `acceptances`. `_compute_freshness` для голів `brief`/`prose`/`memory` активної сцени бере статус зв'язку замість порівняння знімка. Читачі (`effective_scene`, `material_status`, масове затвердження, експорт, MCP, бейдж) отримують нову позначку через вже наявні шляхи.

**Tech Stack:** Python 3.12, Pydantic v2, SQLite (`app_settings`), FastAPI, vanilla JS, pytest, Playwright.

**Spec:** [docs/superpowers/specs/2026-11/2026-11-23-book-validation-design.md](../../specs/2026-11/2026-11-23-book-validation-design.md) — розділи 1–3, 7, 8, 12, 13.

**Межі.** Це перший із двох планів PR 2 (одна гілка `claude/r44-validity-core`, один PR). План 2b (пишеться після фінального рев'ю 2a): `ProseEquivalence`, перенос пам'яті `memory_carry` із пробою, рішення автора для З3, `LinkInvalidation` і діалог карток/локацій, VALID-MEMORY, VALID-CARDS. PR відкривається лише після 2b: без переносу нова пам'ять сцени k лишала б у журналі k+1 старі записи без жодної позначки.

## Global Constraints

- Записи — у `app_settings`, append-only, без міграції SQLite (спека, розділ 7).
- Відбиток зв'язку — SHA-256 від упорядкованих ідентичностей: З1 `(plan_id, p0_digest | None, brief_id)`, З2 `(brief_id, p0_digest | None, prose_id)`, З3 `(prose_id, memory_digest)` (розділ 1).
- Статуси зв'язку: `valid` (джерело `construction`/`auditor`/`author`), `unchecked`, `discrepancy`, `unavailable`, `missing`. Статус сцени: «Валідна» — усі наявні зв'язки `valid`; «Розбіжність» — є `discrepancy`; інакше «Не перевірено» (розділ 2).
- Прийнята як авторська проза (`AcceptanceRecord` голови) не застаріла, але сцена лишається «Не перевірено» (розділ 3).
- Зміна чернетки, канону, стилю й налаштувань твору валідність голів не змінює (розділи 2, 3).
- Мова документації українська; маркери OpenSpec англійські; кожен Scenario — у `docs/verification/traceability.json`; сайт uk/en парами з `check_site.py --rehash`.
- Гейт: `python scripts/check_docs.py && python -m pytest -q` (venv, `PYTHONUTF8=1`, `--basetemp=C:/tmp/r44p2/...`).

## Review Focus

1. **Легасі-версії без знімка** (пам'ять із `save_scene_journal`, завдання з ручного збереження, проза до R-13): зв'язок `unchecked`, а не виняток; книга відкривається.
2. **Сцена в кошику / сцена без плану (лише `beats`)**: обчислення не падає; кошик не дає статусу; ідентичність плану — `None`, коли голови плану немає.
3. **Злиття гілок книги (`MergeRequired`) і початок серії**: П₀ визначається без винятку (`require=False`); відсутня потрібна П₀ — `unavailable/no_previous_memory`.
4. **Продуктивність**: `material_status` обчислює зв'язки для всіх сцен на кожне відкриття твору; дайджести пам'яті й статуси мемоізовано на view (`memo`), 68 сцен < 1 с на копії даних власника.
5. **Гонка рішення автора**: відбиток змінився між читанням і POST → 409, запис не створено.

---

### Task 1: Записи `LinkVerdict` і завантаження у `ContextView`

**Files:**
- Create: `src/storygen/storage/link_records.py`
- Modify: `src/storygen/storage/context_view.py` (завантаження поряд з `acceptances`, `SHARED_FIELDS`)
- Modify: `src/storygen/storage/integrity.py` (перевірка `link_verdict:%`)
- Test: `tests/storage/test_link_records.py`

**Interfaces:**
- Produces:
  - `LinkName = Literal['brief','prose','memory']` (З1, З2, З3 за нижнім компонентом).
  - `class LinkVerdict(DependencyModel)`: `id: str`, `story_id: str`, `scene_id: str`, `link: LinkName`, `inputs: dict[str, str | None]`, `fingerprint: str` (64 hex), `source: Literal['auditor','author']`, `outcome: Literal['valid','discrepancy','unavailable']`, `confidence: int | None` (0–100), `discrepancies: list[Discrepancy]` (≤20; `Discrepancy{text: str, quote: str | None}`), `reason: str | None`, `attempt_id: str | None`, `run_id: str | None`, `created_at: str`.
  - `write_verdict(db, verdict: LinkVerdict) -> None` — `INSERT INTO app_settings VALUES(?,?)` з ключем `link_verdict:{story_id}:{id}`, у транзакції викликача.
  - `ContextView.link_verdicts: dict[tuple[str, LinkName, str], LinkVerdict]` — останній запис (за rowid) для `(scene_id, link, fingerprint)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_verdict_round_trip_through_view(tmp_path):
    repo, story, scene = one_scene(tmp_path)
    verdict = author_verdict(story.id, scene.id, 'brief', 'a'*64)
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE'); write_verdict(db, verdict)
    view = repo.context_view(story.id)          # opened after the write: sees it
    assert view.link_verdicts[(scene.id, 'brief', 'a'*64)] == verdict

def test_latest_verdict_wins_per_fingerprint(tmp_path): ...  # two verdicts, same key → second

def test_fsck_reports_foreign_scene_verdict(tmp_path):
    # key story A, scene of story B → check_integrity(root) has 'invalid_link_verdict'
```

- [ ] **Step 2: Run** `pytest tests/storage/test_link_records.py -q` — Expected: FAIL (`ModuleNotFoundError: storygen.storage.link_records`).
- [ ] **Step 3: Implement** the models and `write_verdict`; load `LIKE 'link_verdict:{story}:%' ORDER BY rowid` in `ContextView.__init__`, refusing a key that is not `'link_verdict:'+story+':'+id` or a scene not of this story (same style as acceptances); add `link_verdicts` to `SHARED_FIELDS`. In `integrity.py` validate each `link_verdict:%` row (key shape, JSON model, scene belongs to story) and report `invalid_link_verdict`.
- [ ] **Step 4: Run** the tests — Expected: PASS.
- [ ] **Step 5: Commit** `feat(R-44): записи висновків про зв'язки сцени`.

### Task 2: Обчислення зв'язків `storage/links.py`

**Files:**
- Create: `src/storygen/storage/links.py`
- Test: `tests/storage/test_links.py`
- Probe (не комітиться): `scratchpad/probe_links.py` на копії `C:\tmp\r44data`

**Interfaces:**
- Consumes: `ContextView.link_verdicts` (Task 1); `previous_memory(view, scene, peek=True, require=False)`; `load_memory`; `view.memo`.
- Produces:
  - `own_events(journal: MemoryJournal) -> list[MemoryEvent]` — події з `source_version_id == journal.source_prose_ids[-1]` (порожньо без джерел).
  - `memory_digest(view, memory_id: str) -> str` — SHA-256 від `json.dumps([e.model_dump(mode='json', exclude={'event_id','source_version_id','evidence_version_id'}) for e in own_events(...)], sort_keys=True, ensure_ascii=False, separators=(',',':'))`. `claim_id`/`resolves_claim_id` входять (стабільні ID тверджень).
  - `p0_identity(view, memory_id: str | None) -> str | None` — `memory` → `memory_digest`; `memory_merge` → `'merge:'+id`; `series_start` → `'series:'+id`; `None` → `None`.
  - `@dataclass(frozen=True) class LinkState`: `link: LinkName`, `status: Literal['valid','unchecked','discrepancy','unavailable','missing']`, `source: Literal['construction','auditor','author'] | None`, `reason: str | None` (`no_previous_memory`/`no_memory`), `inputs: dict[str, str | None]`, `fingerprint: str | None`.
  - `link_state(view, scene_id: str, link: LinkName) -> LinkState` (мемоізовано `memo(view, ('link', scene_id, link), ...)`).
  - `scene_links(view, scene_id) -> dict[LinkName, LinkState]`; `scene_validity(view, scene_id) -> Literal['valid','unchecked','discrepancy','incomplete']` (`incomplete`, якщо немає завдання чи прози).

**Правила (рішення плану, за розділом 2 спеки):**
- `model_made(ref) = ref.source_run_id is not None or (ref.external_origin is not None and snapshot is not None and snapshot.scope not in {'author_text','author_rewrite'})`. MCP `save_draft` (scope `author_text`) — не модель; `save_stage_result` — модель.
- **Записана П₀** знімка — інверсія `previous_memory_selector`: селектор `head/memory` власника `ancestors[-1]` → `expected`; `story/memory_merge_heads` → `expected[merge_key]`; для початку серії — `story.series_start_version_id`, якщо він у `snapshot.refs`. Порівнюється `p0_identity(записана) == p0_identity(поточна)`.
- **З1 за побудовою:** голова завдання `model_made`, знімок має `head/plan` цієї сцени з `expected == scene.heads.get('plan')` (без плану — селектор `scene/beats`, рівний поточним `beats`), і П₀ збігається.
- **З2 за побудовою:** голова прози `edited` і `model_made`. Від неї йти за селектором `head/draft` (`expected`) — кожна версія ланцюжка `model_made`, зі scope `prose_edit`/`patches` — доки не дійде до версії зі scope `draft`. У неї `head/brief == scene.heads['brief']` і П₀ збігається. Обмеження глибини — 50. `author_text`, `author_rewrite`, відсутній знімок, `manual` — розрив.
- **З3 за побудовою:** голова пам'яті має знімок зі scope `memory` (етап, чат або `save_scene_memory`) і `head/prose` цієї сцени з `expected == scene.heads['prose']`.
- **Порядок:** `missing` (немає нижнього чи верхнього компонента сцени: З1 без завдання, З2 без завдання чи прози, З3 без прози) → `unavailable/no_previous_memory` для З1/З2, якщо `ancestors` непорожні чи є злиття, а `memory_id is None` → `unavailable/no_memory` для З3 (проза є, пам'яті немає) → `valid/construction` → останній `LinkVerdict` із поточним відбитком (`valid` → `valid/<source>`, `discrepancy`, `unavailable`) → `unchecked`.
- Сцена в кошику → `missing` для всіх.

- [ ] **Step 1: Write the failing tests** (через `generate_scene` з `FakeGateway` із `tests/generation/test_scene_pipeline.py` і ручні збереження):

```python
def test_generated_scene_is_valid_by_construction(tmp_path):   # VALID-LINKS-S01
    view, scene = generated(tmp_path)
    assert {k: (s.status, s.source) for k, s in scene_links(view, scene.id).items()} == {
        'brief': ('valid','construction'), 'prose': ('valid','construction'), 'memory': ('valid','construction')}

def test_manual_brief_unchecks_brief_and_prose_links(tmp_path): ...    # S02: Z1, Z2 unchecked; Z3 valid
def test_manual_prose_unchecks_prose_and_memory_links(tmp_path): ...   # S03: Z1 valid; Z2, Z3 unchecked
def test_manual_memory_keeps_scene_and_unchecks_next(tmp_path): ...    # S04: own events changed → next Z1/Z2 unchecked
def test_same_own_events_keep_next_scene_valid(tmp_path): ...          # S04: re-saved memory, same events
def test_draft_change_keeps_validity(tmp_path): ...                    # S05: new manual draft head → no change
def test_edit_loop_and_copyedit_chain_is_construction(tmp_path): ...   # S01: patches pass chain → writer draft
def test_chat_stage_result_is_model_made_and_save_draft_is_not(tmp_path): ...  # S09
def test_missing_previous_memory_is_unavailable(tmp_path): ...          # S10: no_previous_memory; no_memory; incomplete → missing
def test_legacy_memory_without_snapshot_is_unchecked(tmp_path): ...     # Review Focus 1
def test_trashed_and_planless_scene_do_not_raise(tmp_path): ...         # Review Focus 2
def test_author_verdict_with_current_fingerprint_validates(tmp_path): ... # вердикт зі старим відбитком не діє
```

- [ ] **Step 2: Run** `pytest tests/storage/test_links.py -q` — Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `links.py` per the rules above. No call to `freshness`, `is_stale`, `get_version(...).stale` or `journal_for_read`: read versions with `view.versions` / `view.read_text`.
- [ ] **Step 4: Run** the tests — Expected: PASS.
- [ ] **Step 5: Probe** — `PYTHONPATH=src python scratchpad/probe_links.py C:/tmp/r44data` (read-only, копія): підрахунок статусів З1/З2/З3 на книзі з 68 сцен і час. Expected: `Z1 valid 49 / unchecked 19`, `Z2 valid 20 / unchecked 48`, `Z3 valid 68`, < 1 с. Розбіжність — помилка правила, не даних: розібрати (systematic-debugging), записати Ruling.
- [ ] **Step 6: Commit** `feat(R-44): валідність трьох зв'язків сцени`.

### Task 3: Рішення автора для З1/З2 і мінімальний інтерфейс

**Files:**
- Create: `src/storygen/storage/link_decisions.py`
- Modify: `src/storygen/web/routes_versions.py` (маршрут), `src/storygen/web/templates/…` (контейнер `#link-attention` поряд із `#workspace-scene-status`)
- Create: `src/storygen/web/static/link-decision.js`; Modify: `src/storygen/web/static/i18n.json` (uk/en)
- Test: `tests/web/test_link_decisions.py`, `tests/web/browser/link-decision.spec.mjs`

**Interfaces:**
- Consumes: `link_state`, `write_verdict`, `LinkVerdict`.
- Produces: `decide_link(repo, scene_id: str, link: LinkName, action: Literal['approve'], fingerprint: str) -> LinkState`; `POST /api/scenes/{scene_id}/links/{link}/decision` body `{action, fingerprint}` → `{'link': LinkState as dict, 'validity': scene_validity}`.

- [ ] **Step 1: Write the failing tests**

```python
def test_author_approves_manual_brief(client_with_manual_brief):          # VALID-LINKS-S08
    state = get_links(client, scene)['brief']; assert state['status'] == 'unchecked'
    r = client.post(f'/api/scenes/{scene}/links/brief/decision', json={'action':'approve','fingerprint':state['fingerprint']})
    assert r.status_code == 200 and r.json()['link'] == {**state, 'status':'valid', 'source':'author'}

def test_stale_fingerprint_is_409_and_writes_nothing(...): ...            # Review Focus 5
def test_memory_link_decision_is_422_until_equivalence(...): ...          # План 2b замінить на «Залишити попередню пам'ять»
def test_unavailable_or_missing_link_cannot_be_approved(...): ...         # 409
```

Playwright: сцена з ручним завданням → у `#link-attention` текст «Завдання не підтверджено» і кнопка «Затвердити завдання» → клік → панель зникає, бейдж сцени не «Не перевірено» (якщо З2 теж валідний). Те саме для прози («Затвердити відповідність»).

- [ ] **Step 2: Run** the tests — Expected: FAIL (404 route).
- [ ] **Step 3: Implement** `decide_link`: `BEGIN IMMEDIATE`, свіжий `ContextView`, `link_state`; відбиток ≠ переданого чи статус `missing`/`unavailable` → `RevisionConflict`; `memory` → `HTTPException(422)`; інакше `write_verdict(LinkVerdict(source='author', outcome='valid', confidence=None, discrepancies=[], ...))`. Статус уже `valid` — без запису, той самий результат. JS: `link-decision.js` читає `material_status[scene].links` з перегляду твору, показує панель для `brief`/`prose` зі статусом `unchecked`, на клік — POST і `refresh()`; 409 → `notice` і `refresh()`. Ключі i18n uk/en.
- [ ] **Step 4: Run** pytest + Playwright — Expected: PASS.
- [ ] **Step 5: Commit** `feat(R-44): авторське затвердження зв'язків завдання й прози`.

### Task 4: Позначка «застаріле» за зв'язками

**Files:**
- Modify: `src/storygen/storage/snapshots.py::_compute_freshness`
- Modify: `src/storygen/storage/context_view.py::effective_scene`
- Test: `tests/storage/test_link_freshness.py`; наявні тести, що впадуть

**Interfaces:**
- Consumes: `link_state` (Task 2).
- Produces: для голови `brief`/`prose`/`memory` активної сцени `FreshnessResult(stale=..., reasons=[DependencyChange(reason='link_unchecked'|'link_discrepancy'|'link_unavailable'|'link_missing', version_id=id)])`; для прийнятої голови прози `stale=False` за будь-якого З2. `effective_scene(id).needs_review = is_stale(prose_head)` для кожної голови прози (збережений прапорець більше не читається).

- [ ] **Step 1: Write the failing tests**

```python
def test_canon_and_style_edits_keep_heads_fresh(tmp_path): ...          # VALID-LINKS-S06
def test_manual_brief_head_is_stale_with_link_reason(tmp_path):        # S02
    assert freshness(view, brief).reasons[0].reason == 'link_unchecked'
def test_accepted_prose_is_fresh_but_scene_unchecked(tmp_path): ...    # S07
def test_non_head_versions_keep_snapshot_comparison(tmp_path): ...     # чернетка й історичні версії як раніше
def test_previous_memory_change_does_not_stale_next_memory_head(tmp_path): ...  # Z3 лише за власною прозою
```

- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement**: у `_compute_freshness` після `incomplete`/`integrity_error`, якщо `ref.scene_id` активної сцени і `scene.heads.get(head) == ref.id` для `head` з `{'brief':'brief','edited':'prose','manual':'prose','memory':'memory'}[ref.kind]`: прийнята проза (`view.acceptances[id].action == 'accept_prose'`) → без причин; інакше статус ≠ `valid` → причина `link_<status>`. Порівняння знімка для таких голів не виконується. `effective_scene` — як у Produces.
- [ ] **Step 4: Run** the new tests — Expected: PASS. Then run the full suite in the background to `C:/tmp/r44p2/full-t4.log` and read the tail. Expected: нові падіння там, де тести покладалися на легасі-позначку чи на застарілу пам'ять через попередника. Кожне падіння класифікувати: (а) тест перевіряв поведінку, яку спека змінює → оновити очікування й маркер на VALID-LINKS; (б) поведінка, яку спека зберігає → виправити код. Кожне (а) з вилученням Scenario — Ruling у журналі.
- [ ] **Step 5: Commit** `feat(R-44): позначка «застаріле» за зв'язками сцени`.

### Task 5: Читачі: `material_status`, масове затвердження, MCP, бейдж

**Files:**
- Modify: `src/storygen/storage/material_status.py` (+ `links`, `validity` на сцену)
- Modify: `src/storygen/storage/acceptance.py::_waiting_prose` (перевірити: голова прози застаріла ⇔ З2 невалідний і не прийнята)
- Modify: `src/storygen/mcp/bridge.py::scene_state`; `src/storygen/web/static/workspace-status.js`; `i18n.json`
- Test: `tests/storage/test_material_status.py`, `tests/mcp/…scene_state…`, `tests/web/browser/workspace-layout.spec.mjs` (або власний спек бейджа)

**Interfaces:**
- Produces: `material_status(view)[scene_id] = {brief, prose, memory, links: {brief|prose|memory: {status, source, reason, fingerprint}}, validity}`. `sceneStatusKey` / `scene_state`: `not_started`, `no_text`, `draft` (без прози), `prose` (проза без завдання — сцена `incomplete`), `valid`, `unchecked`, `discrepancy`. Ключ `needs_review` зникає з бейджа (його поглинає `unchecked`).

- [ ] **Step 1: Write the failing tests** — `material_status` повертає `links`/`validity` (S11); масове затвердження перелічує ручну прозу, але не згенеровану з валідним З2 (S07); `scene_state` дає `unchecked` для сцени з ручним завданням і `valid` для згенерованої (паритет із JS — наявний тест паритету, якщо є; інакше новий).
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** — `links` через `scene_links`; JS-мітки «Валідна» / «Не перевірено» / «Розбіжність» (en: "Valid" / "Unchecked" / "Discrepancy"); експорт (`publication/book.py`) не змінюється: він уже читає `stale`/`needs_review`.
- [ ] **Step 4: Run** pytest + Playwright — Expected: PASS.
- [ ] **Step 5: Commit** `feat(R-44): статуси зв'язків у перегляді твору, MCP і бейджі`.

### Task 6: SPEC, traceability, сайт

**Files:** `SPEC.MD`, `docs/verification/traceability.json`, `docs/verification/manual.md` (за потреби), `docs/site/{uk,en}/…` (сторінки зі змістом «застаріле», бейдж, затвердження прози), `docs/site/sync.json`.

- [ ] **Step 1:** SPEC: нова вимога **VALID-LINKS** (сценарії S01–S12 з цього плану: S01 згенерована сцена; S02 ручне завдання; S03 ручна проза; S04 ручна пам'ять; S05 чернетка; S06 канон/стиль; S07 прийнята проза й масове затвердження; S08 рішення автора й CAS; S09 чат; S10 відсутні компоненти; S11 статуси в перегляді, MCP, бейджі; S12 fsck записів). Змінити DATA-010 (авторське рішення для завдання; S02 — перелік за З2), MCP (`scene_state`), розділ про позначку «застаріле»/BROKEN-TEXT, де він описує голови. Вилучені чи переписані сценарії Task 4 — з причиною.
- [ ] **Step 2:** traceability для кожного нового сценарію; маркери `@pytest.mark.req('VALID-LINKS')`.
- [ ] **Step 3:** сайт uk/en: що означає «Не перевірено», як затвердити завдання/прозу; `check_site.py --rehash <slug>` для кожної пари.
- [ ] **Step 4:** Run `python scripts/check_docs.py` — Expected: OK.
- [ ] **Step 5: Commit** `docs(R-44): VALID-LINKS у специфікації й документації`.

Фінальне рев'ю 2a (opus) — перед планом 2b. Повний гейт, verify.py, cross-review і PR — після 2b.
