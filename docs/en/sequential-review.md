# Scene-by-scene book review

[Українська](../sequential-review.md)

Older briefs and prose without a saved historical baseline use **Current premises**: current plans, canon, character descriptions, the scene brief for prose, and earlier scenes. The preview and report explicitly state that no before-and-after comparison was performed. Original history is preserved. A complete clean search or your decision makes the material current for these premises; later source changes require review again. Corrupt sources and invalid memory remain blockers.

Open **☰ Story actions → Book revision → Check impact** on the story page. While the session waits for your decision, its card is also shown in the editor status row, so you can edit the scene next to the decisions. The preview shows the planner and an approximate initial search call count. Later scenes are planned after earlier scenes finish. Memory updates may require additional calls. For paid roles, enter a session spending limit; the story budget also applies. Opening a page or settings never starts a model call.

The session proceeds in scene order. A complete, successful search without concerns automatically marks the scene current. This is a practical model assessment that can miss problems, not a guarantee of literary quality.

Concerns or questions pause the session. Each includes a message, a scene passage and a premise. Choose **Dismiss as irrelevant** or **Address in corrections** for each, then apply your decisions. **Dismiss all and continue** explicitly accepts the scene as an author decision.

![Neutral example of author review](../images/sequential-review.png)

If you select corrections, open the scene and edit the saved text manually or use the existing generation/rewrite tools. Selecting concerns does not generate anything. Save your work, then choose **Finish corrections and continue**. The system accepts the current materials, updates memory and advances without searching that scene again. Your decision remains separate from the model report.

Memory uses only the current and earlier scenes. Changes to earlier prose can require several journals to be refreshed in order. A memory failure preserves accepted text and pauses the session. **Resume review** asks for explicit permission to repeat a failed call; completed, verified answers are reused without another call. Historical or invalid memory evidence is never silently accepted.

Decisions and session progress survive reload and settings navigation. Unsaved edits block author continuation. Changes to scene order or search sources stop application of the result; prepare a new preview. Role setting changes apply to the next call, while completed attempts retain their original settings.

Earlier impact checks remain in history in their original format. The new button starts protocol3. Journals and proofs are included in normal backup and integrity checks; no SQLite migration is required.

If a rebuild could erase author-maintained memory entries or lose forwarding choices, it stops before a model call and names the scene. Update that scene’s memory manually, preserving the required entries and checking your choices, then resume review. The old journal is not overwritten automatically. Invalid older journals also require manual repair.


## Review with exact evidence

Before previewing, choose **Review with exact evidence** to use the new format. **Standard review** retains the earlier format. The new format first compares premises, including statements within one passage, then compares the text with the premises. The model supplies exact quote pairs; code verifies addresses and determines their category. Exact quotes establish provenance, not the correctness of the model’s reasoning.

**Correction needed** identifies a contradiction with an unambiguous current premise. **Premise conflict** requires an author decision; **Missing information** names information needed for this check. Choose the first or second statement as current for this scene material. This affects that statement, not the whole document. The decision is stored separately, invalidates the current review and requires a new preview. Standard review cannot bypass it. Under **Author priorities for this scene**, revoke a priority if needed; revocation also requires review and never restores an old acceptance.

**Review incomplete** retains valid findings and lists incomplete parts. It cannot be accepted or dismissed to continue. Explicit retry reruns only invalid parts and dependent synthesis tasks; completed verified parts are reused. Invalid JSON and truncated responses are never automatically repaired.

In this release the new format requires **author confirmation even when no concerns are found**. Automatic model acceptance awaits a separate evaluation. Completing the planned tasks does not guarantee that the model found every contradiction.

Local evidence review requires native JSON schema, disabled thinking and an explicitly activated qualified token counter bound to the new system prompt. Old bindings are not transferred; missing or corrupt counters block dispatch. See [token budgeting](../token-budget.md) for offline registration and activation. Selecting the format does not perform qualification.

Premise-pair counts grow quadratically, but fitting premises are grouped in one request. Initial call counts are estimates because returned evidence may change later packing. One-scene search is limited to10000 parts; splitting preflight is additionally limited to100000 pairs. Paid preview shows a conservative one-scene search cost ceiling for that limit, excluding memory and subsequent scenes. Existing story/session budget checks still apply; search never increases a budget itself.

![Neutral example of a premise conflict](../images/review-evidence.png)


Model-generated memory may arrive inside a complete ```json block or paired outer apostrophes. The server removes that wrapper before JSON validation. Apostrophes inside text/quotes and the original response remain unchanged; successful normalization produces a warning. Schema/evidence checks and manual JSON stay strict. Generation is never retried automatically.
