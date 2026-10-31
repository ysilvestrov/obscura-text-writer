# Збірка візуального редактора

R-22a постачає перевірене ядро Markdown/ProseMirror; R-22b підключає його до чернетки й прози. План/JSON залишаються у plain editor adapter. Коментарі R-23 виконуються наступними пакетами.

Користувачеві Python-застосунку Node, npm, CDN або доступ до мережі для завантаження редактора не потрібні: JavaScript і ліцензії включено в Python wheel.

Для розробника потрібні Node 20+ та pnpm 11. З кореня репозиторію:

```powershell
pnpm --dir frontend install --frozen-lockfile --ignore-scripts
pnpm --dir frontend run build
python scripts/check_editor_bundle.py
python scripts/verify.py tests/web/test_markdown_bridge.py -q
```

Реальні браузерні перевірки потребують dev-залежностей і Chromium:

```powershell
pnpm --dir frontend exec playwright install chromium
pnpm --dir frontend exec playwright test rich-editor.spec.mjs
```

Runner піднімає окремий сервер8976 із тимчасовим каталогом, відсутнім env-файлом та gateway, який забороняє модельні виклики. Production-сервер/твори не використовуються. Desktop і Pixel7 перевіряють actual Save, old plain, paste, undo/redo, locale selection та read-only history. Журнал виконання цих JS-перевірок окремий від pytest STATUS.

Безпосередній еквівалент команди збірки після встановлення залежностей: `node frontend/build.mjs`. Налаштування `frontend/pnpm-workspace.yaml` забороняє непомітну автоматичну інсталяцію перед `run`; версії визначено lockfile. Під час оновлення залежностей перевіряйте ліцензії й комітьте lockfile, bundle, manifest та тексти ліцензій разом.

`frontend/src/markdown-bridge.js` читає plain або Markdown і створює ProseMirror-документ. `source-map.js` перетворює точні координати виділення у Unicode codepoints raw source. Не використовуйте пошук схожої цитати для відновлення прив’язки. Збереження без правок повертає первісний source дослівно; після правок незмінені Markdown-блоки й роздільники зберігаються, змінені проходять повторний parse з перевіркою семантичної тотожності.

Редаговані конструкції: абзаци, переноси, жирний і курсив. Решта CommonMark зберігається як буквальні непрозорі блоки без виконання HTML або завантаження зображень; виділення всередині них не є підтримуваною прив’язкою коментаря. Внутрішня карта використовує UTF-16, серверний контракт — Unicode codepoints; межа всередині surrogate pair відхиляється.

`static/editor-bundle.json` фіксує хеші джерел, lockfile, зібраного JavaScript і ліцензій залежностей. `check_editor_bundle.py` перевіряє їх без Node та без `node_modules`. Збірка використовує data-only декодер HTML entities: імпорт ядра не потребує DOM і не інтерпретує авторський HTML.
