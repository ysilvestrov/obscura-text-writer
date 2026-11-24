"""IMPORT-DOCX: matching an editor's DOCX scene headings to the story's scenes (spec §3.4).

Order of evidence: the hidden `_os<scene id>` bookmark, then the exact title, then the position between two
recognized neighbours. A fragment that cannot be matched unambiguously stays unrecognized (`scene_id=None`)."""
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from ..publication.docx import BOOKMARK_PREFIX
from ..publication.docx_import import DocxManuscript

How = Literal['bookmark', 'title', 'position']


@dataclass(frozen=True)
class Fragment:
    scene_id: str | None
    heading: str
    first: int  # the scene text is paragraphs [first, last)
    last: int
    how: How | None


def _fragments(doc):
    paragraphs = doc.paragraphs
    starts = [i for i, p in enumerate(paragraphs) if p.style == 'Heading2']
    boundaries = sorted(starts + [i for i, p in enumerate(paragraphs) if p.style == 'Heading1'])
    out = []
    for i in starts:
        end = next((b for b in boundaries if b > i), len(paragraphs))
        out.append((i, end, ''.join(r.text for r in paragraphs[i].editor).strip()))
    return out


def match_scenes(doc: DocxManuscript, order: Sequence[tuple[str, str]]) -> tuple[list[Fragment], list[str]]:
    position = {scene_id: n for n, (scene_id, _) in enumerate(order)}
    raw = _fragments(doc)
    ids = [[b[len(BOOKMARK_PREFIX):] for b in doc.paragraphs[i].bookmarks if b.startswith(BOOKMARK_PREFIX)]
           for i, _, _ in raw]
    seen = Counter(x for found in ids for x in found)
    warnings: list[str] = []
    matched: list[tuple[str, How] | None] = [None] * len(raw)
    blocked = [False] * len(raw)  # a bookmark that cannot be trusted: no fallback may claim this heading

    for n, found in enumerate(ids):
        if not found:
            continue
        heading = raw[n][2]
        if len(found) == 1 and seen[found[0]] == 1 and found[0] in position:
            matched[n] = (found[0], 'bookmark')
            continue
        blocked[n] = True
        if any(seen[x] > 1 for x in found):
            warnings.append(f'Заголовок «{heading}»: закладка сцени повторюється, фрагмент не розпізнано.')
        elif not all(x in position for x in found):
            warnings.append(f'Заголовок «{heading}»: закладка не відповідає жодній сцені твору, фрагмент не розпізнано.')
        else:
            warnings.append(f'Заголовок «{heading}»: кілька закладок сцен, фрагмент не розпізнано.')

    def taken():
        return {m[0] for m in matched if m}

    def neighbours(n):
        before = max((position[matched[k][0]] for k in range(n) if matched[k]), default=-1)
        after = min((position[matched[k][0]] for k in range(n + 1, len(raw)) if matched[k]), default=len(order))
        return before, after

    titles = Counter(raw[n][2] for n in range(len(raw)) if matched[n] is None and not blocked[n])
    for n in range(len(raw)):
        if matched[n] is not None or blocked[n]:
            continue
        heading = raw[n][2]
        done = taken()
        free = [scene_id for scene_id, title in order if title == heading and scene_id not in done]
        if len(free) != 1 or titles[heading] != 1:
            continue
        before, after = neighbours(n)
        if before < position[free[0]] < after:
            matched[n] = (free[0], 'title')

    n = 0
    while n < len(raw):
        if matched[n] is not None:
            n += 1
            continue
        gap = [n]
        while gap[-1] + 1 < len(raw) and matched[gap[-1] + 1] is None:
            gap.append(gap[-1] + 1)
        before, after = neighbours(n)
        done = taken()
        free = [scene_id for scene_id, _ in order[before + 1:after] if scene_id not in done]
        if len(gap) == 1 and len(free) == 1 and not blocked[n]:
            matched[n] = (free[0], 'position')
            title = order[position[free[0]]][1]
            warnings.append(
                f'Назву змінено редактором: заголовок «{raw[n][2]}» прийнято за сцену «{title}» за місцем у тексті.')
        n = gap[-1] + 1

    fragments = []
    for (first, last, heading), found, blocked_one in zip(raw, matched, blocked):
        fragments.append(Fragment(found[0] if found else None, heading, first + 1, last, found[1] if found else None))
        if found is None and not blocked_one:
            warnings.append(f'Заголовок «{heading}»: не вдалося визначити сцену, фрагмент не розпізнано.')
    return fragments, warnings
