# План: авторське використання пам’яті

Підстава: docs/specs/changes/memory-author-reuse-2026-10-24.md та пряма відповідь власника про дозвіл після попередження. Реалізація в поточній гілці.

1. RED/GREEN memory/reuse.py: перевірка історичного префікса, відмінностей і fingerprint; жодного переписування журналу.
2. DependencySnapshot/ContextBundle: scoped stale-memory allowance і успадкована provenance; memory context/результат та journal_before. Регресії publish/подальшої сцени/CAS.
3. RunRequest, readiness, worker: конкретне підтвердження лише memory stage, перед inference повторна перевірка fingerprint, усі інші блокування чинні.
4. UI runs/readiness/workspace + UA/EN: доступна дія з питанням, decline без enqueue, warnings відрізняють ті самі тексти від змінених.
5. SPEC/traceability/manual/runbook/progress; цільові й повний verify/check_docs. Без фактичної генерації; перезапуск сервера лише після захисту незбережених буферів/активних запусків.

## Виконано

Кроки1–5 завершено; незалежне рев’ю та його підтверджене виправлення ручного Save пройшли RED/GREEN. Повний verify1012 passed/1 skipped, check_docs пройшла. Runbook оновлено українською, сайт двома мовами ще не реалізований. Перезапуск основного сервера погоджено окремо й виконано; API smoke підтвердив можливість автора продовжити сцену9. Реальна генерація не запускалася.
