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
            names.extend(name.strip().rstrip('.').strip() for name in re.split('[,;]',match.group(1)) if name.strip().rstrip('.').strip())
    return SceneDescription(title,names)


def name_key(value):
    return ' '.join(unicodedata.normalize('NFKC',value).casefold().replace('’',"'").replace('ʼ',"'").split()).rstrip('.')


def resolve_participants(names,cards):
    by_id={card.id:card.id for card in cards};by_name={}
    for card in cards:by_name.setdefault(name_key(card.name),[]).append(card.id)
    ids=[];problems=[]
    for name in names:
        matches=[by_id[name]] if name in by_id else by_name.get(name_key(name),[])
        if len(matches)!=1:
            problems.append(('Неоднозначне ім’я' if matches else 'Невідомий персонаж')+': '+name[:120])
        elif matches[0] not in ids:ids.append(matches[0])
    return ids,problems
