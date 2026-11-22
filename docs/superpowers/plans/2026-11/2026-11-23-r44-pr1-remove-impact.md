# R-44 PR 1 — Видалення перевірки впливу (R-28) — план

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Прибрати R-28 / review3/4 повністю, зберігши читання історії й масове затвердження прози (кнопка — у меню твору).

**Architecture:** Видаляються пакети `impact/`, `review/`, їхня обробка в генерації, сховищі, маршрутах і інтерфейсі. Хуки в `_compute_freshness` зникають; позначка «застаріле» — чинне порівняння знімка без накладок R-28. Запуски `mode='impact'` і спроби `impact_*`/`review_part` лишаються читабельними, новий запуск `impact` відхиляється.

**Tech Stack:** Python 3.12, FastAPI, Jinja, vanilla JS (ES modules), pytest + Node-тести.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-23-book-validation-design.md` (розділи 11, 13, 14 — PR 1).

## Global Constraints

- Мова інтерфейсу uk/en; нові рядки — в `static/i18n.json` для обох мов.
- Без міграції SQLite; ключі `impact:`/`review3:`/`review4:`/`review-authority:` не читаються, резервна копія переносить їх як є.
- `RunRequest.mode='impact'` лишається в Literal для читання; `Worker.enqueue` відхиляє його текстом «Перевірку впливу вилучено; скористайтеся валідацією книги».
- Гейт: `python scripts/check_docs.py && python -m pytest -q` (venv проєкту, `PYTHONUTF8=1`, `--basetemp=C:/tmp/r44p1`); `verify.py` — з короткого шляху `C:/tmp/r44p1v`.
- Користувацька документація: сайт uk/en сторінки з «Перевірка книги» оновлюються парно, `check_site.py --rehash`.

## Review Focus

1. Збережена база з запусками `impact` і спробами `impact_part`/`review_part` відкривається: список запусків, історія спроб, резервна копія, `fsck` — без помилок.
2. Версія, яку раніше «очищав» `no_impact` чи прийнята сесія перевірки, після видалення показується як застаріла, а не падає (на даних власника таких 0, але тест потрібен).
3. Масове затвердження прози з меню твору: той самий перелік, підтвердження й CAS, що й раніше на сторінці (DATA-010-S02).
4. Старе посилання `/stories/{id}/revision` (закладки, MCP `next_steps`) веде на сторінку твору.
5. MCP `get_story` / `scene_state` без `impact_status` не ламає клієнтів: стани сцени лишаються з чинного словника.

---

### Task 1: Масове затвердження без R-28 і кнопка в меню

**Files:**
- Modify: `src/storygen/storage/acceptance.py` (відмова за відкритого запуску `impact` вилучається — новий такий запуск неможливий)
- Modify: `src/storygen/web/templates/story.html` (пункт меню «Затвердити всю прозу як авторську» замість «Перевірка книги»; скрипт `prose-acceptance.js`)
- Modify: `src/storygen/web/static/prose-acceptance.js`, `src/storygen/web/static/story-menu.js` (без лічильника `impact_status`; пункт видимий за непорожнього `GET /api/stories/{id}/prose-acceptance`)
- Modify: `src/storygen/web/routes_stories.py` (`/stories/{id}/revision` → 303 на `/stories/{id}`)
- Test: `tests/storage/test_prose_acceptance_bulk.py`, `tests/web/test_story_menu*.py` / відповідні Node-тести

- [ ] Тест: `GET /stories/{id}/revision` → 303 на сторінку твору; сторінка твору містить `#story-menu-accept-prose` (hidden) і не містить `story-menu-revision`.
- [ ] Тест: тест масового прийняття за відкритого запуску `impact` замінено — збережений запуск `impact` у стані `running` не блокує прийняття (він історичний).
- [ ] Реалізація; Node-тест меню: пункт з'являється, коли перелік непорожній, і відкриває той самий діалог підтвердження (назви сцен, кількість).
- [ ] Комміт.

### Task 2: Позначка «застаріле» й читання без R-28

**Files:**
- Modify: `src/storygen/storage/snapshots.py` (вилучити блок review/impact/authority у `_compute_freshness`)
- Modify: `src/storygen/storage/context_view.py` (SHARED_FIELDS і завантаження impact/review/authority; `get_stored_version`/`effective_scene`)
- Modify: `src/storygen/storage/repository.py` (`impact()`, `review()`, скан `review3:`/`review4:` у `get_version`)
- Modify: `src/storygen/storage/integrity.py` (перевірки записів R-28 → ключі пропускаються як невідомі історичні)
- Test: нові `tests/storage/test_impact_removed.py`

