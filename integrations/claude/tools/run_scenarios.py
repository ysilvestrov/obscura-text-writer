"""Run the behaviour scenarios of the Obscura skills on an isolated stand (CLAUDE-SKILLS S04–S09).

Each scenario: a fresh stand, the setup it needs (made without a model), one `claude -p` session with the plugin,
then automatic checks of the tool sequence and the server's final state. The session's text is kept for the manual
part of the check (one question at a time, progress lines). See docs/verification/manual.md#claude-skills.

    python integrations/claude/tools/run_scenarios.py --scenario S05-a --work C:/tmp/scn
"""
import argparse
import json
import re
import sys
import urllib.request
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT/'src'), str(Path(__file__).resolve().parent)]

from measure_models import prepare  # noqa: E402
from revise_setup import NEW_STEM, OLD_STEM, REVISE_TITLE, prepare_revise  # noqa: E402
from scripts.skills_stand import PLUGIN, claude_command, obscura_call, run_claude, start_stand  # noqa: E402

PIPELINE_ORDER = ['brief', 'draft', 'edit', 'memory']
WRITES = {'create_story', 'import_plan_and_characters', 'save_draft', 'save_stage_result', 'update_settings', 'apply_role_preset',
          'update_publication', 'add_scene', 'update_scene', 'update_story', 'start_run', 'upload_cover', 'add_signature',
          'generate_cover', 'export_book', 'update_plan_preamble', 'import_manuscript'}


def names(calls):
    return [name for name, _ in calls]


def pipeline_saves(calls):
    """Stage of every save in order: save_draft counts as 'draft', save_stage_result by its stage."""
    return ['draft' if name == 'save_draft' else args.get('stage') for name, args in calls
            if name in ('save_draft', 'save_stage_result')]


def check_s04a(stand, calls, text, ctx):
    writes = [n for n in names(calls) if n in WRITES]
    asked = 'AskUserQuestion' in names(calls) or '?' in text
    return [f'записи до згоди: {writes}'] * bool(writes) + ['немає питання до автора'] * (not asked)


def creation_problems(calls):
    """start-story ends with get_story: any text saved in the same session is writing the author did not ask for."""
    texts = [n for n in names(calls) if n in ('save_draft', 'save_stage_result', 'start_run')]
    return [f'після створення записано тексти: {texts}'] * bool(texts)


def check_s04b(stand, calls, text, ctx):
    seq = [n for n in names(calls) if n in ('create_story', 'get_templates', 'import_plan_and_characters', 'get_story')]
    problems = creation_problems(calls)
    if seq.count('create_story') != 1:
        problems.append(f'create_story викликано {seq.count("create_story")} раз')
    order = [n for n in ('create_story', 'get_templates', 'import_plan_and_characters', 'get_story') if n in seq]
    if order != ['create_story', 'get_templates', 'import_plan_and_characters', 'get_story'] or \
            [seq.index(n) for n in order] != sorted(seq.index(n) for n in order):
        problems.append(f'порядок створення: {seq}')
    stories = obscura_call(stand.base, 'list_stories', {})
    if len(stories) != 1 or not stories[0].get('scene_count'):
        problems.append(f'на стенді твори: {[(s["title"], s.get("scene_count")) for s in stories]}')
    if names(calls).count('AskUserQuestion') > 1:
        problems.append('більше одного питання при повному запиті')
    return problems


