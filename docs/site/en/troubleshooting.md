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
| Key or authentication error | Check the key in `.env` and restart the server. |
| The request does not fit the context | Shorten the materials, lower the response reserve or choose a model with a larger real context. Text is never silently cut. |

## While working

| What you see | What to do |
|---|---|
| The model refused | There is no automatic retry. Change the brief or the model and run the stage again. |
| A run was interrupted by a failure or a server shutdown | An unfinished run becomes interrupted. Continue it explicitly; repeating a cloud call may cost money. |
| A material is marked outdated | Its sources changed. Regenerate it, or in the version history press **Review and accept text** and then **Continue after accepted stage**. |
| "Changed in another tab" | Your edits stay in the form. Refresh the data and repeat the action. |
| A cost "needs reconciliation" | After a failure the cost is unknown. Reconcile the amount in **Call history and reconciliation** once the run is over. |

## Export

| What you see | What to do |
|---|---|
| FB2 asks for an author or a genre | Fill them in on the publication card and press **Save card**. |
| The publication extras are required | Install them with the command from [Installation](install.md#installing-from-source). |
| Export asks for permission | Some scenes need review or have no prose. Allow an incomplete export or finish the scenes first. |

## Backups

Before an update or an experiment, make a backup as described in [Backup](install.md#backup). A restore creates a new directory and overwrites nothing. If a backup or restore was interrupted, do not use the incomplete directory: repeat the action from a verified copy into a new directory.
