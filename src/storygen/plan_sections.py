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
