# Запуск установленої збірки: без консолі, зі значком у треї — план реалізації (#30, PR 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Мета:** застосунок можна запустити однією командою без консолі: він сам знаходить теку творів у профілі користувача, пише журнал у файл, робить резервну копію перед оновленням бази, відкриває сторінку в браузері й живе у треї, доки автор не натисне «Вийти».

**Архітектура:** нова точка входу `storygen.desktop:main` збирає наявні частини (`create_app`, `uvicorn.Server`, `create_backup`) і додає три власні: запис про запущений сервер (`server.json` з `instance_id`), резервну копію перед міграцією та значок у треї. Звичайний `storygen` (`server.py`) не змінюється. Пакування в MSIX — окремий наступний PR; цей PR дає все, що пакувальник лише загортає.

**Стек:** Python 3.12, uvicorn, `pystray` + Pillow (необов’язкові, extra `desktop`), pytest.

**Специфікація:** `docs/superpowers/specs/2026-11/2026-11-11-store-build-design.md`, розділи «Запуск установленої збірки» й «Резервна копія перед міграцією», ключові рішення 3, 5, 6.

**Поділ залишку #30.** Специфікація називала третій PR «запуск, тека даних, резервна копія, пакування й інструкції». Це понад чотири задачі, і пакування стоїть на запуску, тому за правилом «спершу ядро» залишок ділиться надвоє: цей PR — запуск (ядро), наступний — пакування MSIX і сторінки сайту про встановлену збірку. Оцінка L не змінюється; PR реалізації стає чотири замість трьох.

## Проби (11.11.2026)

- **П8. Збірка без консолі.** У `C:\tmp\frz`: PyInstaller `--onedir --noconsole`, точка входу запускає `uvicorn.Server(..., log_config=None)` у потоці, значок `pystray` — у головному потоці. Результат: збірка 71 МБ; сервер відповідає по HTTP; у журналі `stopping: server.started=True icon.visible=True`, далі `Application shutdown complete` і `server thread alive=False`; порт звільнено. Журнал писався у файл через `logging`. Не перевірено: запуск подвійним кліком з Провідника, коли `sys.stdout` і `sys.stderr` дорівнюють `None` (у пробі процес стартував з оболонки й успадкував потоки); це покриває тест задачі 1 з підміненими потоками й ручна перевірка задачі 4.
- **П9. Резервна копія бази старої схеми.** Тека даних із базою `user_version=4` (міграції 001–004), теками `logs/` і файлом `server.json`: `check_integrity` дає `ok=True`, `create_backup` у сусідню теку проходить, у копії `user_version=4`, у джерелі версія не змінилася. Отже, копія перед міграцією не мігрує базу й не спотикається об нові файли запуску.
- **П6 (зі специфікації).** Міграції застосовує `storage/database.py` за `PRAGMA user_version`; чинна версія схеми — 5.
- **Інструменти пакування.** `makeappx` і Windows SDK на машині немає; `winget` 1.29 є. Для цього PR вони не потрібні.

## Загальні обмеження

- Тека даних установленої збірки: `%USERPROFILE%\Obscura` (рішення власника 11.11.2026); `--data-dir` її перевизначає. Нічого не пишеться в `AppData`.
- Резервні копії перед міграцією: `<тека даних>-backups\pre-migration-v<стара версія>-<РРРРММДД-ГГХХСС>`; тека лежить поруч із текою даних, бо `create_backup` відхиляє вкладене призначення (MAINT-002). Автоматично не видаляються.
- Журнал: `<тека даних>\logs\obscura.log`, ротація 1 МБ × 3 файли, UTF-8. Ніщо не пише в `sys.stdout`/`sys.stderr`; uvicorn запускається з `log_config=None`.
- У журнал не потрапляють тексти творів, запити до моделей і ключі: лише наявні повідомлення застосунку й uvicorn.
- Порт: 8765, якщо вільний на `127.0.0.1`; інакше вільний порт, який дала ОС.
- Без телеметрії й без перевірки оновлень.
- `storygen` (`server.py`), його аргументи й поведінка не змінюються; наявні тести проходять без правок, окрім набору полів `/api/app-info` (додається `instance_id`).
- `pystray` і Pillow — extra `desktop`; без `pystray` точка входу працює в режимі без трея (`--no-tray`) і пише про це в журнал.
- Тести не відкривають браузер, не показують значок і не чекають мережі: відкривач сторінки й трей підставляються параметрами `main`.
- Нові Scenario — у `SPEC.MD` із записами traceability; `python scripts/check_docs.py` проходить. Запуск тестів із worktree й `verify.py` — як у попередніх планах цієї зміни.

