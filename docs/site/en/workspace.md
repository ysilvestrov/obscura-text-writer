# Workspace and scene stages

The story workspace has three parts: the scene list on the left, the scene editor in the middle and the scene sections on the right. On a narrow screen they stack one under another.

If there are many scenes, click the **Scenes** heading with their count: the list collapses, and **Add materials** stays nearby. The current scene and unsaved text are kept.

![Story workspace with the scene list, stages and status row](../../images/site/en/workspace-desktop.png)

## Delete and restore a scene

- In the scene list, the selected scene has a button with a trash icon: **Delete scene**. The app asks for confirmation and moves the scene to the scene trash; the following scenes will then need review.
- Save your text first: with unsaved changes the scene is not deleted and the app tells you why.
- If a run of the story stopped and is waiting for your decision, the app offers to cancel such runs together with deleting or restoring the scene. Text and history are preserved. While a model is working, the scene cannot be deleted: wait for the run to finish or cancel it.
- Accepting a brief or applying point edits finishes the run that was waiting for them, and a new run of the same scene stage cancels the old stopped one.
- To bring a scene back, expand **Scene trash** under the list and click **Restore**. Scenes are never deleted permanently.
- On a narrow screen there is no scene list: pick the scene in the selector and click **Delete scene** under it.

## Top row

