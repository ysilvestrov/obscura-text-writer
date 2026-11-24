# Процедури ручної перевірки

Це інструкції, **не свідчення виконання**. Для кожного реального прогону запишіть дату, commit/знімок, середовище, кроки, результат і безпечне посилання на докази. Авторські тексти, ключі та приватні логи не комітьте.

<a id="architecture-review"></a>
## Архітектурна зміна

Перегляньте git diff коду та SPEC.MD одного набору змін. Для зміненого компонента, схеми, API, станів, провайдерів або контексту знайдіть Requirement/Scenario з новим контрактом і тест/ручний крок. Перевірте, що відомий дефект не названо бажаною поведінкою. Очікування: код, контракт та пояснення сумісності узгоджені. Лише рев’ю набору змін, не наявність AST, доводить цю процесну перевірку.

<a id="batch-import"></a>
## Невалідний файл у наборі імпорту

На окремому порожньому тестовому каталозі створіть твір. Подайте набір із валідного TXT і другого файла: по черзі неправильне розширення, більше 2 MiB, невалідний UTF-8, порожній текст. Звірте sources, versions, heads і файли до/після. Очікування: відмова до збереження будь-якого файла набору. Позитивний контроль — валідний UTF-8 із BOM та рівно граничним розміром. Поточний тест збереження байтів не доводить весь цей batch-сценарій.

<a id="local-origin"></a>
## Локальна HTTP-межа

Запустіть сервер на loopback з одноразовим тестовим каталогом. Через локальний HTTP-клієнт надішліть змінювальний запит з чужим Origin, потім із Origin фактичного сервера; окремо перевірте чужий Host. Очікування: чужий Origin/Host відхиляється до зміни даних, правильний локальний запит виконується. Запит без Origin перевірте відповідно до SECURITY-001: це не автентифікація й не захист від іншого локального користувача. Не публікуйте сервер у мережу.

<a id="provider-behavior"></a>
## Поведінка реального провайдера та літературна якість

За окремим погодженим маршрутом даних і бюджетом запустіть нейтральний і дорослий контрольні приклади. Збережіть точну конфігурацію, версії промптів/набору, finish reason, відмову/технічну причину, usage і сирий результат у приватному артефакті. Після явної відмови діє story/model block; не обходьте його повтором чи fallback. Очікування: відмова відокремлена від низького літературного бала. Для допуску Evaluator потрібне чинне калібрування, а для літературного висновку — окремий перегляд української, голосу й сюжету. Успішний HTTP/JSON сам цього не доводить. Ця процедура нічого не дозволяє надсилати без авторизації.

<a id="publication"></a>
## Публічний пакет і свіжа копія

Виконайте [процедуру пакування](../github-publication.md) в окремій копії. Перевірте відсутність старої приватної Git-історії, авторських матеріалів, ключів і приватних artifacts; не використовуйте .gitignore як доказ приватності. На чистій копії без artifacts створіть venv, установіть документовані залежності й виконайте pytest та check_docs.py. Очікування: тести не потребують робочих творів, а тимчасовий каталог створюється сам. Поточний checkout не є доказом чистої публічної історії. Публікація потребує окремого дозволу; ця процедура не виконує push.

<a id="role-profiles-ui"></a>
## Профілі ролей: preview і незбережені форми

На окремих синтетичних даних збережіть чотири ролі та комплект. У налаштуваннях нового твору перевірте: без вибору preview/apply/export недоступні; після вибору preview/export доступні, apply — ні. Перегляньте версію: показані чотири моделі, ліміти, власний/стандартний промпт та поведінка Evaluator. Apply стає доступним. Змініть genre або інше поле форми: preview очищається, apply блокується. Повторіть preview, змініть вибір — та сама інвалідація.

Повторіть preview й apply: підтвердження попереджає про незбережені правки; відмова від підтвердження не змінює твір; підтвердження публікує всі ролі та оновлює сторінку. Для нової версії збережіть змінені ролі й позначте відповідний прапорець; версія 1 лишається доступною, інший твір не оновлюється. Імпортуйте експортований JSON: окремий профіль без автоматичного застосування. Перевірте клавіатурну навігацію, довгу назву й вузький viewport без горизонтального обрізання. Не запускайте генерацію: процедура не потребує API-витрат або робочих творів.

<a id="ebook-formats"></a>
## FB2 та EPUB

Установіть `.[publication,dev,web]`. Локальна конвертація не потребує моделей або ключів. У робочій області відкрийте «Картка публікації», збережіть назву/метадані й обкладинку. FB2 потребує автора й жанру; EPUB дозволяє відсутнього автора. «Опублікувати» → формат → «Створити файл». Прапорець неповного твору дозволяє лише пропуски/stale з явними позначками, не помилки метаданих чи схеми. Після успіху з’являються файл та manifest; після помилки попередні посилання лишаються. «Скасувати» нічого не створює.