## Фокус рев’ю

1. Старий `server.json` після аварійного завершення, а порт зайняла інша програма (відповідь не JSON, інший `instance_id`, тайм-аут): запуск не вважає сервер своїм і стартує сам (Задача 1).
2. Ім’я користувача з кирилицею чи пробілами в `%USERPROFILE%`: шляхи теки даних, журналу, `server.json` і копії працюють (Задачі 1 і 2).
3. Копію перед міграцією створити не вдалося (немає місця, тека копій недоступна, призначення вже існує): база не мігрується, причина в журналі, код виходу ненульовий (Задача 2).
4. «Вийти» під час генерації: поведінка та сама, що в Ctrl+C сьогодні, процес завершується й звільняє порт і `worker.lock` (Задача 3).
5. `sys.stdout` і `sys.stderr` дорівнюють `None`: жоден шлях запуску й завершення не падає (Задача 1).

---

### Задача 1: Точка входу, журнал, запис про запущений сервер

**Файли:**
- Створити: `src/storygen/desktop.py`
- Змінити: `src/storygen/web/app.py` (`instance_id`), `src/storygen/web/routes_app_info.py`, `src/storygen/maintenance.py` (перевірка позначки видання), `pyproject.toml` (скрипт `storygen-desktop`, extra `desktop`)
- Тест: `tests/test_desktop.py`; правка `tests/web/test_app_info.py` (набір полів)

**Інтерфейси:**
- Дає:
  - `default_data_dir() -> Path` — `Path(os.environ['USERPROFILE'])/'Obscura'` у Windows, `Path.home()/'Obscura'` деінде.
  - `configure_logging(data_dir: Path) -> Path` — шлях журналу; повторний виклик не дублює обробники.
  - `choose_port(preferred: int = 8765) -> int`.
  - `write_server_record(data_dir, url, instance_id) -> None`, `remove_server_record(data_dir) -> None`, `running_server(data_dir, timeout: float = 1.0) -> str | None` — адреса, якщо `GET <url>/api/app-info` за тайм-аут повернув JSON із тим самим `instance_id`; інакше `None`.
  - `create_app(settings, *, gateway_factory=None, evaluator_factory=None)` зберігає `app.state.instance_id` (випадковий `uuid4().hex` на процес); `GET /api/app-info` додає поле `instance_id`.
  - `main(argv=None, *, opener=webbrowser.open, tray=None, serve=None) -> int` — коди виходу: 0 — штатно або «вже запущено», 2 — некоректна позначка видання, 3 — не вдалася копія перед міграцією, 4 — не вдалося стартувати сервер. `tray` — виклик `tray(url, data_dir, backups_dir, stop)`, що блокує до виходу (задача 3); `serve` — фабрика сервера для тестів.
  - Аргументи: `--data-dir`, `--no-tray`, `--no-browser`.
- Порядок у `main`: журнал → позначка видання (`build_edition.current()`; помилка → запис у журнал, код 2, тека даних, крім `logs`, не створюється) → `running_server` (є — відкрити сторінку, код 0) → копія перед міграцією (задача 2) → порт → `create_app` → запис `server.json` після `server.started` → відкрити сторінку → трей або очікування потоку сервера → зупинка сервера, видалення `server.json`.

- [ ] **Крок 1: Написати тести, що падають**

