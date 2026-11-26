---
name: draft-scene
description: Use when an Obscura story already has a plan and the author wants scenes written, continued or finished, in either writing mode. Triggers include "пиши далі", "напиши сцену", "напиши наступну сцену", "допиши книжку", "запусти сцену", "write the next scene", "continue the story", "draft scene 3".
---

# Write scenes: chat mode or Obscura mode

Read `${CLAUDE_PLUGIN_ROOT}/shared/rules.md` first and follow it throughout. It covers consent before writing, progress lines, and the author's approval of prose.

## First: which mode

1. Find the story (`list_stories` if the author did not name it). Then call `get_story(story_id)`.
2. Pick the scene:
   - the one the author named, or
   - the first scene in order that is unfinished: `not_started`, `no_text`, `draft` or `needs_review`. Continue it from its next stage; after `needs_review`, let the author look at the pending changes first.

   `prose` is a written scene.

   A `prose` scene may still lack its memory. If the server answers «Спершу оновіть пам’ять попередньої сцени», finish the memory stage of the previous scene first. When no scene is unfinished, check the last scene: if `get_scene_text(scene_id, 'memory')` has no `version_id`, its memory stage is the next step, since no later scene will ask for it.

   Confirm the choice in one line, together with how many scenes are left.
3. `writing_mode` decides the branch:
   - **`chat`**: you write the texts. Follow `${CLAUDE_PLUGIN_ROOT}/skills/draft-scene/references/chat-pipeline.md`.
   - **`obscura`**: Obscura's models write them; you start and watch the runs. Follow `${CLAUDE_PLUGIN_ROOT}/skills/draft-scene/references/obscura-runs.md`.
   - **`author`** («Пишу сам»): the author writes the prose. Do not write or rewrite a draft, an edit or prose, and do not start runs that write prose: the server refuses them. You may still do the brief and the memory stages from the chat (`get_stage_task` + `save_stage_result`), with the author's consent, and the auditor check. Tell the author in one line that the prose is theirs to write in the Obscura window.

Only the author changes the mode, in the story's settings in Obscura. Never work around it: in `obscura` mode the server refuses texts from chat, and in `author` mode it refuses prose from chat and from models.

## What the author's request covers

- **`chat` mode:** "write the scene" (or "write the next scenes") is consent to save that scene's brief, draft, edit and memory. Do not ask again before each stage.

  A rewrite of the author's existing draft is not covered: ask first, because it replaces their text in the current version. The earlier version stays in Obscura's history.
- **`obscura` mode:** every run costs the author money, so runs need their own consent, as `obscura-runs.md` describes.

## Before each scene (chat mode)

Go through `${CLAUDE_PLUGIN_ROOT}/skills/draft-scene/references/continuity.md`:
- time;
- who is present;
- what they hold and carry;
- the hero's state;
- the facts already introduced.

## Progress

After every stage, write one line. For example:

> Сцена 3 з 7: завдання готове → пишу чернетку.

When a scene is done, write one line with what happened in it and what comes next. Keep going scene after scene while the author has asked for more. After every scene, say that the author can stop you.

## When a scene is done

- Remind the author to read the scene and approve its prose in Obscura. `next_steps(scene_id)` gives the link.
- After the last scene:
  - give a short summary of the book;
  - list your own decisions;
  - suggest the publication card, cover and export (the `publish` skill).
