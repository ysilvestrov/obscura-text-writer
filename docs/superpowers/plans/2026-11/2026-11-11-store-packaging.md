# Пакування збірки для Microsoft Store — план реалізації (#30, PR 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Мета:** одна команда збирає з репозиторію пакет MSIX видання `store`: застосунок без консолі, з позначкою видання, ліцензійними повідомленнями й маніфестом, і сама перевіряє, що зібране справді запускається й уміє все потрібне.

**Архітектура:** скрипт `scripts/build_store.py` виконує чотири кроки: заморожування PyInstaller, доповнення теки збірки (позначка видання, ліцензійні повідомлення, файли, яких бракує замороженому Python), самоперевірка зібраного виконуваного файла, розкладка й пакування MSIX через `makeappx`. Самоперевірка — режим `--self-check` самого застосунку, що пише звіт у файл: саме вона, а не припущення про середовище, вирішує, чи збірка придатна. Подання в Store і підпис — поза цим PR.

**Стек:** Python 3.12, PyInstaller 6, `makeappx` з пакета `Microsoft.Windows.SDK.BuildTools`, pytest.

**Специфікація:** `docs/superpowers/specs/2026-11/2026-11-11-store-build-design.md`, розділ «Пакування»; відкладені пункти з PR 1–3 (журнал виконання, 11.11.2026).

**Основа:** гілка відгалужена від `claude/desktop-launcher` (PR 115). PR цієї гілки відкривається після злиття PR 115.

## Проби (11.11.2026)

- **П10. Інструмент пакування.** `Microsoft.Windows.SDK.BuildTools` 10.0.28000.2957 з nuget.org (згода власника 11.11.2026), розпаковано в `C:\tmp\tools\buildtools`; `makeappx.exe` має чинний підпис Microsoft Corporation; `makeappx pack` зібрав пакет із розкладки.
- **П11. Заморожена збірка запуску у виданні `store`.** PyInstaller `--onedir --noconsole`, точка входу `storygen.desktop:main`, 74 МБ, 318 файлів. З позначкою `_internal/storygen/build_edition.json`: старт за 3 с, `/api/app-info` дає `edition=store` і межу `sexual=1`, сховище ключів доступне (`store_available=true`), значок у треї доступний, сторінка відповідає 200.
- **П12. TLS у замороженій збірці.** Перша спроба впала ще на імпорті: Python, на якому зібрано `.venv` проєкту, — збірка з комплекту Codex із пропатченим `ssl.py`, що під час створення будь-якого TLS-контексту читає файл `codex-rejected-cas.pem` поруч із `ssl.py`. PyInstaller цей файл не бере, тож у замороженій збірці не створюється жоден TLS-контекст: `ssl.SSLContext(...)`, `ssl.create_default_context()` і клієнт `httpx` падають з `FileNotFoundError`. Тобто без втручання зібраний застосунок не зміг би звернутися до жодного хмарного провайдера. З файлом, покладеним у `_internal`, усі три працюють. Офіційного CPython на машині немає.
- **П13. Пакет.** Розкладка з маніфестом (повна довіра, `runFullTrust`) і трьома значками пакується в MSIX 39,7 МБ; найдовший відносний шлях у пакеті — 101 символ. Встановлення пакета не перевірено: воно потребує підпису сертифікатом, якому довіряє система, а це зміна системних налаштувань безпеки.

## Загальні обмеження

