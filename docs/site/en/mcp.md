# Chat clients (MCP)

You can connect Obscura to a chat client you already use: Claude Desktop, Claude Code or Codex. The chat reads a scene's plan, cards, memory and texts, writes a draft with its own model and saves it in Obscura. You need no API key of your own: the model runs under the chat client's account, and Obscura calls no model itself.

The link is `storygen-mcp`, a small program the chat client starts by itself. It talks to the Obscura running on your computer and nowhere else.

## What the chat can do

The chat gets thirteen tools:

- **story list** and **story overview**: scenes, their order and their state, in the same words as the scene list, plus the story's rating, target length and characters;
- **new story**: a title, a language, a target length and, optionally, an age rating;
- **plan and character templates**: the same files the story page offers;
- **story properties**: the title, the language and the age rating;
- **new scene** at the chosen place in the story, with a plan or modelled on the previous scene;
- **scene plan and properties**: the plan (only over the plan the chat has read), the title, the length, the cast and the prose language;
- **scene context**: the plan, the brief, the cast's cards, the memory of earlier scenes, the age rating, the language and the target length;
- **scene text**: the scene's current plan, brief, draft, prose or memory together with the ID of the current version; the chat reads a long text in parts;
- **import a plan and characters**: the same as the [import](imports.md) form;
- **save a draft**: a new version of the scene's draft, only over the draft the chat has read;
- **link to rewriting from memory**: a link that opens [Ghost Mode](ghost-mode.md) for the scene's current draft;
- **next steps**: a link to the scene in Obscura.

The chat cannot delete stories or scenes, move them to the trash, reorder scenes, publish, run generation or the evaluator, or change writing settings, models and keys.

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

**Claude Desktop.** Add the server to the settings file `claude_desktop_config.json`. Where the file is depends on how Claude Desktop was installed:

- the Microsoft Store version — `%LOCALAPPDATA%\Claude-Data\claude_<identifier>\claude_desktop_config.json` (there is a single `claude_` folder with letters and digits);
- the regular installer — `%APPDATA%\Claude\claude_desktop_config.json`.

The file may already hold the application's own settings: keep them and add an `mcpServers` section next to them. While Claude Desktop runs, it rewrites this file itself, so first quit the application completely, including its icon in the notification area. Then save the file and start Claude Desktop again. A file with only this server looks like this:

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
2. Ask it to import the plan and the characters into the story. The chat can create the story itself (see below), or you create it in Obscura beforehand. The import adds materials the same way as the form and is never retried on its own.
3. Ask it to read the first scene's context and write a draft. The chat saves it as the scene's current draft.
4. To extend or rewrite an existing draft, ask the chat to read it first. The chat writes over the text it has read, so the edits you made in Obscura are not lost.
5. Open the scene in Obscura from the link in the chat. The previous draft, if there was one, stays in the version history.
6. Rewrite the draft in your own words in [rewriting from memory](ghost-mode.md), approve the prose and update the scene's [memory](memory.md). Ask the chat for a rewriting link: it opens the mode right away, without looking for the scene and the button.
7. Move on to the next scene.

## Start a story from the chat

Ask the chat to create a story: a title, a language (Ukrainian or English) and, if you like, an age rating. The chat then takes the plan and character templates, fills them in with you and imports them. After that it can add scenes, rewrite a scene plan, and change the story's title, language or rating.

- Creating a story does not fix its language. The language can be changed while the story has no text from a model or the chat. Plans, titles and characters written from the chat do not fix it either.
- In the Microsoft Store edition a rating above the edition limit is refused, and the story is then not created.
- The chat rewrites a scene plan only over the plan it has read. If you changed the plan after the chat read it, the write is refused with "План сцени змінено після того, як його прочитали" (the scene plan was changed after it was read) and nothing is saved.
- The previous plan stays in the scene's version history. A plan from the chat is not marked separately there: it is your authored material.
- The chat changes several story properties one after another. If one of them is refused (for example, the language is already fixed), the rest are not changed, and the chat reports what it managed to apply.
- You delete unneeded stories in Obscura: the chat cannot do that.

A draft from the chat is labelled "External client: <name>" in the version history and in the status row above the editor. If the chat named its model, the model is shown too. This is the client's claim: Obscura cannot check which model actually wrote the text. Once you save your own edit, the label leaves the status row; in the history it stays next to the chat's version.

You can keep Obscura open next to the chat. When you return to the Obscura window, the page checks on its own whether the chat wrote anything. If the editor has no unsaved edits, you see the new draft right away. If it has, your text stays, and "The scene was changed elsewhere" appears above the editor with an "Open the newer version" button; it asks for confirmation before replacing the text.

## Limitations

- Obscura must be running. Otherwise the chat gets the error "Obscura не запущено за адресою …" (Obscura is not running at …).
- The next scene's context can be read only after the previous scene's memory is updated, just as for generation in Obscura.
- If the scene was changed after the context was read, the save is refused with "Сцену вже змінено" (the scene has already been changed). If the cards, the rating, the story language or the memory of earlier scenes changed, it is refused with "Контекст сцени змінився — прочитайте його знову" (the scene context changed, read it again). Either way, ask the chat to read the context again.
- If the draft was changed after the chat read it (by you in Obscura or by another conversation), the save is refused with "Чернетку змінено після того, як її прочитали" (the draft was changed after it was read). Ask the chat to read the draft again and repeat its change over it.
- The chat sees only saved texts. It does not see unsaved edits in an open editor: save them before asking the chat to change anything.
- The chat sees Obscura's errors with the prefix "Error executing tool …", followed by Obscura's code and explanation.
- A draft from the chat counts as model-made material: after it, the story language can no longer be changed.
- Obscura does not evaluate a draft from the chat automatically and does not count it in the [budget](models.md). The cost falls on the chat client's account.
- Regular chat clients may refuse to write explicit scenes. Obscura does not work around that.
