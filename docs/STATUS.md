# Стан перевірки проєкту

**ПЕРЕВІРКА ПРОЙШЛА** — свідчення конкретного запуску, не поточного довільного стану.

- Початок (UTC): 2026-11-05T21:29:43.910606+00:00
- Завершення (UTC): 2026-11-05T21:29:45.867260+00:00
- Базовий commit: `4496fb9b6ad2c21d28ac6dc0b7dfe9db6760f437`
- Незакомічені зміни під час перевірки: `true`
- SHA-256 вихідного знімка: `ed5d461e20f60f96316f36bdda4ef6755493335e7d6b8ad6e9e7f63a30fcf8bd`
- Зміна знімка під час прогону: `false`
- Exit code: `0`
- Фактичні testcase результати JUnit: passed: 8 · failed: 0 · errors: 0 · skipped: 0
- Тривалість: 1.95 с

Точний argv (JSON, не shell-команда):

```json
["C:\\Projects\\text-generator\\.venv\\Scripts\\python.exe", "-m", "pytest", "tests/web/test_word_targets.py", "tests/web/test_localization.py", "-q", "--junitxml=C:\\Projects\\text-generator\\artifacts\\verification-vbwybr4f\\junit.xml", "--basetemp=C:\\Projects\\text-generator\\artifacts\\verification-vbwybr4f\\test-tmp"]
```

Результат стосується лише наведеної команди й вихідного знімка. Якщо в argv зазначено окремі файли або фільтри, це часткова перевірка. Збір (collection) не є виконанням; skipped не зараховано до passed. Відсутній або непридатний XML позначається непідтвердженим. Після зміни вихідних файлів звіт історичний. Власний STATUS і artifacts виключено зі знімка; початкова ревізія може мати dirty=true, оскільки звіт створюється до коміту.

Цей прогін не є доказом літературної якості, реальної поведінки моделей або виконання ручних процедур. Коди виходу та лічильники не замінюють аналізу тестів.

Архітектура: [SPEC.MD](../SPEC.MD). Способи перевірки: [інструкція та матриця](verification/README.md). Мотиви рішень: [ADR](adr/README.md). Подальша робота: [беклог](superpowers/plans/2026-10-20-remediation-backlog.md).
