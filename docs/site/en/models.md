# Models, roles and budget

Four roles prepare a scene: the **Planner** writes the outline and brief, the **Writer** writes the draft, the **Editor** suggests changes, and **Memory** records what happened. Each role can have its own model. The [evaluator](evaluator.md) is configured separately.

![Model settings](../../images/site/en/settings-models-desktop.png)

## Role settings

Open the story settings → **Models** and choose a role. Enter the provider, API address, exact model ID, context, response reserve and input limit. **Get model list** shows the available IDs and known prices. Save the role with the **Save:** button carrying the role name; other roles' settings stay unchanged.

Providers:

- **Venice** and **OpenRouter** are cloud providers: they need a key, either in `.env` or in the "Provider key" block under the model field (see [Installation](install.md#provider-keys)), and a call budget. Venice accepts only models with `uncensored=true`.
- **Local** is a server on your computer, such as LM Studio or Bionic; the default address is `http://localhost:1235/v1`. No key or budget is needed.
- **Codex CLI** uses your existing Codex sign-in; the text is sent to the Codex service.

The input limit in characters is a safeguard, not a token count. Before sending, the application estimates the tokens of the whole request and adds the response reserve; the sum must fit the context. Raising the numbers in the form does not increase the model's real context. Text is never silently cut: a request that does not fit is not sent.

## Model list

Instead of a field with suggestions, the role form and the connection block show the provider's catalog. At the top is the chosen model: its ID, badges, context, price and a **Change** button. Below are a search box, filters and a sortable table; the footer "Showing N of M" tells you how many models the filters hide.

Badges come only from catalog fields, never from the model name:

- **Uncensored** — the provider explicitly marked the model as uncensored.
- **TEE**, **Private**, **Anonymous** — the Venice privacy level. "Privacy unknown" means the catalog did not report the field, as with OpenRouter.
- **JSON Schema** — the catalog says the model supports structured output by schema.

Filters: search by name or ID, **Uncensored only**, **Privacy** (default "Private and above"; you can choose "any" or "TEE only") and **JSON Schema**. For providers that do not report privacy (OpenRouter, local) the privacy filter is inactive and models are shown with "privacy unknown". A missing field always means "unknown", never "yes" or "no".

Venice lists all online models, including those without Uncensored, but such a model cannot be chosen yet: a note beside it says the choice becomes available after the call rules are updated. An ID that is not in the catalog can be typed manually; it is kept and marked "not in catalog".

### JSON Schema mode

If a role or connection uses the **JSON Schema** response mode, the JSON Schema filter is on and locked, and models without schema support are visible but cannot be chosen. Changing the response mode rebuilds the list at once. If the already chosen model does not support JSON Schema, the form will not save, and the server also rejects such a save with an explanation: choose another model or the "JSON by prompt" mode. If the catalog is unavailable or support is unknown, saving is allowed and the app makes the final check before the call. In "JSON by prompt" mode the filter is ordinary and optional.

## Call budget

For Venice and OpenRouter open the story settings → **Call budget**:

1. Set **Total story limit, USD** and press **Save limits**. Without it no cloud model receives a request.
2. Optionally set a default per-run limit; on the workspace page you can change it for the next run.
3. For pricing choose the provider and the exact model ID and press **Update from catalog**. This request carries none of your text; the tariff is valid for 24 hours. You can also save manual pricing with a source and an end date.

The limit is cumulative: restarts, the bin and new attempts do not reset it. To allow more spending, raise the total.

What the amounts mean:

- **Confirmed** — the provider reported the cost, or you reconciled it by hand.
- **Calculated from tokens** — the actual token count × the tariff. An estimate, not a bill.
- **Reserved** — the request is sent, the result is not recorded yet.
- **Needs reconciliation** — the cost is unknown after a failure or cancellation. The reserve stays until you reconcile the amount in **Call history and reconciliation**.

The reserve before a call is conservative: it counts the whole request and the full response limit. This is an internal control, not a guarantee of the provider's bill. Local models and Codex have no dollar price: the application shows usage, not an invented zero. Missing token data is shown as "No data", an explicit zero as 0. Enable **Request streaming usage (if supported)** only when the endpoint supports it.

## Saved presets

The **Saved model presets** block stores the settings of the four roles together with their prompts, so you can apply them to another story.

1. Save all roles with the usual forms.
2. Expand **Save current settings or import a preset**, enter a name and press **Save preset**.
3. In another story choose the preset and version, press **Preview preset**, check the models and limits, and apply it. Unsaved form changes will be lost.

**Export JSON** and file import work without model calls. The JSON contains no keys, only environment variable names: on another computer add the key to `.env` separately. Do not put a key in a model name or a prompt. The evaluator can be added to a preset, but not its calibration.

Role settings and the writing profile can also be changed from a [chat client](mcp.md#settings-from-the-chat). When you return to an open settings page, it checks for changes from the chat or another tab by itself: without unsaved edits the page refreshes, and with edits it stays and says "Settings were changed elsewhere".

## Local models

A local model costs nothing, but large books need many calls and time. Tested profile for an 8 GB GPU: **Huihui-Qwen3.5-9B-abliterated Q4_K_M** with a 131072 context in Bionic, the **Planner** role, address `http://localhost:1235/v1`, response reserve 12288, temperature 0.1, JSON Schema and **Disable thinking (reasoning_effort=none)** enabled. This profile was tested for [impact review](revision.md); other roles can keep using cloud models.

The context estimate is conservative. If an answer does not fit its reserve or a quotation is not found in the text, the stage stops and keeps the finished parts; there are no automatic retries.