```python
def test_default_data_dir_is_under_the_user_profile(monkeypatch,tmp_path):
    monkeypatch.setenv('USERPROFILE',str(tmp_path/'Користувач Тест'))
    assert desktop.default_data_dir()==tmp_path/'Користувач Тест'/'Obscura'


def test_logging_goes_to_a_rotating_file_and_survives_missing_std_streams(monkeypatch,tmp_path):
    monkeypatch.setattr(sys,'stdout',None);monkeypatch.setattr(sys,'stderr',None)
    log=desktop.configure_logging(tmp_path/'Дані')
    logging.getLogger('storygen.desktop').info('перевірка')
    assert log==tmp_path/'Дані'/'logs'/'obscura.log' and 'перевірка' in log.read_text(encoding='utf-8')
    desktop.configure_logging(tmp_path/'Дані')          # без дублювання обробників
    logging.getLogger('storygen.desktop').info('ще раз')
    assert log.read_text(encoding='utf-8').count('ще раз')==1


def test_choose_port_prefers_8765_and_falls_back_when_busy():
    # зайняти вільний порт сокетом; choose_port(зайнятий) повертає інший порт, на якому можна слухати


def test_running_server_trusts_only_a_matching_instance(tmp_path):
    # локальний http.server у потоці з відповіддю {"instance_id": "A"}:
    #   запис із "A" -> адреса; запис із "B" -> None; відповідь не JSON -> None; ніхто не слухає -> None;
    #   відповідь довша за тайм-аут -> None; файла немає або він пошкоджений -> None


def test_main_starts_serves_and_cleans_up(tmp_path):
    # main(['--data-dir',d,'--no-browser'],tray=fake) у потоці; fake(url,...) перевіряє: GET url/api/app-info має instance_id,
    # що збігається з server.json; потім викликає stop(). Після завершення: код 0, server.json немає, порт вільний,
    # журнал містить адресу сервера, opener не викликався


def test_second_launch_opens_the_running_instance(tmp_path):
    # перший main працює; другий main(['--data-dir',d],opener=spy,tray=fail) повертає 0, spy отримав адресу першого,
    # другий сервер не стартував (tray не викликано)


def test_invalid_edition_marker_is_logged_and_stops_before_data(tmp_path,monkeypatch):
    # build_edition.current кидає ValueError('Некоректний файл видання build_edition.json: ...'):
    # код 2, у журналі є текст причини, у теці даних є лише logs


def test_maintenance_commands_check_the_edition_marker(tmp_path,monkeypatch):
    # storygen.maintenance.main(['fsck','--data-dir',d]) з некоректною позначкою: ненульовий код і причина в stderr, fsck не виконано


def test_app_info_has_a_per_process_instance_id(tmp_path):
    # два create_app дають різні instance_id; поле є у відповіді; інші поля без змін
```

- [ ] **Крок 2: Запустити й побачити падіння** — `python -m pytest tests/test_desktop.py -q`: модуля немає.

- [ ] **Крок 3: Реалізувати.** Сервер — `uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, workers=1, log_config=None))` у потоці-демоні; очікування `server.started` до 30 с, інакше код 4. `stop` виставляє `server.should_exit=True`. Запис `server.json`: `{"url","instance_id","pid"}`, атомарно (тимчасовий файл і заміна).

- [ ] **Крок 4: Запустити** `python -m pytest tests/test_desktop.py tests/web/test_app_info.py tests/test_build_edition.py -q` — усі проходять.

- [ ] **Крок 5: Коміт** — `feat(desktop): launcher entry with file logging and a running-server record (#30)`.

---

### Задача 2: Резервна копія перед міграцією

**Файли:**
- Створити: `src/storygen/storage/pre_migration.py`
- Змінити: `src/storygen/storage/database.py` (константа `SCHEMA_VERSION = 5` замість літерала в останній перевірці), `src/storygen/desktop.py`
- Тест: `tests/storage/test_pre_migration.py`, доповнення `tests/test_desktop.py`

