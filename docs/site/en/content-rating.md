# Age rating

The rating describes how explicit the text may be along three axes: **Sexual content**, **Violence** and **Hard themes**. Each axis has a level: **0 — ordinary**, **1 — adult, without graphic detail**, **2 — explicit**.

- **Sexual content** — erotica and intimate scenes.
- **Violence** — physical harm shown in the text: fights, wounds, killings, torture.
- **Hard themes** — heavy subjects the story deals with, even without physical violence: suicide and self-harm, addiction, psychological abuse, discrimination, grievous loss.

The **?** button next to an axis name explains its levels. The rating is passed to the model as a limit at the stages that write the scene: brief, draft, edit, rewrite.

## Story rating

Open the story settings, the **Writing** section, choose a level for each axis and press **Save rating**.

- A new story is "not set". While the rating is not set, no generation stage starts, the plan included.
- You cannot return to "not set", only change the levels.
- If the rating was changed in another tab, reload the page before saving again.

## Scene rating

In the scene settings the **Scene age rating** form offers **Same as the story** (the default) or **Own rating** for this scene. Press **Save scene rating**.

Lowering the rating on at least one axis marks the scene materials created under the higher limit as outdated: review and accept them or regenerate them. Raising it changes nothing. Text you wrote yourself or explicitly accepted does not become outdated when the rating is lowered.

## Character age

Before generating a scene with sexual content 1 or higher, the application checks the age of every character in the scene cast. The age comes from the character card: an `Age:` (or `Вік:`) line at the start of a line in the card entries.

```
Age: 34
Age: adult
```

- If there are several numbers, the smallest is used. Under 18 means a minor.
- An empty value or a negation ("not yet adult") means "age not specified".
- Without a number, only the whole value `adult` (or the Ukrainian `дорослий`, `доросла`, `дорослі`, `доросле`) counts as adult.
- The entry available for this scene is used (see [Characters](characters.md#when-a-character-appears)).

Generation is blocked by an empty scene cast, missing cards, a minor participant or a participant without a stated age. The message names the characters and offers three ways out: add an `Age:` line to the card (a number from 18 or "adult"), remove the character from the scene cast, or mark the scene with "sexual content 0". In the last case the age check does not apply to this scene, and the rating is your responsibility. The application never lowers a rating itself.

## Rating and models without Uncensored

The request rating (the highest level on each axis among the story and the scenes that go into the request) decides whether a model without the Uncensored mark needs consent: at 0/0/0 it does not, with any axis above 0 it does. If a model refused because of the content, the application blocks that model at the same or a higher rating until you clear the mark. See [Models](models.md#consent-for-a-model-without-uncensored) and [Refusal mark](models.md#refusal-mark) for details. There is no automatic switch to another model.

## Scene rating and the writer model

The rating of a scene (or of the story, when the scene has none of its own) also picks the writer model. If you set a [separate model for scenes 0-1](models.md#a-separate-writer-model-for-scenes-0-1), it writes scenes where no axis is 2; scenes with an axis at 2 are written by the main model.

## Label in FB2 and EPUB

When exporting FB2 or EPUB, the highest level among the story rating and the exported scenes is used: 0 gives `0+`, 1 gives `16+`, 2 gives `18+`. The label goes into the file metadata, not the text. MD, TXT and PDF carry no label. If the story rating is not set, there is no label and the export manifest contains a warning.

## Microsoft Store build

In the build installed from the Microsoft Store, the highest sexual content level is 1: level 2 cannot be selected for a story or a scene. Violence and hard themes levels are not limited. A hint under the rating form states this limit.

A story with level 2 brought from another build opens as it is: you can read it, edit it by hand and export it, and the form shows its real rating. The model does not write for such a story or scene: story plan preparation, scene plan, draft, editing, rewriting, memory, publication metadata suggestions and writing through an external client are blocked until you lower the rating. Evaluation and checks of text that already exists keep working.

If the model wrote something unacceptable, use the "Report a result" link in the application header. It opens a page in your browser; the application itself sends nothing there.

## Limitations

The safeguard relies on the age and the rating the author entered and does not verify them: a false age or an understated rating bypasses it. The rating limits the model but does not guarantee matching text. The safeguard helps you comply with the [Terms of Use](legal.md) but does not guarantee legal compliance.
