# Characters

Open **Characters** next to **Settings** at the top of your story. The separate page provides wide description fields, with availability settings alongside them on desktop and below them on mobile.

Use the controls at the top to save, add a character, or reload saved cards. For each entry, choose its availability and, when applicable, the first scene where it becomes available. Preview a selected scene before saving; preview does not save your changes. You can still split descriptions into paragraphs and manage entries, origins and sources.

The return link restores the scene and material you were viewing. Your browser warns before leaving unsaved edits. A failed save or revision conflict keeps your edits; reloading requires confirmation. Another tab uses saved cards only. Without scenes, cards can be edited but preview is unavailable. Switching UA/EN preserves your text.

![Characters on desktop](../images/characters-page-desktop.png)

## Protagonist acquaintances

To keep the model from naming someone the protagonist has not met yet, the brief, draft and rewrite contexts get a short "Protagonist acquaintances" block: who is already acquainted (and from which scene) and who has not been introduced. The block appears only when the protagonist is among the scene participants. If a scene is told from the protagonist's point of view but they are missing from the participants line, add them to the cast, otherwise there is no block.

- **Protagonist.** Mark them with a line of their own in a card description. The parser recognizes only the Ukrainian literals, so write the line exactly as «протагоніст» or «протагоністка» ("protagonist"), or «головний герой» or «головна героїня» ("main character"); English wording is not recognized. The role line from the standard card template also works: «Роль у творі: Головна героїня» ("Role in the story: main heroine"), where the first listed role decides. The mark applies to the whole story, even when it sits in an entry available only from a later scene. Without a mark, the protagonist is the first participant of the earliest scene.
- **Acquaintances before the story.** A line written with the Ukrainian literal «Знайомий з:», «Знайома з:» or «Знайомі з:» ("acquainted with") followed by names, for example "Знайомий з: Name, Name", in the description of the protagonist's card or of the person they know; the acquaintance is mutual. The line follows the availability of its own entry: placed in an entry available from scene 5, the acquaintance appears from scene 5 with no introduction in the text. A dash ("Знайомий з: —") means nobody. An unknown or ambiguous name produces a warning but does not block generation; the warning names the card with the line, the name itself and what to fix. Marks are optional: without them, a character who first appears with the protagonist is treated as not yet introduced.
- **The `introduced` field in the writer's brief.** The planner lists the characters introduced to the protagonist in this scene; once introduced, a character counts as acquainted. If you write or edit a brief by hand, you can change this field. Draft and rewrite do not fill it.
- **Limitations.** Acquaintance is the planner's intent, not a check of the prose: if the writer skipped the introduction, the next scene still treats the character as acquainted. For earlier scenes with prose but no brief (for example written by hand), a fallback applies: everyone in the cast with the protagonist counts as acquainted. If you use a custom brief prompt, the app appends a short description of the response shape with the `introduced` field after it, so older prompts need no rewrite. If a structured-output model still gets stuck emitting whitespace, generation stops with an explanation instead of using up the whole response limit.

The interface does not change; existing cards, briefs and prose are not rewritten.

The age that the age-rating safeguard reads comes from an `Age:` line at the start of a line in the card details; the parsing rules and the blocking messages are described in the [age rating guide](content-rating.md#character-age-and-the-safeguard).
