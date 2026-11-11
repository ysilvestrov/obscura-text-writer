# Встановлення й запуск

## Вимоги

- Windows 10 або 11.
- [Python](https://www.python.org/downloads/) 3.10 або новіший.
- Модельний API: локальний OpenAI-сумісний сервер (наприклад, LM Studio) або обліковий запис OpenRouter чи Venice.

## Інсталятор

Інсталятор для Windows з’явиться згодом (#30). До того застосунок встановлюється з вихідного коду за кроками нижче.

## Встановлення з вихідного коду

Завантажте репозиторій [obscura-text-writer](https://github.com/ysilvestrov/obscura-text-writer) і відкрийте PowerShell у його теці:

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements-lock.txt
./.venv/Scripts/python.exe -m pip install --no-deps -e ".[web,publication]"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Остання команда створює `.env` лише тоді, коли цього файла ще немає, тож повторний запуск не стирає ваших ключів.

## Ключі провайдерів

Відкрийте `.env` у текстовому редакторі й заповніть ключ лише того провайдера, яким користуватиметеся:

- `OPENROUTER_API_KEY` — для OpenRouter;
- `VENICE_API_KEY` — для Venice (лише моделі з `uncensored=true`).

Локальному провайдеру ключ не потрібен. Ключі лишаються на вашому комп’ютері; не публікуйте файл `.env`.

## Запуск

Особисті твори краще тримати в окремому каталозі поза текою застосунку:

```powershell
./scripts/start.ps1 -DataDir "$env:LOCALAPPDATA/ObscuraTextWriter/data"
```

Браузер відкриє `http://127.0.0.1:8765`. Сервер слухає лише ваш комп’ютер. Інший порт задає параметр `-Port`, наприклад `-Port 8770`. Зупинка — `Ctrl+C` у вікні PowerShell.

Якщо запуск PowerShell-скриптів заборонено, використайте пряму команду:

```powershell
./.venv/Scripts/python.exe -m storygen.server --data-dir "$env:LOCALAPPDATA/ObscuraTextWriter/data" --env-file .env --open-browser
```

## Моделі

Після першого запуску відкрийте **Налаштування → Моделі** і для кожної ролі вкажіть провайдера, адресу API, точний ідентифікатор моделі та ліміти. Для локального сервера типова адреса — `http://localhost:1235/v1`. Кнопка отримання списку моделей показує доступні ідентифікатори й відомі ціни.

## Резервне копіювання

Перед копіюванням зупиніть сервер. Штатна резервна копія перевіряє цілісність і хеші:

```powershell
./.venv/Scripts/storygen.exe backup --data-dir "$env:LOCALAPPDATA/ObscuraTextWriter/data" --destination "D:/Backups/obscura-2026-11-11" --json
./.venv/Scripts/storygen.exe restore --backup-dir "D:/Backups/obscura-2026-11-11" --destination "D:/Restored/obscura" --json
```

Батьківські каталоги призначення мають існувати. Відновлення створює лише новий каталог і нічого не перезаписує. Можна також скопіювати **весь** каталог даних зупиненого сервера; не копіюйте базу окремо від текстів.

## Оновлення

Збережіть ручні правки, зупиніть сервер, оновіть код і запустіть сервер знову. Схема даних оновлюється під час відкриття сховища. Після збою незавершені запуски позначаються як перервані й продовжуються лише за вашою командою.
