# Fact change: one fact, everywhere in the book

A fact of the world changes, and it lives in many places at once: the plan, the brief, the prose, the memory, the character cards and the series bible. Old memory keeps the old fact as a verbatim quote, and later scenes see it as settled. So every place has to change together, with the smallest possible edit.

## 1. The change card

A table "was → becomes" for every dimension of the fact, plus the reason in one line. For example:

| Dimension | Was | Becomes |
|---|---|---|
| City | Вроцлав | Познань |
| Venue | Czasoprzestrzeń | MTP (Międzynarodowe Targi Poznańskie) |
| Event | Beer Geek Madness | Poznańskie Targi Piwne 2025 |
| Time | квітень | листопад |
| Format | All You Can Drink | commercial: every beer is paid for |

A dimension the author did not give and the text needs: one question, one at a time.

**Renaming a character** starts with the author. The plan's participants are checked against the cards, so a plan with the new name breaks before the card is renamed. First ask the author to rename the card on the «Персонажі» page (old name into «Інше ім'я:») and wait for «готово». Only then edit plans and texts.

## 2. Checking the facts

- Search the web for the real details of the new fact that the text needs: how people pay, glass and deposit, what the hall looks like and how big it is, how to get there, typical prices, duration. Every detail gets a link.
- An invented part (for example "the 2025 festival did take place") is the author's decision, not something to check.
- Show a table "detail — source" for the author to confirm. A detail without a source becomes either one question or a "my decision" row in the table.
- **No search tools** (the client has no web access): say so in one line, and ask only what the text needs. Never invent details. If the author already said that only the name changes, ask nothing.

## 3. Finding the consequences

Read everything, in full: follow `next_offset` until it is null.
- the plan preamble (`get_story`, field `plan_preamble`);
- the plan of every scene: `get_scene_text(scene_id, 'plan')`;
- the text of every scene: `get_scene_text(scene_id, 'prose')`, and `get_scene_text(scene_id, 'draft')` when the draft differs from the prose (see step 3 of §6);
- the memory of every scene: `get_scene_text(scene_id, 'memory')`;
- the character cards: `get_scene_context(scene_id)`;
- the series bible articles, if `series` is not null.

Match the old fact by its stem, in every case form and every derived word («Одеса», «Одесі», «одеський»).

For every place, one row: scene, quote, kind, proposal. Kinds:
- **direct replacement:** the name itself (Вроцлав → Познань);
- **derived thought:** a sentence that no longer fits (September plus "half a year" in November; a brick vault in an exhibition hall; a commuter train to the wrong city);
- **everyday detail:** how the new place or format works (tasting sets, queues, how beer is poured).

In an `obscura` story you may also offer the Auditor (Ревізор) after the edits are in, as an extra check — never instead of this search.

**The editor's mode** (`chat` story only), read now, before the table: it decides whether the chat writes the text or the author makes the edits by hand (§4, §6). Call `get_stage_task(first_affected_scene_id, 'edit')` once: it only reads and needs no consent. Its `result_format` follows the editor's mode in the story's settings and is the same for every scene. If the server refuses that task (for example, the scene's brief link is unchecked), read the mode from `get_settings(story_id)` instead: `roles.editor.edit_mode` (no editor role configured: the default, `prose`). Do not stop over this refusal. In an `obscura` story skip this: the text edits are made by hand anyway (§9).

## 4. The table of changes

Show one table for consent, naming every affected scene by its title from `get_story`:
- a minimal edit for every place;
- a deeper change as a separate row marked «на твій вибір» (your choice);
- the plan preamble, if it holds the fact (`update_plan_preamble`);
- character cards: ready-made edits for the author to make on the «Персонажі» page, because the server does not change cards;
- the series bible, as its own row (§8);
- **follow-up writes**, as a row of the table itself, not a list or note below it, even when you also show the first scene: briefs (and drafts) saved again for scenes whose previous scene changed, and new memory for later scenes whose memory carry fails (§7). In an `obscura` story, note that these are paid runs with their own consent. For example, a row «Наслідкові записи | — | сцена 2: завдання й чернетка зберігаються знову після нової пам'яті сцени 1».

