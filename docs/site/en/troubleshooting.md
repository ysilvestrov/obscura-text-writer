# Troubleshooting

## Launch

| What you see | What to do |
|---|---|
| PowerShell does not run `start.ps1` | Use the direct launch command from [Installation](install.md#launch). |
| The port is busy | Start with another port, for example `-Port 8770`. |
| "This data directory is already open by another worker" | Another server is already using this directory. Close its PowerShell window or choose another data directory. |
| The page behaves oddly after an update | Save your edits, restart the server and reload the tab. |

## Generation does not start

| What you see | What to do |
|---|---|
| Asks you to set an age rating | Set the rating in the story settings, **Writing** section. See [Age rating](content-rating.md). |
| Blocked because of character age | Add `Age:` to the card, remove the character from the scene cast, or change the scene rating. See [Character age](content-rating.md#character-age). |
| "Set an explicit story budget limit first" | Set the total limit in **Call budget**. See [Call budget](models.md#call-budget). |
| "No valid pricing" | Press **Update from catalog** or save manual pricing. |
| "Insufficient … budget" | Raise the total or the per-run limit. The reserve is conservative and counts the full response. |
| "Output limit exhausted… reasoning" | The model spent the whole response limit on reasoning. For OpenRouter turn **Reasoning** off or lower it in the role; for Venice use reasoning effort; for a local model, thinking. See [Reasoning on OpenRouter](models.md#reasoning-on-openrouter). |
| Key or authentication error | Check the key in `.env` and restart the server. |
| The request does not fit the context | Shorten the materials, lower the response reserve or choose a model with a larger real context. Text is never silently cut. |

## While working

| What you see | What to do |
|---|---|
| The model refused | There is no automatic retry. Change the brief or the model and run the stage again. |
| A run was interrupted by a failure or a server shutdown | An unfinished run becomes interrupted. Continue it explicitly; repeating a cloud call may cost money. |
| A material is marked outdated | Its sources changed. Regenerate it, or in the version history press **Review and accept text** and then **Continue after accepted stage**. If a brief or prose is “Unchecked” and you are sure it matches, approve it on the panel below the scene text ([scene status](workspace.md#scene-status-valid-or-unchecked)). |
| A run is refused: “Memory is being carried” | After the previous scene gets a new memory, Obscura updates the memory of later scenes. Wait for the carry to end (it shows as **Memory carry** in the run summary). If the carry stopped with a warning, create a new memory for the named scene or rebuild memory from it; if it is paused or was interrupted, resume or cancel it on the scene panel ([carry](memory.md#carrying-memory-to-later-scenes)). |
| “The auditor could not check this link: The check input exceeds the auditor’s limit…” | The link’s input is larger than the auditor’s limit. Press **Open auditor settings**, raise the input limit and context or choose a model with a larger context, then press **Check scene** again. The token estimate is conservative, so the limit may trigger earlier than needed. Such a link cannot be approved. See [Auditor](models.md#auditor). |
| “The scene was changed during the check several times in a row” | Three times in a row the auditor gave a verdict for a scene that changed meanwhile. Finish your edits and press **Check scene** again. |
| “Role is not configured: Auditor” | An unsaved auditor uses the editor’s model: configure the **Editor** or save the **Auditor**’s own settings. |
| "Changed in another tab" | Your edits stay in the form. Refresh the data and repeat the action. |
| A cost "needs reconciliation" | After a failure the cost is unknown. Reconcile the amount in **Call history and reconciliation** once the run is over. |
| The text has «�» characters, such as «p��lm» | The provider lost a letter in transit; it cannot be recovered. The app does not save memory or classification with such words: run the stage again. Damaged editor edits are dropped and the rest are shown. In prose, a banner above the editor shows the count: **Next** selects the next one, fix the word by hand. On Venice these memory and edit stages show no live text: the screen says "Waiting for the full model answer". |

## Export

| What you see | What to do |
|---|---|
| FB2 asks for an author or a genre | Fill them in on the publication card and press **Save card**. |
| The publication extras are required | Install them with the command from [Installation](install.md#installing-from-source). |
| Export asks for permission | Some scenes need review or have no prose. Allow an incomplete export or finish the scenes first. |

## Backups

Before an update or an experiment, make a backup as described in [Backup](install.md#backup). A restore creates a new directory and overwrites nothing. If a backup or restore was interrupted, do not use the incomplete directory: repeat the action from a verified copy into a new directory.
