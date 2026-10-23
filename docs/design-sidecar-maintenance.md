# Супровід службового опису Impeccable

`DESIGN.md` містить затверджені візуальні правила й токени. Локальний `.impeccable/design.json` доповнює їх метаданими палітри/типографіки, тінями, контрольними ширинами, прикладами компонентів і дослівним narrative. Він не завантажується застосунком і не замінює DESIGN.md чи архітектурну SPEC.MD. Каталог `.impeccable/` ігнорується Git; у чистому checkout його може не бути.

## Як оновлювати

Використовуйте встановлену навичку Impeccable `document`, розділ **Step 4b: Write .impeccable/design.json sidecar**. При запиті оновити лише sidecar процедура вимагає зберегти DESIGN.md. `document` — інструкція навички, а не CLI-команда генерації JSON.

1. Запустіть `impeccable context` один раз на сесію, а `impeccable doctor --json` — для діагностики. У Windows використовуйте `scripts/impeccable.cmd` із каталогу встановленої навички. Збережіть попередній JSON і результати doctor в локальному `artifacts/`.
2. Звірте всі `colors` і `typography` frontmatter із `app.css`, включно з `[data-theme="dark"]`. Примітиви лишаються у DESIGN.md; sidecar не має старого дубльованого розділу `tokens`.
3. Звірте `extensions.colorMeta`, `typographyMeta`, `shadows`, `breakpoints`, theme refs та файли `sources`. Не створюйте анімацій, якщо CSS їх не визначає. Незмінні палітри не потребують нових tonal ramps.
4. Оновіть сім прикладів: основна/другорядна кнопка, поле, активна сцена, активна вкладка, картка, бейдж. Перенесіть відповідні декларації app.css у класи з префіксом `ds-`, зберігши порядок каскаду, відносну specificity, hover/disabled/focus і мобільний стан вкладки. Додайте успадковані font/color, коли без body вони втратяться в ізольованому preview. Не копіюйте весь stylesheet.
5. Дослівно перенесіть north star, абзаци огляду, характеристики, named rules та do/don't із DESIGN.md. Перевірте `refersTo` проти `components` frontmatter. Лише після звірки оновіть `generatedAt` у JSON schemaVersion=2.
6. Повторіть `doctor --json`. Окремо один раз запустіть `detect --json` для app.css і base/library/story/settings templates; збережіть зауваження, не вимикайте правила заради чистого звіту. Перевірте незмінність хешів DESIGN.md, PRODUCT.md і runtime-файлів.
