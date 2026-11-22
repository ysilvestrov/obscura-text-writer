# Прибрані моделі провайдера — частина 1 (#260): план

> Виконання: native (executing-plans). Спека: [2026-11-22-model-retirement-design.md](../specs/2026-11/2026-11-22-model-retirement-design.md).

**Мета:** Obscura заздалегідь попереджає про модель, яку провайдер прибирає, і дає зрозумілу помилку після видалення.

## Глобальні обмеження

- Модель ніколи не змінюється сама; `retirement` не блокує збереження чи запуск.
- Невідома чи некоректна дата → `retirement = None`.
- Тести не ходять у мережу й не торкаються сховища ключів ОС.

## Фокус рев'ю

1. Редактура (`edit_loop` і етап редактора в `scene`/`remaining`) зберігає попередження про прибрану модель і попередження попередніх етапів.
2. Дата в минулому (модель ще є в каталозі) — те саме попередження, без блокування.
3. Каталог OpenRouter без `expiration_date` чи з `null` — без попередження.
4. Збій каталогу під час збереження ролі — збереження проходить без попередження.
5. Ручний ID поза каталогом у picker — без бейджа, як і раніше.

## T1. Поле каталогу й помилка «немає в каталозі»

- `providers/models.py`: `ModelRetirement(date: date, replacement: str | None)`, `ModelOption.retirement`.
- `providers/retirement.py`: `retirement_from(provider, row) -> ModelRetirement | None`; `retirement_warning(model, retirement) -> str`.
- `providers/catalog.py::model_option` заповнює поле; `providers/venice.py::validate_model` — окремий текст для відсутньої моделі.
- Тести: `tests/providers/test_model_retirement.py` (Venice `removesAt`/`date`, OpenRouter `expiration_date`, некоректна дата, відсутнє поле, текст помилки).

## T2. Попередження запуску в усіх шляхах

- `providers/streaming.py`: шлюз запам'ятовує `retirement` після перевірки каталогу (Venice — spec, OpenRouter — рядок каталогу).
- `generation/stages.py::execute_stage`: `attempt.context['model_retirement_warnings']`.
- `generation/retirement_warnings.py::carry(worker, run_id, attempt)`; виклики: `worker` (обидва шляхи), `editor_loop` (кожен прохід; `finish` зберігає інші попередження), `impact_runner`, `impact_chunk_runner`, `review/runner`.
- Тести: шлюз із фейковим каталогом; `execute_stage`; `edit_loop` і `scene` з редактором — попередження в `run.warning` після завершення.

## T3. Збереження ролі, picker, MCP

- `providers/schema_support`: перевірка повертає й попередження про прибрану модель; `PUT …/settings` і `…/settings/shared-provider` додають `model_warnings` до відповіді, лише коли вони є.
- `static/model-picker.js`: бейдж `retiring`, рядок вибраної моделі; `settings.js` показує `model_warnings`.
- `mcp/bridge.py`: `retirement` у полях `models`.
- Тести: API збереження з фейковим каталогом; node-тест picker; MCP-тест полів.

## T4. Документація й рецепти

- SPEC.MD: нова вимога MODEL-RETIREMENT (S01–S04), MODEL-003 (текст помилки), MCP-BRIDGE (поле), traceability.
- Сайт `models.md` uk/en, `check_site.py --rehash models`.
- `setup-models/references/recipes.md` (Cheap Venice: планувальник і пам'ять → `glm-5-3-flash-uncensored`; редактори — після тесту), `SKILL.md` (попередження про `retirement`), приклад конфігурації оцінювача.
