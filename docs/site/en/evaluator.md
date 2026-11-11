# Evaluator

The evaluator is a separate model that checks a finished scene or story against criteria: language, consistency with the outline and earlier scenes, editing. It does not change the text; it produces a report with quotations. A model assessment is a helper tool, not a literary verdict.

## Setup

1. Open the story settings → **Evaluator**.
2. Enter the provider, model, context, response reserve, temperature and input limit, as for the [other roles](models.md#role-settings).
3. Press **Save: Evaluator**.
4. Tick **Enable evaluator · saved immediately**. The checkbox uses the model already saved, so save a new evaluator first.

A model preset does not configure the evaluator automatically. **Criteria and thresholds** are in an additional form. **Technical JSON** is an optional mode for experienced users: changes in it apply only with the Apply button.

Tested starting configuration for "report only": Venice, model `qwen-3-8-27b`, context 262144, response reserve 3000, temperature 0.1, response mode "schema in the prompt" (`prompt_json`), thinking disabled. This is an example, not a guarantee for every text.

## Modes

- **Off** — the evaluator is not called.
- **Report only** — reports and warnings; a problem or an error does not stop generation. Start with this mode.
- **Pause on failure** — generation stops if an evaluation fails, is incomplete or ends with an error. This mode is available only for a calibrated profile; without calibration it cannot be enabled.

A new profile gives preliminary findings with the status "incomplete", even when the preliminary verdict is positive. This is expected, not a failure.

## Running

On the workspace page press **Evaluate scene** or **Evaluate story** and confirm. Evaluation of English prose is not available yet (see [Story language](story-language.md#what-differs-for-english-prose)). The evaluation runs through the shared queue together with other stages. The report shows findings, quotations and coverage. A matching quotation proves the passage is in the text, not that the evaluator understood it correctly.

## Errors

| What you see | What to check |
|---|---|
| Missing key / authentication error | The key in `.env` or in the "Provider key" block, and the variable name in the settings |
| Quota / rate limit | Balance or rate limits at the provider |
| Timeout / connection | API availability and the timeout |
| Incomplete response | The response reserve and the model's format support |
| Not enough context | The model's real context, the response reserve and the request size |
| Refusal | The model refused to evaluate the text; this is not a technical error |

After a content refusal, the evaluator is **blocked for this story**: later scenes are not sent to it. Changing the prompt or temperature, or restarting, does not lift the block. Choose another model or turn the evaluator off. Technical errors create no block, and there are no automatic retries.
