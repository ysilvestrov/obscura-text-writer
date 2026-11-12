# Chat clients (MCP)

You can connect Obscura to a chat client you already use: Claude Desktop, Claude Code or Codex. The chat reads a scene's plan, cards, memory and texts, writes a draft with its own model and saves it in Obscura. You need no API key of your own: the model runs under the chat client's account, and Obscura calls no model itself.

The link is `storygen-mcp`, a small program the chat client starts by itself. It talks to the Obscura running on your computer and nowhere else.

## What the chat can do

The chat gets twenty-five tools:

- **story list** and **story overview**: scenes, their order and their state, in the same words as the scene list, plus the story's rating, target length and characters;
- **new story**: a title, a language, a target length, the story mode and, optionally, an age rating;
- **plan and character templates**: the same files the story page offers;
- **story properties**: the title, the language and the age rating;
- **new scene** at the chosen place in the story, with a plan or modelled on the previous scene;
- **scene plan and properties**: the plan (only over the plan the chat has read), the title, the length, the cast and the prose language;
- **scene context**: the plan, the brief, the cast's cards, the memory of earlier scenes, the age rating, the language and the target length;
- **scene text**: the scene's current plan, brief, draft, prose or memory together with the ID of the current version; the chat reads a long text in parts;
- **import a plan and characters**: the same as the [import](imports.md) form;
- **save a draft**: a new version of the scene's draft, only over the draft the chat has read;
- **link to rewriting from memory**: a link that opens [Ghost Mode](ghost-mode.md) for the scene's current draft;
- **next steps**: a link to the scene in Obscura;
- **publication card**: reading the [card](publication.md) and changing chosen fields over the card the chat has read, with the FB2 genre catalogue;
- **new signature** in the shared author and pen-name directory;
- **cover** from a file on your computer;
- **book export** to FB2, EPUB, PDF, MD or TXT: the chat gives a link to the finished file;
- **story settings**: reading the writing profile, [role models](models.md), key state and presets, and on request the prompts and the provider's model list;
- **settings changes**: chosen fields of the writing profile or of one role, over what the chat has read;
- **role preset**: a preview and, with your consent in the chat, applying a saved preset;
- **stage task**: the instructions and material for the scene brief, editing or memory — the same as an Obscura model would get;
- **stage result**: the chat's answer to a stage task, which Obscura checks the same way as its own model's answer;
- **run**: in an "Obscura writes" story, a preview and, with your consent in the chat, an Obscura model run of one scene stage or a publication card suggestion;
- **run status**: what is happening with a run now, its result, and cancelling a run the chat started.

The chat cannot delete stories or scenes, move them to the trash, reorder scenes, run generation, synopsis suggestions or the evaluator, or change prompts, the evaluator, the budget and keys.

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

## Publishing from the chat

The chat can fill in the publication card, add an author signature, set a cover and export the book.

- The chat changes only the card fields you named; the rest stays. If the card was changed after the chat read it, the write is refused with code 409, and the chat has to read the card again.
- The chat takes FB2 genres from the same catalogue as the card page.
- The chat reads the cover from a file on a local disk: give the full path, for example `C:\Users\…\cover.png`. PNG and JPEG up to 10 MiB work. Copy a file from a network drive or a shared folder to your own disk first. An uploaded cover becomes part of the card only when the chat writes it there.
- Export returns a link to the file in Obscura. The chat exports an unfinished story only with your explicit permission, and FB2 needs an author and a genre in the card.
- If the card page is open, you will see the chat's changes when you return to it. Unsaved edits in the form stay, and the page says the card was changed elsewhere.

## Settings from the chat

The chat can change the genre, tone, point of view, style rules and story length, choose a provider and a model for a role, change the context, temperature or editor mode, and apply a saved role preset.

- The chat changes only the named fields of one section: the writing profile or one role. If you changed that section after the chat read it, the write is refused with code 409, and the chat has to read the settings again. New scenes or a title change do not get in the way.
- The chat does not see keys: only whether a key exists and where it is (an environment variable or the key store). Only you change the key variable name. When the chat switches the provider, the role takes the new provider's standard key and address.
- The chat shows a preset first and applies it only after confirmation. You apply a preset whose key name is not among the story's roles yourself on the settings page.
- These tools do not call models, but the chosen model sets the cost of your next runs in Obscura. The chat does not change the story budget.
- Role settings have no version history. The chat sees what changed in the tool's answer: ask it to show you. You can save a preset before a big change.
- If the settings page is open, you will see the chat's changes when you return to it. Unsaved edits stay, and the page says the settings were changed elsewhere.

## Who writes the texts

Each story has a mode: **The chat writes** or **Obscura writes**. A story created by the chat has the **The chat writes** mode by default; the new story form in Obscura has **Obscura writes** selected by default. The story list and the story details in the chat show the mode.

- **The chat writes**: the chat writes drafts and goes through the scene stages itself, as described below.
- **Obscura writes**: Obscura models write the texts. The chat still reads the story, imports the plan and characters, changes the settings and the publication, but Obscura refuses a draft or a stage result from it with the message: The story is in the "Obscura writes" mode: start the stage with start_run. Instead, the chat can start the stage with an Obscura model (see below).
- In the **The chat writes** mode it is the other way round: the chat cannot start Obscura models, it writes itself.
- Only you change the mode: in the story settings, **Writing** section, the **Who writes the texts** field. The chat cannot change it. Changing the mode does not touch texts already written or stages already started.

## Obscura runs from the chat

In a story with the **Obscura writes** mode the chat can ask Obscura to run one scene stage — the scene brief, the draft, editing or memory — or to suggest a publication card. This is an ordinary Obscura run: your role models, the story budget and the same readiness check as for the buttons.

- First the chat shows a preview: which models will work, how many calls there will be, warnings and the remaining story budget. It starts the run only after your consent in the chat.
- **A run costs money** at the rates of the role models. Cloud providers need a story budget limit, as for the buttons. The chat can pass a limit for one run. Obscura does not estimate the amount in advance: the preview shows the models and the budget.
- The run goes in the background. The chat checks its status with a separate request; it reads the finished text like other scene texts, and card suggestions come with the run status.
- The chat can cancel only a run it started itself. Pausing, resuming, your runs, a whole scene, the rest of the story, preparation, evaluation, the impact check and the book review stay with you: Obscura refuses such requests from the chat.
- If the previous memory needs your confirmation, the memory stage does not start: the chat advises you to confirm it in Obscura.
- You accept changes that wait for your decision in Obscura, as after a run started with a button.

## Scene stages from the chat

The chat can go through every stage of a scene itself: write the scene brief, write the draft, edit it and update the memory. For each stage it gets the same instructions as an Obscura model: the standard prompts or your own, the role settings, the story language, the rating and the memory of earlier scenes. For the draft, the writer's instructions come with the scene context.

- Obscura checks the chat's answer with the same code as its own model's answer. It does not save a wrong answer even in part, and returns all the violations to the chat at once. After three refusals in a row the chat should stop and show you the violations.
- If the scene, the role settings or the prompt changed between the task and the answer, the answer is refused, and the chat takes the task again.
- A result from the chat behaves like a model result: a brief with significant changes waits for your decision, editing in the edit-selection mode goes to "Editor changes", and the memory becomes current. You confirm the memory core, as for a model.
- If the previous prose changed after its memory, the chat does not get the memory task: you confirm the use of the previous memory in Obscura.
- In the version history such versions are marked "External client: <name>". Prose edited by the chat is an editing version with this mark.
- These tools cost no money and are not counted in the budget. If a role is not configured, Obscura uses the chat's typical context limits; it does not know the chat's own window.

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
