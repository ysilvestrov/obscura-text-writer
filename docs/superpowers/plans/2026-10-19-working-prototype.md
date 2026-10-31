# Перший робочий прототип: наскрізний план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Користувач уже обрав послідовне виконання в поточному чаті; спосіб виконання повторно не обирається.

**Goal:** Отримати локальний застосунок, у якому автор імпортує план і персонажів, налаштовує моделі, створює оповідання українською через чотири етапи з пам’яттю, редагує сцени, відновлює перервані запуски, переглядає автоматичні оцінки та експортує твір.

**Architecture:** Python-сервер обслуговує локальний вебінтерфейс; окремий послідовний виконавець проводить модельні запити та зберігає події. SQLite містить стан, залежності й посилання на незмінні файлові версії. Уже реалізований оцінювач підключається через адаптер і зберігає власний CLI для тестування промптів через Codex.

**Tech Stack:** Python 3.10+, FastAPI, Uvicorn, Jinja2, `python-multipart`, звичайні JavaScript/CSS, SQLite через `sqlite3`, Pydantic 2, наявні `openai>=2,<3`, `httpx`, `python-dotenv`. Для перевірок — pytest, HTTP MockTransport, FastAPI TestClient та Playwright для невеликого набору браузерних сценаріїв. Версії нових залежностей фіксуються після встановлення й перевірки сумісності з наявним середовищем; Node-збірка інтерфейсу не потрібна.

**Spec:** [Погоджена специфікація](../specs/2026-10-19-story-generation-design.md). Попередній [план оцінювача](2026-10-19-automatic-evaluator.md) залишається історією першого етапу, а цей документ визначає весь залишок робіт до прототипу.

**Status:** План прийнято й виконується на feat/working-prototype. Завдання 1–12 технічно реалізовано, 13: повне калібрування виконано, але quality gate не пройдено; 14: технічні сценарії та незалежний огляд із виправленнями завершено. Завдання 15 — реальні модельні пілоти й літературне приймання — обліковується окремо в docs/prototype-acceptance.md.

## Global Constraints

- «Створити локальний застосунок із вебінтерфейсом українською мовою для перетворення авторського плану та описів персонажів на зв’язне оповідання обсягом приблизно 5–15 тисяч слів».
- «Послідовність: завдання → написання → редактура → пам’ять → наступна сцена».
- «Чотири незалежно налаштовані ролі: підготовка завдання, письменник, літературний редактор, ведення пам’яті»; оцінювач є окремою допоміжною роллю.
- «Суттєві зміни формуються як окремі пропозиції. В автоматичному режимі вони не застосовуються без рішення користувача».
- «Збережена версія не переписується; ручне редагування створює нову».
- «Зміни ранніх сцен позначають залежні матеріали для перевірки; вже створені сцени автоматично не переписуються».
- «Матеріали не обрізаються непомітно»; «Немає прихованого переходу з локального провайдера на хмарний».
- «Застосунок не додає власних тематичних фільтрів, прихованих евфемізацій чи правил зменшення відвертості». Відмова моделі зберігається як результат провайдера, без прихованого переписування або fallback.
- «Після часткової відповіді або невизначеного завершення запиту автоматичне повторне надсилання вимкнене».
- «Ручна літературна перевірка виконується для вже відтестованої версії після технічних тестів та автоматичних оцінок».
- Windows, українські повідомлення й тексти, файли UTF-8; зовнішні оригінали `C:/Projects/Texts/Wrong doors/` не змінюються.
- Локальний API початково `http://localhost:1235/v1`, точні model ID та реальний контекст перевіряються на машині. Завантажена модель не вважається автоматично активною.
- Лише локальний Git і запуск на комп’ютері. Хостинг, remote, Cloudflare і зміна його тарифу не входять до плану.
- Нові платні модельні запуски виконуються після вибору моделей і бюджету; конкретні ціни перевіряються перед ними. Проєкт не обіцяє жорсткого грошового ліміту без механізму його забезпечення.

## Review Focus

1. Аварія між записом тексту і фіксацією стану: завершена сцена не губиться, часткова не стає поточною; перезапуск не повторює невизначений платний запит (завдання 1, 7, 9, 14).
2. Дві вкладки, подвійний клік або повтор HTTP-запиту: не створюються дві одночасні генерації й не затирається новіша ручна правка (завдання 3, 7, 9, 10).
3. Зміна ранньої сцени, персонажа чи пам’яті під час генерації: походження результату лишається точним, застарілий результат не просуває процес мовчки (завдання 5, 7, 8, 11).
4. Закриття вкладки, розрив SSE, скасування під час довгого очікування першого токена: сервер продовжує керувати запуском, UI не обіцяє припинення обчислення провайдера (завдання 6, 9, 10, 14).
5. Матеріал із розміткою, інструкціями чи схожим на шлях ім’ям: оригінал збережено, текст не виконується як HTML/код, файли залишаються в каталозі даних; ключі не потрапляють у браузер або звіти (завдання 2–4, 10, 12).

## 1. Від чого починаємо

Базовий коміт: `0855244`, гілка `feat/automatic-evaluator`. На момент складання плану робоча папка чиста; повторний запуск pytest дав **65 passed**.

Уже є:

- `src/storygen/evaluation/`: строгі входи/звіти, українська рубрика, перевірка цитат, агрегація, звіти та fingerprints.
- API-адаптери локального сервера й OpenRouter; окремий `codex_cli` для випробування промпту.
- CLI `evaluate`, `compare`, `calibrate`, dry-run; десять контрольних прикладів.
- Незалежний огляд, виправлення та чотири реальні проби Codex CLI.

Ще немає: сховища творів, імпорту зі структурою сцен, виконавця генерації, пам’яті твору, вебсервера, інтерфейсу й експорту. Оцінювач не пройшов повного калібрування на явно обраній моделі. Реальні локальний API й OpenRouter ще не перевірені інтеграційно.

Перший крок виконання — гілка `feat/working-prototype` **від `0855244` або його поточного нащадка з цим планом**, у поточній папці за збереженим вибором користувача. Об’єднання попередньої гілки в main не є передумовою; історія оцінювача має входити до нової гілки. Не починати від main, де оцінювача поки немає.

## 2. Видимі результати по дорозі

| Віха | Завдання | Що вже можна зробити |
|---|---|---|
| A. Авторські матеріали в браузері | 1–3 | Створити твір, завантажити план і персонажів, розділити сцени, відредагувати й зберегти матеріали |
| B. Повний цикл однієї сцени | 4–7 | Налаштувати моделі в браузері; через сервіс і тестовий runner отримати завдання, прозу, редактуру й пам’ять із потоковими подіями |
| C. Автоматичний прохід твору | 8–10 | Пройти сцени послідовно, робити паузи, відновлюватися, редагувати попередні сцени зі збереженням історії |
| D. Оцінювання та готовий файл | 11–12 | Переглянути оцінки й різницю версій, зібрати поточний текст, запустити застосунок одним локальним скриптом |
| E. Перевірений прототип | 13–15 | Відкалібрований оцінювач, перевірене відновлення, реальний прохід семи сцен і підсумкова ручна оцінка |

