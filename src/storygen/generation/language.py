"""Local, non-blocking evidence-based hints; never a literary quality score."""
import hashlib
import json
import re
from importlib.resources import files


def language_suite():
    return json.loads(files('storygen.generation').joinpath('resources', 'language_regressions_v1.json').read_text(encoding='utf-8'))


def language_suite_hash():
    return hashlib.sha256(json.dumps(language_suite(), ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def language_warnings(text):
    warnings = []
    def add(code, match, message):
        warnings.append(dict(code=code, start=match.start(), end=match.end(), quote=match.group(), message=message))
    for match in re.finditer('[ыэъёЫЭЪЁ]', text):
        add('non_ukrainian_letters', match, 'Літера не належить українській абетці; перевірте, чи це навмисна цитата.')
    for match in re.finditer(r"[^\W\d_]+(?:[’'ʼ][^\W\d_]+)*", text):
        word = match.group()
        if re.search('[a-zA-Z]', word) and re.search('[а-яА-ЯіІїЇєЄґҐёЁ]', word):
            add('mixed_alphabet', match, 'У слові змішані латинські й кириличні літери; перевірте також написання імені.')
    for match in re.finditer(r'\b([^\W\d_]+)[ \t]+\1\b', text, re.IGNORECASE):
        add('repeated_word', match, 'Повтор сусідніх слів; він може бути авторським прийомом.')
    for match in re.finditer(r'(?m)^[ \t]*[-–](?=[ \t]+\S)', text):
        # Highlight only the dash, not indentation.
        start = match.end() - 1
        warnings.append(dict(code='dialogue_dash', start=start, end=match.end(), quote=text[start:match.end()],
                             message='Якщо це репліка, оформіть її довгим тире; маркер списку може бути навмисним.'))
    for case in language_suite()['cases']:
        for match in re.finditer(case['pattern'], text, re.IGNORECASE):
            add('known_regression', match, case['message'])
    return sorted(warnings, key=lambda warning: (warning['start'], warning['code']))
