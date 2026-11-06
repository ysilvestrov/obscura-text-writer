# Згортання довгих списків сцен

Дата06.11.2026. Погоджений запит власника: обидва екрани, редактор і результати перевірки. Уточнення:60+ сцен відсувають імпорт персонажів униз; список має згортатися як сусідні details.

Редактор: один native details «Сцени» з поточною кількістю, open за замовчуванням. Усередині наявні scene-list і mobile select; importer залишається наступним sibling поза details. Натискання/клавіатурне згортання не перемикає сцену/матеріал, не зберігає/стирає dirty текст і не надсилає запити. Refresh і UA/EN зберігають стан, reload відкриває початково.

Результати: наявний заголовок «Останні результати» стає summary native details навколо всіх report articles. Початково відкрито, стан зберігається при locale/refresh; за відсутності reports порожнього disclosure немає. Поточний author-review/checkpoint і blockers не ховаються цим списком історії, вкладені цитати/докази зберігають власне керування.

Малий UI пакет inline поверх select-all: RED browser65 scenes/import accessibility/dirty+selection+UA/EN та reports toggle → мінімальна template/DOM зміна, штатні styles → SPEC/traceability/UA/EN/screenshots → спільний web/browser gate та один cross-review PR. Нового API/storage/localStorage немає.


Фінальний спільний UI gate:104 Playwright desktop/mobile passed,2.6m (artifacts/near-term-controls-browser-final.log);185 web/API/Node passed через verify.py, source_changed_during_run=false (artifacts/verification-yi06cfb8/result.json). check_docs пройшов,6 нейтральних screenshots оглянуто. Попередній full browser102 passed/2 failures був помилкою тестового EN locator після UA-switch при screenshot; виправлено stable data attr із окремою перевіркою тексту.
