# Characters

Open **Characters** in the story's top row. The separate page has wide description fields, with availability settings alongside them on a computer and below the description on a phone. **Return** opens the same scene and material you came from.

![Characters page](../../images/site/en/characters-desktop.png)

## Cards and entries

The buttons at the top save the cards, add a character or reload what is saved. Each card consists of entries; a solid imported description can be split into entries at blank paragraphs. Entries written by hand are marked "Author statement", imported ones keep their source quotations, and entries accepted from the model's character search are marked "From model".

After you save changed cards, Obscura asks: “Cards changed: … Mark the dependent scenes as unchecked? Scenes: N.” Dependent scenes are the scenes with a brief where the character is a participant or the narrator, including for a removed card. **Yes** makes the brief and prose of these scenes “Unchecked” until you approve or regenerate them ([scene status](workspace.md#scene-status-valid-or-unchecked)); **No** changes nothing. Cards changed through a chat client (MCP) do not change scene status.

The **Find a character** field next to the buttons keeps only the cards whose title or [other name](#other-names) contains the text you type, and shows how many cards are visible. Enter or picking a name from the suggestions moves to that card and puts the cursor in its name field. Cards are only hidden: your edits are kept, and **Save details** saves every card. If a hidden card has an empty required field, the filter is cleared so you can see it. **Add character** clears the filter too.

## Character and place search in the prose

If the book is already written, for example [imported from a manuscript](manuscript-import.md), you do not have to write the cards by hand: the Memory role model reads the prose and proposes them, together with the places of scenes whose plan has no `Location:` line. The **Character and place search in the prose** section is shown once some scene has prose.

**Find characters and places in the prose…** opens a preview, and nothing starts until you press **Start**. The model reads the book in groups of whole scenes and sees the characters found so far, so it understands better who the main character is. **Group size, words** is from 1,000 to 20,000, 5,000 by default. The preview shows how many scenes and groups will be read, the largest number of model calls, the upper bound on cost (for a local model, "Cost unknown") and the scenes the search will not read, with reasons. The real price is usually cents per book. If the previous proposal is not accepted yet, the preview warns that after a new search it can no longer be accepted.

While the search runs, the row under the button shows how many groups are left and how many calls were made; **Pause**, **Resume** and **Cancel the search** are there too. You can close the page: the search goes on, and the row comes back when you open the page again. A cancelled search proposes what it managed to read and names the scenes it did not read. If the model refused to answer because of the content, the search stops: choose another Memory role model and press **Resume**.

![Character and place search proposal with checkboxes](../../images/site/en/character-proposal-desktop.png)

After the search a proposal appears. Nothing is written automatically:

- **New cards** — the name, other names and one or two verbatim quotes with the scene title;
- **New names** — names the existing cards do not have yet;
- **Main character** — if no card has the main character mark yet;
- **Scene casts** — the participants of a scene. An empty cast gets a full one, and a filled one only gets new participants added: nobody is removed.
- **Scene places** — up to three places of a scene named in its prose, with the full path as in a `Location:` line (`Lighthouse / lamp room`). A place that is not among the [location cards](memory.md#locations) yet is marked “new”. A scene whose plan already names a place is left alone, and places the scene already has are not proposed again.

Every item has a checkbox, and every group has **Select all** and **Clear all**. Names in lower case (descriptions and forms of address such as "the old woman" or "fisherman") start unselected, and so does a place the scene's prose does not name. Below the list you see how many scenes with built memory will become stale. In a book without cards the very first accepted cards make the memory of every scene stale, so search for characters before building memory.

**Accept selected** writes the selected items. While the cards have unsaved edits the button is unavailable: save or discard them first. An item that went stale (the scene was removed, the prose changed or a card with that name was added) is skipped, and the summary lists what was skipped with reasons. Quotes become entries marked "From model", available from the scene of the quote; you can edit them like any other. Accepted places become cards of the [Locations](memory.md#locations) section and places of the scene. A `Location:` line you add to the plan later takes precedence over them, and a wrong place can be removed from the scene in the same section. A proposal is accepted once: what you did not select is dropped, and a new selection needs a new search.

## When a character appears

For each entry choose:

- **From the beginning**: the model knows it in every scene;
- **Starting from a scene**: only from the chosen scene;
- **Timing unverified**: the entry is visible with a warning.

**What the writer will see** shows which entries reach the context of the chosen scene, with no model call and without saving. After you reorder scenes, availability follows the new order.

**Save details** creates a new version of the cards. If the cards changed in another tab meanwhile, your edits stay in the form, and reloading asks for confirmation.

## Other names

If a character goes by several names, list the other names in a card entry with a line such as `Other name: Boss` (also `Other names:`, `Also known as:`, `AKA:`, or the Ukrainian «Інше ім’я:», «Інші імена:», «Також відомий як:»). Separate several names with commas.

- Plans recognise the character by the card name and by every other name: in the scene cast, `Knows:`, the narrator line and `Protagonist:`.
- To have the character called differently from some scene on, set the entry with the line `Other name: John` to **Starting from a scene**. From that scene the models call the character John and see the earlier names: "John (also: Boss)". Obscura does not insert the name John into earlier scenes; your own text in plans or other entries goes as written.
- An entry without a first scene only adds a name; it does not change what the character is called.
- A card name wins over another card's other name: with the cards "Aya" and "Aya-bot" whose entry says `Other name: Aya`, "Aya" in a plan means the card "Aya". The Characters page and the import result point this out.
- If two cards share a card name, or two cards share an other name, the page and the import result show a warning, and a plan using that name asks you to clarify the cast.
- The interface calls the character by the card name. A name change makes stale the drafts whose requests it changed.

## Protagonist and acquaintances

To keep the model from naming people the protagonist has not met yet, the brief, draft and rewrite contexts get a short "Protagonist acquaintances" block.

- Mark the protagonist with a line of its own in a card description: `Protagonist`, `Main character` or `Lead character` (or the Ukrainian «протагоніст», «протагоністка», «головний герой», «головна героїня»). A template line such as `Role in the story: Protagonist` also works. Without a mark, the protagonist is the first participant of the earliest scene.
- Acquaintances from before the story use the line `Knows: Name, Name` or `Acquainted with: Name, Name` (or the Ukrainian «Знайомий з:», «Знайома з:», «Знайомі з:»). A dash, `Knows: —`, means the protagonist knows nobody. An unknown name produces a warning but does not block generation.
- The planner records in the brief whom the protagonist meets in this scene. If you write the brief by hand, you can change this field.

An acquaintance is the planner's intent, not a check of the prose: if the writer skipped the introduction, the next scene still treats the character as acquainted.

If prose was saved by hand and its link to the brief was lost, the prose tab shows the **Brief and introductions** panel. Tick who was introduced to the protagonist in this scene and press **The prose rests on this brief**. If the brief does not match the prose, press **Open the brief**, fix and save it. **Next unconfirmed scene** moves to the next scene waiting for confirmation. Confirmation does not change the prose.

## Character age

The age-rating safeguard reads the age from a line starting with `Age:` or `Вік:` in the card entries. See [Age ratings](content-rating.md#character-age).
