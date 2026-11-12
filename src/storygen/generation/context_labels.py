"""Model-facing context labels by story language (STORY-LANGUAGE, #32).

Only text that reaches the model lives here; UI diagnostics stay Ukrainian and go through the i18n catalog.
Ukrainian values are the exact strings used before #32: a Ukrainian request must not change byte for byte.
English section names match the ones the English prompts refer to ("CORE STATE", "ACTIVE THREADS", "DAY CHANGED").
"""
LABELS: dict[str, dict[str, str]] = {
    'scene_header': {'uk': 'СЦЕНА {number}/{total}: {title}\nЦільовий обсяг: {words} слів.',
                     'en': 'SCENE {number}/{total}: {title}\nTarget length: {words} words.'},
    'author_source': {'uk': 'АВТОРСЬКЕ ДЖЕРЕЛО', 'en': 'AUTHOR SOURCE'},
    'review_basis_note': {'uk': 'Історична база цього тексту невідома. Перевірте узгодженість із поточними передумовами; не вигадуйте його історію створення.',
                          'en': 'The historical basis of this text is unknown. Check consistency with the current premises; do not invent how it was created.'},
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
    'ending_goal': {'uk': 'АВТОРСЬКИЙ ОРІЄНТИР ФІНАЛУ — ЗАДУМ, НЕ ЗДІЙСНЕНІ ПОДІЇ',
                    'en': 'AUTHOR ENDING GOAL — INTENT, NOT EVENTS THAT HAVE HAPPENED'},
    'memory_header': {'uk': 'ЗДІЙСНЕНІ ПОДІЇ — ПЕРЕВІРЕНА ПАМ’ЯТЬ', 'en': 'EVENTS THAT HAVE HAPPENED — VERIFIED MEMORY'},
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
    'memory_core_owner': {'uk': 'ЯДРО СТАНУ — {name}', 'en': 'CORE STATE — {name}'},
    'memory_protagonist': {'uk': 'протагоніст', 'en': 'protagonist'},
    'memory_none': {'uk': 'Немає.', 'en': 'None.'},
    'memory_dropped': {'uk': 'Не показано записів: {count}{scenes}.', 'en': 'Entries not shown: {count}{scenes}.'},
    'memory_dropped_scenes': {'uk': ' (сцени {ranges})', 'en': ' (scenes {ranges})'},
    # Characters (characters/projection.py, characters/context.py, characters/acquaintance.py).
    'characters': {'uk': 'КАРТКИ ПЕРСОНАЖІВ', 'en': 'CHARACTER CARDS'},
    'character': {'uk': 'ПЕРСОНАЖ: ', 'en': 'CHARACTER: '},
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
    # Impact and review premises (impact/planning.py).
    'impact_raw_characters': {'uk': '[Нерозмічені вихідні описи не передаються; використовуйте картки персонажів]',
                              'en': '[Unmarked source descriptions are not passed on; use character cards]'},
    'field_canon_version_id': {'uk': 'Канон', 'en': 'Canon'},
    'field_style_version_id': {'uk': 'Стиль', 'en': 'Style'},
    'field_characters_version_id': {'uk': 'Персонажі', 'en': 'Characters'},
    'field_source_preamble': {'uk': 'Авторські вказівки', 'en': 'Author notes'},
    'field_source_plan': {'uk': 'План твору', 'en': 'Story plan'},
    'field_source_characters': {'uk': 'Описи персонажів', 'en': 'Character descriptions'},
    'impact_current_sources': {'uk': 'ПОТОЧНІ ДЖЕРЕЛА', 'en': 'CURRENT SOURCES'},
    'impact_historical_sources': {'uk': 'ІСТОРИЧНІ ДЖЕРЕЛА — НЕ ПЕРЕПРИВ’ЯЗАНІ ДО НОВОЇ ПРОЗИ',
                                  'en': 'HISTORICAL SOURCES — NOT RE-LINKED TO THE NEW PROSE'},
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
