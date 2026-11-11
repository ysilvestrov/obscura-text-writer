# MCP-клієнт: показ походження й інструкції (PR 2 #84) — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** автор бачить, що чернетку записав зовнішній чат-клієнт, і має інструкцію UA/EN, як підключити `storygen-mcp`.

**Architecture:** чиста функція `externalOriginLabel(version)` у новому `static/external-origin.js`; її показують історія версій (`versions.js`) і рядок стану (`#workspace-origin`, оновлюється в `loadBuffer`). Нова сторінка сайту `mcp` UA/EN.

**Tech Stack:** vanilla ES-модулі, i18n.json, node-тести через pytest, `docs/site/`.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-10-mcp-server-design.md` (розділ «PR 2 — показ і документація»).

## Global Constraints

- Позначка: «Зовнішній клієнт: <client>», з моделлю — «Зовнішній клієнт: <client> · <model>»; EN «External client: <client>» / «… · <model>».
- Назва клієнта й модель показуються лише як текст (`textContent`), ніколи як HTML.
- Сторінка сайту — обидві мови, `python scripts/check_site.py --rehash mcp`; без посилань на внутрішні матеріали.
- Приймання з реальним клієнтом — дія власника (MCP-BRIDGE-S07), PR її не оголошує виконаною.

## Review Focus

1. Модель або назва клієнта з `<`/`&` не стає розміткою.
2. Позначка зникає, коли поточна версія вже без `external_origin` (автор зберіг свою правку).
3. Старі версії без поля не показують нічого.
4. Перемикання UA/EN оновлює позначку без перезавантаження.
5. Інструкція описує обмеження: Obscura має бути запущена, пам’ять попередньої сцени має бути оновлена, відверті сцени клієнт може відхилити.

---

### Task 1: Позначка зовнішнього клієнта

**Files:** Create `src/storygen/web/static/external-origin.js`, `tests/web/js/external_origin.mjs`, `tests/web/test_external_origin_ui.py`; Modify `src/storygen/web/static/versions.js`, `src/storygen/web/static/editor.js`, `src/storygen/web/templates/story.html`, `src/storygen/web/static/i18n.json`.

**Interfaces:** Produces `externalOriginLabel(version) -> string` ('' без походження).

- [ ] Тест node: без поля → ''; `{client:'Claude Code'}` → «Зовнішній клієнт: Claude Code»; з моделлю → «… · sonnet»; EN-локаль → «External client: …».
- [ ] Реалізація й ключі `version.external_client`, `version.external_client_model` (UA/EN).
- [ ] Історія: опція версії з походженням має « · <позначка>»; рядок стану: `<p id="workspace-origin" class="muted" hidden>` у `#workspace-status-row`, оновлюється в `loadBuffer` через `uiText`.
- [ ] Тест шаблону: `#workspace-origin` є в рядку стану; `editor.js` і `versions.js` імпортують `externalOriginLabel`.
- [ ] Commit.

### Task 2: Інструкція, SPEC, traceability

**Files:** Create `docs/site/{uk,en}/mcp.md`; Modify `docs/site/site.json`, `docs/site/{uk,en}/index.md` (тема), `docs/site/sync.json`, `SPEC.MD` (MCP-BRIDGE: показ походження, S10), `docs/verification/traceability.json`, `docs/verification/manual.md` (процедура посилається на сторінку), журнал, беклог R-32, специфікація зміни («Actual»).

- [ ] Сторінка: встановлення extra, реєстрація в Claude Code / Claude Desktop / Codex, сценарій «план → імпорт → контекст → чернетка → Ghost Mode», позначка в історії, обмеження й помилки (префікс «Error executing tool …»).
- [ ] `check_site.py --rehash mcp`, `check_docs.py`, повний pytest, verify.py.
- [ ] Commit.
