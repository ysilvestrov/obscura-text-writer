# Book series

A series joins several books. The next book starts where the previous one ended: the heroes’ memory and the character cards pass into it as a **snapshot**. It is a copy taken at one moment, not a live link: after that the book lives its own life.

Series are available in the paid build of Obscura and when running from source, like [parts and arcs](book-structure.md). The Microsoft Store build does not have them: see [below](#in-a-build-without-series).

## Adding a book to a series

Books of a series stay ordinary stories in the story list. There are three ways to add a book to a series.

**Outline preamble.** When you [import an outline](imports.md), lines before the first scene set the series:

```text
Series: Sea saga
Number: 2
Start: Year 2 after the first book, anchor 1

## Scene 1: Return
The captain returns to the harbour.
```

- `Series:` — the series title. If there is no such series, Obscura creates it and tells you so.
- `Number:` — the book’s number in the series by release.
- `Start:` — an optional line for the chronology axis (see [below](#chronology)).
- These lines do not go into the outline.
- If the number is already taken by another book of the series or the lines are not recognised, the outline is imported without the series, and Obscura explains why.

**Book settings.** On the story settings page, in the writing section, the **Series** panel has the fields “Series” (an existing series or “New series…”), “Number in the series” and “Start”. To leave the series, choose “— no series —”.

**The “New book in the series” button.** On the series screen it creates a book with the next free number and opens it.

## Series screen

The **Series** link is on the library page. On the series screen:

- on the left — the books by release: number, title, snapshot state, the “Open” button;
- on the right — the same books on the chronology axis, with the books off the axis below it;
- at the top — renaming the series, “New book in the series” and “Delete series”.

Only a series without books can be deleted, including books in the trash. A book in the trash stays in the series, keeps its number and is shown marked “in the trash”.

Under the title of a series book in the workspace you see the series title and number. The link leads to the series screen.

## Snapshot of the previous book

The snapshot is taken by itself when a book enters a series with number 2 or higher and the previous book is already **finished**: its last scene has current memory (or the book-end merge of the arcs is usable).

- **Memory.** The first scenes of the book continue the memory of the end of the previous book. On the memory panel these entries are marked “Previous book of the series”.
- **Cards.** The book gets a copy of the previous book’s character cards with the same heroes. If the book already has a card with the same name that is a different character, the snapshot is not taken by itself, and the book shows a warning. “Update from the previous book” then names those cards: rename them in the book and update again.
- The previous book is the nearest book of the series with a smaller number that is not in the trash.

If the previous book is not finished yet, there is no snapshot, and the book shows “the previous book has no summary yet”.

## Warnings and updates

Finishing or editing the previous book **does not change** the next one by itself. The book and the series screen only show a warning:

- “⚠ book N has changed” — the memory of the end of the previous book, its cards or the previous book itself changed after the snapshot;
- “the previous book is finished — possible inconsistency” — the book started without a snapshot, and the previous book is now finished.

Next to it is the **Update from the previous book** button. Before acting, Obscura warns you:

- the memory, briefs and drafts of this book’s first scenes will become stale;
- new cards of the previous book are added;
- cards changed in the previous book are not overwritten: Obscura lists them, and you carry the edits over.

## Chronology

The `Start` line places the book on the chronology axis. The book without `Start` is the origin of the axis; usually it is the first book. The other books hold a time mark without the hour (year, month, day with a sign) from the anchor book, followed by the anchor number:

- `Year 2, Day 5, anchor 1` — two years and five days after the start of book 1;
- `Year -10, anchor 1` — ten years before it;
- `Year -1, anchor 3` — a year before the start of book 3.

The anchor is a book of the series with a smaller number that is already on the axis itself. A second book without `Start`, an anchor with a larger number or an anchor off the axis puts the book off the axis; this does not affect how the book works.

## Prequels

A prequel is a book that stands on the axis earlier than some book with a smaller number, for example book 2 with `Start: Year -10, anchor 1`. It is marked “Prequel”.

A prequel does not get the memory of earlier books as events that have already happened: its characters have not yet lived through what will happen to them later. These records go to the writer's requests as a separate section, “The future you must not contradict”, so the prequel's text does not contradict later books. A prequel snapshot taken before this version keeps the earlier memory as the past and shows the warning “review the facts of later books”.

You decide which facts of later books have already happened before the prequel. In the prequel's settings, on the series panel, press “Review the facts of later books”. The records are grouped by kind (facts, character states, open threads, timeline), each with the book it comes from. Mark a record “Past” if it has already happened: it then becomes the prequel's memory. “Future” keeps it in the section that must not be contradicted. “Save marks” asks for confirmation, because the memory and briefs of the prequel's first scenes become stale.

A book after a prequel starts from the memory of the main book — the nearest earlier book that is not a prequel — and of the prequels between them. If a prequel changed something the main book has (a character's clothes, say), the main book's value is kept; between two prequels, the one later in the chronology wins. A new prequel between the source book and the book gives a warning, and “Update from the previous book” takes it into the snapshot. On the series screen such a book has a “Sources: …” line and a collapsed “Conflicts settled automatically” block: which prequel values were dropped and whose book's value stayed.

## Export

If the series fields of the [publication card](publication.md) are empty, the EPUB gets the series title and the book number as the series and the position in it.

## Chat clients

Through [MCP](mcp.md) a chat sees the series, the number, `Start`, the snapshot state, whether the book is a prequel and how many conflicts were settled automatically in `get_story`; a prequel scene's context has a `future` field. A chat can add a book to a series with an outline preamble in `import_plan_and_characters`. Other series actions are available only in the app.

## In a build without series

The Microsoft Store build has no series screen, and series changes are unavailable. A series book created in another build can be opened for reading and export.
