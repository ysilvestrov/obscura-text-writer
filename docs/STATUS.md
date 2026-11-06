# Стан перевірки проєкту

**ПЕРЕВІРКА ПРОЙШЛА** — свідчення конкретного запуску, не поточного довільного стану.

- Початок (UTC): 2026-11-06T23:41:42.682433+00:00
- Завершення (UTC): 2026-11-06T23:41:45.765798+00:00
- Базовий commit: `bd7a429acf214ac66807ef3ec0fd856a12224756`
- Незакомічені зміни під час перевірки: `true`
- SHA-256 вихідного знімка: `95b1fdb5e34f63c4a18eab11ee5849654cceb7b79ddae8d5790f81ca149a880c`
- Зміна знімка під час прогону: `false`
- Exit code: `0`
- Фактичні testcase результати JUnit: passed: 13 · failed: 0 · errors: 0 · skipped: 0
- Тривалість: 3.08 с

Точний argv (JSON, не shell-команда):

```json
["C:\\Users\\yuriy\\.codex\\worktrees\\workspace-telemetry\\text-generator\\.venv\\Scripts\\python.exe", "-m", "pytest", "tests/web/test_runs.py", "tests/web/test_workspace_route.py", "tests/web/test_editor_loop_ui.py", "tests/web/test_resumed_events.py", "-q", "--junitxml=C:\\Users\\yuriy\\.codex\\worktrees\\workspace-telemetry\\text-generator\\artifacts\\verification-mksgvsg0\\junit.xml", "--basetemp=C:\\Users\\yuriy\\.codex\\worktrees\\workspace-telemetry\\text-generator\\artifacts\\verification-mksgvsg0\\test-tmp"]
```

Результат стосується лише наведеної команди й вихідного знімка. Якщо в argv зазначено окремі файли або фільтри, це часткова перевірка. Збір (collection) не є виконанням; skipped не зараховано до passed. Відсутній або непридатний XML позначається непідтвердженим. Після зміни вихідних файлів звіт історичний. Власний STATUS і artifacts виключено зі знімка; початкова ревізія може мати dirty=true, оскільки звіт створюється до коміту.

Цей прогін не є доказом літературної якості, реальної поведінки моделей або виконання ручних процедур. Коди виходу та лічильники не замінюють аналізу тестів.

Архітектура: [SPEC.MD](../SPEC.MD). Способи перевірки: [інструкція та матриця](verification/README.md). Мотиви рішень: [ADR](adr/README.md). Подальша робота: [беклог](superpowers/plans/2026-10-20-remediation-backlog.md).
