# Reviewing and selecting memory

Open a scene and choose **Memory**. Instead of JSON, the default is a table view: the text of each entry, its category, and the source scene. Technical IDs are hidden; **Show evidence** opens the quote from the prose. The source scene filter initially shows entries from the current scene; select another scene or All scenes to see inherited entries. Search and the scene and category filters do not change the selection of hidden rows.

Clear **Forward** next to entries you do not need and press **Save**. A choice made on scene 5 applies from scene 6 onward, including inherited facts, without deleting them from the journal or rebuilding memory from scratch. In a later scene you can tick the box again; earlier scenes keep their own choice. If the same entry is updated, it stays hidden until you enable it explicitly.

Only the entry in the literary memory block for the planner, the writer and the full literary edit is switched off. It is not deleted from your plan, canon, prose or the tail of the previous scene. The memory model keeps the full catalog for the journal; the Evaluator works from its own primary sources.

Finished texts are not rewritten automatically. Dependent tasks, drafts and prose of later scenes may become stale: review and accept them explicitly, or regenerate. The memory journal itself does not become stale because of the checkboxes. Restoring the exact earlier selection restores freshness under the usual dependency rules.

Stale memory is shown read-only; refresh memory before saving its checkboxes. If another tab causes a conflict, your changes stay in the form and are not applied; **Refresh table** lets you discard the unsaved selection and reload current data. Unsaved changes block generation, and leaving for other material asks you to confirm discarding them.

**JSON for advanced editing** returns the previous journal editor with all its quote/prefix checks. Checkboxes are not part of the JSON; they are a separate author setting. Historical versions are browsed through history as before. Fully regenerating an entry with a new internal ID creates a new entry with the default enabled checkbox; the system never carries a choice over to similar text by guesswork.

## Evidence in memory entries

Memory is updated only in evidence mode (`evidence_delta`, format v4, labelled "Evidence-based memory operations v4"); the legacy "Full snapshot" mode is gone, and a role saved with it automatically works in evidence mode. The model does not rewrite quotes. For the protagonist it must decide every core state slot (clothing, carried, location, body, company): unchanged, changed with evidence, unknown with a reason, or "introduced" for an author entry that the prose shows to the reader for the first time. For every active thread it must say whether the thread stays open or is closed by evidence of its resolution; a character's absence from the scene never closes a thread. When the plan's `Початок:` line shows a new day, the model receives a separate notice. Everything else is grouped operations: add only for facts and timeline, add, update and retire for other states, and add for new threads. Each operation names 1 to 3 prose fragment IDs (`evidence_ids`). The application takes the verbatim quotes from the prose itself: the first fragment becomes the main quote, and the rest (up to two) become supporting quotes.

In the memory table, **Show evidence** opens the main quote with the supporting quotes below it, in the same order. If there are none, only the main quote is shown.

For models that support response schemas, choose the `json_schema` response mode: the application builds a schema for each request (allowed fragment IDs, active entries available for update, scene characters), which rules out most format errors.

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