Для офіційного контролю завантажте [EPUBCheck 5.4.0](https://github.com/w3c/epubcheck/releases/tag/v5.4.0) і Java 11+ з офіційного джерела, звірте SHA-256. Вони не встановлюються сервером. Виконайте (шляхи замініть своїми):

```powershell
.venv/Scripts/python.exe scripts/check_ebooks.py --java C:/Tools/Java/bin/java.exe --epubcheck C:/Tools/epubcheck/epubcheck.jar --output artifacts/ebook-acceptance
```

Скрипт створює лише синтетичні тимчасові дані під output, генерує мінімальні/повні/неповні книги (сім сцен понад 15 тисяч слів), перевіряє FB2 комплектною XSD й EPUB офіційним validator, зберігає файли та result.json із кодами/хешами/stdout. Exit code 0 потрібен для всіх шести файлів. EPUBCheck 5.4.0 застосовує поточні правила EPUB 3.4 до package 3.0; формат рендерера використовує лише можливості EPUB 3.3. Цей прогін окремий від pytest.

Відкрийте повну й неповну книги в локальному читачі FB2/EPUB; перевірте обкладинку, зміст EPUB, усі сім заголовків у порядку сцен, Ґ/Є/І/Ї, апострофи, тире, пусті рядки, позначки неповноти й відсутність інтерпретації `<не тег>` як розмітки. Налаштування шрифту читача мають працювати. Окремо перевірте форму на desktop/mobile: вибір формату, keyboard focus, busy/dirty, скасування та конкретну помилку FB2 без автора. Запишіть назву/версію читача, фактичні результати й обмеження; успішна XSD/EPUBCheck не замінює цього перегляду.

<a id="pdf-publication"></a>
## PDF A5

Установіть publication extra (див. README). У формі «Опублікувати» оберіть «Книга A5 (.pdf)». Погоджений профіль: Noto Serif11/15pt, поля17мм/нижнє18мм, обкладинка за наявності, титул, зміст і нумерація зі змісту. Інших профілів поки немає. Поля титулу беруться лише зі збереженої картки; прозу не редагує модель. Непідтримуваний символ зупиняє експорт з U+codepoint: виправте джерело або використайте інший формат, автоматичної заміни немає.

Для відтворення синтетичного приймання встановіть dev extra (pypdf/pdfplumber) та вкажіть наявний локальний Poppler pdftoppm. Ці інструменти не є залежностями запуску сервера:

```powershell
.venv/Scripts/python.exe scripts/check_pdf.py --pdftoppm C:/Tools/Poppler/bin/pdftoppm.exe --output artifacts/pdf-acceptance
```

Скрипт створює чотири синтетичні PDF: мінімальний, повний семисценовий >15k слів з PNG transparency, неповний і довгі назви/слова. pypdf перевіряє витягуваний текст/відсутність порожніх сторінок/вбудовані шрифти; pdfplumber — межі слів у printable area з окремим допуском footer; Poppler рендерить кожну сторінку. result.json містить hashes/word_count/format_details/порушення; ненульовий exit — невдала перевірка. Перегляньте всі PNG (оглядові контактні листи плюс вибрані сторінки в повному розмірі): не повинно бути обрізань, перекриттів, квадратів, відірваних заголовків або випадкових порожніх сторінок. Звірте номери у змісті з фактичними першими сторінками розділів. Окремо перевірте довгий title/author і вибір PDF у формі desktop/mobile. Це інженерне приймання, без оцінки літературної якості.

Комплектні шрифти: незмінені Noto Serif Regular/Italic/Bold/BoldItalic, [джерело](https://github.com/notofonts/noto-fonts/tree/ffebf8c1ee449e544955a7e813c54f9b73848eac/hinted/ttf/NotoSerif), OFL-1.1 у src/storygen/publication/resources/fonts/OFL.txt; hashes/commit у сусідньому manifest.json. Системна Georgia, завантаження шрифтів під час роботи та платні API не потрібні.


<a id="r20-workspace"></a>
## R-20: ручний маршрут у браузері

На окремому синтетичному творі з сімома сценами перевірити desktop і mobile390: постійний Plan/шість вкладок, видимість активної вкладки після переходу/повернення, sticky toolbar без перекриття, клавіатурні стрілки/Home/End і фокус. На кожному етапі переглянути результат та ручні правки, пройти diff/прозу/пам’ять до наступної сцени й картки. Не використовувати реальний платний gateway: виклики дозволені лише з mock transport або готовими synthetic attempts.

Перевірити missing/stale матеріал, no-changes/partial editor-loop, історію, forwarding, dirty/Save/error та появу active run під час очікування. Відкрити посилання налаштувань відповідної ролі, зберегти/повернутися без inference. У деталях обліку звірити unknown і явний zero usage. Порівняти з вихідним MD-рядком, включно з переносами й emoji. Фактичний результат/скріншоти записати окремо; наявність цієї процедури не означає, що її виконано.


<a id="r21-settings"></a>
## R-21: налаштування за розділами

На синтетичному творі з fake gateway, без платних викликів, перевірити:
1. Desktop і mobile390: п’ять розділів, одна форма ролі, sticky Save без перекриття; Tab/Shift+Tab, видимий focus, відкриття details із невалідним полем.
2. Змінити Writer, перейти Editor, зберегти Editor; Writer має лишитися dirty зі своїм значенням. Save Writer не конфліктує лише через власний попередній Save Editor. Зовнішню зміну того самого scope не перезаписувати мовчки.
3. Затримати API Save/Reset/profile Apply: введення всіх зареєстрованих форм і повторний запис заблоковані. Після помилки значення збережені. Shared connection підтверджує зачеплені поля, а dirty промпт сусіда лишається.
4. Налаштувати Evaluator і editor classifier звичайними полями. Перевірити null CLI model/timeout/temperature та legacy advanced, enable/disable classifier і Save Editor; inference не відбувається.
5. Увести невалідний raw JSON: normal fields/Save заблоковані, Discard повертає форму; негайний off працює. Валідний Apply після off не вмикає оцінювач. Калібрований pause після зміни конфігурації вимагає явної policy; candidate і refusal block не обходяться.
6. Перейти із помилки контексту за role/scene/material, змінити поле, повернутися до матеріалу. Вихід із dirty форм має попередження; бюджетна звірка/тариф зберігаються своїми діями.

Це процедура, не звіт про виконання. Фактично виконані кроки й обмеження браузерного інструмента записуються в журналі R-21; автоматичні результати — у STATUS.md.


<a id="r24-localization"></a>
## R-24: UA/EN інтерфейс без зміни матеріалів

На окремому синтетичному творі без API-ключів перевірити:
1. Перший вхід en-US/uk-UA, явну UA/EN перевагу, повернення/нову сторінку; html.lang, title, aria labels. Для інших мов fallback uk.
2. У редакторі відкрити чернетку, ввести незбережений текст з HTML-подібними символами й {p1}, встановити selection; перемкнути мову. Значення, dirty, selection і сцена збережені; вкладені статуси не зникають. SSE fake delta і partial не стираються при перемиканні.
3. У налаштуваннях змінити Writer/Editor без Save, перемкнути мову/роль/розділ; буфери й dirty мітки збережені. Перевірити Evaluator, пороги/checkbox labels, classifier, prompt text, бюджет і комплекти; поля авторських значень/ID незмінні.
4. Перевірити бібліотеку, імпорт, персонажів/add/edit/delete, пам’ять/forwarding, trash, history/acceptance, publication/186 genres, export labels, помилку API й original diagnostics обома мовами. Не змінювати реальні твори й не викликати платні моделі.
5. Desktop/mobile390 та клавіатура: вибір мови доступний, активний стан видимий, довгі підписи без overflow/перекриття. Перевірити браузерний console й screenshots обох мов на нейтральних прикладах.

Наявність процедури не означає її виконання. Фактичні кроки/межі — у журналі R-24, автоматичні результати — через verify.py у STATUS.md.


<a id="r22-visual-editor"></a>
## R-22b: форматування, plain сумісність і browser runner

На синтетичному сервері без .env і production даних виконати `pnpm --dir frontend exec playwright test rich-editor.spec.mjs` (після dev install та `playwright install chromium`). Сценарії визначено у tests/web/browser/rich-editor.spec.mjs; сервер tests/web/browser/server.py завжди створює тимчасовий каталог і заборонені gateways. Порт8976 має бути вільним; чинний сервер не підміняти.

Перевірити desktop/mobile: strong/em, no-op ID, Ctrl+B/undo/redo, actual Save та undo після нього, UA/EN з selection і dirty, повернення до plain плану, literal legacy зірочки, text-only HTML-paste, reload/один adapter, readonly history/disabled toolbar. Окремо оглянути нейтральні screenshots на overflow, focus, читабельність, висоту editor й сталість правої панелі. JS runner не входить у pytest STATUS; фактичний прогін і межі фіксуються окремо в журналі. Наявність цієї процедури не означає виконання всіх майбутніх UI сценаріїв коментарів/експорту.


<a id="r23-comments"></a>
## R-23: коментарі у чернетці

На синтетичному сервері без ключів запустити `pnpm --dir frontend exec playwright test comments.spec.mjs rich-editor.spec.mjs`. Desktop/mobile: вибрати фрагмент, відкрити коментар, змінити інструкцію, Escape/повторне відкриття/видалення; заборонити перетин. Додати загальний коментар, явно Save, reload, правка всередині, undo/redo, Save pending, перевірити origin. Створити коментар на незбереженому тексті, змінити його, Save/reload/явно переприв’язати. Перемикання UA/EN з відкритим popover зберігає ввід. Інша вкладка змінює notes:409 зберігає робочий ввід і розблоковує форму. Перевірити multiline paste з двома paragraphs. Записати фактичний результат окремо; наявність процедури не означає PASS.


<a id="r23-rewrite"></a>
## R-23: переписування за коментарями

На синтетичному сервері без ключів запустити `pnpm --dir frontend exec playwright test rewrite-review.spec.mjs`. Desktop/mobile: general comment, одне натискання без діалогу (атомарне збереження і один fake writer), помилка Save/preflight (жодного run), повторне натискання під час збереження (жодного дубля), readonly review у draft, початково немає вибору. Вибрати цілу групу, побачити assembled preview, apply: новий draft, prose незмінна, notes очищено. Повторити з reject-all: source ID і notes ID незмінні. Перевірити history instructions, location labels та UA/EN. UI execution не є перевіркою літературної якості або реальної моделі. Фактичні результати записувати окремо.


Додаткова R-23 регресія: у двох вкладках відкрити ті самі збережені notes; друга змінює лише notes. Rewrite у першій SHALL показати конфлікт без нового run, зберігши її показаний ввід. Автоматично перевіряється Playwright scenario `rewrite never substitutes another tab notes for the locally reviewed set`. Text undo після явного reattach не повертає стару прив’язку; Node comment-state regression перевіряє, що два valid ranges не перетинаються.

R-22 прокрутка: Playwright `long draft scrolls internally while formatting toolbar stays in place` у rich-editor.spec.mjs перевіряє desktop/mobile на100 абзацах: обмежена висота, внутрішній scrollTop, незмінні координати toolbar та scrollY сторінки.


<a id="r20-position"></a>
## R-20: місце роботи після reload

На синтетичному сервері запустити `pnpm --dir frontend exec playwright test workspace-position.spec.mjs`: desktop/mobile, друга scene+draft →reload; інший story має власний вибір; bare link повертає remembered місце. Явний URL перевизначає його, наступний вибір+reload не повертає старий query. Trash обраної сцени дає перший plan; blocked localStorage не перешкоджає URL restore. History перегляд не замінює remembered current material; payload містить лише scene_id/material. Результат runner записати окремо; наявність процедури не є виконанням.


<a id="r20-brief-review"></a>
## R-20: pending завдання в основному workflow

`pnpm --dir frontend exec playwright test brief-proposal.spec.mjs` на синтетичному сервері: old head + new proposed brief (після R-44 старе завдання фікстури збережене без запуску моделі, тож воно авторське й не позначається stale, VALID-LINKS). Перевірити новий JSON у вкладці й явний список змін/accept; Save не приймає його, accept вибирає exact displayed version й розблоковує draft за придатного контексту. Dirty edit блокує accept до Save, після Save приймається саме нова авторська версія. Конкурентна зміна scene дає помилку без втрати тексту. Story refresh відкритого чистого brief підхоплює нову пропозицію без head change; dirty ввод лишається. Сценарій `acceptance follows refreshed run state without switching tabs` перевіряє блокування під час роботи та доступність після оновлення стану без переходу між вкладками. Desktop/mobile, без реальних моделей; наявність процедури не є звітом про виконання.

Сценарії `editing an accepted brief keeps acceptance when starting a draft` і `manual save of an accepted brief keeps acceptance`: прийняти пропозицію, змінити її, перевірити ручний Save та основну дію; нова версія лишається прийнятою, а основна дія після збереження надсилає запит на запуск; тест перехоплює цей запит без виклику моделі. Окремо перевірити, що правка неприйнятої пропозиції все ще потребує явного прийняття.


<a id="run-recovery-visible"></a>
## Видимість відновлення після налаштувань

На синтетичному стенді (`tests/web/browser/server.py`) вручну в desktop і mobile (375 px): створити твір зі збереженим failed запуском етапу сцени, затримати readiness (DevTools → Network throttling) і зробити налаштування ролі несумісними, перейти в налаштування та повернутися. Автоматичний сценарій `restored failed run` був у вилученому `impact.spec.mjs` (R-44, PR 1); окремого браузерного тесту для запуску етапу поки немає. Repeat має бути видимим і disabled із причиною; жодного resume POST. Для фактично ready run додатково перевірити доступну кнопку без натискання; completed run не має repeat. Сам опис не є підтвердженням виконання.


<a id="characters-page"></a>
## Окрема сторінка персонажів

Запустити `node frontend/node_modules/@playwright/test/cli.js test --config frontend/playwright.config.mjs characters-page --reporter=line`.
Перевірки desktop/mobile: перехід і повернення до prose, додавання картки, довгий опис, UA/EN без втрати вводу, preview, save, порожній твір без сцен, відмова від виходу з dirty, CAS409 без втрати правок. Переглянути нейтральні `docs/images/characters-page-desktop.png` і `characters-page-mobile.png`: поля видимі, немає горизонтального переповнення.


<a id="characters-find"></a>
## Пошук картки на сторінці персонажів

Запустити `node frontend/node_modules/@playwright/test/cli.js test --config frontend/playwright.config.mjs characters-page -g "find a character" --reporter=line`.
Перевірки desktop/mobile (CHARACTER-TIME-S04): фільтр за іншим ім'ям, статус «Показано 1 з 3», Enter переносить фокус, вибір «Анна» з підказок за наявності «Маріанна», введення не переносить фокус, правка під фільтром і збереження всіх карток, зняття фільтра за порожнього поля прихованої картки під час збереження й preview (без запиту preview), приховування після виходу з картки, «Додати персонажа» знімає фільтр, без горизонтальної прокрутки.


<a id="additive-import-ui"></a>
## Інтерфейс письма та доповнювального імпорту

`node frontend/node_modules/@playwright/test/cli.js test --config frontend/playwright.config.mjs additive-imports --reporter=line` на синтетичному сервері. Desktop/mobile: writing target25000, Save, Reset, UA/EN, remote-target conflict без втрати вводу; журнал назв/дат, нові/дубльовані матеріали, partial/error, pending-submit, збереження selection. Наявність процедури не означає її виконання; фактичний результат записується в журналі й STATUS.

Додатково: confirmed POST + failed GET лишає «Імпорт завершено» й кількості; кнопка повторює тільки GET. POST застосований сервером, але відповідь втрачена: невідомий результат без нульових кількостей, файлові поля очищено, журнал оновлюється без нового POST. Writing409/мережевий збій зберігають ввід і блокують dirty-вихід.


<a id="r23-select-all"></a>
## Пакетний вибір переписування

Запустити `node frontend/node_modules/@playwright/test/cli.js test --config frontend/playwright.config.mjs rewrite-review --reporter=line`. Новий сценарій select all rewrite changes перевіряє desktop/mobile: початково0, click→усі групи без mutations, UA/EN, preview обов’язковий навіть після повернення до all, apply двох змін/очищення notes. Нейтральні screenshots docs/images/rewrite-select-all-desktop.png і mobile.png оглянути на читабельність/overflow. Наявність процедури не означає виконання.


<a id="collapsible-scenes"></a>
## Згортання списків сцен

Запустити Playwright collapsible-scenes.spec.mjs на synthetic server:65 scenes, dirty draft, selected scene/material, click/Enter, UA/EN/refresh зберігають open; імпорт поза collapsed list. Synthetic latest reports collapse без втрати articles; поточні blockers/checkpoint не ховаються. Оглянути screenshots collapsed-scenes/reports desktop/mobile. Наявність процедури не є фактичним PASS.


<a id="workspace-layout"></a>
## Робочий простір: рядок стану, меню й розділи сцени

З `PYTHONPATH=<робоча копія>/src` у `frontend` запустити `npx playwright test workspace-layout --project=desktop --project=mobile` на synthetic server без provider calls. `workspace-layout.spec.mjs`: `status row holds run controls and the next-run limit`; `waiting run shows a decision link and the pinned area stays small` (R20-WORKSPACE-S03); `full screen mode spreads the editor and exits on Escape` (R20-WORKSPACE-S05); `story menu opens from the keyboard and returns focus on Escape` (пункту «Перевірка книги» немає); `scene sections reopen after reload and leave unsaved text alone` (зокрема оцінювання приховане без оцінювача); `sections work when storage throws`. Переглянути знімки `docs/images/workspace-*-{desktop,mobile}.png` на нейтральність і відсутність горизонтального прокручування на 375 px. Наявність процедури не є фактичним PASS; результат запуску записується в журналі виконання.


<a id="run-status-collapse"></a>
## Згорнутий рядок запуску над редактором

З `PYTHONPATH=<робоча копія>/src` у `frontend` запустити `npx playwright test run-status-collapse --project=desktop --project=mobile` на synthetic server без provider calls. `run-status-collapse.spec.mjs`: `a finished run collapses to one line and opens its details on click` (⚠, приховане попередження, клік розгортає й згортає); `a running run with many long models keeps the mark and the timer on the summary line` (обрізання моделей, витрати «усього / останній» з двох подій, usage лише в підказці, ⚠ і таймер у тому самому рядку, знімок `run-status.png` у результатах тесту); `a failed run shows its error at once and can be collapsed`. Наявність процедури не є фактичним PASS; результат запуску записується в журналі виконання.


<a id="docs-site-publish"></a>
## Сайт інструкцій: публікація після злиття

Після злиття PR, що змінює `docs/site/**`, відкрити вкладку Actions репозиторію й переконатися, що запуск workflow `site` для push у `main` завершився успішно, включно з кроком «Check the published address». Відкрити `https://obscurawriter.com/` і `…/en/install.html`: обидві сторінки відповідають, перемикач мови веде на ту саму сторінку іншою мовою, зміст відповідає новому коміту. Перевірити також `https://obscurawriter.com/robots.txt`, `/sitemap.xml` і будь-яку неіснуючу адресу (двомовна сторінка 404); стара адреса `https://ysilvestrov.github.io/obscura-text-writer/` переадресовує на домен. Вибір мови в справжньому браузері: у вікні InPrivate з мовою браузера English головна відкриває `/en/index.html`, з українською в списку мов лишається українська; після кліку на «Українська» в англійському браузері українська лишається й після перезавантаження. Перевірка щойно відкритого PR: у запуску workflow для `pull_request` немає задачі `deploy`.


<a id="waitlist-live"></a>
## Список очікування: перевірка наживо

Після кроків власника з [docs/waitlist.md](../waitlist.md), до злиття PR, на гілці PR:
1. У теці `workers/waitlist` тимчасово змінити в `wrangler.toml` `ALLOWED_ORIGINS` на `"https://obscurawriter.com,http://localhost:8000"` і виконати `npx wrangler deploy`.
2. З кореня репозиторію `python scripts/build_site.py --out C:\tmp\wl-site`; у `C:\tmp\wl-site` — `python -m http.server 8000`; відкрити `http://localhost:8000/paid.html`. Віджет Turnstile видно під позначкою згоди.
3. Записати нейтральну адресу (наприклад, `test.waitlist@example.com`) з позначкою згоди → сторінка з повідомленням «Готово». Ту саму адресу великими літерами → знову «Готово». Адресу без `@` (перевірку браузера обійти, прибравши `type="email"` у інструментах розробника) → повідомлення про хибну адресу. Без позначки згоди браузер форму не надсилає. Те саме на `http://localhost:8000/en/paid.html` → англійські повідомлення на англійській сторінці.
4. У консолі D1: на адресу один рядок, `lang` відповідає сторінці, `privacy_edition` — дата редакції «Приватності», `created_at` — UTC. У панелі D1 видно юрисдикцію `eu`. Видалити тестові рядки (`DELETE FROM waitlist WHERE email LIKE 'test.waitlist%';`).
5. `git restore workers/waitlist/wrangler.toml` і знову `npx wrangler deploy`. У панелі Worker → Settings → Variables `ALLOWED_ORIGINS` рівно `https://obscurawriter.com`.

Наявність процедури не є фактичним PASS; результат записується в журналі виконання (без адрес, крім тестових).

<a id="core-review"></a>
## Панель підтвердження ядра

З кореня робочої копії з `PYTHONPATH=<робоча копія>/src` запустити `frontend/node_modules/.bin/playwright test -c frontend/playwright.config.mjs core-review` (не `npx playwright`, який ставить іншу версію). Synthetic server, нейтральні сцени «Ранок»/«Гість», без provider calls. Cases `core-review.spec.mjs` для desktop і mobile: `changes are expanded, unchanged rows collapsed, confirm without edits` (знімки `docs/images/core-review-{desktop,mobile}.png`, без горизонтального прокручування); `keep previous on an unknown slot creates a version where the slot is unchanged` (після цього без wire «Лишити попереднє» вимкнене, «Вписати…» для закритої лінії відсутнє); `write in with a quote from an earlier scene` (пошук звужує фрагменти); `write in without a quote is unknown to the reader; cancel keeps the draft`; `refreshing the table asks before dropping a core draft`; `a conflict shows the server message and reloads the panel`. Переглянути обидва знімки на нейтральність. Наявність процедури не є фактичним PASS; результат запуску записується в журналі виконання.

<a id="ghost-mode"></a>
## Переписування по пам’яті

З теки `frontend` з `PYTHONPATH=<робоча копія>/src` запустити `./node_modules/.bin/playwright test ghost-mode --reporter=line`. Synthetic server (`POST /test-ghost-mode`): нейтральна сцена «Вечір біля маяка» з AI-чернеткою Markdown (3 блоки: текст із діалогом, розділювач, текст), без provider calls, локаль uk-UA. Cases `ghost-mode.spec.mjs` для desktop і mobile: `reading, writing and Tab peek; save creates an author draft` (Tab до першого символу нічого не робить, стирання до порожнього не повертає AI-блок, утримання Tab блокує набір, `Ctrl+Enter`, збереження Markdown з `author_lineage` і `peeks=2`; знімки `docs/images/ghost-mode-{desktop,mobile}.png`); `peek button, blocked paste and copy, explicit skip`; `an unsaved rewrite survives a reload and cancel discards it`; `plain draft with formatting saves Markdown; notices stay above the mode` (утримання пробілу на кнопці проблиску); `a corrupted saved session never leaves the mode stuck`. Окремо вручну в Windows із фізичною клавіатурою: утримання й відпускання `Tab` у Chrome та Edge не перемикає фокус і не відкриває меню, автоповтор `Tab` не рахує додаткових проблисків, українська розкладка й IME не вмикають проблиск. Переглянути знімки на нейтральність. Наявність процедури не є фактичним PASS; результат запуску записується в журналі виконання.

<a id="brief-link"></a>
## Підтвердження завдання для прози

З теки `frontend` з `PYTHONPATH=<робоча копія>/src` запустити `./node_modules/.bin/playwright test brief-link --reporter=line`. Synthetic server (`POST /test-brief-link`): нейтральні картки «Лера» (протагоністка), «Марко», «Ніна», сцени «Ранок у парку» і «Кав’ярня» з головою brief і ручною прозою без родоводу, без provider calls, локаль uk-UA. Cases `brief-link.spec.mjs` для desktop і mobile: `author confirms the brief with introductions and moves to the next scene` (знімки `docs/images/brief-link-{desktop,mobile}.png`; після підтвердження панель згорнута, API повертає `source=link`, «Наступна непідтверджена сцена» відкриває «Кав’ярня»); `conflict keeps the ticked introductions and saves nothing` (зміна сцени до натискання → повідомлення про помилку, прапорець лишається, `source=fallback`); `opening the brief and switching scenes keep the ticked introductions`; `prose replaced elsewhere is never confirmed unseen` (409, редактор перечитує нову прозу, позначки старої прози не переносяться, підтвердження записується на нову прозу); `an unsaved change to a confirmation is not shown as confirmed`. Переглянути обидва знімки на нейтральність. Наявність процедури не є фактичним PASS; результат запуску записується в журналі виконання.

<a id="plan-numbering"></a>
## Перенумерація пунктів плану

З теки `frontend` з `PYTHONPATH=<робоча копія>/src` запустити `npx playwright test browser/plan-numbering.spec`. Synthetic server (`POST /test-fixture`), без provider calls. Cases для desktop і mobile: `PLAN-NUMBERING-S01 Enter at the end of an item continues the list and shifts the rest` (зокрема порожній пункт розриває список, а пункти нижче нумеруються від 1); `PLAN-NUMBERING-S01 Ctrl+Z after Enter takes back the renumbering, then the new item`; `PLAN-NUMBERING-S02 a new first item renumbers the list and leaves parsed lines alone`; `PLAN-NUMBERING-S03 deleting an item shifts the numbers; the button fixes every list`; `PLAN-NUMBERING-S04 one Ctrl+Z undoes the renumbering; other tabs keep their numbers`. Наявність процедури не є фактичним PASS; результат запуску записується в журналі виконання.

<a id="brief-form"></a>
## Форма завдання письменнику

З теки `frontend` з `PYTHONPATH=<робоча копія>/src` запустити `npx playwright test browser/brief-form.spec browser/brief-proposal.spec browser/save-and-run.spec`. Synthetic server (`POST /test-fixture`; завдання зберігається через `POST /api/scenes/{id}/brief`), без provider calls, локаль uk-UA. Cases `brief-form.spec.mjs` для desktop і mobile: `BRIEF-FORM-S01 a beat with quotes and a line break saves exactly, introduced stays`; `BRIEF-FORM-S02 insert, move and remove renumber the labels, not the texts`; `BRIEF-FORM-S03 advanced JSON keeps unsaved edits; broken JSON keeps the author there`; `BRIEF-FORM-S04 planner numbers, history and a brief without beats`; `BRIEF-FORM-S04 save and run from the form with an empty row starts the run`; `BRIEF-FORM-S03 advanced JSON for a scene without a brief can be saved`; `BRIEF-FORM narrow screen has no horizontal scroll`. `brief-proposal.spec.mjs` і `save-and-run.spec.mjs` правлять завдання в розширеному JSON і перевіряють, що прийняття пропозиції й «Зберегти й запустити» працюють як раніше. Знімки `docs/images/site/{uk,en}/brief-form-desktop.png` знімає `scripts/capture_screenshots.py`; переглянути їх на нейтральність. Наявність процедури не є фактичним PASS; результат запуску записується в журналі виконання.

<a id="model-import-metadata"></a>
## Тарифи, ліміти й journal counts

Playwright model-metadata.spec.mjs: selected model shows tariff units/caps/unknown, manual expired+stale discovery, shared classifier same tariff without limit changes; desktop/mobile UA/EN. Additive-imports case journal retains actual import counts after reload and marks old counts unknown: actual1/0/duplicate0, reload, UA/EN, missing fields unknown. Переглянути neutral model-tariff/import-journal-counts desktop/mobile PNG. Mock APIs/synthetic gateway, без key/.env/production/inference. Фактичні pytest результати — verify.py/STATUS, browser runner — окремо в журналі.
<a id="workspace-one-click"></a>
## Телеметрія та зупинка основної дії

На синтетичному сервері запустити `node frontend/node_modules/@playwright/test/cli.js test --config frontend/playwright.config.mjs workspace-telemetry.spec.mjs workspace-cancel.spec.mjs save-and-run.spec.mjs editor-toolbar.spec.mjs draft-scroll.spec.mjs`. Перевірити desktop/mobile, передзапускову модель, збереження без загального dialog, затриманий і втрачений POST, серверний cancel і відновлення плану після reload. Тести не виконують реальний inference; наявність процедури не означає її виконання.

WORKSPACE-TELEMETRY-S01: у `workspace-telemetry.spec.mjs` сценарії `plan/brief/draft/prose shows its model and warning before a single-click start`, а також `draft displays editor and planned calls before starting` перевіряють ролі, попередження, UA/EN і зміну ліміту. `editor-toolbar.spec.mjs` (`editor buttons share one row with the model line under the primary button`) перевіряє, що на широкому екрані кнопки матеріалу й основна дія стоять в одному ряду, а рядок моделі — під основною кнопкою в межах панелі. WORKSPACE-TELEMETRY-S02: у `workspace-cancel.spec.mjs` сценарії `stop during reconciliation is not lost`, `stopping readiness restores controls without a settings error`, `unknown enqueue is not shown as cancelled and Stop fences it` та інші перевіряють конкретні гонки. WORKSPACE-TELEMETRY-S03: `sidebar retains the planned model after reload` і `legacy run with no saved plan is explicitly unknown`. R20-WORKSPACE-S08: `draft-scroll.spec.mjs` (`creating a draft from the end of a long brief opens the draft from its top`) прокручує довге завдання до кінця, запускає чернетку синтетичним письменником і перевіряє, що верх матеріалу стоїть одразу під закріпленою областю, а перший абзац видно, на desktop і mobile; `a draft whose top is already in view does not move the page` перевіряє, що сторінка з уже видимим верхом матеріалу не прокручується. Playwright тести перелічено тут, бо структурна матриця індексує Python testcase, а не browser test names.

<a id="workspace-speed"></a>
## Швидкість відповіді робочого простору

Запустити `python scripts/workspace_bench.py --data <копія data> --story <id-префікс> --json` на копії робочих даних (не на робочій базі) і `python scripts/workspace_bench.py --synthetic 300 --workdir <нова тека> --json`. Синтетичний твір отримує локальні ролі зі стандартними промптами, тому readiness `brief`/`scene` має доходити до побудови контексту (`ready=true`) без викликів моделей; теку можна повторно використати лише для того самого числа сцен і завершеної побудови, інакше скрипт завершується з кодом 2 (`synthetic_mismatch`/`synthetic_incomplete`/`synthetic_ambiguous`). Для базового прогону скопіюйте теку до запуску старого коду. Порівняти `digest` із базовим прогоном до змін: він має збігатися. Потім у браузері виміряти від кліку до завершення останнього API-запиту: запустити `python -m storygen.server --data-dir <копія data або C:/tt/bench300r> --env-file <порожній файл>` (порожній env-файл не дає завантажити `.env` проєкту й ключі), відкрити сторінку у вбудованому браузері, обгорнути `window.fetch` лічильником запитів у польоті й міткою часу останнього завершеного запиту, а для відкриття твору використати `performance.getEntriesByType('resource')` після перезавантаження. Дії: «вибір сцени» (кілька різних сцен, у т.ч. пізніша), «перевірка готовності первинної дії» (запит `readiness?operation=…`, входить у вибір сцени), «розгорнути додаткові команди» (readiness усіх 9 операцій, на 300 сценах — на пізній сцені), «відкриття твору»; не менше 3 повторів, медіана й діапазон, перший холодний клік записати окремо. Цілі: 68 сцен — не більше 1 с, 300 синтетичних — не більше 3 с. Збереження вимірювати лише на окремій копії, яка не порівнюється з digest бенчмарку. Тексти не друкувати: лише ID, коди й час. Результат залежить від машини, тому процедура ручна; наявність процедури не означає її виконання. Виконано 08.11.2026 (код `08218e7`): цілі не досягнуто (відкриття твору 3,2–3,5 с на 68 і 5,4–5,9 с на 300; вибір сцени до 1,08 с на 68; розгортання всіх операцій 5,3–5,6 с на пізній сцені 300), збереження не вимірювалося. Виконано 21.11.2026 (гілка `claude/workspace-speed`, #39) на синтетичних 300 сценах, старий і новий код на окремих свіжих копіях: відкриття твору 9,7–10,2 → 5,4–5,5 с, вибір сцени 5,5–9,1 → 2,3–3,0 с, усі операції на сцені 290 11,5–11,9 → 1,3–1,7 с, збереження плану 16,1–16,6 → 7,3–8,0 с; цілі відкриття й збереження не досягнуто. Копія 68 сцен (старий → новий код): відкриття 2,94–3,14 → 2,75–3,01 с, вибір сцени 1,05–2,12 → 0,91–1,93 с, усі операції 1,87–1,95 → 1,43–1,55 с, збереження 3,30–3,45 → 2,95–3,09 с; ціль 1 с не досягнуто. Виконано 21.11.2026 після спільного знімка (PERF-001-S06, гілка `claude/workspace-speed-2`): 68 сцен — відкриття 2,65–2,99 → 1,24–1,32 с одразу після запису плану (запис робиться перед кожним відкриттям, щоб виміряти нове покоління) і 0,43–0,56 с без змін, запис 0,55 → 0,02 с; 300 сцен — 4,84–5,00 → 1,95–2,03 с після запису й 0,45–0,49 с без змін; на 68 сценах ціль 1 с для першого відкриття після запису не досягнуто. Відкриття вимірюйте окремо після запису й без змін між відкриттями: спільний знімок живе до наступного запису. Якщо `backup` відмовляє через перевірку цілісності, копію закритої теки робіть лише читанням (SQLite backup з read-only з'єднання й копіювання `stories` без `.env`), не змінюючи оригіналу. Для збереження фіксуйте окремо тривалість самого запису (resource timing) і всіх запитів оновлення. Виміри й причини — у SPEC.MD (PERF-001) і журналі виконання.

<a id="mcp-real-client"></a>
## Приймання MCP-клієнта з реальним чат-клієнтом

MCP-BRIDGE-S07. Встановити extra `pip install -e ".[mcp]"` і запустити Obscura на копії даних або на новому каталозі: `python -m storygen.server --data-dir <тека>`. Зареєструвати `storygen-mcp` у клієнті за інструкцією сторінки сайту «Чат-клієнти (MCP)» (`docs/site/uk/mcp.md`): Claude Code — `claude mcp add --scope user obscura -- <тека>\.venv\Scripts\storygen-mcp.exe`, Claude Desktop — запис у `mcpServers` файлу `claude_desktop_config.json`, Codex — `codex mcp add obscura -- …`. Перевірити також позначку «Зовнішній клієнт: …» в історії версій і рядку стану. Створити в Obscura нейтральний твір і в чаті попросити: (1) показати список творів і сцен; (2) імпортувати короткий план із двох сцен і картку персонажа; (3) прочитати контекст першої сцени й написати та зберегти чернетку. Перевірити в Obscura: чернетка поточна, попередня (якщо була) лишається в історії версій, `GET /api/versions/<id>` має `external_origin.client` з назвою клієнта. Потім змінити сцену в Obscura й попросити чат зберегти ще раз зі старим контекстом: чат має отримати помилку 409 з текстом сервера, а чернетка не змінюється. Зупинити Obscura й викликати будь-який інструмент: помилка «Obscura не запущено за адресою …». Пакет 1 (MCP-BRIDGE-S12–S15, #108), на тому самому нейтральному творі: (а) попросити чат прочитати чернетку сцени — він називає її текст; (б) дописати в Obscura речення в чернетку й зберегти, потім попросити чат додати фразу на початок чернетки — нова поточна версія містить і фразу чату, і речення автора; (в) попросити чат прочитати чернетку, потім змінити її в Obscura й попросити чат зберегти зміну без нового читання — чат отримує 409 «Чернетку змінено після того, як її прочитали…», чернетка не змінюється; (г) вставити в чернетку нейтральний текст довжиною понад 50000 символів (наприклад, повторений абзац) і попросити чат прочитати її повністю й назвати останнє речення — чат читає частинами й не повідомляє про обрізану відповідь; (д) попросити прочитати пам’ять сцени з пам’яттю — чат перелічує твердження. Модельні виклики клієнта йдуть з облікового запису власника, тож процедура ручна; наявність процедури не означає її виконання. Результат (дата, клієнт, версія коду) записати в журнал виконання.

<a id="build-edition-forms"></a>
## Форми рейтингу у виданні для Store

BUILD-EDITION-001-S06, BUILD-EDITION-001-S07. Автоматична частина — Playwright `tests/web/browser/build-edition.spec.mjs` (cases на desktop і mobile: рівні форми твору, збережений вищий рівень, панель сцени з пізньою відповіддю `app-info`, посилання шапки з перекладом, недоступний `app-info`); запуск окремим runner: `cd frontend && npx playwright test build-edition`. Сервер специфікацій перемикає видання тестовим маршрутом `/test-build-edition`. Ручна частина для справжньої позначки: у робочій копії створити тимчасовий файл `src/storygen/build_edition.json` з `{"edition":"store","report_url":"https://example.test/report"}` (не комітити) і запустити застосунок на новій теці даних: `python -m storygen.server --data-dir <тека>`. Створити твір і сцену з нейтральним текстом. У налаштуваннях твору й у рейтингу сцени: для сексуального змісту доступні лише рівні 0 і 1, для насильства й жорстких тем — 0, 1, 2; під формою видно підказку про межу; у шапці є посилання «Поскаржитися на результат». Записати рівень 2 сексуального змісту твору напряму в базу (`UPDATE stories SET payload=...`), перезавантажити сторінку: форма показує рівень 2, збереження без змін не дає помилки, збереження рівня 1 проходить, після чого рівень 2 зникає з переліку. Перемкнути мову інтерфейсу: підказка й посилання перекладаються. Видалити файл-позначку й переконатися, що форма знову має три рівні, а посилання зникло.

<a id="provider-key-store"></a>
## Ключ провайдера у сховищі Windows

SECURITY-002-S06, SECURITY-002-S07. Автоматична частина — Playwright `tests/web/browser/provider-key.spec.mjs` (вісім cases; восьмий — назва змінної `  venice_api_key ` зберігається як `VENICE_API_KEY`; на desktop і mobile: блок для хмарного й локального провайдера, збереження без значення в DOM і відповідях, назва змінної й середовище, машина без сховища, оцінювач, Enter у полі ключа, блокування під час запису); запуск окремим runner: `cd frontend && npx playwright test provider-key`. Сервер специфікацій тримає ключі в пам’яті й справжнього сховища не торкається. Ручна частина зі справжнім сховищем: встановити `keyring`, запустити застосунок на новій теці даних без `.env`, для ролі вибрати OpenRouter, у блоці «Ключ провайдера» ввести тестове значення (не справжній ключ) і зберегти: стан «Ключ збережено у сховищі Windows.», у «Диспетчері облікових даних» Windows є запис `OPENROUTER_API_KEY@Obscura` або `Obscura` з цим іменем користувача. Перезапустити застосунок: стан той самий, поле порожнє. Натиснути «Видалити збережений ключ»: стан «Ключ не задано.», запису в «Диспетчері облікових даних» немає.

<a id="model-picker-browser"></a>
## Каталог моделей у браузері

MODEL-005-S01, MODEL-005-S02. Автоматична частина — Playwright `tests/web/browser/model-picker.spec.mjs` (дев’ять cases на desktop і mobile: позначки й типовий фільтр приватності, режим JSON Schema із заблокованим фільтром, Venice-модель без Uncensored, ручний ID поза каталогом, очищення списку після зміни провайдера, вибір рядка з клавіатури, локальна модель із невідомою підтримкою в режимі JSON Schema вибирається й зберігається, сортування з `aria-sort`, рядки не змінюють модель під час збереження форми): `node frontend/node_modules/@playwright/test/cli.js test tests/web/browser/model-picker.spec.mjs --config frontend/playwright.config.mjs`. Цей зв’язок не є доказом виконання; фактичний запуск фіксується окремо.

<a id="writer-variant-browser"></a>
## Окрема модель письменника для сцен 0–1 у браузері

MODEL-001-S02. Автоматична частина — Playwright `tests/web/browser/writer-variant.spec.mjs` (два cases: перемикач «Окрема модель для сцен рівня 0–1» відкриває власні поля, збереження пише `low_rating_variant` з лімітами, відновлення після reload, зняття перемикача зберігає `null`; модель варіанта без Uncensored отримує власний блок згоди для ролі письменника): `node frontend/node_modules/@playwright/test/cli.js test tests/web/browser/writer-variant.spec.mjs --config frontend/playwright.config.mjs`. Цей зв’язок не є доказом виконання; фактичний запуск фіксується окремо.

<a id="openrouter-reasoning-browser"></a>
## Поле Reasoning OpenRouter у браузері

OPENROUTER-REASONING-S04. Автоматична частина — Playwright `tests/web/browser/openrouter-reasoning.spec.mjs`, два cases. (1) Роль планувальника з OpenRouter і збереженим `low`: поле видно й воно показує `low` до завантаження каталогу; перемикання на local ховає поле, а збереження прибирає `openrouter_reasoning_effort` з ролі. (2) Із синтетичним каталогом: для моделі з обов'язковим reasoning варіанти — типове, `low`, `high`, `max` без «Вимкнено»; для моделі без рівнів — типове й «Вимкнено»; вибране `none` зберігається. Запуск із кодом робочого дерева (тестовий сервер інакше імпортує editable-встановлення): `cd frontend; $env:PYTHONPATH='<worktree>\src'; npx playwright test ../tests/web/browser/openrouter-reasoning.spec.mjs`. Прогін 22.11.2026 на гілці `claude/openrouter-reasoning` у повному наборі: 475 passed, 6 skipped, 1 failed — `workspace-layout.spec.mjs` «full screen mode…», який окремо пройшов двічі на гілці й раз на main, тобто нестабільний і не пов'язаний зі зміною. Після додавання case (2): `openrouter-reasoning`, `writer-variant`, `model-picker`, `model-policy`, `local-thinking` — 38 passed.

<a id="scene-delete-browser"></a>
## Видалення сцени зі списку в браузері

WORKSPACE-TOOLS-S05. Автоматична частина — Playwright `tests/web/browser/scene-delete.spec.mjs` (три cases: на desktop іконка стоїть у правому краї рядка обраної сцени, переходить за вибором, після підтвердження сцена зникає зі списку й з’являється в кошику сцен; з незбереженим текстом клік показує причину й не відкриває підтвердження; на mobile лишається підписана кнопка під редактором, а іконки не видно). Запуск: `cd frontend; ./node_modules/.bin/playwright test ../tests/web/browser/scene-delete.spec.mjs`. Прогін 12.11.2026 на гілці `claude/scene-delete-button`: 3 passed, 3 skipped (cases іншого проєкту).

<a id="model-limits-browser"></a>
## Межі моделі з каталогу у формі налаштувань

MODEL-005-S03. Автоматична частина — Playwright case «limits above the chosen model caps block the save until fixed» у `tests/web/browser/model-picker.spec.mjs` (поле резерву відповіді отримує `max` з каталогу, значення понад межу показує пояснення й не надсилає PUT, допустиме значення зберігається): `node frontend/node_modules/@playwright/test/cli.js test tests/web/browser/model-picker.spec.mjs --config frontend/playwright.config.mjs`. Цей зв’язок не є доказом виконання; фактичний запуск фіксується окремо.

<a id="edit-pass-limit-browser"></a>
## Максимум проходів редактури в налаштуваннях редактора

EDIT-LOOP-REVIEW-S02. Автоматична частина — Playwright `tests/web/browser/edit-pass-limit.spec.mjs` (поле «Максимум проходів редактури» видиме у формі редактора на сторінці налаштувань, типово 5; збережене значення 3 повертає API налаштувань, а оцінка біля основної дії на вкладці «Чернетка» показує до 3 викликів; поля в робочій області немає): `node frontend/node_modules/@playwright/test/cli.js test tests/web/browser/edit-pass-limit.spec.mjs --config frontend/playwright.config.mjs`. Цей зв’язок не є доказом виконання; фактичний запуск фіксується окремо.

<a id="model-policy-browser"></a>
## Згода й позначка відмови в браузері

MODEL-003-S02, MODEL-003-S03, MODEL-004-S01. Автоматична частина — Playwright `tests/web/browser/model-policy.spec.mjs` (шість cases на desktop і mobile: згода для моделі OpenRouter записується одразу й не переходить на іншу модель, Venice без Uncensored показує галочку, а локальна модель — ні, збережена модель Venice не показує попередження до завантаження списку моделей, збій запиту згоди лишає попередній стан із помилкою, записана відмова показує червоне повідомлення зі зняттям і вибором іншої моделі, налаштування класифікації мають блок згоди для ролі редактора): `node frontend/node_modules/@playwright/test/cli.js test tests/web/browser/model-policy.spec.mjs --config frontend/playwright.config.mjs`. Цей зв’язок не є доказом виконання; фактичний запуск фіксується окремо.

<a id="book-structure-browser"></a>
## Структура книги в браузері

BOOK-STRUCTURE-S06, BUILD-EDITION-001-S08. Автоматична частина — Playwright `tests/web/browser/book-structure.spec.mjs` (п’ять cases на desktop і mobile: список сцен структурованої книги згрупований заголовками частин і арок, а на телефоні — групами вибору сцени; пласка книга без заголовків; поле «Арка» в параметрах сцени зберігає вибір одразу; прапорець «Сцена зустрічі з арками» зберігає другу арку сцени, вона лишається після перезавантаження, а основна арка іншої частини знімає зустріч; панель «Структура книги» перейменовує частину одним збереженням; у виданні store структурована книга показує банер лише для читання й не має панелі): `node frontend/node_modules/@playwright/test/cli.js test tests/web/browser/book-structure.spec.mjs --config frontend/playwright.config.mjs`. Цей зв’язок не є доказом виконання; фактичний запуск фіксується окремо.

<a id="memory-merge-browser"></a>
## Вікно злиття пам’яті в браузері

MEMORY-MERGE-S04. Автоматична частина — Playwright `tests/web/browser/memory-merge.spec.mjs` (шість cases на desktop і mobile на нейтральному прикладі: дві арки по-різному вдягають героїню перед сценою зустрічі; вікно показує голови з арками й рядок конфлікту, кнопка вимкнена без вибору; вибір голови підтверджує злиття й стан стає «Актуальне»; власне значення зберігається; після зміни ревізії твору іншим запитом відмова лишає вибір, а повторне натискання проходить; неготова сцена показує «Відкрити злиття пам’яті», яка відкриває вікно; стрілки клавіатури перемикають значення, не гублячи фокус): `node frontend/node_modules/@playwright/test/cli.js test tests/web/browser/memory-merge.spec.mjs --config frontend/playwright.config.mjs`. Платний запуск моделі ця перевірка не робить. Цей зв’язок не є доказом виконання; фактичний запуск фіксується окремо.

<a id="flashback-browser"></a>
## Спогад у браузері

STORY-TIME-S07. Автоматична частина — Playwright `tests/web/browser/flashback.spec.mjs` (три cases на desktop і mobile на нейтральному прикладі: прапорець «Спогад» у параметрах сцени зберігається, а на desktop у списку сцен з’являється позначка «спогад»; сцена з `Початок: Рік -2 (спогад)` має прапорець увімкненим і недоступним із поясненням; панель «Структура книги» показує підказку «Початок арки невідомий» біля арок без відомого початку, коли в книзі є спогад). Запуск: `cd frontend; ./node_modules/.bin/playwright test --grep "flashback|unknown start"`. Прогін 13.11.2026 на гілці `claude/story-flashbacks`: 6 passed. Цей зв’язок не є доказом виконання наступних змін; фактичний запуск фіксується окремо.

<a id="scene-narrator"></a>
## Оповідач у картці сцени

SCENE-NARRATOR-S07. Автоматична частина — Playwright `tests/web/browser/scene-narrator.spec.mjs` (три cases на desktop і mobile на нейтральному творі з картками: вибір «Перша особа» й героя в параметрах сцени зберігається в полі `narrator`; герой поза складом сцени дає під полем попередження «Оповідача немає серед учасників сцени»; сцена з рядком плану `Оповідач: Лєра, перша особа` показує його значення у вимкнених полях із поясненням). Запуск: `cd frontend; npx playwright test ../tests/web/browser/scene-narrator.spec.mjs`. Прогін 20.11.2026 на гілці `claude/scene-narrator`: 6 passed. Платний запуск моделі ця перевірка не робить. Цей зв’язок не є доказом виконання наступних змін; фактичний запуск фіксується окремо.

<a id="timeline-summaries-panel"></a>
## Панель підсумків хронології

MEMORY-SUMMARY-S07. Автоматична частина — Playwright `tests/web/browser/timeline-summaries.spec.mjs` (три cases на desktop і mobile на нейтральному творі з 22 сцен і пам’яттю до сцени 21: панель пам’яті показує блок 1–10 «актуальний» з текстом і кнопками «Перебудувати»/«Редагувати» та блок 11–20 «немає підсумку» з кнопкою «Створити підсумок» без редагування; збережене виправлення заміняє текст; якщо іншу голову опубліковано раніше, збереження показує конфлікт і лишає набраний текст у полі): `node frontend/node_modules/@playwright/test/cli.js test tests/web/browser/timeline-summaries.spec.mjs --config frontend/playwright.config.mjs`. Платний запуск моделі ця перевірка не робить. Цей зв’язок не є доказом виконання; фактичний запуск фіксується окремо.

<a id="locations-panel"></a>
## Панель «Локації»

MEMORY-LOCATIONS-S07. Автоматична частина — Playwright `tests/web/browser/locations.spec.mjs` (три cases на desktop і mobile на нейтральному творі з двох сцен: розділ показує картки зі сценами й підказку «Квартира Джоржа» схоже на «Квартира Джорджа»; злиття після підтвердження прибирає підказку й показує «Злито в…», «Розділити» скасовує; опис зберігається, а після зміни з іншої вкладки збереження показує конфлікт і лишає набраний текст; збережений опис не робить наступну зміну типу запису в таблиці пам’яті конфліктом, а рядок пам’яті показує локацію): `node frontend/node_modules/@playwright/test/cli.js test tests/web/browser/locations.spec.mjs --config frontend/playwright.config.mjs` (з worktree — з `PYTHONPATH=<корінь>/src`). Платний запуск моделі ця перевірка не робить. Цей зв’язок не є доказом виконання; фактичний запуск фіксується окремо.

<a id="desktop-launcher"></a>
## Запуск без консолі та значок у треї

DESKTOP-001-S04, S07, S08 (і S01, S02 наживо). Запустити без консолі на тимчасовій теці: `./.venv/Scripts/pythonw.exe -m storygen.desktop --data-dir <тека з кирилицею в назві>`. Очікувано: відкривається окреме вікно Edge без вкладок і адресного рядка з бібліотекою; у теці даних з’являється прихована тека `.window`; у теці є `server.json` і `logs\obscura.log` з адресою сервера; у треї Windows є значок Obscura. Значок і кліки:
- значок — емблема Obscura (перо на винному тлі), а не кружечок; наведення миші показує підказку «Obscura», а не порожній блок;
- лівий клік по значку виводить те саме вікно наперед (нового вікна чи вкладки немає); згорнуте вікно розгортається; після закриття вікна лівий клік відкриває нове;
- посилання на інший сайт у вікні (наприклад, «Поскаржитися» у виданні Store) відкривається у звичайному браузері, а вікно лишається на Obscura;
- правий клік показує меню біля значка, «Відкрити Obscura» виділено жирним;
- Win+B, стрілками до значка, Enter показує вікно, Shift+F10 показує меню біля значка (не біля курсора миші);
- після `taskkill /f /im explorer.exe` і `start explorer.exe` значок з’являється знову.

Далі: «Тека творів» відкриває теку даних у Провіднику; «Вийти» закриває вікно, прибирає значок, завершує процес і видаляє `server.json`. Повторний запуск тієї самої команди, поки застосунок працює, лише виводить наперед те саме вікно. Після примусового завершення процесу (`taskkill` для `pythonw.exe`, вікно Edge лишається) наступний запуск стартує сам, попри залишений `server.json`, і закриває залишене вікно й відкриває одне нове (не два); «Вийти» закриває і його. Створена резервна копія (`storygen backup`) не містить `.window`.

<a id="store-package-build"></a>
## Збирання пакета для Microsoft Store

PACKAGING-001-S02, PACKAGING-001-S03, PACKAGING-001-S05. Встановити залежності збирання (`pip install -e ".[web,publication,local-tokens,desktop,build]"`) і мати `makeappx.exe`. Виконати `python scripts/build_store.py --out <порожня тека> --report-url https://example.test/report --skip-msix`: код 0, у теці є `BUILD-OK.json`; у `self-check.json` `ok=true`, `frozen=true`, `edition=store`, версія з `pyproject.toml`, усі сім перевірок пройдено, `package_data` каже «N файлів за маніфестом збірки». У `Obscura\_internal` немає `storygen-*.dist-info`. Запустити `<тека>\Obscura\Obscura.exe --data-dir <тимчасова тека> --no-browser` і перевірити, що `GET <адреса з server.json>/api/app-info` повертає `edition=store` з межею `sexual=1`, а сторінка `/` відповідає 200. Зворотні перевірки на копії збірки: дописати рядок у `_internal\storygen\storage\migrations\001_initial.sql` — `Obscura.exe --self-check <файл>` завершується з кодом 5 і називає файл; прибрати `_internal\storygen\build_edition.json` (і, якщо інтерпретатор його додав, `_internal\codex-rejected-cas.pem`) — код 5. Повне збирання: та сама команда без `--skip-msix`, з `--identity-name`, `--publisher`, `--publisher-display-name`, `--makeappx` (на інтерпретаторі з додатковими файлами — ще й `--allow-vendor-runtime`; без нього скрипт відмовляє); у теці результату з’являється `Obscura-<версія>.msix`, у якому є `Obscura.exe`, `AppxManifest.xml`, `THIRD-PARTY-NOTICES.txt`, `_internal/storygen/build_edition.json` і `_internal/storygen/build_manifest.json`. Останнє виконання: 11.11.2026, 30 с без MSIX (337 файлів, 78,9 МБ, 198 файлів даних, 52 компоненти в повідомленнях) і 32 с з MSIX (42,1 МБ) на робочому середовищі; того ж дня на офіційному CPython 3.12.10 в окремому середовищі — 37 с, 335 файлів, 75,2 МБ, MSIX 41,6 МБ, без `--allow-vendor-runtime`.

<a id="store-package-ci"></a>
## Збирання пакета в GitHub Actions

PACKAGING-001-S07. Відкрити запуск `store-build` для PR (або запустити вручну з вкладки Actions після злиття файла в `main`). Запуск зелений; в артефакті `store-build-reports` є `BUILD-OK.json` і `self-check.json` з `ok=true`, `frozen=true`, `edition=store` і версією з `pyproject.toml`; `THIRD-PARTY-NOTICES.txt` містить PyInstaller, `pyinstaller-hooks-contrib` і розділ `tokenizers` з повним текстом Apache-2.0 та ліцензіями crate Rust. Якщо в журналі немає попередження про `makeappx`, у тому ж артефакті є `Obscura-<версія>.msix`: відкрити його як ZIP і перевірити `AppxManifest.xml` (ідентичність `Obscura.CI`), три значки в `Assets/`, `obscura-mcp.exe` і теку `claude/`. Після відмови в артефакті є `BUILD-FAILED.txt` із причиною. Пакет із CI не підписаний і не встановлюється.

PACKAGING-001-S09. Ручний запуск (Actions → store-build → Run workflow) з трьома значеннями з Partner Center (Product identity: `Package/Identity/Name`, `Package/Identity/Publisher`, `Package/Properties/PublisherDisplayName`): у `AppxManifest.xml` з артефакту — саме ці `Name`, `Publisher` і `PublisherDisplayName`, а `DisplayName` дорівнює зарезервованій назві. Запуск із заповненими одним-двома полями або з `publisher` без `CN=` падає з `::error::` до збирання.

<a id="store-package-install"></a>
## Встановлення зібраного пакета (виконує власник машини)

PACKAGING-001, DESKTOP-001, STORE-MCP-001 наживо. Не виконано. Пакет збирати на офіційному CPython (`docs/packaging.md`) з ідентичністю з Partner Center; на машині зі Smart App Control — ручним запуском CI (PACKAGING-001-S09).

1. **Smart App Control.** Перевірити стан: «Безпека Windows» → «Керування програмами та браузером» → «Smart App Control» (або `HKLM\SYSTEM\CurrentControlSet\Control\CI\Policy\VerifiedAndReputablePolicyState`: 1 — увімкнено). Якщо вимкнено — далі шлях із власним сертифікатом (крок 2). Якщо увімкнено, він не пропускає програм, підписаних сертифікатом, який користувач сам додав у довірені: спробувати крок 2 і, якщо застосунок не запускається з повідомленням Smart App Control, перевіряти через приватний тестовий випуск (крок 3). Змінювати налаштування Smart App Control не треба: це рішення власника машини.
2. **Власний сертифікат.** У PowerShell від імені адміністратора створити самопідписаний сертифікат із суб’єктом, що дорівнює `--publisher` (`New-SelfSignedCertificate -Type Custom -Subject "CN=<назва>" -KeyUsage DigitalSignature -CertStoreLocation Cert:\CurrentUser\My -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3")`), підписати пакет (`signtool sign /fd SHA256 /sha1 <відбиток> <пакет>`; `signtool.exe` лежить поруч із `makeappx.exe`), експортувати сертифікат, додати його до «Довірені особи» локального комп’ютера й встановити пакет (`Add-AppxPackage <пакет>`). Наприкінці прибрати сертифікат із довірених.
3. **Приватний тестовий випуск у Partner Center.** Подати пакет у приватний (private audience) випуск, додати свій обліковий запис Microsoft до аудиторії, встановити застосунок за посиланням зі Store. Такий пакет підписує Microsoft, і Smart App Control його пропускає.
4. **Перевірки встановленого застосунку.** Застосунок запускається з меню «Пуск» без консолі й відкриває окреме вікно Obscura (без вкладок); лівий клік по значку виводить те саме вікно наперед; у `%USERPROFILE%\Obscura\.window` лежить профіль вікна, а в `%LOCALAPPDATA%\Packages\<пакет>\LocalCache` профілю немає; у треї є значок, меню мовою інтерфейсу Windows (українська — українською, інакше англійською), «Вийти» зупиняє застосунок; у налаштуваннях підключення можна зберегти й видалити тестовий ключ (не справжній) у сховищі Windows; назва змінної `venice_api_key` зберігається як `VENICE_API_KEY`; твори лежать у `%USERPROFILE%\Obscura`; рівень 2 сексуального змісту недоступний для запису, а твір із ним, відновлений з копії, експортується з позначкою `18+`.
5. **Чат-клієнти.** «Підключити Claude Code» реєструє міст і встановлює скіли: у новій сесії Claude Code `/obscura:start-story` доступний, `obscura-mcp.exe --self-check` друкує `guide: ok`. «Скіли для Claude Desktop» кладе п’ять ZIP у `%USERPROFILE%\Obscura\claude\skills`; один із них завантажується в Claude Desktop (Customize → Skills → Upload a skill).
6. **Підвал редактора (STORE-FOOTER).** У сцені з прозою під матеріалом немає «Параметрів запуску» й «Додаткових дій та автоматичного режиму»; «Статистика сцени» показує таблицю матеріалів і рядок «Поточна проза: … (… весь твір)»; «Історія та альтернативні версії» має три кнопки, а «Повернути цю версію» для старішої прози робить її поточною; на вкладці «Чернетка» ліворуч від основної дії є «Взяти як прозу».
7. **WACK.** Windows App Certification Kit для встановленого пакета без помилок; попередження записати.
8. Після видалення застосунку (`Remove-AppxPackage`) тека творів лишається.

<a id="series-browser"></a>
## Серії книг у браузері

SERIES-S07. Автоматична частина — Playwright `tests/web/browser/series.spec.mjs` (три cases на desktop і mobile: посилання «Серії» в бібліотеці й створення серії; екран серії з книгою за виходом, віссю хронології, недоступним «Видалити серію» і «Новою книгою серії», що відкриває книгу з рядком «Серія «…», книга 2»; панель серії в налаштуваннях книги зберігає серію, номер і `Початок`). Запуск із кодом робочої теки: `PYTHONPATH=<тека>/src;<тека>` і `cd frontend; npx playwright test series`. Вручну на нейтральній дописаній книзі 1: книга 2 серії показує «знімок актуальний»; правка пам’яті останньої сцени книги 1 дає «⚠ книга 1 змінилася»; «Оновити з попередньої книги» просить підтвердження й повертає «знімок актуальний». SERIES-S11 — ще два cases Playwright: приквел відкриває «Переглянути факти пізніших книг», бачить два записи з книгою-джерелом, позначає один «Минуле», лічильник «Змінено: 1», «Зберегти позначки» з підтвердженням дає «Позначки збережено» й зберігає лише цю позначку; екран серії показує в книги 3 «Джерела: «Перша книга», «Приквел 2»» і розгорнутий конфлікт одягу. Вручну: після збереження позначок пам’ять і завдання першої сцени приквела стають застарілими. Цей зв’язок не є доказом виконання; фактичний запуск фіксується окремо.

<a id="series-library-browser"></a>
## Серії в бібліотеці в браузері

SERIES-S12. Автоматична частина — Playwright `tests/web/browser/library-series.spec.mjs` (desktop і mobile: серія з біблією й двома книгами стоїть у бібліотеці групою із заголовком «Серія «…»», картки в порядку «біблія, книга 1, книга 2» з рядками «Серія «…», біблія світу» / «…, книга N»; перемикач мови на англійську змінює рядок на «Series «…», book 1» без перезавантаження; заголовок веде на екран серії). Запуск із кодом робочої теки: `PYTHONPATH=<тека>/src` і `cd frontend; npx playwright test library-series`. Цей зв’язок не є доказом виконання; фактичний запуск фіксується окремо.

<a id="series-bible-browser"></a>
## Біблія світу в браузері

SERIES-BIBLE-S06 і SERIES-BIBLE-S08. Автоматична частина — Playwright `tests/web/browser/series-bible.spec.mjs` (desktop і mobile: прапорець «Біблія світу» в налаштуваннях книги ховає номер і `Початок`, «Зберегти» дає стан `bible`, рядок під назвою «Серія «…», біблія світу», кнопки «Оновити з попередньої книги» немає; «Нова біблія світу» на екрані серії створює біблію, що стоїть окремим блоком зі станом «ще не має підсумку», вісь і «Поза віссю» без неї, кнопка зникає; у діалозі фактів приквела факт біблії без перемикача з поясненням «завжди минуле», «Усе — майбутнє» його не змінює) і `tests/web/browser/scene-without-plan.spec.mjs` (desktop і mobile: нова сцена звичайної книги й біблії — «Додати сцену», вкладка «Проза», текст, «Зберегти» → «Збережено», голова прози є). Запуск із кодом робочої теки: `PYTHONPATH=<тека>/src` і `cd frontend; npx playwright test series-bible scene-without-plan`. Вручну на нейтральній біблії: панель структури книги не має поля протагоніста. Цей зв’язок не є доказом виконання; фактичний запуск фіксується окремо.

<a id="tone-sample-browser"></a>
## Зразок звучання в налаштуваннях

STYLE-SAMPLE-001-S03. Автоматична частина — Playwright `tests/web/browser/tone-sample.spec.mjs` (desktop і mobile): поле «Зразок звучання» в «Профілі письма», лічильник «0 / 3000» → «18 / 3000», «Зберегти» дає «Профіль письма збережено», зразок повертається API й після перезавантаження. Запуск: `PYTHONPATH=<тека>/src;<тека>` і `cd frontend; npx playwright test tone-sample`. Вручну на нейтральному творі: після зміни лише зразка завдання сцени лишається без позначки «застаріло», а чернетка її отримує. Цей зв’язок не є доказом виконання; фактичний запуск фіксується окремо.

<a id="store-mcp-package"></a>
## Міст MCP з установленого пакета (виконує власник машини)

STORE-MCP-S04 наживо. Не виконано: потребує підписаного пакета й довіри до сертифіката, як у [встановленні зібраного пакета](#store-package-install). Зібрати, підписати й установити пакет за тією процедурою. У новому вікні PowerShell `obscura-mcp.exe --help` за псевдонімом друкує довідку `storygen-mcp` українською без помилки кодування. Вийти з Obscura через меню значка в треї й переконатися, що процесу `Obscura.exe` немає. Додати тимчасовий запис у Claude Code: `claude mcp add --scope user obscura-store -- obscura-mcp.exe`; у новій сесії Claude Code попросити список творів. Очікувано: Obscura запускається у трей без вікна консолі й без відкриття браузера, чат отримує список творів, а після закриття Claude Code значок у треї лишається. Повторний запит знаходить уже запущену Obscura без другого процесу. Прибрати тимчасовий запис (`claude mcp remove --scope user obscura-store`). Підключення кнопками (STORE-MCP-S08–S11), після запуску Obscura з меню «Пуск»:
1. **Claude Desktop.** У бібліотеці «Підключити до Claude» → «Підключити Claude Desktop». Очікувано:
   - повідомлення називає файл `claude_desktop_config.json`, а поруч лежить `claude_desktop_config.json.obscura-backup`;
   - у файлі змінився лише запис `obscura` з командою псевдоніма `…\WindowsApps\obscura-mcp.exe`.
2. **Перезапуск.** «Перезапустити Claude зараз» → підтвердити. Claude Desktop закривається й відкривається знову, а сесії Claude Code працюють далі.
3. **Перевірка в Claude Desktop.** Попросити список творів.
4. **Claude Code.** «Підключити Claude Code» → «Claude Code підключено разом зі скілами Obscura»; у `%USERPROFILE%\Obscura\claude\marketplace` є `obscura-version.txt` з версією пакета. У новій сесії Claude Code `claude plugin list` показує `obscura@obscura`; попросити «почни нову історію» — працює скіл `start-story` (питання по одному), і список творів відкривається (STORE-MCP-S15).
4a. **Скіли для Claude Desktop.** «Скіли для Claude Desktop» → відкривається `…\Obscura\claude\skills` з п’ятьма ZIP. У Claude Desktop: Settings → Capabilities → Code execution and file creation; Customize → Skills → «+» → Create skill → Upload a skill, завантажити `start-story.zip`. Скіл з’являється в списку; у новій розмові «почни нову історію» веде інтерв’ю за скілом (STORE-MCP-S16).
5. **Автозапуск і значок.** Значок Obscura є у треї: лівий клік відкриває сторінку, правий — меню біля значка. Вийти через «Вийти» в меню й попросити Claude продовжити історію: Obscura запускається сама у треї.
6. **Запасний шлях.** «Інший спосіб» → «Підготувати файл розширення», відкривається тека з `obscura.mcpb`. Перетягнути файл у Claude → Settings → Desktop app → Extensions → Install.
7. **Межа видання.** Попросити чат створити серію чи книгу з частинами: відповідь пояснює платну версію й дає посилання на запис.

Наприкінці:
- прибрати записи `obscura` (у Claude Desktop — з копії, у Claude Code — `claude mcp remove --scope user obscura`), розширення, плагін (`claude plugin uninstall obscura@obscura`, `claude plugin marketplace remove obscura`) і завантажені скіли Claude Desktop;
- прибрати сертифікат із довірених.

Цей зв’язок не є доказом виконання; фактичний запуск фіксується окремо.

<a id="claude-connect-browser"></a>
## Підключення до Claude в браузері

STORE-MCP-S08–S10. Автоматична частина — Playwright `tests/web/browser/claude-connect.spec.mjs` (desktop і mobile, маршрути `/api/connect/*` перехоплено, справжній Claude не зачіпається):
- «Підключити Claude Desktop» показує «Запис додано у …» без слова «підключено»;
- «Перезапущу сам» розкриває пояснення з «Quit»;
- «Перезапустити Claude зараз» питає підтвердження про відкриту розмову й показує «Claude Desktop перезапускається»;
- без файлу налаштувань «Підготувати файл розширення» показує кроки Settings → Desktop app → Extensions;
- без Claude Code блок показує команду й «Копіювати»;
- англійська локаль перекладає блок;
- «Скіли для Claude Desktop» показує теку й кроки Upload a skill; Claude Code зі скілами — «разом зі скілами Obscura», без скілів — команди `claude plugin` для копіювання (STORE-MCP-S15, S16).

Запуск із кодом робочої теки: `PYTHONPATH=<тека>/src` і `cd frontend; npx playwright test claude-connect`. Цей зв’язок не є доказом виконання; фактичний запуск фіксується окремо.

<a id="scene-insert-browser"></a>
## Нова сцена після відкритої в браузері

IMPORT-NUMBER-S03. Автоматична частина — Playwright `tests/web/browser/scene-insert.spec.mjs` (один case: у творі з двома нумерованими сценами відкрито першу, «Додати сцену» вставляє нову другою з заголовком «## Сцена 2: …», план наступної сцени отримує «Сцена 3», список на desktop показує «2. Полудень»). Запуск: `cd frontend; ./node_modules/.bin/playwright test ../tests/web/browser/scene-insert.spec.mjs`. Цей зв’язок не є доказом виконання; фактичний запуск фіксується окремо.

<a id="prose-accept-browser"></a>
## Прийняття всієї прози з меню твору

DATA-010-S02. Автоматична частина — Playwright `tests/web/browser/prose-acceptance.spec.mjs` (один case на desktop і mobile: дві сцени з ручною прозою під завданням автора, тож зв'язок завдання → проза неперевірений і проза чекає (VALID-LINKS); у меню твору пункт «Прийняти всю прозу як авторську» видимий, підтвердження називає «Ранок», «Вечір», після прийняття `GET /prose-acceptance` повертає порожній перелік, а пункт зникає; відкрита проза сцени «Ранок» після прийняття редагується й зберігається без 409). Запуск: `cd frontend; ./node_modules/.bin/playwright test -c playwright.config.mjs ../tests/web/browser/prose-acceptance.spec.mjs`. Цей зв’язок не є доказом виконання; фактичний запуск фіксується окремо.

<a id="claude-skills"></a>
## Скіли Obscura для Claude: сценарії поведінки

CLAUDE-SKILLS-S04…S09. Поведінку моделі pytest детерміновано не перевірить, тож сценарії проганяються сесіями `claude -p` на ізольованому стенді:
- окрема тека даних у `C:/tmp`;
- вільний порт;
- `--strict-mcp-config`;
- плагін з `integrations/claude/obscura` через `--plugin-dir`.

Робочого екземпляра Obscura й MCP-налаштувань автора прогони не торкаються.

Запуск (у середовищі має бути `claude` з входом в акаунт):

```
python integrations/claude/tools/run_scenarios.py --scenario S04-a --scenario S04-b --scenario S05-a --scenario S05-b --scenario S06 --scenario S07-a --scenario S07-b --scenario S08-a --scenario S08-b --scenario S09-a --scenario S09-b --work C:/tmp/<назва> --model sonnet
```

Опис сценаріїв і тверджень — `integrations/claude/obscura/evals/*.json` (формат `skill-creator`). Скрипт друкує рядок JSON на сценарій: `passed`, `problems`, `cost_usd`, послідовність інструментів. У `C:/tmp/<назва>/<сценарій>/` лишаються `run.jsonl`, `text.md` і `summary.json`.

Автоматично перевіряються послідовність викликів і кінцевий стан стенда. S08-b звіряє налаштовані ролі з живим каталогом `https://openrouter.ai/api/v1/models`, тож потребує мережі; сервер стенда отримує фіктивний `OPENROUTER_API_KEY` лише у своєму середовищі. Вручну за `text.md` перевіряються:
- одне питання за раз;
- рядок прогресу після кожного етапу;
- мова відповіді.

**Правило провалу:**
- **поведінка скіла** — PR блокується, доки скіл не виправлено;
- **інфраструктура** (сервер, мережа, ліміт акаунта) — повторний прогін із записом причини;
- **провал, що не повторюється у двох повторних прогонах,** — записується в журнал як нестабільність і PR не блокує.

Вартість у `cost_usd` — оцінка за цінами API; за підпискою claude.ai вона витрачає ліміт підписки. Цей розділ — процедура, а не доказ виконання. Фактичні прогони (дата, коміт, модель, результат) записуються в журнал виконання R-35.

<a id="broken-text-browser"></a>
## Банер пошкоджених літер у редакторі

BROKEN-TEXT-S05. Автоматична частина — Playwright `tests/web/browser/broken-text.spec.mjs` (один case на desktop і mobile: чернетка з двома «�» показує банер «У тексті пошкоджених символів «�»: 2.», «До наступного» виділяє «�», після заміни тексту банер зникає). Запуск: `PYTHONPATH=<тека>/src`, `cd frontend; ./node_modules/.bin/playwright test -c playwright.config.mjs ../tests/web/browser/broken-text.spec.mjs`. Цей зв’язок не є доказом виконання; фактичний запуск фіксується окремо.

<a id="codex-connect-ui"></a>
## Codex: бібліотека

У frontend виконати npx playwright test codex-connect.spec.mjs claude-connect.spec.mjs із PLAYWRIGHT_BROWSERS_PATH до тестового Chromium. Стенд server.py створює тимчасові HOME/USERPROFILE/CODEX_HOME до create_app (Windows: C:/tmp), synthetic gateways і MemorySecretStore. Перевірки desktop/mobile: незалежні дії, збережено проти підключено, конфлікт/partial з буквальними довгими шляхами, UA/EN попередніх результатів, Store skills disabled/MCP enabled, keyboard details, pending обох кнопок і clipboard fallback. Додаткові регресії: згорнутий блок не робить status GET, перше розгортання робить один; незалежні помилки статусу не блокують іншу дію; install_busy та unsafe_install_root мають окремі пояснення після UA/EN. M3: Codex lists each skill once and preserves changed versus current перевіряє first install, unchanged і частковий managed update — кожна назва один раз із ознакою installed/current після UA/EN; partial/conflict перевіряються окремим сценарієм. Cross-review регресія Codex keeps path failures out of skill names and retains partial state: код linked_path не показано як назву скіла; локалізована причина шляху й стан partial зберігаються після UA/EN. Помилка будь-якого сценарію — провал. Наявність цієї процедури не є виконанням.

<a id="codex-clients"></a>
## Codex: два клієнти без моделей

**Чинне приймання206 після погодженого поділу:** [B1 у окремому локальному Windows-акаунті](codex-checkout-acceptance.md). Потрібні штатна user .agents/skills і CLI/GUI. B1 виконано: PASS, запуск20261118-164659-b6b2f8; докази наведено нижче. B2/B3 (Store runtime/license) передано R-39 PR2 й вони не є критеріями злиття206. Нижче збережено попередню діагностичну процедуру та історичні результати до поділу.

1. Зафіксувати --version CLI та app/resources/codex.exe, для кожного експортувати app-server generate-json-schema --out у C:/tmp.
2. Створити нові fixture repo, home, CODEX_HOME; file auth, жодного auth.json, API-key/token env або OS keyring. Сервер — scripts.skills_stand.start_stand з порожнім env_file і fail-keyring. Не запускати GUI автора.
3. Перевірити джерела home-resolution перед запуском: [Codex 0.166 host roots](https://github.com/openai/codex/blob/rust-v0.166.0/codex-rs/ext/skills/src/host_roots.rs), [app 0.169 alpha host roots](https://github.com/openai/codex/blob/rust-v0.169.0-alpha.11.1/codex-rs/ext/skills/src/host_roots.rs). Обидва використовують dirs6: Windows home — FOLDERID_Profile, HOME/USERPROFILE не ізолюють .agents. Без окремої згоди на читання справжніх скілів потрібен окремий Windows-профіль/VM. Згода на читання не дозволяє встановлення у справжній профіль.
4. Установити генератором у fixture home/.agents/skills; repo-scope — копія у fixture repo/.agents/skills. За дозволу лише читання справжнього профілю user-scope перевіряти через сумісний тимчасовий CODEX_HOME/skills; це не перевірка встановлення у системну .agents. Точну системну .agents перевіряти в окремому Windows-профілі/VM.
5. Запустити app-server stdio з fixture cwd; initialize підтверджує codexHome; initialized; skills/list(cwds,forceReload=true) підтверджує п'ять obscura-* paths і відповідний scope, errors=[]. У звіт не включати імена/вміст інших скілів.
6. thread/start(cwd,ephemeral=true,approvalPolicy=never,sandbox=read-only); mcpServerStatus/list(threadId,serverName=obscura,detail=toolsAndAuthOnly); mcpServer/tool/call(server=obscura,threadId,tool=list_stories,arguments={}). Очікується isError=false і порожній нейтральний список. Ніколи turn/start, codex exec або модельні задачі. Завершити backend і стенд.
7. Окремо перевірити GUI discovery у безпечному профілі та чинний Store freeze/self-check за packaging-процедурою. Наявність tomlkit у PYZ не доводить успішний запуск. Application Control не обходити.

Фактичне виконання 18.11.2026: CLI 0.166.0 і app backend 0.169.0-alpha.11.1 — PASS repo-scope (.agents), user-scope (CODEX_HOME/skills), MCP catalog і list_stories; errors=0, моделей=0. Власник окремо дозволив читання справжніх скілів. Артефакти: C:/tmp/obscura-codex-accept-7we6gbos/results.json і schema обох версій. GUI discovery та системна .agents на згенерованих скілах НЕ перевірені.

Store: C:/tmp/obscura-codex-store-20261118, чинний build_store.py --edition store --skip-msix --report-url https://obscurawriter.com/report.html --waitlist-url https://obscurawriter.com/paid.html. PYZ містить tomlkit і routes_codex_connect; окремий чинний license gate також НЕ пройшов: у frozen TOC знаходить pyinstaller/pyinstaller-hooks-contrib і відхиляє GPL-family; diagnostic-notices.txt не створений. Ліцензію самого tomlkit перевірено окремо, це не замінює gate збірки. Збірка НЕ пройшла runtime gate: Windows Application Control блокує новий obscura-mcp.exe, self-check не виконався; BUILD-FAILED.txt лишається. Не обходили політику, не публікували MSIX. Це невиконаний критерій до злиття.


### B1 — завершене checkout-приймання18.11.2026

B1 виконано 18.11.2026, запуск 20261118-164659-b6b2f8 (15:46:59–15:49:25 UTC, 16:46–16:49 Europe/Warsaw), checkout027434b. Штатний установник встановив усі п’ять скілів у C:/Users/Test/.agents/skills; MCP configured у Test/.codex/config.toml зі штатною копією. CLI0.166.0 та app backend0.169.0-alpha.11.1 підтвердили ті самі п’ять user-scope шляхів, discovery_errors=0,27tools incl get_guide, list_stories=[] без помилки; model_turns=0. Власник підтвердив у GUI всі п’ять скілів і enabled obscura. Загальний automatic/status=PASS. Доказ: docs/verification/evidence/2026-11-18-codex-b1.json (копія без Windows SID, SHA-256 оригіналу збережено). Це закриває checkout B1, але не доводить Store runtime/license чи літературну якість. Тестову Obscura після перевірки зупинено; її збережений у Test MCP URL належить цьому завершеному тестовому запуску.

<a id="store-footer-browser"></a>
## Підвал редактора й основна панель (STORE-FOOTER)

R20-WORKSPACE-S07, STORE-FOOTER-S01, STORE-FOOTER-S02. Автоматична частина — Playwright `tests/web/browser/store-footer.spec.mjs` (на вкладці «Чернетка» «Взяти як прозу» стоїть ліворуч від основної дії й зберігає чернетку як прозу з її форматом; у виданні Store немає «Параметрів запуску», «Додаткових дій» і розбору контексту; історія Store показує лише текстові версії й повертає версію з її форматом) і `tests/web/browser/scene-delete.spec.mjs` (у підвалі немає «Видалити сцену»): `node frontend/node_modules/@playwright/test/cli.js test tests/web/browser/store-footer.spec.mjs tests/web/browser/scene-delete.spec.mjs --config frontend/playwright.config.mjs`. Браузерний сервер імпортує пакет із `PYTHONPATH`, тож у worktree задайте `PYTHONPATH=<worktree>/src`. Цей зв’язок не є доказом виконання; фактичний запуск фіксується окремо.

<a id="site-consent"></a>
## Банер згоди й теги Google на живому сайті (DOCS-SITE-S11)

Після злиття PR з розділом `ads` у `docs/site/site.json` і публікації сайту, у вікні InPrivate браузера з інструментами розробника (вкладка «Мережа») або з Google Tag Assistant:

1. Відкрити `https://obscurawriter.com/` — банер з рівними кнопками; у «Мережі» немає запитів до `googletagmanager.com`, `google-analytics.com`, `googleadservices.com`, `doubleclick.net`.
2. «Відхилити», перейти на іншу сторінку — банера немає, запитів до Google немає.
3. «Налаштування cookies» → «Прийняти» — з'являється запит `gtag/js?id=AW-…`, далі запити GA4 (`collect`); у Tag Assistant стан згоди `granted` для всіх чотирьох типів.
4. Записатися в список очікування на `paid.html` нейтральною тестовою адресою — після повернення на `#waitlist-ok` у Tag Assistant одна подія конверсії Google Ads і подія `sign_up` GA4; перезавантаження вкладки другої конверсії не дає. Тестовий запис видалити з D1 за `docs/waitlist.md`.
5. «Налаштування cookies» → «Відхилити» — сторінка перезавантажується, cookies `_ga`, `_ga_*`, `_gcl_au` на `obscurawriter.com` зникли, запитів до Google немає.

Результат (дата, браузер, що побачено) записати в журнал виконання.

<a id="plan-preamble-panel"></a>
## Панель «Загальні вказівки з плану»

PLAN-PREAMBLE-S02, PLAN-PREAMBLE-S04. Запустіть Obscura з порожньою текою даних, створіть твір і імпортуйте нейтральний план із назвою, рядком вказівок і двома сценами `## Сцена N: …`.
1. Налаштування → «Письмо»: панель показує назву й вказівки; кнопка «Зберегти» неактивна, доки текст не змінено; загальна кнопка збереження розділу лишається «Без змін».
2. Додайте рядок до вказівок і збережіть: з’являється повідомлення про збереження (сцени з попереднім вступом потребують перевірки); після перезавантаження сторінки поле показує новий текст.
3. Додайте рядок `## Тон` і збережіть: повідомлення пояснює, що вступ змінив би поділ на сцени (англійською в англійському інтерфейсі), а введений текст лишається в полі.
4. У творі без плану панель неактивна з поясненням «Імпортуйте план із заголовками сцен».
Цей зв’язок не є доказом виконання; фактичний запуск фіксується окремо.

<a id="docx-word"></a>
## Рукопис DOCX і RTF у Word (EXPORT-DOCX-S05)

Потрібен Microsoft Word. Створіть нейтральну тестову книгу з двома частинами (одна без назви), трьома сценами з прозою (курсив, жирний, табуляція) і карткою з автором; експортуйте «Рукопис Word (.docx)» і «Рукопис RTF (.rtf)».
1. Відкрийте DOCX: Word не пропонує відновити файл; титул, кожна частина й сцена на окремій сторінці; область навігації показує частини й сцени двома рівнями; номер сторінки внизу.
2. «Вставлення → Закладка», увімкніть «Приховані закладки»: є закладка `_os…` на кожну сцену.
3. Увімкніть рецензування, змініть слово в заголовку сцени й в абзаці, додайте примітку, збережіть як новий DOCX.
4. Відкрийте збережений файл як zip: `word/document.xml` містить ті самі імена закладок, `w:ins`/`w:del` і `word/comments.xml`; `docProps/custom.xml` — `ObscuraStoryId` і `ObscuraExportId`.
5. Відкрийте RTF: кирилиця, лапки, курсив і жирний на місці, частини й сцени з нової сторінки.
Цей зв’язок не є доказом виконання; фактичний запуск фіксується окремо.

<a id="link-decision-browser"></a>
## Рішення автора для зв'язків сцени

VALID-LINKS-S08, VALID-MEMORY-S08. Автоматична частина — Playwright `tests/web/browser/link-decision.spec.mjs` (desktop і mobile), три випадки на synthetic server `tests/web/browser/server.py`:
1. Сцена з завданням і прозою автора: панель `#link-attention` показує «Затвердити завдання» й «Затвердити відповідність»; після натискань обидва зв'язки валідні з джерелом `author`, а лишається один рядок «У сцени ще немає пам’яті…» з кнопкою «Створити пам’ять».
2. Фікстура `/test-memory-decision`: проза першої сцени змінена після пам'яті, readiness чернетки другої сцени відмовляє через пам'ять попередньої сцени. На вкладці пам'яті першої сцени панель показує «Пам’ять не підтверджена: прозу змінено після неї.» з «Залишити попередню пам’ять» і «Створити нову пам’ять»; після «Залишити попередню пам’ять» рядок зникає, З3 валідний з джерелом `author`, а чернетка другої сцени готова до запуску.
3. Фікстура без пам'яті першої сцени: на другій сцені панель називає «Попередня сцена «Ранок» не має пам’яті»; «Створити пам’ять» відкриває першу сцену й показує діалог запуску, а «Скасувати» не створює запуску.
Запуск: `cd frontend; ./node_modules/.bin/playwright test -c playwright.config.mjs ../tests/web/browser/link-decision.spec.mjs` з абсолютним `PYTHONPATH=<робоча копія>/src` (відносний `../src` може підхопити `storygen` іншої копії). Цей зв’язок не є доказом виконання; фактичний запуск фіксується окремо.

<a id="card-invalidation-browser"></a>
## Діалог після зміни карток і локацій

VALID-CARDS-S04, VALID-CARDS-S05. Автоматична частина — Playwright `tests/web/browser/card-invalidation.spec.mjs` (desktop і mobile) на фікстурі `/test-card-invalidation` (валідна сцена з персонажем «Олена» й локацією «Пагорб»):
1. На сторінці персонажів змінити відомість Олени й зберегти: діалог «Змінено картки: Олена. Позначити залежні сцени як неперевірені? Сцен: 1.»; «Так» показує «Залежні сцени позначено як неперевірені.», а після повернення сцена «Не перевірено» і З1 `unchecked`.
2. Те саме з «Ні»: діалог зникає, сцена лишається «Валідна».
3. На вкладці пам'яті в розділі «Локації» зберегти новий опис «Пагорб»: діалог «Змінено локації: Пагорб. … Сцен: 1.»; «Так» робить сцену «Не перевірено».
Запуск: `cd frontend; ./node_modules/.bin/playwright test -c playwright.config.mjs ../tests/web/browser/card-invalidation.spec.mjs` з абсолютним `PYTHONPATH=<робоча копія>/src`. Цей зв’язок не є доказом виконання; фактичний запуск фіксується окремо.

<a id="scene-audit-browser"></a>
## Перевірка сцени Ревізором

VALID-AUDITOR-S01, VALID-AUDITOR-S07, VALID-RUN-S01, VALID-RUN-S02. Автоматична частина — Playwright `tests/web/browser/scene-audit.spec.mjs` (desktop і mobile) на synthetic server `tests/web/browser/server.py`; фікстура `/test-scene-audit` має власного локального Ревізора `synthetic-auditor`, а фейковий шлюз відповідає на етапи `audit_*` двома розбіжностями з цитатами (упевненість 35):
1. Валідна сцена фікстури `/test-card-invalidation`: бейдж «Валідна», кнопки «Перевірити сцену» немає.
2. Сцена фікстури `/test-scene-audit`: кнопка «Перевірити сцену» видима; перегляд показує «Зв’язки до перевірки: завдання, проза…» і модель `synthetic-auditor`; «Скасувати» не створює запуску. Після «Підтвердити» запуск `audit` стає `needs_review` з checkpoint на `brief`, рядок завдання на панелі `#link-attention` показує «Ревізор вважає…», «35%», підказку «пояснення моделі можуть бути неточними», дві розбіжності з цитатами в `blockquote`; «Затвердити завдання» прибирає рядок, а З1 валідний з джерелом `author`. Запуск несе `audit_plan_fingerprint` із перегляду (64 hex).
3. Налаштування твору без рядка Ревізора: форма Ревізора має нотатку «Поки Ревізора не збережено, він бере модель редактора.», модель редактора й редактори промптів перевірки завдання й пам’яті; збереження створює власний рядок, і нотатка зникає.
4. Після збереження іншої моделі редактора похідна форма Ревізора показує нову модель; збереження Ревізора з іншою температурою проходить без конфлікту й створює власний рядок.
Запуск: `cd frontend; ./node_modules/.bin/playwright test -c playwright.config.mjs ../tests/web/browser/scene-audit.spec.mjs` з абсолютним `PYTHONPATH=<робоча копія>/src`. Цей зв’язок не є доказом виконання; фактичний запуск фіксується окремо.

<a id="book-validation-browser"></a>
## Валідація книги з меню твору

VALID-RUN-S08, VALID-UI-S01, VALID-UI-S02, VALID-UI-S03, VALID-UI-S04, VALID-UI-S05, R20-WORKSPACE-S10. Автоматична частина — Playwright `tests/web/browser/book-validation.spec.mjs` (desktop і mobile, локаль `uk-UA`) на synthetic server `tests/web/browser/server.py`. Фікстура `/test-book-validation` має дві сцени із завданням, прозою й пам’яттю, чиї З1 і З2 `unchecked`, і локального Ревізора `synthetic-book-auditor`: фейковий шлюз дає розбіжність лише для `audit_brief` сцени зі словами «Світло на воді», решта — `valid`.
1. Меню твору: пункт «Валідація книги (2)» активний. Натискання показує діалог «Сцен до перевірки: 2.», «До 4 викликів Ревізора», модель `synthetic-book-auditor` і застереження про правки під час перевірки; «Скасувати» не створює запуску.
2. Повторне натискання й «Почати валідацію»: запуск `audit` з `audit_scope: 'story'` стає `needs_review`. Кнопка «Перейти до сцени 1» відкриває сцену «Ранок», де рядок завдання на панелі `#link-attention` показує розбіжність «Місце дії не збігається з планом». «Затвердити завдання» прибирає рядок; «Продовжити» показує згоду «Сцен до перевірки: 2.», «Підтвердити» доводить запуск до `completed`.
3. Після завершення кнопка переходу прихована, обидві сцени мають `validity: valid`, а пункт меню — «Книга валідна» й неактивний.
4. Нова фікстура: відкрити діалог валідації, тоді змінити прозу першої сцени через API й натиснути «Почати валідацію». Діалог показує «План перевірки змінився. Перегляньте його ще раз» з кнопкою «Переглянути знову», запусків немає. «Переглянути знову» відкриває свіжий перегляд «Сцен до перевірки: 2.», а «Скасувати» лишає чергу порожньою.
5. Прогрес запуску з вкладки (R20-WORKSPACE-S10): після «Почати валідацію» рядок запуску розгорнуто (`#run-status` має клас `expanded`), заголовок `.run-progress-title` читає «Валідація книги: сцена 1 з 2, «Ранок»», крок `.run-progress-step` — «завдання ↔ план», лічильник — «Викликів: 1 / 4…», `progress.run-progress-bar` має `value` 0.25, а фокус стоїть на заголовку й переживає перемальовування `queued` → `running` → `needs_review`. «Скасувати валідацію» показано посиланням (`link-button`), а «Перейти до сцени 1» — не `secondary`.
6. Пункт меню після зупинки (VALID-UI-S05): з фокусом у `#editor` меню показує «Валідацію зупинено: показати», клік повертає фокус на заголовок прогресу й не ставить нового запуску (`GET …/runs` має один запуск). Після `reload` рядок зупиненого запуску розгорнуто, але заголовок фокуса не отримує, а `#link-attention` сцени зупинки отримує його (Р7).
7. Продовження з вкладки (Р2): після рішення автора «Продовжити» перераховує план («Валідація книги: сцена 2 з 2, «Вечір»», «Викликів: n / 4»), а фокус знову стоїть на заголовку прогресу.
Запуск: `cd frontend; ./node_modules/.bin/playwright test -c playwright.config.mjs ../tests/web/browser/book-validation.spec.mjs` з абсолютним `PYTHONPATH=<робоча копія>/src`. Цей зв’язок не є доказом виконання; фактичний запуск фіксується окремо.
