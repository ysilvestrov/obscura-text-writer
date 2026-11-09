"""Pure parsing of character age lines for the minors safeguard; no IO."""
import re
from typing import Literal

AgeVerdict=Literal['adult','minor','unknown']

AGE_LINE=re.compile(r'(?im)^[ \t]*\W*(вік|age)[ \t]*:[ \t]*([^\r\n]*)$')
ADULT_WORDS=frozenset({'дорослий','доросла','дорослі','доросле','adult'})
# Worst verdict first: minor > unknown > adult.
_SEVERITY={'minor':2,'unknown':1,'adult':0}


def worst(verdicts)->AgeVerdict:
    return max(verdicts,key=_SEVERITY.__getitem__)


def parse_age_value(value: str) -> AgeVerdict:
    value=value.strip(' \t\r\n*_')  # markdown emphasis around the value
    numbers=[int(item) for item in re.findall(r'\d+',value)]
    if numbers:return 'adult' if min(numbers)>=18 else 'minor'
    word=value.lower().rstrip('.').strip()
    return 'adult' if word in ADULT_WORDS else 'unknown'


def entry_age(text: str) -> AgeVerdict | None:
    verdicts=[parse_age_value(match.group(2)) for match in AGE_LINE.finditer(text)]
    return worst(verdicts) if verdicts else None


def scene_ages(cards,scenes,scene_id: str) -> dict[str,AgeVerdict]:
    """Age verdict per scene participant; availability rules mirror project_characters.

    Entries with an invalid anchor (trashed, missing, other story) are skipped silently:
    the projection reports that error separately.
    """
    active={scene.id:scene for scene in scenes if not scene.trashed_at}
    scene=active.get(scene_id)
    if scene is None:raise ValueError('Сцена проєкції недоступна')
    by_id={card.id:card for card in cards}
    result: dict[str,AgeVerdict]={}
    for character_id in scene.character_ids:
        card=by_id.get(character_id)
        verdict: AgeVerdict='unknown'
        if card is not None:
            anchored: dict[int,list[AgeVerdict]]={};plain: list[AgeVerdict]=[]
            for entry in card.entries:
                age=entry_age(entry.text)
                if age is None:continue
                if entry.availability=='from_scene':
                    anchor=active.get(entry.available_from_scene_id)
                    if anchor is None or anchor.story_id!=scene.story_id or anchor.position>scene.position:continue
                    anchored.setdefault(anchor.position,[]).append(age)
                else:plain.append(age)
            group=anchored[max(anchored)] if anchored else plain
            if group:verdict=worst(group)
        result[character_id]=verdict
    return result
