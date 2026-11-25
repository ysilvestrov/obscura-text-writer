---
name: start-story
description: Use when the author wants to write a new story or book in Obscura, has an idea, lore, characters or a ready plan, or does not know where to start. Triggers include "хочу написати оповідання", "напиши історію про…", "не знаю, з чого почати", "є ідея для книжки", "write a story about…", "I want to write a book", "help me start a story".
---

# Start a story: from an idea to an imported plan

Read `${CLAUDE_PLUGIN_ROOT}/shared/rules.md` first and follow it throughout. It covers one question at a time, consent before writing, marking your own decisions, and progress lines.

This skill turns the author's idea into an Obscura story with an imported plan and character cards. The rule that matters most: **nothing is created until the author agrees to the summary.**

## Model

Planning shapes the whole book, so use the strongest model available.

- **Claude Code:** if the session model is weaker than the strongest one, tell the author once and suggest switching with `/model`. Do not insist.
- **Advisor:** if an advisor tool is available, consult it once before you show the summary.
- **Claude Desktop:** you cannot switch the model yourself. Suggest it once, only if the current model is clearly a light one.

## Gates

Go through these gates in this order. At each gate, ask only what the author has not already given. Each question is its own message, one card. The details, defaults and example cards are in `${CLAUDE_PLUGIN_ROOT}/skills/start-story/references/interview.md`.

1. **Main characters.** Each main character needs:
   - an age, or an explicit "all participants are adults";
   - a few traits of appearance;
   - an occupation;
   - a way of speaking.

   Ask one card per missing item. Invent secondary characters yourself and mark them as your decisions.
2. **Idea, plan, ending.** The minimum is the idea. If the plan or the ending is missing:
   - show the structure: exposition → inciting incident → rising action → climax → resolution;
   - for each missing part, offer 2–3 concrete options of what could happen, one card per part.
3. **Length and scenes.** The default is 7000 words in 7 scenes of 1000 words. Offer it on one card with the merge options from the interview reference. Obscura accepts at least 5000 words per story; the reference says what to do for shorter pieces.
4. **Title.** If there is none, offer a card with 3 titles. The author can type their own.
5. **Only if not said:** point of view, place and time, content rating, language. Offer the default for each. The content rating is required: Obscura will not generate text without it.

**Series or a world with rules.** If the idea has lore, magic rules, factions or a planned cycle, suggest writing a series bible before the first book. Use the `series-bible` skill for that; if the author prefers to start with the book, note the bible as a later step and go on.

## A ready manuscript

If the author already has the finished text of a book (a Word, Markdown or plain-text file), do not run the interview and do not retell the text. Import the file as it is:

1. Ask for the full path to the file on this computer (or, for a small file under 2 MiB, take its content). Never open the file yourself.
2. `import_manuscript(file_path)` without `confirm`. It creates nothing and calls no model.
3. Show the author the proposed scenes: the titles, the words in each, the warnings, and `tracked_changes` if it is not zero (unresolved Word revisions are accepted as they stand, so suggest resolving them in Word first). Ask for the book title (offer `title_suggestion`) and the content rating. To change the chapter markers or the source of chapters, call `import_manuscript` again with the same import_id and the new `chapter_markers`, `part_markers` or `chapter_source`. To move a boundary, pass your own `scenes` on the confirm call. Parts and series are only for the full edition: check `edition` before offering them.
4. Wait for explicit consent. Then call `import_manuscript` with `confirm=True`, the import_id and `fingerprint` of the preview the author saw, and the `title`. A changed preview means a new `fingerprint` and a new consent.
5. The imported book has the author's prose and no memory yet. Offer to build it, with the cost named:
   - **`obscura` mode:** `start_run(action='rebuild_memory')` without `confirm` returns the preview: the number of scenes, the cost (an upper bound, or "unknown" for a local model), the scenes that do not fit the memory model's limits, the series hint and the cast that Obscura will fill in from the names in the prose. Show it to the author. Only after a clear yes call it again with `confirm=True` and the `plan_fingerprint` from that preview. If the answer says the plan changed, show the new preview and ask again. Follow the run with `get_run`.
   - **`chat` mode:** Obscura does not start the build. Either the author switches the book to `obscura` in the book settings, or you build the memory scene by scene in the chat with the `draft-scene` skill.
6. Then continue as in "After creating": the author reads the book in the Obscura window, and writing new scenes is a separate request.

Importing never changes an existing book and never costs money; only step 5 does, and only after the author has seen the cost.

## Summary and consent

Show one summary:
- characters with their cards;
- scenes with their role in the structure;
- title, length, rating, language, writing mode;
- your own decisions, listed.

**Writing mode:**
- **`chat`** (default) — you write the texts;
- **`obscura`** — Obscura's own models write them, and the author pays the provider.

If the author has not said, recommend `chat` and say why in one line.

Wait for explicit consent. A changed detail means a new summary.

## Create

Only after consent:

1. `create_story(title, language, target_words, content_rating, writing_mode)`.
2. `get_templates(language)`. Fill the plan template and the characters template with the agreed content:
   - keep the headings «Сцена N: Назва» (or "Scene N: Title");
   - keep the «Хто бере участь:» line with names exactly as in the character headings;
   - when a scene is told from a different point of view than the rest of the book, add a line «Оповідач: <name>, перша особа» (or «третя особа»; «Оповідач: всезнаючий» for an omniscient narrator; English: «Narrator: <name>, first person»);
   - for a book of a series, start the plan with the preamble lines «Серія: <name>» and «Номер: N».
3. `import_plan_and_characters(story_id, plan_markdown, characters_markdown)`. Check the import result. If it reports problems, fix the Markdown and import only the missing part again.
4. `get_story(story_id)`. Confirm:
   - the number of scenes;
   - the characters;
   - `writing_mode`;
   - the series status, if the story belongs to a series.

## After creating

**Stop after `get_story`.** This skill never writes scenes. Consent to the summary, even "create it right away, no questions", covers creating the story only. Writing scenes is the author's next request: ask whether to start the first scene, and on a yes follow the `draft-scene` skill from its beginning (it starts with the brief, not the draft).

Tell the author what now exists and what comes next:
- **`chat` mode:** writing the first scene, with the `draft-scene` skill;
- **`obscura` mode:** first check `get_settings`. If the roles are not configured, the next step is choosing models with the `setup-models` skill. Then write scenes with `draft-scene`.

End with your list of own decisions.