- Збірку визнає придатною лише самоперевірка зібраного `Obscura.exe`; скрипт завершується з помилкою, якщо звіту немає або хоч одна перевірка не пройшла.
- Позначку видання створює лише скрипт збирання; після збирання він читає її з теки збірки й звіряє з тим, що повідомляє самоперевірка. Відсутня позначка означає повне видання, тож це перевіряється явно.
- `report_url` обов’язковий для видання `store` (BUILD-EDITION-001); адреси — аргументи скрипта.
- Ідентичність пакета (`Name`, `Publisher`, `PublisherDisplayName`) дає Partner Center; до реєстрації вони — аргументи скрипта без типових значень. Версія пакета — версія з `pyproject.toml`, доповнена до чотирьох частин (`0.1.0` → `0.1.0.0`).
- У пакет не входять тести, документація, MCP-міст і сам Codex CLI.
- Ліцензійні повідомлення: для кожного дистрибутива Python у збірці — назва, версія, ліцензія й текст ліцензійного файла з його метаданих; плюс наявні `static/licenses/*.txt` і `LICENSE`. Дистрибутив без ліцензійного тексту зупиняє збирання з переліком назв.
- Скрипт нічого не завантажує з мережі й не встановлює: PyInstaller і `makeappx` мають бути вже доступні (шлях до `makeappx` — аргумент `--makeappx` або змінна `MAKEAPPX`).
- Тека результату задається аргументом і має бути порожньою або відсутньою; скрипт нічого не видаляє поза нею.
- Повне збирання не входить у `pytest`: воно триває хвилини й потребує інструментів. Автоматичні тести покривають чисті частини; саме збирання — записана процедура, результат якої вноситься в журнал.
- Мова документації — українська; нові Scenario мають записи в traceability; `python scripts/check_docs.py` проходить.

## Фокус рев’ю

1. Збірка на Python без `codex-rejected-cas.pem` (офіційний CPython): скрипт не падає через відсутній файл, а самоперевірка TLS проходить (Задачі 1 і 2).
2. Позначка видання не потрапила в теку збірки (змінилася розкладка PyInstaller): самоперевірка каже `edition=full`, і скрипт зупиняється, а не пакує повне видання як збірку для Store (Задача 2).
3. Адреса чи назва видавця з символами `&`, `<`, лапками: маніфест лишається коректним XML (Задача 3).
4. Версія з суфіксом (`0.2.0rc1`, `1.2`): перетворення у версію пакета або зрозуміла відмова (Задача 3).
5. Самоперевірка в процесі без консолі й без прав запису в поточну теку: звіт пишеться лише за явно вказаним шляхом, код виходу відображає результат (Задача 1).

---

### Задача 1: Самоперевірка зібраного застосунку

**Файли:**
- Створити: `src/storygen/self_check.py`
- Змінити: `src/storygen/desktop.py` (аргумент `--self-check <файл звіту>`)
- Тест: `tests/test_self_check.py`

**Інтерфейси:**
- Дає:
  - `run_checks() -> dict` — `{"ok": bool, "frozen": bool, "version": str, "edition": str, "max_rating": {...}, "checks": [{"name": str, "ok": bool, "detail": str}]}`.
  - Перевірки (назви сталі): `tls_context` (створення `ssl.create_default_context()` і клієнта `httpx`), `edition_marker` (читання `build_edition.current()`), `package_data` (є `web/static/i18n.json`, шаблони, міграції `storage/migrations/001_initial.sql`…`005`, ресурси промптів, шрифти публікації), `key_store` (`secrets.default_backend()` не `None`; нічого не читає й не пише у сховище), `tray` (імпорт `pystray` і Pillow, побудова зображення значка без показу), `database` (створення `Repository` у тимчасовій теці й версія схеми `SCHEMA_VERSION`), `licenses` (поруч із виконуваним файлом є `THIRD-PARTY-NOTICES.txt`; у незамороженому запуску — пропущено з `ok=true` і `detail='не заморожена збірка'`).
  - `desktop.main(['--self-check', шлях])` пише звіт JSON за шляхом і повертає 0, якщо `ok`, інакше 5; не стартує сервер, не чіпає теку даних користувача, не відкриває браузер і трей.
- `detail` — короткий авторський текст або назва винятку; без шляхів профілю користувача.

- [ ] **Крок 1: Написати тести, що падають**