Це п’ять послідовних блоків із власними перевірками. Не потрібно чекати завершення всього бекенду, щоб побачити перший екран. Калібрування й вибір моделей можна готувати паралельно з інфраструктурою; їхній результат потрібен перед підсумковою перевіркою якості, а не перед створенням сховища.

## 3. Технічні рішення для цього прототипу

### Сервер і інтерфейс

FastAPI + Jinja2 формують сторінки; невеликі JS-модулі виконують запити, редагування та оновлення стану. Одна основна сторінка твору використовує погоджений поділ: сцени ліворуч, робочий текст у центрі, контекст/пам’ять/параметри праворуч. Початковий редактор — textarea з кнопкою збереження й індикатором незбережених змін; багатий текстовий редактор не потрібний.

Процес запускається на `127.0.0.1:8765`, один Uvicorn worker, без reload у звичайному режимі. Життєвий цикл сервера керує окремим потоком-виконавцем. Одна глобальна черга охоплює всі твори та всі ролі, включно з оцінювачем: одночасно активний лише один модельний запит застосунку.

SSE передає збережені події через `GET /api/runs/{run_id}/events`; браузер передає останній event ID після перепідключення. Закриття SSE закриває лише підписку. Довгий виклик моделі не виконується всередині HTTP-обробника сторінки.

### Дані та транзакції

Початковий корінь — ігнорований Git каталог `data/` у проєкті; параметр `--data-dir` дозволяє вибрати інший каталог. Усередині: `storygen.sqlite3`, `stories/{story_id}/sources/`, `versions/`, `runs/`, `exports/`. Шляхи формуються з внутрішніх ID, назви творів/файлів є лише метаданими.

SQLite: окреме connection на операцію/потік, foreign_keys=ON, WAL, busy_timeout=5000, послідовні міграції з user_version. Файли завершених версій записуються до тимчасового файла, закриваються й атомарно перейменовуються до фіксації посилання в транзакції. Збій може залишити файл без посилання, але не поточну версію без файла. Осиротілі файли виявляються під час перевірки; автоматичного видалення матеріалів немає.

Частковий текст пишеться у файл запуску, не є незмінною завершеною версією й не може стати current. Позначка завершення етапу, його dependencies і просування поточного покажчика фіксуються разом; уже записана версія може лишитися непоточною альтернативою. Просування використовує очікувану revision сцени; конфлікт лишає завершену альтернативну версію для перегляду й зупиняє автоматичне продовження.

### Запуски та відновлення

Один `Run` — один запит автора: етап, сцена або решта твору; один `StageAttempt` — один модельний виклик. Зберігаються точні вхідні версії, конфігурація ролі, prompt version, text/hash, usage, finish_reason і помилка. Реконструкція стану спирається на SQLite й завершені артефакти.

Після перезапуску running/cancellation_requested стають interrupted. Процес не надсилає невизначений запит повторно автоматично. «Продовжити» використовує завершені актуальні етапи; окрема дія «Повторити перерваний етап» явно створює нову спробу. Пауза спрацьовує на межі етапів. Скасування ставить cancellation_requested, намагається закрити потік відповіді й лишає частковий текст; cancelled підтверджується після виходу клієнта з запиту. UI не стверджує, що GPU або віддалений провайдер уже зупинили обчислення.

### Контекст і пам’ять

План майбутніх подій, авторський канон і факти вже написаних сцен мають різні типи. Для сцени N використовується пам’ять лише до N−1, релевантні картки, стиль, завдання та завершення попередньої сцени. Весь план може бути доданий для розуміння арки, з явною позначкою «майбутні події».

Пам’ять — послідовність незмінних знімків із facts, character_states, open_threads, timeline та посиланнями на source prose versions. Кожен новий факт має цитату з поточної сцени; збережені попередні факти зберігають свої джерела. При переході на іншу версію прози або ручній зміні пам’яті похідні матеріали позначаються неактуальними. Оновлення знімків і переписування самої прози — різні дії.

Плануємо явні бюджети контексту й резерв відповіді. За наявності перевіреного токенізатора оцінка точна для нього; інакше консервативна оцінка позначається приблизною. Перевищення не виправляється прихованим обрізанням. Для прототипу достатні видимий вибір карток і компактна структурована пам’ять; векторна база та RAG не потрібні.

## 4. Файли та спільні контракти

```text
src/storygen/
  domain.py                           # Story, Scene, VersionRef, Run, StageAttempt та помилки
  storage/{database,files,repository}.py
  storage/migrations/001_initial.sql
  authoring/{imports,blueprints,service}.py
  providers/{models,client,discovery,streaming}.py
  generation/{models,prompts,context,stages,pipeline,worker,dependencies,events}.py
  generation/resources/*.txt
  memory/{models,service}.py
  application/{settings,evaluation_bridge,exports}.py
  web/{app,routes_stories,routes_settings,routes_runs,routes_versions}.py
  web/templates/{base,library,story,settings}.html
  web/static/{app.css,api.js,editor.js,runs.js,versions.js}
  server.py
  evaluation/                         # уже існує; розвивається без втрати CLI
scripts/start.ps1
tests/{storage,authoring,providers,generation,memory,web,integration}/
tests/fixtures/prototype/              # нейтральні приклади та відповіді fake gateway
docs/{prototype-runbook,prototype-acceptance}.md
```

Контракти вводяться в зазначених завданнях; поле ID — рядок UUID, version/hash — рядки. Усі DTO строгі Pydantic-моделі, невідомі поля відхиляються.

| Контракт | Основні поля / призначення | Завдання |
|---|---|---|
| Story / StoryCreate | id, title, target_words (5000–15000), style_version_id, canon_version_id, characters_version_id?, revision | 1 |
| StyleProfile | genre, tone, point_of_view, tense, dialogue_rules, freedom=controlled_expansion; довільні авторські правила зберігаються текстом | 4 |
| Scene / SceneCreate | id, story_id, position, title, beats, target_words, character_ids[], revision, heads; позиції унікальні в творі | 1 |
| VersionRef | id, story_id, scene_id?, kind, format=text/json, sha256, relative_path, source_run_id?, complete | 1 |
| SourceFile / ImportResult | name, raw bytes / незмінні raw copies, текстові версії, запропоновані сцени, попередження | 2 |
| ProviderSettings / RoleSettings | local або openrouter, base_url, model, api_key_env, timeouts, context/output limits / role, settings, prompt_version_id | 4 |
| StoryBlueprint | сцени, персонажі, запропонований канон, ambiguity warnings із source citations; до застосування лише пропозиція | 4 |
| ContextBundle | story_id, messages, input_refs, serialized_prompt, config_snapshot, budget_report, fingerprint | 5 |
| MemorySnapshot | through_scene_id?, source_prose_refs, facts, character_states, open_threads, timeline, revision_sources | 5 |
| GenerationEvent | type=delta або terminal, text, finish_reason?, usage?, refusal?; terminal потрібний для успішного завершення | 6 |
| WriterBrief | scene_goal, required_beats, emotional_arc, constraints, target_words, proposed_changes | 7 |
| Run / RunRequest | story_id, scene_ids, scope=stage/scene/remaining, starting_stage?, pause_after[], expected_story_revision | 9 |
| StageAttempt | run_id, scene_id?, stage, state, input_refs/config/prompt snapshot, partial_path, result_ref?, promotion_status=applied/alternative/none, error, usage | 7, 9 |
| RunEvent | run_id, monotonic seq, type, payload; SSE ID дорівнює seq | 9 |

