# Story language and length

A story can be written in Ukrainian or English. The interface language (the UA/EN switch at the top) does not depend on the story language: you can work in the English interface on a Ukrainian story and vice versa.

## New story

When creating a story in the library, choose the **Story language**: Ukrainian (the default) or English. The language determines:

- the standard prompts of all roles and the context headings the model sees;
- the outline and character templates for [import](imports.md): an English story uses the `Scene 1:` and `Characters:` headings;
- the language hints after editing;
- the default language of the publication card.

Until the story contains any model-generated text, you can change the language in **Settings → Writing → Story language**. After the first generation the language is fixed: the field is disabled and explains why.

## Prose language of a single scene

The **Prose language** field in the scene card lets you write one scene in another language. **As the story** means the story language. The model instructions stay in the story language, and the model receives a note on which language to write this scene's prose in. Changing the prose language marks the scene draft and prose as outdated; the brief and memory are not affected.

## What differs for English prose

- **Language hints** check only mixed alphabets and repeated words; the Ukrainian rules do not apply.
- **Negation protection** in targeted edits also covers English `not`, `cannot`, `n't`.
- **Evaluation** of English prose is not available yet: the evaluation buttons are disabled with an explanation, because the [evaluator](evaluator.md) was calibrated on Ukrainian texts.
- A model preset remembers the language of the story it was saved from. Applying it to a story in another language shows a warning: your own prompts are not translated.

## Story length

The target length is set in **Settings → Writing → Story target word count**. Recommended up to 15,000 words; the minimum is 5,000 for a story and 1 for a scene, the defaults 7,000 and 1,000. Larger values are saved without truncation, but the model context still limits generation. Changing the story target does not redistribute the scene targets.