```python
def test_checks_pass_in_the_development_environment():
    report=run_checks()
    assert report['ok'] is True and report['frozen'] is False and report['edition']=='full'
    assert [c['name'] for c in report['checks']]==['tls_context','edition_marker','package_data','key_store','tray','database','licenses']


def test_broken_tls_is_reported_not_raised(monkeypatch):
    # ssl.create_default_context кидає FileNotFoundError -> ok False, перевірка tls_context має ok False і назву винятку


def test_missing_package_data_names_the_missing_file(monkeypatch):
    # підмінити перелік обов'язкових файлів на неіснуючий -> package_data ok False, detail містить відносну назву


def test_store_edition_is_reported(store_edition):
    assert run_checks()['edition']=='store' and run_checks()['max_rating']['sexual']==1


def test_key_store_check_never_touches_the_store(secret_store,monkeypatch):
    # get/set/delete сховища кидають AssertionError; перевірка key_store не викликає їх


def test_self_check_mode_writes_the_report_and_starts_nothing(tmp_path,monkeypatch):
    # main(['--self-check',str(tmp_path/'r.json'),'--data-dir',str(tmp_path/'data')],serve=fail,opener=fail,tray=fail)==0
    # звіт є і ok; теки data немає; з поламаним TLS код 5 і звіт із ok False
```

- [ ] **Крок 2: Запустити й побачити падіння** — `python -m pytest tests/test_self_check.py -q`.

- [ ] **Крок 3: Реалізувати.** Кожна перевірка — у власному `try`; виняток дає `ok=False` і `detail=type(error).__name__`.

- [ ] **Крок 4: Запустити** `python -m pytest tests/test_self_check.py tests/test_desktop.py -q` — усі проходять.

- [ ] **Крок 5: Коміт** — `feat(packaging): self-check of the built application (#30)`.

---

### Задача 2: Скрипт збирання — заморожування, доповнення, самоперевірка

**Файли:**
- Створити: `scripts/build_store.py`, `src/storygen/packaging.py` (чисті функції, які тестуються)
- Змінити: `pyproject.toml` (extra `build = ["pyinstaller>=6,<7"]`)
- Тест: `tests/test_packaging.py`

**Інтерфейси:**
- Дає (`storygen/packaging.py`):
  - `edition_marker(edition, report_url, support_url='', waitlist_url='') -> str` — JSON позначки; перевіряється тим самим `load_build_edition`.
  - `third_party_notices(distributions: Iterable[str]) -> str` і `missing_licenses(distributions) -> list[str]`.
  - `bundled_distributions(frozen_dir: Path) -> list[str]` — назви дистрибутивів за теками `*.dist-info` у збірці; якщо PyInstaller їх не поклав, перелік береться з залежностей `storygen[web,publication,local-tokens,desktop]` через `importlib.metadata`.
  - `vendor_runtime_files(python_lib: Path) -> list[Path]` — файли, які стандартна бібліотека цього інтерпретатора читає під час роботи, але PyInstaller не бере; сьогодні це `codex-rejected-cas.pem`, якщо він є поруч із `ssl.py`; для офіційного CPython — порожній перелік.
  - `pyinstaller_args(entry: Path, name: str, dist: Path, work: Path) -> list[str]`.
  - `check_report(report: dict, edition: str) -> list[str]` — перелік причин відмови (порожній — придатна).
- `scripts/build_store.py --out <тека> --report-url <адреса> [--support-url] [--waitlist-url] [--edition store] [--skip-msix]` → `<тека>/Obscura/` (заморожена збірка), `<тека>/self-check.json`; код 0 лише за порожнього `check_report`.

- [ ] **Крок 1: Написати тести, що падають**

- `edition_marker('store', 'https://example.test/r')` читається `load_build_edition` у видання `store`; без `report_url` — `ValueError`.
- `third_party_notices(['pydantic','fastapi'])` містить назви, версії й непорожні тексти ліцензій; `missing_licenses` для підставного дистрибутива без ліцензії повертає його назву.
- `vendor_runtime_files`: тека з `ssl.py` і `codex-rejected-cas.pem` → один файл; тека лише з `ssl.py` → порожньо.
- `pyinstaller_args` містить `--noconsole`, `--onedir`, `--collect-data storygen`, `--collect-submodules storygen`, приховані імпорти бекенда `keyring` для Windows і `pystray._win32`; не містить `--onefile`.
- `check_report`: звіт з `ok=False` → назви провалених перевірок; `frozen=False` → причина; `edition` не збігається з очікуваним → причина «позначка видання не потрапила в збірку»; придатний звіт → `[]`.