Kind версії: source_plan, source_characters, character_cards, scene_plan, canon, style, prompt, brief, draft, edited, manual, memory, evaluation. Scene.heads містить brief/draft/prose/memory. Поточна prose може посилатися на edited або manual; чернетка й редактура зберігаються поруч. Нормалізовані персонажні картки — окремий версійований JSON character_cards після застосування blueprint; до цього контекст може використовувати повний вихідний текст персонажів. Source text та raw-файли лишаються окремо й не замінюються JSON-картками.

У SQLite окремі таблиці stories, scenes, versions, role_settings, runs, stage_attempts, dependency_edges, run_events. `dependency_edges` посилаються на точні version IDs, не лише на scene IDs. Початкові run/attempt states: queued, running, paused, cancellation_requested, cancelled, interrupted, failed, incomplete, completed; допустимі переходи задає worker, а не браузер.

Моделі генерації не використовують `EvaluationRequest` як універсальний тип: writer повертає прозу, brief/memory — структуровані дані, оцінювач має свій контракт. `EvaluatorConfig` і fingerprints існуючого оцінювача зберігаються сумісними. Codex CLI лишається засобом оцінювання/тестування промптів, а не неявною заміною виробничих ролей.

ID ролей у конфігурації: planner, writer, editor, memory; допоміжний evaluator налаштовується окремо. Відповідність етапів: prepare/brief→planner, draft→writer, edit→editor, memory→memory. Model ID завжди задається явно; збережена конфігурація ролі не містить сам ключ, тільки назву змінної environment.

## 5. Завдання реалізації

Кожне завдання має власний RED→GREEN цикл і локальний коміт. Після цільових тестів запускається весь pytest-набір. У тестах модельні виклики імітовані; реальні інтеграційні запуски описані окремо в завданні 15. Відомий поточний `--basetemp=artifacts/pytest-tmp` означає, що pytest-процеси не запускаються одночасно в одній папці.

### Завдання 1. Сховище творів і незмінних версій

**Files:** створити `domain.py`, `storage/database.py`, `storage/files.py`, `storage/repository.py`, `storage/migrations/001_initial.sql`, `tests/storage/test_repository.py`; оновити пакування SQL-ресурсів у `pyproject.toml`.

**Interfaces:** `Repository(data_dir: Path)`; `create_story(data: StoryCreate) -> Story`; `create_scene(story_id: str, data: SceneCreate) -> Scene`; `get_story(id: str) -> Story`; `list_stories() -> list[Story]`; `list_scenes(story_id: str) -> list[Scene]`; `get_scene(id: str) -> Scene`; `save_version(story_id: str, scene_id: str | None, kind: str, text: str, input_refs: list[str], source_run_id: str | None = None) -> VersionRef`; `read_text(version_id: str) -> str`; `set_head(scene_id: str, head: str, version_id: str, expected_revision: int) -> Scene`. Ввести DTO з таблиці вище та `RevisionConflict`, `StorageCorruption`.

- [ ] Написати `test_versions_survive_reopen`: дві правки створюють різні ID, старий текст не змінюється; повторне відкриття Repository повертає той самий current. `test_stale_revision_cannot_replace_head`: друга вкладка зі старою revision отримує RevisionConflict. `test_failed_file_write_never_creates_current`: після збою файла немає DB-посилання; `test_missing_or_modified_blob_reports_corruption`: підмінений hash не читається як правильний текст.
- [ ] Запустити `python -m pytest tests/storage/test_repository.py -q`; очікується FAIL до появи Repository.
- [ ] Реалізувати SQLite-міграцію, файловий запис і наведені методи. У схемі передбачити всі таблиці з розділу 4; typed операції над runs додаються в завданні 9. Версії та dependencies незмінні; зміна current використовує транзакцію й revision. Суму цільових обсягів сцен можна редагувати; її відхилення від target твору показується як попередження, не виправляється автоматично.
- [ ] Повторити цільові тести та `python -m pytest -q`; очікується PASS. Повторний startup не змінює існуючих даних і не повторює міграцію.
- [ ] Коміт: `feat: persist stories scenes and immutable text versions`.

### Завдання 2. Імпорт плану, персонажів і ручна структура сцен

**Files:** створити `authoring/imports.py`, `authoring/service.py`, `tests/authoring/test_imports.py`, нейтральну копію тестових джерел у `tests/fixtures/prototype/`.

**Interfaces:** `import_sources(repo: Repository, story_id: str, files: list[SourceFile]) -> ImportResult`; `suggest_scene_sections(plan: str) -> list[SceneCreate]`; `update_scene_plan(repo: Repository, scene_id: str, text: str, expected_revision: int) -> Scene`; `reorder_scenes(repo: Repository, story_id: str, scene_ids: list[str], expected_revision: int) -> Story`.

- [ ] Написати `test_wrong_doors_import_proposes_seven_scenes`: заголовки «Сцена 1.»…«Сцена 7.» дають сім впорядкованих пропозицій, наскрізна тема й символи залишаються в загальному плані. `test_sources_preserved_byte_for_byte`: raw copy має SHA оригінальних байтів, український текст із BOM доступний для редагування як окрема версія. `test_filename_cannot_escape_data_root`: ім’я `../plan.md` зберігається як metadata, не шлях. `test_unknown_structure_remains_editable`: без впізнаваних заголовків пропонується одна сцена з усім планом і попередження про ручний поділ.
- [ ] Запустити `python -m pytest tests/authoring/test_imports.py -q`; очікується FAIL.
- [ ] Реалізувати імпорт `.md`/`.txt` із raw copies, UTF-8-sig декодуванням і лімітом 2 MiB на файл із явною помилкою перевищення. Не виконувати вміст документів. Дозволити додавання/поділ/перейменування сцен через сервіс. Перестановка приймає кожен ID цього твору рівно один раз; матеріали іншого твору недоступні за чужим ID.
- [ ] Повторити цільові тести та весь pytest; очікується PASS, зовнішні оригінали не змінено.
- [ ] Коміт: `feat: import author materials and editable scene structure`.

### Завдання 3. Перший локальний екран: бібліотека та матеріали твору

