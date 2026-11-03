# Нейтральний local smoke послідовного пошуку

27.10.2026, локальний API localhost:1235/v1, huihui-qwen3.5-9b-abliterated. Використано синтетичний приклад про лист; авторський твір не запускався й не передавався. Thinking вимкнено, native JSON Schema, поточний planner profile128K/output12288. Платних API-викликів немає.

| Частина | Вхідні токени | Вихідні токени | Reasoning | Секунди | Результат |
|---|---:|---:|---:|---:|---|
| delta |587|173|0|23,51|completed, валідний wire3|
| check |1480|194|0|27,97|completed, валідний wire3|
| synthesis |588|190|0|21,56|completed, валідний wire3|

Разом73,04с. Raw/attempts/usage збережено локально в ignored artifacts/sequential-review-smoke; це перевірка транспорту, схеми й локальних посилань, не літературне приймання. Модель висловила сумнівне зауваження, трактуючи «згадала лист» як потенційну суперечність знанню про лист. Авторський reject/fix checkpoint потрібний і після коректного JSON; модельний judge не додано.

Offline tokenizer з перевіреними tokenizer/template bytes точно відтворив587/1480/588 observed prompt_tokens. Створено окремий profile `c06b6ac93445287880b84f79d09d8df8931866d35be1c40613a656d0fc64164f`, прив’язаний до model/endpoint/system hash; незнайомий scope, деактивація або змінені bytes повертають conservative fallback. Власник окремо погодив активацію27.10.2026. Два попередні активні bindings збережено, додано третій; налаштування інших ролей не змінювалися.

Перший smoke проводився до додавання читабельних назв передумов у evidence payload. System prompt і native request envelope не змінювалися; кваліфікація стосується точного tokenizer/template й цього envelope, а не конкретного тексту user payload. Валідація нового payload та fallback додатково покрита тестами `tests/review/test_local_counter.py`.
