"""MANUSCRIPT-IMPORT: detects chapters, parts, scene separators and front matter in a paragraph sequence.

Pure functions over `ManuscriptParagraph` (spec §3.3–3.5). Scene ranges are inclusive `ManuscriptParagraph.index` values of
prose paragraphs only; a scene's first paragraph can precede a chapter heading (text under a part heading is prepended to
that part's first chapter), so a range may contain heading indices: filter by `Structure.prose_indices`. Paragraph
`index` equals the list position (Task 1 re-indexing); `detect` keys internal sets by position and reports `index`.
"""
import math
import re
from bisect import bisect_left
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from .manuscript_read import ManuscriptParagraph

SCENE_WORD_LIMIT = 2500
PROLOGUE_MIN_WORDS = 50
WINDOW = 0.2
PARTS_NOT_ALLOWED = 'частини доступні у виданні з довгою прозою'
LONG_PARAGRAPH = 'довгий абзац без меж'
NO_HEADINGS = 'У рукописі немає заголовків і маркерів глав: увесь текст стане однією главою'
DOES_NOT_FIT = "Частина сцени не вміститься в ліміти пам'яті навіть після поділу"
SINGLE_CHAPTER_TITLE = 'Рукопис'
# A paragraph that is only one of these words (any case, optional trailing punctuation) is a chapter boundary in marker
# mode; the title is the word as the author typed it. Not part of `chapter_markers`: these chapters carry no number.
STANDALONE_CHAPTERS = ('Пролог', 'Епілог', 'Післямова', 'Інтерлюдія', 'Prologue', 'Epilogue', 'Afterword', 'Interlude')
MAX_SCENE_TITLE = 200  # ManuscriptApplyScene.title
MAX_BOOK_TITLE = 300  # StoryCreate.title
ROLES = ('prose', 'front_matter', 'chapter_heading', 'part_heading', 'separator', 'title', 'dropped')

_WORD = re.compile(r"[^\W_]+(?:['’ʼ][^\W_]+)*")
_FIRST_WORD = re.compile(r'^\s*([^\W\d_]+)')
_ROMAN = re.compile(r'(?=[IVXLCDM])M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})')
_CYRILLIC_ROMAN = str.maketrans('ІХСМ', 'IXCM')
_SEPARATOR_CHARS = set('*#—–~⁂•· \t')
_TITLE_LEAD = ' \t.:—–-)'
_DIALOGUE = ('—', '–', '-', '«', '„', '“', '"')
_SENTENCE_END = re.compile(r'[.!?…]["\'»”’)]*$')
_STANDALONE = {word.casefold() for word in STANDALONE_CHAPTERS}
_STANDALONE_TRAIL = '.:!?…;,'


def _ordinals() -> dict[str, int]:
    table: dict[str, int] = {}
    uk = [('перш', 1), ('друг', 2), ('четверт', 4), ("п'ят", 5), ('шост', 6), ('сьом', 7), ('восьм', 8),
          ("дев'ят", 9), ('десят', 10), ('одинадцят', 11), ('дванадцят', 12), ('тринадцят', 13),
          ('чотирнадцят', 14), ("п'ятнадцят", 15), ('шістнадцят', 16), ('сімнадцят', 17), ('вісімнадцят', 18),
          ("дев'ятнадцят", 19), ('двадцят', 20)]
    for stem, value in uk:
        for ending in ('ий', 'а', 'е'):
            table[stem + ending] = value
    for ending in ('ій', 'я', 'є'):
        table['трет' + ending] = 3
    cardinal = ['one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve',
                'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen', 'twenty']
    ordinal = ['first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth', 'ninth', 'tenth',
               'eleventh', 'twelfth', 'thirteenth', 'fourteenth', 'fifteenth', 'sixteenth', 'seventeenth',
               'eighteenth', 'nineteenth', 'twentieth']
    for value, (card, order) in enumerate(zip(cardinal, ordinal), start=1):
        table[card] = value
        table[order] = value
    return table


_ORDINALS = _ordinals()


@dataclass(frozen=True)
class ParseSettings:
    chapter_markers: tuple[str, ...] = ('Глава', 'Розділ', 'Chapter')
    part_markers: tuple[str, ...] = ('Частина', 'Книга', 'Part', 'Book')
    chapter_source: Literal['auto', 'markers', 1, 2, 3] = 'auto'
    parts_allowed: bool = True
    prologue_title: str = 'Пролог'
    single_chapter_title: str = SINGLE_CHAPTER_TITLE


