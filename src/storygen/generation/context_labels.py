"""Model-facing context labels by story language (STORY-LANGUAGE, #32).

Only text that reaches the model lives here; UI diagnostics stay Ukrainian and go through the i18n catalog.
Ukrainian values are the exact strings used before #32: a Ukrainian request must not change byte for byte.
English section names match the ones the English prompts refer to ("CORE STATE", "ACTIVE THREADS", "DAY CHANGED").
"""
LABELS: dict[str, dict[str, str]] = {
    'scene_header': {'uk': 'СЦЕНА {number}/{total}: {title}\nЦільовий обсяг: {words} слів.',
                     'en': 'SCENE {number}/{total}: {title}\nTarget length: {words} words.'},
    'author_source': {'uk': 'АВТОРСЬКЕ ДЖЕРЕЛО', 'en': 'AUTHOR SOURCE'},
    'current_prose': {'uk': 'ПОТОЧНА ПРОЗА', 'en': 'CURRENT PROSE'},
    'memory_core': {'uk': 'ЯДРО СТАНУ ВІДСТЕЖУВАНИХ ПЕРСОНАЖІВ — УСІ СЛОТИ ОБОВ’ЯЗКОВІ',
                    'en': 'CORE STATE OF TRACKED CHARACTERS — ALL SLOTS REQUIRED'},
    'memory_threads': {'uk': 'АКТИВНІ ЛІНІЇ — ДЛЯ КОЖНОЇ ОБОВ’ЯЗКОВЕ open/closed',
                       'en': 'ACTIVE THREADS — open/closed REQUIRED FOR EACH'},
    'memory_claims': {'uk': 'ЧИННІ ТВЕРДЖЕННЯ — MUTABLE ДЛЯ UPDATE/RETIRE, IMMUTABLE ЛИШЕ ДЛЯ УНИКНЕННЯ ПОВТОРІВ',
                      'en': 'CURRENT CLAIMS — MUTABLE FOR UPDATE/RETIRE, IMMUTABLE ONLY TO AVOID REPEATS'},
    'day_changed': {'uk': 'ЗМІНИВСЯ ДЕНЬ: {before} → {after} ({name})\n'
                          'Одяг, речі при собі й тілесний стан могли застаріти: якщо проза їх не підтверджує, познач unknown із причиною.',
                    'en': 'DAY CHANGED: {before} → {after} ({name})\n'
                          'Clothing, items carried and bodily state may be out of date: if the prose does not confirm them, mark them unknown with a reason.'},
    # Brief, draft, full edit, rewrite and MCP writing-context: the day change is data, the rules live in the prompts.
    'writer_day_changed': {'uk': 'ЗМІНИВСЯ ДЕНЬ: {before} → {after} ({name})\n'
                                 'Одяг, речі при собі й тілесний стан у «ЯДРО СТАНУ» — з попереднього дня й можуть бути вже не чинні.',
                           'en': 'DAY CHANGED: {before} → {after} ({name})\n'
                                 'Clothing, items carried and bodily state in "CORE STATE" are from the previous day and may no longer hold.'},
    'scene_locations': {'uk': 'ЛОКАЦІЇ СЦЕНИ', 'en': 'SCENE LOCATIONS'},
    'allowed_location_ids': {'uk': 'ДОЗВОЛЕНІ LOCATION_IDS: додайте до нового запису location_ids місць цієї сцени, яких він стосується (порожній список — запис не про місце)',
                             'en': 'ALLOWED LOCATION_IDS: give a new record the location_ids of the places of this scene it is about (an empty list — not about a place)'},
    'allowed_ids': {'uk': 'ДОЗВОЛЕНІ CHARACTER_IDS ДЛЯ НОВИХ СТАНІВ', 'en': 'ALLOWED CHARACTER_IDS FOR NEW STATES'},
    'prose_fragments': {'uk': 'ПОТОЧНА ПРОЗА [version_id={id}] — НУМЕРОВАНІ ФРАГМЕНТИ',
                        'en': 'CURRENT PROSE [version_id={id}] — NUMBERED FRAGMENTS'},
    'draft': {'uk': 'ЧЕРНЕТКА', 'en': 'DRAFT'},
    'draft_fragments': {'uk': 'ЧЕРНЕТКА [version_id={id}] — НУМЕРОВАНІ ФРАГМЕНТИ',
                        'en': 'DRAFT [version_id={id}] — NUMBERED FRAGMENTS'},
    'style': {'uk': 'ПРОФІЛЬ ПИСЬМА', 'en': 'WRITING PROFILE'},
    'canon': {'uk': 'АВТОРСЬКИЙ КАНОН', 'en': 'AUTHOR CANON'},
    'global_notes': {'uk': 'ГЛОБАЛЬНІ АВТОРСЬКІ ВКАЗІВКИ', 'en': 'GLOBAL AUTHOR NOTES'},
    'future_plan': {'uk': 'МАЙБУТНІ ПОДІЇ — ПЛАН СЦЕНИ {number}', 'en': 'FUTURE EVENTS — PLAN OF SCENE {number}'},
    # SCENE-NARRATOR (narration.py).
    'narrator': {'uk': 'ОПОВІДАЧ СЦЕНИ — ДЛЯ ЦІЄЇ СЦЕНИ ЗАМІНЯЄ point_of_view ЗІ СТИЛЮ',
                 'en': 'SCENE NARRATOR — FOR THIS SCENE REPLACES point_of_view FROM THE STYLE'},
    'narrator_first': {'uk': 'Перша особа: розповідає {name}.', 'en': 'First person: told by {name}.'},
    'narrator_third_limited': {'uk': 'Третя особа через героя: {name} (лише його сприйняття й знання).',
                               'en': 'Third person through a character: {name} (only their perception and knowledge).'},
    'narrator_third_omniscient': {'uk': 'Третя особа, всезнаючий оповідач.', 'en': 'Third person, omniscient narrator.'},
    'tone_sample': {'uk': 'ЗРАЗОК ЗВУЧАННЯ — НЕ СЮЖЕТ: ПЕРЕЙМИ РИТМ, ЛЕКСИКУ Й БУДОВУ РЕЧЕНЬ; НЕ БЕРИ ПОДІЙ, ІМЕН ЧИ СВІТУ',
                    'en': 'VOICE SAMPLE — NOT PLOT: TAKE ITS RHYTHM, VOCABULARY AND SENTENCE STRUCTURE; NOT ITS EVENTS, NAMES OR WORLD'},
    'ending_goal': {'uk': 'АВТОРСЬКИЙ ОРІЄНТИР ФІНАЛУ — ЗАДУМ, НЕ ЗДІЙСНЕНІ ПОДІЇ',
                    'en': 'AUTHOR ENDING GOAL — INTENT, NOT EVENTS THAT HAVE HAPPENED'},
    # SERIES-S10: records of later books a prequel must not contradict; not memory, no quotes.
    'future_facts': {'uk': 'МАЙБУТНЄ, ЯКОМУ НЕ МОЖНА СУПЕРЕЧИТИ — ПОДІЇ ПІЗНІШИХ КНИГ СЕРІЇ, ЩЕ НЕ ЗДІЙСНЕНІ В ЦІЙ КНИЗІ',
                     'en': 'THE FUTURE YOU MUST NOT CONTRADICT — EVENTS OF LATER BOOKS OF THE SERIES, NOT YET HAPPENED IN THIS BOOK'},
    'future_more': {'uk': '…і ще записів майбутнього, що не вмістилися: {count}',
                    'en': '…and {count} more future records that did not fit'},
    # SERIES-BIBLE: the memory stage of a world bible scene.
    'bible_facts': {'uk': 'БІБЛІЯ СВІТУ: УСЕ НОВЕ — ФАКТИ, ДО 10 ЗІ СЦЕНИ; БЕЗ СТАНІВ, ЛІНІЙ І ХРОНОЛОГІЇ',
                    'en': 'WORLD BIBLE: EVERYTHING NEW IS A FACT, UP TO 10 PER SCENE; NO STATES, THREADS OR TIMELINE'},
    'memory_header': {'uk': 'ЗДІЙСНЕНІ ПОДІЇ — ПЕРЕВІРЕНА ПАМ’ЯТЬ', 'en': 'EVENTS THAT HAVE HAPPENED — VERIFIED MEMORY'},
    # STORY-TIME: facts of flashbacks of other arcs earlier than the start of this scene's arc; no structure names.
    'foreign_flashbacks': {'uk': 'МИНУЛЕ ІНШИХ АРОК — ФАКТИ СПОГАДІВ', 'en': 'THE PAST OF OTHER ARCS — FACTS FROM FLASHBACKS'},
    'foreign_flashback_scene': {'uk': 'Сцена {number} ({time}):', 'en': 'Scene {number} ({time}):'},
    'previous_tail': {'uk': 'ЗАВЕРШЕННЯ ПОПЕРЕДНЬОЇ СЦЕНИ (явно вибраний фрагмент)',
                      'en': 'ENDING OF THE PREVIOUS SCENE (explicitly selected excerpt)'},
    'rewrite_source': {'uk': 'ЗБЕРЕЖЕНА ЧЕРНЕТКА ДЛЯ ПЕРЕПИСУВАННЯ', 'en': 'SAVED DRAFT TO REWRITE'},
    'head_brief': {'uk': 'ЗАВДАННЯ ПИСЬМЕННИКУ', 'en': 'WRITER BRIEF'},
    'head_draft': {'uk': 'ЧЕРНЕТКА ДЛЯ РЕДАКТУРИ', 'en': 'DRAFT TO EDIT'},
    'head_prose': {'uk': 'ПОТОЧНА ПРОЗА — ДЖЕРЕЛО НОВОЇ ПАМ’ЯТІ', 'en': 'CURRENT PROSE — SOURCE OF NEW MEMORY'},
    'rewrite_notes': {'uk': 'АВТОРСЬКІ ВКАЗІВКИ — JSON ДАНІ', 'en': 'AUTHOR NOTES — JSON DATA'},
    # Memory projection (memory/projection.py, memory/selection.py).
    'memory_reader_unknown': {'uk': ' (читачеві невідомо: якщо знадобиться, введи в тексті як нове)',
                              'en': ' (unknown to the reader: if needed, introduce it in the text as new)'},
    'memory_facts': {'uk': 'ФАКТИ', 'en': 'FACTS'},
    'memory_character_states': {'uk': 'ПОТОЧНІ СТАНИ', 'en': 'CURRENT STATES'},
    'memory_open_threads': {'uk': 'ВІДКРИТІ ЛІНІЇ', 'en': 'OPEN THREADS'},
    'memory_timeline': {'uk': 'ХРОНОЛОГІЯ', 'en': 'TIMELINE'},
    'memory_scene_prefix': {'uk': 'Сцена {number}: ', 'en': 'Scene {number}: '},
    'memory_core_earlier_today': {'uk': ' (раніше цього дня: {value})', 'en': ' (earlier this day: {value})'},
    'memory_core_owner': {'uk': 'ЯДРО СТАНУ — {name}', 'en': 'CORE STATE — {name}'},
    'memory_protagonist': {'uk': 'протагоніст', 'en': 'protagonist'},
    'memory_none': {'uk': 'Немає.', 'en': 'None.'},
    'memory_dropped': {'uk': 'Не показано записів: {count}{scenes}.', 'en': 'Entries not shown: {count}{scenes}.'},
    'memory_dropped_scenes': {'uk': ' (сцени {ranges})', 'en': ' (scenes {ranges})'},
    'summary_scenes': {'uk': 'Підсумок сцен {first}–{last}: {text}', 'en': 'Summary of scenes {first}–{last}: {text}'},
    'summary_part': {'uk': 'Підсумок частини «{title}» (сцени {first}–{last}): {text}', 'en': 'Summary of part “{title}” (scenes {first}–{last}): {text}'},
    # Characters (characters/projection.py, characters/context.py, characters/acquaintance.py).
    'characters': {'uk': 'КАРТКИ ПЕРСОНАЖІВ', 'en': 'CHARACTER CARDS'},
    'character': {'uk': 'ПЕРСОНАЖ: ', 'en': 'CHARACTER: '},
    'character_also': {'uk': ' (також: {names})', 'en': ' (also: {names})'},
    # EDITOR-NAME-SPELLING: the editor keeps the spelling of the scene cast's names (characters/context.py).
    'name_spelling': {'uk': 'НАПИСАННЯ ІМЕН', 'en': 'NAME SPELLING'},
    'name_spelling_rule': {'uk': 'Пиши імена персонажів точно так, як подано нижче: тими самими літерами й тим самим алфавітом. '
                                 'Не транслітеруй, не перекладай і не замінюй їх іншими формами. Відмінюй їх так, як це вже робить чернетка.',
                           'en': 'Write the character names exactly as given below: the same letters in the same alphabet. '
                                 'Do not transliterate, translate or replace them with other forms. Inflect them the way the draft already does.'},
    'character_timeless': {'uk': 'ПОЗАЧАСОВІ ВІДОМОСТІ', 'en': 'TIMELESS DETAILS'},
    'character_from_scene': {'uk': 'ДОСТУПНІ АВТОРСЬКІ ВКАЗІВКИ — НЕ ДОКАЗ МИНУЛИХ ПОДІЙ',
                             'en': 'AVAILABLE AUTHOR NOTES — NOT EVIDENCE OF PAST EVENTS'},
    'character_unclassified': {'uk': 'НЕПЕРЕВІРЕНІ ЗА ЧАСОМ АВТОРСЬКІ ВІДОМОСТІ',
                               'en': 'AUTHOR DETAILS NOT CHECKED FOR TIMING'},
    'acquaintance_header': {'uk': 'ЗНАЙОМСТВА ГОЛОВНОГО ГЕРОЯ — {name}', 'en': 'WHOM THE PROTAGONIST KNOWS — {name}'},
    'acquaintance_known': {'uk': 'Знайомі: ', 'en': 'Known: '},
    'acquaintance_before': {'uk': 'до початку історії', 'en': 'before the story begins'},
    'acquaintance_since': {'uk': 'зі сцени {number}', 'en': 'since scene {number}'},
    'acquaintance_unknown': {'uk': 'Ще не представлені: ', 'en': 'Not yet introduced: '},
    'acquaintance_rule': {'uk': 'Не називай ще не представлених на ім’я, доки їх не представлено в тексті історії; до того описуй їх як незнайомців.',
                          'en': 'Do not call characters who have not been introduced by name until the story text introduces them; until then describe them as strangers.'},
    'acquaintance_brief_rule': {'uk': ' Якщо представлення відбувається в цій сцені, додай їхні ID в поле introduced.',
                                'en': ' If the introduction happens in this scene, add their IDs to the introduced field.'},
    # Story horizon (story_horizon.py).
    'horizon_last': {'uk': 'Поточна сцена остання: виконайте її власний план.',
                     'en': 'The current scene is the last one: carry out its own plan.'},
    'horizon_not_last': {'uk': 'Поточна сцена не остання: не завершуйте весь твір і не переносіть розв’язку сюди.',
                         'en': 'The current scene is not the last one: do not end the whole story and do not move the resolution here.'},
    'horizon': {'uk': 'МЕЖІ ПОТОЧНОЇ СЦЕНИ\nРеалізуйте лише біти поточної сцени. Майбутні плани та орієнтир фіналу — задум, а не вже здійснені події. ',
                'en': 'LIMITS OF THE CURRENT SCENE\nCarry out only the beats of the current scene. Future plans and the ending goal are intent, not events that have happened. '},
    # Prose language of a scene that differs from the story (STORY-LANGUAGE-S03); said in the story language.
    'prose_directive_en': {'uk': 'Пиши прозу цієї сцени англійською мовою.', 'en': "Write this scene's prose in English."},
    'prose_directive_uk': {'uk': 'Пиши прозу цієї сцени українською мовою.', 'en': "Write this scene's prose in Ukrainian."},
}


def label(key, language, **params):
    text = LABELS[key][language]
    return text.format(**params) if params else text


def prose_language_directive(story, scene, language_of_instructions=None):
    """One sentence in the instruction language when the scene's prose language differs from the story; otherwise None."""
    from ..language import prose_language
    prose = prose_language(story, scene)
    if prose == story.language:
        return None
    return label('prose_directive_' + prose, language_of_instructions or story.language)
