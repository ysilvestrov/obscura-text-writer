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

`pnpm --dir frontend exec playwright test brief-proposal.spec.mjs` на синтетичному сервері: stale old head + new proposed brief. Перевірити новий JSON у вкладці й явний список змін/accept; Save не приймає його, accept вибирає exact displayed version й розблоковує draft за придатного контексту. Dirty edit блокує accept до Save, після Save приймається саме нова авторська версія. Конкурентна зміна scene дає помилку без втрати тексту. Story refresh відкритого чистого brief підхоплює нову пропозицію без head change; dirty ввод лишається. Сценарій `acceptance follows refreshed run state without switching tabs` перевіряє блокування під час роботи та доступність після оновлення стану без переходу між вкладками. Desktop/mobile, без реальних моделей; наявність процедури не є звітом про виконання.

Сценарії `editing an accepted brief keeps acceptance when starting a draft` і `manual save of an accepted brief keeps acceptance`: прийняти пропозицію, змінити її, перевірити ручний Save та основну дію; нова версія лишається прийнятою, а основна дія після збереження надсилає запит на запуск; тест перехоплює цей запит без виклику моделі. Окремо перевірити, що правка неприйнятої пропозиції все ще потребує явного прийняття.


<a id="r28-impact"></a>
## R-28 — Браузерний сценарій перевірки впливу

Виконати `pnpm --dir frontend exec playwright test impact.spec.mjs` на синтетичному сервері tests/web/browser/server.py, без .env/production data/реальних gateway. Обидва проєкти desktop/mobile мають пройти: preview показує synthetic planner/calls; protocol3 clean не змінює prose ID; concerns мають точні цитати; legacy reject перевіряється API-тестами; введений незбережений текст і UA/EN switch не губляться. Нейтральні screenshot у artifacts/r28-impact; проглянути desktop/mobile разом та скопіювати підтверджені зображення до docs/images. Сам цей опис не підтверджує виконання; свідчення — журнал і результат runner.


<a id="r28-preview-wait"></a>
### R-28: очікування попереднього перегляду

На синтетичному сервері виконати `pnpm --dir frontend exec playwright test --config playwright.config.mjs impact.spec.mjs`. Сценарії `slow impact preview is visible immediately and can be cancelled without dispatch`, `impact preview timeout unlocks controls and reports a specific cause`, `failed impact preview unlocks retry and does not retain stale start action`: route hold робить затримку контрольованою; loading/elapsed/cancel видимі, start прихований; cancel і virtual clock121с повертають кнопку без run. HTTP503 дає пояснення, наступний preview успішний. Виконати desktop/mobile; production API й модельні витрати відсутні.


<a id="run-recovery-visible"></a>
## Видимість відновлення після налаштувань

На синтетичному стенді виконати `pnpm --dir frontend exec playwright test --config playwright.config.mjs --grep "restored failed run"`. Сценарій у tests/web/browser/impact.spec.mjs перевіряє desktop/mobile: останній failed run, затриману readiness, конфігураційну відмову, перехід у налаштування та повернення. Repeat має бути видимим і disabled із причиною; жодного resume POST. Для фактично ready run додатково перевірити доступну кнопку без натискання; completed run не має repeat. Сам опис не є підтвердженням виконання.


<a id="sequential-review"></a>
## Послідовний перегляд книги

У frontend виконати `pnpm exec playwright test --config playwright.config.mjs impact.spec.mjs sequential-review.spec.mjs` на синтетичному сервері. Desktop/mobile: повний clean результат автоматично завершується; concerns мають source/target уривки; reject-all приймає без зайвого confirm, fix choices зберігаються через reload/settings return. Dirty проза блокує finish; після Save finish оновлює пам’ять без нового search. UA/EN labels змінюються, авторський текст — ні. Контрольовані preview wait/cancel/timeout/error не запускають модель. Старі protocol1/2 API/replay перевіряються Python-тестами tests/web/test_impact_api.py та tests/impact. Знімки нейтральної панелі: artifacts/sequential-review. Наявність процедури не підтверджує її виконання.

Додатковий R-28k сценарій `legacy current-consistency mode is explicit in preview and restored author report`: `/test-impact?legacy=true` показує Поточні передумови/Current premises; report явно без історичного порівняння після reload і UA/EN; reject-all завершує сесію. Тільки synthetic data.


<a id="characters-page"></a>
## Окрема сторінка персонажів

Запустити `node frontend/node_modules/@playwright/test/cli.js test --config frontend/playwright.config.mjs characters-page --reporter=line`.
Перевірки desktop/mobile: перехід і повернення до prose, додавання картки, довгий опис, UA/EN без втрати вводу, preview, save, порожній твір без сцен, відмова від виходу з dirty, CAS409 без втрати правок. Переглянути нейтральні `docs/images/characters-page-desktop.png` і `characters-page-mobile.png`: поля видимі, немає горизонтального переповнення.


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
## Робочий простір: рядок стану, меню, розділи сцени й «Редагування книги»

