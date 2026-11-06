# Структуровані proposed_changes у модельному brief

Прямий запит власника06.11: proposed_changes містить видимий текст, проте схема каже «Потрібен текст». Read-only діагностика підтвердила список об’єктів із рівно scene_number:int та change:str у prompt_json. Приватні значення не копіюються в тести/документацію й не передаються reviewer.

Модельна wire-сумісність до незмінного WritersBrief: лише у brief кожний об’єкт із рівно двома ключами scene_number (strict positive int, не bool) і change (непорожній str) перетворюється на рядок «Сцена N: {change}». Сам текст change, порядок і дублікати не обрізаються/не переписуються; номер зберігається. Рядки та інші поля незмінні. Невідомі/неповні об’єкти, додаткові ключі, вкладені значення, null/числа й schema/evidence/CAS помилки не виправляються. Domain/manual JSON далі потребує list[str]; prepare не нормалізується.

Після успішної strict схеми normalized JSON стає candidate version, оригінальний partial лишається дослівним. Непорожні proposed_changes завжди needs_review, без автоматичного head/оновлення планів. Безпечне попередження planner_warnings/run/context_warning UA/EN пояснює перетворення. Старі failed attempts не редагуються, нового inference/retry немає. Provider/prompt/schema/SQL незмінні.

План inline, base382bd9d: RED synthetic mixed-list/raw/manual/unknown schemas → мінімальна нормалізація у planner_output і UA/EN warning → SPEC/traceability/UA+EN instructions → verify.py planner/generation/protocol/web regressions → cross-review/commit/push/PR й idle-server update. Нового продуктового рішення або загального object-to-string coercion немає.


Фінальний gate: **654 passed,0 failures/errors/skipped**,148.50с, source_changed_during_run=false; artifacts/verification-iiov2nhk/result.json, STATUS оновлено verify.py. Усі generation/web/integration перевірки виконано. check_docs пройшов. Новий warning на чинній панелі без зміни layout: UA/EN інструкції актуалізовано, screenshots не потребують заміни. Production raw/failed state/settings не переписано; нових inference немає.


Cross-review: claude/default @ a8ba12e (author: codex) — 5 findings: 4 fixed, 1 rejected

Очищений review heada8ba12e відповідає code4d55d68, base382bd9d. Перед запуском npm0.5.0/integrity й81 package files звірено;643→645 allowlisted files,0 credentials. Приватний raw/user materials/env/research/original.git виключено. Після review production code незмінний;27 посилених synthetic tests passed.

| № | Рішення | Доказ / зміна |
|---|---|---|
| 1 | rejected | Пряме відтворення plain і structured lone-surrogate повертає Pydantic ValidationError/category schema, а не припущений UnicodeEncodeError/publication. Додано4 execute_stage регресії objective/change × string/object: failed/schema, без result/head, original partial незмінний. Production ensure_ascii не змінювався. |
| 2 | fixed | Точні ValidationError type/loc, точний PlannerProtocolError duplicate_key; кожна invalid shape також виконується через stage і перевіряє failed/schema/no result/no head/raw/one call. |
| 3 | fixed | Повні очікувані lists, три plain/fenced/apostrophe випадки для worker reload; точний merged run.warning і context_warning event. |
| 4 | fixed | Прямий manual brief POST400 без створення version/head та prepare parser extra_forbidden; traceability доповнено. |
| 5 | fixed | Після Repository reopen читається одна saved attempt із needs_review, exact planner_warnings і raw bytes для всіх трьох обгорток. |


Post-review gate: **61 passed,0 failures/errors/skipped**, source_changed_during_run=false, artifacts/verification-pzeedox0/result.json. Production parser/catalog код4d55d68 не змінювався після широкого654passed gate; лише посилено tests/traceability/docs. check_docs.py пройшов.
