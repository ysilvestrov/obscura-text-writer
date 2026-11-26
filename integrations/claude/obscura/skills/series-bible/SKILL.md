---
name: series-bible
description: Use when the author plans a series or cycle of books, or a story world with its own rules (magic, factions, races, geography, history), and wants a world bible before the first book. Triggers include "хочу цикл", "серія книжок", "світ із магією", "біблія світу", "a series of books", "world bible", "a fantasy world with rules".
---

# Series bible: the world before the first book

Read `${CLAUDE_PLUGIN_ROOT}/shared/rules.md` first and follow it throughout. It covers one question at a time, consent before writing, marking your own decisions, and progress lines.

A series bible is a separate Obscura story that holds the facts of a world. Every book of the series then gets those facts in its memory context. The rule that matters most: **nothing is created until the author agrees to the list of articles.**

## 1. The world

Ask one question at a time, only what the author has not said:

1. **The series' title.** If there is none, offer 3 on a card.
2. **What makes the world special:** magic and its rules, organisations and factions, races or peoples, geography, history and chronology, scales (ranks, money, distances, power levels).
3. **Recurring characters** of the cycle, if any: age, a few traits of appearance, occupation, way of speaking — as in the `start-story` skill.
4. Language and content rating, if not clear.

## 2. The list of articles

Propose the articles. Each one is a scene of the bible:
- the heading «Сцена N: <тема>» (or "Scene N: <topic>");
- 400–800 words;
- **no fictional events**: facts, rules, scales, names, dates.

A typical list: the world and its geography; magic and its limits; organisations; peoples; chronology. Mark the topics you added yourself as your decisions.

Show the whole list — articles with one line each, series title, language, rating, your decisions — and wait for explicit consent. A changed article means a new list.

## 3. Create

Only after consent:

1. `create_story(title="<Series>: біблія" (or "<Series>: bible"), language, target_words, content_rating, writing_mode)`. Obscura accepts at least 5000 words per story, so `target_words` is the sum of the articles and at least 5000. In `author` mode («Пишу сам») the author writes the articles themself; you create the story and the plan only.
2. `get_templates(language)`. Fill the plan template:
   - start it with the preamble lines «Серія: <назва>» and «Номер: біблія» (or "Series: <title>" and "Number: bible");
   - one scene per agreed article.

   Fill the characters template with the cycle's recurring characters, if any.
3. `import_plan_and_characters(story_id, plan_markdown, characters_markdown)`. Check the import result and fix only the missing part.
4. `get_story(story_id)`. Confirm the number of articles and that `series.bible` is true.
   - `series` is null: this Obscura edition keeps no series. Tell the author: the bible exists as an ordinary story, and the series lines stayed in its plan.
   - a warning about series lines: show it and fix the preamble.

## 4. After creating

**Stop after `get_story`.** This skill never writes the articles. Ask whether to start the first article; on a yes, follow the `draft-scene` skill from its beginning. The articles go through the same stages as scenes, without fictional events.

Tell the author how the books of the series join it: each book's plan starts with «Серія: <назва>» and «Номер: N» (or "Series:" and "Number:"), and the `start-story` skill does that when the author says the book belongs to this series.

End with your list of own decisions.
