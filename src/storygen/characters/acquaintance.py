"""Author markers in character cards: protagonist and pre-story acquaintances; pure, no IO."""
import re
from dataclasses import dataclass
from ..scene_description import split_participants,resolve_participants
from .projection import entry_available
from .models import load_characters
from ..generation.models import WritersBrief

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


LINEAGE_KINDS={'draft','edited','manual','brief'}


@dataclass(frozen=True)
class Acquaintances:
    hero_id: str | None
    known: dict
    warnings: list


def lineage_brief(view,scene):
    """Найновіший brief цієї сцени в родоводі голови prose; обхід лише через input_refs, застарілість не перевіряється."""
    head=scene.heads.get('prose')
    if not head:return None
    seen=set();stack=[head];briefs=[]
    while stack:
        ref_id=stack.pop()
        if ref_id in seen:continue
        seen.add(ref_id)
        try:ref=view.get_version(ref_id)
        except KeyError:continue
        if ref.scene_id!=scene.id or ref.kind not in LINEAGE_KINDS:continue
        if ref.kind=='brief':
            briefs.append(ref);continue
        stack.extend(ref.input_refs)
    return max(briefs,key=lambda ref:ref.created_at) if briefs else None


def introduced_of(view,scene):
    ref=lineage_brief(view,scene)
    if ref is None:return None
    try:return WritersBrief.model_validate_json(view.read_text(ref.id)).introduced
    except (ValueError,KeyError,OSError):return None


def acquaintances(view,story,scene):
    if not story.characters_version_id:return Acquaintances(None,{},[])
    cards=load_characters(view.read_text(story.characters_version_id))
    if not cards:return Acquaintances(None,{},[])
    scenes=view.list_scenes(story.id)
    active=[item for item in scenes if not item.trashed_at]
    hero,warnings=protagonist(cards,active)
    if hero is None:return Acquaintances(None,{},warnings)
    known={}
    for past in sorted(active,key=lambda item:item.position):
        if past.position>=scene.position or not past.heads.get('prose') or hero not in past.character_ids:continue
        cast=set(past.character_ids)
        introduced=introduced_of(view,past)
        names=cast if introduced is None else set(introduced)&cast
        for cid in past.character_ids:
            if cid in names and cid!=hero:known.setdefault(cid,past.position+1)
    pre,more=pre_story_known(cards,active,scene.id,hero)
    for cid in pre:known[cid]=None
    return Acquaintances(hero,known,warnings+more)
