# Локації: інтерфейс і документація (#67, PR 2) — план

**Мета:** автор бачить картки локацій твору, зливає схожі, розділяє, відхиляє підказки й пише опис; таблиця пам'яті показує локації записів; сайт uk/en пояснює рядок «Локація:» і панель.

**Спека:** `docs/superpowers/specs/2026-11/2026-11-22-memory-locations-design.md` (PR 2). Ядро — PR #257.

## Глобальні обмеження

- Кожна зміна — CAS за ревізією твору (`RevisionConflict` → 409), ревізія твору +1; без явного COMMIT.
- Опис ≤ 2000 знаків (`DESCRIPTION_LIMIT`), обрізання пробілів.
- Злиття не змінює текстів планів; застарілість — лише через селектори знімка (PR 1).
- Сцени в кошику в переліку сцен картки не показуються.
- Тексти uk/en у `i18n.json`; знімки сайту — нейтральний приклад.

## Фокус рев'ю

- Подвійне злиття ланцюжком (А→Б, Б→В): картка показує кінцеву ціль, «Розділити» Б не ламає А.
- Злиття в картку, що сама злита: показ і підказки використовують канонічну ціль.
- Конфлікт ревізії під час редагування опису: введений текст лишається.
- Твір без локацій: панель показує порожній стан, а не помилку.
- Відхилена пара більше не пропонується, навіть після розділення.

## T1. API локацій

- `storage/locations.py`: `locations_view(repo, story_id) -> dict` (`story_revision`, `locations: [{id, path, parent_id, merged_into, target_path, description, scenes: [{id, position, title}]}]`, `suggestions: [{a, b, a_path, b_path}]`) і `change_locations(repo, story_id, expected_revision, action)`: `BEGIN IMMEDIATE`, перевірка ревізії, дія, ревізія +1.
- `web/routes_locations.py`: `GET /api/stories/{id}/locations`, `POST …/locations/{lid}/merge` (`into`), `POST …/locations/{lid}/split`, `POST …/locations/dismiss` (`a`, `b`), `PUT …/locations/{lid}` (`description`); тіла з `expected_revision`; відповідь — свіжий `locations_view`.
- Тести `tests/web/test_locations_api.py`: перелік зі сценами й підказками; злиття/розділення/відхилення/опис змінюють ревізію; стара ревізія → 409 і без змін; невідома картка → 4xx; опис > 2000 → 422; злиття в себе чи цикл → 4xx; сцена в кошику не в переліку.

## T2. Локації в таблиці пам'яті

- `memory/forwarding.memory_view_from_view`: рядок має `locations` — шляхи канонічних карток запису (порожній список, якщо немає).
- `memory-table.js`: під текстом рядка — «Локації: …» (`memory.locations`), фільтр пошуку враховує шляхи.
- Тести: API рядка (pytest), node-тест форматування.

## T3. Панель «Локації»

- `static/locations.js` (чисті функції рядків: картки верхнього рівня й вкладені з відступом, злиті під ціллю, підказки) і `static/locations-panel.js` (секція `#story-locations` у `#memory-view`, як підсумки хронології): опис з кнопкою «Зберегти опис» і лічильником N / 2000; «Злити в…» (вибір цілі), «Розділити», підказки «Схоже на…» з «Злити» / «Не схожі».
- `story.html` підключає модуль; тексти `locations.*` uk/en.
- Тести: node (`tests/web/js/locations.mjs`), сторінка й каталог (`tests/web/test_locations_ui.py`), браузер (`tests/web/browser/locations.spec.mjs` з фікстурою `/test-locations`).

## T4. Специфікація й сайт

- SPEC.MD `MEMORY-LOCATIONS`: API, панель, таблиця; прибрати «PR 2» з відомих обмежень; новий Scenario S07 (API й панель); traceability.
- Сайт: `memory.md` і `first-story.md` uk/en — рядок «Локація:», панель, опис; знімок панелі з нейтральним прикладом; `check_site.py --rehash`.
- Журнал виконання, `verify.py`, PR з «Closes #67».
