# Memory

Once prose is accepted, the memory model records what happened in the scene: facts, character states, open plot lines and the timeline. Every entry rests on a quotation from the prose. Later scenes receive this memory in the planner, writer and editor context.

## Viewing

Open a scene → **Memory**. The table shows the text of each entry, its category and the source scene. **Show evidence** opens the quotation from the prose. The source scene filter first shows entries of the current scene; choose another scene or **All scenes** to see inherited entries.

## What to pass forward

Clear **Share forward** next to entries you do not need and press **Save**. A choice made in scene 5 applies from scene 6, inherited facts included; the entry itself stays in the journal. In a later scene you can tick it again.

Only the entry in the memory block for the models is switched off, not the fact in your outline or prose. Finished texts are not rewritten automatically, but dependent materials of later scenes may become stale: review and accept them or generate them again.

## Protagonist core state

For the protagonist, memory keeps a core state: clothing, items carried, location, physical state and who they are with. The writer's memory block starts with these values. When a change of day is visible from the `Start:` (or `Початок:`) line of the scene outline (`D.M.Y, H:M` or `day N, H:M`), the model decides separately what carries over to the new day. The planner, the writer and a chat over MCP also get a "DAY CHANGED" note, and the standard prompts ask them not to contradict the core, to show a change of clothes or any other change explicitly, and not to carry yesterday's clothing over silently. Custom prompts do not get these rules, but they still see the note. If you change the day in the `Start:` line of the hero's previous scene, the brief and the draft of the next scene become out of date; your own manual texts do not.

You can check the model's core decisions in the panel above the table: **Accept**, **Keep previous** or **Write in…** your own value with or without a quotation. **Keep previous** is available only for versions produced by the memory model. Edits to outdated memory are rejected: regenerate this scene's memory first. **Apply** and **Cancel** change only the panel draft. **Confirm** without edits only marks the memory as checked, while **Confirm with edits (N)** creates a new memory version; memory of later scenes then becomes stale. An unsaved core draft is protected like unsaved text.

An author entry without a quotation is a truth of the world the reader has not seen yet. The writer gets it marked "unknown to the reader" and has to introduce it in the text as new.

## When memory does not fit

While the request fits the role limits, memory is passed in full. Otherwise the application selects the most important part and warns you: the protagonist core always in full, then recent protagonist states, open lines involving the scene participants, other participants' states, facts, the timeline of the last 20 scenes and "atmosphere". If even the core does not fit, the request is not sent.

The **Type** column guides the selection: **Auto**, **Core** (always shown) or **Atmosphere** (only within a small share). The choice is saved at once and applies to the whole story.

## Timeline summaries

A selected request leaves out the timeline older than 20 scenes. To keep the model aware of what happened earlier, create a summary in the **Timeline summaries** section of the memory panel. A block is a part of the book, or, in a book without parts, every 10 scenes (1–10, 11–20…). The **Create summary** button is highlighted once the first scene of the block leaves the timeline window. The summary is written by the Memory role model: you see the model and the token estimate before the run, and the call is paid. You can correct the finished text with **Edit**.

A summary is used only when memory does not fit: it replaces all timeline entries of its block with one line. If the prose or memory of a scene in the block changes, or the block's scenes change, the summary is marked "stale" and is not sent until you rebuild it.

## Memory merge

In a book with [arcs](book-structure.md) each arc keeps its own memory. Where arcs come together — in a meeting scene, in the first scene of the next part, in the first scene of an arc after several arcs have ended, and at the end of the book — the memory has to be merged. What changed in one arc only carries over without questions, and so does the same result in both arcs. When the arcs changed the same record differently (say, Anna put on a jacket in one and a raincoat in the other), that is a conflict, and you decide it.

The **Memory merge** section in the memory tab of such a scene shows the arcs that meet and one row per conflict: the value of each arc and **Own value**. Choose a value in every row and press **Confirm merge**. If the book or the arc memory changed while you were choosing, the app warns you, reads the merge again and keeps your choice wherever the conflict is the same.

Until the merge is confirmed, writing this scene does not start: a run stops before it, and an **Open memory merge** button appears next to the run status. After confirming, press **Continue** — the run goes on from the same scene.

If the memory of one of the arcs changes later, the merge becomes out of date and has to be confirmed again; decisions for the same conflicts with the same values are filled in by themselves and marked as carried over. The end-of-book merge appears in the memory tab of the last scene: it does not stop writing, but the summary of the last part needs it.

## Confirming earlier memory

If updating a scene's memory relies on an old journal of the previous scene, the application asks for confirmation. The dialog shows the memory scene, the number of new versions and of changed texts; **Cancel** does not start the model. Confirmation keeps the old sources and quotations; it does not verify the facts. If the sources change again, confirm again.

## Advanced editing

**JSON for advanced editing** opens the memory journal as JSON with all quotation checks. Use it only when the table is not enough.

Stale memory is shown read-only: update it first. If memory changed in another tab, your choice stays in the form, and **Refresh table** lets you reread the current data explicitly.
