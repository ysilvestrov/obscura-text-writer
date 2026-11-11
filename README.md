# Obscura Text Writer

Локальний вебзастосунок для написання української прози за авторським планом.
Автор керує сценами й чотирма модельними ролями: планувальником, письменником,
редактором і пам’яттю.

## Можливості

- Імпорт плану й персонажів із TXT/Markdown та ручне редагування сцен.
- Незмінні версії тексту, порівняння й вибір результату, облік застарілих залежностей.
- Послідовна генерація, потокова відповідь, пауза, скасування й відновлення.
- Локальний OpenAI-сумісний API, OpenRouter та Venice з перевіркою `uncensored=true`.
- Пам’ять з перевіркою джерел, точкова редактура, автоматичне оцінювання.
- Експорт Markdown/TXT/FB2/EPUB/PDF із карткою публікації та обкладинкою; кошик творів і сцен.

Це прототип. Успішний модельний виклик або автоматична оцінка не гарантує
літературної якості; остаточний текст перевіряє автор. Відомі технічні
обмеження наведено в [SPEC.MD](SPEC.MD).

## Швидкий запуск у Windows

Потрібні Python 3.10+ та сумісний модельний API.

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements-lock.txt
./.venv/Scripts/python.exe -m pip install --no-deps -e ".[web,publication]"
Copy-Item .env.example .env
./scripts/start.ps1
```

Команду копіювання `.env` виконуйте лише при першому налаштуванні, якщо цього
файла ще немає. Для хмарних провайдерів заповніть відповідні ключі; локальному
провайдеру вони не потрібні. В інтерфейсі налаштуйте API URL, model ID та ліміти
для кожної ролі. Хмарні виклики можуть бути платними.

Інтерфейс: `http://127.0.0.1:8765`. Для особистих творів рекомендовано окремий
каталог поза репозиторієм:

```powershell
./scripts/start.ps1 -DataDir "$env:LOCALAPPDATA/ObscuraTextWriter/data"
```

Інструкції українською й англійською: [сайт Obscura](https://ysilvestrov.github.io/obscura-text-writer/) (джерело — `docs/site/`).

Докладніше: [запуск і резервне копіювання](docs/prototype-runbook.md), [експорт FB2/EPUB](docs/verification/manual.md#ebook-formats) та [PDF A5](docs/verification/manual.md#pdf-publication).
Для першої проби можна імпортувати нейтральні [план](tests/fixtures/prototype/plan.md)
та [персонажів](tests/fixtures/prototype/characters.md) тестової історії про бібліотеку.

## Приватність

Дані зберігаються локально відкритим текстом. Вибраний хмарний провайдер отримує
контекст запущеної операції. `.gitignore` виключає типові приватні каталоги,
але не обмежує читання файлів редактором або AI-асистентом.
Застосунок призначений для локального користувача й не має автентифікації.
Детальніше — [SECURITY.md](SECURITY.md).

## Розробка

- [Архітектура й відомі обмеження](SPEC.MD).
- [Правила внесення змін і перевірки](CONTRIBUTING.md).
- [Стан фактичної перевірки](docs/STATUS.md) та [зв’язки сценаріїв із тестами](docs/verification/README.md).
- [Інструкція публікації](docs/github-publication.md).

## Ліцензія

Код наступних версій розповсюджується за [Functional Source License 1.1, MIT Future
License (FSL-1.1-MIT)](LICENSE). Це ліцензія з відкритим кодом для читання
(source-available), але не open source за визначенням OSI:

- користуватися програмою можна безкоштовно, зокрема для творів, які ви продаєте;
- змінювати код і ділитися змінами можна, якщо це не конкурентний продукт;
- заборонено надавати іншим у комерційному продукті чи сервісі збірку або
  сервіс, що замінює Obscura чи повторює її можливості;
- кожна версія через два роки після публікації стає доступною за MIT.

Версії до тегу `last-mit` включно лишаються за MIT назавжди:
[текст попередньої ліцензії](docs/licensing/MIT-previous-versions.txt).
Сторонні частини лишаються під власними ліцензіями: бандл редактора
(`src/storygen/web/static/licenses`), шрифт Noto Serif (OFL-1.1) і схеми FictionBook.
Назву й логотип Obscura регулює [політика назви](docs/trademark-policy.md)
([English](docs/en/trademark-policy.md)). Приватні твори та дані користувачів
не входять до репозиторію.

**English.** Versions after the `last-mit` tag are source-available under
[FSL-1.1-MIT](LICENSE): free to use, including for books you sell; competing
commercial builds or services are not allowed; each version becomes MIT two years
after release. Earlier versions remain [MIT](docs/licensing/MIT-previous-versions.txt).
See the [name and logo policy](docs/en/trademark-policy.md).

Умови використання (чернетка, ще не чинна): [українською](docs/terms-of-use.md), [English](docs/en/terms-of-use.md).


Платні виклики потребують явного ліміту оповідання/CLI та чинного тарифу.
Налаштування й пояснення сум: [бюджет модельних викликів](docs/provider-budget.md).

Повторне використання моделей і промптів між творами: [комплекти ролей](docs/role-profiles.md).

Обмеження майбутніх планів у контексті ролі: [горизонт сюжету](docs/story-horizon.md).

Твір українською або англійською, мова прози окремої сцени: [інструкція українською](docs/story-language.md), [English](docs/en/story-language.md).

Табличний перегляд і відбір пам’яті: [інструкція українською](docs/memory-view.md), [English](docs/en/memory-view.md).

Жирний, курсив і збереження джерела: [візуальний редактор](docs/visual-editor.md). Переписування AI-чернетки власними словами: [інструкція українською](docs/ghost-mode.md), [English](docs/en/ghost-mode.md). Для розробника — [збірка локального JS bundle](docs/frontend-development.md).

Перевірка наслідків змін після написання: [редагування книги й перевірка впливу / Book revision impact review](docs/impact-review.md). Двофазний planner-аналіз, окремі висновки для завдання/прози та пам’яті, явний бюджет і збережені докази.

Інтерфейс персонажів: [інструкція українською](docs/prototype-runbook.md#часова-доступність-персонажів-r-06), [English](docs/en/characters.md).

Віковий рейтинг, запобіжник щодо віку персонажів і позначка в експорті: [інструкція українською](docs/content-rating.md), [English](docs/en/content-rating.md).
