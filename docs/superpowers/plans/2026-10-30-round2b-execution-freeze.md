# A′/round2b: execution adapter і freeze

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Виконати в цьому чаті, з code-only рев’ю наприкінці.

**Goal:** Реалізувати guard точних відправлених байтів,720-slot dry-run без HTTP та окремий execution freeze, STOP до активації quality.

**Spec:** Пряма вказівка власника30.10.2026; [погоджений input freeze](../../research/round2b/frozen-quality.json), [політика L3/secondary](../../research/2026-10-30-round2b-freeze-admission.md).

**Architecture:** Новий адаптер читає незмінні240nativewire й використовує незмінні normalize/validator/ledger helpers. Legacy frozen_send не застосовується. Input snapshot не перезаписується; execution snapshot охоплює лише явно додані файли й посилається на погоджений input SHA.

## Контракт і rulings

- Перед кожним live POST guard перевіряє точні request.content байти, URL/method і прив’язку до правильних model/case/slot. Невідповідність — STOP **до HTTP й платного резервування**.
- Старий wire_sha256 є digest JSON-конверта. Новий http_body_sha256 — SHA-256 compact UTF8 JSON body зі збереженим frozen порядком ключів (`ensure_ascii=False`, `allow_nan=False`). Він виводиться з того самого замороженого body, без зміни його полів, і записується для кожного240wire в execution freeze. Старий digest перевіряється окремо.
- Використовується `content=bytes`, не `json=...`; перевірка повторюється над фінальним HTTP Request безпосередньо перед send. Ключі лише в auth headers, ніколи в журналах чи request snapshots.
- Local model не переписується на runtime ID. Echo load_config має дослівно збігатися з qualification; instance ID має дозволяти використати незмінний frozen model ID. Якщо це неможливо — STOP до inference, без нормалізації hash.
- Backend перевіряється при вході в кожну live model session. Окремий load-only probe може перевірити3моделі без генерації й після себе звільняє GPU; він не є dry-run і не підміняє повторний runtime guard. За зайнятої GPU не витісняти чужі моделі.
- Dry-run має пройти720слотів через той самий byte guard, без API-клієнта/HTTP/inference/ledger-змін. Пише лише в окрему dry-run папку; planned live paths завжди `artifacts/round-2b/quality/`, ніколи round2. Fake-відповіді не стають quality slots.
- Quality activation artifact відсутній і цим етапом не створюється. Live шлях fail-closed без окремого явного дозволу, прив’язаного до execution freeze. CLI run має подвійний gate: явний --authorized-quality та окремий owner activation artifact, якого цей етап не створює.
- Primary/secondary/пороги/набір/A′/schema не змінюються. Ніяких holdout викликів, timing, senior чиB7.

## Кроки

1. [ ] RED→GREEN synthetic тести: змінені body/URL/slot; байти перед send; незмінний local model; backend echo mismatch; auth без запису ключів; safe round2b paths; відсутня activation; guarded response normalization без зміни primary.
2. [ ] Реалізація `docs/research/round2b/execution.py`, `test_execution.py`, CLI `docs/research/r28q-round2b-execution.py`; старі helpers і input freeze незмінні.
3. [ ] Офлайн-регресія та code commit; load-only backend check за вільної GPU, без generation endpoint.
4. [ ] Dry-run720 без HTTP, exact-byte evidence й перевірка output namespace. Перевірити незмінність ledger та відсутність quality results.
5. [ ] Зібрати execution snapshot, не активуючи його; окремий commit. Code-only рев’ю коду/metadata без передачі holdout/seed іншій моделі; important findings RED→GREEN і новий snapshot до першого inference.
6. [ ] Підсумкові перевірки й звіт. STOP перед quality activation.

## Evidence

Результати команд, точні SHA, рев’ю й відхилення записуються у execution report і remediation-progress; цей файл — план, не запис виконаних перевірок. Research tooling не змінює продукт/SPEC; продуктові UA/EN інструкції не потребують змін, research CLI інструкція оновлюється.

Ruling до freeze: literalbody serialization точно відтворює pinned HTTPX json= encoding, включно з порядком schema properties. Sort_keys не застосовується, бо міг би змінити порядок полів constrained schema порівняно з qualification. Старий envelope digest лишається окремим semantic guard. One-shot streams відхиляються, фінальний byte-stream має бути повторюваним ByteStream; headers/hooks не змінюють body.