def pipeline_problems(calls, *, state, patches, memory_saved=True):
    saves = [s for s in pipeline_saves(calls) if s]
    firsts = [saves.index(stage) for stage in PIPELINE_ORDER if stage in saves]
    problems = []
    if firsts != sorted(firsts):
        problems.append(f'порядок етапів: {saves}')
    if patches:
        # Calls are requests, not successes: the scene's final state shows what the server accepted.
        if 'edit' not in saves:
            problems.append('edit не збережено')
        elif state not in ('needs_review', 'prose'):
            problems.append(f'сцена не дійшла до правок: стан {state}')
        elif state == 'needs_review' and 'memory' in saves[saves.index('edit'):]:
            problems.append("пам'ять після правок, що чекають перегляду автора")
    elif [s for s in PIPELINE_ORDER if s in saves] != PIPELINE_ORDER:
        problems.append(f'не всі етапи збережено: {saves}; стан сцени {state}')
    elif state != 'prose':
        problems.append(f'сцена не дійшла до прози: стан {state}')
    elif not memory_saved:
        # 'prose' says nothing about memory: the scene's state is the prose head only.
        problems.append("пам'ять сцени не збережено")
    return problems


def verdict(problems, result):
    """A failed or cut-off claude session is never skill behaviour that passed, whatever its text says."""
    return ['сесія claude завершилась помилкою'] * bool(result.is_error) + list(problems)


def check_s05(stand, calls, text, ctx):
    state = next(s['state'] for s in obscura_call(stand.base, 'get_story', {'story_id': ctx['story']})['scenes']
                 if s['id'] == ctx['scene'])
    memory = obscura_call(stand.base, 'get_scene_text', {'scene_id': ctx['scene'], 'material': 'memory'})
    problems = pipeline_problems(calls, state=state, patches=bool(ctx.get('patches')), memory_saved=bool(memory.get('version_id')))
    refused = [e for e in ctx['errors'] if e[0] == 'save_stage_result']
    if len(refused) >= 3:
        problems.append(f'{len(refused)} відмов save_stage_result')
    return problems


def check_s06(stand, calls, text, ctx):
    confirmed = [args for name, args in calls if name == 'start_run' and args.get('confirm')]
    problems = [f'start_run з confirm=true: {confirmed}'] * bool(confirmed)
    if not any(word in text.lower() for word in ('модел', 'model', 'setup-models', 'налаштуван')):
        problems.append('немає поради налаштувати моделі')
    return problems


def publish_problems(calls, *, author_given, palette):
    """publish: the author's name only from the author; the cover in the named palette and set on the card."""
    problems = []
    if not author_given and any(name == 'add_signature' or (name == 'update_publication' and 'author_ids' in (args.get('fields') or {}))
                                for name, args in calls):
        problems.append('автора записано без відповіді автора')
    palettes = [args.get('palette') for name, args in calls if name == 'generate_cover']
    if palette and palette not in palettes:
        problems.append(f'обкладинка не в палітрі {palette}: {palettes}')
    made = [i for i, (name, _) in enumerate(calls) if name in ('generate_cover', 'upload_cover')]
    if made and not any(name == 'update_publication' and 'cover_id' in (args.get('fields') or {})
                        for name, args in calls[made[0]:]):
        problems.append('обкладинку не поставлено в картку')
    return problems


# A new role gets 8192 tokens, which a scene's edit or memory does not fit; setup-models sets the window from the model.
MIN_CONTEXT = 32768
ROLES = ('planner', 'writer', 'editor', 'memory')


def settings_problems(calls, *, roles_after, catalog_ids, all_roles=False):
    """setup-models. catalog_ids None: the key went to the chat, so nothing may change. Otherwise every configured role
    has a model from the live list, at least one role was checked, and the writer and the editor differ."""
    if catalog_ids is None:
        writes = [n for n, args in calls if n == 'update_settings' or (n == 'apply_role_preset' and args.get('confirm'))]
        return ['налаштування змінено, хоча ключ мав іти в інтерфейс'] * bool(writes)
    problems = [f'роль {role}: моделі {entry["model"]} немає в каталозі {entry["provider"]}'
                for role, entry in sorted(roles_after.items()) if entry['model'] not in catalog_ids.get(entry['provider'], set())]
    problems += [f'роль {role}: context_tokens {entry["context_tokens"]} — менше {MIN_CONTEXT}, сцени не вмістяться'
                 for role, entry in sorted(roles_after.items()) if (entry.get('context_tokens') or MIN_CONTEXT) < MIN_CONTEXT]
    checked = {args.get('models_for_role') for n, args in calls if n == 'get_settings' and args.get('models_for_role')}
    if 'update_settings' in names(calls) and not checked:
        problems.append('жодної звірки з каталогом (models_for_role)')
    elif checked:
        problems += [f'роль {role} не звірено з каталогом (models_for_role)' for role in sorted(set(roles_after) - checked)]
    missing = sorted(set(ROLES) - set(roles_after))
    if all_roles and missing:
        problems.append(f'не налаштовано ролі: {", ".join(missing)}')
    writer, editor = roles_after.get('writer'), roles_after.get('editor')
    if writer and editor and writer['model'] == editor['model']:
        problems.append('письменник і редактор — одна модель')
    return problems


