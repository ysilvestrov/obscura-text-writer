# Ghost Mode — PR 2: інтерфейс режиму (#55)

Дизайн: `docs/superpowers/specs/2026-11/2026-11-09-ghost-mode-design.md`. Ядро — PR 1 (#79): `ghost-blocks.js`, `POST /api/scenes/{id}/ghost-rewrite`.
Гілка `claude/ghost-ui-55` від `claude/ghost-core-55`; PR на `main` після злиття #79.

## Задача 1. Модель сеансу (inline)

`web/static/ghost-session.js` — чиста модель без DOM: `createSession`, переходи станів блоку `reading → writing ⇄ peek`, `skipped` і повернення, `canSave`, `resultText`, лічильники, серіалізація в `localStorage` (`ghost:<scene>:<draft>`, try/catch), `ghostStatsText`. Node-тест `tests/web/js/ghost_session.mjs` через pytest.

## Задача 2. Режим (inline)

`web/static/ghost-mode.js`, секції `#ghost-entry` і `#ghost-mode` у `story.html`, стилі, ключі UA/EN.
- Вхід: кнопка «Переписати по пам’яті» в режимі чернетки (не історія) для повної голови чернетки; «Продовжити переписування», якщо є сеанс; незбережена чернетка блокує вхід.
- Повноекранний шар: AI-блок (`createTextEditor`, лише читання, без виділення й копіювання), редактор автора на блок (`createTextEditor`, формат чернетки), прогрес «Блок N з M», «Назад», «Далі» (`Ctrl+Enter`), «Пропустити блок»/«Повернути блок», кнопка «Проблиск» з утриманням, «Зберегти», «Скасувати».
- Проблиск: `Tab` (без повтору, не під час IME) лише в `writing`; фокус переходить на контейнер шару, редактор `readOnly`, будь-які клавіші ігноруються; `keyup Tab`, втрата фокуса вікна, `visibilitychange` завершують; повернення фокуса в редактор.
- `paste`/`drop` у редакторі скасовуються (capture), `copy` у AI-блоці скасовується; `Esc` знімає фокус.
- Збереження: підтвердження за пропущених блоків, POST, очищення сеансу, перехід до нової чернетки, повідомлення зі статистикою; попередження, якщо голова чернетки змінилася після початку; `beforeunload` за незбереженого сеансу.

## Задача 3. Статистика в історії, Playwright, документація (inline)

- Рядок `ghostStatsText` під списком історії для версії з `ghost_rewrite`.
- Фікстура `POST /test-ghost-mode`, `tests/web/browser/ghost-mode.spec.mjs` (desktop/mobile): стани й Tab на порожньому блоці, стирання до порожнього, кнопка проблиску, вставка, пропуск, відновлення з `localStorage`, збереження Markdown; знімки `docs/images/ghost-mode-{desktop,mobile}.png`.
- SPEC.MD GHOST-REWRITE: технічний опис інтерфейсу, S02, S03, S06, S08; traceability (Playwright через ручну процедуру `docs/verification/manual.md#ghost-mode`, клавіатура Windows); `docs/ghost-mode.md`, `docs/en/ghost-mode.md`, посилання з README і `docs/visual-editor.md`; журнал; verify.
