# R-16b — План модельних пропозицій картки публікації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Поточний чат і гілка, реалізувати без додаткового погодження за рішенням власника.

**Goal:** Одна кнопка «Запропонувати» через планувальника; повний готовий текст, тільки порожні поля, явне Save.

**Architecture:** publication_suggestions — незалежний контракт/джерела/парсер, generation/publication_metadata — контекст/preflight/історія, наявні Run/StageAttempt/accounting, publication_store — остаточна транзакційна перевірка при Save. UI доповнює чинну картку, не змінює прози.

**Tech Stack:** Чинні Python/Pydantic/SQLite/FastAPI/ES modules. Нових залежностей/SQL міграцій немає.

**Spec:** docs/specs/changes/R-16-publication-formats.md, R-16b. Чинний контракт R-16a — SPEC R16-META/COVER.

## Global Constraints

- Planner settings frozen на старті етапу; спеціальний комплектний промпт v1, не промпт структури сцен.
- Увесь ready prose + назви/порядок, без планів/пам’яті/карток персонажів. Переповнення блокує до dispatch/accounting.
- Порожні лише title/annotation/genres/keywords, effective inherited title вважається наявним.
- Інші заповнені та dirty значення ніколи не перезаписуються. Model result не публікується автоматично.
- Помилки refusal/technical/empty/protocol/output limit розрізняються; partial/usage збережені; немає повтору/заміни моделі.
- Старі API/режими, чотири ролі, SQL3 і старі attempts незмінні. Без реальних модельних викликів.

## Review Focus

- Save під BEGIN IMMEDIATE перевіряє саме proposal/owner/fingerprint/джерела і порожність, а не лише HTTP preview.
- Зміна/кошик/порядок/rename/prose replacement після відповіді дає stale; metadata override сам по собі не інвалідовує prose.
- Поки запит триває, автор вводить значення або йде зі сторінки: poll не затирає форму, reload знаходить збережену спробу.
- Duplicate request_id/активний запуск, cancel/restart без тихих повторів; configure planner перед наступним етапом.
- Structured schema бере участь у фактичній оцінці контексту; paid explicit limit/accounting збережені; zero dispatch при overflow/no-targets.

## Task 1: контракт, контекст і збереження

- [x] RED tests/generation/test_publication_metadata.py: маска, повний текст, schema/duplicate keys/refusal, overflow/no gateway, queued idempotency/error/cancel/recovery, freshness.
- [x] publication_suggestions.py, typed suggestions; generation/publication_metadata.py та resources/publication_metadata_uk_v1.txt; generation_request schema; RunRequest.mode, worker/readiness/stages.
- [x] storage.publication_save приймає optional suggestion acceptance (attempt_id/fingerprint/fields), повторює checks у write transaction; tests/storage/test_publication_suggestions.py перевіряють CAS/source race/nonempty/foreign refs.
- [x] GREEN цільових тестів, SQL3/no VersionKind changes.

## Task 2: HTTP та одна кнопка

- [x] RED GET suggestions/preflight, typed acceptance PUT, JS async dirty/refusal/reload/empty-field guards.
- [x] GET /api/stories/{id}/publication/suggestions і /suggestions/readiness; POST /api/runs mode=publication_suggest. UI: одна кнопка, поточний planner/причина disabled, status/cancel/history, explicit review→fill empty→Save; proposal provenance передається серверу.
- [x] Poll збережених run/attempt після reload, without automatic retry; late response/dirty поля збережені, conflicting Save409 не очищує форму.
- [x] GREEN HTTP/JS, browser synthetic з fake gateway, без платних API.

## Task 3: приймання

- [x] SPEC: тільки реалізований R-16b, сценарії/traceability; інструкція/беклог/журнал.
- [x] Impeccable detector один раз, independent whole-package review, важливі findings RED→GREEN.
- [x] Повний verify.py та check_docs.py/diff --check, записи фактичних результатів.
- [x] Локальний коміт без push; далі R-16c FB2/EPUB.

## Журнал

22.10.2026: base49b58c8, clean tree. Ruling: два окремі кроки UI «Запропонувати» й перегляд/застосування результату до форми без автоматичного Save, щоб не приймати model text приховано. Створюється одна модельна операція, не окремі кнопки на поля. Свої typed snapshots metadata не додають selectors до загального dependency graph; стамп прози порівнюється через ту саму SQL transaction, що остаточне Save.

22.10.2026: реалізація контракту/контексту/черги/атомарного Save й UI. Початковий RED: missing module, artifacts/r16b-red.log; цільові генераційні/storage тести27 passed, HTTP4 passed, JS1 passed, providers21 passed. Independent review знайшов: реальна SDK failure category (окремі mock SDK тести RED→GREEN), operation-specific текстові відмови, змішування provenance, apply під час Save; усі виправлені й покриті тестами. Reviewer48 backend passed. Detector запущено один раз:2 findings, успадкований hidden cover без src до upload та чорний fallback Jinja під час статичного аналізу; нових кольорів/стилів не додано, ignore не змінено. Браузерний синтетичний твір7 сцен на окремому data_dir: один fake gateway, review/fill/Save/reload; screenshot artifacts/r16b-publication.png. Тимчасовий сервер8886 зупинено, тестову вкладку закрито. Реальних моделей/робочих даних не торкалися.

Фінальне приймання: scripts/verify.py →856 passed,0 failed/errors,1 skipped за121.69с; artifacts/verification-oq9kf76v/result.json, snapshot_changed=false, base49b58c8. Після прогону змінено лише цей план і журнал приймання; runtime/tests/SPEC не змінювалися. Локальний коміт R-16b, без push.
