"""Author markers in character cards: protagonist and pre-story acquaintances; pure, no IO."""
import re
from ..scene_description import split_participants,resolve_participants
from .projection import entry_available

BAD_NAME_WARNING='Позначка «Знайомий з:» містить невідоме або неоднозначне ім’я; перевірте картки.'
DUPLICATE_PROTAGONIST_WARNING='Позначку протагоніста мають кілька карток; використано першу за порядком.'
PROTAGONIST=re.compile(r'(?i)^(?:протагоніст(?:ка)?|головний\s+герой|головна\s+героїня)$')
KNOWN=re.compile(r'(?i)^(?:знайомий|знайома|знайомі|знайм)\s+з\s*:\s*(.*)$')


def plain_line(line):
    return re.sub(r'^[\s\-*—–]+','',line.replace('**','').replace('__','').strip()).rstrip('* ').strip()


def is_protagonist_line(line):
    return bool(PROTAGONIST.match(plain_line(line).rstrip('.:!;, ').strip()))


def known_names_line(line):
    match=KNOWN.match(plain_line(line))
    return split_participants(match.group(1)) if match else None


def protagonist(cards,scenes):
    marked=[card.id for card in cards if any(is_protagonist_line(line) for entry in card.entries for line in entry.text.splitlines())]
    if marked:return marked[0],([DUPLICATE_PROTAGONIST_WARNING] if len(marked)>1 else [])
    for scene in sorted((scene for scene in scenes if not scene.trashed_at),key=lambda scene:scene.position):
        if scene.character_ids:return scene.character_ids[0],[]
    return None,[]


def pre_story_known(cards,scenes,scene_id,hero_id):
    active={scene.id:scene for scene in scenes if not scene.trashed_at}
    scene=active.get(scene_id)
    if scene is None:raise ValueError('Сцена недоступна')
    known=set();bad=False
    for card in cards:
        for entry in card.entries:
            marked=[names for names in map(known_names_line,entry.text.splitlines()) if names is not None]
            if not marked or not entry_available(entry,active,scene):continue
            for names in marked:
                ids,problems=resolve_participants(names,cards)
                bad=bad or bool(problems)
                if card.id==hero_id:known.update(ids)
                elif hero_id in ids:known.add(card.id)
    known.discard(hero_id)
    return known,([BAD_NAME_WARNING] if bad else [])