Before consent, warn: unreviewed point edits of the editor in the affected scenes will become invalid.

In an `obscura` story, or with an editor in `patches`/`diff`, the text edits are made by hand (§9). End the table message by asking the author to say «готово» once those edits are in, and say that until then the memory of the affected scenes is stale.

Show any open question in the same message as the table; do not hold the table back.

## 5. The first scene

Show the first affected scene before anything is saved: fragments "was → becomes" for every changed sentence. You may show it together with the table. The author's «ок» then covers both the table and the approach; until it, nothing is written. A correction from the author to the approach applies to all remaining scenes.

## 6. Applying in `chat` mode

Go by the editor's mode you read in §3:
- `prose`: go on below.
- `patches` or `diff`: an empty editor pass is refused, so write no text. Give the replacement table (§9) instead, and finish with §10.

If the plan preamble changes, write it first (§8), before the first scene's chain: a preamble change makes earlier non-current versions stale.

Then scene after scene, in book order. A scene's entities form a chain: plan → brief → draft → prose → memory, each built from the one before. Start with **the first entity whose content needs the edit**; rebuild every entity below it, and leave those above it alone:
- the old fact is in the plan: plan → brief → draft → prose → memory;
- plan and brief are fine, the fact is in the text: draft → prose → memory;
- the text was already fixed (for example by the author by hand), only the memory is old: memory only.

How each entity is built:

1. **Plan:** `get_scene_text(scene_id, 'plan')` → `update_scene(story_id, scene_id, expected_revision=<revision from get_story>, plan_markdown, plan_version_id)` with the minimal edit: change only the words of the fact; every other line stays as it is.
2. **Brief:** `get_stage_task(scene_id, 'brief')` → the previous brief (`get_scene_text(scene_id, 'brief')`) with the minimal edit → `save_stage_result(scene_id, 'brief', task_fingerprint, result)`.
3. **Draft:** `get_scene_context(scene_id)` (gives `revision` and `context_fingerprint`) and `get_scene_text(scene_id, 'draft')` in full (gives `version_id`) → `save_draft(scene_id, text, expected_revision=<revision>, context_fingerprint, draft_version_id=<version_id>)`.
   - The base is the current prose (`get_scene_text(scene_id, 'prose')`): that is what readers and the export see.
   - Change only the agreed places. Every other sentence stays byte for byte.
   - If the draft head is the author's own text (no `external_origin`) and differs from the prose, the server does not say which is newer: ask the author which one to use.
4. **Prose:** only the edit stage changes prose. `get_stage_task(scene_id, 'edit')` → return prose identical to the draft you just saved, with no copy-editing → `save_stage_result(scene_id, 'edit', task_fingerprint, result)`.
5. **Memory:** `get_stage_task(scene_id, 'memory')` (read all of it with `offset`, `max_chars` at most 20000) → the scene's memory built again from the current prose, as a first memory stage (`add` only; the scene's own claims are not in the material). Keep everything the previous memory said (`get_scene_text(scene_id, 'memory')`), with the old fact replaced by the new one and every other text and quote word for word. For `core`, repeat the decisions the previous memory shows: a slot with a `character_states` claim there keeps it (`changed`, the same text and quote, the old fact replaced); any other slot keeps the state it had before the scene. Change a decision only where the old fact is replaced or the task's own rules require it, and mark that change as your decision → `save_stage_result(scene_id, 'memory', task_fingerprint, result)`. The claim ids will change when the prose changed: they depend on the prose version. With unchanged prose and the same claims they stay the same (§7).

After each memory save, call `get_story` again:
- «Пам'ять переноситься» (memory is being carried): read again a little later.
- A later scene with memory `carry_failed`: see §7. If that scene is itself in the table, the memory step of its own chain covers it; do not save its memory separately first.

After each scene, one progress line, for example:

> Сцена 2 з 7: план → завдання → чернетка → проза → пам'ять збережено. Далі сцена 3.