- [ ] **Крок 2: Запустити й побачити падіння** — `python -m pytest tests/test_packaging.py -q`.

- [ ] **Крок 3: Реалізувати** чисті функції й скрипт. Скрипт: перевірка порожньої теки результату → PyInstaller → позначка в `_internal/storygen/` → файли `vendor_runtime_files` у `_internal/` → `THIRD-PARTY-NOTICES.txt` і `LICENSE` поруч з `Obscura.exe` → запуск `Obscura.exe --self-check <тека>/self-check.json` з тайм-аутом 120 с → `check_report`.

- [ ] **Крок 4: Запустити** `python -m pytest tests/test_packaging.py -q` — усі проходять.

- [ ] **Крок 5: Справжнє збирання без MSIX.** Встановити PyInstaller у `.venv` (`pip install "pyinstaller>=6,<7"`), виконати `python scripts/build_store.py --out C:\tmp\obscura-build --report-url https://example.test/report --skip-msix`. Очікувано: код 0, `self-check.json` з `ok=true`, `edition=store`, усі сім перевірок пройдені. Запустити `Obscura.exe --data-dir <тимчасова тека> --no-browser` і перевірити `/api/app-info`. Розмір, час і результат — у повідомлення коміту.

- [ ] **Крок 6: Коміт** — `feat(packaging): build script with edition marker, notices and self-check (#30)`.

---

### Задача 3: Маніфест і пакет MSIX

**Файли:**
- Змінити: `src/storygen/packaging.py`, `scripts/build_store.py`
- Створити: `packaging/msix/Assets/StoreLogo.png`, `Square44x44Logo.png`, `Square150x150Logo.png` (згенеровані тим самим малюнком, що й значок трея; власник може замінити)
- Тест: `tests/test_packaging.py`

**Інтерфейси:**
- Дає:
  - `package_version(project_version: str) -> str` — `0.1.0` → `0.1.0.0`, `1.2` → `1.2.0.0`; версія з нецифровим суфіксом — `ValueError('Версія пакета MSIX має складатися з чисел: …')`.
  - `appx_manifest(*, identity_name, publisher, publisher_display_name, version, display_name='Obscura Text Writer', description, executable='Obscura.exe') -> str` — XML, усі значення екрановані; мови ресурсів `uk-UA` та `en-US`; `TargetDeviceFamily` `Windows.Desktop` від `10.0.19041.0`; `runFullTrust`.
  - `find_makeappx(explicit: str | None) -> Path` — аргумент → змінна `MAKEAPPX` → `PATH`; інакше `ValueError` з поясненням, де взяти інструмент.
- Скрипт без `--skip-msix` вимагає `--identity-name`, `--publisher`, `--publisher-display-name` і створює `<тека>/Obscura-<версія>.msix`.

- [ ] **Крок 1: Написати тести, що падають**

- `package_version` для `0.1.0`, `1.2`, `2.0.1.5`; відмова для `0.2.0rc1`, `1.2.3.4.5`, порожнього рядка.
- `appx_manifest(...)` розбирається `xml.etree.ElementTree`; `Identity` має передані `Name`, `Publisher`, `Version` і `ProcessorArchitecture="x64"`; є `Application` з `Executable="Obscura.exe"` і `EntryPoint="Windows.FullTrustApplication"`; є можливість `runFullTrust`; три шляхи значків збігаються з файлами в `packaging/msix/Assets`.
- Значення `Publisher='CN=A&B "C" <D>'` і такий самий `publisher_display_name` після розбору XML дорівнюють вихідним рядкам.
- `find_makeappx`: явний шлях до наявного файла; `MAKEAPPX`; відсутній інструмент → `ValueError` з назвою пакета `Microsoft.Windows.SDK.BuildTools`.
- Файли значків існують і мають розміри 50×50, 44×44, 150×150.