**Інтерфейси:**
- Дає:
  - `pending_migration(data_dir: Path) -> int | None` — поточна `user_version`, якщо файл бази існує і `0 < user_version < SCHEMA_VERSION`; читає базу лише для читання й нічого не створює.
  - `backups_dir(data_dir: Path) -> Path` — `data_dir.parent / (data_dir.name + '-backups')`.
  - `backup_before_migration(data_dir: Path, now: datetime | None = None) -> Path | None` — `None`, якщо міграції немає; інакше шлях копії. Кидає `PreMigrationBackupFailed(ValueError)` з авторським текстом без шляхів творів.
- Споживає: `storage.backup.create_backup` без змін.

- [ ] **Крок 1: Написати тести, що падають**

```python
def old_schema_dir(tmp_path,version=4):
    # база з міграціями 001..version (як у пробі П9), один файл версії в теці твору


def test_no_database_and_current_schema_need_no_backup(tmp_path):
    # тека без бази -> None; свіжа Repository(tmp) -> pending_migration is None і backup_before_migration is None;
    # нічого не створено поруч


def test_old_schema_is_backed_up_next_to_the_data_dir(tmp_path):
    data=old_schema_dir(tmp_path)
    path=backup_before_migration(data,now=datetime(2026,11,11,9,30,5))
    assert path==tmp_path/(data.name+'-backups')/'pre-migration-v4-20261111-093005'
    # у копії user_version==4, manifest.json має status 'complete'; у джерелі user_version досі 4


def test_backup_failure_blocks_the_migration(tmp_path,monkeypatch):
    # create_backup кидає ValueError -> PreMigrationBackupFailed; user_version джерела не змінилася


def test_existing_destination_is_a_failure_not_an_overwrite(tmp_path):
    # два виклики з тим самим now: другий кидає PreMigrationBackupFailed, перша копія ціла


def test_desktop_backs_up_then_migrates(tmp_path):
    # main на теці зі старою схемою: копія є, після старту user_version==SCHEMA_VERSION, у журналі шлях копії


def test_desktop_refuses_to_start_when_backup_fails(tmp_path,monkeypatch):
    # код 3, user_version не змінилася, сервер не стартував, причина в журналі
```

- [ ] **Крок 2: Запустити й побачити падіння** — `python -m pytest tests/storage/test_pre_migration.py -q`.

- [ ] **Крок 3: Реалізувати.** Версію читати через `sqlite3.connect('file:<шлях>?mode=ro', uri=True)`. Теку копій створювати перед викликом `create_backup` (він вимагає наявного батьківського каталогу).

- [ ] **Крок 4: Запустити** `python -m pytest tests/storage tests/test_desktop.py -q` — усі проходять.

- [ ] **Крок 5: Коміт** — `feat(desktop): verified backup before a schema migration (#30)`.

---

### Задача 3: Значок у треї

**Файли:**
- Створити: `src/storygen/desktop_tray.py`
- Змінити: `src/storygen/desktop.py` (типовий `tray`), `src/storygen/web/static/i18n.json` (підписи меню), `pyproject.toml` (package-data для значка, якщо він окремим файлом)
- Тест: `tests/test_desktop_tray.py`

**Інтерфейси:**
- Дає:
  - `menu_items(url, data_dir, backups_dir, stop, opener, reveal, locale) -> list[tuple[str, Callable]]` — три пункти в порядку: «Відкрити Obscura» / `Open Obscura` (типова дія), «Тека творів» / `Stories folder`, «Вийти» / `Quit`.
  - `run_tray(url, data_dir, backups_dir, stop) -> None` — блокує до «Вийти»; ліниво імпортує `pystray`; якщо імпорт не вдався, кидає `TrayUnavailable`.
  - Мова меню — системна мова користувача через `locale.getlocale()`: `uk` для української, інакше `en`.
- Споживає: `desktop.main(..., tray=...)`; при `TrayUnavailable` або `--no-tray` `main` пише в журнал і чекає на потік сервера.

- [ ] **Крок 1: Написати тести, що падають**

