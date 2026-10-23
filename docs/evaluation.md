# Автоматичне оцінювання

Модуль запускається без вебінтерфейсу. Потрібні Python 3.10+ та встановлені залежності. Перевірте доступність Python перед створенням віртуального середовища.

## Встановлення

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e '.[dev]'
./.venv/Scripts/python.exe -m pytest -q
```

Для відтворення перевіреного середовища замість довільних нових версій використовуйте `pip install -r requirements-lock.txt`, потім `pip install --no-deps --no-build-isolation -e .` за наявності setuptools.

## Провайдери

- `config/evaluator.example.json`: локальний API. Замініть model на фактичний API ID; адреса за скриншотом — `http://localhost:1235/v1`.
- OpenRouter: provider=openrouter, base_url=https://openrouter.ai/api/v1, точний model і `OPENROUTER_API_KEY` у environment або локальному `.env`. Ключ не передається в JSON-конфігурації.
- `config/evaluator.codex.json`: випробування промпту через `codex exec`, stdin, `--output-schema` та `--output-last-message`. CLI працює з наявною авторизацією; вартість у грошах не вигадується, використання акаунта не вважається безлімітним. Авторський текст може бути переданий сервісу Codex. Явний model можна додати до config; без нього результат годиться для проби, але не для прив’язаного калібрування.

Codex запускається без shell-інтерполяції, у тимчасовому каталозі, з read-only sandbox та `--ignore-user-config`: користувацькі MCP/плагіни й глобальні налаштування не потрібні оцінювачу. Сам промпт забороняє інструменти й вимагає лише оцінку. Ліміти вихідних токенів та temperature є параметрами API-адаптера; Codex CLI не має ідентичних прапорців, тому для нього вони не гарантуються. Результати різних провайдерів не змішуються в каліброваному профілі.

## Команди

```powershell
./.venv/Scripts/python.exe -m storygen.evaluation.cli evaluate --case tests/fixtures/evaluation/clean/case.json --config config/evaluator.codex.json --dry-run
./.venv/Scripts/python.exe -m storygen.evaluation.cli evaluate --case tests/fixtures/evaluation/clean/case.json --config config/evaluator.codex.json
./.venv/Scripts/python.exe -m storygen.evaluation.cli compare --baseline artifacts/evaluation/BASE/outcome.json --candidate artifacts/evaluation/NEW/outcome.json
```

Входи — JSON-маніфести з documents, target_ids, mode, coverage. Документ містить text або відносний path у каталозі прикладу. Тексти читаються як UTF-8; BOM дозволено. Path поза каталогом прикладу заборонений.

Кожний запуск створює каталог із inputs.json, request.json, raw_response.txt, report.md та outcome.json. Останній файл є маркером завершеного запису. Точні вхідні тексти й сирі відповіді можуть бути приватними: artifacts виключено з Git.

Exit codes: 0 — пройдено; 1 — не пройдено; 2 — неповно або профіль ще не відкалібровано; 3 — помилка. Для compare: 0 — без погіршень, 1 — погіршення, 2 — звіти не можна порівняти, 3 — помилка. Початковий candidate-профіль завжди дає incomplete, навіть коли preliminary_verdict=passed.

Скасований, частковий чи невдалий виклик автоматично не повторюється. Ліміт символів — консервативний операційний запобіжник; він не обчислює токени й не гарантує відповідності контекстному вікну. Для великого твору потрібні явно сформовані групи сцен; неохоплені зв’язки позначають оцінку як неповну.

Збіг цитат доводить наявність фрагментів у джерелі, але не правильність інтерпретації оцінювача. Автоматичні бали залишаються інструментом розробки; ручна літературна перевірка відбувається для вже відтестованої версії.

Текстові limitations зберігаються як пояснення меж аналізу. Неповнота визначається структурованими статусами обов’язкових критеріїв, перевіркою цитат і покриттям; сама примітка «оцінено одну сцену» не робить перевірку цієї сцени неуспішною.

## Калібрування

```powershell
./.venv/Scripts/python.exe -m storygen.evaluation.cli calibrate --suite tests/fixtures/evaluation/suite.json --config config/evaluator.codex.json --dry-run
./.venv/Scripts/python.exe -m storygen.evaluation.cli calibrate --suite tests/fixtures/evaluation/suite.json --config config/evaluator.codex.json --output artifacts/calibration --repeats 3
```

У наборі десять прикладів; стандартний запуск робить 30 окремих викликів. Для короткої проби доступні `--case-id language --repeats 1`; така проба не є завершеним калібруванням. Expected findings зчитуються окремо після оцінювання і не входять у промпт. Для кожного повтору редактури чергується порядок представлення текстів.

Звіт містить precision, recall, пропуски критичних дефектів, хибні major/critical на контрольних текстах, доступність повних відповідей, розмах балів і зміни verdict між повторами. Немає знаменника — значення null. Відсутні повтори й помилки не дають нульову варіативність.

Для калібрування перевіряються збережені тексти, актуальний промпт, конфігурація моделі й профіль. Той самий run_id не зараховується кілька разів. Запуск лише вибраних case-id лишається пілотом і не може підтвердити придатність оцінювача для повного набору. У контрольній розмітці allowed_findings описує додаткові коректні прояви вже внесеного дефекту: вони не збільшують ні кількість обов’язкових виявлень, ні false positives.

Початкові умови придатності: три повтори, жодного пропуску критичного дефекту чи неперевіреного критичного прикладу, recall >=80%, false-positive rate <=20%, availability >=90%, без зміни verdict у повторах. Мала контрольна вибірка не доводить загальної якості. Профіль не стає calibrated автоматично: після перегляду звіту створюється новий версійований профіль із calibration_fingerprint та evaluator_fingerprint. Для нього потрібен явний model; зміна промпту, моделі, параметрів чи рубрики потребує нового калібрування.
