# Story and scene age rating

This page explains how to set an age rating, what the safeguard on character age does, and which label FB2 and EPUB files receive. Ukrainian version: [Віковий рейтинг](../content-rating.md).

## Why a rating

The rating describes how explicit the text may be along three axes: **Sexual content**, **Violence** and **Hard themes**. Each axis has a level from 0 to 2:

- **0 — ordinary**;
- **1 — adult, without graphic detail**;
- **2 — explicit**.

The rating enters the requests to the model as a limit: the model must stay within the levels of the scene. It also drives the safeguard on character age and the age label of exports.

## Story rating in settings

Open the story settings, the **Writing** section, choose a level for each axis, and press **Save rating**. Until all three levels are chosen, the rating cannot be saved ("Choose a level for every rating axis").

- A new story, and every story created before ratings existed, is "not set". While the story rating is not set, no generation stage starts, including plan preparation: the application asks you to set the rating in settings.
- The rating cannot be returned to "not set": only the axis levels can be changed.
- If the rating was already changed in another tab, the application asks you to reload the page before saving again.

## Scene rating in Scene settings

Scene settings contain the **Scene age rating** form with two options:

- **Same as the story**, with the story rating shown in brackets. This is the default; the three lists are disabled in this mode.
- **Own rating**: the same three axis lists, and the value applies to this scene only.

Press **Save scene rating**. Going back to "Same as the story" removes the own rating. For a story without a rating, "Same as the story" shows "not set", but the scene can still be given its own rating.

Lowering the rating (on at least one axis) marks the scene's materials created under the higher limit as outdated: review and accept the writer's brief, draft, edit and rewrite, or regenerate them. Raising the rating does not change the materials. Text that you wrote yourself or explicitly accepted after it was created does not become outdated when the rating is lowered: the rating limits the model, and the decision about the text stays with you.

## Character age and the safeguard

Before generating a scene whose sexual content is 1 or higher (the brief, draft, edit, rewrite and memory stages), the application checks the age of every character in the scene cast. The age comes from the **character card**: an `Age:` line (or `Вік:`) must be at the start of a line in the card details.

```
Age: 34
Age: adult
```

Parsing rules:

- If the value contains several whole numbers, the smallest is used (`Age: 17, 34` gives 17). Under 18 means a minor.
- An empty value, or a negation such as "not yet adult", gives "age not specified".
- Without a number, only the whole value `adult` (or the Ukrainian `дорослий`, `доросла`, `дорослі`, `доросле`) counts as adult.
- The details available for the scene under [character availability](characters.md) are used: the group whose first scene is the latest one not later than the current scene. If the group has several entries with different ages, a minor takes priority, then "not specified", then adult.

Generation is blocked by an empty scene cast, missing character cards, a minor participant, or a participant without a stated age. The message names up to five characters (then "and k more") and offers three ways to unblock:

1. add an "Age: …" line to the card (a number from 18 or "adult");
2. remove the character from the scene cast;
3. mark the scene with the rating "sexual content 0". In such a scene the age checks do not apply to any participant, so you take responsibility for the rating.

The application never lowers a rating automatically. The block is visible in the start message and on the readiness screen, including for a later scene of an "all remaining scenes" run.

## Age label in FB2 and EPUB

When exporting FB2 or EPUB, the application takes the highest level among the story rating and the effective ratings of the exported scenes, across all axes, and adds a label: level 0 gives `0+`, 1 gives `16+`, 2 gives `18+`. In FB2 it is written as `custom-info` with `info-type="age-rating"`, in EPUB as the `obscura:age-rating` metadata. The label is not inserted into the book text or the title page. MD, TXT and PDF carry no label.

If the story rating is not set, the book has no label, and the export manifest gets the warning "Віковий рейтинг твору не задано; позначку не додано" ("the story age rating is not set; the label was not added"; the text is in Ukrainian). The warning does not stop the export and does not make it incomplete. The manifest also records `age_rating` (the value or `null`).

## Limitations

The safeguard relies on the age that the author wrote in the card and on the rating that the author set. It does not verify them: a false age or an understated rating bypasses it. The rating in a request limits the model but does not guarantee matching text. The safeguard helps you comply with the [Terms of Use](terms-of-use.md) but does not guarantee legal compliance. The application does not change a rating on its own, and it does not rewrite existing cards or texts.
