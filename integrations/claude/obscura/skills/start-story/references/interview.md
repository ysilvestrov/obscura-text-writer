# Interview reference for start-story

Each question is one card (`AskUserQuestion`):
- the recommended option first, marked "(Recommended)";
- 2–4 options in total.

The author can always type their own answer. Write the cards in the author's language; the examples below are in Ukrainian because Obscura's authors mostly write in it.

## 1. Main characters

The minimum card for each main character:

| Item | Why it matters | Example card when missing |
|---|---|---|
| Age, or "all participants are adults" | content rating and plausibility | «Скільки років Михайлові?» — «Близько 30», «Близько 45», «Неважливо, дорослий» |
| Appearance (2–4 traits) | writers invent looks when none are given, and readers notice contradictions | «Як виглядає Оксана?» — 2–3 short portraits that fit the story, plus «Не важливо, вигадай сам» |
| Occupation | gives scenes their places and conflicts | «Чим займається Петро?» — 2–3 options that fit the plot |
| Way of speaking | keeps dialogue distinct | «Як говорить Анна?» — «Коротко й сухо», «Багато жартує», «Говорить книжною мовою» |

If the author answers «вигадай сам» (make it up), invent the item and mark it as your decision.

Secondary characters need only a name and a role. Invent them yourself and mark them.

If a character goes by another name (a nickname, a real name revealed later), add the line «Інше ім’я: Джон» (English «Other name: John») to their card: plans then recognise the character by either name. If the name changes from some scene on, after the import set that entry to start from that scene yourself: `get_characters`, then `update_characters` with `set_entry` (`availability: from_scene`, `available_from_scene_id` of the scene); show the preview to the author and write it with `confirm=true` only after their consent. From that scene the models use the new name.

## 2. Structure

Show the five parts and mark what the author has already given:

1. Exposition: the world and the hero before the change.
2. Inciting incident: what breaks the usual course.
3. Rising action: attempts, obstacles, complications.
4. Climax: the decisive confrontation or choice.
5. Resolution: what changed and where everyone ends up.

For each missing part, ask one card with 2–3 concrete events that fit the idea and the characters. Avoid generic options such as «щось несподіване» (something unexpected).

## 3. Length and scenes

Default: **7000 words = 7 scenes × 1000 words**:
- exposition: 1 scene;
- inciting incident: 1;
- rising action: 3;
- climax: 1;
- resolution: 1.

The card:
- «Лишити 7 сцен по 1000 слів» (Recommended);
- «Змінити обсяг або кількість сцен»;
- «Об'єднати експозицію із зав'язкою»;
- «Об'єднати кульмінацію з розв'язкою».

The two merges can be combined. After a merge, give the freed words to the rising action, or reduce the total if the author prefers.

If the author changes the length, keep scenes at 700–1500 words each, and propose the scene count yourself.

**Obscura's minimum is 5000 words per story** (`create_story` refuses less with a 422). For a shorter piece:
- create the story with `target_words` 5000;
- give each scene its own smaller target in the plan;
- tell the author that the story's total is only a target, not a requirement.

## 4. Title

The card offers 3 titles that fit the tone: one direct, one intriguing, one playful if the story is light. The author can always type their own.

## 5. Other settings (only if not said)

| Item | Default to offer |
|---|---|
| Point of view | third person, close to the main hero |
| Place and time | from the idea; if it is unclear, the present day |
| Content rating | ask on a card. Obscura's levels for sexual content, violence and dark themes are each 0–2. Offer the combination that fits the idea, and note that the Microsoft Store edition allows sexual content only up to level 1 |
| Language | the language of the author's messages (`uk` or `en`) |

## Series preamble

A book of a series starts its plan with:

```
Серія: <назва серії>
Номер: <номер книги>
```

The series bible itself uses `Номер: біблія`. Obscura then brings the bible's facts into each book's memory context.