@dataclass(frozen=True)
class ProposedScene:
    start: int
    end: int
    title: str
    words: int
    part_index: int | None
    proposed: bool
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class Structure:
    """`parts` — (index of the heading paragraph, name); `ProposedScene.part_index` is a position in `parts`.
    `chapter_source` — 'markers', 'level:N' (1–3) or 'none'. `dropped` — (index, text, reason) of paragraphs not imported:
    reason 'part_heading' (parts not allowed) or 'toc' (Word's table of contents). `prose_indices` — every paragraph index
    inside some scene, in file order. `roles` — one of `ROLES` per paragraph, by position."""
    title_suggestion: str | None
    chapter_source: str
    parts: tuple[tuple[int, str], ...]
    scenes: tuple[ProposedScene, ...]
    front_matter: tuple[int, ...]
    dropped: tuple[tuple[int, str, str], ...]
    warnings: tuple[str, ...]
    prose_indices: tuple[int, ...] = ()
    roles: tuple[str, ...] = ()


def words(text: str) -> int:
    return len(_WORD.findall(text))


def _token(text: str) -> str:
    match = _WORD.match(text)
    return match.group(0).replace('’', "'").replace('ʼ', "'") if match else ''


def _is_number(token: str) -> bool:
    if not token:
        return False
    if token.isdigit():
        return True
    return bool(_ROMAN.fullmatch(token.translate(_CYRILLIC_ROMAN))) or token.casefold() in _ORDINALS


def _marker_title(text: str, markers: Sequence[str], need_number: bool) -> str | None:
    """Returns the chapter title when `text` is a marker paragraph, else None."""
    stripped = text.strip()
    if not stripped or len(stripped) > 120:
        return None
    first = _FIRST_WORD.match(stripped)
    if not first or first.group(1).casefold() not in {m.casefold() for m in markers}:
        return None
    rest = stripped[first.end():]
    lead = rest.lstrip()
    token = _token(lead)
    if _is_number(token) and (len(lead) == len(token) or not lead[len(token)].isalnum()):
        remainder = lead[len(token):]
    elif need_number:
        return None
    elif not rest.strip():
        remainder = ''
    elif lead[0] in '.:—–-)':
        remainder = rest
    else:
        return None
    title = remainder.lstrip(_TITLE_LEAD).strip()
    return title or stripped


def _standalone_title(text: str) -> str | None:
    """The chapter title when `text` is only a standalone chapter word (`STANDALONE_CHAPTERS`), else None."""
    stripped = text.strip()
    if len(stripped) > 120:
        return None
    word = stripped.rstrip(_STANDALONE_TRAIL).strip()
    return word if word.casefold() in _STANDALONE else None


def _clamped(text: str, limit: int, suffix: str = '') -> str:
    """`text + suffix` within `limit` characters: a too long `text` is cut and ends with «…», the suffix is kept."""
    if len(text) + len(suffix) <= limit:
        return text + suffix
    return text[:limit - len(suffix) - 1].rstrip() + '…' + suffix


def _is_separator(p: ManuscriptParagraph) -> bool:
    if p.heading_level is not None or p.is_title:
        return False
    text = p.text.strip()
    significant = sum(1 for c in text if not c.isspace())
    return 1 <= significant <= 12 and all(c in _SEPARATOR_CHARS for c in text)


def _starts_dialogue(p: ManuscriptParagraph) -> bool:
    return p.text.lstrip().startswith(_DIALOGUE)


def split_points(paragraphs: Sequence[ManuscriptParagraph], start: int, end: int, parts: int) -> list[int]:
    """Mechanical scene boundaries (spec §3.5): the `ManuscriptParagraph.index` that begins each part after the first.

    `paragraphs` are prose paragraphs; those with `start <= index <= end` are split into `parts` parts of about equal
    length. Fewer boundaries are returned when the range has too few paragraph boundaries."""
    items = [p for p in paragraphs if start <= p.index <= end]
    count = len(items)
    needed = min(parts - 1, count - 1)
    if needed <= 0:
        return []
    before = [0]
    for p in items:
        before.append(before[-1] + words(p.text))
    total = before[-1]
    part_length = total / parts
    chosen: list[int] = []
    previous = 0
    for i in range(1, needed + 1):
        target = i * total / parts
        low, high = previous + 1, count - (needed - i)  # allowed boundaries: low <= j < high
        margin = WINDOW * part_length
        first = max(low, bisect_left(before, target - margin, low, high))
        last = max(first, bisect_left(before, target + margin + 1e-9, first, high))
        window = range(first, last)

        def rank(j: int) -> tuple[int, float]:
            if not window:
                level = 3
            elif items[j].after_break:
                level = 0
            elif not _starts_dialogue(items[j]):
                level = 1
            elif _SENTENCE_END.search(items[j - 1].text.rstrip()):
                level = 2
            else:
                level = 3
            return (level, abs(before[j] - target))

        if window:
            best = min(window, key=rank)
        else:
            at = min(max(bisect_left(before, target, low, high), low), high - 1)
            best = min((j for j in (at - 1, at) if low <= j < high), key=rank)
        chosen.append(best)
        previous = best
    return [items[j].index for j in chosen]


