# Reviewing and selecting memory

Open a scene and choose **Memory**. Instead of JSON, the default is a table view: the text of each entry, its category, and the source scene. Technical IDs are hidden; **Show evidence** opens the quote from the prose. The source scene filter initially shows entries from the current scene; select another scene or All scenes to see inherited entries. Search and the scene and category filters do not change the selection of hidden rows.

Clear **Forward** next to entries you do not need and press **Save**. A choice made on scene 5 applies from scene 6 onward, including inherited facts, without deleting them from the journal or rebuilding memory from scratch. In a later scene you can tick the box again; earlier scenes keep their own choice. If the same entry is updated, it stays hidden until you enable it explicitly.

Only the entry in the literary memory block for the planner, the writer and the full literary edit is switched off. It is not deleted from your plan, canon, prose or the tail of the previous scene. The memory model keeps the full catalog for the journal; the Evaluator works from its own primary sources.

Finished texts are not rewritten automatically. Dependent tasks, drafts and prose of later scenes may become stale: review and accept them explicitly, or regenerate. The memory journal itself does not become stale because of the checkboxes. Restoring the exact earlier selection restores freshness under the usual dependency rules.

Stale memory is shown read-only; refresh memory before saving its checkboxes. If another tab causes a conflict, your changes stay in the form and are not applied; **Refresh table** lets you discard the unsaved selection and reload current data. Unsaved changes block generation, and leaving for other material asks you to confirm discarding them.

**JSON for advanced editing** returns the previous journal editor with all its quote/prefix checks. Checkboxes are not part of the JSON; they are a separate author setting. A core state slot (`slot`) can be set in the JSON only for the protagonist; a `resolves_claim_id` link must point to an entry already in the journal, and the application itself moves it to the internal ID that entry receives. Historical versions are browsed through history as before. Fully regenerating an entry with a new internal ID creates a new entry with the default enabled checkbox; the system never carries a choice over to similar text by guesswork.

## Evidence in memory entries

Memory is updated only in evidence mode (`evidence_delta`, format v4, labelled "Evidence-based memory operations v4"); the legacy "Full snapshot" mode is gone, and a role saved with it automatically works in evidence mode. The model does not rewrite quotes. For the protagonist it must decide every core state slot (clothing, carried, location, body, company): unchanged, changed with evidence, unknown with a reason, or "introduced" for an author entry that the prose shows to the reader for the first time. For every active thread it must say whether the thread stays open or is closed by evidence of its resolution; a character's absence from the scene never closes a thread. When the plan's `Початок:` line shows a new day, the model receives a separate notice. Everything else is grouped operations: add only for facts and timeline, add, update and retire for other states, and add for new threads. Each operation names 1 to 3 prose fragment IDs (`evidence_ids`). The application takes the verbatim quotes from the prose itself: the first fragment becomes the main quote, and the rest (up to two) become supporting quotes.

In the memory table, **Show evidence** opens the main quote with the supporting quotes below it, in the same order. If there are none, only the main quote is shown.

For models that support response schemas, choose the `json_schema` response mode: the application builds a schema for each request (allowed fragment IDs, active entries available for update, scene characters), which rules out most format errors.

## Protagonist core state in the writer context