- `menu_items`: три підписи обома мовами в зазначеному порядку; «Відкрити» викликає `opener(url)`; «Тека творів» викликає `reveal(data_dir)`; «Вийти» викликає `stop()` рівно раз.
- `run_tray` із підставним модулем `pystray` (об’єкт у `sys.modules`): значок створено з назвою `Obscura`, меню з трьох пунктів, типовий пункт — перший; вибір «Вийти» викликає `stop` і `icon.stop()`.
- Без `pystray` (`sys.modules['pystray']=None`): `TrayUnavailable`; `desktop.main` у цьому разі не падає, пише «трей недоступний» у журнал і працює до зупинки сервера.

- [ ] **Крок 2: Запустити й побачити падіння** — `python -m pytest tests/test_desktop_tray.py -q`.

- [ ] **Крок 3: Реалізувати.** Значок — наявний `web/static/favicon.svg` не підходить для `pystray` (потрібен растр): згенерувати 64×64 через Pillow з кольорів бренду в коді, без нового файла. «Тека творів» — `os.startfile(data_dir)` у Windows.

- [ ] **Крок 4: Запустити** `python -m pytest tests/test_desktop_tray.py tests/test_desktop.py -q` — усі проходять.

- [ ] **Крок 5: Коміт** — `feat(desktop): tray icon with open, folder and quit (#30)`.

---

### Задача 4: SPEC, ручна перевірка, повна перевірка

**Файли:**
- Змінити: `SPEC.MD`, `docs/verification/traceability.json`, `docs/verification/manual.md`, `docs/site/uk/install.md`, `docs/site/en/install.md`

- [ ] **Крок 1: `SPEC.MD`.** Нова вимога `DESKTOP-001 — Запуск установленої збірки` зі Scenario: `S01` тека даних і журнал; `S02` запис про сервер і другий запуск (довіра лише за `instance_id`); `S03` копія перед міграцією й відмова стартувати без неї; `S04` трей і вихід; `S05` некоректна позначка видання зупиняє `storygen-desktop` і команди `fsck`/`backup`/`restore`. BUILD-EDITION-001-S05: додати `instance_id` до переліку полів. Технічний опис у розділі Architecture; у «Known limitations»: значення порту для MCP-моста лишається 8765 за замовчуванням, тож при зайнятому порту міст треба налаштувати на адресу з `server.json`. Записи traceability з вузлами тестів задач 1–3.

- [ ] **Крок 2: Ручна процедура** `manual.md#desktop-launcher` і її виконання: встановити extra `desktop`, запустити `storygen-desktop --data-dir <тимчасова тека>` через `pythonw.exe` (без консолі, потоки `None`): сторінка відкривається, значок у треї є, меню працює, другий запуск відкриває ту саму адресу, «Вийти» завершує процес і прибирає `server.json`. Повторити на копії теки зі старою схемою з проби П9: копія в сусідній теці, застосунок стартує. Результат — у повідомленні коміту.

- [ ] **Крок 3: Сторінка сайту `install` (uk/en).** Короткий розділ «Запуск без консолі»: команда `storygen-desktop`, де лежать твори, журнал і копії, що робить значок у треї. `python scripts/check_site.py --rehash install`.

- [ ] **Крок 4: Перевірка й коміти.** `python scripts/check_docs.py` — код 0; `verify.py` з короткої теки на коміті гілки — `state: passed`; коміти `docs(spec): DESKTOP-001 …` і `docs(status): …`.

---

## Після задач

1. Наскрізне рев’ю гілки окремим рев’юером із наголосом на «Фокус рев’ю».
2. Крос-рев’ю, таблиця рішень в описі PR; PR на `main` без `Closes #30`; запис у журнал виконання; оновити основну теку.
3. Наступний план — пакування: скрипт збирання (PyInstaller без консолі, позначка видання з перевіркою, що вона в пакеті, сторонні ліцензійні повідомлення для `keyring`, `pystray`, Pillow), маніфест MSIX і `makeappx`. Перед ним потрібна згода власника на встановлення інструмента: Windows SDK через `winget` або менший пакет `Microsoft.Windows.SDK.BuildTools` з nuget.org.
