# Інтеграція Codex — план основи

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Безпечний запис користувацької MCP-конфігурації Codex, детермінований пакет п’яти скілів із джерел Claude та його встановлення/оновлення без втрати авторських файлів. UI додається наступним планом.

**Architecture:** Незалежні модулі конфігурації, генерації та керованого встановлення; CLI — тонкий адаптер генератора/установника. Межі й поведінка відповідають затвердженій специфікації. Кореневий контракт і traceability змінюються разом із відповідним кодом у кожній задачі, без передчасних обіцянок про UI чи discovery клієнтів.

**Tech Stack:** Python >=3.10, pathlib, dataclasses, hashlib, json, tempfile, TOML Kit >=0.13,<1, pytest. Жодних викликів моделей.

**Spec:** [2026-11-17-codex-integration-design.md](../../specs/2026-11/2026-11-17-codex-integration-design.md), затверджено власником 17.11.2026.

**Статус:** затверджено власником 17.11.2026; виконання нативне.

## Global Constraints

- Робоча тека виконання — окремий worktree у C:/tmp; інтерпретатор — C:/Projects/text-generator/.venv/Scripts/python.exe. PYTHONPATH у дочірньому Python явно починається з src поточного worktree.
- Не змінювати integrations/claude/obscura/**, scripts/build_store.py, src/storygen/packaging*.py, store_build/**. Не рефакторити Claude; незмінені тести Claude залишаються зеленими.
- tomlkit>=0.13,<1 додається тільки до extra web. Пакування залежності й live discovery — критерії периферії до злиття, не результати цього плану.
- MCP-файл: абсолютний CODEX_HOME/config.toml або USERPROFILE/.codex/config.toml. Корінь скілів: USERPROFILE/.agents/skills, незалежно від CODEX_HOME. У production fallback USERPROFILE — Path.home(); у тестах корені завжди підмінені.
- Запис конфігурації керує command, args, enabled=true у mcp_servers.obscura; зберігає інші stdio-політики й інші налаштування; при переході HTTP→stdio прибирає лише конфліктні HTTP-поля цієї таблиці.
- Backup і staging скілів — .agents/obscura-backups/<operation-id> та .agents/obscura-staging/<operation-id>, поза сканованим skills/. Назви п’яти встановлених тек починаються з obscura-.
- Ні справжній ~/.codex, ні ~/.agents не читаються й не змінюються тестами. Усі pytest base/temp roots — C:/tmp; subprocess не має запускати codex exec, claude -p, мережу або моделі.
- Кожна задача: RED→GREEN, check_docs.py, git diff --check, журнал і окремий коміт. Наприкінці — verify.py для повного набору та цілісне незалежне рев’ю.
- План основи й майбутня периферія входять в один PR реалізації на main. До завершення периферії цей PR лишається draft; не оголошувати всю інтеграцію готовою.

## Review Focus

1. Windows junction/symlink у цільовій теці не має спрямувати запис поза тестовий/користувацький корінь. Задача 3: test_reparse_target_is_refused_before_any_write.
2. Вимкнений або HTTP-запис obscura з локальними політиками не повинен втратити сторонні налаштування. Задача 1: test_http_migration_keeps_unrelated_settings.
3. Зміна Claude-джерел, яка залишає в тексті непомітний /model або Advisor, має зупинити генерацію до встановлення. Задача 2: test_source_drift_refuses_the_whole_bundle.
4. Помилка третього rename та паралельна авторська правка не повинні призвести до руйнівного відкату чи хибного installed. Задача 3: test_rollback_preserves_concurrent_author_edit.
5. CLI, запущений із чужим cwd чи editable install іншого worktree, мусить використати власний checkout і тимчасові корені. Задача 4: test_cli_uses_its_checkout_from_another_cwd.

## Файли й інтерфейси

| Файл | Відповідальність |
|---|---|
| src/storygen/codex_connect.py | Вибір конфігурації, стан, безпечний запис TOML, команда PowerShell для копіювання; не запускає процесів |
| src/storygen/codex_skills.py | Генерація байтів п’яти самодостатніх скілів із незмінених Claude-джерел |
| src/storygen/codex_skill_install.py | Встановлення, маніфест, конфлікти, копії, staging, відкат і результат часткової відмови |
| scripts/install_codex_skills.py | Взаємовиключні --output/--install, виклик модулів і JSON-результат, exit code |
| tests/test_codex_connect.py | Реальні тимчасові TOML-файли, резервні копії, помилки й конкурентна зміна |
| tests/test_codex_skills.py | Генератор на реальних джерелах і навмисно пошкоджених тимчасових копіях |
| tests/test_codex_skill_install.py | Реальні тимчасові файлові дерева й точкові помилки файлових операцій |
| tests/test_install_codex_skills.py | Запуск CLI дочірнім Python з ізольованими профілями та cwd |
| SPEC.MD, docs/verification/traceability.json | Лише реалізований контракт поточної задачі |
| docs/superpowers/plans/2026-10-20-remediation-progress.md | Фактичні RED/GREEN, рішення, результати й SHA |

Рішення виконавця: установник — окремий модуль codex_skill_install.py, щоб генератор не містив запису в профіль. Це уточнення внутрішнього поділу, не зміна затвердженої поведінки. Manifest має schema=1, generator_version, sources (відносний шлях→SHA-256 джерела), files (відносний шлях→SHA-256 установлених байтів, без самого маніфесту). У ньому немає абсолютних шляхів або матеріалів творів.

### Task 1: Безпечна MCP-конфігурація

**Files:** створити src/storygen/codex_connect.py, tests/test_codex_connect.py; змінити pyproject.toml, tests/conftest.py, SPEC.MD, traceability та журнал.

**Interfaces:**
- config_path(userprofile: Path, codex_home: str | None) -> Path; відносний/порожній заданий CODEX_HOME — CodexConfigError.
- config_status(path: Path, command: list[str]) -> dict[str, object]; state = missing/configured/different/invalid, path; жодного повного вмісту/env.
- write_config(path: Path, command: list[str]) -> ConfigResult; поля result=configured|unchanged, path: Path, backup: Path|None, created: bool.
- powershell_command(command: list[str]) -> str; починається з codex mcp add obscura --, кожен аргумент — коректно екранований PowerShell-літерал.
- CodexConfigError(ValueError): безпечна причина відмови; OSError окремо для файлових відмов. Модуль не читає середовище під час імпорту.

- [x] 1. Додати автоматичну isolated_codex у conftest.py: USERPROFILE, HOME й CODEX_HOME спрямувати до tmp_path_factory; Path.home() повертає тимчасовий профіль. Не змінювати існуючу isolated_claude. Нові тести використовують ці корені; ізоляцію перевірити test_codex_roots_are_temporary.
- [x] 2. Додати тести з реальними файлами. Основні точні результати:
  ~~~python
  result = write_config(tmp_path / "profile/config.toml", command)
  assert result.result == "configured" and result.created and result.backup is None
  assert config_status(result.path, command)["state"] == "configured"
  before = result.path.read_bytes()
  repeat = write_config(result.path, command)
  assert repeat.result == "unchanged" and repeat.backup is None
  assert result.path.read_bytes() == before
  ~~~
  Окремі функції: test_missing_config_is_created, test_existing_config_is_idempotent, test_http_migration_keeps_unrelated_settings, test_invalid_toml_is_untouched, test_non_table_is_untouched, test_unique_backup_keeps_exact_previous_bytes, test_changed_file_is_not_overwritten, test_failed_replace_keeps_original, test_powershell_command_quotes_apostrophes, test_config_home_must_be_absolute. У HTTP-тесті залишити інший сервер, верхній коментар, model і tools-політику obscura; перевірити enabled=true, нові command/args та відсутність url/oauth/http_headers тільки в obscura. Тест concurrent change змінює файл після створення backup, але до фінальної звірки, й доводить збереження авторських байтів; він не приписує гарантій вузькій гонці після останньої звірки.
- [x] 3. Запустити тести до модуля — RED через відсутній імпорт/можливість запису, не помилку фікстури. Додати tomlkit до extra web й установити цю залежність у тестове середовище, лише після схвалення виконання плану.
- [x] 4. Реалізувати парсинг/перевірку таблиць, керовані поля, унікальну байтову копію, тимчасовий файл поруч, повторний parse, замок, перевірку актуальних байтів перед replace й перечитування після нього. Якщо зовнішній редактор змінив результат після replace, не відновлювати автоматично старий файл. Зафіксувати залишкову вузьку зовнішню гонку як обмеження.
- [x] 5. Додати STORE-MCP-S12 до STORE-MCP-001: WHEN виклик конфігуратора Codex — THEN керовані поля/backup/unchanged/відмова; жодної заяви, що UI вже існує або клієнт підключено. Traceability посилається на конкретні функції цієї задачі. Сайт поки не змінювати: кнопки й публічної команди ще немає; причину записати в коміт.
- [x] 6. Запустити test_codex_connect.py та незмінені test_claude_connect.py, check_docs.py і diff --check; усі мають завершитися кодом 0. Коміт: feat(codex): preserve user MCP configuration.

### Task 2: Детермінований генератор п’яти скілів

**Files:** створити src/storygen/codex_skills.py, tests/test_codex_skills.py; оновити SPEC.MD, traceability й журнал.

**Interfaces:**
- SkillBundle — dataclass із files: dict[str, bytes], sources: dict[str, str], generator_version: str. Ключі files — відносні POSIX-шляхи виду obscura-start-story/SKILL.md.
- generate_skills(source: Path) -> SkillBundle, source — корінь integrations/claude/obscura.
- GenerationError(ValueError) — структурний дрейф, неприпустимий шлях, посилання або неочікувані клієнтські інструкції. Генерація не пише на диск.

- [x] 1. Написати test_real_sources_generate_five_self_contained_skills і test_generation_does_not_change_sources. Перевірити рівно п’ять obscura-* тек, узгоджені name/назву теки, непорожній description, переносний frontmatter; джерела до/після мають однакові байти. Повторний виклик дає однаковий files/sources.
- [x] 2. Додати test_rules_and_references_are_portable: правила рівно один раз в усіх SKILL.md; усі локальні посилання розв’язуються від теки поточного файла в межах bundle; змінних кореня плагіна немає. Перевірити адаптацію AskUserQuestion із текстовим fallback, назв клієнта і звернень до інших скілів.
- [x] 3. Додати test_planning_and_scene_routing_use_current_session і test_provider_recipes_are_preserved: у start-story більше немає секції зі /model або Advisor, сцена не маршрутизує на Sonnet/Opus, але рецепти provider/model та протокол етапів збережені байтово, крім необхідної адаптації локальних посилань.
- [x] 4. Додати test_source_drift_refuses_the_whole_bundle, test_external_reference_is_rejected, test_symlink_source_is_rejected, test_unknown_mcp_tool_is_reported: змінити очікувану межу Model, лишити клієнтську команду, додати посилання поза джерелом і невідомий MCP-інструмент у тимчасових копіях. Структурна звірка згадок із storygen.mcp.bridge.TOOLS виконується тестами, не імпортом MCP у production-генератор.
- [x] 5. Запустити RED, реалізувати лише структурно перевірені перетворення. Секції Model/Model routing замінюються цілком; не використовувати глобальну Claude→Codex заміну. Включити лише п’ять SKILL.md і їхні потрібні references; відхиляти нерозв’язані/зовнішні шляхи до будь-якої установки.
- [x] 6. Додати Requirement CODEX-SKILLS із S01 (самодостатній переносний результат), S03 (MCP-контракт і поточна сесія); traceability — точні тести цієї задачі. Опис встановлення поки не оголошувати готовим. Запустити нові тести й незмінені test_claude_plugin.py, check_docs.py, diff --check. Коміт: feat(codex): generate portable Obscura skills.

### Task 3: Кероване встановлення й оновлення

**Files:** створити src/storygen/codex_skill_install.py, tests/test_codex_skill_install.py; оновити SPEC.MD, traceability й журнал.

**Interfaces:**
- install_skills(bundle: SkillBundle, userprofile: Path) -> InstallReport.
- InstallReport: result = installed|unchanged|conflict|partial|failed; installed: tuple[str, ...], restored: tuple[str, ...], conflicts: tuple[str, ...], backups: tuple[Path, ...], errors: tuple[str, ...].
- errors містить безпечні коди причин, не вміст файлів/винятків. failed означає відмову до змін або повне безпечне відновлення; partial — є невідновлена власна зміна чи зовнішній конфлікт. Це уточнення відмови, не нова успішна поведінка.
- installed у звіті містить лише теки, які залишилися встановленими цим викликом; після повного відкату installed=(), restored містить відновлені назви.
- Власний маніфест .obscura-install.json у кожній теці, schema=1. Усі шляхи й хеші маніфесту перевіряються, сам маніфест не входить до files.

- [x] 1. Написати test_first_install_and_repeat: результат installed має рівно п’ять перевірених тек; усі байти відповідають bundle; другий виклик unchanged і не створює backup. test_managed_update_creates_exact_backups перевіряє стару керовану версію, нові байти, новий manifest, копії поза skills/.
- [x] 2. Написати параметризований test_conflict_preflight_leaves_all_targets_untouched: чужа тека без manifest, зіпсований manifest, змінений SKILL.md, видалений reference, доданий автором файл. В кожному випадку result=conflict; повний знімок усіх п’яти тек не змінюється.
- [x] 3. Додати test_reparse_target_is_refused_before_any_write для symlink і Windows junction/FILE_ATTRIBUTE_REPARSE_POINT. Якщо тест створює junction, він спрямований лише у C:/tmp; ціль і сторонній файл лишаються незмінними. Перевіряються .agents, skills, конкретна ціль і небезпечні маніфестні шляхи; не ходити через reparse при обчисленні inventory.
- [x] 4. Додати test_failed_third_rename_restores_original_trees і test_rollback_preserves_concurrent_author_edit: точково спричинити збій третьої заміни; при незмінених власних байтах відновити попередній стан і result=failed. Якщо автор паралельно змінив першу вже встановлену теку, вона не стирається; result=partial, report називає конфлікт і копії. test_backups_and_staging_are_not_discoverable перевіряє inventory skills/ після обох відмов.
- [x] 5. Запустити RED і реалізувати preflight усього пакета, перевірку маніфестів/сум, staging, унікальні копії, замок установки й контрольовані rename. Перед кожною заміною повторно звірити попередній стан. Відкат — лише для своїх незмінених результатів. Фінальний installed — тільки після перечитування всіх цілей; одного маніфесту недостатньо. Тест busy-lock доводить, що одночасний установник відмовляє без запису. Не додавати автоматичне очищення чужого stale-lock: помилка називає потребу перевірки.
- [x] 6. Додати CODEX-SKILLS-S02 й traceability цієї задачі; технічний опис manifest, шляхів, безпечного відкату й залишкової зовнішньої гонки. Запустити всі три нові файли тестів, check_docs.py і diff --check. Коміт: feat(codex): safely install and update generated skills.

### Task 4: CLI і цілісна перевірка основи

**Files:** створити scripts/install_codex_skills.py, tests/test_install_codex_skills.py; оновити парні docs/site/{uk,en}/mcp.md, їхній маніфест, SPEC.MD, traceability, docs/STATUS.md та журнал. Ручні кнопки й GUI ще не описувати як доступні.

**Interfaces:**
- main(argv: list[str] | None = None) -> int; взаємовиключні --output PATH / --install. Джерело за замовчуванням визначає checkout самого скрипта, не cwd чи сторонній editable install.
- --output пише bundle у нову або порожню задану теку, не перезаписує непорожню. --install використовує USERPROFILE/.agents/skills. Веб-адаптер згодом викликає модулі без цих довільних параметрів.
- source_root() -> Path повертає корінь checkout самого скрипта; тест генераційної відмови підміняє лише це визначення на fixture, не production-файли.
- stdout — один JSON-результат із result, names і безпечними шляхами копій; exit 0 для generated/installed/unchanged, 1 для відмов, 2 для неправильних аргументів. Не друкувати вміст конфігурації чи traceback.

- [ ] 1. Написати test_cli_output_is_deterministic, test_cli_requires_one_destination, test_cli_refuses_nonempty_output, test_cli_installs_into_temporary_profile. Запускати дочірнім Python з PYTHONPATH=<поточний checkout>/src, окремими HOME/USERPROFILE/CODEX_HOME та cwd у C:/tmp; перевіряти реальні результати на диску й exit code.
- [ ] 2. Додати test_cli_uses_its_checkout_from_another_cwd: cwd містить чужу integrations/claude із sentinel; результат має збігатися з джерелом самого скрипта й не містити sentinel. Додати test_cli_generation_failure_does_not_install: зіпсований fixture-джерело тестувати через завантаження скрипта та ін’єкцію визначення checkout, не редагувати справжнє integrations/.
- [ ] 3. Запустити RED, реалізувати тонкий CLI, без дублювання генератора/установника, глобальної установки пакетів чи shell-викликів Codex. Сайт uk/en отримує точну CLI-команду, п’ять назв, корені, повторну установку, конфлікти й ручне відновлення/видалення. Окремо уточнити storygen-mcp.exe для checkout і obscura-mcp.exe для Store. Чинні пояснення Claude зберегти; Store-скіли лишаються недоступними.
- [ ] 4. Перевірити весь контракт основи: generate→install→update→conflict, config write→status→unchanged. Джерела Claude і заборонені файли мають порожній diff. Додати CODEX-SKILLS-S06 для CLI (S04/S05 зарезервовані під живі клієнти/Store-UI), traceability на фактичні функції цього файла. Підтвердити пару сторінок check_site.py --rehash mcp.
- [ ] 5. Запустити check_docs.py та повний verify.py в worktree C:/tmp, прочитати JUnit/pytest.log і docs/STATUS.md. Будь-який failed/error дослідити, skipped не зараховувати до passed. Чинні тести Claude не змінювати для маскування регресій. Зафіксувати комітом feat(codex): expose source-checkout skill installer; зазначити оновлені uk/en інструкції.
- [ ] 6. Провести незалежне цілісне рев’ю всього механізму за планом і Review Focus. Важливі дефекти виправити RED→GREEN, повторити потрібні перевірки; записати висновки й рішення у журнал. Не оголошувати цим виконаними живі discovery, Store-freeze чи якість роботи моделей.

## Межа наступного плану

Після виконання задач 1–4 та рев’ю основи написати окремий план периферії за її реальними інтерфейсами. Він включає маршрути Codex, middleware/long_prose_guard, UI і переклади, SPEC/traceability S13/S04/S05, парні інструкції кнопок, ізольоване discovery клієнтів, перевірку нової Store-залежності, загальний gate, cross-review PR, push і синхронізацію основної теки. Жодних моделей для ручної перевірки не запускати. Неможливість ізолювати клієнт або виконати freeze — явний невиконаний критерій, який повертається власнику до злиття.

## Самоперевірка плану

- Охоплення основи: §3 дизайну — задача 1; §4 — задачі 2–4; §6–§8 — контракт, traceability та звіт кожної задачі. UI §5 і live/Store-критерії відкладені явно, не позначені готовими.
- Усі типи й результати, які споживає наступна задача, визначені вище; result=failed уточнений у дизайні як невдала установка з повним відновленням.
- Кожен Review Focus має власний тест у задачі власника. Немає готових тіл production-функцій чи нового незатвердженого продуктового вибору.
- Реалізація чекає на перегляд цього плану та вибір способу виконання за writing-plans; рекомендований спосіб — нативно в цій сесії, з одним незалежним рев’ю основи наприкінці.
