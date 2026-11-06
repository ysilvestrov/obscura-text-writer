# Зовнішня обгортка всіх модельних JSON-відповідей

Пряме рішення власника06.11.2026: прибирати зовнішні апострофи не лише в пам’яті, а й у перевірках та інших структурованих відповідях моделей.

Причина дефекту: impact/review decoder передавав модельний текст безпосередньо до json.loads; нормалізація пам’яті не поширювалася на інші межі протоколу.

Один спільний чистий helper знімає лише одну повну парну зовнішню обгортку JSON-об’єкта: одинарні апострофи/backticks або потрійний блок з окремими рядками й необов’язковим json. Без витягування JSON із пояснень, без ремонту вмісту та без заміни апострофів усередині рядків. Непарні/вкладені/кілька блоків залишаються помилкою. Чинні schema, duplicate-key, evidence, scope та publication guards зберігаються. Сирий partial і звіт оцінювання залишаються оригінальними.

Межі застосування: planner brief/prepare, editor patches, classifier, publication suggestions, memory, impact/review (також replay/fsck), evaluator model response. Ручні JSON, конфігурація, збережені доменні об’єкти й CLI event protocol залишаються строгими. Текстова генерація draft/rewrite/edit diff не нормалізується. Fingerprint evaluator protocol збільшується: попередня калібрація не дає автоматичного допуску новому parser contract; історичні результати не переписуються.

Реалізація inline: регресії RED → helper та підключення лише на модельних межах → SPEC/traceability/UA+EN інструкції → verify.py та check_docs.py → cross-review/commit/push/PR. Нових запитів до моделей або повтору невдалого запуску немає.


Фінальний спільний gate model/import metadata та global MODEL-JSON: **1244 passed,1 skipped,0 failures/errors**, source_changed_during_run=false, artifacts/verification-smi5njs9/result.json. check_docs.py пройшов. Раніше UI110 browser passed2.7m,8 додаткових metadata/counts/shared passed,6 фінальних pricing/accessibility passed; фінальні screenshots перевірено візуально, detector[]. Без реального inference або зміни production матеріалів.

RED4 failures/8 passes → GREEN41 wrappers/memory;65 targeted parser/evaluation/review replay tests passed. Read-only перевірка останньої невдалої review_part підтвердила повний Markdown JSON-блок; після нормалізації проходять decoder і frozen schema/evidence. Оригінальний partial/статус запуску не змінено; приватний вміст не копіюється й не передається рецензенту.
