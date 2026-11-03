# R-07: план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans.

**Goal:** Відтворювана оцінка повного API body з явним допуском профілів.
**Architecture:** Нейтральний token_budget, спільні request builders,
предметний storage, інтеграція generation/evaluation.
**Tech Stack:** Python, Pydantic, SQLite app_settings; без нових залежностей.
**Spec:** docs/specs/changes/R-07-token-budget.md.

## Global Constraints
- Без нових платних викликів, clipping, автоматичної активації.
- 40 distinct, train30/holdout10, запас20%+256, діапазон4×, expiry7days.
- SQLite2; legacy без body не стає каліброваною вибіркою.
- SPEC.MD у тому самому коміті з архітектурним кодом.

## Review Focus
- Підміна schema/options між preflight і transport.
- Повторні або відсутні usage та недостовірна provenance.
- Малі контексти й холодний старт без профілю.
- Нове спостереження деактивує profile без пошкодження готової прози.
- Витік приватного body через CLI list/report.

### Task 1: Чистий estimator і профіль
- [x] RED: tests/token_budget/test_profiles.py (fallback, split, classes,
  duplicates, insufficient/range, drift/expiry).
- [x] GREEN: token_budget/core.py; функції measure, estimate, build_profile.
- [x] Перевірити цільові тести; зберегти результати в цьому плані.

### Task 2: Exact requests і runtime
- [x] RED: tests/providers/test_request_budget.py: body parity/schema;
  generation/evaluation integration і legacy.
- [x] GREEN: providers/requests.py; ContextBundle.api_request/token_estimate;
  streaming та evaluation gateway використовують однаковий builder.
- [x] Підключити оцінку та observation capture без знищення результату.

### Task 3: Storage, ручна активація й документація
- [x] RED: storage/service manual activation/reopen/drift; CLI/snapshot
  regression coverage додано після основного GREEN без штучного RED.
- [x] GREEN: repository token API, token_budget/service.py та cli.py,
  entrypoint storygen-tokens; інструкція керування без авторського тексту.
- [x] SPEC.MD + цільові перевірки + повний suite.
- [x] Незалежне read-only review, виправлення Important, фінальна перевірка.

Початковий стан: специфікація підготовлена після обраного власником manual
activation. Чинна вказівка — виконати план у цьому чаті без додаткового
підтвердження. Пріоритет — 1→2→3; request identity є спільним інтерфейсом.

Ruling: первісний запас4096 поверх повного UTF-8 body блокував навіть1304
символи короткої сцени (6458>6144), відтворено accepted_resume. Замість
довільного великого overhead застосовано256 поверх уже врахованої схеми й
байтової верхньої евристики. Це не гарантія невідомих server-side tokens;
прогноз лишається heuristic. Контекст моделей користувача не збільшується.

## Докази виконання

- Початковий RED: відсутні token_budget/service/request builder; GREEN чистого
  estimator7, потім service/transport і повний пакет135 цільових тестів.
- Виправлено fixture test_request_budget: EvaluationRequest потребує explicit
  temperature=None; production contract не послаблено.
- test_token_cli має унікальну назву через pytest basename collision з
  evaluation/test_cli. Видалення кешів або зміни import mode не потрібні.
- Незалежне read-only review r07_review: Important — frozen profile у
  наступному evaluation window після drift. Regression RED відтворив
  empirical/empirical; GREEN підтвердив empirical/fallback і metadata parity.
  Minor — недостатній числовий звіт запасу: додано holdout min/max surplus,
  multiplier1.20 і256additive. Невиправлених findings немає.
- Reviewer не перевіряв реальні tokenizer/provider guarantees; це збережене
  обмеження, а не привід оголосити евристику точним tokenizer.
- Два ранні sandbox full runs зупинено: TestClient зависав у внутрішньому
  asyncio socketpair. Faulthandler локалізував socket.accept у conftest.
  Завершальний прогін з loopback доступом: **468 passed, 1 skipped, 77.41s**;
  skip — чинні права Windows symlink. Лог artifacts/r07-verified.log.
- Перевірено збереження прози при telemetry storage failure, CLI privacy,
  snapshot і cold backup/restore. Живі налаштування твору не змінювалися;
  платних модельних викликів немає. Новий профіль не активовано.
- Wheel зібрано; zip-перевірка підтвердила новий пакет token_budget,
  спільний request builder і entrypoint storygen-tokens. Інсталяція wheel
  в окреме середовище не виконувалася.
