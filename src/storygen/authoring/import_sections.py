"""Exact source sections with explicit author numbers, independent of list position."""
import re
from dataclasses import dataclass
from ..scene_description import clean_title, explicit_scene_number, SCENE_HEADING

@dataclass(frozen=True)
class PlanSection:
    title: str
    text: str
    author_scene_number: int | None


def split_plan(text):
    lines=text.splitlines(keepends=True)
    records=[];offset=0
    for line in lines:
        content=line.rstrip('\r\n')
        heading=re.match(r'^[ \t]*(#{1,6})[ \t]+(.+)$',content)
        number=explicit_scene_number(content)
        if heading or number is not None:records.append((offset,content,heading,number))
        offset+=len(line)
    numbered_levels=[len(h[1]) for _,_,h,n in records if h and n is not None]
    levels=numbered_levels or [len(h[1]) for _,_,h,_ in records if h and clean_title(h[2]).casefold() not in {'план','план оповідання','plan','story plan'}]
    level=min(levels) if levels else None
    boundaries=[r for r in records if r[3] is not None or r[2] and len(r[2][1])==level and clean_title(r[2][2]).casefold() not in {'план','план оповідання','plan','story plan'}]
    if not boundaries:return '',[PlanSection('Сцена 1',text,None)]
    sections=[]
    for index,(start,content,heading,number) in enumerate(boundaries):
        title=SCENE_HEADING.fullmatch(content)
        title=clean_title(title[1] if title else heading[2])
        end=boundaries[index+1][0] if index+1<len(boundaries) else len(text)
        sections.append(PlanSection(title,text[start:end],number))
    return text[:boundaries[0][0]],sections