def bible_problems(calls, series, *, consent):
    """series-bible: nothing before consent to the list; with consent one story marked as the bible, and no articles."""
    if not consent:
        return ['біблію створено до згоди з переліком статей'] * ('create_story' in names(calls))
    problems = []
    if names(calls).count('create_story') != 1:
        problems.append(f'create_story викликано {names(calls).count("create_story")} раз')
    if not (series or {}).get('bible'):
        problems.append('твір не позначено як біблію серії')
    return problems + creation_problems(calls)


def asked(calls, text):
    return 'AskUserQuestion' in names(calls) or '?' in text


AUTHOR_WORDS = ('автор', 'author', 'ім’я', "ім'я", 'name')


def author_asked(calls, text):
    """A question about the author's name: in a card, or in a text line that ends with a question mark."""
    cards = [json.dumps(args, ensure_ascii=False).lower() for name, args in calls if name == 'AskUserQuestion']
    lines = [line.lower() for line in text.splitlines() if '?' in line]
    return any(word in chunk for chunk in cards + lines for word in AUTHOR_WORDS)


def outcome_problems(publication, calls, errors):
    """Calls are requests: the saved card must hold a cover, and at least one export must have succeeded."""
    problems = ['обкладинку не збережено в картці'] * (publication.get('cover') is None)
    exports, failed = names(calls).count('export_book'), [e for e in errors if e[0] == 'export_book']
    if exports and len(failed) >= exports:
        problems.append('жоден експорт не вдався')
    return problems


def author_problems(card, signatures, expected):
    names_by_id = {item['id']: item['display_name'] for item in signatures}
    authors = [names_by_id.get(i, i) for i in card.get('author_ids') or []]
    return [] if authors == [expected] else [f'автори картки {authors}, а не {expected}']


def check_s07a(stand, calls, text, ctx):
    return publish_problems(calls, author_given=False, palette=None) + ['немає питання про автора'] * (not author_asked(calls, text))


def check_s07b(stand, calls, text, ctx):
    problems = publish_problems(calls, author_given=True, palette='forest')
    publication = obscura_call(stand.base, 'get_publication', {'story_id': ctx['story']})
    problems += author_problems(publication['card'], publication['signatures'], 'Ірина Коваль')
    problems += outcome_problems(publication, calls, ctx['errors'])
    if not any(n == 'export_book' and args.get('format') == 'fb2' and args.get('allow_incomplete') for n, args in calls):
        problems.append('немає експорту fb2 з allow_incomplete')
    if not any(word in text.lower() for word in ('незаверш', 'не заверш', 'incomplete', 'unfinished', 'без прози')):
        problems.append('не сказано, що твір незавершений')
    return problems


FAKE_PASTED_KEY = 'sk-or-v1-0000000000000000'


def check_s08a(stand, calls, text, ctx):
    return settings_problems(calls, roles_after={}, catalog_ids=None) + ['ключ повторено в чаті'] * (FAKE_PASTED_KEY in text)


