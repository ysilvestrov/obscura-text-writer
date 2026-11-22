---
name: publish
description: Use when every scene of an Obscura story has prose, or when the author asks to publish, export, make a cover, or fill the book's card (author, annotation, genres). Triggers include "опублікуй", "експортуй у FB2", "зроби обкладинку", "анотація до книжки", "publish the book", "export to EPUB", "make a cover".
---

# Publish: card, cover and export

Read `${CLAUDE_PLUGIN_ROOT}/shared/rules.md` first and follow it throughout. It covers one question at a time, consent before writing, and progress lines.

This skill fills the book's publication card, draws a text cover and exports the book. The rule that matters most: **the author's name comes only from the author.** Never invent it and never take an existing signature silently.

## 1. Is the book finished?

`get_story(story_id)`. Export takes only the prose the author has approved in Obscura.

- Every scene has prose: go on.
- Some scenes do not: tell the author which ones and ask whether to export the unfinished book anyway. A request that names the export and says to go on without questions already answers yes. On a yes, export later with `allow_incomplete=true` and say in the final message that the book is unfinished. On a no, stop and suggest finishing them with the `draft-scene` skill.

## 2. Read the card

`get_publication(story_id, genres_language=<the story's language, uk or en>)`. Note `revision`, the current `card`, `signatures` (names already in Obscura's shared list) and the `genres` catalog.

## 3. Fill the card

Ask only what is missing from the card or from the author's request, one card each.

1. **Author** — always required. If the card already has `author_ids`, ask once to confirm them. Otherwise offer a card with the `display_name` of the non-archived `signatures` plus "another name".
   - An existing name, or a name the author gives that matches a signature exactly: take its `id`. Never add a duplicate.
   - A new name the author gives (in the request or on the card): `add_signature(display_name)` and take the new `id`. A new signature is a write: do it only once the author has named that person as the author.
2. **Annotation** — 2–3 sentences, no spoiler of the ending, in the story's language. Base it on the plan from `get_story` and the prose (`get_scene_text(scene_id, 'prose')`, following `next_offset`). Show it for approval. Text the author dictated needs no second approval.
3. **Genres** — 1–3 codes from the `genres` catalog, offered on a card with their names.
4. **Keywords** — up to 10, no repeats.
5. **Series** — `cycle_title` and `cycle_number` from the story's `series` in `get_story`, if it belongs to one.

Show the filled card as one summary, with your own decisions marked, and wait for consent. Then `update_publication(story_id, expected_revision=revision, fields=<only the changed fields>)`. Keep the `revision` it returns.

## 4. Cover

1. A card with the palette: «Чорнило» / Ink (`ink`), «Папір» / Paper (`paper`), «Бордо» / Wine (`wine`), «Ліс» / Forest (`forest`).
2. `generate_cover(story_id, palette)`. It draws from the **saved** card — title, series, authors — so it always comes after step 3.
3. `update_publication(story_id, expected_revision=<latest revision>, fields={cover_id})`.
4. Tell the author the cover is set and offer another palette. Choosing another one repeats 2–3.

**The author's own image:** `upload_cover(story_id, file_path)` with an absolute path to a PNG or JPEG of at most 10 MiB, then `update_publication({cover_id})` as above.

## 5. Export

1. A card with the format: FB2, EPUB or PDF (`fb2`, `epub`, `pdf`; `md` and `txt` also exist). For handing the book to an outside editor, offer the Word manuscript `docx` (or `rtf` for editors without Word). FB2 needs an author and a genre in the card.
2. `export_book(story_id, format, allow_incomplete)`, with `allow_incomplete=true` only if the author agreed in step 1.
3. Give the author the `download_url`, the `word_count` and any `warnings`. In Obscura the same export is under ☰ «Дії твору» → «Експорт…».

## 6. Summary

What is now in the card, which cover was set, the export link, your own decisions, and — if the book is unfinished — which scenes are still missing.
