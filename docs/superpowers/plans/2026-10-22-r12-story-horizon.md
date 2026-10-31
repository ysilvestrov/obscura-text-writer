# R-12 Story Horizon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Виконання в цьому чаті й поточній гілці, як погодив власник.

**Goal:** Явний горизонт планів для кожної ролі та необов’язковий спільний орієнтир фіналу.

**Architecture:** Чиста проєкція планів спільна для context builder і dependency snapshots. RoleSettings зберігає all/next_n/current та N, StyleProfile — ending_goal; snapshot відстежує лише вибрані плани та фактично використане обрамлення.

**Tech Stack:** Python/Pydantic, SQLite2, чинні FastAPI/ES modules і pytest.

**Spec:** docs/specs/changes/R-12-story-horizon.md.

## Global Constraints

- Типово all; future_plan_count 0–1000 (типово 2); ending_goal до 12000 символів, типово порожній.
- Пам’ять/patches/diff/prepare не отримують нового майбутнього контексту.
- Без SQL-міграції, нових бібліотек, платних API чи автоматичного summary.
- Авторські baseline, frozen attempts, token overflow та refusal/budget guards зберігаються.

## Review Focus

- Плани виключено з тексту, але лишилися selectors — тест далекої правки й точних refs.
- Приховані сцени переставлено або додано сцену — window не реагує на перше, scene_count реагує на друге.
- Brief містить далекий план — чесне попередження, транзитивна stale зберігається.
- N=0, кінець твору, кошик — жодної зайвої сцени чи IndexError.
- ending_goal випадково потрапив у memory/diff чи R-11 — перевірка ізоляції та round-trip без авторського фіналу.

## Task 1: проєкція та залежності

Files: новий src/storygen/story_horizon.py; providers/models.py, generation/models.py, generation/context.py, dependency_models.py, storage/snapshots.py. Тести: tests/generation/test_story_horizon.py.

Interfaces: selected_plan_scenes(scenes, scene, settings) → list[Scene]; horizon_future_count(settings) → int|None. Selector narrative_window/future_count та story.scene_count.

- [x] RED: literal fixtures 7/15 сцен для all/next_n/current, N=0/кінець/кошик; точні refs, included/excluded edits, reorder/count та snapshot legacy.
- [x] Реалізувати схему/проєкцію, роздільний орієнтир і warnings; оновити selector evaluation без зміни author baseline.
- [x] GREEN: python -m pytest tests/generation/test_story_horizon.py tests/storage/test_dependency_snapshots.py tests/generation/test_context.py -q.

## Task 2: налаштування, комплекти та UI

Files: web/static/settings.js, новий web/static/horizon-controls.js, templates/settings.html; тести tests/web/test_story_horizon_api.py та JS поведінки horizon-controls; доповнити R-11 tests.

- [x] RED: HTTP role/style round-trip, стара конфігурація all, R-11 з горизонтом без ending_goal; перемикання редактора prose/patches/diff не активує зайвий контекст.
- [x] Реалізувати select/N, disable для непридатних режимів, підказки та ending_goal у чинній формі стилю.
- [x] GREEN: цільові HTTP/JS тести без зовнішньої мережі.

## Task 3: приймання та документація

- [x] SPEC і матриця з конкретними Scenario→test, docs/story-horizon.md, беклог/журнал, окреме збереження планової R-19 правки.
- [x] Самоперевірка й незалежне рев’ю фактичного контексту/refs/order/frozen compatibility.
- [x] check_docs.py, verify.py; фактичні результати в STATUS, без твердження про доведену літературну якість.
- [x] Окремий локальний коміт R-12 із SPEC, без push.

## Журнал

22.10.2026: власник обрав per-role та optional shared ending_goal із warning. Ruling: N=0 еквівалентний current для добору планів і попередження; загальний scene_count лишається залежністю через видимий заголовок n/total. Збереження широкого авторського baseline — захист уже погодженого ручного прийняття.

22.10.2026: RED — відсутня проєкція/поля, далі відсутні ending_goal у формі та JS control. GREEN: core context/snapshots 22 passed; HTTP/JS/R-11 19 passed. Додані prefix-memory, кошик і frozen/legacy тести. Незалежний reviewer знайшов два P2: fsck помилково вимагав story owner для narrative_window; raw legacy snapshot при copyedit acceptance порівнювався з новою нормалізованою моделлю. Обидва відтворено RED, виправлено та перевірено: core/copyedit/sentence_groups/fsck 69 passed. Reviewer незалежно підтвердив виправлення (3 passed), важливих відкритих findings немає.

Браузер на синтетичному каталозі: ending_goal і next_n=0 збереглися після reload; editor diff вимикає horizon, memory не має horizon controls. Screenshot artifacts/r12-browser/horizon-settings.png. Робочий сервер/дані не змінювалися, платних викликів немає. Планова задача R-19 окремо закомічена як 8d06de1; службові файли дизайну не регенерувалися.

Повний прогін R-12: 798 passed, 1 skipped, exit 0, source_changed_during_run=false; artifacts/verification-k4ikmirc/result.json. UI detector: одне advisory про наявне посилання «До твору»/rgb(0,0,0), нових кольорів немає; синхронізація sidecar лишається окремою R-19. Тимчасову вкладку закрито, сервер зупинено.
