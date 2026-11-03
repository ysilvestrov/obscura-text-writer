# Редактура з програмним diff — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Виконання в цьому чаті й поточній гілці за раніше погодженим вибором власника. Один незалежний review наприкінці.

**Goal:** Приймати вибрані автором зміни суцільної редактури без вимоги модельних JSON-патчів.

**Architecture:** Новий edit_mode=diff і протокол пропозиції v2 використовують незмінну чернетку, програмні позиції й наявний storage CAS. Обов’язковий авторський перегляд; окрема необов’язкова queued-класифікація не змінює пропозицію.

**Tech Stack:** Python/Pydantic/SQLite/difflib, наявна черга й OpenAI-compatible gateways, vanilla JS.

**Spec:** docs/specs/changes/editor-rewrite-diff-review.md; чинні SPEC.MD EDIT-REVIEW/R-05.

## Обмеження

- Не змінювати робочі тексти, профілі або запущений сервер; не запускати платні API.
- Старі протоколи, guards patches, auto й prompt contracts сумісні.
- Позиції — code points Python; UI не застосовує їх до JS-рядка.
- Структурні зміни MUST відображатися у SPEC.MD разом із кодом.
- Приватні авторські артефакти не додавати в Git.

## 1. Домен diff і публікація

- [x] RED: tests/generation/test_rewrite_diff.py — round-trip, вставки, повтори, Unicode/CRLF, злиття, підмножина/порожній вибір, перевищення меж і підроблена пропозиція.
- [x] Реалізувати src/storygen/rewrite_diff.py: build_rewrite_diff(original,candidate), apply_rewrite_diff(original,proposal), локальні попередження.
- [x] Адаптувати src/storygen/copyediting.py, generation/copyedit_review.py та storage/copyedit_store.py до v1/v2 через спільні helpers без storage→generation.
- [x] GREEN: нові тести й tests/generation/test_copyedit_review.py; CAS/stale/ABA для v2.

## 2. Новий режим і провайдер

- [x] RED: stage diff чекає на автора навіть при auto; потрібна тільки чернетка; немає response_format; prompt edit/diff/1; reasoning effort і конфлікти.
- [x] ProviderSettings.venice_reasoning_effort; RoleSettings.edit_mode=diff; PromptContract mode=diff; builtin rewrite_editor_uk_v1.
- [x] Оновити context/prompts/stages/requests/snapshots; зберігати сирий кандидат і незмінний v2.
- [x] GREEN: generation/provider/prompt/dependency tests; старі режими незмінні.

## 3. Окрема класифікація

- [x] RED: optional профіль, queued classify, fingerprint/власність, повне покриття індексів, помилка/відмова/скасування, відсутність публікації й повторів.
- [x] Додати ClassificationSettings до editor role, RunRequest mode=classify з proposal ID/fingerprint.
- [x] src/storygen/generation/edit_classification.py: build_context/readiness/parse; окремий StageAttempt через штатний gateway/accounting/чергу.
- [x] API classify enqueue; preview повертає поради зі спроб, а не змінює parent proposal або рішення.
- [x] GREEN: worker/readiness/API/budget/failure tests, без модельних витрат.

## 4. Інтерфейс і документація

- [x] RED: browser/node regression вибір за замовчуванням порожній для v2, безпечний контекст, preview вибраного тексту, ручна класифікація не скидає вибір, dirty/async захист.
- [x] copyedits.js: контекст, category advisory, default-none, вибраний preview із серверної відповіді, classify button/status.
- [x] settings.js: diff mode, mandatory review hint, effort, optional classifier JSON з прикладом; без автоматичної зміни профілів.
- [x] SPEC.MD + docs/editor-review.md + журнал виконання; точний опис v2/API/станів/сумісності/обмежень.

## 5. Перевірки й review

- [x] Targeted pytest + JS regression; один повний suite в унікальному basetemp.
- [x] Один механічний UI detector; синтетична браузерна перевірка, якщо доступна, без робочих даних/платних API.
- [x] Незалежний review через requesting-code-review; виправити істотні знахідки й повторити потрібні тести.
- [x] git diff --check, журнал evidence, локальний коміт змін коду+SPEC разом; не push/PR без запиту.

## Рішення

- Авторський вибір за замовчуванням порожній для нового режиму: виявлені модельні підміни не мають бути неявно прийняті.
- Зміни чисел/заперечень у ручному diff — попередження, не послаблення чинних guards модельних patches.
- Погоджена класифікація за окремою кнопкою за бажанням; профіль не заповнюється прихованою платною моделлю.

## Підсумок виконання 21.10.2026

Усі кроки реалізовано в поточній гілці. RED→GREEN перевірено для домену, режиму, класифікації та UI; остання UI-регресія перевіряє збереження попереджень вибраного тексту й очищення між сценами. Фінальний offline suite: **622 passed, 1 skipped, 88.33s**, artifacts/rewrite-final.log. Незалежне рев’ю завершено без невиправлених Critical/Important зауважень; знайдені відмови content_filter/текстова відмова й категорії output_limit/budget/configuration виправлено.

Один UI detector: 20 advisory зауважень до наявних стилів; у нових рядках стилів знахідок немає. У браузері на окремому синтетичному сервері перевірено порожній початковий вибір, preview підмножини, окрему queued-класифікацію без скидання прапорців і публікацію лише вибраних змін. Помилок консолі немає; screenshot: artifacts/rewrite-browser-2026-10-21/review.png. Тимчасовий сервер і вкладку завершено, робочий сервер не змінювався. Платних викликів і змін робочих профілів у реалізації немає. Код і SPEC.MD оформлюються разом локальним комітом; публікація не виконується.
