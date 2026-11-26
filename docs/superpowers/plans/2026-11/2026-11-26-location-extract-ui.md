# Місця сцен у пошуку — інтерфейс (R-51, специфікація 2, PR 2) — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** автор бачить і вибирає місця сцен у пропозиції пошуку на сторінці «Персонажі», а помилково прийняте місце моделі прибирає зі сцени в панелі «Локації».

**Architecture:** група «Місця сцен» у `static/character-extract.js` поверх `AcceptRequest.locations` з PR 1; дія «прибрати місце зі сцени» — новий `POST …/locations/{lid}/remove-from-scene` через `change_locations` (CAS на ревізію твору), запис у `storage/locations.py`; панель показує кнопку лише для сцен з `location_source='model'`.

**Tech Stack:** Python 3.12, FastAPI, ES modules без збирача, Playwright.

**Spec:** [2026-11-26-location-extract-design.md](../../specs/2026-11/2026-11-26-location-extract-design.md) (§5, §6; питання 1 власника — дія входить у PR 2; поправка 2 цього PR описує контракт дії).

## Global Constraints

- Тексти: розділ «Пошук персонажів і місць у прозі», кнопка «Знайти персонажів і місця у прозі…» (діалог — «Знайти персонажів і місця у прозі»); en — «Find characters and places in the prose…».
- Група «Місця сцен» — після «Склад сцен»; рядок сцени, прапорці місць з шляхом, позначка «нова» для `new: true`, `suggested: false` — невибране; «вибрати все» / «зняти все»; `dry_run` як досі.
- Стара пропозиція без `locations` показується й приймається (`proposal.locations||[]`).
- Сцена без вибраного місця в тіло прийняття не йде.
- Прибрати можна лише місце сцени з `location_source='model'`; сцена без місць повертається до `plan` (payload знову читає старіша версія).
- Усі зміни панелі — CAS на ревізію твору (`change_locations`); приватні методи репозиторію — лише в `storage/`.
- Кожна нова відмова сервера має uk/en у `i18n.json`.

## Review Focus

1. Злита картка: сцена тримає ID злитої картки, автор прибирає ціль — мають зникнути всі ID з тією самою канонічною карткою.
2. Сцена з місцем у плані (`plan`) — кнопки немає, сервер відмовляє 400 без змін.
3. Застаріла ревізія твору — 409, сцена не змінена.
4. Пропозиція лише з місцями (без карток і складу) — не «нічого не запропонував».
5. Пропущене місце в підсумку прийняття показує назву сцени, а не `location`.

---

### Task 1: дія «прибрати місце зі сцени» (сервер)

**Files:** `src/storygen/storage/locations.py`, `src/storygen/web/routes_locations.py`, `src/storygen/web/static/i18n.json`; тест `tests/web/test_locations_api.py`, `tests/web/test_locations_ui.py`.

**Interfaces:**
- Produces: `store.remove_scene_place(repo, db, story_id, location_id, scene_id) -> None` (на транзакції `change_locations`; ревізію твору зберігає `change_locations`); `POST /api/stories/{id}/locations/{lid}/remove-from-scene {scene_id, expected_revision}` → як інші зміни: свіжий перелік і `dependent_scene_ids`; `locations_view` — `scenes[{id, position, title, source}]`, `source` — `plan|model`.
- Відмови (`ValueError`, 400): «Невідома локація», «Невідома сцена» (немає, кошик, інший твір), «Місце сцени з плану: змініть рядок «Локація:»» (`plan`), «Сцена не має цього місця».

- [ ] Тести: прибирання місця моделі (ID злитої картки теж зникає, решта лишається, `source` лишається `model`, ревізії сцени й твору +1); останнє місце → `location_ids == []`, `location_source == 'plan'`, у payload поля немає; кожна відмова — 400 без змін ревізій; застаріла ревізія — 409; `scenes[].source` у переліку. Існуючі порівняння `scenes` оновити.
- [ ] Реалізація: як `apply_places_in_transaction` — `stale_scene_material`, `revision += 1`, `_save_scene`; без `_touch_story`.
- [ ] uk/en ключі `locations.error.unknown_scene`, `locations.error.plan_place`, `locations.error.not_in_scene`; `test_server_messages_match_the_catalog` перевіряє їх.

### Task 2: кнопка в панелі «Локації»

**Files:** `static/locations.js`, `static/locations-panel.js`, `i18n.json`; тести `tests/web/js/locations.mjs`, `tests/web/browser/locations.spec.mjs`, фікстура `/test-locations` у `tests/web/browser/server.py`.

- [ ] `locationRows` дає `modelScenes:[{id,label}]` (лише незлита картка, сцени з `source==='model'`).
- [ ] Панель: під рядком сцен кнопка «Прибрати з «{сцена}»» для кожної; підтвердження «Прибрати «{місце}» зі сцени «{сцена}»? Повернути його можна новим пошуком або рядком «Локація:» плану.»; повідомлення «Місце прибрано зі сцени»; потім `offerInvalidation` для цієї картки (як опис і злиття).
- [ ] Фікстура `/test-locations?model=true`: третя сцена з місцем моделі; Playwright: кнопка лише в неї, прибирання після підтвердження, сцена зникає з картки.

### Task 3: група «Місця сцен» і нова назва

**Files:** `static/character-extract.js`, `templates/characters.html` (без змін розмітки, лише ключі), `i18n.json`; тести `tests/web/js/character_extract.mjs`, `tests/web/test_character_extract_ui.py`, `tests/web/browser/character-extract.spec.mjs`, `tests/web/browser/memory-build.spec.mjs`, фікстура `/test-character-extract`.

- [ ] `defaultSelection`: `places` — `Set` ключів `` `${scene_id}\n${path}` `` для `suggested`; `acceptBody`: `locations:[{scene_id, places:[path…]}]` у порядку пропозиції, без сцен без вибраних місць.
- [ ] `renderProposal`: група `character_extract.ui.places` («Місця сцен ({p0})») після складу; рядок — назва сцени й прапорці місць, «нова» — `character_extract.ui.place_new`; `empty` враховує місця; `itemLabel('location')` — назва сцени.
- [ ] Перейменування `character_extract.ui.heading/open/title`, `memory_build.ui.find_characters` uk/en; оновити специфікації Playwright і `manual.md`.
- [ ] Фікстура `?proposal=true` має місця: сцена 1 — «Пірс» (наявна? ні — нова) і незгадане «Маяк / ліхтарна» (`suggested:false`); Playwright: група, позначка «нова», невибране місце, прийняття пише місце сцени.

### Task 4: SPEC, сайт, знімок

- [ ] SPEC: CHARACTER-EXTRACT-S14 (група), MEMORY-LOCATIONS-S08 (прибирання), технічний опис API й панелі, хто пише `Scene.location_ids`; прибрати обмеження «без дії прибрати» з чинного тексту; traceability.
- [ ] Поправка 2 у дизайні: контракт дії, `source` у переліку.
- [ ] Сайт uk/en: `characters` (місця в пошуку), `memory` (порада шукати місця до побудови пам'яті; панель «Локації» — прибирання), `manuscript-import`; `check_site.py --rehash`.
- [ ] Знімок: seed `seed_character_proposal` з місцями (тест seed приймає місця з `dry_run`), перезняти `character-proposal-desktop.png` uk/en.

### Task 5: перевірка

- [ ] `check_docs.py`; Playwright `character-extract`, `locations`, `memory-build` (desktop і mobile); `verify.py` з нового `C:/tmp/r51luv`; фінальне рев'ю; cross-review.