**Files:** створити `application/settings.py`, `web/app.py`, `web/routes_stories.py`, `web/templates/{base,library,story}.html`, `web/static/{app.css,api.js,editor.js}`, `tests/web/test_authoring.py`; додати web extras до `pyproject.toml` та оновити lock.

**Interfaces:** `AppSettings(data_dir: Path, env_file: Path, host='127.0.0.1', port=8765)`; `create_app(settings: AppSettings) -> FastAPI`. HTML: `GET /`, `GET /stories/{id}`. API: `POST /api/stories`, `GET /api/stories/{id}`, `POST /api/stories/{id}/sources` (multipart), `PATCH /api/scenes/{id}`, `PUT /api/stories/{id}/scene-order`. Сервіси — завдання 1–2, помилка revision відображається як HTTP 409.

- [ ] Написати `test_browser_flow_create_import_edit`: створення → upload двох файлів → отримання семи сцен → правка → повторне завантаження повертає збережений текст. `test_html_in_source_is_displayed_as_text`: `<script>` не виконується/не вставляється як HTML. `test_conflicting_save_returns_409`: попередня правка не губиться. `test_foreign_story_scene_is_rejected`: чужий scene ID не змінюється.
- [ ] Запустити `python -m pytest tests/web/test_authoring.py -q`; очікується FAIL.
- [ ] Реалізувати сторінки й routes через Jinja2 autoescape та JS `textContent`/textarea. Показувати незбережені зміни й конфлікт зі збереженою версією. Усі мутації — POST/PATCH/PUT з перевіркою локального Host і same-origin; CORS не вмикати. Сервер читає ключі тільки з явного env_file/environment, не відправляє їх у HTML/API.
- [ ] Повторити цільові тести та весь pytest; очікується PASS. Перевірити сторінку через браузер. **Віха A:** уже можна імпортувати й редагувати твір без жодного виклику моделі.
- [ ] Коміт: `feat: add local story library and authoring interface`.

### Завдання 4. Налаштування ролей, промпти та підготовка структури

**Files:** створити `providers/{models,client,discovery}.py`, `authoring/blueprints.py`, `generation/{models,prompts}.py`, `generation/resources/{prepare,brief,writer,editor,memory}_uk_v1.txt`, `web/routes_settings.py`, `web/templates/settings.html`, `tests/providers/test_settings.py`, `tests/authoring/test_blueprints.py`; за потреби змінити `evaluation/gateway.py` лише для спільного створення API-клієнта.

**Interfaces:** `build_openai_client(settings: ProviderSettings, http_client: httpx.Client | None = None) -> OpenAI`; `discover_models(settings: ProviderSettings) -> list[ModelOption]`; `save_role_settings(repo, story_id: str, role: str, settings: RoleSettings, expected_revision: int) -> Story`; `update_story_profile(repo, story_id: str, profile: StyleProfile, expected_revision: int) -> Story`; `parse_blueprint(raw: str) -> StoryBlueprint`; `apply_blueprint(repo, story_id: str, proposal: StoryBlueprint, expected_revision: int) -> Story`. API: `GET/PUT /api/stories/{id}/settings`, `POST /api/providers/discover`, `POST /api/stories/{id}/blueprint/apply`. Сам модельний виклик prepare додається в завданні 7.

- [ ] Написати `test_four_roles_can_use_different_providers`, `test_env_key_never_serialized`, `test_discovery_does_not_generate_or_load_by_request`: GET models не підміняється chat completion; невідома підтримка контексту не стає вигаданим значенням. `test_blueprint_is_proposal_until_apply`: результат моделі не змінює канон автоматично. `test_existing_evaluator_contract_unchanged`: наявні evaluator tests і serialized config продовжують працювати.
- [ ] Запустити `python -m pytest tests/providers/test_settings.py tests/authoring/test_blueprints.py -q`; очікується FAIL.
- [ ] Реалізувати окремі ProviderSettings для генерації (local/openrouter) і зберегти EvaluatorConfig для оцінювача (також codex_cli). Промпти — версійовані тексти; авторські правки створюють нові версії в сховищі. Prepare і brief використовують роль планувальника. Нормалізовані персонажі/канон мають source citations, неоднозначності лишаються warnings. Політика відповіді редактора зберігає події, підтекст і відвертість. API max_retries=0, локальний timeout 3600 s, хмарний 180 s із можливістю зміни; конфігурація не має вигаданого model ID.
- [ ] Повторити цільові тести та весь pytest; очікується PASS. GET models можна перевірити локально окремо; без реальних completions цей етап не доводить якість моделей.
- [ ] Коміт: `feat: configure generation roles prompts and blueprint proposals`.

### Завдання 5. Контекст сцени та формат пам’яті

**Files:** створити `generation/context.py`, `memory/{models,service}.py`, `tests/generation/test_context.py`, `tests/memory/test_snapshots.py`.

**Interfaces:** `build_context(repo: Repository, scene_id: str, stage: str, settings: RoleSettings) -> ContextBundle`; `memory_before(repo: Repository, scene_id: str) -> MemorySnapshot`; `validate_memory(snapshot: MemorySnapshot, source_versions: dict[str, str]) -> MemorySnapshot`. MemorySnapshot включає вихідні посилання на prose versions; для початку твору — порожній знімок.

- [ ] Написати `test_scene_two_sees_only_committed_past`: жоден факт із майбутньої сцени не потрапляє до здійснених подій; план майбутнього маркований окремо. `test_context_uses_selected_prose_and_latest_valid_memory`: відкинута редактура не використовується. `test_budget_overflow_is_explicit`: input не обрізано, повернуто typed ContextOverflow з обсягами. `test_memory_facts_require_existing_source_quotes`: невідома версія або вигадана цитата не стає поточною пам’яттю.
- [ ] Запустити `python -m pytest tests/generation/test_context.py tests/memory/test_snapshots.py -q`; очікується FAIL.
- [ ] Реалізувати збирання контексту зі snapshot точних версій, зарезервувати ліміт виходу. Наприкінці попередньої сцени використовувати заданий у profile обсяг і явно фіксувати вибраний фрагмент у manifest. Нестача контексту — помилка до виклику. Приблизні токенові оцінки позначати приблизними; окремий max_input_chars лишити операційним лімітом. Змістова правильність фактів лишається предметом оцінювання, не лише JSON-валідації.
- [ ] Повторити цільові тести та весь pytest; очікується PASS. ContextBundle містить достатні дані для відтворення входу й визначення актуальності.
- [ ] Коміт: `feat: assemble versioned scene context and validate story memory`.

### Завдання 6. Потокова генерація з локального API та OpenRouter

**Files:** створити `providers/streaming.py`, `tests/providers/test_streaming.py`; використовувати API-клієнт завдання 4.

**Interfaces:** `GenerationGateway.stream(context: ContextBundle, cancel: threading.Event) -> Iterator[GenerationEvent]`; `build_generation_gateway(settings: ProviderSettings) -> GenerationGateway`. Fake gateway для наступних тестів живе лише в `tests/`.

