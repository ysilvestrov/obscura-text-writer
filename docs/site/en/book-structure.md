# Parts and arcs

A long book can be divided into parts, and a part into arcs. An arc is a line of scenes with its own protagonist; a part holds one or several. An ordinary short story is one part with one arc, and there is nothing to set up.

Parts and arcs are available in the paid build of Obscura and when running from source. The Microsoft Store build does not have them: see [below](#in-a-build-without-parts-and-arcs).

## Parts and arcs in the outline

When you [import an outline](imports.md), Obscura recognises:

- a **part** — a heading one level above the scene headings that starts with the word “Part”;
- an **arc** — an `Arc: Name` line in a scene outline;
- an **arc protagonist** — a `Protagonist: Name` line in a scene outline (see [below](#arc-protagonist)).

```text
# Part 1: The city

## Scene 1: The station
Arc: Anna
Anna arrives in the city.

## Scene 2: The hotel
Anna looks for a room.

# Part 2: The road

## Scene 3: Dawn
Anna leaves.
```

- A scene without an `Arc:` line belongs to the arc of the previous scene in the same part.
- Part headings, `Arc:` and `Protagonist:` lines do not go into the scene outlines.
- Importing again with the title of the book’s last part continues that part; another title creates a new part at the end.
- If the book already had scenes without parts, they become the first part.

## The “Book structure” panel

On the story settings page, in the writing section, the **Book structure** panel lists the parts with their arcs. Here you can:

- add a part or an arc, rename it, move it up or down;
- delete a part or an arc that has no scenes — move its scenes to another arc first;
- save all changes with **Save structure**;
- return the book to its ordinary form with **Dissolve structure**; scenes and texts stay as they are.

A part keeps at least one arc, and a book keeps at least one part.

## The arc of a scene

In the scene parameters, the **Arc** field lists “Part › Arc”. The choice is saved at once.

Arcs follow one another: the scenes of an arc stand together, and parts come in order. Obscura refuses a change that would mix arcs or split a part, and names the scene in the way. A new scene joins the arc of the scene before it.

## Arc protagonist

By default every arc follows one book hero: the card marked as the protagonist, or the first participant of the earliest scene. An arc with a different lead can have its own protagonist:

- in the outline — a `Protagonist: Bohdan` line in the outline of any scene of the arc; the name must match a card title. If the card does not exist yet, Obscura looks again at the end of the import, so the character file can be imported after the outline. An unknown name gives a warning and sets no protagonist. The line sets a protagonist only for an arc that has none; change an existing one in the panel;
- in the **Book structure** panel — with the protagonist field in the arc row: **Book hero** or one of the cards. The choice is saved with **Save structure**.

The arc protagonist affects two things in the scenes of that arc:

- **core state** — memory always shows the model the clothing, location and other state of the scene’s arc protagonist. The state of another arc’s protagonist is an ordinary entry here, and its type can be changed in the memory table;
- **acquaintances** — the acquaintance block for the planner and the brief confirmation count whom the arc protagonist knows.

If you set a protagonist for an arc whose scenes are already written, only the written scenes of that arc become stale; scenes of other arcs and earlier scenes stay fresh. Until the book has an explicit protagonist, everything works as without arcs.

## The scene list

In a book with parts the scene list is grouped: a part heading, and under it the arcs when the part has several or the arc has a title. Scene numbers run through the whole book. On a phone, parts become groups in the scene picker.

## Memory and texts

The titles and order of parts and arcs never go into model requests. Renaming or dissolving the structure does not make any text stale. The exception is the [arc protagonist](#arc-protagonist): moving a scene to an arc with another protagonist, or changing the protagonist, changes the core state of its requests.

## Export

In book files parts become higher-level sections: in Markdown a `##` heading with scenes under `###`; in TXT a separate line before the first scene of the part; in FB2 and EPUB nested sections and table of contents; in PDF a page for each part and two bookmark levels. An untitled part is exported as “Part 2”. Arcs are not shown in the export. See [Publication and export](publication.md) for more.

## In a build without parts and arcs

The Microsoft Store build has no panel and no “Arc” field, and an outline is imported as usual: part headings and `Arc:` lines stay in the text.

A book with several parts or arcs made in another build can be read and exported here, but not changed: the workspace shows a message about it.
