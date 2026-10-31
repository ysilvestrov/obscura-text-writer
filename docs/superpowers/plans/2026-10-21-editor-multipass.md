# Багатопрохідна редактура — план реалізації

Виконання: у цьому чаті, поточній гілці; за попереднім дорученням власника після плану реалізувати без додаткового підтвердження. Навички writing-plans та executing-plans; один незалежний reviewer наприкінці.

Специфікація: docs/specs/changes/editor-multipass.md. Мета — до 5 спроб на окремій копії з одним фінальним авторським diff, без ручного копіювання прози в чернетку.

## 1. Домен і непублічний результат проходу
- [x] RED тести RunRequest strict limit 1..10, patches/diff working candidates без head publication, no_changes як нормальний stop лише всередині loop.
- [x] run_models.py: mode/edit_pass_limit/editor_loop checkpoint. generation/editor_loop.py: source/context/readiness, save_pass_result; stages.py делегує лише внутрішній loop marker після чинного парсингу/guards.
- [x] GREEN домен/стадії, старий одиночний редактор незмінний.

## 2. Черга, відновлення й підсумкове прийняття
- [x] RED синтетичні цикли patches/diff: ланцюг, limit/cycle/no_changes, помилка, pause/cancel/recovery, source CAS, ідемпотентність, спільний diff/підмножина.
- [x] editor_loop.py: execute/finish з persisted IDs і reuse completed attempt; worker.py enqueue/execute/readiness/resume hooks. Без дублювання gateway/accounting або прихованих retry.
- [x] storage/copyedit_store.py: атомарне завершення needs_review loop-run після чинного CAS; повернення Run. Новий snapshot не підмінює початкові залежності.
- [x] GREEN тести черги/API/публікації та наявні copyedit/evidence тести.

## 3. UI та завершення
- [x] RED UI/readiness/confirmation для ліміту й лише редактора; кнопка циклу; номер проходу/stop reason; прийняття освіжає Run.
- [x] runs.js, run-readiness.js, copyedits.js: чинні UI dirty/async guards; ліміт, queued flow, оновлення після прийняття.
- [x] SPEC.MD + docs/editor-review.md та журнал прогресу: контракти, сумісність, відомі обмеження.
- [x] Повний offline suite, один UI detector і синтетична browser перевірка; незалежне review і виправлення істотних знахідок; локальний коміт коду+SPEC. Без платних API, змін робочих текстів/профілів/сервера або push.


## Виконання й evidence

Усі кроки реалізовано в поточній гілці. RED→GREEN для ланцюга, лімітів, циклу, no_changes, API й recovery. Первинний повний suite: 668 passed, 1 skipped, 98.88s; після незалежного review додано два регресійні випадки й виправлено локальне завершення збереженого no_changes після зміни ролі та лічильник спроб після stream exception. Остаточний повний suite: **670 passed, 1 skipped, 94.67s**, artifacts/editor-loop-final.log. Рев’ю кінцевих виправлень без Critical/Important.

Синтетичний browser шлях: кнопка циклу, підтвердження лише редактора й до 5 спроб, три fake-проходи, один combined diff, вибір/серверний preview, прийняття та completed без додаткового виклику. Початковий draft залишився вибраним; поточна проза створена лише після прийняття. Помилок консолі немає, UI detector без знахідок. Screenshot: artifacts/editor-loop-browser/completed.png (та review.png). Тимчасові сервер і вкладку завершено. Платних викликів, змін робочих текстів/профілів/сервера чи push немає.

Ruling: перша версія підтримує patches/diff, бере актуальну вибрану прозу або чернетку за відсутності прози; непридатна проза не підміняється мовчки. За помилки проміжні draft доступні в історії, окреме підсумкове прийняття часткового циклу не додається. Нормальний фінал має один перегляд. Пауза — між проходами; кожна спроба витрачає один слот навіть при бюджетному блокуванні, що консервативно зберігає ліміт викликів.