З `PYTHONPATH=<робоча копія>/src` у `frontend` запустити `npx playwright test workspace-layout impact sequential-review review-evidence --project=desktop --project=mobile` на synthetic server без provider calls. `workspace-layout.spec.mjs`: `status row holds run controls and the next-run limit`; `story menu opens from the keyboard and returns focus on Escape`; `book revision page opens from the menu with a pending count`; `scene sections reopen after reload and leave unsaved text alone` (зокрема оцінювання приховане без оцінювача); `sections work when storage throws`. `sequential-review.spec.mjs` і `impact.spec.mjs` перевіряють запуск на `/stories/{id}/revision` і картку сесії поруч з редактором. Переглянути знімки `docs/images/workspace-*-{desktop,mobile}.png` на нейтральність і відсутність горизонтального прокручування на 375 px. Наявність процедури не є фактичним PASS; результат запуску записується в журналі виконання.


<a id="core-review"></a>
## Панель підтвердження ядра

З кореня робочої копії з `PYTHONPATH=<робоча копія>/src` запустити `frontend/node_modules/.bin/playwright test -c frontend/playwright.config.mjs core-review` (не `npx playwright`, який ставить іншу версію). Synthetic server, нейтральні сцени «Ранок»/«Гість», без provider calls. Cases `core-review.spec.mjs` для desktop і mobile: `changes are expanded, unchanged rows collapsed, confirm without edits` (знімки `docs/images/core-review-{desktop,mobile}.png`, без горизонтального прокручування); `keep previous on an unknown slot creates a version where the slot is unchanged` (після цього без wire «Лишити попереднє» вимкнене, «Вписати…» для закритої лінії відсутнє); `write in with a quote from an earlier scene` (пошук звужує фрагменти); `write in without a quote is unknown to the reader; cancel keeps the draft`; `refreshing the table asks before dropping a core draft`; `a conflict shows the server message and reloads the panel`. Переглянути обидва знімки на нейтральність. Наявність процедури не є фактичним PASS; результат запуску записується в журналі виконання.

<a id="ghost-mode"></a>
## Переписування по пам’яті

З теки `frontend` з `PYTHONPATH=<робоча копія>/src` запустити `./node_modules/.bin/playwright test ghost-mode --reporter=line`. Synthetic server (`POST /test-ghost-mode`): нейтральна сцена «Вечір біля маяка» з AI-чернеткою Markdown (3 блоки: текст із діалогом, розділювач, текст), без provider calls, локаль uk-UA. Cases `ghost-mode.spec.mjs` для desktop і mobile: `reading, writing and Tab peek; save creates an author draft` (Tab до першого символу нічого не робить, стирання до порожнього не повертає AI-блок, утримання Tab блокує набір, `Ctrl+Enter`, збереження Markdown з `author_lineage` і `peeks=2`; знімки `docs/images/ghost-mode-{desktop,mobile}.png`); `peek button, blocked paste and copy, explicit skip`; `an unsaved rewrite survives a reload and cancel discards it`; `plain draft with formatting saves Markdown; notices stay above the mode` (утримання пробілу на кнопці проблиску); `a corrupted saved session never leaves the mode stuck`. Окремо вручну в Windows із фізичною клавіатурою: утримання й відпускання `Tab` у Chrome та Edge не перемикає фокус і не відкриває меню, автоповтор `Tab` не рахує додаткових проблисків, українська розкладка й IME не вмикають проблиск. Переглянути знімки на нейтральність. Наявність процедури не є фактичним PASS; результат запуску записується в журналі виконання.

<a id="brief-link"></a>
## Підтвердження завдання для прози

З теки `frontend` з `PYTHONPATH=<робоча копія>/src` запустити `./node_modules/.bin/playwright test brief-link --reporter=line`. Synthetic server (`POST /test-brief-link`): нейтральні картки «Лера» (протагоністка), «Марко», «Ніна», сцени «Ранок у парку» і «Кав’ярня» з головою brief і ручною прозою без родоводу, без provider calls, локаль uk-UA. Cases `brief-link.spec.mjs` для desktop і mobile: `author confirms the brief with introductions and moves to the next scene` (знімки `docs/images/brief-link-{desktop,mobile}.png`; після підтвердження панель згорнута, API повертає `source=link`, «Наступна непідтверджена сцена» відкриває «Кав’ярня»); `conflict keeps the ticked introductions and saves nothing` (зміна сцени до натискання → повідомлення про помилку, прапорець лишається, `source=fallback`); `opening the brief and switching scenes keep the ticked introductions`; `prose replaced elsewhere is never confirmed unseen` (409, редактор перечитує нову прозу, позначки старої прози не переносяться, підтвердження записується на нову прозу); `an unsaved change to a confirmation is not shown as confirmed`. Переглянути обидва знімки на нейтральність. Наявність процедури не є фактичним PASS; результат запуску записується в журналі виконання.

