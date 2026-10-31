# Ручне редагування завдання після вибору пам’яті

Причина підтверджена read-only API: generated brief актуальний зі snapshot, дві нові manual brief версії complete/stale=true без manual_projection_policy. Попереднє виправлення охопило draft/prose, але пропустило POST /brief.

Виправлення: той самий nullable manual_projection_policy для нового ручного brief; inputs і sorted hidden_before беруться з одного ContextView. Збереження створює нову версію, не копіює старий модельний snapshot і не приймає його приховано. Native WritersBrief validation/CAS/історія/proposed_changes збережені. Brief із proposed_changes чекає явного accept-brief; без них нова авторська версія стає head, якщо policy/revision ще збігаються. Старі версії не змінюються. Поле вже існує, SQL migration/config/model calls не потрібні.

RED: HTTP400 для звичайної правки, відсутня policy для proposal. GREEN тести обох шляхів плюс accept/CAS/подальша policy change. SPEC/traceability/review/full verify, застосування backend без reload вкладки або зміни авторського тексту.

Приймання: scripts/verify.py -q — **920 passed, 1 skipped**, 0 failed/errors; artifacts/verification-raak39r6/result.json, source_changed_during_run=false. Незалежне статичне рев’ю: actionable findings немає; його окремий pytest rerun не завершився й не рахується додатковим підтвердженням. Після перевірки відсутності активних runs точний сервер8765 перезапущено; HTTP200, revisions/heads обох творів незмінні (artifacts/manual-brief-restart-result.json). Вкладку не перезавантажували, авторські тексти/версії не застосовували, моделей не викликали. Після full verify — лише записи приймання; runtime/tests незмінні. Локальний коміт без push; R-18 залишається наступною плановою задачею.
