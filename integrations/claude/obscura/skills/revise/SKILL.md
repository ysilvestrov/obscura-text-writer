---
name: revise
description: Use when the author wants to change something in an already written Obscura story, for example move the setting, change a date or an event's format, fix a character, or make a scene funnier, slower, shorter. Triggers include "перенеси дію", "виправ у творі", "зміни факт у книжці", "цей персонаж не такий", "зроби сцену смішнішою", "change a fact in the story", "move the story to another city", "make scene 3 funnier", "this character is wrong".
---

# Revise a written story: change a fact or rework a scene

Read `${CLAUDE_PLUGIN_ROOT}/shared/rules.md` first and follow it throughout. It covers one question at a time, consent before writing, marking your own decisions, and progress lines.

The rule that matters most: **nothing is written until the author agrees to the table of changes you showed.** The request itself ("move the story to Kherson", "I agree in advance") is not consent: consent covers only a table the author has seen. A changed table needs new consent. Every change is minimal by default; deeper changes are only offered.

## 1. The story and its mode

1. Find the story (`list_stories` if the author did not name it). Then call `get_story(story_id)`.
2. Note:
   - `writing_mode` (`chat` or `obscura`);
   - `series` (only `title`, `number` and `bible`; not null means the book belongs to a series, which may have a bible: find it as §3 of the fact-change route says);
   - `plan_preamble` and its `plan_version_id`;
   - the scenes in order: id, title, state.

## 2. The route

Pick the route from the request and say it in one line. The author may pick the other one.

- **Fact change:** a fact of the world changes — a place, a time, an event or its format, a character's name, age, role or trait ("this character is wrong" belongs here: the character lives in the card and in every scene). Follow `${CLAUDE_PLUGIN_ROOT}/skills/revise/references/fact-change.md`.
- **Local edit:** an instruction about the quality or tone of one scene ("funnier", "slower", "fewer explanations"). Follow `${CLAUDE_PLUGIN_ROOT}/skills/revise/references/local-edit.md`.

## 3. Before writing

- `needs_review` in `get_story` means unchecked links between scenes, not edits waiting for review: unreviewed point edits of the editor show as `prose`. So `needs_review` does not block this skill.
- Only server refusals block, for example «Спершу оновіть пам'ять попередньої сцени», «Пам'ять переноситься», or a request to confirm the memory. If a refusal does not come from your own chain of changes (see the route), stop and tell the author what to do in Obscura.
- Read everything first; reading needs no consent. Show the table in one message whose only question is the consent ask. A point still open goes into the table as a row marked «потребує рішення» (needs a decision), not as a second question.

## 4. Summary

At the end:
- what changed: scenes, plan, preamble, character cards, memory, series bible; and what the author still has to change by hand (replacement tables, deleting a whole card, merging old location cards left without scenes);
- your own decisions;
- scenes that got new memory, the Auditor's findings if it ran, and scenes waiting for «Я перевірив сам»;
- what the author has to do in Obscura: read and approve the prose, review editor edits. `next_steps(scene_id)` gives the link.