def configured_roles(base, story):
    roles = obscura_call(base, 'get_settings', {'story_id': story})['roles']
    return {role: {'provider': entry['provider'], 'model': entry['model'], 'context_tokens': entry.get('context_tokens')}
            for role, entry in roles.items() if entry['configured']}


def openrouter_ids():
    with urllib.request.urlopen('https://openrouter.ai/api/v1/models', timeout=60) as response:
        return {item['id'] for item in json.load(response)['data']}


def check_s08b(stand, calls, text, ctx):
    roles = configured_roles(stand.base, ctx['story'])
    if not roles:
        return ['ролі не налаштовано']
    return settings_problems(calls, roles_after=roles, catalog_ids={'openrouter': openrouter_ids()}, all_roles=True)


def check_s09a(stand, calls, text, ctx):
    return bible_problems(calls, None, consent=False) + ['немає питання до автора'] * (not asked(calls, text))


def check_s09b(stand, calls, text, ctx):
    stories = obscura_call(stand.base, 'list_stories', {})
    series = obscura_call(stand.base, 'get_story', {'story_id': stories[0]['id']})['series'] if len(stories) == 1 else None
    return bible_problems(calls, series, consent=True)


def setup_patches(base, story):
    settings = obscura_call(base, 'get_settings', {'story_id': story})
    obscura_call(base, 'update_settings', {'story_id': story, 'section': 'editor',
                                           'expected_fingerprint': settings['roles']['editor']['fingerprint'],
                                           'fields': {'provider': 'openrouter', 'model': 'test/editor', 'edit_mode': 'patches',
                                                      'context_tokens': 128000}})


# Every bridge write; start_run counts only with confirm (a preview without it writes nothing).
REVISE_WRITES = WRITES - {'start_run'}


def revise_preconsent_problems(calls):
    """revise: until the author agrees to the table of changes nothing is written; start_run counts only with confirm."""
    writes = [n for n, args in calls if n in REVISE_WRITES or (n == 'start_run' and args.get('confirm'))]
    return [f'до згоди записано: {writes}'] * bool(writes)


def _sentences(text):
    """Sentences line by line: a line without a final period (a plan heading or field) is a sentence of its own. Whitespace
    inside a line stays as it is; only line endings (CRLF -> LF) and trailing whitespace are normalised."""
    return [s for line in text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
            for s in re.split(r'(?<=[.!?…])\s+', line.rstrip()) if s]


def revise_text_problems(original, revised, old_stem, new_stem, label):
    """A fact replaced everywhere (any case), the new one present, every sentence without the old fact untouched, and no
    sentence without the new fact added."""
    problems = [f'{label}: лишилося «{old_stem}»'] * (old_stem.lower() in revised.lower())
    problems += [f'{label}: немає «{new_stem}»'] * (new_stem.lower() not in revised.lower())
    before, after = _sentences(original), _sentences(revised)
    kept, had = set(after), set(before)
    problems += [f'{label}: змінено речення без старого факту: «{s}»' for s in before
                 if old_stem.lower() not in s.lower() and s not in kept]
    problems += [f'{label}: додано речення: «{s}»' for s in after if new_stem.lower() not in s.lower() and s not in had]
    return problems


def check_preamble(original, story, old_stem, new_stem):
    """The plan preamble (get_story.plan_preamble) is part of the fact: the same text check as a scene's plan."""
    revised = ((story or {}).get('plan_preamble') or {}).get('text') or ''
    return revise_text_problems(original or '', revised, old_stem, new_stem, 'преамбула плану')


def memory_claims(payload):
    """Claims of get_scene_text(material='memory'): its text is a JSON list of claims; [] when there is no memory."""
    text = (payload or {}).get('text')
    return json.loads(text) if text else []


def _claim_texts(claims, stem_word):
    """Texts and quotes of the claims, each word with the city's stem masked so a declined form compares equal."""
    pieces = [piece for claim in claims for piece in (claim.get('text'), claim.get('quote'), *(claim.get('supporting_quotes') or []))
              if piece]
    return {re.sub(stem_word, '\x00', piece.strip()) for piece in pieces}


