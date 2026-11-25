# Local edit: rework places in one scene

The author asks for a change of quality or tone in one scene ("funnier", "slower", "fewer explanations"). You find the places where it matters most and offer variants; the author chooses. The facts of the scene stay as they are.

## Steps

1. **Scene and instruction.** If the author did not name the scene, ask one question.
2. **Read the scene in full:** `get_scene_text(scene_id, 'prose')` (or `'draft'` if the scene has no prose yet), following `next_offset` until it is null.
3. **Pick 3–6 places** where the instruction has the biggest effect. Show them as quotes, numbered.
4. **One card per place, one at a time**, as the shared rules say:
   - 2–3 replacement variants, the recommended one first;
   - plus «лишити як є» (leave as is).

   A variant never changes a fact of the scene: names, numbers, events. If the instruction needs a fact to change, say so and offer the fact-change route.
5. **Apply** after the last choice, and only what the author chose. The choices are the consent for these replacements.
   - **`chat` mode, editor `prose`** (`result_format` of `get_stage_task(scene_id, 'edit')`): the chain from the draft for this one scene — draft → prose → memory — as steps 3–5 of §6 in `${CLAUDE_PLUGIN_ROOT}/skills/revise/references/fact-change.md`. Every sentence you were not asked to change stays byte for byte. Then the next scene's links become unchecked: handle it as §7 there.
   - **`obscura` mode, or editor `patches`/`diff`:** write nothing. Give the table of chosen replacements «знайти — замінити на» for the author to make in Obscura, and finish as §10 there.
6. **Summary:** what changed, the variants you invented as your decisions, and the reminder to read and approve the prose in Obscura (`next_steps(scene_id)`).
