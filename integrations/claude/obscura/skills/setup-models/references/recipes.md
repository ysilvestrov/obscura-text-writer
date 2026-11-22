# Model recipes

A recipe is a starting point, not a promise. Model lists and prices change: every recipe below was checked against the providers' live model lists on **2026-11-17** (the cheap Venice planner and memory, and every editor, on **2026-11-22**), and the skill checks each model again after writing it (step 7 of `setup-models`).

Prices are $ per 1M tokens, input/output, as the provider listed them on that date. Only the standard key names are used — `OPENROUTER_API_KEY`, `VENICE_API_KEY` — because the chat cannot set a role's key name.

## Rule: the writer and the editor are different models

An editor that is the writer's own model barely corrects anything. In every recipe the writer and the editor are different models, from different families where possible. Keep this rule when you look for a replacement.

## Uncensored — Venice (`VENICE_API_KEY`), checked 2026-11-17 and 2026-11-22

| Budget | planner | writer | editor | memory |
|---|---|---|---|---|
| Cheap | `glm-5-3-flash-uncensored` (0.165/0.55) | `deepseek-v4-1-flash-1017-uncensored` (0.33/1.32) | `glm-5-3-flash-uncensored` | `glm-5-3-flash-uncensored` |
| Balanced | `deepseek-v4-1-flash-1017-uncensored` | `deepseek-v4-1-flash-1017-uncensored` | `glm-5-3-flash-uncensored` | `deepseek-v4-1-flash-1017-uncensored` |
| Quality | `deepseek-v4-1-flash-1017-uncensored` | `aion-labs-aion-3-5` (3.75/7.5) | `glm-5-3-flash-uncensored` | `deepseek-v4-1-flash-1017-uncensored` |

## Normal rating — OpenRouter (`OPENROUTER_API_KEY`), checked 2026-11-17 and 2026-11-22

| Budget | planner | writer | editor | memory |
|---|---|---|---|---|
| Cheap | `google/gemma-4-26b-a4b-it` (0.0765/0.255) | `deepseek/deepseek-v4-flash` (0.09/0.18) | `google/gemma-4-31b-it` (0.2/0.4) | `google/gemma-4-26b-a4b-it` |
| Balanced | `deepseek/deepseek-v4-flash` | `deepseek/deepseek-v4.1-flash` (0.3/1.2) | `google/gemma-4-31b-it` | `deepseek/deepseek-v4-flash` |
| Quality | `anthropic/claude-sonnet-5.5` (2/10) | `anthropic/claude-sonnet-5.5` | `google/gemma-4-31b-it` | `deepseek/deepseek-v4.1-flash` |

A story with a normal rating whose author has only a Venice key takes the uncensored recipe of the same budget.

Venice removes `gemma-4-uncensored` on 2026-12-01; its catalog names `glm-5-3-flash-uncensored` as the replacement, which the cheap recipe uses for the planner and memory.

## Editors: why one per provider

The editors come from a comparison on 2026-11-22 (Obscura repository, `docs/research`, editor models for Ukrainian): Obscura's own five-pass edit loop on Ukrainian prose with 30 planted spelling, punctuation and russism mistakes per text.

- **Venice.** `glm-5-3-flash-uncensored` fixed as many mistakes as `qwen-3-6-plus` (the previous Balanced and Quality editor), on the sexual-content text too. It was about five times faster and a quarter of the price, and it kept the text whole, so every budget uses it. `qwen-3-6-plus` is the replacement of the same quality.
- **OpenRouter.** `google/gemma-4-31b-it` fixed the most mistakes and was the cheapest working editor. `openai/gpt-6.1-sol`, the previous Quality editor, did no better on the one text it ran at about 48 times the cost. `anthropic/claude-haiku-5.5` is close, but it is the Quality writer's family.
- **Reasoning models.** With the provider's default reasoning and the 8192-token output limit, `z-ai/glm-5.3-flash`, `qwen/qwen3.8-flash` and `qwen/qwen3.7-plus` spend the whole limit on reasoning and return no text. A re-run on 2026-11-22 with the role's reasoning set:
  - `qwen/qwen3.8-flash` and `qwen/qwen3.7-plus` with reasoning `none` fixed as many mistakes as `google/gemma-4-31b-it`, but were slower (51 s and 70 s per pass against 30 s); `qwen3.7-plus` cost three times as much. `qwen/qwen3.8-flash` with reasoning `none` is the replacement of the same quality and close in price.
  - `z-ai/glm-5.3-flash` cannot turn reasoning off; with `low` it once returned only the first fifth of the scene as a finished pass. Do not use it as an editor.

## Families for replacements

When a model is missing, search the role's model list by its family: `gemma`, `glm`, `deepseek`, `qwen`, `aion`, `claude-sonnet`, `gpt`.

## Known limits

- The cheap planners have a small context window. Obscura's "Suggest" button for the book's annotation currently uses the planner role and may not fit a long book; the `publish` skill writes the annotation in the chat instead.