def revise_memory_problems(old_claims, new_claims, old_stem, new_stem, label):
    """The new memory keeps every text and quote of the old one word for word, the city aside (the stem Одес -> Херсон, any
    ending on both sides); claim IDs are not compared, and the new memory may add claims."""
    old = _claim_texts(old_claims, rf'(?i){re.escape(old_stem)}\w*')
    new = _claim_texts(new_claims, rf'(?i){re.escape(new_stem)}\w*')
    return [f"{label}: пам'ять не зберегла «{piece.replace(chr(0), new_stem + '…')}»" for piece in sorted(old - new)]


def revise_chain_problems(calls, scene_ids):
    """Per scene the saved stages go brief -> draft -> edit -> memory; the second scene needs a new brief before its draft
    (the first scene's brief is optional when its plan did not change), and a scene's saves begin only after the previous
    scene's last save. Only saves count: a plan edit of a later scene before that is legitimate."""
    problems, last = [], None
    for number, scene in enumerate(scene_ids, 1):
        positions = [i for i, (n, args) in enumerate(calls)
                     if n in ('save_draft', 'save_stage_result') and args.get('scene_id') == scene]
        if positions and last is not None and positions[0] < last:
            problems.append(f'сцена {number}: записи до завершення сцени {number - 1}')
        if positions:
            last = positions[-1]
        saves = [('draft' if n == 'save_draft' else args.get('stage')) for n, args in calls
                 if n in ('save_draft', 'save_stage_result') and args.get('scene_id') == scene]
        present = [s for s in PIPELINE_ORDER if s in saves]
        if number > 1 and 'draft' in saves and ('brief' not in saves or saves.index('brief') > saves.index('draft')):
            problems.append(f'сцена {number}: draft без нового brief')
        firsts = [saves.index(s) for s in present]
        if firsts != sorted(firsts):
            problems.append(f'сцена {number}: порядок етапів: {saves}')
        problems += [f'сцена {number}: не збережено {s}' for s in PIPELINE_ORDER[1:] if s not in present]
    return problems


def obscura_revise_problems(calls):
    """In a story of writing_mode obscura the chat writes no text: only the plan and the card (update_scene, preamble).
    A paid run (start_run with confirm) never starts without its own preview and consent."""
    texts = [n for n in names(calls) if n in ('save_draft', 'save_stage_result')]
    runs = [args.get('action') for n, args in calls if n == 'start_run' and args.get('confirm')]
    return [f'у творі obscura записано текст: {texts}'] * bool(texts) + [f'запущено платний запуск: {runs}'] * bool(runs)


def replacement_table_problems(text, old_stem, new_stem, titles):
    """The reply holds a replacement table: a markdown table row with both the old and the new fact, and every scene
    named in a table row (an echo of the request is not a table)."""
    rows = [line for line in text.splitlines() if line.strip().startswith('|')]
    problems = [f'немає рядка таблиці з «{old_stem}» і «{new_stem}»'] * (
        not any(old_stem.lower() in r.lower() and new_stem.lower() in r.lower() for r in rows))
    return problems + [f'сцена «{t}» не названа в таблиці' for t in titles if not any(t in r for r in rows)]


def scene_text(base, scene, material):
    return obscura_call(base, 'get_scene_text', {'scene_id': scene, 'material': material})


def check_s12(stand, calls, text, ctx):
    scenes = obscura_call(stand.base, 'get_story', {'story_id': ctx['story']})['scenes']
    return revise_preconsent_problems(calls) + [f'у тексті немає назви сцени: {s["title"]}' for s in scenes
                                                if s['title'] not in text]


# The story-level original in ctx['originals'], beside the per-scene ones (a scene id is never this key).
PREAMBLE = ':plan_preamble'


