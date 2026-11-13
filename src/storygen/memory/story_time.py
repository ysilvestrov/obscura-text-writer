"""Story time from the scene's «Початок:» line (STORY-TIME): moments, their order and the day-change signal; pure, no IO."""
import re
from dataclasses import dataclass
from typing import Literal

# Legacy forms keep their prefix match (text after the time is allowed) and their persisted day keys.
START=re.compile(r'(?i)^(?:початок|start)\s*:\s*(?:(\d{1,2}\.\d{1,2}\.\d{2,4})|(?:день|day)\s+(\d+))\s*,\s*(\d{1,2}:\d{2})')
HEAD=re.compile(r'(?i)^(?:початок|start)\s*:\s*(.*)$')
FLASHBACK_MARK=re.compile(r'(?i)\s*\(\s*(?:спогад|флешбек|flashback)\s*\)\s*$')
UNKNOWN=re.compile(r'(?i)^(?:невідомо|unknown)$')
PART=re.compile(r'(?i)(рік|year|місяць|month|день|day)\s+([+-]?\d+)')
TIME=re.compile(r'\s*,?\s*(\d{1,2}):(\d{2})$')
UNITS={'рік':0,'year':0,'місяць':1,'month':1,'день':2,'day':2}


@dataclass(frozen=True)
class Moment:
    kind: Literal['rel','date','unknown']
    key: tuple[int,int,int] | None  # (year, month, day); a missing part of a relative mark is 0
    minutes: int | None  # minutes of the day, None without a time
    legacy_day: bool  # a day-only relative mark: its day key stays day:N


def canonical_date(date):
    # 1.3.24, 01.03.2024 and 1.3.2024 are one day; the key is also the persisted memory_day_key selector value.
    d,m,y=(int(part) for part in date.split('.'))
    return f'date:{d}.{m}.{2000+y if y<100 else y}'


def _minutes(hours,minutes):
    return int(hours)*60+int(minutes)


def _relative(text):
    time=TIME.search(text);minutes=None
    if time:
        hours,mins=int(time.group(1)),int(time.group(2))
        if hours>23 or mins>59:return None
        minutes=hours*60+mins;text=text[:time.start()]
    parts=PART.findall(text)
    if not parts or PART.sub('',text).strip(' ,\t'):return None
    values=[None,None,None]
    for unit,value in parts:
        index=UNITS[unit.lower()]
        if values[index] is not None:return None
        values[index]=int(value)
    legacy_day=values[0] is None and values[1] is None
    return Moment('rel',tuple(v or 0 for v in values),minutes,legacy_day)


def _parse(line):
    """(Moment, day key, time) for one plain line, or None when it is not a recognised «Початок:» mark."""
    legacy=START.match(line)
    if legacy:
        date,day,time=legacy.groups()
        if date:
            key=canonical_date(date);d,m,y=(int(part) for part in key[5:].split('.'))
            return Moment('date',(y,m,d),_minutes(*time.split(':')),False),key,time
        return Moment('rel',(0,0,int(day)),_minutes(*time.split(':')),True),f'day:{int(day)}',time
    head=HEAD.match(line)
    if not head:return None
    body=FLASHBACK_MARK.sub('',head.group(1)).strip()
    if not body:return None
    if UNKNOWN.match(body):return Moment('unknown',None,None,False),None,None
    moment=_relative(body)
    if moment is None:return None
    y,m,d=moment.key
    key=f'day:{d}' if moment.legacy_day else f'rel:{y}.{m}.{d}'
    time=None if moment.minutes is None else f'{moment.minutes//60:02d}:{moment.minutes%60:02d}'
    return moment,key,time


def _plain_lines(beats):
    from ..characters.acquaintance import plain_line
    return (plain_line(line) for line in (beats or '').splitlines())


def _start(beats):
    for line in _plain_lines(beats):
        parsed=_parse(line)
        if parsed:return parsed
    return None


def scene_moment(beats) -> Moment | None:
    parsed=_start(beats)
    return parsed[0] if parsed else None


def flashback_marked(beats) -> bool:
    return any(HEAD.match(line) and FLASHBACK_MARK.search(line) for line in _plain_lines(beats))


def is_flashback(scene) -> bool:
    """A scene that remembers the past: its flashback flag or the «(спогад)»/«(флешбек)» mark in its «Початок:» line."""
    return bool(getattr(scene,'flashback',False)) or flashback_marked(scene.beats)


def flashback_mode(story, scenes) -> Literal['simple','full']:
    """How a flashback works: 'simple' in a book without explicit structure (short prose), 'full' otherwise."""
    from ..book.structure import structure_kind
    return 'simple' if structure_kind(story,scenes)=='flat' else 'full'


def scene_start(beats):
    """(day key, 'ГГ:ХХ' or None) of the scene's mark; None without a mark or for «невідомо»."""
    parsed=_start(beats)
    if not parsed or parsed[0].kind=='unknown':return None
    return parsed[1],parsed[2]


def day_key(scene):
    start=scene_start(scene.beats)
    return start[0] if start else None


def before(a: Moment | None, b: Moment | None) -> bool | None:
    """Whether moment a is earlier than b; None when either is missing or unknown, the kinds differ, or the day is the
    same and only one of them has a time."""
    if a is None or b is None or 'unknown' in (a.kind,b.kind) or a.kind!=b.kind:return None
    if a.key!=b.key:return a.key<b.key
    if a.minutes is None or b.minutes is None:return None if a.minutes!=b.minutes else False
    return a.minutes<b.minutes


def day_label(key, language='uk'):
    # Literary form of a day key for prompts: «день 3»/«day 3», «рік 2, день 14» or «1.3.2024»; the key format never
    # reaches the model.
    kind,value=key.split(':',1)
    if kind=='date':return value
    names=('year','month','day') if language=='en' else ('рік','місяць','день')
    if kind=='day':return f'{names[2]} {value}'
    parts=[f'{name} {number}' for name,number in zip(names,(int(v) for v in value.split('.'))) if number]
    return ', '.join(parts) or f'{names[2]} 0'


def comparison_scene(scenes,scene,character_id,story=None):
    """The latest scene of the lineage (BOOK-LINEAGE) with this character; production callers pass the story."""
    from ..book.lineage import previous_scenes
    before=[item for item in previous_scenes(story,scenes,scene) if character_id in item.character_ids]
    return before[-1] if before else None


def day_change(scenes,scene,character_id,story=None):
    previous=comparison_scene(scenes,scene,character_id,story)
    if previous is None:return False
    # Moments of one kind with different days; «день N» and «Рік …, День …» are one kind (relative), dates another.
    old,new=scene_moment(previous.beats),scene_moment(scene.beats)
    return bool(old and new and old.kind==new.kind!='unknown' and old.key!=new.key)
