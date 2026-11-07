# Згортання довгих списків сцен

Дата06.11.2026. Погоджений запит власника: обидва екрани, редактор і результати перевірки. Уточнення:60+ сцен відсувають імпорт персонажів униз; список має згортатися як сусідні details.

Редактор: один native details «Сцени» з поточною кількістю, open за замовчуванням. Усередині наявні scene-list і mobile select; importer залишається наступним sibling поза details. Натискання/клавіатурне згортання не перемикає сцену/матеріал, не зберігає/стирає dirty текст і не надсилає запити. Refresh і UA/EN зберігають стан, reload відкриває початково.

Результати: наявний заголовок «Останні результати» стає summary native details навколо всіх report articles. Початково відкрито, стан зберігається при locale/refresh; за відсутності reports порожнього disclosure немає. Поточний author-review/checkpoint і blockers не ховаються цим списком історії, вкладені цитати/докази зберігають власне керування.

Малий UI пакет inline поверх select-all: RED browser65 scenes/import accessibility/dirty+selection+UA/EN та reports toggle → мінімальна template/DOM зміна, штатні styles → SPEC/traceability/UA/EN/screenshots → спільний web/browser gate та один cross-review PR. Нового API/storage/localStorage немає.


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