<a id="model-import-metadata"></a>
## Тарифи, ліміти й journal counts

Playwright model-metadata.spec.mjs: selected model shows tariff units/caps/unknown, manual expired+stale discovery, shared classifier same tariff without limit changes; desktop/mobile UA/EN. Additive-imports case journal retains actual import counts after reload and marks old counts unknown: actual1/0/duplicate0, reload, UA/EN, missing fields unknown. Переглянути neutral model-tariff/import-journal-counts desktop/mobile PNG. Mock APIs/synthetic gateway, без key/.env/production/inference. Фактичні pytest результати — verify.py/STATUS, browser runner — окремо в журналі.
<a id="workspace-one-click"></a>
## Телеметрія та зупинка основної дії

На синтетичному сервері запустити `node frontend/node_modules/@playwright/test/cli.js test --config frontend/playwright.config.mjs workspace-telemetry.spec.mjs workspace-cancel.spec.mjs save-and-run.spec.mjs`. Перевірити desktop/mobile, передзапускову модель, збереження без загального dialog, затриманий і втрачений POST, серверний cancel і відновлення плану після reload. Тести не виконують реальний inference; наявність процедури не означає її виконання.

WORKSPACE-TELEMETRY-S01: у `workspace-telemetry.spec.mjs` сценарії `plan/brief/draft/prose shows its model and warning before a single-click start`, а також `draft displays editor and planned calls before starting` перевіряють ролі, попередження, UA/EN і зміну ліміту. WORKSPACE-TELEMETRY-S02: у `workspace-cancel.spec.mjs` сценарії `stop during reconciliation is not lost`, `stopping readiness restores controls without a settings error`, `unknown enqueue is not shown as cancelled and Stop fences it` та інші перевіряють конкретні гонки. WORKSPACE-TELEMETRY-S03: `sidebar retains the planned model after reload` і `legacy run with no saved plan is explicitly unknown`. Playwright тести перелічено тут, бо структурна матриця індексує Python testcase, а не browser test names.

<a id="workspace-speed"></a>
## Швидкість відповіді робочого простору

Запустити `python scripts/workspace_bench.py --data <копія data> --story <id-префікс> --json` на копії робочих даних (не на робочій базі) і `python scripts/workspace_bench.py --synthetic 300 --workdir <нова тека> --json`. Синтетичний твір отримує локальні ролі зі стандартними промптами, тому readiness `brief`/`scene` має доходити до побудови контексту (`ready=true`) без викликів моделей; теку можна повторно використати лише для того самого числа сцен і завершеної побудови, інакше скрипт завершується з кодом 2 (`synthetic_mismatch`/`synthetic_incomplete`/`synthetic_ambiguous`). Для базового прогону скопіюйте теку до запуску старого коду. Порівняти `digest` із базовим прогоном до змін: він має збігатися. Потім у браузері виміряти від кліку до завершення останнього API-запиту: запустити `python -m storygen.server --data-dir <копія data або C:/tt/bench300r> --env-file <порожній файл>` (порожній env-файл не дає завантажити `.env` проєкту й ключі), відкрити сторінку у вбудованому браузері, обгорнути `window.fetch` лічильником запитів у польоті й міткою часу останнього завершеного запиту, а для відкриття твору використати `performance.getEntriesByType('resource')` після перезавантаження. Дії: «вибір сцени» (кілька різних сцен, у т.ч. пізніша), «перевірка готовності первинної дії» (запит `readiness?operation=…`, входить у вибір сцени), «розгорнути додаткові команди» (readiness усіх 9 операцій, на 300 сценах — на пізній сцені), «відкриття твору»; не менше 3 повторів, медіана й діапазон, перший холодний клік записати окремо. Цілі: 68 сцен — не більше 1 с, 300 синтетичних — не більше 3 с. Збереження вимірювати лише на окремій копії, яка не порівнюється з digest бенчмарку. Тексти не друкувати: лише ID, коди й час. Результат залежить від машини, тому процедура ручна; наявність процедури не означає її виконання. Виконано 08.11.2026 (код `08218e7`): цілі не досягнуто (відкриття твору 3,2–3,5 с на 68 і 5,4–5,9 с на 300; вибір сцени до 1,08 с на 68; розгортання всіх операцій 5,3–5,6 с на пізній сцені 300), збереження не вимірювалося; виміри й причини — у SPEC.MD (PERF-001) і журналі виконання.