The memory block for the planner, the writer and the full literary edit starts with a **ЯДРО СТАНУ — <protagonist name>** (core state) section (if the protagonist's card has no name, **ЯДРО СТАНУ — протагоніст**). It lists the current slot values in a fixed order: clothing, carried, location, body, company. Empty slots are not shown, and older stories have no such section until a scene's memory is regenerated. The core is shown even in a scene where the protagonist is not in the cast: their state carries over unchanged. A slot value is not repeated under current states. The **Forward** checkbox applies to core entries the same way as to other entries. If you hid a slot value and the model later marks it unknown, the value moves to current states still hidden (in the memory table its checkbox is cleared) until you explicitly enable that state itself.

**Closing threads.** A closed thread leaves the open threads, and its resolution becomes an ordinary fact; the closure is not repeated in the timeline. Closures made before format v4 stay in the timeline as before. If you hid a thread, its resolution is hidden too (in the memory table the resolution's checkbox is cleared) until you explicitly enable the thread itself or the resolution fact itself.

**Unknown to the reader.** An author entry without a quote is a truth of the story world that the reader has not seen yet. The writer receives it marked "(читачеві невідомо: якщо знадобиться, введи в тексті як нове)" (unknown to the reader: if needed, introduce it in the text as new) and must introduce it as new information. Once the prose shows it, the memory stage marks the slot as "introduced" and the mark disappears. If the model instead marks such a slot unknown, the entry moves to current states and keeps the mark.

**Day change.** A new day is detected from the `Початок:` line in the scene plan (`D.M.Y, H:M` or `день N, H:M`). Different spellings of the same date (`1.3.24`, `01.03.2024`, `1.3.2024`) are one day. The memory model then decides separately whether clothing, carried items and body state still hold or marks them unknown with a reason. Without this line there is no signal, and the values stay current until the prose changes them.

## Confirming the core

On the **Memory** tab, below the table buttons, there is a **Protagonist core and threads** panel. It compares this scene's memory with the memory it was built from: for each core slot it shows "was" and "now", for an unknown value the model's reason, and for a closed thread its resolution. The **Changes** group is expanded; the **Unchanged** group (and threads that stay open) is collapsed. The top line shows the state: "Not confirmed" or "Confirmed" with the time. In the first scene or an older story without a core, the panel shows "The core is not filled in yet" and only the threads.

![Core confirmation panel, neutral example](../images/core-review-desktop.png)

Row actions:

- **Accept** keeps the model's decision (and removes your edit of this row, if there was one).
- **Keep previous** restores the value of the previous scene or keeps the thread open. It is available only for versions generated by the memory model: a manually saved version has no model answer, so the button is disabled with an explanation.
- **Write in…** opens the entry panel: enter a value (for a thread, its resolution), choose the quote scene and a fragment of its prose (search narrows the list), or select **No quote**. An entry without a quote becomes "unknown to the reader": the writer receives it with that mark. For a thread that is already closed in a version without a model answer, Write in… is not offered.

**Apply** and **Cancel** change only the panel's draft; nothing is sent to the server. **Confirm** without edits only marks the current memory as confirmed: it does not change the journal and does not make the memory of later scenes outdated. **Confirm with edits (N)** creates a new memory version with your edits and confirms it at once; the memory of later scenes then becomes outdated under the usual rules.

An unsaved core draft is protected like unsaved text: **Refresh table**, choosing another scene or material, or closing the page asks first whether to discard it. If the scene memory has changed in the meantime (for example in another tab), the panel reloads and the draft is discarded with a notice. If a confirmation fails because of such a change, the panel shows the reason and reloads; check the state and repeat if needed.

Edits on an outdated scene memory (one not built from the current memory of the previous scene) are rejected: regenerate this scene's memory first. Confirming it without edits still works.

Automatic mode does not wait for confirmation. Before running a scene or the remaining scenes, the confirmation window shows how many scenes have an unconfirmed core; this is information only and does not block the run.

![Core confirmation panel on a phone, neutral example](../images/core-review-mobile.png)

## If a memory run fails

The run status shows the full list of response-format violations (up to 50 items, then "N more"). Each item is an operation label (for example `facts.add, element 2`, `Operation 3` or `Response`) plus a code. Texts and record IDs never appear in the list.

- `evidence_unknown` - evidence not found in the source: the fragment ID is not in the current prose.
- `evidence_count` - invalid number of evidence quotes: 1 to 3 distinct IDs are required.
- `add_limit` - add limit exceeded: at most three new entries per category.
- `ops_limit` - operation limit exceeded: at most 12 elements per response.
- `target_unknown` - unknown target: the entry to update or retire is not an active entry of that category.
- `target_meta` - (v2 format only) an update or retire changed the claim's category or scope.
- `target_twice` - the same entry is changed twice in one response.
- `scope_unknown` - unknown record scope (a character who is not in the scene).
- `schema` - the response does not match the schema: required keys are missing, extra fields are present, and so on.
- `wire_version` - unsupported format version: the response does not match the format the prompt asks for.

Most often the `json_schema` mode or simply running again helps; if a code keeps repeating, review your custom prompt.

## Custom memory prompt: moving to v4

Custom prompts saved with contract `/2` or `/3` no longer run: they do not ask for the mandatory core state and thread decisions, so runs and role saves stop with the explanation "Incompatible prompt: required memory/evidence_delta/4". For such a prompt the memory role settings show the checkbox **Move the custom prompt to format v4**. First rewrite the text so that it asks for format v4 (the `core` and `threads` sections together with the operation groups), then tick the checkbox and save: the prompt is stored with contract `/4`. Without the rewritten text the model will answer in the old format and the run will fail with `wire_version` or `schema`. Clearing the custom prompt returns the built-in v4 prompt.
