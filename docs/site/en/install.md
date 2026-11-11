# Installation and launch

## Requirements

- Windows 10 or 11.
- [Python](https://www.python.org/downloads/) 3.10 or newer.
- A model API: a local OpenAI-compatible server (for example LM Studio) or an OpenRouter or Venice account.

## Installer

A Windows installer will come later (#30). Until then, install the application from source with the steps below.

## Installing from source

Download the [obscura-text-writer](https://github.com/ysilvestrov/obscura-text-writer) repository and open PowerShell in its folder:

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements-lock.txt
./.venv/Scripts/python.exe -m pip install --no-deps -e ".[web,publication]"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

The last command creates `.env` only when the file does not exist yet, so running the block again does not erase your keys.

## Provider keys

Open `.env` in a text editor and fill in the key only for the provider you will use:

- `OPENROUTER_API_KEY` for OpenRouter;
- `VENICE_API_KEY` for Venice (only models with `uncensored=true`).

A local provider needs no key. Keys stay on your computer; do not publish the `.env` file.

## Launch

Keep personal stories in a separate folder outside the application folder:

```powershell
./scripts/start.ps1 -DataDir "$env:LOCALAPPDATA/ObscuraTextWriter/data"
```

The browser opens `http://127.0.0.1:8765`. The server listens only on your computer. The `-Port` parameter sets another port, for example `-Port 8770`. Stop it with `Ctrl+C` in the PowerShell window.

If running PowerShell scripts is not allowed, use the direct command:

```powershell
./.venv/Scripts/python.exe -m storygen.server --data-dir "$env:LOCALAPPDATA/ObscuraTextWriter/data" --env-file .env --open-browser
```

## Models

After the first launch open **Settings → Models** and, for each role, set the provider, the API address, the exact model ID and the limits. A local server usually listens on `http://localhost:1235/v1`. The model list button shows available IDs and known prices.

## Backup

Stop the server before copying. The built-in backup checks integrity and hashes:

```powershell
./.venv/Scripts/storygen.exe backup --data-dir "$env:LOCALAPPDATA/ObscuraTextWriter/data" --destination "D:/Backups/obscura-2026-11-11" --json
./.venv/Scripts/storygen.exe restore --backup-dir "D:/Backups/obscura-2026-11-11" --destination "D:/Restored/obscura" --json
```

Destination parent folders must exist. Restore creates only a new folder and overwrites nothing. You can also copy the **whole** data folder of a stopped server; do not copy the database apart from the texts.

To check the data folder without changing it, run `./.venv/Scripts/storygen.exe fsck --data-dir "<folder>" --json`. It reports problems but repairs and deletes nothing. If a backup or restore was interrupted, do not use the incomplete folder: repeat the restore from a verified backup into another new folder.

## Updating

Save manual edits, stop the server, update the code and start the server again. The data schema is updated when the storage opens. After a crash, unfinished runs are marked interrupted and continue only on your command.
