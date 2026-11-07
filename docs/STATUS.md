# Стан перевірки проєкту

**ПЕРЕВІРКА ПРОЙШЛА** — свідчення конкретного запуску, не поточного довільного стану.

- Початок (UTC): 2026-11-07T12:27:37.804084+00:00
- Завершення (UTC): 2026-11-07T12:27:39.407826+00:00
- Базовий commit: `0fcba9696cfb0df84e018de05ec003750f4eb382`
- Незакомічені зміни під час перевірки: `true`
- SHA-256 вихідного знімка: `aeaa33e996d06be9df545fd8924a5f920d49a2d8800df77d8a99277befad3f59`
- Зміна знімка під час прогону: `false`
- Exit code: `0`
- Фактичні testcase результати JUnit: passed: 1 · failed: 0 · errors: 0 · skipped: 0
- Тривалість: 1.61 с

Точний argv (JSON, не shell-команда):

```json
["C:\\Users\\yuriy\\.codex\\worktrees\\workspace-telemetry\\text-generator\\.venv\\Scripts\\python.exe", "-m", "pytest", "tests/authoring/test_scene_description.py::test_parenthetical_matching_preserves_exact_names_and_ambiguity", "-q", "--junitxml=C:\\Users\\yuriy\\.codex\\worktrees\\workspace-telemetry\\text-generator\\artifacts\\verification-jo2xogo8\\junit.xml", "--basetemp=C:\\Users\\yuriy\\.codex\\worktrees\\workspace-telemetry\\text-generator\\artifacts\\verification-jo2xogo8\\test-tmp"]
```

Результат стосується лише наведеної команди й вихідного знімка. Якщо в argv зазначено окремі файли або фільтри, це часткова перевірка. Збір (collection) не є виконанням; skipped не зараховано до passed. Відсутній або непридатний XML позначається непідтвердженим. Після зміни вихідних файлів звіт історичний. Власний STATUS і artifacts виключено зі знімка; початкова ревізія може мати dirty=true, оскільки звіт створюється до коміту.

Цей прогін не є доказом літературної якості, реальної поведінки моделей або виконання ручних процедур. Коди виходу та лічильники не замінюють аналізу тестів.

Архітектура: [SPEC.MD](../SPEC.MD). Способи перевірки: [інструкція та матриця](verification/README.md). Мотиви рішень: [ADR](adr/README.md). Подальша робота: [беклог](superpowers/plans/2026-10-20-remediation-backlog.md).
