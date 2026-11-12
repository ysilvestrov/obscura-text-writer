"""Day-change signal from the scene's «Початок:» line; pure, no IO."""
import re

START=re.compile(r'(?i)^(?:початок|start)\s*:\s*(?:(\d{1,2}\.\d{1,2}\.\d{2,4})|(?:день|day)\s+(\d+))\s*,\s*(\d{1,2}:\d{2})')


def canonical_date(date):
    # 1.3.24, 01.03.2024 and 1.3.2024 are one day; the key is also the persisted memory_day_key selector value.
    d,m,y=(int(part) for part in date.split('.'))
    return f'date:{d}.{m}.{2000+y if y<100 else y}'


def scene_start(beats):
    from ..characters.acquaintance import plain_line
    for line in (beats or '').splitlines():
        match=START.match(plain_line(line))
        if match:
            date,day,time=match.groups()
            return (canonical_date(date) if date else f'day:{int(day)}'),time
    return None


def day_key(scene):
    start=scene_start(scene.beats)
    return start[0] if start else None


def day_label(key, language='uk'):
    # Literary form of a day key for prompts: «день 3»/«day 3» or «1.3.2024»; the key format never reaches the model.
    kind,value=key.split(':',1)
    if kind!='day':return value
    return f'day {value}' if language=='en' else f'день {value}'


def comparison_scene(scenes,scene,character_id,story=None):
    """The latest scene of the lineage (BOOK-LINEAGE) with this character; production callers pass the story."""
    from ..book.lineage import previous_scenes
    before=[item for item in previous_scenes(story,scenes,scene) if character_id in item.character_ids]
    return before[-1] if before else None


def day_change(scenes,scene,character_id,story=None):
    previous=comparison_scene(scenes,scene,character_id,story)
    if previous is None:return False
    old,new=day_key(previous),day_key(scene)
    return bool(old and new and old.split(':')[0]==new.split(':')[0] and old!=new)
