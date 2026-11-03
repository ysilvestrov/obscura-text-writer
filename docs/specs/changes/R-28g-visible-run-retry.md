# R-28g — Видиме відновлення невдалого запуску

Дефект: updateControls приховує repeat/resume за будь-якої причини недоступності, зокрема під час async pending readiness після навігації та після зміни ролі. Автор втрачає кнопку й пояснення.

Для failed/interrupted/cancelled repeat SHALL бути видимим, доки цей run вибраний; для paused/needs_review/alternative аналогічно resume. Readiness/saving/dirty/busy лише вимикають кнопку й показують причину. State gate залишається: completed не отримує repeat, активний run не отримує repeat/resume. Повернення з налаштувань знову завантажує останній run без dispatch; незбережений буфер не перезаписується. API/SQL/states незмінні.

План: browser regression з відновленим failed run, затриманою готовністю та configuration blocker; RED→GREEN мінімальна правка updateControls; SPEC/traceability/UA+EN guide; цільові browser/JS тести. Окремо погоджено підвищити лише planner output8192→12288, що чинною формулою дає cap5939 за context131072/maxchars500000. Нічого не обрізати й не переписувати frozen manifests; новий preview/run явною дією автора.

Виконано: browser RED відтворив hidden під час pending, GREEN desktop/mobile2PASS після мінімальної правки. API CAS178: planner output12288, інші roles/prompts/profile незмінні; запусків не додано. Фінальні перевірки: verify-gtnfup7r33PASS/source_changed=false; повний impact browser desktop/mobile14PASS; check_docsPASS. Робоча сторінка після reload показує disabled repeat з причиною «Налаштування планувальника змінилися; потрібен новий перегляд частин»;0active. Static ресурс оновлено без server restart, inference не було.
