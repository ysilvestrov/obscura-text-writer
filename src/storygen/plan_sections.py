"""Exact source sections with explicit author numbers, independent of list position."""
import re
from dataclasses import dataclass
from .scene_description import clean_title, explicit_scene_number, SCENE_HEADING

@dataclass(frozen=True)
class PlanSection:
    title: str
    text: str
    author_scene_number: int | None


def _container(title):
    title=clean_title(title).casefold()
    return title in {'plan','story plan'} or re.fullmatch(r'(?:тестовий\s+)?план(?:\s+оповідання)?(?:\s+«[^»]*»)?',title) is not None


def split_plan(text,default_title='Сцена'):
    """`default_title` names unheaded sections in the story language: «Сцена» or «Scene» (#32)."""
    lines=text.splitlines(keepends=True)
    records=[];offset=0
    for line in lines:
        content=line.rstrip('\r\n')
        heading=re.match(r'^[ \t]*(#{1,6})[ \t]+(.+)$',content)
        number=explicit_scene_number(content)
        if heading or number is not None:records.append((offset,content,heading,number))
        offset+=len(line)
    numbered_levels=[len(h[1]) for _,_,h,n in records if h and n is not None]
    if not numbered_levels and any(n is not None for _,_,_,n in records):
        # Scenes are plain «Сцена N:» lines: a lone level-1 heading that opens the file is the plan title (#103).
        first=records[0]
        lone=sum(1 for _,_,h,_ in records if h and len(h[1])==1)==1
        if first[2] and len(first[2][1])==1 and lone and not text[:first[0]].strip():records=records[1:]
    levels=numbered_levels or [len(h[1]) for start,_,h,_ in records if h and not _container(h[2])]
    level=min(levels) if levels else None
    boundaries=[r for r in records if r[3] is not None or r[2] and len(r[2][1])==level and not _container(r[2][2])]
    if not boundaries:return '',[PlanSection(f'{default_title} 1',text,None)]
    sections=[]
    for index,(start,content,heading,number) in enumerate(boundaries):
        title=SCENE_HEADING.fullmatch(content)
        title=clean_title(title[1] if title else heading[2]) or f"{default_title} {index+1}"
        end=boundaries[index+1][0] if index+1<len(boundaries) else len(text)
        sections.append(PlanSection(title,text[start:end],number))
    return text[:boundaries[0][0]],sections


# BOOK-STRUCTURE: parts and arcs in a plan. A part heading sits above the scene level; an arc line is cut from the scene plan.
PART_TITLE=re.compile(r'^(?:частина|part)\b[^:]*(?::\s*(.*))?$',re.IGNORECASE)
ARC_LINE=re.compile(r'^(?:арка|arc)\s*:\s*(.*)$',re.IGNORECASE)
# BOOK-LINEAGE-S04: the arc protagonist by card name, cut from the scene plan like an arc line.
PROTAGONIST_LINE=re.compile(r'^(?:протагоніст|protagonist)\s*:\s*(.*)$',re.IGNORECASE)
# MEMORY-MERGE harness: «Арки: А, Б» — a meeting scene of several arcs of its part (comma or semicolon separated).
ARCS_LINE=re.compile(r'^(?:арки|arcs)\s*:\s*(.*)$',re.IGNORECASE)
# STORY-TIME: «Спогад: так|ні» sets the scene's flashback flag in every edition and is cut from the scene plan.
FLASHBACK_LINE=re.compile(r'^(?:спогад|flashback)\s*:\s*(.*)$',re.IGNORECASE)
FLASHBACK_VALUES={'так':True,'yes':True,'true':True,'ні':False,'no':False,'false':False}


def cut_flashback_line(text):
    """(text without «Спогад:» lines, the last valid value or None, whether a line had another value)."""
    kept=[];value=None;invalid=False
    for line in text.splitlines(keepends=True):
        match=FLASHBACK_LINE.fullmatch(_plain(line.rstrip('\r\n')))
        if not match:kept.append(line);continue
        word=_plain(match[1]).strip().casefold()
        if word in FLASHBACK_VALUES:value=FLASHBACK_VALUES[word]
        else:invalid=True
    return ''.join(kept),value,invalid