- [ ] Написати `test_deltas_and_terminal_are_preserved`: українські delta збираються без втрати символів, usage після тексту не губиться. `test_length_refusal_and_disconnect_keep_partial`: частковий текст зберігається, terminal stop не вигадується. `test_timeout_has_one_attempt`: рівно один мережевий запит. `test_cancel_during_stream_closes_reader`: після cancel не запускається наступний етап; тест першого токена використовує керований fake, не багатохвилинний sleep.
- [ ] Запустити `python -m pytest tests/providers/test_streaming.py -q`; очікується FAIL.
- [ ] Реалізувати `chat.completions.create(stream=True)` без tools. Для brief/memory response schema застосовується лише в явно обраному підтримуваному режимі; writer/editor повертають текст. include_usage надсилати тільки коли це ввімкнено в конфігурації endpoint. Порожній результат, length/refusal/помилка — незавершена спроба з доступним текстом/usage. Cancel перевіряється при отриманні частин та закритті клієнта; затримка до першої частини не маскується статусом «вже скасовано».
- [ ] Повторити цільові тести та весь pytest; очікується PASS. Локальний endpoint і OpenRouter відрізняються конфігурацією, а не прихованими fallback.
- [ ] Коміт: `feat: stream prose generation with explicit cancellation and usage`.

### Завдання 7. Чотири етапи однієї сцени

**Files:** створити `generation/{stages,pipeline}.py`, `tests/generation/test_stages.py`, `tests/generation/test_scene_pipeline.py`; доповнити операції Repository для StageAttempt.

**Interfaces:** `execute_stage(repo, scene_id: str | None, stage: str, context: ContextBundle, gateway: GenerationGateway, cancel: threading.Event, on_delta: Callable[[str], None]) -> StageAttempt`; `generate_scene(repo, scene_id: str, role_settings: dict[str, RoleSettings], gateway_factory: Callable[[ProviderSettings], GenerationGateway], cancel, on_event) -> list[StageAttempt]`; `prepare_story(repo, story_id: str, planner: RoleSettings, gateway, cancel) -> StoryBlueprint`; `Repository.commit_stage_result(attempt_id: str, result_ref: VersionRef, expected_revision: int) -> StageAttempt`. Останній метод атомарно фіксує завершення й current або alternative при revision-конфлікті. Stage: prepare/brief/draft/edit/memory/evaluate; generate_scene використовує brief/draft/edit/memory.

- [ ] Написати `test_scene_pipeline_uses_edited_text_for_memory`: чотири запити в правильному порядку, пам’ять читає edited, а не draft. `test_invalid_brief_or_memory_stops_pipeline`: raw result збережено, наступного виклику немає. `test_manual_edit_during_generation_keeps_alternative_result`: CAS-конфлікт не затирає ручну версію. `test_crash_after_completed_blob_does_not_advance_head_without_commit`: стан після відкриття сховища пояснює, що завершено, а що ні.
- [ ] Запустити `python -m pytest tests/generation/test_stages.py tests/generation/test_scene_pipeline.py -q`; очікується FAIL.
- [ ] Реалізувати етапи з фіксацією входів до API-виклику й незмінною версією результату після нього. Для brief запропоновані суттєві зміни не застосовувати: етап потребує рішення автора. Невалідний JSON не ремонтується додатковим прихованим викликом. Prepare створює лише StoryBlueprint; apply — окрема авторська дія. Edited автоматично стає current лише за незмінних вхідних revision; memory просувається тільки після перевірки джерел.
- [ ] Повторити цільові тести та весь pytest; очікується PASS. **Віха B:** повний цикл однієї сцени працює через сервіс; наступний інтерфейс використовує цей самий код.
- [ ] Коміт: `feat: generate brief prose edit and memory for one scene`.

### Завдання 8. Залежності, ручна пам’ять і повторна генерація

**Files:** створити `generation/dependencies.py`, `tests/generation/test_dependencies.py`, `tests/memory/test_rebuild.py`; доповнити `authoring/service.py`, `memory/service.py`, Repository.

**Interfaces:** `invalidate_dependents(repo, changed_version_ids: list[str]) -> list[str]`; `select_prose(repo, scene_id: str, version_id: str, expected_revision: int) -> Scene`; `save_manual_prose(repo, scene_id: str, text: str, expected_revision: int) -> VersionRef`; `rebuild_memory(repo, from_scene_id: str, gateway_factory, cancel, on_event) -> list[StageAttempt]`. Для ручної правки пам’яті — нова memory version із source refs, без підміни старого знімка.

- [ ] Написати `test_edit_scene_two_invalidates_downstream_not_other_story`: змінені залежні brief/prose/memory/evaluation позначаються застарілими, текст сцен 3+ не переписується. `test_reselecting_older_prose_changes_memory_source`: відновлена проза має свій hash/source. `test_rebuild_memory_uses_current_texts_in_order`: відновлення від сцени 2 використовує актуальну сцену 1 та поточні тексти далі. `test_new_canon_and_scene_order_invalidate_relevant_manifests`.
- [ ] Запустити `python -m pytest tests/generation/test_dependencies.py tests/memory/test_rebuild.py -q`; очікується FAIL.
- [ ] Реалізувати транзитивний обхід dependency_edges, окремі ознаки stale та needs_review. Зміна канону/стилю/порядку враховується в context fingerprints. Rebuild є явним запуском із потенційними модельними викликами; без нього знімки лише втрачають актуальність. Ручна проза зберігається завжди, але автоматичний прохід чекає оновлення потрібної пам’яті. Вихідний текст версії або старий звіт не видаляються.
- [ ] Повторити цільові тести та весь pytest; очікується PASS. На зміні сцени 2 автор бачить, які наступні матеріали потребують перевірки.
- [ ] Коміт: `feat: track downstream staleness and rebuild memory from selected prose`.

### Завдання 9. Послідовний виконавець, паузи й відновлення

**Files:** створити `generation/{worker,events}.py`, `tests/generation/test_worker.py`, `tests/integration/test_recovery.py`; доповнити `web/app.py` lifespan та Repository для runs/events.

**Interfaces:** `RunCoordinator(repo: Repository, gateway_factory)`; `enqueue(request: RunRequest, request_id: str) -> Run`; `pause(run_id: str) -> Run`; `cancel(run_id: str) -> Run`; `resume(run_id: str, repeat_interrupted: bool = False) -> Run`; `recover_interrupted() -> list[Run]`; `list_events(run_id: str, after_seq: int) -> list[RunEvent]`. AppInstanceLock утримує OS-lock файла в data_dir до завершення процесу й не допускає другого worker над тією самою базою.

