# Стан перевірки проєкту

**ПЕРЕВІРКА ПРОЙШЛА** — свідчення конкретного запуску, не поточного довільного стану.

- Початок (UTC): 2026-11-07T00:13:37.762811+00:00
- Завершення (UTC): 2026-11-07T00:13:40.709321+00:00
- Базовий commit: `559724687ac880b94d58f1c7fd9a1a8b03fc199a`
- Незакомічені зміни під час перевірки: `true`
- SHA-256 вихідного знімка: `d4e2245ce7dda92f32545e8d61a19b951e37495d9c7d230e449af4491e84f648`
- Зміна знімка під час прогону: `false`
- Exit code: `0`
- Фактичні testcase результати JUnit: passed: 6 · failed: 0 · errors: 0 · skipped: 0
- Тривалість: 2.94 с

Точний argv (JSON, не shell-команда):

```json
["C:\\Users\\yuriy\\.codex\\worktrees\\workspace-telemetry\\text-generator\\.venv\\Scripts\\python.exe", "-m", "pytest", "tests/web/test_runs.py::test_readiness_filters_operations_without_changing_existing_contract", "tests/web/test_runs.py::test_readiness_and_queue_share_prerequisite_reasons", "tests/web/test_editor_loop_ui.py", "tests/web/test_resumed_events.py", "-q", "--junitxml=C:\\Users\\yuriy\\.codex\\worktrees\\workspace-telemetry\\text-generator\\artifacts\\verification-vkf_8qzh\\junit.xml", "--basetemp=C:\\Users\\yuriy\\.codex\\worktrees\\workspace-telemetry\\text-generator\\artifacts\\verification-vkf_8qzh\\test-tmp"]
```

Результат стосується лише наведеної команди й вихідного знімка. Якщо в argv зазначено окремі файли або фільтри, це часткова перевірка. Збір (collection) не є виконанням; skipped не зараховано до passed. Відсутній або непридатний XML позначається непідтвердженим. Після зміни вихідних файлів звіт історичний. Власний STATUS і artifacts виключено зі знімка; початкова ревізія може мати dirty=true, оскільки звіт створюється до коміту.

Цей прогін не є доказом літературної якості, реальної поведінки моделей або виконання ручних процедур. Коди виходу та лічильники не замінюють аналізу тестів.

Архітектура: [SPEC.MD](../SPEC.MD). Способи перевірки: [інструкція та матриця](verification/README.md). Мотиви рішень: [ADR](adr/README.md). Подальша робота: [беклог](superpowers/plans/2026-10-20-remediation-backlog.md).
