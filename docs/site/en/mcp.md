# Chat clients (MCP)

You can connect Obscura to a chat client you already use: Claude Desktop, Claude Code or Codex. The chat reads a scene's plan, cards, memory and texts, writes a draft with its own model and saves it in Obscura. You need no API key of your own: the model runs under the chat client's account, and Obscura calls no model itself.

The link is `storygen-mcp`, a small program the chat client starts by itself. It talks to the Obscura running on your computer and nowhere else.

## What the chat can do

The chat gets thirty-one tools:

- **story list** and **story overview**: scenes, their order and their state, in the same words as the scene list, plus the story's rating, target length and characters;
- **new story**: a title, a language, a target length, the story mode and, optionally, an age rating;
- **plan and character templates**: the same files the story page offers;
- **story properties**: the title, the language and the age rating;
- **outline preamble**: the title and general notes before the first scene, only over the version the chat has read;
- **new scene** at the chosen place in the story, with a plan or modelled on the previous scene;
- **scene plan and properties**: the plan (only over the plan the chat has read), the title, the length, the cast and the prose language;
- **scene context**: the plan, the brief, the cast's cards, the scene's locations with descriptions, the memory of earlier scenes, the age rating, the language and the target length;
- **scene text**: the scene's current plan, brief, draft, prose or memory together with the ID of the current version; the chat reads a long text in parts;
- **import a plan and characters**: the same as the [import](imports.md) form;
- **character cards**: reading all cards and, with your consent in the chat, renaming, new cards and entries, changing and removing entries (see [Character cards from the chat](#character-cards-from-the-chat));
- **import a manuscript**: a new book from a finished DOCX, Markdown or TXT file — a scene preview first, the book is created only after your consent (see [Importing a manuscript from the chat](#importing-a-manuscript-from-the-chat));
- **save a draft**: a new version of the scene's draft, only over the draft the chat has read;
- **link to rewriting from memory**: a link that opens [Ghost Mode](ghost-mode.md) for the scene's current draft;
- **next steps**: a link to the scene in Obscura;
- **publication card**: reading the [card](publication.md) and changing chosen fields over the card the chat has read, with the FB2 genre catalogue;
- **new signature** in the shared author and pen-name directory;
- **cover** from a file on your computer;
- **text cover** from the publication card in one of four palettes — when the chat has no access to files, such as Claude Desktop from the Microsoft Store build;
- **book export** to FB2, EPUB, PDF, MD, TXT, DOCX or RTF: the chat gives a link to the finished file;
- **story settings**: reading the writing profile, [role models](models.md), key state and presets, and on request the prompts and the provider's model list;
- **settings changes**: chosen fields of the writing profile or of one role, over what the chat has read;
- **role preset**: a preview and, with your consent in the chat, applying a saved preset;
- **stage task**: the instructions and material for the scene brief, editing or memory — the same as an Obscura model would get;
- **stage result**: the chat's answer to a stage task, which Obscura checks the same way as its own model's answer;
- **run**: in an "Obscura writes" story, a preview and, with your consent in the chat, an Obscura model run of one scene stage, the book memory build or a publication card suggestion; in any story, an auditor check of a scene or of the whole book the same way;
- **run status**: what is happening with a run now, its result, and cancelling a run the chat started;
- **guide**: the steps of the Obscura skills for chat clients that do not have the skills installed (see [Obscura skills](#obscura-skills)).

The chat cannot delete stories or scenes, move them to the trash, reorder scenes, run generation, synopsis suggestions or the evaluator, or change prompts, the evaluator, the budget and keys.

## Installation

`storygen-mcp` is part of the regular [installation](install.md). If you installed Obscura earlier, repeat the two install commands in the application folder to add the new dependencies:

```powershell
./.venv/Scripts/python.exe -m pip install -r requirements-lock.txt
./.venv/Scripts/python.exe -m pip install --no-deps -e ".[web,publication]"
```

`storygen-mcp.exe` then appears in `.venv/Scripts/`. The examples below use `C:\Obscura` as the application folder; use your own.

## Connecting

### The button in the library

The easiest way to connect is from the Obscura library: expand the “Connect to Claude” block.

- **Connect Claude Desktop** adds only the `obscura` entry to the Claude Desktop settings. The other settings stay, and a copy of the file before the change appears next to it (`claude_desktop_config.json.obscura-backup`). Obscura shows which file it wrote to and offers to restart Claude: it reads its settings only when it starts.
- **Restart Claude now** closes Claude Desktop together with the open conversation, including unsent text, and opens it again. **I will restart it myself** explains how to do it by hand: a closed window leaves Claude running, so quit from the Claude icon next to the clock (“Quit”) and open it again.
- **Another way** is the fallback when there is no settings file yet (Claude Desktop has never been started) or it has an unknown format. Obscura prepares the extension file `obscura.mcpb` in the stories folder and opens the folder. In Claude Desktop, open Settings → Desktop app → Extensions, drag the file into the window and click Install. Claude shows its standard warning about extensions outside its directory.
- **Connect Claude Code** runs `claude mcp add --scope user obscura` and checks the entry. The [Obscura skills](#obscura-skills) are installed together with the bridge. If Claude Code is not found or the skills were not installed, Obscura shows the commands with a “Copy” button.
- **Skills for Claude Desktop** puts the skill ZIP files into the stories folder and opens it (see [Obscura skills](#obscura-skills)).

The chat cannot connect or restart Claude by itself: only you do this, in Obscura.

### Codex buttons in the library

If config.toml is write-protected, check its permissions before trying again. A backup creation error stops the settings write. If the skill installation path changed or became unsuitable, review the folders and named backups; a partial result also requires checking what was actually restored.

Expand “Connect to Codex” and press the button with the same name. Obscura saves the obscura stdio server in CODEX_HOME/config.toml or USERPROFILE/.codex/config.toml. The button can create the file before Codex is installed. It explicitly enables obscura and replaces its HTTP settings with local stdio; other servers and policies are preserved. After “Codex settings saved”, open a new session or restart Codex. This confirms the file; check the live connection in the client itself.

Each change to an existing config.toml creates a unique .obscura-backup-* copy beside it; repeating an unchanged action creates no backup. Repair malformed TOML by hand first. To restore, close Codex, save any later edits and restore the chosen copy. You can copy the PowerShell command for manual setup from the same block.

“Install Codex skills” is a separate checkout action that installs five obscura-* skills and lists their names. MCP success does not confirm skill installation. For conflict, review the named author edits; for partial, also review installed and restored folders and backups before removing anything. Update and recovery details are in the skills section below. The skills button is disabled in Store/frozen builds. In this update, the Codex buttons target Obscura installed from source; acceptance of the Microsoft Store version is separate.

### By hand

Start Obscura as usual before you work. The chat client connects to `http://127.0.0.1:8760`. If Obscura runs on another port, add the arguments `--url http://127.0.0.1:<port>`.

If you start Obscura without a console through `storygen-desktop` ([installation](install.md)), add the arguments `--data-dir <stories folder>` instead of `--url` (by default `%USERPROFILE%\Obscura`). Then you do not need to start Obscura beforehand: on the chat's first request the bridge finds it on any port and, if it is not running, quietly starts it in the tray without a browser. Obscura stays in the tray after you close the chat; you can quit it from the tray icon.

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

**Codex.** For Obscura installed from Microsoft Store, run in a terminal:

~~~powershell
codex mcp add obscura -- obscura-mcp.exe
~~~

For a source checkout, use that checkout's own bridge (replace C:\Obscura with your folder):

~~~powershell
codex mcp add obscura -- "C:\Obscura\.venv\Scripts\storygen-mcp.exe"
~~~

`obscura-mcp.exe` is the installed build's bridge; `storygen-mcp.exe` in `.venv\Scripts` is the source checkout's bridge. If the checkout runs on another port, append `--url http://127.0.0.1:8770`; for a desktop-launcher instance with a separate library, use `--data-dir "C:\Obscura Library"`.

Alternatively, add a `[mcp_servers.obscura]` entry with `command` and optional `args` in `~/.codex/config.toml`. Preserve the rest of the file and keep a backup. With `CODEX_HOME` set, the file lives in that folder. Local Codex clients use the same configuration profile; open a new session or restart the client after changing it.

Browser chat clients (claude.ai, chatgpt.com) do not support local servers.

## Obscura skills

Skills are ready-made instructions for Claude that lead the conversation step by step: one question at a time, with a summary and your consent before every write. The chat works with Obscura without them too, but then you explain every step yourself. The `obscura` set has five skills:

- `start-story` — from an idea to a story with a plan and character cards;
- `series-bible` — a world bible for a cycle of books: articles on magic, organisations, geography, chronology;
- `draft-scene` — a scene stage by stage: brief, draft, edit, memory; in "Obscura writes" mode, runs of its models;
- `publish` — the publication card, a text cover and export to FB2, EPUB, PDF or a DOCX manuscript;
- `setup-models` — models for the four roles by genre and budget, checked against the provider's list.

**Claude Code.** The “Connect Claude Code” button in the library installs the skills together with the bridge (see [The button in the library](#the-button-in-the-library)). Obscura copies them into the stories folder, under `claude\marketplace`, so an Obscura update does not break them. Do not put your own files in that folder: a folder without Obscura's marker is left unchanged, and Obscura shows its path.

By hand, in the source version, after connecting the bridge, run in a terminal, replacing `C:\Obscura` with the folder where Obscura lives:

```powershell
claude plugin marketplace add "C:\Obscura\integrations\claude"
```

```powershell
claude plugin install obscura@obscura
```

**Claude Desktop.** Click “Skills for Claude Desktop”: Obscura puts one ZIP file per skill into the stories folder, under `claude\skills`, and opens that folder. In Claude, first turn on Settings → Capabilities → Code execution and file creation. Then, for each file: Customize → Skills → “+” → Create skill → Upload a skill. Obscura does not touch other files in the `claude\skills` folder.

**Other chat clients.** Codex and other MCP clients without the skills get the same steps through the guide tool: the chat calls it at the start of a task and then follows the steps it gets.

**Using them.** Just ask the chat, for example "I want to write a story about a lighthouse" or "set up models for my story", and Claude picks the right skill itself. You can also name a skill: `/obscura:start-story`, `/obscura:publish` and so on.

The skills do not accept API keys in the chat. If you send a key to the chat, the skill changes nothing and asks you to enter the key in Obscura's settings; it is better to revoke that key at the provider.

**Updating and removing.** A new version of Obscura updates the skills too. At launch it refreshes their copy in the stories folder, and Claude Code takes the new skills in the next session. After an Obscura update, prepare and upload the Claude Desktop ZIP files again. To remove the set from Claude Code:

```powershell
claude plugin uninstall obscura@obscura
```

```powershell
claude plugin marketplace remove obscura
```
## Codex skills from a source checkout

If Obscura reports an incomplete skill source, restore the checkout files and try again. This refusal does not change installed skills. A successful result lists each skill once and marks installed and already current skills. For a partial installation, review the separate groups of changed, restored and conflicting folders.

The Codex package is generated from the same sources as the Claude skills; no manual text copying is needed. It contains `obscura-start-story`, `obscura-series-bible`, `obscura-draft-scene`, `obscura-publish`, and `obscura-setup-models`. Planning and every scene stage use the current Codex session without automatically switching models.

First connect MCP as described above. Then run from the Obscura checkout folder:

~~~powershell
.\.venv\Scripts\python.exe .\scripts\install_codex_skills.py --install
~~~

Skills are saved in `%USERPROFILE%\.agents\skills`. `CODEX_HOME` changes the MCP configuration folder, but not this skills folder. If skills do not appear, open a new session or restart Codex. Ask to “start a story” or explicitly mention `$obscura-start-story`.

To inspect the package without installing it, generate into a new or empty folder:

~~~powershell
.\.venv\Scripts\python.exe .\scripts\install_codex_skills.py --output "C:\tmp\obscura-codex-skills"
~~~

**Updating.** Update the source checkout and repeat `--install`. An unchanged package is not rewritten. The previous managed version is kept in `%USERPROFILE%\.agents\obscura-backups\<id>`; prepared or unrecovered files stay in the adjacent `obscura-staging\<id>`. These folders are outside skill discovery. The JSON result lists actual backup paths.

An unmanaged folder, a damaged `.obscura-install.json` manifest, or your edits stop installation of the entire set before replacements. Save your changes separately and reconcile them with the new package; there is no automatic force overwrite. `failed` means an unsuccessful operation with no remaining changes made by it; `partial` means a complete safe rollback was not possible. Inspect the listed conflicts and backups before retrying.

**Restoring and removing.** Close Codex. To restore, first save any later edits, then manually return the needed folder from the reported backup. To remove the set, delete only the five listed `obscura-*` folders under `.agents\skills`. After checking them, you can manually clear backups and staging; they are not removed automatically. Do not remove `.agents\.obscura-install.lock` while another installer is running; after a crash, check that its process has finished.

This method is available from source. Installing skills from the Microsoft Store package will come in a separate update.

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
- The chat reads the outline preamble (the title and general notes before the first scene) with the story and changes it only over the version it has read, as with a scene plan. The scenes stay the same, and those written with the previous preamble need review.
- The chat changes several story properties one after another. If one of them is refused (for example, the language is already fixed), the rest are not changed, and the chat reports what it managed to apply.
- You delete unneeded stories in Obscura: the chat cannot do that.

A draft from the chat is labelled "External client: <name>" in the version history and in the status row above the editor. If the chat named its model, the model is shown too. This is the client's claim: Obscura cannot check which model actually wrote the text. Once you save your own edit, the label leaves the status row; in the history it stays next to the chat's version.

You can keep Obscura open next to the chat. When you return to the Obscura window, the page checks on its own whether the chat wrote anything. If the editor has no unsaved edits, you see the new draft right away. If it has, your text stays, and "The scene was changed elsewhere" appears above the editor with an "Open the newer version" button; it asks for confirmation before replacing the text.

## Publishing from the chat

The chat can fill in the publication card, add an author signature, set a cover and export the book.

- The chat changes only the card fields you named; the rest stays. If the card was changed after the chat read it, the write is refused with code 409, and the chat has to read the card again.
- The chat takes FB2 genres from the same catalogue as the card page.
- The chat reads the cover from a file on a local disk: give the full path, for example `C:\Users\…\cover.png`. PNG and JPEG up to 10 MiB work. Copy a file from a network drive or a shared folder to your own disk first. An uploaded cover becomes part of the card only when the chat writes it there.
- The chat can ask Obscura to draw a [text cover](publication.md#publication-card) from the saved card. It likewise becomes part of the card only when the chat writes it to the card.
- Export returns a link to the file in Obscura. The chat exports an unfinished story only with your explicit permission, and FB2 needs an author and a genre in the card.
- If the card page is open, you will see the chat's changes when you return to it. Unsaved edits in the form stay, and the page says the card was changed elsewhere.

## Character cards from the chat

The chat can read the [character cards](characters.md) and change them: rename a character, add a card or an entry, change the text or availability of an entry ("Starting from a scene" and so on), remove an entry.

- First the chat shows what will change: the name before → after and which entries are added, changed or removed. It writes only after your consent. If the cards or the story were changed after the chat read them, the write is refused with code 409, and the chat has to read the cards again.
- When a character is renamed, the old name stays in an "Other name:" line, so scene plans with the old name keep working. The chat can remove it later, once it has rewritten the plans. While a plan ("Who takes part:", "Narrator:") or a card ("Knows:") still uses the old name, the chat cannot write that change and names those places.
- If a change affects scenes with a brief, the chat asks whether to mark them unchecked, like the dialog on the Characters page. The mark is set only after your "yes".
- An entry the chat changed is marked as the author's. The chat does not change the source quotes of imported entries.
- The chat does not delete a whole card: you do that on the Characters page.

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
- In the **The chat writes** mode it is the other way round: the chat does not start stages with Obscura models, it writes itself. The exception is the auditor check (see below): it writes no text, so it is available in both modes.
- Only you change the mode: in the story settings, **Writing** section, the **Who writes the texts** field. The chat cannot change it. Changing the mode does not touch texts already written or stages already started.

## Obscura runs from the chat

In a story with the **Obscura writes** mode the chat can ask Obscura to run one scene stage — the scene brief, the draft, editing or memory — or to suggest a publication card. This is an ordinary Obscura run: your role models, the story budget and the same readiness check as for the buttons.

- First the chat shows a preview: which models will work, how many calls there will be, warnings and the remaining story budget. It starts the run only after your consent in the chat.
- **A run costs money** at the rates of the role models. Cloud providers need a story budget limit, as for the buttons. The chat can pass a limit for one run. For stages Obscura does not estimate the amount in advance: the preview shows the models and the budget.
- The run goes in the background. The chat checks its status with a separate request; it reads the finished text like other scene texts, and card suggestions come with the run status.
- The chat can cancel only a run it started itself. Pausing, resuming, your runs, a whole scene, the rest of the story, preparation and evaluation stay with you: Obscura refuses such requests from the chat.
- If the previous memory needs your confirmation, the memory stage does not start: the chat advises you to confirm it in Obscura.
- You accept changes that wait for your decision in Obscura, as after a run started with a button.

The chat can also start the [book memory build](memory.md#building-the-book-memory) from the first scene without valid memory.

- The preview shows the number of scenes and calls, the upper bound on the cost (for a cloud model with a known price), the scenes that do not fit the memory role limits, the character cards and an offer to update a series book from the previous one first. You update the series book yourself in the Obscura window (**Update from the previous book**); the chat only reminds you.
- The chat starts the build only after your consent and only with the plan you were shown: without it Obscura refuses the run from the chat. If the book, the cards or the memory model changed in the meantime, the chat has to show you a new preview.
- If a build of this book is already queued or running, Obscura does not start a second one, even when the chat repeats the confirmation: you do not pay twice for one build.
- Before the run Obscura fills the scene participants from the names in the prose, as the **Build** button does. If the run is refused after that (for example, by the budget), the written participants stay.
- In a "Chat writes" story Obscura does not start the memory build: the chat goes through the scenes one by one itself (the memory stage from the chat), or you switch the story mode.

In either mode the chat can also start an [auditor check](workspace.md#validating-the-book): of one scene or of the whole book.

- The preview shows which scenes and links will be checked, the maximum number of calls and the upper bound on the cost (for a cloud model with a current price). The chat starts the check only after your consent in the chat and only with the plan you were shown. If the book changed in the meantime, Obscura refuses with “The check plan has changed. Review it again”, and the chat has to show you the new preview.
- When the auditor stops at a discrepancy, the chat sees in which scene. You make the decision and continue the check in Obscura.
- A new book check from the chat cancels only stopped checks the chat started; it does not touch yours.

## Scene stages from the chat

The chat can go through every stage of a scene itself: write the scene brief, write the draft, edit it and update the memory. For each stage it gets the same instructions as an Obscura model: the standard prompts or your own, the role settings, the story language, the rating and the memory of earlier scenes. For the draft, the writer's instructions come with the scene context.

- Obscura checks the chat's answer with the same code as its own model's answer. It does not save a wrong answer even in part, and returns all the violations to the chat at once. After three refusals in a row the chat should stop and show you the violations.
- If the scene, the role settings or the prompt changed between the task and the answer, the answer is refused, and the chat takes the task again.
- A result from the chat behaves like a model result: a brief with significant changes waits for your decision, editing in the edit-selection mode goes to "Editor changes", and the memory becomes current. An edit that keeps fewer than 60% of the words of the text is treated as an excerpt and is not saved. You confirm the memory core, as for a model.
- If the previous prose changed after its memory, the chat does not get the memory task: you confirm the use of the previous memory in Obscura.
- In the version history such versions are marked "External client: <name>". Prose edited by the chat is an editing version with this mark.
- These tools cost no money and are not counted in the budget. If a role is not configured, Obscura uses the chat's typical context limits; it does not know the chat's own window.

## Importing a manuscript from the chat

The chat can create a book from your finished manuscript the same way as the [manuscript import](manuscript-import.md) in the library.

- Give the chat the full path to a `.docx`, `.md` or `.txt` file on a local disk (with the drive letter, up to 20 MiB). Obscura reads only the file itself: it refuses a link, a folder, a network path or a file on a network drive. OneDrive files on your disk work. The chat can also send a small file (up to 2 MiB) as content.
- First the chat shows a preview: scenes with titles and word counts, proposed boundaries and warnings. It can parse the file again with other chapter or part markers and pass its own scene boundaries. On your request the chat adds the front matter (a dedication or an epigraph before the first chapter) to the start of the first scene, like the switch in the library.
- The book is created only after your consent, in the language of the preview. No model is called, the import costs nothing.
- The answer has a link to the book in Obscura. The chat builds the book memory with a separate [run](#obscura-runs-from-the-chat) with a cost preview.

## Start a story with one request

The chat client sees the “Start a story” prompt (`start_story`). It leads the chat from an idea to a story: create the story in the “chat writes” mode, fill in the plan and the characters, write the scenes and finally give a link to read and edit the story in the Obscura window. The prompt first repeats your idea and then follows the same steps as the `start-story` skill: one question at a time, with a summary and your consent.

## The Microsoft Store version

The Microsoft Store version includes the MCP bridge and the [Obscura skills](#obscura-skills): there is nothing to install separately, and the “Connect to Claude” button in the library is expanded right away. “Connect Claude Code” installs the skills together with the bridge, and “Skills for Claude Desktop” prepares the ZIP files just as in the source version. A new story created in the library form uses the **Obscura writes** mode by default here too; a story created by the chat uses **The chat writes**. If Obscura is not running, Claude quietly starts it in the tray when it is needed; you can quit it from the tray icon.

The free version does not write long prose (books, parts, arcs), series or scenes above the rating limit. When the chat meets such a limit, it explains that this is a feature of the paid version and gives the waitlist link.

## Limitations

- Obscura must be running. Otherwise the chat gets the error "Obscura не запущено за адресою …" (Obscura is not running at …).
- The next scene's context can be read only after the previous scene's memory is updated, just as for generation in Obscura.
- If the scene was changed after the context was read, the save is refused with "Сцену вже змінено" (the scene has already been changed). If the cards, a location description, the rating, the story language or the memory of earlier scenes changed, it is refused with "Контекст сцени змінився — прочитайте його знову" (the scene context changed, read it again). Either way, ask the chat to read the context again.
- If the draft was changed after the chat read it (by you in Obscura or by another conversation), the save is refused with "Чернетку змінено після того, як її прочитали" (the draft was changed after it was read). Ask the chat to read the draft again and repeat its change over it.
- The chat sees only saved texts. It does not see unsaved edits in an open editor: save them before asking the chat to change anything.
- The chat sees Obscura's errors with the prefix "Error executing tool …", followed by Obscura's code and explanation.
- A draft from the chat counts as model-made material: after it, the story language can no longer be changed.
- Obscura does not evaluate a draft from the chat automatically and does not count it in the [budget](models.md). The cost falls on the chat client's account.
- Regular chat clients may refuse to write explicit scenes. Obscura does not work around that.