- [ ] Написати `test_global_queue_has_one_active_model_request` для двох творів і двох HTTP-клієнтів. `test_repeated_request_id_returns_same_run`: подвійний клік не дублює виклик; той самий request_id з іншим body дає конфлікт. `test_pause_after_brief_stops_before_writer`. `test_reopen_marks_running_interrupted_without_retry`: жодного API-виклику при startup. `test_resume_reuses_completed_steps_only_if_inputs_match`. `test_second_server_cannot_recover_first_servers_live_run`: OS-lock перевіряється до recovery.
- [ ] Запустити `python -m pytest tests/generation/test_worker.py tests/integration/test_recovery.py -q`; очікується FAIL.
- [ ] Реалізувати чергу поверх DB, один worker-потік і явні переходи станів. Queue/request_id зберігаються; DB-транзакція резервує спробу до виклику. На startup активні невизначені спроби стають interrupted; queued не стартують без явного відновлення сесії автором. Кожен новий етап повторно перевіряє актуальність вхідних refs. Cancel не запускає новий виклик, доки поточний клієнт не вийшов. Збережені RunEvent.seq дозволяють відновлення підписки без повторного запуску роботи.
- [ ] Повторити цільові тести та весь pytest; очікується PASS. Тести аварій використовують тимчасову DB/процес, не видаляють користувацький data_dir і не чекають реальної моделі.
- [ ] Коміт: `feat: orchestrate persistent sequential runs with pause cancel and recovery`.

### Завдання 10. Робоче місце автора: запуск і перегляд версій

**Files:** створити `web/{routes_runs,routes_versions}.py`, `web/static/{runs,versions}.js`, `tests/web/test_runs.py`, `tests/web/test_versions.py`; доповнити story template й editor.js.

**Interfaces:** `POST /api/stories/{id}/prepare`; `POST /api/runs` з RunRequest і request_id; `GET /api/runs/{id}`; `GET /api/runs/{id}/events`; `POST /api/runs/{id}/{pause,cancel,resume}`; `GET /api/scenes/{id}/versions`; `GET /api/versions/{id}`; `GET /api/versions/compare?left=ID&right=ID`; `POST /api/scenes/{id}/prose`; `POST /api/scenes/{id}/select-version`; `POST /api/scenes/{id}/rebuild-memory`. Сервіс Coordinator — завдання 9; текстові зміни — завдання 8. Порівняння показує обидва тексти й відмінності без виконання HTML із вмісту.

- [ ] Написати `test_run_returns_id_without_waiting_for_model`, `test_sse_reconnect_replays_after_last_event_id`, `test_disconnect_does_not_cancel_run`, `test_partial_is_not_selectable_as_current`. `test_edit_conflict_keeps_unsaved_browser_text`: HTTP 409 не очищає редактор. `test_run_status_does_not_expose_keys` і `test_model_text_is_not_executed_as_html`.
- [ ] Запустити `python -m pytest tests/web/test_runs.py tests/web/test_versions.py -q`; очікується FAIL.
- [ ] Реалізувати кнопки «Завдання», «Написати», «Редагувати», «Оновити пам’ять», «Пройти решту», «Пауза», «Скасувати», «Продовжити»; налаштування пауз після етапів. Показати живий текст, elapsed time, модель/роль, збережені версії, stale/needs_review та точну причину зупинки; доступні usage/cost відображати як reported, відсутні — як невідомі, не нулі. Перед запуском показати ролі з хмарними провайдерами та очікувану кількість викликів без прихованих оцінок ціни. Живий результат відділений від незбережених ручних правок. SSE — JSON data, monotonic IDs, keepalive та закриття підписки після terminal. Для перерваного виклику дія повтору явно відрізняється від продовження після завершеного етапу.
- [ ] Повторити цільові тести та весь pytest; очікується PASS. **Віха C:** із браузера можна пройти твір автоматично, зупинитися й продовжити, зберігши версії та пам’ять.
- [ ] Коміт: `feat: add live generation controls and scene version workbench`.

### Завдання 11. Підключення оцінювача до твору й редактур

**Files:** створити `application/evaluation_bridge.py`, `tests/integration/test_story_evaluation.py`, `tests/web/test_evaluation.py`; доповнити worker та story template; `evaluation/` змінювати тільки для підтверджених потреб інтеграції.

**Interfaces:** `build_evaluation_case(repo, story_id: str, scene_id: str | None, mode: str) -> EvaluationCase`; `queue_evaluation(coordinator, story_id: str, scene_id: str | None, mode: str, request_id: str) -> Run`; `plan_evaluation_windows(repo, story_id: str, config: EvaluatorConfig) -> list[EvaluationCase]`. API: `POST /api/stories/{id}/evaluate`, `GET /api/stories/{id}/evaluations`.

- [ ] Написати `test_revision_evaluation_uses_exact_draft_and_edit_refs`, `test_prose_change_marks_report_stale`, `test_partial_story_coverage_never_looks_like_full_pass`, `test_evaluation_shares_generation_queue`. `test_candidate_profile_is_not_presented_as_quality_pass`: попередній verdict не стає зеленим статусом «пройдено».
- [ ] Запустити `python -m pytest tests/integration/test_story_evaluation.py tests/web/test_evaluation.py -q`; очікується FAIL.
- [ ] Реалізувати міст до існуючого `evaluate()`, зберігати артефакт і dependency refs. Показувати критерії, підтверджені/непідтверджені цитати, помилки та порівняння draft/edit. Опції оцінювання: off, report, pause_on_failure; остання потребує каліброваного профілю. Звичайний автоматичний прохід не блокується candidate-звітом, а тестовий quality gate не зараховує його як успіх. Для всього твору використовувати повні тексти, якщо дозволяє перевірений контекст; інакше явно визначені вікна та перелік неперевірених далеких зв’язків, без статусу «весь твір перевірено».
- [ ] Повторити цільові тести та весь pytest; очікується PASS; старі команди evaluator CLI працюють без сервера.
- [ ] Коміт: `feat: evaluate selected story versions and surface editorial regressions`.

### Завдання 12. Експорт і простий запуск на Windows

**Files:** створити `application/exports.py`, `server.py`, `scripts/start.ps1`, `docs/prototype-runbook.md`, `tests/authoring/test_exports.py`, `tests/web/test_startup.py`; додати entry point `storygen` та пакування templates/static у `pyproject.toml`.

**Interfaces:** `export_story(repo, story_id: str, format: Literal['md','txt'], allow_incomplete: bool = False) -> Path`; `server.main(argv: list[str] | None = None) -> int`. API: `POST /api/stories/{id}/export`; повертає посилання для завантаження лише створеного всередині data_dir файла. CLI: `storygen --data-dir PATH --port 8765 --open-browser`.

