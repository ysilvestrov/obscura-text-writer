# Стан перевірки проєкту

**ПЕРЕВІРКА ПРОЙШЛА** — свідчення конкретного запуску, не поточного довільного стану.

- Початок (UTC): 2026-11-06T16:00:14.942343+00:00
- Завершення (UTC): 2026-11-06T16:00:54.049626+00:00
- Базовий commit: `f1a35b933c6237d117c8c4529d366a8d1ed81386`
- Незакомічені зміни під час перевірки: `true`
- SHA-256 вихідного знімка: `2eb5106f606fed08f3c843b5b1892ed4be623d3ce028d3d6335efc52b1129fa3`
- Зміна знімка під час прогону: `false`
- Exit code: `0`
- Фактичні testcase результати JUnit: passed: 541 · failed: 0 · errors: 0 · skipped: 0
- Тривалість: 39.11 с

Точний argv (JSON, не shell-команда):

```json
["C:\\Projects\\text-generator\\.venv\\Scripts\\python.exe", "-m", "pytest", "tests/providers", "tests/billing", "tests/storage/test_import_counts.py", "tests/generation/test_provider_diagnostics.py", "tests/generation/test_model_json_boundaries.py", "tests/generation/test_planner_output.py", "tests/generation/test_editor_output.py", "tests/evaluation", "tests/web", "tests/review/test_contract4_runner.py::test_report4_replay_and_backup_are_exact", "-q", "--junitxml=C:\\Projects\\text-generator\\artifacts\\verification-qxf5vqkl\\junit.xml", "--basetemp=C:\\Projects\\text-generator\\artifacts\\verification-qxf5vqkl\\test-tmp"]
```

Результат стосується лише наведеної команди й вихідного знімка. Якщо в argv зазначено окремі файли або фільтри, це часткова перевірка. Збір (collection) не є виконанням; skipped не зараховано до passed. Відсутній або непридатний XML позначається непідтвердженим. Після зміни вихідних файлів звіт історичний. Власний STATUS і artifacts виключено зі знімка; початкова ревізія може мати dirty=true, оскільки звіт створюється до коміту.

Цей прогін не є доказом літературної якості, реальної поведінки моделей або виконання ручних процедур. Коди виходу та лічильники не замінюють аналізу тестів.

Архітектура: [SPEC.MD](../SPEC.MD). Способи перевірки: [інструкція та матриця](verification/README.md). Мотиви рішень: [ADR](adr/README.md). Подальша робота: [беклог](superpowers/plans/2026-10-20-remediation-backlog.md).
