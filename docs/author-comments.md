# Авторські коментарі до чернетки

У вкладці «Чернетка» загальна вказівка розташована під редактором. Для окремої фрази виділіть текст і натисніть іконку коментаря на toolbar. Натискання на підсвічений фрагмент відкриває ту саму вказівку. «Зберегти коментар» змінює робочі нотатки; кнопка «Зберегти» рукопису публікує текст і всі нотатки разом. Escape скасовує незастосований ввід popover. Кнопка «Переписати за коментарями» під панеллю запускає один виклик Writer після підтвердження.

`GET /api/scenes/{id}/comments?material=draft` повертає збережений набір, ревізію, джерело й `source_matches_current`. Коментарі не переприв’язуються автоматично після генерації або заміни чернетки. Редагування нотаток без зміни тексту не змінює версію тексту та не робить наступні сцени застарілими.

Для atomic Save використовується чинний `POST /api/scenes/{id}/draft`:

```json
{
  "text": "Збережений текст чернетки.",
  "content_format": "markdown",
  "expected_revision": 3,
  "expected_source_version_id": "поточний-id-чернетки",
  "expected_comments_revision": 1,
  "comment_set": {"general": "Скоротити вступ.", "comments": []}
}
```

Для першого тексту без head джерело явно `null`, початкова ревізія notes —0. Поля прикладу слід брати з фактичної відповіді сервера. Успішне збереження повертає scene/version/comment_set. Конфлікт409 вимагає оновлення джерел; не повторюйте запит автоматично й не викидайте робочий текст.

Фрагментні anchors використовують Unicode codepoints, не JS UTF-16. Сервер перевіряє точну raw цитату й її видимий текст у всьому документі. Діапазони напіввідкриті; сусідні дозволені, вкладені/пересічні — ні. Коментар до зміненого фрагмента зберігає `needs_review` та первісне джерело; це не дозвіл відправляти його письменнику. Новий коментар на ще не збереженому тексті може зберегти початковий raw source proof лише під час явного Save. Ніякого HTML або сторонніх модельних викликів при Save немає.

Межі:100 коментарів,8000 символів на інструкцію,12000 general,50000 сумарно для інструкцій/general. Не обрізайте надлишок мовчки. Історичні source proofs мають окремі обмеження160000/1млн символів; immutable blob з повним SHA включається у fsck/verified backup.

## Міграція та перевірка

Міграція004 переводить SQLite3→4 й додає append-only history; старі текстові blobs та payload не переписуються. Перед production restart потрібен перевірений cold backup та відсутність активної/незбереженої роботи. Read-only fsck підтримує2/3/4 й не мігрує каталог. Відновлюйте резерв у нову папку за чинною інструкцією, не поверх робочих даних.

Розробницька перевірка: `python scripts/verify.py tests/storage/test_comments.py tests/storage/test_comments_migration.py tests/web/test_comments_api.py -q`. Усі приклади й бази синтетичні; production дані не використовуються.

## English

In Draft, write a general instruction below the editor, or select text and use the comment toolbar icon. Click a highlight to edit its instruction. Save comment updates working notes; manuscript Save stores text and notes atomically. Escape cancels uncommitted popover input. Overlapping selections are blocked. Editing a commented fragment requires reattachment or deletion; text undo/redo preserves corresponding anchor geometry without undoing instruction edits. Use Rewrite from comments below the notes to make one confirmed Writer call. A comment set is independent from the manuscript version. Saving notes alone preserves text IDs, scene/story revisions and dependent freshness. Save draft text and notes together with explicit scene revision, note revision and source version ID. A409 response preserves the other tab's changes; do not retry automatically or discard the working buffer.

Anchors use Unicode codepoints and exact source/visible quotes. Adjacent ranges are allowed; overlaps are rejected. Modified anchors retain their original source and require review. Unpublished originals can be retained as immutable source proofs on explicit Save. No model call occurs during Save.

Migration004 upgrades SQLite3→4. Before applying it to production, stop safely and create a verified cold backup. Read-only integrity checks support schema2/3/4 and never migrate the database.


## Черга переписування (R-23c, API)

Після явного Save передайте в `POST /api/runs` mode=`rewrite`, scene_id, source_version_id, comment_set_id та comment_fingerprint з GET comments. Один request_id відповідає одному незмінному запиту. Використовується модель і параметри Writer; окремий системний промпт повертає повний текст, без JSON. У цьому пакеті результат лишається пропозицією, без заміни чернетки; панель перегляду доступна у вкладці «Чернетка». Не запускайте resume для повтору готової пропозиції. Невдалий/перерваний виклик потребує окремого явного рішення; автоматичного повтору немає.

English: Save first, then enqueue `mode=rewrite` with exact source version, comment set and fingerprint from GET comments. The writer uses a separate plain-response prompt and makes one call. A proposal does not replace the draft. Review UI is available inside Draft; a ready proposal cannot be resumed into another paid call.


## Перегляд і прийняття

1. Напишіть загальну вказівку та/або коментарі до непересічних фрагментів. Виправте pending прив’язки. Без вказівок кнопка недоступна.
2. Натисніть «Переписати за коментарями». Незбережені правки спочатку пропонуються до Save; Cancel залишає їх без виклику моделі. Після preflight перевірте Writer/model й підтвердьте один виклик.
3. Результат відкривається в «Чернетці» як readonly diff. Початково нічого не обрано. Мітки «У межах», «Поза», «Перетинає» описують координати змін, а не доводять виконання побажань.
4. Виберіть групи речень/форматування, перегляньте зібраний текст і завершіть перегляд. Порожній вибір відхиляє все й зберігає нотатки. Прийняття subset/all створює нову чернетку й очищає робочі вказівки; історичні інструкції лишаються в деталях спроби. Проза не замінюється.
5. Продовжуйте вручну, додайте нові коментарі або запустіть звичайну редактуру. Переписування завдання/прози поки не підтримується.

English: Add general and/or nonoverlapping range comments, resolve pending anchors, then choose Rewrite from comments. Dirty edits require Save or Cancel; preflight confirms one Writer call. The draft stays unchanged until grouped review and assembled preview are accepted. Geometric location labels do not prove instruction compliance. An empty selection rejects all and keeps notes. Partial/full acceptance creates a draft and clears working notes while preserving attempt instructions and history. Prose remains unchanged. You can then edit manually, comment again, or continue to the usual editor.

Нейтральний приклад перегляду: [знімок](images/r23-rewrite-review.png).

Якщо інша вкладка змінила вказівки, переписування зупиниться з конфліктом: збережіть свій ввід окремо й явно оновіть чернетку/нотатки. English: if another tab changed instructions, rewriting stops with a conflict; preserve your working input separately and explicitly reload the draft/notes.

Підтвердження збереження правок і запуску переписування відкриваються у вікні застосунку. «Скасувати» або Escape залишає поточні правки без запуску; при закритті вкладки попередження про незбережене показує браузер.
