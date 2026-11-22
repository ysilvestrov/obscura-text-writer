# Model recipes

A recipe is a starting point, not a promise. Model lists and prices change: every recipe below was checked against the providers' live model lists on **2026-11-17** (the cheap Venice planner and memory on **2026-11-22**), and the skill checks each model again after writing it (step 7 of `setup-models`).

Prices are $ per 1M tokens, input/output, as the provider listed them on that date. Only the standard key names are used — `OPENROUTER_API_KEY`, `VENICE_API_KEY` — because the chat cannot set a role's key name.

## Rule: the writer and the editor are different models

An editor that is the writer's own model barely corrects anything. In every recipe the writer and the editor are different models, from different families where possible. Keep this rule when you look for a replacement.

## Uncensored — Venice (`VENICE_API_KEY`), checked 2026-11-17 and 2026-11-22

| Budget | planner | writer | editor | memory |
|---|---|---|---|---|
| Cheap | `glm-5-3-flash-uncensored` (0.165/0.55) | `deepseek-v4-1-flash-1017-uncensored` (0.33/1.32) | `glm-5-3-flash-uncensored` | `glm-5-3-flash-uncensored` |
| Balanced | `deepseek-v4-1-flash-1017-uncensored` | `deepseek-v4-1-flash-1017-uncensored` | `qwen-3-6-plus` (0.625/3.75) | `deepseek-v4-1-flash-1017-uncensored` |
| Quality | `deepseek-v4-1-flash-1017-uncensored` | `aion-labs-aion-3-5` (3.75/7.5) | `qwen-3-6-plus` | `deepseek-v4-1-flash-1017-uncensored` |

## Normal rating — OpenRouter (`OPENROUTER_API_KEY`), checked 2026-11-17

| Budget | planner | writer | editor | memory |
|---|---|---|---|---|
| Cheap | `google/gemma-4-26b-a4b-it` (0.0765/0.255) | `deepseek/deepseek-v4-flash` (0.09/0.18) | `z-ai/glm-5.3-flash` (0.0399/0.0784) | `google/gemma-4-26b-a4b-it` |
| Balanced | `deepseek/deepseek-v4-flash` | `deepseek/deepseek-v4.1-flash` (0.3/1.2) | `qwen/qwen3.7-plus` (0.32/1.28) | `deepseek/deepseek-v4-flash` |
| Quality | `anthropic/claude-sonnet-5.5` (2/10) | `anthropic/claude-sonnet-5.5` | `openai/gpt-6.1-sol` (2/10) | `deepseek/deepseek-v4.1-flash` |

A story with a normal rating whose author has only a Venice key takes the uncensored recipe of the same budget.

Venice removes `gemma-4-uncensored` on 2026-12-01; its catalog names `glm-5-3-flash-uncensored` as the replacement, which the cheap recipe now uses for the planner and memory. The editors are kept until the editor comparison is done.

## Families for replacements

When a model is missing, search the role's model list by its family: `gemma`, `glm`, `deepseek`, `qwen`, `aion`, `claude-sonnet`, `gpt`.

## Known limits

- The cheap planners have a small context window. Obscura's "Suggest" button for the book's annotation currently uses the planner role and may not fit a long book; the `publish` skill writes the annotation in the chat instead.
