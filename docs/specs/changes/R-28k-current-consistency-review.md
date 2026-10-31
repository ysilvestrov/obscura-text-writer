# R-28k — Перевірка старих текстів за поточними передумовами

Власник погодив27.10.2026: за відсутності історичної бази перевіряти узгодженість із поточними передумовами. Початкові версії не backfill. Стару/нову базу не вигадувати.

Protocol3 розрізняє historical_delta і current_consistency для кожного target. Fallback дозволений лише коли root version не має dependency snapshot або авторського baseline; інші blockers не обходяться. Current-consistency будує окремий read-only snapshot поточного плану/канону/карток, метаданих, попередньої прози й попередньої пам’яті. Майбутня проза заборонена; чинні temporal projections і memory validation лишаються. Ancestor creation histories не трактуються як історія створення legacy target.

Для такого target немає delta; check/synthesis отримують повні чинні передумови й текст за наявними правилами розбиття. Report/preview/UI явно показують mode й відсутність історичного порівняння. Повне clean coverage дозволяє звичну model authority, concerns — авторський checkpoint. Acceptance й CAS прив’язані до того самого mode/current snapshot; зміна джерел знову інвалідує результат. Первинні version records/acceptance records не переписуються. Старі report/run без mode map лишаються historical_delta й відтворюють старий exact API body.

Без змін SQL4, system prompt/local-counter binding, ролей, бюджету й автоматичних повторів. Немає автоматичного запуску авторської книги. Помилки показують сцену/матеріал замість повтореного безадресного повідомлення.

Продуктове рішення вичерпано відповіддю власника; згідно з попередньою інструкцією план одразу реалізується без додаткового підтвердження.