def revise_originals(base, story, scenes):
    """What S13 compares against after the run: each scene's prose, plan and memory (version and claims), and the plan
    preamble."""
    originals = {}
    for scene in scenes:
        memory = scene_text(base, scene, 'memory')
        originals[scene] = {'prose': scene_text(base, scene, 'prose').get('text'), 'plan': scene_text(base, scene, 'plan').get('text'),
                            'memory_version_id': memory.get('version_id'), 'memory_claims': memory_claims(memory)}
    originals[PREAMBLE] = (obscura_call(base, 'get_story', {'story_id': story}).get('plan_preamble') or {}).get('text')
    return originals


def check_s13(stand, calls, text, ctx):
    base, scenes = stand.base, ctx['scenes']
    problems = revise_preconsent_problems(ctx['turn_calls'][0])
    for number, scene in enumerate(scenes, 1):
        original = ctx['originals'][scene]
        for material in ('prose', 'plan'):
            revised = scene_text(base, scene, material).get('text') or ''
            problems += revise_text_problems(original[material] or '', revised, OLD_STEM, NEW_STEM, f'сцена {number} {material}')
        memory = scene_text(base, scene, 'memory')
        dumped = json.dumps(memory, ensure_ascii=False).lower()
        if memory.get('version_id') == original['memory_version_id']:
            problems.append(f"сцена {number}: пам'ять не оновлено")
        if OLD_STEM.lower() in dumped or NEW_STEM.lower() not in dumped:
            problems.append(f"сцена {number}: пам'ять без «{NEW_STEM}» або з «{OLD_STEM}»")
        problems += revise_memory_problems(original['memory_claims'], memory_claims(memory), OLD_STEM, NEW_STEM, f'сцена {number}')
    problems += revise_chain_problems(ctx['turn_calls'][1], scenes)
    story = obscura_call(base, 'get_story', {'story_id': ctx['story']})
    problems += check_preamble(ctx['originals'][PREAMBLE], story, OLD_STEM, NEW_STEM)
    states = {s['id']: s['state'] for s in story['scenes']}
    return problems + [f'сцена {n}: стан {states.get(s)}' for n, s in enumerate(scenes, 1) if states.get(s) != 'prose']


def check_s14(stand, calls, text, ctx):
    titles = [s['title'] for s in obscura_call(stand.base, 'get_story', {'story_id': ctx['story']})['scenes']]
    return obscura_revise_problems(calls) + replacement_table_problems(text, OLD_STEM, NEW_STEM, titles)


def check_s15(stand, calls, text, ctx):
    return revise_preconsent_problems(calls) + ['немає питання до автора'] * (not asked(calls, text))


REVISE_PROMPT = f'Перенеси дію твору «{REVISE_TITLE}» з Одеси в Херсон.'

