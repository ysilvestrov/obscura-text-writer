# Структуровані proposed_changes у модельному brief

Прямий запит власника06.11: proposed_changes містить видимий текст, проте схема каже «Потрібен текст». Read-only діагностика підтвердила список об’єктів із рівно scene_number:int та change:str у prompt_json. Приватні значення не копіюються в тести/документацію й не передаються reviewer.

Модельна wire-сумісність до незмінного WritersBrief: лише у brief кожний об’єкт із рівно двома ключами scene_number (strict positive int, не bool) і change (непорожній str) перетворюється на рядок «Сцена N: {change}». Сам текст change, порядок і дублікати не обрізаються/не переписуються; номер зберігається. Рядки та інші поля незмінні. Невідомі/неповні об’єкти, додаткові ключі, вкладені значення, null/числа й schema/evidence/CAS помилки не виправляються. Domain/manual JSON далі потребує list[str]; prepare не нормалізується.

Після успішної strict схеми normalized JSON стає candidate version, оригінальний partial лишається дослівним. Непорожні proposed_changes завжди needs_review, без автоматичного head/оновлення планів. Безпечне попередження planner_warnings/run/context_warning UA/EN пояснює перетворення. Старі failed attempts не редагуються, нового inference/retry немає. Provider/prompt/schema/SQL незмінні.

План inline, base382bd9d: RED synthetic mixed-list/raw/manual/unknown schemas → мінімальна нормалізація у planner_output і UA/EN warning → SPEC/traceability/UA+EN instructions → verify.py planner/generation/protocol/web regressions → cross-review/commit/push/PR й idle-server update. Нового продуктового рішення або загального object-to-string coercion немає.


Фінальний gate: **654 passed,0 failures/errors/skipped**,148.50с, source_changed_during_run=false; artifacts/verification-iiov2nhk/result.json, STATUS оновлено verify.py. Усі generation/web/integration перевірки виконано. check_docs пройшов. Новий warning на чинній панелі без зміни layout: UA/EN інструкції актуалізовано, screenshots не потребують заміни. Production raw/failed state/settings не переписано; нових inference немає.
