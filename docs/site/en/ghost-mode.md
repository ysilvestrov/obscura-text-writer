# Rewriting from memory

This mode helps you rewrite a scene's AI draft in your own words instead of editing it mechanically. At any moment you either read the original or write, never both at once. The result becomes your manual draft, which you can proofread with the regular editor or accept as prose right away.

## Getting started

1. Open the scene and the **Draft** stage. The draft must be saved.
2. Click **Rewrite from memory**. A full-screen mode opens.

The draft is split into blocks of about two lines: a paragraph, with short paragraphs such as dialogue lines joined to the following ones. Scene separators (`***`) are carried into the result as they are.

## Writing

- You see the current draft block. As soon as you start typing, it disappears and only your text remains.
- **Peek:** while you hold `Tab`, your text is hidden, the draft block is shown and typing is locked. For mouse and touch there is a **Peek (hold)** button.
- `Ctrl+Enter` or **Next** moves to the next block, **Back** to the previous one.
- **Skip block** deliberately leaves a fragment out of the new draft; **Restore block** undoes that.
- `Esc` moves the cursor out of the field, because `Tab` in the field is taken by the peek.
- Pasting is disabled, and the draft text cannot be selected or copied.

## Saving

**Save as draft** becomes available once every block is written or explicitly skipped; skipped blocks need a confirmation. Saving creates a new manual draft; the AI draft stays in history unchanged. Then follow the usual path: run the editor, which fixes spelling and punctuation without rewriting, or accept the draft as prose.

Under such a version in the history you see statistics: blocks rewritten and skipped, the share of your text that matches the draft verbatim (by four-word fragments), the number of peeks and of blocked pastes. Nothing is sent to models or anywhere else.

## Unsaved rewriting

Until you save or cancel, the rewrite is kept in this browser: after closing the tab the button reads **Continue rewriting**. In another browser or after clearing site data the unsaved text is gone. **Cancel rewriting** deletes it after you confirm with **Delete my text**.

If the draft changed after you started, the mode warns you: you keep rewriting the version you started from.

## Limitations

The mode is a discipline for the author, not a protection: the draft can be opened in another tab. The overlap share sees only verbatim matches, not close paraphrase.