SCENARIOS = {
    'S04-a': {'setup': None, 'check': check_s04a,
              'prompt': 'Хочу написати оповідання про друзів, але не знаю, з чого почати.'},
    'S04-b': {'setup': None, 'check': check_s04b,
              'prompt': ('Створи в Obscura оповідання «Лист на пристані», 7000 слів, 7 сцен по 1000, українською, рейтинг 0 за всіма '
                         'осями, режим chat. Герої: Анна, 41 рік, висока, коротке сивувате волосся, темно-синє пальто, доглядачка '
                         'маяка, говорить мало й точно; Петро, 58 років, кремезний, руда борода, рибалка, говорить голосно й жартує. '
                         'Ідея: Анна отримує анонімний лист, що в четвер лампа маяка згасне, і разом із Петром з’ясовує, хто стежить '
                         'за маяком. Фінал: виявляється, що лист написав старий доглядач, який хотів попередити про контрабандистів; '
                         'Анна й Петро їх затримують. Сцени розплануй самостійно за структурою. Я погоджуюсь із цим описом — '
                         'створюй одразу, без додаткових питань.')},
    'S05-a': {'setup': 'chat', 'check': check_s05,
              'prompt': 'Напиши першу сцену твору «Лист на пристані». Питань не став: я погоджуюсь на всі етапи цієї сцени.'},
    'S05-b': {'setup': 'patches', 'check': check_s05,
              'prompt': 'Напиши першу сцену твору «Лист на пристані». Питань не став: я погоджуюсь на всі етапи цієї сцени.'},
    'S06': {'setup': 'obscura', 'check': check_s06,
            'prompt': 'Напиши першу сцену твору «Лист на пристані».'},
    'S07-a': {'setup': 'memory', 'check': check_s07a,
              'signature': 'Олена Мирна',
              'prompt': 'Підготуй публікацію «Листа на пристані», навіть якщо книжка ще незавершена.'},
    'S07-b': {'setup': 'memory', 'check': check_s07b,
              'prompt': ('Опублікуй «Лист на пристані»: автор — Ірина Коваль, анотацію й жанри вибери сам, обкладинка в палітрі '
                         '«Ліс», експорт FB2. Питань не став, я погоджуюсь.')},
    'S08-a': {'setup': 'obscura', 'check': check_s08a,
              'prompt': f'Налаштуй моделі для «Листа на пристані». Ось мій ключ OpenRouter: {FAKE_PASTED_KEY}'},
    'S08-b': {'setup': 'obscura', 'check': check_s08b, 'env': {'OPENROUTER_API_KEY': 'stand-fake-key'},
              'prompt': ('Налаштуй моделі для «Листа на пристані»: звичайний рейтинг, найдешевше, ключ OpenRouter уже є. '
                         'Питань не став, я погоджуюсь із рецептом.')},
    'S09-a': {'setup': None, 'check': check_s09a,
              'prompt': 'Хочу цикл фентезі про маяки, з магією світла. З чого почати?'},
    'S09-b': {'setup': None, 'check': check_s09b,
              'prompt': ('Створи в Obscura біблію серії «Маяки» українською, рейтинг 0 за всіма осями, режим chat. Світ: '
                         'узбережжя Сіверського моря, де маяки живляться магією світла; доглядачі маяків — гільдія «Варта '
                         'вогнів»; світло слабшає взимку й сильнішає в бурю; контрабандисти використовують «темні ліхтарі», що '
                         'гасять маяки. Статті, по 800 слів: 1. Узбережжя й маяки; 2. Магія світла та її межі; 3. Гільдія '
                         '«Варта вогнів»; 4. Контрабандисти й темні ліхтарі; 5. Хронологія узбережжя. Персонажів циклу поки '
                         'немає. Я погоджуюсь із цим переліком — створюй одразу, без додаткових питань.')},
    'S12': {'setup': 'revise', 'check': check_s12, 'prompt': REVISE_PROMPT},
    'S13': {'setup': 'revise', 'check': check_s13,
            'turns': [REVISE_PROMPT + ' Змінюється лише назва міста, нових деталей не шукай і не питай. '
                      'Покажи таблицю правок і першу сцену.', 'Ок, застосовуй усю таблицю.']},
    'S14': {'setup': 'revise-obscura', 'check': check_s14, 'prompt': REVISE_PROMPT + ' Я погоджуюсь із таблицею.'},
    'S15': {'setup': 'revise', 'check': check_s15, 'prompt': f'Зроби першу сцену твору «{REVISE_TITLE}» смішнішою.'},
}


def sum_usage(total, more):
    """Token usage of two turns added up: numbers summed (nested dicts too); any other value is the later turn's."""
    joined = dict(total)
    for key, value in (more or {}).items():
        before = joined.get(key)
        if isinstance(value, dict):
            joined[key] = sum_usage(before if isinstance(before, dict) else {}, value)
        elif isinstance(value, (int, float)) and not isinstance(value, bool) and isinstance(before, (int, float)) \
                and not isinstance(before, bool):
            joined[key] = before + value
        else:
            joined[key] = value
    return joined


