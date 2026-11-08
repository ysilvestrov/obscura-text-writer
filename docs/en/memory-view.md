# Reviewing and selecting memory

Open a scene and choose **Memory**. Instead of JSON, the default is a table view: the text of each entry, its category, and the source scene. Technical IDs are hidden; **Show evidence** opens the quote from the prose. The source scene filter initially shows entries from the current scene; select another scene or All scenes to see inherited entries. Search and the scene and category filters do not change the selection of hidden rows.

Clear **Forward** next to entries you do not need and press **Save**. A choice made on scene 5 applies from scene 6 onward, including inherited facts, without deleting them from the journal or rebuilding memory from scratch. In a later scene you can tick the box again; earlier scenes keep their own choice. If the same entry is updated, it stays hidden until you enable it explicitly.

Only the entry in the literary memory block for the planner, the writer and the full literary edit is switched off. It is not deleted from your plan, canon, prose or the tail of the previous scene. The memory model keeps the full catalog for the journal; the Evaluator works from its own primary sources.

Finished texts are not rewritten automatically. Dependent tasks, drafts and prose of later scenes may become stale: review and accept them explicitly, or regenerate. The memory journal itself does not become stale because of the checkboxes. Restoring the exact earlier selection restores freshness under the usual dependency rules.

Stale memory is shown read-only; refresh memory before saving its checkboxes. If another tab causes a conflict, your changes stay in the form and are not applied; **Refresh table** lets you discard the unsaved selection and reload current data. Unsaved changes block generation, and leaving for other material asks you to confirm discarding them.

**JSON for advanced editing** returns the previous journal editor with all its quote/prefix checks. Checkboxes are not part of the JSON; they are a separate author setting. Historical versions are browsed through history as before. Fully regenerating an entry with a new internal ID creates a new entry with the default enabled checkbox; the system never carries a choice over to similar text by guesswork.

## Evidence in memory entries

In evidence mode (`evidence_delta`, format v3, labelled "Evidence-based memory operations v3") the model does not rewrite quotes. It returns grouped operations: add only for facts and timeline; add, update and retire for character states and open threads. Each operation names 1 to 3 prose fragment IDs (`evidence_ids`). The application takes the verbatim quotes from the prose itself: the first fragment becomes the main quote, and the rest (up to two) become supporting quotes.

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

## Custom memory prompt: v2 and v3

A custom prompt saved with contract `/2` keeps working as format v2 (one quote, `evidence_id`). The upgrade checkbox appears only when a saved custom `/2` memory prompt is assigned to the memory role in `evidence_delta` mode. To move to v3, first rewrite the prompt text so that it asks for the grouped v3 format, then tick **Move the custom prompt to format v3** in the memory role settings and save: the prompt is stored with contract `/3`. Without the rewritten text the model will answer in the old format and the run will fail with `wire_version`. Clearing the custom prompt returns the built-in v3 prompt.
