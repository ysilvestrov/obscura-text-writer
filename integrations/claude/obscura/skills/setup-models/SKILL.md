---
name: setup-models
description: Use when an Obscura story in "obscura" writing mode has no configured model roles, when start_run reports that roles are not ready, or when the author asks which models to choose or how much a book will cost. Triggers include "налаштуй моделі", "яку модель вибрати", "скільки коштуватиме книжка", "ролі не налаштовано", "set up models", "which model should I use".
---

# Set up models: four roles from a goal

Read `${CLAUDE_PLUGIN_ROOT}/shared/rules.md` first and follow it throughout. It covers one question at a time, consent before writing, and progress lines.

In `obscura` writing mode, Obscura's own models write the book and the author pays the provider. This skill fills the four roles — `planner`, `writer`, `editor`, `memory` — from the author's goal, writes them, and checks each one against the provider's live model list. It never calls a model.

**API keys never pass through the chat.** If the author pastes a key into the chat, do not repeat it, do not save it anywhere, and change no settings in that session. Tell them to enter it in Obscura instead (step 3), and suggest revoking that key at the provider, since it has now been in a chat.

## 1. Read the current state

`get_settings(story_id)`. Note for each role:
- `configured`, `provider`, `model`, `fingerprint`;
- `key`: `source` is `env` or `store` when a key is there; a missing `key` or `source` means there is none.

Also note `presets` (the author's own saved role presets) and `preset_fingerprint`.

## 2. The goal

Ask only what you cannot see, one card each:

1. **Uncensored models needed?** Recommend "yes" when the story's sexual content rating is 1 or more, or its dark-themes rating is 2. This is a recommendation; the author decides.
2. **Budget for the book:** cheap / balanced / quality.
3. **Provider:** which of `openrouter` (key `OPENROUTER_API_KEY`) or `venice` (key `VENICE_API_KEY`) the author already has a key for. Skip the question if a configured role already shows a key.

## 3. No key

If the author has no key for any of the two providers: explain where to enter it in Obscura: the story's settings, the model of any role, the «Ключ провайдера» ("Provider key") block under the model choice; or the `.env` file next to Obscura. A saved key serves every story. Then wait. Do not continue until they say it is done; then start again from step 1.

## 4. The author's own preset

If one of `presets` fits the goal, offer it first:
1. `apply_role_preset(story_id, profile_id, version, expected_fingerprint=preset_fingerprint)` without `confirm` — show what changes;
2. on consent, the same call with `confirm=true`;
3. go to step 9, and say there that a preset's models were not checked against the live list.

## 5. Otherwise, a recipe

Take the recipe for the goal from `${CLAUDE_PLUGIN_ROOT}/skills/setup-models/references/recipes.md`. It gives a provider and a model for each of the four roles. A story with a normal rating but only a Venice key takes the uncensored recipe of the same budget.

## 6. One consent for the whole recipe

Show one table — role → provider, model, price per 1M tokens in/out — and say what happens next:
- the roles are written one by one;
- each is then checked against the provider's live model list;
- if a model is missing or does not fit, there will be a separate question.

Consent covers only that table.

## 7. Write and check

First keep, from the `get_settings` you just read, the current `provider`, `model`, `base_url`, `context_tokens`, `max_output_tokens` and `key.name` of every role (or "not configured").

Then for each role in turn:
1. `get_settings(story_id)` again and take this role's fresh `fingerprint`;
2. `update_settings(story_id, section=<role>, expected_fingerprint, fields={provider, model})`. For a role that is already configured, add `context_tokens: 8192` and `max_output_tokens: 2048`: Obscura refuses a model whose window is smaller than the role's saved limits, and step 4 raises them again;
3. `get_settings(story_id, models_for_role=<role>, models_query=<exact model id>)` and look for an exact `id` match in `models`. Check its `tariff` against the budget and, if uncensored is needed, `uncensored`. If the match has a `retirement` (the provider removes the model on `date`, with an optional `replacement`), tell the author the date and treat the model as unsuitable (step 8), offering the `replacement` first when there is one.
4. **Limits.** A new role gets Obscura's default window of 8192 tokens, too small for editing a scene or updating memory. On a match, `update_settings(fields={context_tokens, max_output_tokens})` with the fresh fingerprint: `context_tokens` = the model's `context_tokens`, at most 131072; `max_output_tokens` = the model's `max_output_tokens`, at most 8192 and always less than `context_tokens` (otherwise a quarter of it). An unknown (null) limit takes the maximum. If Obscura refuses the limits, halve them and try once more. These are upper bounds, not the size of each request.
5. **Editor reasoning (OpenRouter only).** A model that reasons by default can spend the whole output limit on reasoning and return no text. For the `editor` role with provider `openrouter`, read the match's `reasoning`. If it is null, or `default_enabled` is not `true`, change nothing. Otherwise `update_settings(fields={openrouter_reasoning_effort})` with the fresh fingerprint:
   - `mandatory` is false → `none` (reasoning off);
   - `mandatory` is true and `efforts` is a non-empty list → its last element (the list goes from highest to lowest);
   - `mandatory` is true and `efforts` is null → `low`;
   - `mandatory` is true and `efforts` is empty → change nothing; tell the author this model's reasoning cannot be set.

   Tell the author in one line what you set and that they can change it in the role's «Reasoning» field. Leave the other roles' reasoning as it is.

The role must be written before it can be checked: the server lists models only for a configured role. Writing changes no money by itself; the next runs will cost what the model costs.

If the check fails because the key is missing, roll this role back (step 8.4), then go to step 3.

## 8. Missing or unsuitable model

A model is unsuitable when its `id` is not in the list, `uncensored` is false while uncensored is needed, or its price is above the budget. Then:

1. **Find replacements:** `get_settings(models_for_role=<role>, models_query=<family>)` with the model's family from the recipe (`deepseek`, `gemma`, `qwen`…); if that is empty, without a filter. The answer holds at most 200 models: when `models_total` is above 200, narrow the filter instead of drawing conclusions from a partial list.
2. Offer a card with the 2–3 closest models: same family and size, price within the budget, uncensored if needed. **The writer and the editor must stay different models**, from different families where possible: an editor that is the writer's own model barely corrects anything.
3. On consent, `update_settings` with the chosen model and check it as in step 7.
4. **Roll back** when the author declines, there is no replacement or the check fails: `update_settings` with the role's kept `provider`, `model`, limits and, for `local`, `base_url`. The chat cannot set a key name: if the kept `key.name` is not the provider's standard one (`OPENROUTER_API_KEY`, `VENICE_API_KEY`), do not roll back; tell the author which role to restore in the story's settings. A role that was not configured before cannot be removed from the chat: tell the author it stays with an unchecked model and that they can change it in the story's settings.

## 9. Summary

List, for every role: what `changed` (from → to), the price per 1M tokens, the editor's reasoning setting if step 7.5 changed it, and any role left unchecked. Remind the author that the next runs will be paid to the provider at these prices, and that the next step is writing scenes with the `draft-scene` skill.
