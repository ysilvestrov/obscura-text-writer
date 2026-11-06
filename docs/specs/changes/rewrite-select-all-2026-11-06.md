# Пакетний вибір змін переписування за коментарями

Дата06.11.2026. Прямий запит власника з активного беклогу; початок найближчих задач погоджено. Це малий UI fix без нового API/storage: одна кнопка «Обрати всі зміни» у rewrite review над grouped changes, чинні secondary styles і UA/EN.

Кнопка позначає всі поточні sentence/format groups, скидає indeterminate і старий assembled preview; жодного POST/generation/save на натискання. Далі автор явно переглядає зібраний текст і застосовує вибір через чинні fingerprint/revision/comments CAS. Dirty/saving/busy/loading/нечинна чи вже вирішена пропозиція блокують дію так само, як окремі choices. Коли все вибрано — disabled. Для порожнього/no-change результату кнопка прихована. Початковий вибір залишається порожнім; окремі checkbox лишаються; copyediting UI не змінюється.

Одна inline задача, base32a04ad: RED browser select-all/no-publication → мінімальний control у change-review.js/i18n → browser partial/all/UA/EN/pending guards і desktop/mobile screenshot → SPEC/traceability та UA/EN інструкції → verify/check_docs/cross-review → commit/push/PR і основна тека. Нових залежностей, міграцій, inference чи платних дій немає.

Наступну задачу згортання сцен власник уточнив для обох екранів: редактора й результатів перевірки книги. Це окремий пакет після цього fix; поведінка згортання списку уточнюється асинхронно.


Реалізовано: initial browser RED2 failures (відсутня кнопка) → GREEN2 passed після виправлення тестового підпису preview. Без API/storage змін. Спільний gate/cross-review після наступного малого пакета згортання, review base32a04ad.


Фінальний спільний UI gate:104 Playwright desktop/mobile passed,2.6m (artifacts/near-term-controls-browser-final.log);185 web/API/Node passed через verify.py, source_changed_during_run=false (artifacts/verification-yi06cfb8/result.json). check_docs пройшов,6 нейтральних screenshots оглянуто. Попередній full browser102 passed/2 failures був помилкою тестового EN locator після UA-switch при screenshot; виправлено stable data attr із окремою перевіркою тексту.


## Спільний cross-review UI controls

Cross-review: claude/default @ 14bcb22 (author: codex) — 7 findings: 6 fixed, 1 rejected

Пакет0.5.0/integrity повторно звірено з npm і81 файлами архіву; independent filtered snapshot629files HEAD2394922→14bcb22, base32a04ad. Без original .git/.env/config/credentials, data/partials, research/progress/diagnostics/STATUS, artifacts/backups/binary images. Claude safe/restricted Read/Grep/Glob; Google/agy не запускався, credential scan0. Report не комітиться. Після перевірки findings посилені browser16 tests passed,26.8s; production UI code не змінювався.


|№|Зауваження|Рішення й доказ|
|---|---|---|
|1|Late preview test не чекав фактичної відповіді.|Fixed: waitForResponse.finished+render frames, exact selection-changed text після late response, apply disabled до свіжого preview.|
|2|Guard завершеної all-пропозиції не доведений.|Fixed: після partial apply1/2 select-all disabled; прямий виклик handler не змінює choices, apply disabled.|
|3|Неоднозначність current report vs author checkpoint.|Fixed: уточнено SPEC/UA/EN: current verdict і його reject action згортаються зі звітом, лише #review-session checkpoint/blockers поза history лишаються. Тест current:true показує reject до/після expand і приховує при collapse.|
|4|History count/empty/blockers не покриті.|Fixed: рівно2 articles; synthetic blocker видимий поза history; empty response прибирає disclosure.|
|5|Немає доказу no-mutations/scene/reload.|Fixed: mutation counter0, точний scene picker ID, importer direct sibling+in viewport, reload повертає open.|
|6|Traceability scope неточний, tests порожні.|Fixed: scope history відповідає report тесту; manual reason пояснює, що check_docs індексує pytest IDs (scripts/check_docs.py:87,139–142), Playwright file/case/command подані у процедурі за дозволеним AGENTS manual contract.|
|7|PASS artifacts/screenshots відсутні в filtered repo.|Rejected: навмисне privacy виключення artifacts/STATUS/binaries. У головній теці185-result і6images існують, hashes зафіксовані в локальному manifest, check_docs перевірив links. Пропуск у reviewer snapshot не є дефектом оригіналу.|
