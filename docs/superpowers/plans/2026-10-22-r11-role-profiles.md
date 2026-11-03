# R-11 Role Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Виконання в поточному чаті, у поточній гілці за рішенням власника.

**Goal:** Іменований переносимий комплект чотирьох ролей з необов’язковим Evaluator.

**Architecture:** Строгий переносимий документ і незмінні глобальні версії в app_settings; застосування через атомарну storage-операцію. Промпти створюються заново у цільовому творі; живого зв’язку з профілем немає.

**Tech Stack:** Python/Pydantic/SQLite/FastAPI, чинні ES modules, pytest.

**Spec:** docs/specs/changes/R-11-role-profiles.md.

## Global Constraints

- Чотири ролі planner/writer/editor/memory; Evaluator необов’язковий.
- JSON максимум 2 MiB, промпт максимум 100000 символів, name 1–100 непорожніх символів.
- Без нових залежностей, міграції SQL або платних викликів.
- Активна спроба незмінна; нові налаштування — з наступного етапу.

## Review Focus

- Невідома роль/секретне поле/надмірний JSON — відхилити без echo значення.
- Власний промпт із чужого твору — новий локальний UUID і чинний контракт.
- Конфлікт profile/story revision — жодної часткової публікації.
- Evaluator без локального допуску — не імпортувати calibrated=true; блокування твору незмінне.
- Несвіжий UI preview або незбережені форми — явне попередження, без тихої втрати правок.

## Task 1: переносимий документ, версії, копіювання

Files: нові `src/storygen/role_profiles.py`, `src/storygen/storage/role_profile_store.py`; зміни `storage/settings_store.py`, `storage/repository.py`, `evaluation/story_adapter.py`; тести `tests/authoring/test_role_profiles.py`.

Interfaces: `capture_profile(repo,story_id,name,expected_revision,include_evaluator=False,profile_id=None,expected_version=None)`, `preview_profile(repo,story_id,profile_id,version,expected_revision)`, `apply_profile(...)`; Repository.role_profiles(action, **data). ProfileDocument з roles і portable prompts.

- [x] RED: capture→apply створює власні prompt refs, зміна v2 не переписує твори; story/profile CAS; optional Evaluator; invalid contract/JSON/calibration; round-trip та rollback.
- [x] Реалізувати строгі схеми, capture, safe parse/export; storage list/read/save/apply та повторну валідацію під транзакцією. Виділити спільний writer ролей у helper, перевірку Evaluator — у функцію без запису.
- [x] GREEN: `python -m pytest tests/authoring/test_role_profiles.py -q`.

## Task 2: HTTP і UI

Files: нові `web/routes_role_profiles.py`, `web/static/role-profiles.js`; зміни `web/app.py`, `web/templates/settings.html`; тести `tests/web/test_role_profiles_api.py`.

- [x] RED: HTTP capture/preview/apply/export/import; некоректний JSON без секретного echo, CAS 409, рольові значення відображаються текстом.
- [x] Реалізувати endpoint-и зі специфікації та панель із reset preview при зміні вибору, disabled apply до preview, перевіркою незбережених форм.
- [x] GREEN: цільові тести й синтаксис JS, перевірка поведінки UI на ізольованих даних.

## Task 3: контракт і приймання

- [x] Оновити SPEC.MD, матрицю Scenario→tests, інструкцію користувача й журнал; відзначити R-11 у беклозі.
- [x] Саморев’ю: секрети, CAS, атомарність, prompt ownership, калібрування, blocked Evaluator, незбережені форми.
- [x] `python scripts/check_docs.py`, `python scripts/verify.py`; проаналізувати фактичні результати.
- [x] Окремі локальні коміти попередньої діагностики й R-11; без push/PR або платних викликів.

## Журнал

22.10.2026: досліджено settings_store, prompt_contracts, Evaluator settings та UI; власник обрав комплект. Перенесення авторського стилю не входить у межі R-11.

22.10.2026: GREEN домен+HTTP+сумісність — 20 passed; UI ES module — 1 passed. Capture/apply CAS, rollback, власні prompt UUID, optional Evaluator, refusal block, imported pause без калібрування перевірено на синтетичних даних. Незалежний reviewer r11_review не виявив actionable дефектів; його HTTP-тест перерваний через sandbox, незалежного повного прогону він не заявляв. Основний агент виконав HTTP-тести з дозволом локального транспорту.

Браузер: initial disabled, вибір→preview→enabled, dirty→reset перевірено; screenshot artifacts/r11-browser/profile-preview.png. Підтвердження native confirm заблокувало керування тестовою вкладкою; повний browser apply/reload не заявляється. Він перевірений окремо HTTP та ES module тестами (cancel, CAS, apply/reload). Повний responsive/клавіатурний сценарій лишається ручною процедурою. Тимчасовий сервер зупинено; робочі дані не відкривалися.

Ruling: переносимий Evaluator є candidate без автоматичного відновлення калібрування; pause_on_failure явно блокується, report/off переносяться. Це зберігає повноваження калібрування поза імпортом. Власний codex_command не переноситься через ризик виконання імпортованої команди.

Повний прогін: 775 passed, 1 skipped, exit 0, source_changed_during_run=false; artifacts/verification-izmkgd5w/result.json. Документація узгоджена check_docs. Попереднє виправлення empty-stop збережено окремо: 7115478. R-11 підготовлено до окремого локального коміту, без push.