@dataclass(frozen=True)
class BookSection:
    section: PlanSection
    part_title: str | None
    arc_title: str | None
    part_index: int | None = None  # ordinal of the part heading in this plan; equal titles stay separate parts
    protagonist_name: str | None = None
    # Two or more titles: a meeting scene; arc_title is then the arc the next section without a line continues.
    arc_titles: tuple[str, ...] | None = None


def _plain(line):
    return re.sub(r'^[\s\-—–>]+','',line.replace('**','').replace('__','').replace('*','').strip()).strip()


def _part_headings(text):
    """(start, end, title) of part headings: level above the numbered scene headings, or any level if scenes have none."""
    found=[];offset=0;headings=[]
    for line in text.splitlines(keepends=True):
        content=line.rstrip('\r\n')
        heading=re.match(r'^[ \t]*(#{1,6})[ \t]+(.+)$',content)
        if heading:headings.append((offset,offset+len(line),len(heading[1]),heading[2],explicit_scene_number(content)))
        offset+=len(line)
    numbered=[level for _,_,level,_,number in headings if number is not None]
    for start,end,level,title,number in headings:
        title=clean_title(title)
        match=PART_TITLE.fullmatch(title)
        if not match or number is not None or numbered and level>=min(numbered):continue
        found.append((start,end,(match[1] if match[1] is not None else title).strip()))
    return found


def _cut_arc_lines(text):
    """The section text without arc, arcs and protagonist lines, the last arc title, the last protagonist name and the
    titles of the last arcs line (None without one) in it."""
    kept=[];arc=None;protagonist=None;arcs=None
    for line in text.splitlines(keepends=True):
        plain=_plain(line.rstrip('\r\n'))
        match=ARC_LINE.fullmatch(plain)
        if match:arc=match[1].strip()[:200];continue
        match=ARCS_LINE.fullmatch(plain)
        if match:
            titles=[_plain(t).strip()[:200] for t in re.split(r'[,;]',match[1])]
            arcs=tuple(dict.fromkeys(t for t in titles if t))[:20];continue
        match=PROTAGONIST_LINE.fullmatch(plain)
        if match:protagonist=_plain(match[1]).strip()[:200] or None;continue
        kept.append(line)
    return ''.join(kept),arc,protagonist,arcs


def split_book_plan(text,default_title='Сцена'):
    """split_plan with parts and arcs: (preamble, sections, found) — found is whether any part heading or arc line exists.

    A section before any part heading has part_title None (the book's current part); a section without an arc line keeps
    the previous section's arc in its part, and the first one of a part has arc_title None (the part's current arc)."""
    parts=_part_headings(text)
    stripped=[];marks=[];cursor=0;removed=0
    for start,end,title in parts:
        stripped.append(text[cursor:start]);removed+=end-start;cursor=end
        marks.append((start-(removed-(end-start)),title))
    stripped.append(text[cursor:])
    preamble,sections=split_plan(''.join(stripped),default_title)
    found=bool(parts);result=[];offset=len(preamble);part=None;arc=None;mark=0;index=None
    for section in sections:
        while mark<len(marks) and marks[mark][0]<=offset:
            part=marks[mark][1];arc=None;index=mark;mark+=1
        body,line_arc,protagonist,line_arcs=_cut_arc_lines(section.text)
        if line_arc is not None:arc=line_arc;found=True
        if protagonist is not None:found=True
        meeting=None
        if line_arcs:
            found=True
            if len(line_arcs)==1:arc=line_arcs[0]
            else:
                # The next section without a line goes back to the arc before the meeting when it is a meeting arc.
                meeting=line_arcs;arc=arc if arc in line_arcs else line_arcs[0]
        result.append(BookSection(PlanSection(section.title,body,section.author_scene_number),part,arc,index,protagonist,meeting))
        offset+=len(section.text)
    return preamble,result,found
