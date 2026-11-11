"""Plan of a newly added scene, carried over from the previous scene's plan (SCENE-PLAN-TEMPLATE); pure, no IO."""
import re

# Field -> labels read from an author plan, in either language whatever the story language is.
READ = {
    'location': ('Локація', 'Location'),
    'end': ('Кінець', 'End'),
    'cast': (r'Хто\s+бере\s+участь', 'Персонажі', 'Characters', 'Participants', 'Cast'),
    'happens': (r'Що\s+відбувається', r'What\s+happens'),
    'realisation': (r'Ключове\s+усвідомлення', r'Key\s+reali[sz]ation'),
    'emotion': (r'Емоційний\s+акцент', r'Emotional\s+focus'),
}
PATTERNS = {field: re.compile(r'(?i)^(?:' + '|'.join(labels) + r')\s*:\s*(.*)$') for field, labels in READ.items()}

# Lines of the new plan: (label, field of the previous plan that fills it or None). The labels are those of
# web/static/templates/story-plan*.md, so «Початок:»/«Start:» stays readable for memory/story_time.py.
LINES = {
    'uk': ('Сцена', [('Локація', 'location'), ('Початок', 'end'), ('Кінець', None), ('Хто бере участь', 'cast'),
                     ('Що було в попередніх сценах', 'happens'), ('Що відбувається', None), ('Дії', None), ('1.', None), ('2.', None), ('3.', None),
                     ('Ключове усвідомлення', 'realisation'), ('Емоційний акцент', 'emotion')]),
    'en': ('Scene', [('Location', 'location'), ('Start', 'end'), ('End', None), ('Characters', 'cast'),
                     ('Previously', 'happens'), ('What happens', None), ('Beats', None), ('1.', None), ('2.', None), ('3.', None),
                     ('Key realisation', 'realisation'), ('Emotional focus', 'emotion')]),
}


def plan_fields(text):
    """Non-empty one-line values of the carried fields; the first value wins, cast lines are joined."""
    from .characters.acquaintance import plain_line
    found = {}
    for line in (text or '').splitlines():
        plain = plain_line(line)
        for field, pattern in PATTERNS.items():
            match = pattern.match(plain)
            value = match.group(1).strip() if match else ''
            if not value:
                continue
            if field == 'cast' and field in found:
                found[field] += ', ' + value
            else:
                found.setdefault(field, value)
    return found


def next_scene_plan(language, number, title, fields):
    word, lines = LINES[language]
    out = [f'## {word} {number}: {" ".join(title.split())}']
    for label, field in lines:
        value = fields.get(field, '') if field else ''
        label = label if label[0].isdigit() else label + ':'
        out.append(f'{label} {value}' if value else label)
    return '\n'.join(out) + '\n'
