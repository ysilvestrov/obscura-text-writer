"""Score an edited text against the gold list: per category fixed / missed / other, plus changes outside the gold.

`fixed` is strict: the whole touched region equals the gold. `fixed_lenient` also counts a mistake whose right form is
there and whose wrong form is gone while a neighbouring word changed too (a subset of fixed + other).

Counts only — no text leaves this function. Alignment is by tokens (words and punctuation marks) of the broken text.
"""
import re
from difflib import SequenceMatcher

from .inject import CATEGORIES

TOKEN = re.compile(r"[^\W_]+(?:[’'-][^\W_]+)*|[^\w\s]")


def _tokens(text):
    return [(m.group(), m.start(), m.end()) for m in TOKEN.finditer(text)]


def _touches(op, lo, hi):
    _, i1, i2, _, _ = op
    return i1 < hi and i2 > lo if i1 != i2 else lo < i1 < hi


def _mapped(ops, index, after):
    """Position in the edited tokens of a boundary between broken tokens; `after` skips an insertion at the boundary."""
    hits = []
    for tag, i1, i2, j1, j2 in ops:
        if i1 <= index <= i2:
            hits.append(j1 + index - i1 if tag == 'equal' else j1 if index == i1 else j2)
    return max(hits) if after else min(hits)


def _contains(tokens, part):
    """The lenient check: `part` appears in `tokens` as a contiguous run (a fix next to a neighbouring change)."""
    return any(tokens[i:i + len(part)] == part for i in range(len(tokens) - len(part) + 1))


def score(gold, broken: str, edited: str) -> dict:
    a, b = _tokens(broken), _tokens(edited)
    ops = SequenceMatcher(None, [t[0] for t in a], [t[0] for t in b], autojunk=False).get_opcodes()
    changed = [op for op in ops if op[0] != 'equal']
    result = {c: {'fixed': 0, 'missed': 0, 'other': 0, 'fixed_lenient': 0} for c in CATEGORIES}
    regions = []
    for m in gold:
        inside = [i for i, (_, s, e) in enumerate(a) if s < m.start + len(m.wrong) and e > m.start]
        lo, hi = inside[0], inside[-1] + 1
        regions.append((lo, hi))
        touching = [op for op in changed if _touches(op, lo, hi)]
        if not touching:
            result[m.category]['missed'] += 1
            continue
        first, last = min([lo] + [op[1] for op in touching]), max([hi] + [op[2] for op in touching])
        got = [t[0] for t in b[_mapped(ops, first, True):_mapped(ops, last, False)]]
        s, e = a[first][1], a[last - 1][2]
        expected = [t[0] for t in _tokens(broken[s:m.start] + m.right + broken[m.start + len(m.wrong):e])]
        result[m.category]['fixed' if got == expected else 'other'] += 1
        result[m.category]['fixed_lenient'] += _contains(got, [t[0] for t in _tokens(m.right)]) and not _contains(got, [t[0] for t in _tokens(m.wrong)])
    result['off_gold_tokens'] = sum(max(op[2] - op[1], op[4] - op[3]) for op in changed
                                    if not any(_touches(op, lo, hi) for lo, hi in regions))
    # A deletion that spans a mistake is counted as "other", not off-gold; the word share shows a shortened text.
    result['words_kept'] = round(len(edited.split()) / max(1, len(broken.split())), 3)
    return result
