"""Deterministic author scene headings and cast; no inference or IO."""
import re
import unicodedata
from dataclasses import dataclass

SCENE_HEADING=re.compile(r'(?im)^[ \t]*(?:#{1,6}[ \t]*)?(?:\*\*)?Сцена[ \t]+\d+[.:][ \t]*([^\r\n]+)')


@dataclass(frozen=True)
class SceneDescription:
    title: str | None
    participants: list[str] | None


def clean_title(value):
    return value.replace('**','').replace('__','').strip()[:300]


def parenthetical_spans(value):
    stack=[];spans=[]
    for index,char in enumerate(value):
        if char=='(':stack.append(index)
        elif char==')' and stack:
            start=stack.pop()
            if not stack:spans.append((start,index+1))
    return spans


def split_participants(value):
    spans=parenthetical_spans(value)
    start=0;names=[]
    for index,char in enumerate(value):
        if char in ',;' and not any(left<=index<right for left,right in spans):
            names.append(value[start:index]);start=index+1
    names.append(value[start:])
    return [name.strip().rstrip('.').strip() for name in names if name.strip().rstrip('.').strip()]


def without_parentheticals(value):
    spans=parenthetical_spans(value)
    for start,end in reversed(spans):value=value[:start]+' '+value[end:]
    return value.strip()


def parse_scene_description(text):
    first=next((line for line in text.splitlines() if line.strip()),'')
    heading=SCENE_HEADING.fullmatch(first)
    title=clean_title(heading.group(1)) if heading else None
    names=None
    for line in text.splitlines():
        line=line.replace('**','').strip()
        match=re.match(r'(?i)^(?:[-*]\s+)?(?:Хто\s+бере\s+участь|Персонажі)\s*:\s*(.*)$',line)
        if match:
            if names is None:names=[]
            names.extend(split_participants(match.group(1)))
    return SceneDescription(title,names)


def name_key(value):
    return ' '.join(unicodedata.normalize('NFKC',value).casefold().replace('’',"'").replace('ʼ',"'").split()).rstrip('.')


def resolve_participants(names,cards):
    by_id={card.id:card.id for card in cards};by_name={}
    for card in cards:by_name.setdefault(name_key(card.name),[]).append(card.id)
    ids=[];problems=[]
    for name in names:
        matches=[by_id[name]] if name in by_id else by_name.get(name_key(name),[])
        if not matches:
            plain=without_parentheticals(name)
            matches=[by_id[plain]] if plain in by_id else by_name.get(name_key(plain),[])
        if len(matches)!=1:
            problems.append(('Неоднозначне ім’я' if matches else 'Невідомий персонаж')+': '+name[:120])
        elif matches[0] not in ids:ids.append(matches[0])
    return ids,problems


def explicit_scene_number(text):
    first=next((line for line in text.splitlines() if line.strip()),'')
    match=re.match(r'(?i)^[ \t]*(?:#{1,6}[ \t]*)?(?:\*\*)?Сцена[ \t]+(\d+)[.:][ \t]*.+$',first)
    return int(match[1]) if match else None
