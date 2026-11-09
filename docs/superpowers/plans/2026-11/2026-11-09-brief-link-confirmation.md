# План: підтвердження зв'язку «завдання → проза» (#44)

Специфікація: `docs/superpowers/specs/2026-11/2026-11-09-brief-link-confirmation-design.md` (затверджено 2026-11-09). Один PR, виконання inline (executing-plans), кожна задача — окремий коміт із гейтом.

## Задача 1. Метадані й обхід родоводу

- `domain.py`: `BriefLink{brief_version_id, introduced, confirmed_at, by}`, `AuthorLineage{parent_version_id}`; поля `VersionRef.brief_link`, `VersionRef.author_lineage` (за замовчуванням `None`, без SQL-міграції).
- `storage/repository.py::save_version(..., author_lineage=None)`; `generation/dependencies.py::save_manual_prose/save_manual_draft` записують попередню голову матеріалу сцени. `input_refs`, знімок і `dependency_edges` без змін.
- `characters/acquaintance.py`: `lineage_source(view, scene)` — обхід `input_refs` + `author_lineage`, зупинка на `brief_link`; `introduced_of` повертає `link.introduced ∩ cast` або `introduced` brief.
- Тести: `tests/characters/test_brief_link_lineage.py`.

## Задача 2. Репозиторій і API

- `Repository.confirm_brief_link` (CAS: ревізія, голова прози, голова brief; валідація `introduced`).
- `characters/brief_link.py::brief_link_state(view, story, scene)` → `needed/source/checked/next_scene_id/...`.
- `web/routes_brief_link.py`: `GET/POST /api/scenes/{id}/brief-link`; реєстрація в застосунку.
- Тести: `tests/web/test_brief_link_api.py`.

## Задача 3. Панель у робочому просторі

- `web/static/brief-link.js`, підключення в `editor.js` під прозою; i18n UA/EN; захист незбережених позначок; «Наступна непідтверджена сцена».
- Playwright `tests/web/browser/brief-link.spec.mjs`; знімки `docs/images/brief-link-{desktop,mobile}.png` з нейтральним прикладом.

## Задача 4. Специфікація й документація

- SPEC.MD: PLANNER-ACQUAINTANCE (технічний опис, S04, S07–S11, відомі обмеження), Source map; traceability; `docs/verification/manual.md#brief-link`.
- `docs/characters.md`/`docs/en/characters.md` (розділ про знайомства), за потреби `docs/memory-view.md`.
- Журнал виконання, `python scripts/verify.py` → `docs/STATUS.md`.
