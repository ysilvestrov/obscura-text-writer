"""MANUSCRIPT-IMPORT: detects chapters, parts, scene separators and front matter in a paragraph sequence.

Pure functions over `ManuscriptParagraph` (spec §3.3–3.5). Scene ranges are inclusive `ManuscriptParagraph.index` values of
prose paragraphs only: chapter/part headings, the book title and separator paragraphs never fall inside a scene.
"""
import math
import re
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

_WORD = re.compile(r"[^\W_]+(?:['’ʼ][^\W_]+)*")
_FIRST_WORD = re.compile(r'^\s*([^\W\d_]+)')
_ROMAN = re.compile(r'(?=[IVXLCDM])M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})')
_SEPARATOR_CHARS = set('*#—–~⁂•· \t')
_TITLE_LEAD = ' \t.:—–-)'
_DIALOGUE = ('—', '–', '-', '«', '„', '“', '"')
_SENTENCE_END = re.compile(r'[.!?…]["\'»”’)]*$')


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
    `chapter_source` — 'markers', 'level:N' (1–3) or 'none'. `dropped` — (index, text) of part headings not imported.
    `prose_indices` — every paragraph index inside some scene, in file order."""
    title_suggestion: str | None
    chapter_source: str
    parts: tuple[tuple[int, str], ...]
    scenes: tuple[ProposedScene, ...]
    front_matter: tuple[int, ...]
    dropped: tuple[tuple[int, str], ...]
    warnings: tuple[str, ...]
    prose_indices: tuple[int, ...] = ()


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
    return bool(_ROMAN.fullmatch(token)) or token.casefold() in _ORDINALS


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
        available = range(previous + 1, count - (needed - i))
        window = [j for j in available if abs(before[j] - target) <= WINDOW * part_length]

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

        best = min(window or available, key=rank)
        chosen.append(best)
        previous = best
    return [items[j].index for j in chosen]


def _joined(items: Sequence[ManuscriptParagraph]) -> str:
    return '\n\n'.join(p.text for p in items)


def _pieces(segment: list[ManuscriptParagraph], fits: Callable[[str], bool]):
    """Splits one separator-free run of prose into (paragraphs, proposed, warnings) pieces."""
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
    if base == 1 and fits(_joined(segment)):
        groups = [segment]
    else:
        groups = [segment]
        for parts in range(max(base, 2), len(segment) + 1):
            groups = cut(parts)
            if all(fits(_joined(g)) for g in groups):
                break
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
    separators = {i for i, p in enumerate(paras) if _is_separator(p)}
    titles = {i for i, p in enumerate(paras) if p.is_title}
    plain = [i for i in range(len(paras)) if i not in separators and i not in titles]
    chapter_marks = {i: t for i in plain
                     if (t := _marker_title(paras[i].text, settings.chapter_markers, False)) is not None}
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
        chapters = dict(chapter_marks)
    elif source == 'level':
        for i in headings:
            if paras[i].heading_level == level and i not in part_marks:
                chapters[i] = _marker_title(paras[i].text, settings.chapter_markers, False) or paras[i].text.strip()
    if not chapters:
        warnings.append(NO_HEADINGS)
        chapter_source = 'none'
    else:
        chapter_source = 'markers' if source == 'markers' else f'level:{level + 1}'

    part_heads: dict[int, str] = {}
    title_suggestion = next((paras[i].text.strip() for i in sorted(titles)), None)
    title_positions = set(titles)
    if chapters:
        part_heads = dict(part_marks)
        if source == 'level':
            for i in headings:
                if i not in chapters and paras[i].heading_level < level:
                    part_heads.setdefault(i, paras[i].text.strip())
        if title_suggestion is None:
            candidates = [i for i in headings if i < min(chapters) and i not in part_marks
                          and (source == 'markers' or paras[i].heading_level < level)]
            if candidates and (not part_marks or candidates[0] < min(part_marks)):
                title_suggestion = paras[candidates[0]].text.strip()
                title_positions.add(candidates[0])
                part_heads.pop(candidates[0], None)

    parts: list[tuple[int, str]] = []
    dropped: list[tuple[int, str]] = []
    if chapters:
        current = _Section('front', settings.prologue_title, None, [])
    else:
        current = _Section('chapter', title_suggestion or SINGLE_CHAPTER_TITLE, None, [])
    sections = [current]
    part_index: int | None = None
    for i, p in enumerate(paras):
        if i in title_positions:
            continue
        if i in part_heads:
            if settings.parts_allowed:
                parts.append((p.index, part_heads[i]))
                part_index = len(parts) - 1
            else:
                dropped.append((p.index, part_heads[i]))
            current = _Section('loose', '', part_index, [])
            sections.append(current)
        elif i in chapters:
            current = _Section('chapter', chapters[i], part_index, [])
            sections.append(current)
        elif i in separators:
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
        if section.kind == 'loose' or short_front:
            front_matter.extend(p.index for s in segments for p in s)
            continue
        pieces = [piece for segment in segments for piece in _pieces(segment, fits)]
        if not pieces and section.kind == 'chapter':
            warnings.append(f'Глава «{section.title}» без тексту: сцену не створено')
        for number, (group, proposed, scene_warnings) in enumerate(pieces, start=1):
            title = f'{section.title} ({number})' if len(pieces) > 1 else section.title
            scenes.append(ProposedScene(group[0].index, group[-1].index, title, sum(words(p.text) for p in group),
                                        section.part_index, proposed, scene_warnings))
            prose.extend(p.index for p in group)
            warnings.extend(f'{title}: {w}' for w in scene_warnings)
    return Structure(title_suggestion, chapter_source, tuple(parts), tuple(scenes), tuple(sorted(front_matter)),
                     tuple(dropped), tuple(warnings), tuple(sorted(prose)))


def prose_indices(paragraphs: Sequence[ManuscriptParagraph], settings: ParseSettings = ParseSettings()) -> list[int]:
    """Indices of all prose paragraphs inside scenes (what author-moved boundaries are validated against)."""
    return list(detect(paragraphs, settings).prose_indices)