- **Characters** opens the character cards on a separate page.
- **Settings** opens the models, writing, evaluator and budget for this story.
- **Add scene** creates a scene right after the open one (at the end of the list if no scene is open) and fills its outline from a template right away. Location, characters, key realisation and emotional focus are carried over from the previous scene's outline; its "End" becomes the "Start" of the new scene, and its "What happens" becomes "Previously". "End", "What happens" and the three "Beats" items stay empty. The number in the heading is the new scene's place in the list; the numbers in the outlines of the following scenes move on. A scene added at the end gets the number after the previous scene's number. In a Ukrainian story the outline labels are Ukrainian. Whatever the previous outline lacks stays empty; you can correct everything in the outline straight away.
- The **☰ Story actions** menu holds everything that concerns the whole story: **Book validation** with the number of invalid scenes ([book validation](#validating-the-book)), **Accept all prose as the author's** (when the prose of at least one scene is unchecked), **Card and publication**, **Export…**, story evaluation and reports (when an evaluator is configured), the budget line and **Rename story**. The menu works from the keyboard; `Escape` closes it.

![Story actions menu](../../images/site/en/story-menu-desktop.png)

## Change the scene order

- Open a scene and press **Move up** or **Move down** in **Scene settings**. Each press moves the scene by one place.
- Save the text first: a scene with unsaved edits does not move.
- After a move the story's texts need review: what the model knows from earlier scenes depends on the order.
- The number in the first line of the outline ("Scene 3: …") becomes the scene's number in the list. Only the number changes; a saved outline gets a new version and the previous one stays in the history. Scenes without a number in the outline (a prologue, an interlude) get no number but keep their place. The same happens when a scene is inserted in the middle, moved to the trash or restored.
- In a story with parts and arcs these buttons cannot move a scene into another arc: use the [book structure](book-structure.md).

## Scene stages

The **Outline → Brief → Draft → Editing → Prose → Memory** tabs show the scene materials and their state: "No material", "Material available", "Needs updating". A tab only opens the material; the primary button above the text starts the action.

On the **Outline** tab numbered items ("1.", "2)" and so on) number themselves. Enter at the end of an item starts the next number and shifts the items below; Enter on an empty item removes its number and ends the list. After you insert, delete or drag lines, the list is renumbered from its first item. A blank line separates two lists. The **Renumber** button puts every list in the outline in order, for example after you paste a whole outline. Ctrl+Z first brings back the old numbers, then undoes the edit itself. The scene heading and lines such as "Who takes part:" stay as they are.

The **Brief** tab shows the writer's brief as a form: the objective, numbered beats, constraints and proposed changes. Each beat has its own field; the buttons next to it move the beat up or down, insert a new one before it or remove it, and **Add beat** adds one at the end. The numbers next to the fields are set automatically and are not part of the beat text, so quotes, line breaks and any other text are saved as written. Empty fields are dropped when you save; with no beats **Save** is unavailable. **Advanced JSON** shows the same brief as JSON and **Simple view** brings the form back; unsaved edits are kept. If the JSON is broken, the form explains the error and waits until it is fixed.

![The writer's brief form with the objective, beats and constraints](../../images/site/en/brief-form-desktop.png)

If the planner reports "Significant changes require the author’s decision", the **Brief** tab opens a new proposal with a list of changes. Review it, save your manual edits and press **Accept brief**; **Save** keeps the proposal without accepting it.

Before you press it, the primary button shows the model and the maximum number of calls. Hover over it or reach it with Tab to see details and warnings. If a role is not configured, a button next to it takes you to that role in the settings.

On the **Draft** tab the primary button starts editing: the first time it reads **Save and edit**, and once there is prose it reads **Edit**. To its left, **Use as prose** saves the draft as prose without editing, just as if you copied it into the **Prose** tab. On the **Prose** tab the same place has the **Edit current prose** button.

## Status row

Only the stage tabs and the row with **Save** and the primary action stay pinned at the top. The same place shows why the primary action is unavailable, the mark for text from an external client and the warning that the material changed elsewhere. Below the scene text you see the note about the primary action, the scene status, the run progress and the pause, cancel, continue and repeat buttons. When a run waits for your decision (review, choosing a variant, pause, failure), the pinned row shows a **Decision needed ↓** link that scrolls to the buttons. The run progress takes one line: the state, the models, the cost in dollars (total / last call) and a ⚠ mark when there is a warning. The provider's usage details are in the tooltip on the cost. Click that line to see the plan, warnings and stages, and click again to hide them. A failed run shows its error right away. The text the model is writing right now appears in the **Text the model is writing** block below the scene text: it opens while a stage runs and closes once the stage's text is in. **Run options** sets the limit for the next run. **Run remaining scenes** runs the remaining scenes one after another. The Microsoft Store edition has neither these buttons nor the **Additional actions and automatic mode** block: there, a chat over [MCP](mcp.md) automates several stages or scenes. Pause takes effect between stages; closing the tab does not cancel the work, and cancelling does not guarantee that the provider stops answering at once. Check one scene first, as described in [Your first story](first-story.md).

## Scene status: valid or unchecked

A scene has three links: the brief follows the plan and the memory of earlier scenes, the prose follows the brief, and the scene memory follows its prose. The scene status shows under the scene text and in the scene list:

- **Valid** — all three links hold: Obscura models or a chat made the texts from the current materials, or you approved them.
- **Unchecked** — something was written or changed by hand, or the memory of the previous scene changed, and nobody confirmed that the texts still match.
- **Discrepancy** — the [auditor](#checking-a-scene-with-the-auditor) found a possible mismatch.

A brief, prose or memory becomes outdated only when what it was made from changes: the plan, the memory of the previous scene, the brief or the prose. Changing settings — the narrator, prose language, rating, style, flashbacks or names — marks only drafts as outdated. A brief you wrote or edited yourself does not block the draft, but the scene stays “Unchecked”.

When a brief or prose is unchecked, a panel below the scene text offers **Approve brief** and **Approve match**. Press them once you are sure the brief follows the plan and the prose follows the brief. Approving prose does not make it the author’s text and does not change it. If the scene changed after the panel was shown, Obscura approves nothing, shows an error and refreshes the panel.

For memory and missing memory the panel offers other actions:

- **The memory is not confirmed: the prose changed after it.** If the prose change did not touch the facts, press **Keep the earlier memory**: the scene memory stays, and the next scene no longer asks you to update it because of this change. If the facts changed, press **Create a new memory** — the memory stage runs after a preview and your consent.
- **This scene has no memory yet** — **Create memory** runs the memory stage of this scene.
- **The previous scene “…” has no memory** — the brief and prose of this scene cannot be checked. **Create memory** opens that scene and offers to run its memory stage. If the scene continues a memory merge, the panel only explains what is missing.
- **The memory is being carried over…** — after the previous scene gets a new memory, Obscura updates the memory of later scenes on its own ([carrying memory to later scenes](memory.md#carrying-memory-to-later-scenes)). Until the carry reaches the scene, model runs for it are refused with the explanation “Memory is being carried”, while you can still read and edit the text. The note disappears on its own when the carry ends; if it takes longer than two minutes, refresh the page.
- **The memory was not carried over** — the carry stopped at this scene. **Create a new memory** builds its memory on the new memory of the previous scene, and the carry continues; **Rebuild memory** has a model create the memory of this scene and of all later scenes. Such a memory cannot be kept.
- **The memory carry stopped before this scene** — the carry is paused, ended with an error or was interrupted. **Resume carry** (no cost) or **Cancel carry**: after a cancel, model runs are available, and the scene memory stays built on the old memory of the previous scene.

In full-screen mode the panel is hidden.

## Checking a scene with the auditor

When a scene is “Unchecked” or has a “Discrepancy”, a **Check scene** button appears next to its status. It runs the [auditor](models.md#auditor): the model reads the scene links one by one (brief, prose, memory) and changes no text. First you see which links will be checked, the model, the maximum number of calls and, for a cloud model, the maximum amount in dollars; the check starts only after **Confirm**. The number of calls and the amount are an upper bound while the scene stays unchanged. If the scene changed while the dialog was open, the check does not start and Obscura says “The check plan has changed. Review it again”: press **Check scene** again. The budget limit applies as for other runs.

- If the auditor is at least 90% confident and found no discrepancies, the link holds and the check moves on to the next one.
- Otherwise the check stops, and the panel below the text shows a row “The auditor thinks … may differ …” with the confidence, a list of discrepancies and quotes. The model’s explanations can be inaccurate: it may notice that something is off but name the wrong thing. Reread the scene yourself.
- If everything is fine, press **Approve brief**, **Approve match** or **Keep the earlier memory**; if not, fix the text on the stage tab or press **Create a new memory**. Then press **Continue** to check the remaining links. Continuing without your decision stops at the same discrepancy again without calling the model.
- If the auditor could not check a link, the row explains why. When the input exceeds the auditor’s limit, the **Open auditor settings** button takes you to its settings; raise the limit and run the check again. Such a link cannot be approved.
- A link that cannot be checked without memory (the previous scene has no memory, the memory is being carried over) stops the check without a model call; its actions are described above.

Pause and cancel take effect between calls. If you change the scene during a call, the verdict is not applied and the link is checked again; after three such times in a row the check stops with the error “The scene was changed during the check several times in a row”. A wrong answer from the model stops the check without a verdict; you can repeat it only explicitly. While a link waits for your decision, the **Check scene** button stays visible, but a new check only stops at the same discrepancy: use **Continue**.

## Validating the book

To check the whole book, open the **☰ Story actions → Book validation (N)** menu item, where N is the number of scenes that have at least one “Unchecked”, “Discrepancy” or “Unavailable” link (including a scene with only a brief). When there are no such scenes, the item shows “The book is valid” and is inactive; it is also inactive while another run is going on.

- First you see how many scenes will be checked, the maximum number of auditor calls, its model and the upper bound on the cost: “Cost: up to $X (upper bound)”. A local model has no amount. If the model has no price or the price is out of date, the dialog says “No cost estimate: …”: update the prices in the settings ([call budget](models.md#call-budget)). The check starts only after **Start validation**; **Cancel** starts nothing.
- The auditor goes through the scenes in list order (without the trash), in each one the brief, prose and memory, and calls the model only for unchecked links and those where the input did not fit before. It skips valid scenes.
- At the first discrepancy or unavailable link the check stops, and a **Go to scene N** button appears in the status row. It opens the scene, where the panel below the text shows the discrepancy. Make your decision as for [checking a scene](#checking-a-scene-with-the-auditor) and press **Continue**. The check reads the book from the start again, so if you changed an earlier scene in the meantime, it checks that scene first.
- The scenes, calls and cost are an upper bound only while the book stays unchanged: edits during the check may add work. If the book changed while the dialog was open, Obscura does not start the check and shows “The check plan has changed. Review it again” with a **Review again** button. It shows the new plan, and the check starts only after your new consent.
- While a validation is running or stopped, the menu item shows “Validation in progress: show” or “Validation stopped: show”. It starts nothing; it expands the line of that validation: how many scenes are checked, the calls and the spending. When the line shows another run that is still going on, the item is inactive until that run ends.
- A new book validation cancels the stopped checks of this story (of a scene or of the book), so an old plan is not continued. The dialog does not warn about this.
- Pause, cancel, failure and repeat work the same as for a scene check.

## Editor

Draft and Prose have a formatting toolbar: **B** (`Ctrl+B`), *I* (`Ctrl+I`), undo (`Ctrl+Z`) and redo (`Ctrl+Y`). **Save** creates a new version and does not erase earlier ones. Pasting brings in plain text only. The browser warns you before you leave with unsaved edits.

The editor remembers the last scene and tab separately for each story in this browser.

The **Full screen** button in the row with **Save** spreads the text over the whole app window: the header, scene list, right panel, tabs and status row are hidden, and **Save** and **Exit full screen** remain. Leave with that button or the `Esc` key. The mode works on any tab; to run a stage or open another scene, leave it first.

## Scene sections

On the right, the **Scene settings** section (participants, narrator, word target, scene age rating) and the **Scene evaluation** section collapse and remember their state. Evaluation is hidden when the evaluator is off.

On a phone the sections go below the editor, and the top-row buttons show icons only.

![Workspace on a phone](../../images/site/en/workspace-mobile.png)

## Scene narrator

By default every scene is told by the narrator from the story style. To tell one scene from another point of view, choose the **Narrator** field in **Scene settings**: **First person**, **Third person through a character** or **Third person, omniscient**. For first person and third person through a character also choose the **Character** from the character cards. **As in the story** returns the narrator from the style. The model receives the choice in the brief, the draft and the full edit of this scene.

You can also set the narrator with an outline line:

```
Narrator: Lera, first person
```

`Narrator: omniscient` and `Narrator: Marko, third person` work too. The outline line takes precedence: the fields in the settings are then unavailable and show its value. When the line is unclear (no person, no character, or the name does not match a card), an explanation appears under the field, and the choice in the settings applies.

When the narrator is not among the scene participants, Obscura saves the choice and warns about it. Changing the narrator makes only this scene’s draft out of date; the brief and prose stay current (see [scene status](#scene-status-valid-or-unchecked)).
