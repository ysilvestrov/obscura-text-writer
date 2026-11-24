# План: пропозиція картки для довгої книжки

Специфікація: [2026-11-24-publication-suggest-long-book-design.md](../../specs/2026-11/2026-11-24-publication-suggest-long-book-design.md), затверджено 2026-11-24. Один PR (оцінка M). Ядро — задачі 1–3, обв'язка — задачі 4–6. Виконання inline (`executing-plans`), кожна задача з тестом перед кодом.

## Ядро

1. **Ідея в знімку й штампі.** `plan_sections.preamble_text(text)`; `PublicationSnapshot.idea`; `source_stamp` додає `idea_sha256` при непорожній ідеї; `read_plan_preamble` і `context.py` (`global_notes`) беруть ту саму функцію. Тести: штамп без вступу незмінний; зі вступом — ключ є; зміна вступу робить пропозицію застарілою при Save (R16-SUGGEST-S08).
2. **Підбір сцен і промпт v2.** `build_publication_context(repo, story_id, expected_selection=None, enforce=False)`: тіло з `idea`, `coverage`, двоетапний пошук `k` (символи двійково, токени вниз), `ContextOverflow` для `k=1`, `fragments['publication_selection']` з `key` і `bound_by`, `input_refs` з `source_plan`, `prompt_version` 3; `publication_metadata_{uk,en}_v2.txt` і `language.PROMPTS`. Тести: повний режим з ідеєю; неповний (`k` найбільше, `k+1` не вміщається, цілі сцени); без ідеї; навіть перша сцена не вміщається; немонотонна оцінка (профіль із вузьким діапазоном).
3. **Прив'язка відбору.** `RunRequest.expected_selection` (лише для `publication_suggest`); `readiness(repo, request, enforce_selection=True)` повертає `selection` і попередження; маршрут готовності UI — `enforce_selection=False`; worker перед dispatch порівнює ключ. `stages.py` зберігає `publication_selection`; `suggestions_state` віддає `selection`. Тести: невідповідний/відсутній ключ при неповному відборі — відмова без запуску й виклику; повний відбір без ключа працює; спроба й API несуть `selection`; стара спроба без поля — null.

## Обв'язка

4. **UI.** `#publication-suggestion-selection` під кнопкою, «Прочитано…» в пропозиції, «Відібрано…» в історії, POST /api/runs з `expected_selection`; ключі i18n uk/en. Playwright у `tests/web/test_publication_ui.py`.
5. **MCP.** `start_run` для `publication_suggest`: перегляд повертає `selection`; `confirm` передає `expected_selection` зі свіжої готовності.
6. **Документи.** SPEC.MD R16-SUGGEST (текст, S01, S02, техніка, нові S07, S08), traceability, `docs/site/{uk,en}/publication.md` + `check_site.py --rehash publication`, `check_docs.py`; `verify.py` з `C:/tmp/<коротка>` і запис у `docs/STATUS.md`.
