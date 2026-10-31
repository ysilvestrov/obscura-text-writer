# Успішна редактура без змін створює прозу

25.10.2026. Погоджений запитом власника напрям: перший успішний no_changes стандартного editor loop не має залишати сцену без прози.

Лише валідований completed/stop pass із no_changes та непорожньою первинною відповіддю, коли робоча копія дорівнює base, автоматично публікує незмінний текст у prose. Успадкувати content_format. Ідентична чинна fresh проза повторно використовується без дубліката/інвалідації. Draft лишається head draft; diff acceptance не пропонується. Це не літературна оцінка якості. Empty/refusal/failed/length/cancel/limit без успішної перевірки не публікують прозу. Після справжніх змін лишається один явний grouped review.

Storage публікує edited version/head і no-change checkpoint atomically із повторними source/dependency/scene/head CAS guards. Recovery після publication не створює дубліката й не викликає модель. Pipeline може перейти до memory, pause-after-edit збережено. UI переходить у Prose лише за незмінного буфера; dirty ввід не замінюється. Legacy single-stage API behavior поза цим виправленням.

Наявний completed no_changes run користувача можна завершити локально без повторної генерації під час погодженого безпечного restart, через ту саму guarded publication під exclusive maintenance lock. Не обробляти автоматично всі історичні run.