def _joined(items: Sequence[ManuscriptParagraph]) -> str:
    return '\n\n'.join(p.text for p in items)


def _pieces(segment: list[ManuscriptParagraph], fits: Callable[[str], bool]):
    """Splits one separator-free run of prose into (paragraphs, proposed, warnings) pieces."""
    cache: dict[str, bool] = {}
    raw_fits = fits

    def fits(text: str) -> bool:
        if text not in cache:
            cache[text] = raw_fits(text)
        return cache[text]

    total = sum(words(p.text) for p in segment)
    first, last = segment[0].index, segment[-1].index

    def cut(parts: int) -> list[list[ManuscriptParagraph]]:
        points = set(split_points(segment, first, last, parts))
        groups: list[list[ManuscriptParagraph]] = [[]]
        for p in segment:
            if p.index in points:
                groups.append([])
            groups[-1].append(p)
        return groups

    base = math.ceil(total / SCENE_WORD_LIMIT) if total > SCENE_WORD_LIMIT else 1
    cap = len(segment)
    if base == 1 and fits(_joined(segment)):
        groups = [segment]
    else:
        # Fitting is not monotone in k (boundaries snap to paragraph edges), so the search is bounded, not exhaustive:
        # double from the word-count baseline, bisect between the last k that failed and the first that fit, then try
        # the three smaller k and keep the smallest that fits. Absolute minimality is not guaranteed.
        def ok(parts: int) -> bool:
            return all(fits(_joined(g)) for g in cut(parts))

        low = max(base, 2)
        good = None
        if low <= cap:
            if ok(low):
                good = low
            else:
                bad = low
                while good is None and bad < cap:
                    step = min(bad * 2, cap)
                    if ok(step):
                        good = step
                    else:
                        bad = step
                if good is not None:
                    while good - bad > 1:
                        mid = (bad + good) // 2
                        bad, good = (bad, mid) if ok(mid) else (mid, good)
                    for parts in range(good - 1, max(good - 4, low - 1), -1):
                        if ok(parts):
                            good = parts
        # Nothing fits: the word-count baseline (one scene up to the threshold), never a forced split into paragraphs.
        groups = cut(good) if good is not None else ([segment] if base == 1 else cut(base))
    result = []
    for number, group in enumerate(groups):
        warnings = []
        if sum(words(p.text) for p in group) > SCENE_WORD_LIMIT:
            warnings.append(LONG_PARAGRAPH)
        elif not fits(_joined(group)):
            warnings.append(DOES_NOT_FIT)
        result.append((group, number > 0, tuple(warnings)))
    return result


@dataclass
class _Section:
    kind: str  # 'front' | 'chapter' | 'loose'
    title: str
    part_index: int | None
    items: list  # ManuscriptParagraph, or None for a separator


