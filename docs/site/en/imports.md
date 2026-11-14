# Importing materials

You can load the outline and the characters from UTF-8 TXT or Markdown files.

## How to import

1. In the scene list expand **Add materials**.
2. If needed, download the **Outline with timing (.md)** and **Characters (.md)** templates and fill them in.
3. Choose an outline file, a characters file or both, and press **Import**.

The result appears next to the form: how many new scenes and cards were created, what was skipped and the state of each file. The current scene stays open.

## Importing again only adds

- **Characters:** only new names are added. Existing cards do not change; edit them on the [Characters](characters.md) page.
- **Scenes:** a duplicate is identified by the author's explicit number: "Scene 2. The meeting" and "Scene 2: Friends" count as one scene. Titles and list positions do not identify duplicates. Sections without a number are added as new scenes every time.
- New scenes go to the end; the existing outline keeps its text.

## Outline format

Every scene starts with a heading "Scene N: Title" or "Scene N. Title". The file may open with the plan title, a single first-level heading (`# The Lighthouse`): the title and the text under it up to the first scene are the plan introduction. It does not become a scene, and the models see it as general notes for every scene. Other headings without a number (`## Interlude`) become unnumbered scenes. A line "Characters:", "Participants:" or "Cast:" sets the scene cast; names are separated by commas or semicolons.

```text
Scene 3: A call from her sister
Characters: Lera, Maria (on the phone).
Point of view: Lera
What happens: Maria calls Lera and asks for advice.
```

- An explanation in brackets stays in the outline for the model but is not part of the name.
- Names must match the cards exactly; case and extra spaces do not matter. The application does not guess a similar name and does not create a character from a name alone: generation waits until you fix the name or add a card.
- An empty "Characters:" line clears the cast; without the line, a cast chosen by hand stays.
- The other fields are instructions for the models. The number in the heading does not reorder scenes.

A character file with name headings of the same level (`## Lera`) creates starting cards with the status "Timing unverified" in a new story. Names that mix alphabets (a Latin C instead of a Cyrillic С) produce a warning.

A long book can be divided into parts and arcs right in the outline: see [Parts and arcs](book-structure.md). The `Series:`, `Number:` and `Start:` lines before the first scene add the book to a series: see [Book series](series.md).

## If something goes wrong

- A wrong format or encoding rejects the whole set of files before anything is saved.
- If one file fails, the following ones are not processed; successful files are cleared from the form, and only the failed ones remain for a retry.
- Do not repeat the whole set automatically: unnumbered scenes would be added a second time.
- If the server response is lost, press **Refresh journal** and check the scenes and cards before choosing files again.

## Import journal

In **Add materials** the journal lists every imported file with its local date and time and the number of scenes and cards actually created. Skipped duplicates are not counted.

The story word target is changed in **Settings → Writing**: at least 5,000, recommended up to 15,000 words.