- [ ] Тест: версія з застарілим знімком і записом `impact:{story}:report:` + `application` (сирі JSON у `app_settings`) — `resolve_freshness` повертає `stale=True` з причинами знімка; `fsck` і резервна копія проходять, ключі збережено.
- [ ] Тест: `get_version` для версії без знімка з записом `review3:{story}:acceptance:` повертає ref без звернення до review.
- [ ] Реалізація; повний `tests/storage` зелений.
- [ ] Комміт.

### Task 3: Запуски, етапи й статус сцени без R-28

**Files:**
- Modify: `src/storygen/run_models.py` (поля `impact_protocol`, `review_contract_version`, `impact_plan_fingerprint` — лише для читання; `Run.impact` — необов'язкове)
- Modify: `src/storygen/generation/worker.py` (enqueue відхиляє `impact`; dispatch/resume гілки вилучено)
- Modify: `src/storygen/generation/readiness.py`, `generation/stages.py`, `providers/requests.py`, `providers/policy.py` (`impact_*`, `review_part` поза `STAGE_POLICY_ROLE` і `MULTI_SCENE_STAGES`), `generation/broken_text.py`, MODEL-002 перелік
- Modify: `src/storygen/web/routes_stories.py` (без `impact_status`), `src/storygen/application/workspace_bench.py`, `src/storygen/mcp/bridge.py` (`scene_state` без `impact_*`, `get_story` без `impact_status`)
- Modify: `src/storygen/web/static/workspace-status.js` (без `impact_*` ключів, `pendingMaterialCount`, `reviewNeedsAuthor`), `workspace-navigation.js`, `run-jump.js` (без `#review-attention`)
- Test: `tests/web/test_runs.py`, `tests/mcp/test_bridge.py`, Node `workspace_status.mjs`, `workspace_navigation.mjs`

- [ ] Тест: `POST /api/runs` з `mode='impact'` → 400 з текстом із Global Constraints; збережений запуск `impact` і спроби `impact_part`/`review_part` читаються через `GET /api/stories/{id}/runs` і список спроб.
- [ ] Тест: MCP `get_story` не має `impact_status`; `scene_state` дає стани з чинного словника для застарілої прози.
- [ ] Реалізація.
- [ ] Комміт.

### Task 4: Видалення пакетів, сторінки й тестів R-28

**Files:**
- Delete: `src/storygen/impact/`, `src/storygen/review/`, `src/storygen/generation/impact_*.py`, `src/storygen/storage/{impact_store,impact_validity,impact_checks,review_store,review_authority,review_checks}.py`, `src/storygen/web/routes_{impact,review}.py` (+ реєстрація в `web/app.py`), `templates/revision.html`, `static/{impact,review-session,revision-page,revision-context}.js`, `generation/resources/{impact_*,review_part_*}`, записи `PROMPTS` у `language.py`
- Delete: `tests/impact/`, `tests/review/`, `tests/web/test_{impact,review,review4}_api.py`, `tests/integration/test_review_regressions.py`; правки тестів, що лише імпортували R-28 як фікстуру
- Modify: `static/i18n.json` (ключі `impact.*`, `review.*`, `review4.*`, `workspace.menu_revision`, `workspace.review_attention`); `story.html` (`#review-attention`, `#review-session`, скрипт)

- [ ] Пошуковий тест (новий `tests/test_impact_removed.py`): у `src/storygen` немає `import`/`from` модулів `impact`, `review`, `impact_*`, `review_*` і рядків `review-session`, `impact.js`; у каталозі i18n немає ключів `impact.`/`review.`/`review4.`.
- [ ] Видалення; `python -m pytest -q` зелений (тести, що перевіряли лише R-28, видалено разом із ним; список видалених — у описі PR).
- [ ] Комміт.

### Task 5: SPEC.MD, traceability, документація

**Files:**
- Modify: `SPEC.MD` (вилучити блок «R-28: перевірка впливу редагування книги» — 17 вимог; DATA-010 / DATA-010-S02: кнопка в меню твору, без відмови за `impact`; IMPACT-UI посилання; MODEL-002 перелік без `impact_*`/`review_part`; абзац політики `providers/policy.py`; згадки в інших розділах — `grep -n "impact\|review3\|review4\|Перевірка книги" SPEC.MD`); новий абзац «Вилучено R-28 (R-44, PR 1)» у відомих змінах зі сумісністю
- Modify: `docs/verification/traceability.json` (вилучити сценарії R-28; DATA-010-S02 — нові тести)
- Modify: сайт `docs/site/{uk,en}/` сторінки зі «Перевірка книги» / «Book check» (`grep -rln "Перевірка книги\|Book check" docs/site`), `README.md`/`PRODUCT.md` за потреби, скіли в `integrations/` зі згадками
- [ ] `python scripts/check_docs.py` OK; `python scripts/check_site.py --rehash <slug>` для кожної парної зміни.
- [ ] Комміт.

---

Після Task 5: повний гейт, ruff F821/F401 на змінених файлах, перехресне рецензування гілки, `verify.py`, PR на `main`.
