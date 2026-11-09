"""Author markers in character cards: protagonist and pre-story acquaintances; pure, no IO."""
import re
from dataclasses import dataclass
from ..scene_description import split_participants,resolve_participants,name_key,without_parentheticals
from .projection import entry_available
from .models import load_characters
from ..generation.models import WritersBrief

UNKNOWN_NAME_WARNING='У картці «{card}» позначка «Знайомий з:» називає «{name}», але картки з таким іменем немає; виправте ім’я в позначці або назву картки.'
AMBIGUOUS_NAME_WARNING='У картці «{card}» позначка «Знайомий з:» називає «{name}», але так названо кілька карток; перейменуйте одну з них, щоб ім’я було однозначним.'
DUPLICATE_PROTAGONIST_WARNING='Позначку протагоніста мають кілька карток; використано першу за порядком.'
PROTAGONIST=re.compile(r'(?i)^(?:протагоніст(?:ка)?|головний\s+герой|головна\s+героїня)$')
ROLE=re.compile(r'(?i)^роль(?:\s+у\s+творі)?\s*:\s*(.*)$')
KNOWN=re.compile(r'(?i)^(?:знайомий|знайома|знайомі|знайм)\s+з\s*:\s*(.*)$')


def plain_line(line):
    return re.sub(r'^[\s\-—–]+','',line.replace('**','').replace('__','').replace('*','').strip()).strip()


def is_protagonist_line(line):
    text=plain_line(line)
    role=ROLE.match(text)
    if role:  # template form «Роль у творі: Головна героїня, …»: the first listed role decides
        text=re.split(r'[,;.(—–]',role.group(1),maxsplit=1)[0]
    return bool(PROTAGONIST.match(text.rstrip('.:!;, ').strip()))


def known_names_line(line):
    match=KNOWN.match(plain_line(line))
    if not match:return None
    # A placeholder such as «—», «-» or «…» means "nobody": only entries with a letter or digit are names.
    return [name for name in split_participants(match.group(1)) if any(char.isalnum() for char in name)]


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
    known=set();warnings=[];reported=set()
    for card in cards:
        for entry in card.entries:
            marked=[names for names in map(known_names_line,entry.text.splitlines()) if names is not None]
            if not marked or not entry_available(entry,active,scene):continue
            for names in marked:
                ids,_=resolve_participants(names,cards)
                for name in names:
                    # One warning per card and name as the resolver sees it (case, apostrophes and spacing ignored).
                    if (card.id,name_key(name)) in reported or not resolve_participants([name],cards)[1]:continue
                    reported.add((card.id,name_key(name)))
                    template=AMBIGUOUS_NAME_WARNING if _ambiguous(name,cards) else UNKNOWN_NAME_WARNING
                    warnings.append(template.format(card=card.name[:120],name=name[:120]))
                if card.id==hero_id:known.update(ids)
                elif hero_id in ids:known.add(card.id)
    known.discard(hero_id)
    return known,warnings


def _ambiguous(name,cards):
    """True when the name (or its form without parentheticals) belongs to several cards, i.e. it is ambiguous, not unknown."""
    count=lambda value:sum(name_key(card.name)==name_key(value) for card in cards)
    return (count(name) or count(without_parentheticals(name)))>1


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


WRITING_STAGES={'brief','draft','rewrite'}


def unexpected_introduced(scene,hero_id,introduced):
    """True, якщо brief назвав ID поза складом сцени або самого героя."""
    if not introduced:return False
    allowed=set(scene.character_ids)-{hero_id}
    return any(cid not in allowed for cid in introduced)


def acquaintance_material(view,story,scene,stage):
    """Блок знайомств для brief/draft/rewrite: (текст, попередження); порожній текст, якщо блок не потрібен."""
    if stage not in WRITING_STAGES:return '',[]
    if not story.characters_version_id:return '',[]
    cards=load_characters(view.read_text(story.characters_version_id))
    hero,warnings=protagonist(cards,view.list_scenes(story.id)) if cards else (None,[])
    if hero is None or hero not in scene.character_ids:return '',warnings
    others=[cid for cid in scene.character_ids if cid!=hero]
    if not others:return '',warnings
    result=acquaintances(view,story,scene)
    names={card.id:card.name for card in load_characters(view.read_text(story.characters_version_id))}
    def name(cid):return names.get(cid,cid)
    known=[cid for cid in others if cid in result.known]
    known.sort(key=lambda cid:(result.known[cid] is not None,result.known[cid] or 0))
    unknown=[cid for cid in others if cid not in result.known]
    lines=[f'ЗНАЙОМСТВА ГОЛОВНОГО ГЕРОЯ — {name(hero)}']
    if known:
        lines.append('Знайомі: '+'; '.join(f'{name(cid)} ('+('до початку історії' if result.known[cid] is None else f'зі сцени {result.known[cid]}')+')' for cid in known))
    if unknown:
        lines.append('Ще не представлені: '+'; '.join(name(cid)+(f' [id={cid}]' if stage=='brief' else '') for cid in unknown))
    rule='Не називай ще не представлених на ім’я, доки їх не представлено в тексті історії; до того описуй їх як незнайомців.'
    if stage=='brief':
        rule+=' Якщо представлення відбувається в цій сцені, додай їхні ID в поле introduced.'
    lines.append(rule)
    return '\n'.join(lines),result.warnings