- [ ] Написати `test_export_contains_selected_versions_in_scene_order`, `test_export_blocks_partial_stale_or_missing_scene_by_default`, `test_export_path_ignores_story_title_as_path`, `test_installed_package_finds_templates_outside_repo`, `test_server_binds_loopback_and_rejects_second_instance`. Для allow_incomplete незавершені частини явно позначені в тексті й manifest, не замінені порожніми рядками.
- [ ] Запустити `python -m pytest tests/authoring/test_exports.py tests/web/test_startup.py -q`; очікується FAIL.
- [ ] Реалізувати Markdown/TXT із зафіксованим snapshot current versions та manifest з порядком/ID/hash/попередженнями. Запис експорту атомарний. Скрипт start використовує `.venv/Scripts/python.exe`, не змінює системний Python, execution policy чи глобальні пакети; якщо середовища немає, показує інструкцію встановлення. Відкрити браузер після готовності сервера, не виводити в консоль ключі або тексти промптів. У runbook описати запуск, зупинку, місце data_dir, відновлення та копіювання даних після коректної зупинки сервера.
- [ ] Повторити цільові тести та весь pytest; очікується PASS. **Віха D:** весь шлях від імпорту до файла доступний через локальний інтерфейс.
- [ ] Коміт: `feat: export story snapshots and launch the local Windows app`.

### Завдання 13. Калібрування оцінювача та автоматичні якісні перевірки

**Files:** змінити `evaluation/calibration.py`, `tests/evaluation/test_calibration.py`, `docs/evaluation.md`; додати профіль до `config/` тільки після реального успішного калібрування; доповнити тестові pipeline-прогони.

**Interfaces:** наявні `calibrate`, `evaluate`, fingerprints зберігаються; показник score_ranges стає `int | None` для критерію, якщо доступних спостережень менше двох. Профіль оцінювача прив’язаний до точного model ID, промпту, рубрики та параметрів.

- [ ] Написати `test_single_observation_does_not_claim_zero_variability`: один доступний повтор дає null; два бали 4/2 дають 2. `test_scene_pipeline_fixture_detects_seeded_fact_change`: інтеграція не губить критичну помилку редактури. `test_incomplete_calibration_cannot_enable_pause_on_failure`.
- [ ] Запустити відповідні evaluation/integration тести; очікується FAIL для нових гарантій. Зафіксувати команду й результати в журналі виконання.
- [ ] Реалізувати виправлення показника та quality gate. Обрати доступного оцінювача з явним ID і контекстом, достатнім для підсумкового сценарію; для проб промпту використовувати Codex CLI. Виконати dry-run контрольного набору, далі реальне калібрування десяти прикладів із трьома повторами в межах вибраного бюджету. Всі результати лишаються в artifacts; за недостатньої якості змінювати модель/промпт із новою версією, не «лікувати» звіт ручним calibrated=true.
- [ ] Повторити технічні тести та весь pytest; очікується PASS. Калібрований профіль створюється лише за виконання вже визначених порогів: без пропусків критичних дефектів, recall>=80%, false-positive rate<=20%, availability>=90%, повний набір, три повтори й стабільний verdict. Функціональна реалізація наступних завдань не вимагає приховувати невдале калібрування; підсумковий quality gate в такому разі лишається невиконаним.
- [ ] Коміт: `test: calibrate evaluator and enforce prototype quality reporting` (якщо реальний прогін ще неможливий — назва/документація мають явно відображати pending, а не claimed calibration).

### Завдання 14. Наскрізні технічні сценарії прототипу

**Files:** створити `tests/integration/test_prototype_flow.py`, `tests/web/test_browser_flow.py`, browser fixtures; оновити `docs/prototype-acceptance.md` і dev-залежності для Playwright.

**Interfaces:** використовуються публічні API, Repository та RunCoordinator попередніх завдань. Для pytest app створюється з fake gateway через dependency injection; той самий fake підтримує успіх, затримку, розрив, відмову й невалідну пам’ять. Ні сервер, ні Playwright не повинні викликати справжню модель у цьому наборі.

- [ ] Написати три сценарії: `test_seven_scene_flow_to_export`; `test_restart_after_scene_three_resumes_without_duplicate_calls`; `test_browser_edit_during_generation_and_sse_reconnect_preserves_both_texts`. Додатково `test_cancel_before_first_delta_has_honest_status` і `test_model_refusal_does_not_trigger_provider_fallback`. Перевірки: сім завершених сцен у правильному порядку, джерела пам’яті відповідають selected prose, точний лічильник очікуваних викликів, відсутні загублені правки/дублікати.
- [ ] Запустити нові сценарії до їх підтримки; зафіксувати конкретні FAIL. Якщо гарантія вже реалізована й тест одразу проходить, записати це як інтеграційне підтвердження, не вигадувати RED і не змінювати робочий код лише для процесу.
- [ ] Усунути виявлені функціональні прогалини мінімальними змінами з відтворенням дефекту. Перевірити читабельність бібліотеки, редактора, статусів і порівняння версій у справжньому браузері; UI-скриншоти зберегти до artifacts. Всі живі тексти/keys залишаються відсутніми в логах технічних тестів.
- [ ] Запустити весь pytest, браузерні сценарії та `git diff --check`; очікується PASS. Встановлений пакет має працювати не лише з cwd репозиторію. Після незалежного огляду гілки виправити суттєві проблеми з regression RED→GREEN; зафіксувати дрібні відкладені зауваження.
- [ ] Коміт: `test: verify complete prototype flow recovery and browser controls`.

### Завдання 15. Реальний твір і приймання прототипу

**Files:** заповнити `docs/prototype-acceptance.md`, доповнити runbook і README. Приватні вхідні матеріали, результати та звіти лишаються в data/artifacts, не комітяться автоматично.

**Interfaces:** автор використовує локальний інтерфейс, затверджену структуру та реальні конфігурації моделей. Model ID, контекст, параметри й фактичні outputs фіксуються у manifest реального прогону.

- [ ] Перевірити локальний endpoint через models discovery, вибрати ролі й зробити одну сцену на 300–600 слів для перевірки першого токена, стабільності потоку, української та часу. Для OpenRouter спочатку вибрати модель й перевірити актуальні ціни/умови, після чого виконати погоджений короткий тест; відсутній ключ позначає цю частину як неперевірену, а не успішну.
- [ ] Імпортувати «Двері…», переглянути сім сцен, уточнити суперечності персонажів, вибрати орієнтир 7000 слів із розподілом між сценами. Зафіксувати профіль письма та активні промпти до старту.
- [ ] Провести всі сцени через brief→draft→edit→memory, зробити паузу та продовження, перевірити правку однієї ранньої сцени й позначення залежностей. Порівнюваний quality run проводити на одному послідовному наборі поточних версій, а не суміші чернеток із різних експериментів.
- [ ] Запустити автоматичне оцінювання сцен, draft/edit і всього твору з явним coverage та каліброваним профілем; усунути підтверджені критичні проблеми окремими контрольованими ітераціями. Немає безмежного автопереписування. Невдалий quality gate фіксується як невдалий, навіть якщо UI і генерація працюють.
- [ ] Після автоматичних перевірок виконати ручну літературну оцінку, експортувати актуальний твір у MD/TXT, зафіксувати фактичний обсяг 5000–15000 слів і результат за чеклістом нижче. Якщо модель не виконала обсяг, показати відхилення та явно перегенерувати вибрані сцени; автоматичного обрізання/дописування без записаного запуску немає.
- [ ] Оновити README реальним станом, обмеженнями й інструкцією. Коміт: `docs: record first working prototype acceptance` лише після відділення фактично пройдених пунктів від неперевірених. Модельні артефакти не додаються через `git add .`.

