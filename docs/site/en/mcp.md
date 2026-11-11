# Chat clients (MCP)

You can connect Obscura to a chat client you already use: Claude Desktop, Claude Code or Codex. The chat reads a scene's plan, cards and memory, writes a draft with its own model and saves it in Obscura. You need no API key of your own: the model runs under the chat client's account, and Obscura calls no model itself.

The link is `storygen-mcp`, a small program the chat client starts by itself. It talks to the Obscura running on your computer and nowhere else.

## What the chat can do

The chat gets six tools:

- **story list** and **story overview**: scenes, their order and their state, in the same words as the scene list;
- **scene context**: the plan, the brief, the cast's cards, the memory of earlier scenes, the age rating, the language and the target length;
- **import a plan and characters**: the same as the [import](imports.md) form;
- **save a draft**: a new version of the scene's draft;
- **next steps**: a link to the scene in Obscura.

The chat cannot delete, publish, run generation or the evaluator, or change settings and keys.

## Installation

`storygen-mcp` is part of the regular [installation](install.md). If you installed Obscura earlier, repeat the two install commands in the application folder to add the new dependencies:

```powershell
./.venv/Scripts/python.exe -m pip install -r requirements-lock.txt
./.venv/Scripts/python.exe -m pip install --no-deps -e ".[web,publication]"
```

`storygen-mcp.exe` then appears in `.venv/Scripts/`. The examples below use `C:\Obscura` as the application folder; use your own.

## Connecting

Start Obscura as usual before you work. The chat client connects to `http://127.0.0.1:8765`. If Obscura runs on another port, add the arguments `--url http://127.0.0.1:<port>`.

**Claude Code.** In a terminal:

```powershell
claude mcp add --scope user obscura -- C:\Obscura\.venv\Scripts\storygen-mcp.exe
```

`--scope user` makes the server available in any folder. Without it, Claude Code sees the server only in the folder where you ran the command.

**Claude Desktop.** Open "Settings → Developer → Edit Config", add the server to `claude_desktop_config.json` and restart Claude Desktop:

```json
{
  "mcpServers": {
    "obscura": {
      "command": "C:\\Obscura\\.venv\\Scripts\\storygen-mcp.exe"
    }
  }
}
```

For another port add `"args": ["--url", "http://127.0.0.1:8770"]`. In the `claude mcp add` and `codex mcp add` commands the arguments go after the program path: `… storygen-mcp.exe --url http://127.0.0.1:8770`.

**Codex.** In a terminal:

```powershell
codex mcp add obscura -- C:\Obscura\.venv\Scripts\storygen-mcp.exe
```

Or add a `[mcp_servers.obscura]` section with the line `command = 'C:\Obscura\.venv\Scripts\storygen-mcp.exe'` to `~/.codex/config.toml`.

Browser chat clients (claude.ai, chatgpt.com) do not support local servers.

## Writing with the chat

1. Discuss the idea, the plan and the characters with the chat.
2. Ask it to import the plan and the characters into the story. You can create an empty story in Obscura beforehand. The import adds materials the same way as the form and is never retried on its own.
3. Ask it to read the first scene's context and write a draft. The chat saves it as the scene's current draft.
4. Open the scene in Obscura from the link in the chat. The previous draft, if there was one, stays in the version history.
5. Rewrite the draft in your own words in [rewriting from memory](ghost-mode.md), approve the prose and update the scene's [memory](memory.md).
6. Move on to the next scene.

A draft from the chat is labelled "External client: <name>" in the version history and in the status row above the editor. If the chat named its model, the model is shown too. This is the client's claim: Obscura cannot check which model actually wrote the text. Once you save your own edit, the label leaves the status row; in the history it stays next to the chat's version.

## Limitations

- Obscura must be running. Otherwise the chat gets the error "Obscura не запущено за адресою …" (Obscura is not running at …).
- The next scene's context can be read only after the previous scene's memory is updated, just as for generation in Obscura.
- If the scene was changed after the context was read, the save is refused with "Сцену вже змінено" (the scene has already been changed). If the cards, the rating, the story language or the memory of earlier scenes changed, it is refused with "Контекст сцени змінився — прочитайте його знову" (the scene context changed, read it again). Either way, ask the chat to read the context again.
- The chat sees Obscura's errors with the prefix "Error executing tool …", followed by Obscura's code and explanation.
- A draft from the chat counts as model-made material: after it, the story language can no longer be changed.
- Obscura does not evaluate a draft from the chat automatically and does not count it in the [budget](models.md). The cost falls on the chat client's account.
- Regular chat clients may refuse to write explicit scenes. Obscura does not work around that.
