# Пакетний вибір змін переписування за коментарями

Дата06.11.2026. Прямий запит власника з активного беклогу; початок найближчих задач погоджено. Це малий UI fix без нового API/storage: одна кнопка «Обрати всі зміни» у rewrite review над grouped changes, чинні secondary styles і UA/EN.

Кнопка позначає всі поточні sentence/format groups, скидає indeterminate і старий assembled preview; жодного POST/generation/save на натискання. Далі автор явно переглядає зібраний текст і застосовує вибір через чинні fingerprint/revision/comments CAS. Dirty/saving/busy/loading/нечинна чи вже вирішена пропозиція блокують дію так само, як окремі choices. Коли все вибрано — disabled. Для порожнього/no-change результату кнопка прихована. Початковий вибір залишається порожнім; окремі checkbox лишаються; copyediting UI не змінюється.

Одна inline задача, base32a04ad: RED browser select-all/no-publication → мінімальний control у change-review.js/i18n → browser partial/all/UA/EN/pending guards і desktop/mobile screenshot → SPEC/traceability та UA/EN інструкції → verify/check_docs/cross-review → commit/push/PR і основна тека. Нових залежностей, міграцій, inference чи платних дій немає.

Наступну задачу згортання сцен власник уточнив для обох екранів: редактора й результатів перевірки книги. Це окремий пакет після цього fix; поведінка згортання списку уточнюється асинхронно.


Реалізовано: initial browser RED2 failures (відсутня кнопка) → GREEN2 passed після виправлення тестового підпису preview. Без API/storage змін. Спільний gate/cross-review після наступного малого пакета згортання, review base32a04ad.
