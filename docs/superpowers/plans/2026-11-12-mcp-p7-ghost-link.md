# MCP, пакет 7: посилання, що відкриває Ghost Mode — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** посилання з чату `/stories/{story}?scene=..&material=draft&ghost=1[&draft=..]` відкриває Ghost Mode поточної чернетки; інструмент `open_ghost_mode` видає таке посилання лише для наявної поточної чернетки.

**Architecture:** чиста логіка посилання — новий модуль `static/ghost-link.js` (розбір адреси, причина відмови, очищення адреси), тестований у node; `ghost-mode.js` лише під'єднує її до одноразового `editor-state-changed` і викликає наявний `open()`. Клієнт `storygen-mcp` отримує 13-й інструмент.

**Tech Stack:** ES modules (браузер, node для тестів), Python 3.12, `mcp==2.3.0`, httpx, pytest.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-11-mcp-p7-ghost-link-design.md` (затверджено 2026-11-12).

## Global Constraints

- Адреси без `ghost` поводяться як зараз; даних і сервера пакет не змінює.
- `ghost` діє лише разом із `material=draft` і чинним `scene`; `draft` перевіряється тим самим `safeId`, що `scene`.
- `history.replaceState` прибирає `ghost` і `draft` (лишає `scene`, `material`) до виклику `open()`.
- Посилання відкриває лише поточну голову чернетки: `draft` ≠ голова → відмова; незавершене переписування іншої чернетки → відмова.
- Тексти повідомлень — через `i18n.json` (uk/en), лише `textContent` (через `notice`).
- Інструмент не використовує `writing-context` (межа Store-збірки), лише `GET /api/stories/{id}`.

## Review Focus

1. Посилання на сцену, яку `restorePosition` показує спершу в «Плані»: очікування не скасовується, поки не вибрано іншу сцену.
2. Автор встиг перейти на іншу сцену до завантаження чернетки — режим не відкривається й повідомлення немає.
3. `draft=../x` або `ghost=1` з `material=plan` — посилання ігнорується.
4. Перезавантаження сторінки після відкриття — режим не відкривається вдруге (адресу очищено).
5. Сцена без чернетки чи сцена іншого твору в інструменті — помилка без посилання.

---

### Task 1: Сторінка — модуль посилання й під'єднання до Ghost Mode

**Files:** Create `src/storygen/web/static/ghost-link.js`; Modify `src/storygen/web/static/ghost-mode.js`, `src/storygen/web/static/i18n.json`; Test `tests/web/js/ghost_link.mjs`, `tests/web/test_ghost_mode_ui.py`.

**Interfaces (Produces):**
- `readGhostLink(search: string) -> {sceneId: string, draftId: string|null} | null`
- `ghostLinkRefusal({hasDraft, history, dirty, saving, headDraft, expectedDraftId, resumeDraftId}) -> null | 'no_draft'|'history'|'dirty'|'stale_link'|'old_session'` (порядок перевірок саме такий; `saving` → `'dirty'`)
- `clearGhostLink(location, history) -> void`

- [ ] Тест `ghost_link.mjs`: розбір (повне посилання; без `draft`; `material=plan` → null; `ghost=0` → null; `draft='../x'` → null; без `scene` → null); кожна причина відмови й `null` для поточної голови без сесії та з сесією поточної голови; `clearGhostLink` лишає `scene`, `material` і інші параметри, прибирає `ghost`, `draft`. Обгортка pytest `test_ghost_link_parsing_and_refusals` у `test_ghost_mode_ui.py`.
- [ ] `node tests/web/js/ghost_link.mjs` → FAIL (модуля немає).
- [ ] Реалізація модуля; у `ghost-mode.js`: на старті `link=readGhostLink(location.search)`; якщо є — `clearGhostLink` і одноразовий слухач `editor-state-changed`: інша вибрана сцена → зняти слухача мовчки; та сама сцена, `mode==='draft'`, не `saving` → зняти слухача, `ghostLinkRefusal(...)`; відмова → `notice(t('ghost.link_refused',{p0:t('ghost.link_'+reason)}),'error')`, інакше `open()`. Ключі i18n uk/en: `ghost.link_refused`, `ghost.link_no_draft`, `ghost.link_history`, `ghost.link_dirty`, `ghost.link_stale_link`, `ghost.link_old_session`.
- [ ] `node tests/web/js/ghost_link.mjs` і `pytest tests/web/test_ghost_mode_ui.py tests/web -k "i18n or locali or ghost"` → PASS.
- [ ] commit `feat(ghost): a link with ghost=1 opens Ghost Mode of the current draft`.

### Task 2: Клієнт — `open_ghost_mode`

**Files:** Modify `src/storygen/mcp/bridge.py`; Test `tests/mcp/test_bridge_ghost_link.py`, `tests/mcp/test_bridge.py` (13 інструментів).

- [ ] Тести: посилання для поточної чернетки (з `draft_version_id` і без) — `url == f'{base}/stories/{story}?scene={scene}&material=draft&ghost=1[&draft=..]'`, повертає `draft_version_id` голови; сцена без чернетки → помилка; застарілий `draft_version_id` → помилка; сцена не з цього твору → помилка; ідентифікатори з `..` → без запиту; у Store-збірці для твору понад межу посилання видається; `next_steps` згадує `open_ghost_mode`.
- [ ] `pytest tests/mcp -q` → FAIL.
- [ ] Реалізація за технічним описом специфікації.
- [ ] `pytest tests/mcp -q` → PASS; commit `feat(mcp): open_ghost_mode returns a link that starts Ghost Mode`.

### Task 3: Контракт і документація

- [ ] SPEC: MCP-BRIDGE (13 інструментів, `open_ghost_mode`, S06), GHOST-REWRITE (параметри `ghost`, `draft`), сценарії S23–S25; traceability; сайт `mcp` і `ghost-mode` uk/en з `check_site.py --rehash`; `check_docs.py`.
- [ ] commit `docs(mcp): Ghost Mode link in MCP-BRIDGE, GHOST-REWRITE and on the site`.
