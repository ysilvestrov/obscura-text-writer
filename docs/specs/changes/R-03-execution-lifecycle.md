# R-03 — Надійне виконання й відновлення workflow

Статус: частини 1–2 реалізовані тут; залежна частина 3 завершена в R-05c (397 passed, 1 skipped у спільному фінальному прогоні).
Джерело: погоджений беклог R-03, T-03/T-10. Рішення автора 20.10.2026:
скасування зупиненого запуску завершує його як cancelled зі збереженням матеріалів.

## Межі

Буфер генераційного потоку, довговічні checkpoint, SSE replay та переходи
cancel/pause/resume/recovery. Один worker і кооперативне скасування збережені.
Evaluator має власні checkpoints; його транспорт не змінюється цим пакетом.
Нової схеми БД, міграції, моделей або зовнішніх викликів немає.

## Requirement: R03-STREAM — Пакетний запис

Система SHALL зберегти порожній partial до звернення до моделі. Нові delta
SHALL накопичуватися до 16384 байтів UTF-8 або 0,5 секунди від останнього
checkpoint; час перевіряється лише при надходженні наступної непорожньої delta.
Фонового таймера немає. Одна велика delta не розрізається посеред Unicode.
Partial SHALL дозаписуватися окремим writer; атомарний запис незмінних версій
залишається без змін. Перед callback пакетної delta SHALL виконуватися flush/fsync.
SQL сам призначає seq у транзакції; протокол delta.text не змінюється.

### Scenario: Маленькі фрагменти
- GIVEN 1000 delta по 10 ASCII-байтів і незмінний годинник
- WHEN потік завершується
- THEN partial і конкатенація пакетних подій дорівнюють точному тексту
- AND не більше трьох записів partial, fsync і транзакцій delta.

### Scenario: Завершення або помилка
- GIVEN є незбережений хвіст
- WHEN потік закінчується, скасовується або шлюз кидає виняток
- THEN хвіст скидається перед фінальним станом
- AND невалідний/скасований/перерваний результат не публікується.

### Scenario: Помилка checkpoint
- GIVEN запис partial, fsync або збереження delta завершується помилкою
- WHEN етап припиняється
- THEN результат не публікується і автоматичного повтору checkpoint/inference немає.

### Scenario: Аварійна зупинка
- GIVEN попередній checkpoint довговічний, наступний хвіст лише в RAM
- WHEN процес аварійно завершується без finally
- THEN збережений checkpoint доступний, хвіст може бути втрачений
- AND відновлення не трактує partial як завершену версію.

Файл і SQL не є однією транзакцією: збій між fsync та SQL може залишити partial
довшим за журнал delta. Збій усередині запису може лишити непідтверджений хвіст;
після recovery він лише діагностичний. Exactly-once inference не обіцяється.
SSE SHALL віддавати тільки зафіксовані події з seq > after/Last-Event-ID;
продовження читання не дублює вже підтверджені пакети. GET partial повертає коректний UTF-8 префікс при незавершеному останньому символі; файл не змінюється, внутрішні помилки UTF-8 не приховуються.

## Requirement: R03-STATES — Явні переходи

| Стан | cancel | pause | resume |
|---|---|---|---|
| queued | cancelled | paused | помилка |
| running | cancellation_requested | pause_requested | помилка |
| pause_requested | cancellation_requested | без зміни | помилка |
| cancellation_requested | без зміни | без зміни | помилка |
| paused/interrupted/needs_review/alternative | cancelled | без зміни | queued після preflight |
| failed/cancelled | без зміни | без зміни | queued після preflight |
| completed | без зміни | без зміни | помилка |

Для активного worker pause_requested очікує межі етапу; queued pause
відразу стає paused. Повторний cancel SHALL не створювати зайвих state-подій.
Cancel SHALL зберігати error/cursor/спроби/версії; активне скасування спостерігається
кооперативно. Resume невизначеної спроби вимагає repeat_interrupted=true;
помилки preflight не змінюють стан. Startup переводить queued/running/
pause_requested/cancellation_requested та running attempts в interrupted без API.

### Scenario: Збереження завершеного результату
- GIVEN completed, failed або cancelled зі збереженою помилкою та cursor
- WHEN автор натискає cancel повторно
- THEN payload і журнал подій не змінюються.

### Scenario: Завершення зупиненого запуску
- GIVEN paused, interrupted, needs_review або alternative
- WHEN автор натискає cancel
- THEN запуск стає cancelled, тексти й версії залишаються доступними.

## Частина 3 — завершена в R-05c

Явне продовження після вибраного/прийнятого alternative реалізовано за контрактом
[R-05](R-05-dependency-publication.md) і чинною SPEC.MD. Repository атомарно
звіряє run/task/cursor, останню спробу/result, selected head, freshness,
scene revision і acceptance ID перед просуванням. Вибір голови сам не
запускає worker; прийнятий етап не викликає inference повторно. Тести:
`tests/generation/test_accepted_resume.py`,
`tests/integration/test_prototype_flow.py::test_seven_scenes_accept_alternative_restart_and_export`.

## Перевірка й сумісність

Fake clock: розмір/час/Unicode; реальний файл і SQLite: порядок довговічності,
пакетування, exception/cancel, failure injection; аварійний subprocess без finally;
HTTP SSE replay; матриця cancel/pause/resume/recovery; регресії pipeline/worker.
Повний pytest послідовно з коротким унікальним basetemp. Ключі й авторські дані
не використовуються. Коренева SPEC.MD оновлюється разом із реалізацією.

## Простежуваність перевірок

| Контракт | Перевірка |
|---|---|
| R03-STREAM / PIPE-007-BATCH | `tests/generation/test_stream_buffer.py::test_many_small_deltas_use_one_durable_batch`, `test_utf8_threshold_and_time_checkpoint_preserve_order` |
| Завершення/error/cancel/exception | `tests/generation/test_stage_checkpoints.py::test_stage_checkpoints_flush_before_final_state` |
| Помилка checkpoint | `test_checkpoint_failure_never_publishes_result`, `test_stream_buffer.py::test_failed_checkpoint_is_not_retried_on_close` |
| PIPE-007-CRASH | `test_stage_checkpoints.py::test_abrupt_process_exit_keeps_only_prior_checkpoint` |
| PIPE-007-REPLAY | `tests/web/test_runs.py::test_batched_sse_replay_respects_both_cursors`, чинні `tests/web/test_resumed_events.py` |
| PIPE-007-UTF8 | `tests/web/test_runs.py::test_partial_reload_tolerates_incomplete_utf8_tail_during_append` |
| R03-STATES / PIPE-005-CANCEL-FINISHED | `tests/generation/test_worker.py::test_cancel_preserves_finished_or_already_requested_run` |
| PIPE-005-CANCEL-STOPPED | `test_cancel_stopped_run_keeps_material_and_diagnostics` |
| Pause/resume/recovery | `test_pause_does_not_change_stopped_or_pending_run`, `test_resume_uncertain_attempt_requires_explicit_repeat`, `test_recovery_interrupts_active_states_without_model_calls` |
