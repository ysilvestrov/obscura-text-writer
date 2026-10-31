# A′ / round2b: execution freeze — STOP

Дата: 30.10.2026. Виконано доручення власника щодо адаптера, guard, сухого прогону й окремого execution freeze. Quality не активовано; holdout-відповідей не отримували.

## Зафіксований пакет

- [Execution freeze](round2b/execution-freeze.json): `30419ff93043bc410233cd8e87b68273a0514b8b1464d69782ca1ff940cb24e0`; окремий commit `3014cda`, реалізація з виправленням namespace — `f05ae25`.
- Незмінний [input freeze](round2b/frozen-quality.json): `ce1b4068175e470d3671c93bf1c23c7d568643992638306b0ec6cbe8734f291d`.
- 370 файлів у execution snapshot; 240 frozen native wire, 720 слотів. [Машинний аудит](round2b/execution-audit.json).

## Контракт адаптера

Перед кожним POST перевіряються слот, точні method/URL, envelope digest і SHA-256 фактичного повторюваного HTTP byte-stream. Змінені байти зупиняють dispatch до HTTP та платного резерву. JSON кодується compact UTF-8 зі збереженим frozen порядком ключів, як у pinned HTTPX; використовується `content=bytes`. Старий envelope hash і новий literal-body hash перевіряються окремо. Модель у body не підміняється runtime ID. Headers із ключами не записуються.

Виходи належать лише фізичному namespace `artifacts/round-2b/quality`; перенаправлення через junction/symlink відхиляється. Dry-run пише лише окремий report, не створює quality slots. Основні helpers, A′, schema, набір, primary/secondary правила й пороги незмінні.

Live потребує одночасно `run --authorized-quality` та окремого `activation.json`, прив’язаного до execution/input SHA з явним owner authorization і exclusive local API window. Цей етап artifact не створює. Перед кожною локальною сесією перевіряються актуальні echo load_config та model ID проти qualification; розбіжність зупиняє виклик.

## Фактичні перевірки

- Load-only Bionic probe: L3, L5, L6 — точний збіг qualification echo й frozen model ID; generation calls **0**, GPU після перевірки звільнено. Це окрема перевірка backend із керувальними HTTP-запитами, а не offline dry-run.
- Повторний offline dry-run після namespace hardening: **720/720** byte matches; HTTP **0**, inference **0**, ledger writes **0**. Доказ: `artifacts/round-2b/execution-dry-run/report.json`; backend proof: `artifacts/round-2b/execution-preflight/backend-echo.json`.
- Офлайн-регресія через `scripts/verify.py docs/research/round2 docs/research/round2b -q`: **264 passed, 0 failed**. Доказ: `artifacts/verification-opzcomfd/result.json`, [STATUS](../STATUS.md). Перевірка охоплює дослідницький код, не весь продукт і не змістову якість моделей.
- Незалежне code-only рев’ю початкового кандидата `a8c877…`: критичних/важливих зауважень немає; 19 synthetic тестів пройшли. Рев’ю не читало holdout/seed й не виконувало HTTP/inference. Додатковий власний аудит виявив parent-junction escape; дві регресії спочатку відтворили дефект, після виправлення ввійшли до 264 успішних тестів. Попередній неактивний кандидат збережено в історії (`c2fe673`) та приватному архіві.

## Бюджет та межі

Read-only ledger: settled **$0.1711025**, невизначений резерв **$0**, доступно зі спільних $10 **$9.8288975**. Нових платних викликів не було. Activation і quality slots відсутні. Timing, senior та B7 не запускалися. Valid/invalid результати holdout ще відсутні; byte-перевірка не є доказом змістової якості.

## Користування дослідницьким CLI

За `PYTHONPATH=src;docs/research` команда `.venv/Scripts/python.exe docs/research/r28q-round2b-execution.py verify` перевіряє execution snapshot та залежності без inference. Не повторювати `freeze`/`dry-run` поверх доказів: існуючі файли захищено від перезапису. `run` на цьому етапі не викликати.

Research-only зміни не змінюють архітектуру продукту чи користувацький UI; SPEC.MD і продуктові UA/EN інструкції оновлення не потребують. Оновлено інструкції дослідницького CLI й звіт.

**STOP перед окремим дозволом на активацію quality.**