## 6. Критерії готовності першого прототипу

### Функціональне приймання

- [ ] Один локальний запуск відкриває український інтерфейс; стан переживає перезапуск сервера.
- [ ] План і персонажі імпортуються без зміни оригіналів; автор переглядає й редагує сім сцен.
- [ ] Усі чотири ролі налаштовуються незалежно; реально перевірено щонайменше один повний шлях через обрані моделі. Підтримка другого API-провайдера окремо відмічена як інтеграційно перевірена або неперевірена.
- [ ] Одна сцена та решта твору проходять усі чотири етапи; пам’ять має джерела з current edited/manual версій.
- [ ] Автор бачить текст під час генерації, може переглянути завдання, порівняти редактуру, зберегти правку й вибрати версію.
- [ ] Пауза, скасування, перепідключення вкладки та відновлення не гублять завершені матеріали й не роблять прихованих повторних запитів.
- [ ] Зміна ранньої сцени або канону показує залежні застарілі матеріали; наступні сцени самі не переписуються.
- [ ] Актуальні версії експортуються в один MD/TXT у правильному порядку; прогалини й часткові тексти не маскуються.
- [ ] Ключі не потрапляють у браузер/експорт; приватні матеріали й результати лишаються поза Git.

### Перевірка якості та фактичного результату

- [ ] Технічні та браузерні сценарії пройдено; незалежний огляд не лишив невиправлених суттєвих проблем.
- [ ] Є повний звіт калібрування оцінювача на явній моделі та незмінному профілі. Пілот або candidate не зараховується як успіх цього пункту.
- [ ] Реальний твір містить сім поточних сцен і фактичні 5000–15000 слів; усі сцени мають manifest джерел і параметрів.
- [ ] Оцінено мову, редактуру та сюжет із чесним покриттям; відсутні підтверджені критичні проблеми або вони явно лишають приймання якості невиконаним.
- [ ] Лише після автоматичних перевірок автор прочитав фінальну поточну версію й зафіксував ручний висновок.

У звіті окремо зазначаються «функціональний прототип працює» і «літературний результат прийнято». Жоден із цих статусів не підміняє інший. Невдала конкретна модель не означає автоматично дефект усієї архітектури, але й не дозволяє назвати її текст прийнятим.

## 7. Залежності, ризики й рішення перед живими тестами

| Питання | Коли потрібне рішення | Що можна робити до нього |
|---|---|---|
| Явний ID та параметри оцінювача | Калібрування, завдання 13 | Сховище, інтерфейс, fake-прогони; проби промпту через Codex CLI |
| Реальні local model IDs, доступний контекст і швидкість | Початок коротких реальних генерацій | Налаштування й реалізація протоколу; GET models discovery |
| OpenRouter key, моделі, поточні ціни та бюджет | Перед платними completions | HTTP MockTransport, локальні моделі, інтерфейс вибору ролей |
| Освіта Лєри та інші суперечності матеріалів | Застосування канону до реального твору | Імпорт із warnings, редагування пропозицій |
| Допустимі час/якість на ноутбуці з 8 GB VRAM | Пілот однієї сцени | Обмеження черги одним запитом, збереження стану, можливість заміни ролі |

Головні ризики — слабка українська в конкретних моделях, повільне локальне виконання, накопичення помилок у пам’яті та неповне покриття оцінювачем. Їх перевіряють окремі пілоти та manifests. Довгий реальний прогін починається після короткого, а не за припущенням, що завантажена модель уже відповідає вимогам.

Зміна промптів/моделей із метою покращення тексту оформлюється новим versioned експериментом. Для порівняння зберігається однаковий вхід і контекст; не робимо висновок про покращення з різних сцен або різного канону.

## 8. Що свідомо лишається після прототипу

Хостинг і віддалений Git; багатокористувацька робота; мобільний застосунок; багатий редактор; DOCX/PDF; навчання моделей; векторна пам’ять; автоматичний добір моделей; великі романи з багатьма лініями; наскрізне автоматичне переписування всього твору; автономні цикли виправлень без ліміту.

Перший прототип працює локально і не потребує Cloudflare-сервісів чи зміни тарифу Free. Повернення до хостингу є окремою задачею після перевірки прототипу.

## 9. Джерела технічних рішень

Переглянуто 19 жовтня 2026 року; конкретні версії пакетів перевіряються при встановленні.

- [FastAPI: templates](https://fastapi.tiangolo.com/advanced/templates/) — серверні Jinja2-шаблони та статичні ресурси.
- [FastAPI: lifespan](https://fastapi.tiangolo.com/advanced/events/) — запуск і завершення керованих ресурсів застосунку.
- [MDN: Server-sent events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events) — EventSource, event IDs, перепідключення та UTF-8 події. Вебпідписка відділена від самого модельного запиту нашим coordinator.
- [SQLite: WAL](https://www.sqlite.org/wal.html) — режим журналювання локальної бази; транзакційна узгодженість файлових версій додатково забезпечується Repository.
- Правила API та Codex CLI спираються також на джерела, збережені в [плані оцінювача](2026-10-19-automatic-evaluator.md) й [інструкції оцінювання](../../evaluation.md).

## 10. Самоперевірка плану та передача до виконання

| Частина специфікації | Покриття |
|---|---|
| Мета, мова, обсяг, контрольоване розширення | StyleProfile, завдання 2, 4, 7, 15 |
| Імпорт, жанр/стиль, персонажі, редагування | 2–4, 10 |
| Чотири ролі та промпти | 4, 6–7 |
| Пам’ять, джерела, майбутній план окремо від фактів | 5, 7–8 |
| Версії, залежності, повторна генерація | 1, 7–10 |
| Локальний вебінтерфейс і живий прогрес | 3, 9–10, 12 |
| Відновлення, помилки, тривалі запити, секрети | 1, 3–6, 9–10, 14 |
| Оцінювання, регресії та калібрування | уже реалізований модуль + 11, 13–15 |
| Експорт, простий запуск, реальний тестовий твір | 12, 14–15 |

Перевірено: всі п’ять Review Focus мають цільові сценарії; контракти вводяться до споживачів; існуючий evaluator CLI не переписується під вебсервер; реальна перевірка відокремлена від імітацій API; незавершене калібрування лишається видимою роботою; функціональний прототип не плутається з прийнятою літературною якістю.

Перед виконанням користувач переглядає цей план, насамперед стек, віхи й критерії приймання. Після погодження зберігається раніше обраний режим: реалізація послідовно мною в поточному чаті, з одним незалежним оглядом гілки перед завершенням. Повторно обирати спосіб виконання або підтверджувати кожне завдання не потрібно.