def detect(paragraphs: Sequence[ManuscriptParagraph], settings: ParseSettings = ParseSettings(),
           fits: Callable[[str], bool] = lambda text: True) -> Structure:
    paras = list(paragraphs)
    warnings: list[str] = []
    skipped = {i for i, p in enumerate(paras) if p.skip}
    separators = {i for i, p in enumerate(paras) if i not in skipped and _is_separator(p)}
    # Only the first Title-styled paragraph is the book title; any further one is ordinary prose.
    titles = {next((i for i, p in enumerate(paras) if p.is_title and i not in skipped), None)} - {None}
    plain = [i for i in range(len(paras)) if i not in separators and i not in titles and i not in skipped]
    chapter_marks = {i: t for i in plain
                     if (t := _marker_title(paras[i].text, settings.chapter_markers, False)) is not None}
    standalone = {i: t for i in plain if i not in chapter_marks and (t := _standalone_title(paras[i].text)) is not None}
    part_marks = {i: paras[i].text.strip() for i in plain if i not in chapter_marks
                  and _marker_title(paras[i].text, settings.part_markers, True) is not None}
    headings = [i for i in plain if paras[i].heading_level is not None]

    source, level = settings.chapter_source, 0
    if source == 'auto':
        if len(chapter_marks) >= 2:
            source = 'markers'
        else:
            counts: dict[int, int] = {}
            for i in headings:
                if i not in part_marks and paras[i].heading_level <= 2:
                    counts[paras[i].heading_level] = counts.get(paras[i].heading_level, 0) + 1
            repeated = [lv for lv, n in counts.items() if n >= 2]
            source, level = ('level', min(repeated)) if repeated else ('none', 0)
    elif source in (1, 2, 3):
        source, level = 'level', source - 1
    chapters: dict[int, str] = {}
    if source == 'markers':
        chapters = {**chapter_marks, **standalone}
    elif source == 'level':
        for i in headings:
            if paras[i].heading_level == level and i not in part_marks:
                chapters[i] = _marker_title(paras[i].text, settings.chapter_markers, False) or paras[i].text.strip()
    if not chapters:
        if not part_marks:  # with part markers each part becomes its own scene, not one chapter
            warnings.append(NO_HEADINGS)
        chapter_source = 'none'
    else:
        chapter_source = 'markers' if source == 'markers' else f'level:{level + 1}'

    part_heads = dict(part_marks)  # parts come only from marker paragraphs, with or without chapters
    title_suggestion = next((paras[i].text.strip() for i in sorted(titles)), None)
    title_positions = set(titles)
    if chapters:
        first_chapter = min(chapters)
        higher = ([i for i in headings if i not in chapters and i not in part_marks and paras[i].heading_level < level]
                  if source == 'level' else [])
        if title_suggestion is None:  # a standalone chapter word (Пролог) is never the book's title
            candidates = [i for i in (higher if source == 'level' else headings)
                          if i < first_chapter and i not in part_marks and i not in standalone]
            if candidates and (not part_marks or candidates[0] < min(part_marks)):
                title_suggestion = paras[candidates[0]].text.strip()
                title_positions.add(candidates[0])
        for i in higher:  # a shallower non-marker heading is itself a chapter boundary
            if i not in title_positions:
                chapters[i] = paras[i].text.strip()

    parts: list[tuple[int, str]] = []
    dropped: list[tuple[int, str]] = []
    if chapters:
        current = _Section('front', settings.prologue_title, None, [])
    else:  # before the first part marker, if any: a 'loose' section makes no "chapter without text" warning
        current = _Section('loose' if part_heads else 'chapter', title_suggestion or settings.single_chapter_title,
                           None, [])
    sections = [current]
    part_index: int | None = None
    roles: list[str] = [''] * len(paras)
    for i, p in enumerate(paras):
        if i in skipped:
            roles[i] = 'dropped'
            dropped.append((p.index, p.text.strip(), p.skip))
            continue
        if i in title_positions:
            roles[i] = 'title'
            continue
        if i in part_heads:
            if settings.parts_allowed:
                roles[i] = 'part_heading'
                parts.append((p.index, part_heads[i]))
                part_index = len(parts) - 1
            else:
                roles[i] = 'dropped'
                dropped.append((p.index, part_heads[i], 'part_heading'))
            current = _Section('loose', part_heads[i], part_index, [])
            sections.append(current)
        elif i in chapters:
            roles[i] = 'chapter_heading'
            items = []
            if current.kind == 'loose':  # text between a part heading and its first chapter opens that chapter
                items, current.items = current.items, []
            current = _Section('chapter', chapters[i], part_index, items)
            sections.append(current)
        elif i in separators:
            roles[i] = 'separator'
            current.items.append(None)
        else:
            current.items.append(p)
    if part_heads and not settings.parts_allowed:
        warnings.append(PARTS_NOT_ALLOWED)

    scenes: list[ProposedScene] = []
    front_matter: list[int] = []
    prose: list[int] = []
    for section in sections:
        segments: list[list[ManuscriptParagraph]] = [[]]
        for item in section.items:
            if item is None:
                segments.append([])
            else:
                segments[-1].append(item)
        segments = [s for s in segments if s]
        short_front = section.kind == 'front' and sum(words(p.text) for s in segments for p in s) <= PROLOGUE_MIN_WORDS
        if short_front:
            front_matter.extend(p.index for s in segments for p in s)
            continue
        pieces = [piece for segment in segments for piece in _pieces(segment, fits)]
        if not pieces and section.kind == 'chapter' and section.title:
            warnings.append(f'Глава «{section.title}» без тексту: сцену не створено')
        for number, (group, proposed, scene_warnings) in enumerate(pieces, start=1):
            title = _clamped(section.title, MAX_SCENE_TITLE, f' ({number})' if len(pieces) > 1 else '')
            scenes.append(ProposedScene(group[0].index, group[-1].index, title, sum(words(p.text) for p in group),
                                        section.part_index, proposed, scene_warnings))
            prose.extend(p.index for p in group)
            warnings.extend(f'{title}: {w}' for w in scene_warnings)
    for index in front_matter:
        roles[index] = 'front_matter'
    for index in prose:
        roles[index] = 'prose'
    if title_suggestion is not None:
        title_suggestion = _clamped(title_suggestion, MAX_BOOK_TITLE)
    return Structure(title_suggestion, chapter_source, tuple(parts), tuple(scenes), tuple(sorted(front_matter)),
                     tuple(dropped), tuple(warnings), tuple(sorted(prose)), tuple(roles))


def prose_indices(paragraphs: Sequence[ManuscriptParagraph], settings: ParseSettings = ParseSettings()) -> list[int]:
    """Indices of all prose paragraphs inside scenes (what author-moved boundaries are validated against)."""
    return list(detect(paragraphs, settings).prose_indices)
