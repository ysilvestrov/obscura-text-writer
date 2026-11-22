# Comments, prompts and horizon

## Draft comments

On the **Draft** tab, below the editor, there is a field for a general instruction. To comment on a single phrase, select it and press the comment icon on the editor toolbar; clicking a highlighted passage opens the same instruction. **Save comment** updates the working notes, while the manuscript's **Save** stores the text and all notes together. Commented passages cannot overlap.

**Rewrite from comments** saves your edits, checks readiness and starts one writer call. The result opens as a change review in which nothing is selected at first:

1. Choose groups of changes and review the assembled text. **Select all changes** ticks every group at once. Labels such as **Inside a commented range** describe where a change is, not whether the instruction was followed.
2. Accepting all or some changes creates a new draft and clears the working instructions; the history keeps them. An empty selection rejects everything and keeps the notes.
3. Then edit by hand, add new comments or run the usual [editing](revision.md).

Notes saved without text changes do not make later scenes outdated. Limits: up to 100 comments, 8,000 characters per instruction and 50,000 in total.

## Editor modes and prompts

In the settings of the **Editor** role you can choose a mode:

- **Revision with change review** — the model returns prose, and the application shows each change as "Before / After". Tick the ones you want, press **Preview edited text** and then **Accept edits**. If there are no changes, the text becomes prose at once.
- **Targeted language edits** — see [Editing a scene](revision.md#editing-a-scene).

**Maximum editing passes** (1 to 10, default 5) — how many times the editor may pass over the text in one run. Each pass is a separate model call; the editor stops earlier when there is nothing left to change. The value is kept for each story separately. If a pass leaves fewer than 60% of the words of the text the editor received, or of the text the run started from, Obscura treats the reply as an excerpt and rejects the pass. You still get the earlier successful passes to review, as after any other failure. The editor only proofreads, so shorten a scene by hand or with a rewrite.

Changes to numbers, negations and large parts of the text are flagged with warnings. The **Optional change classifier** is a separate paid call that only advises which changes are stylistic; it ticks nothing.

Every role has a standard prompt for its mode. You can write your own prompt instead; after changing the mode, adapt it and tick **I adapted the custom prompt and assign it to the selected stage and mode**, or press **Restore default prompt**. The application checks only the response format, not the content of your instructions.

## Future outline horizon

In the settings of every role the **Future outline horizon** block sets how many outlines of later scenes the model sees:

- **Current and all following scenes** — the default;
- **Current and next N scenes** — for example, for scene 3 and N=2 the model gets outlines 3, 4 and 5;
- **Current scene only**.

The planner and the writer can have different horizons; memory never receives future outlines. In the **Writing profile** you can add an **Author’s ending guide** — the intended resolution, up to 12,000 characters, which the model sees separately from the outlines. The horizon limits only outlines: if the ending is already mentioned in a brief, the style or a prompt, the model will see it. When the model sees outlines of later scenes, the request asks it to carry out only the beats of the current scene, whatever the horizon.

The **Voice sample** field in the **Writing profile** takes a passage of up to 3,000 characters — for example, a few sentences in the rhythm the story should have. The writer takes its rhythm, vocabulary and sentence structure, but not its events, names or world. Only the draft, the comment-based rewrite and the edit in full-rewrite mode see the sample. Changing it makes drafts and scene texts stale, but not outlines and briefs. Use your own text or text you have the right to use.

## Scene statistics

Below the editor you see the word and character count of the current text. Expand **Scene and context statistics** to see the size of saved materials, the prose compared with the word target, and what makes up the request of the chosen stage: outline, memory, characters, reserve. The **Current prose** line shows the scene's prose words against its target, and in brackets the same for the whole story. Only the current prose of each active scene counts: earlier versions, alternatives and scenes in the trash are not added up, and a scene without prose or without a target counts as 0. In the Microsoft Store edition the section is called **Scene statistics** and shows only the materials table and the prose line. Tokens here are an estimate, not a count by the model's tokenizer. **Refresh statistics** recalculates without a model call.