## 7. Dependence between scenes

A scene's brief depends on the previous scene's memory. After new memory for scene k, the server marks the brief and prose of scene k+1 as unchecked, even when their content is right.

- **Scene k+1 has its own edits:** its chain starts no lower than the brief. Save the brief again, unchanged if its content is fine (the server accepts an identical brief as a new version); without it the editor refuses «завдання не перевірено проти плану й пам'яті попередньої сцени». Then save the draft again too, even if identical; otherwise the editor answers «Контекст містить застарілий матеріал».
- **Scene k+1 has no edits:** do not rewrite it. After all rows of the table, offer the Auditor for the whole book: `start_run(story_id, action='audit')` without `scene_id` and without `confirm`, show the preview and its cost, and only after the author's yes call it again with `confirm=true`; watch it with `get_run(run_id)`. The Auditor writes nothing:
  - `valid` clears the check by itself;
  - `discrepancy` means the scene needs an edit: offer it as a new table row (usually new memory, step 5; changing prose only with the author's consent).

  If the preview says «Роль не налаштовано: Ревізор», or the author does not want to pay, the author confirms such scenes with «Я перевірив сам» for the brief and prose links in the «Узгодженість сцени» panel. Do not rebuild an identical chain yourself unless the author asks: it builds new memory and pushes the same check onto scene k+2 and on to the end of the book.
- **Memory carry:** Obscura carries the new memory of scene k into later scenes by itself, without a model or cost; do not rebuild the book's memory. A scene whose carry failed (`carry_failed`: its events referred to claims of scene k whose ids changed) blocks every scene after it, and neither the Auditor nor the author's decision clears it. If the scene is in the table, the memory step of its own chain covers this. Otherwise give it new memory (step 5) even without a table row: in `chat` mode it is free and covered by the agreed table. In an `obscura` story it is a paid run: offer `start_run(story_id, action='memory', scene_id)` for that scene, preview without `confirm`, show readiness, models and cost, then `confirm=true` only after the author's yes; watch with `get_run(run_id)` and call `get_story` again after the run. Its prose did not change, so the same texts and quotes keep the same claim ids, and the carry goes on. The chain of new memories continues only where a scene's memory really changes.

## 8. Plan preamble, cards, series bible

- **Preamble:** `update_plan_preamble(story_id, text, plan_version_id)` on top of what you read, as a row of the table. Write it before the first scene's chain, never between a scene's draft and its edit.
- **Character cards:** the server does not change them. Give the author ready edits for the «Персонажі» page.
- **Series bible:** a separate story with its own mode and editor. Its articles go through the same chain from the first entity that needs the edit, under the rules of the bible's mode, after the author agrees to that separate row.

## 9. `obscura` mode, or an editor in `patches`/`diff`

- Write only what this mode allows: the scene plan (`update_scene`) and the plan preamble (`update_plan_preamble`), after consent to the table. A changed plan puts the affected scenes into «чекає перевірки».
- Never call `save_draft` or `save_stage_result` in an `obscura` story, and never start a paid run without its own preview and consent.
- Give the text edits as a replacement table «сцена — знайти — замінити на», for the author to make in Obscura. Say that automatic edits by Obscura's models will come in a later package.
- End the table by asking the author to say «готово» when the edits are in. Say that until then the memory of the affected scenes is stale.

## 10. After the manual edits

Manual edits leave the old fact in memory. When the author says «готово»:
- **`chat` mode with `patches`/`diff`:** the memory stage of every affected scene in order, as step 5 of §6, without separate consent: it is part of the agreed table.
- **`obscura` mode:** offer `start_run(story_id, action='memory', scene_id)` for every affected scene in order: preview without `confirm`, show readiness, models and cost, then `confirm=true` only after the author's yes; watch with `get_run(run_id)`. After each run, call `get_story` again: a later scene with memory `carry_failed` gets the same offer, with its own preview and consent (§7).
- **Both:** offer the Auditor for the whole book (§7) and give the summary, with the scenes waiting for a check of their links.