- [ ] **Крок 2: Запустити й побачити падіння.**

- [ ] **Крок 3: Реалізувати.** Розкладка — копія теки збірки плюс `AppxManifest.xml` і `Assets`; `makeappx pack /d <розкладка> /p <пакет> /o`; вивід `makeappx` — у `<тека>/makeappx.log`; ненульовий код зупиняє скрипт.

- [ ] **Крок 4: Запустити** `python -m pytest tests/test_packaging.py -q` — усі проходять.

- [ ] **Крок 5: Справжнє збирання з MSIX** з пробними значеннями ідентичності (`--identity-name ObscuraProbe.TextWriter --publisher CN=ObscuraProbe --publisher-display-name "Obscura probe" --makeappx C:\tmp\tools\buildtools\pkg\bin\10.0.28000.0\x64\makeappx.exe`): пакет створено, у ньому є `Obscura.exe`, `AppxManifest.xml`, `_internal/storygen/build_edition.json`, `THIRD-PARTY-NOTICES.txt`. Розмір — у повідомлення коміту.

- [ ] **Крок 6: Коміт** — `feat(packaging): MSIX manifest, assets and makeappx packing (#30)`.

---

### Задача 4: SPEC, процедури, журнал

**Файли:**
- Змінити: `SPEC.MD`, `docs/verification/traceability.json`, `docs/verification/manual.md`, `docs/superpowers/plans/2026-10-20-remediation-progress.md`
- Створити: `docs/packaging.md` (як зібрати пакет: вимоги, команда, що перевіряє самоперевірка, як перевірити встановлення)

- [ ] **Крок 1: `SPEC.MD`.** Вимога `PACKAGING-001 — Збирання пакета для Microsoft Store` зі Scenario: `S01` самоперевірка зібраного застосунку (сім перевірок, звіт, коди); `S02` позначка видання в пакеті й відмова, якщо її немає; `S03` ліцензійні повідомлення й відмова без тексту ліцензії; `S04` маніфест і версія пакета; `S05` збирання на інтерпретаторі з додатковими файлами стандартної бібліотеки й без них. Технічний опис, проби П10–П13. У «Known limitations»: встановлення пакета не перевірено (потрібен довірений сертифікат); поточний `.venv` стоїть на Python із комплекту Codex — для публічного релізу збирати на офіційному CPython; збирання ручне, без CI; ідентичність пакета й справжні значки — за власником.

- [ ] **Крок 2: Ручні процедури.** `manual.md#store-package-build` (кроки 5 задач 2 і 3) і `manual.md#store-package-install` для власника: створити самопідписаний сертифікат із тим самим `Publisher`, підписати пакет `signtool`, довірити сертифікат, встановити `Add-AppxPackage`, запустити з меню «Пуск», перевірити сторінку, трей, сховище ключів, теку `%USERPROFILE%\Obscura`, видалити застосунок і переконатися, що тека творів лишилася.

- [ ] **Крок 3: `docs/packaging.md`** і запис у журнал виконання.

- [ ] **Крок 4: Перевірка й коміти.** `check_docs.py` — код 0; `verify.py` з короткої теки — `state: passed`; коміти `docs(spec): PACKAGING-001 …`, `docs(status): …`. Користувацькі сторінки сайту не змінюються до публікації в Store: розділ «Інсталятор» і далі каже, що інсталятор з’явиться згодом; це зазначити в повідомленні коміту.

---

## Після задач

1. Наскрізне рев’ю гілки окремим рев’юером із наголосом на «Фокус рев’ю» й на те, що скрипт нічого не видаляє поза текою результату.
2. Крос-рев’ю, таблиця рішень в описі PR; PR на `main` після злиття PR 115; у цьому PR `Closes #30` не ставити: задачу закриває подання в Store, відкладене власником.
3. Питання до власника перед справжнім релізом: встановити офіційний CPython 3.12 для збирання; зареєструватися в Partner Center і передати ідентичність пакета; замінити згенеровані значки; виконати процедуру встановлення пакета.
