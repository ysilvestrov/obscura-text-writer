"""Deterministic injection of known mistakes into a clean Ukrainian text: the gold list for the editor bench (#260 part 2).

Three categories, ten each, every mistake in its own sentence. A mistake is a span of the broken text (`start`, `wrong`)
and the form a good editor restores (`right`); for a removed comma both strings include the neighbouring words.
"""
import random
import re
from dataclasses import dataclass

CATEGORIES = ('spelling', 'punctuation', 'russism')
PER_CATEGORY = 10

# Correct Ukrainian word → a russism or surzhyk form an editor should replace back.
RUSSISMS = {
    'навіть': 'даже', 'раптом': 'вдруг', 'майже': 'почті', 'звичайно': 'конєшно', 'нарешті': 'наконєц',
    'мабуть': 'навєрно', 'відразу': 'сразу', 'одразу': 'сразу', 'також': 'тоже', 'ніколи': 'нікогда',
    'протягом': 'на протязі', 'наступного': 'слідуючого', 'наступний': 'слідуючий', 'наступна': 'слідуюча',
    'приблизно': 'примєрно', 'зовсім': 'совсєм', 'дійсно': 'дєйствітельно', 'згодом': 'потом', 'поки': 'пока',
    'завжди': 'всігда', 'тільки': 'тіко', 'взагалі': 'вообщє', 'щоб': 'чтоб', 'тепер': 'тепер',
}
RUSSISMS = {k: v for k, v in RUSSISMS.items() if k != v}
WORD = re.compile(r"[^\W\d_]+(?:[’'-][^\W\d_]+)*")
SENTENCE = re.compile(r'[^.!?…]+[.!?…]*')


@dataclass(frozen=True)
class Mistake:
    category: str
    sentence: int
    start: int
    wrong: str
    right: str


def _sentences(text):
    return [(m.start(), m.end()) for m in SENTENCE.finditer(text) if m.group().strip()]


def _russism(sentence, base, rng):
    options = [m for m in WORD.finditer(sentence) if m.group().lower() in RUSSISMS]
    if not options:
        return None
    m = rng.choice(options)
    word = m.group()
    wrong = RUSSISMS[word.lower()]
    if word[0].isupper():
        wrong = wrong[0].upper() + wrong[1:]
    return base + m.start(), word, wrong


def _punctuation(sentence, base, rng):
    commas = [m for m in re.finditer(r'([^\W\d_]+), ([^\W\d_]+)', sentence)]
    dashes = [m for m in re.finditer(r'([^\W\d_]+) — ([^\W\d_]+)', sentence)]
    pool = dashes + commas if dashes and rng.random() < 0.3 else commas or dashes
    if not pool:
        return None
    m = rng.choice(pool)
    right = m.group()
    wrong = right.replace(', ', ' ', 1) if ', ' in right else right.replace(' — ', ' - ', 1)
    return base + m.start(), right, wrong


def _typo(word, rng):
    inner = range(1, len(word) - 2)
    kind = rng.choice(('swap', 'drop', 'vowel'))
    if kind == 'vowel':
        spots = [i for i, ch in enumerate(word) if ch in 'иі' and i > 0]
        if spots:
            i = rng.choice(spots)
            return word[:i] + ('і' if word[i] == 'и' else 'и') + word[i + 1:]
    i = rng.choice(list(inner))
    if kind == 'drop':
        return word[:i] + word[i + 1:]
    swapped = word[:i] + word[i + 1] + word[i] + word[i + 2:]
    return swapped if swapped != word else word[:i] + word[i + 1:]


def _spelling(sentence, base, rng):
    options = [m for m in WORD.finditer(sentence) if len(m.group()) >= 6 and m.group().isalpha()
               and m.group().lower() not in RUSSISMS]
    if not options:
        return None
    m = rng.choice(options)
    return base + m.start(), m.group(), _typo(m.group(), rng)


FINDERS = {'russism': _russism, 'punctuation': _punctuation, 'spelling': _spelling}


def inject(text: str, seed: int) -> tuple[str, list[Mistake]]:
    """The broken text and its gold list, sorted by position. Refuses a text with too few usable sentences."""
    rng = random.Random(seed)
    spans = _sentences(text)
    free = list(range(len(spans)))
    rng.shuffle(free)
    chosen = []
    # The scarcest category first, so russisms get the few sentences that have a known word.
    for category in CATEGORIES[::-1]:
        found = 0
        for index in list(free):
            if found == PER_CATEGORY:
                break
            a, b = spans[index]
            hit = FINDERS[category](text[a:b], a, rng)
            if hit:
                chosen.append((category, index) + hit)
                free.remove(index)
                found += 1
        if found < PER_CATEGORY:
            raise ValueError(f'Замало речень: для категорії {category} знайдено {found} із {PER_CATEGORY}')
    broken, shift, gold = text, 0, []
    for category, index, start, right, wrong in sorted(chosen, key=lambda item: item[2]):
        at = start + shift
        broken = broken[:at] + wrong + broken[at + len(right):]
        gold.append(Mistake(category, index, at, wrong, right))
        shift += len(wrong) - len(right)
    return broken, gold