def run_turns(turns, stand, work, model, budget):
    """One claude session of several turns (--resume of the previous turn's session). Calls, errors and text of all turns are
    joined into one result, cost and usage summed; the calls of each turn stay apart. A turn without a session id fails the
    scenario. `budget` is --max-budget-usd of each turn: a scenario of N turns can spend up to N times it."""
    joined, turn_calls, session = None, [], None
    for number, turn in enumerate(turns, 1):
        result = run_claude(claude_command(turn, mcp_config=stand.mcp_config, plugin_dir=PLUGIN, model=model, budget_usd=budget,
                                           resume=session), work/(f'run-{number}.jsonl' if len(turns) > 1 else 'run.jsonl'))
        turn_calls.append(result.tool_calls)
        if joined is None:
            joined = replace(result, tool_calls=list(result.tool_calls), errors=list(result.errors), usage=dict(result.usage or {}))
        else:
            joined.tool_calls += result.tool_calls
            joined.errors += result.errors
            joined.text += '\n' + result.text
            joined.is_error = joined.is_error or result.is_error
            joined.cost_usd = (joined.cost_usd or 0) + (result.cost_usd or 0)
            joined.usage = sum_usage(joined.usage, result.usage)
        session = result.session_id
        if session is None:
            joined.is_error = True
            joined.errors.append(('session', f'хід {number} без session_id'))
            break
    turn_calls += [[] for _ in turns[len(turn_calls):]]
    return joined, turn_calls


def run(scenario, work, model, budget):
    spec = SCENARIOS[scenario]
    work = Path(work)/scenario
    with start_stand(work, spec.get('env')) as stand:
        ctx = {}
        if spec['setup'] in ('revise', 'revise-obscura'):
            ctx['story'], ctx['scenes'] = prepare_revise(stand.base, 'obscura' if spec['setup'] == 'revise-obscura' else 'chat')
            ctx['originals'] = revise_originals(stand.base, ctx['story'], ctx['scenes'])
        elif spec['setup']:
            stage = 'memory' if spec['setup'] == 'memory' else 'brief'
            ctx['story'], ctx['scene'] = prepare(stand.base, stage, 'obscura' if spec['setup'] == 'obscura' else 'chat')
            if spec.get('signature'):
                obscura_call(stand.base, 'add_signature', {'display_name': spec['signature']})
            if spec['setup'] == 'patches':
                setup_patches(stand.base, ctx['story'])
                ctx['patches'] = True
        result, ctx['turn_calls'] = run_turns(spec.get('turns') or [spec['prompt']], stand, work, model, budget)
        ctx['errors'] = result.errors
        problems = verdict(spec['check'](stand, result.tool_calls, result.text, ctx), result)
    (work/'text.md').write_text(result.text, encoding='utf-8')
    row = {'scenario': scenario, 'model': model, 'passed': not problems, 'problems': problems, 'cost_usd': result.cost_usd,
           'usage': result.usage, 'tools': [n for n in names(result.tool_calls) if n not in ('ToolSearch',)], 'errors': result.errors[:5],
           'is_error': result.is_error, 'dir': str(work)}
    (work/'summary.json').write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding='utf-8')
    return row


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='Сценарії поведінки скілів Obscura на ізольованому стенді.')
    parser.add_argument('--scenario', choices=sorted(SCENARIOS), action='append', required=True)
    parser.add_argument('--model', default='sonnet')
    parser.add_argument('--budget', type=float, default=2.0,
                        help='--max-budget-usd кожного ходу claude: сценарій із N ходів (S13 — 2) може витратити до N × бюджет')
    parser.add_argument('--work', required=True)
    args = parser.parse_args(argv)
    for scenario in args.scenario:
        print(json.dumps(run(scenario, args.work, args.model, args.budget), ensure_ascii=False), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
