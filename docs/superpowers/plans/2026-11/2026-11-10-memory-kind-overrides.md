# План: позначки типу запису пам'яті й рядок відбору (#60, PR 3 із 3)

Дизайн: `docs/superpowers/specs/2026-11/2026-11-09-memory-context-selection-design.md`, розділ «Перевизначення типу (PR 3)», інваріант І8. Стоїть на ядрі відбору (#82), звуженому каталозі (#83) і виправленнях крос-рев'ю (#86).

## Обсяг

1. **Домен.** `Story.memory_kind_overrides: dict[claim_id, 'core'|'atmosphere']` у payload твору, не більше 10 000 ключів, без SQL-міграції; старі payload читаються з порожнім словником.
2. **Збереження.** `storage/memory_kinds.py::update_memory_kind(repo, story_id, claim_id, kind, expected_revision)`:
   - `BEGIN IMMEDIATE`, CAS на ревізію твору, `kind=None` знімає позначку.
   - Запис шукається в журналах пам'яті сцен твору, від останньої сцени до першої; не знайдено — `ValueError`. Для слота ядра позначка заборонена, бо слот завжди в ядрі.
   - Без змін — без нової ревізії. Застарілість не розсилається активно, її рахує селектор (п. 4), як для `memory_forwarding`.
3. **API.** `PUT /api/stories/{id}/memory-kind` `{claim_id, kind | null, expected_revision}` → твір. Помилки: конфлікт ревізії 409, невідомий запис або слот 400.
4. **Застарілість (І8).** `memory/kinds.py::kind_overrides(view, scene_id)` рахує позначки для записів, активних у журналі попередньої сцени (з того самого джерела, що `projection_policy`).
   - `build_context` передає їх у `SelectionInput.kinds`.
   - `make_context` додає селектор `scene/memory_kind_overrides` зі значенням `kind_overrides` лише тоді, коли запит зібрано з відбором.
   - `selector_value` уміє його рахувати; поле додано до дозволених полів сцени в `dependency_models`.
   - Етап memory і версії без відбору селектора не мають.
5. **Таблиця пам'яті.** У рядках `memory-view` з'являються `kind` (позначка або `null`) і `slot`, а у відповіді — `story_revision`. Стовпець «Тип» стоїть останнім, щоб не зсувати наявні: перемикач «Авто / Ядро / Атмосфера» зберігається одразу, окремо від кнопки «Зберегти» для вибору пересилання. Для слота показано «Ядро» без перемикача. Конфлікт ревізії повідомляє й перезавантажує таблицю.
6. **Статистика сцени.**
   - `context.memory_selection` = `{selected, total, dropped, layers, dropped_layers}` з `memory_metrics.selection` для brief/draft/edit.
   - Для етапу memory зі звуженим каталогом — `context.memory_narrow` з `narrow`.
   - У UI з'являється рядок «Відбір пам'яті: вибрано X з Y, відкинуто Z (шари …)» або «Каталог пам'яті звужено: не показано N».
7. **SPEC.MD**: MEMORY-SELECT S08, технічний опис, інваріант І8, Source map; traceability S08 (pytest, JS-тест таблиці, Playwright).
8. **Документація**: `docs/memory-view.md`, `docs/en/memory-view.md` (стовпець «Тип», знімок `docs/images/memory-kind-{desktop,mobile}.png` з нейтральним прикладом), `docs/scene-statistics.md`, `docs/en/scene-statistics.md` (рядок відбору).

## Задачі

1. Домен, збереження, API, тести CAS і валідації (`tests/web/test_memory_kind_api.py`).
2. `kind_overrides`, передача в відбір, селектор лише з відбором, тести застарілості (`tests/generation/test_memory_kind_staleness.py`).
3. `memory-view` і статистика на сервері, тести.
4. UI: стовпець «Тип», рядок статистики, i18n UA/EN, JS-тест `tests/web/js/memory-table.mjs`, Playwright `tests/web/browser/memory-kind.spec.mjs` зі знімками.
5. SPEC, traceability, документація, журнал, verify.

## Критерій приймання

- Позначка змінює шар запису лише в запиті з відбором. Без відбору запит байт у байт той самий (І1).
- Зміна позначки робить застарілою версію, зібрану з відбором, у якої цей запис був активним до сцени. Версія без відбору від позначки не залежить, як і версія, де запису ще не було.
- Слот не можна позначити; конфлікт ревізії не губить чужу зміну.
