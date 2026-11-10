# План: звужений каталог етапу memory (#60, PR 2)

Дизайн: `docs/superpowers/specs/2026-11/2026-11-09-memory-context-selection-design.md`, розділ «Звужений каталог етапу memory (PR 2)». Ядро (PR 1, #82) злито; цей план стоїть на ньому.

## Рішення в межах плану

1. **Один набір `keep` для каталогу й меж.** `memory_catalog_v4(..., keep=None)` і `schema_bounds_v4(..., keep=None)` фільтрують лише `mutable` стани (і `immutable` у каталозі) тим самим набором claim ID. Ядро (слоти відстежуваних) і лінії не звужуються. Без `keep` обидві функції байтово ті самі (І1).
2. **Звуження — одна спроба, без двійкового пошуку.** Склад звуженого каталогу задано дизайном (присутні, загальні, до 20 станів за прозою, факти про учасників, хронологія 20 сцен), а не бюджетом. Не вміщається звужений → `ContextOverflow`, як і раніше.
3. **Підключення.** `make_context(..., memory_narrower=None)`: якщо повний запит не проходить ту саму оцінку токенів і `max_input_chars`, виклик `memory_narrower()` повертає нові секції, оновлення фрагментів (`memory_schema_bounds`), метрики й попередження; запит перевимірюється один раз. Перевірка `check_v4` уже відхиляє update/retire невідомого ID (`target_unknown`), тож межі = каталог (І5) без змін у парсері.
4. **Метрики.** `projection_version='memory-catalog-v4-narrow'`, `catalog_chars` звуженого, `narrow={hidden, mutable_shown, immutable_shown}`; попередження «Каталог пам’яті звужено: N записів не показано моделі».
5. **Бенчмарк.** `SceneInput.catalog_v4` (журнал, склад, відстежувані, імена, проза, номери сцен) лише для реальних даних; `catalog_full_v4`/`catalog_narrow_v4` у звіті під окремим ключем `memory_stage_v4` (наявний `memory_stage` без змін). Ціль доступна, якщо її claim є в ядрі, лініях або показаних mutable.

## Задачі

1. `narrow_catalog(...)` у `memory/selection.py` і `keep` у `memory_catalog_v4`/`schema_bounds_v4`; тести `tests/memory/test_catalog_narrow.py` (склад, FTS-ліміт 20, ядро й лінії не звужуються, без `keep` байтово те саме, межі = каталог).
2. `memory_narrower` у `make_context` і `build_context`; тести `tests/generation/test_memory_stage_narrow.py` (без переповнення без змін, звуження при малому ліміті, межі в фрагменті, попередження й метрики, `ContextOverflow` якщо не вміщається й звужений, update поза каталогом відхиляється).
3. Бенчмарк `catalog_narrow_v4`, тести `tests/retrieval_bench/test_catalog_v4.py`; замір на свіжій копії даних (критерій: звужений v4 не втрачає цілей проти повного v4).
4. SPEC MEMORY-SELECT S07, traceability, `docs/memory-view.md` (UA/EN), журнал виконання, verify.
