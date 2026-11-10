"""Fixed rating instructions (Ukrainian or English, by story language) appended to the system text of literary stages."""
from ..domain import ContentRating
from ..story_horizon import selected_plan_scenes
from .levels import AXES, effective_rating, higher_axes

INSTRUCTION_STAGES=frozenset({'brief','draft','edit','rewrite'})
LABELS={'sexual':'Сексуальний зміст','violence':'Насильство','themes':'Жорсткі теми'}
AXIS_NAMES={'sexual':'сексуальний зміст','violence':'насильство','themes':'жорсткі теми'}
# Axis scope, worded as in the approved UI help tips: the model must tell violence (what is shown) from hard themes (what the story deals with).
DEFINITIONS={
    'sexual':'еротика та інтимні сцени',
    'violence':'фізична шкода, яку показано в тексті: бійки, поранення, вбивства, катування',
    'themes':'важкі теми, про які йдеться в тексті, навіть без фізичного насильства: самогубство й самоушкодження, залежності, психологічне насильство й цькування, дискримінація, тяжка втрата',
}
DESCRIPTIONS={
    'sexual':('без сексуального змісту; романтика без еротичних подробиць','дорослий сексуальний зміст без графічних подробиць','відвертий сексуальний зміст допустимий'),
    'violence':('без детального насильства й крові','насильство без графічних подробиць','графічне насильство допустиме'),
    'themes':('жорсткі теми лише згадуються, без зображення','жорсткі теми без детального зображення','відверте зображення жорстких тем допустиме'),
}
HEADING='ВІКОВИЙ РЕЙТИНГ СЦЕНИ — МЕЖА, ЯКУ НЕ МОЖНА ПЕРЕВИЩУВАТИ'
FOOTER='Межа не вимагає досягати рівня: пиши так, як потребує сцена.'
HIGHER='СЦЕНИ З ВИЩИМ РЕЙТИНГОМ: {groups}.'
HIGHER_RULE='Не переказуй і не згадуй їхніх подробиць понад межу цієї сцени; можна посилатися лише на події, важливі для сюжету.'
LEVEL='рівень'

EN={
    'LABELS':{'sexual':'Sexual content','violence':'Violence','themes':'Hard themes'},
    'AXIS_NAMES':{'sexual':'sexual content','violence':'violence','themes':'hard themes'},
    'DEFINITIONS':{
        'sexual':'erotica and intimate scenes',
        'violence':'physical harm shown in the text: fights, injuries, killings, torture',
        'themes':'heavy themes the text deals with, even without physical violence: suicide and self-harm, addiction, psychological abuse and bullying, discrimination, grave loss',
    },
    'DESCRIPTIONS':{
        'sexual':('no sexual content; romance without erotic detail','adult sexual content without graphic detail','explicit sexual content allowed'),
        'violence':('no detailed violence or gore','violence without graphic detail','graphic violence allowed'),
        'themes':('hard themes only mentioned, not depicted','hard themes without detailed depiction','frank depiction of hard themes allowed'),
    },
    'HEADING':'SCENE AGE RATING: A LIMIT THAT MUST NOT BE EXCEEDED',
    'FOOTER':'The limit does not require reaching the level: write what the scene needs.',
    'HIGHER':'SCENES WITH A HIGHER RATING: {groups}.',
    'HIGHER_RULE':'Do not retell or mention their details beyond the limit of this scene; you may refer only to events that matter for the plot.',
    'LEVEL':'level',
}
UK={'LABELS':LABELS,'AXIS_NAMES':AXIS_NAMES,'DEFINITIONS':DEFINITIONS,'DESCRIPTIONS':DESCRIPTIONS,'HEADING':HEADING,
    'FOOTER':FOOTER,'HIGHER':HIGHER,'HIGHER_RULE':HIGHER_RULE,'LEVEL':LEVEL}


def texts(language):
    return EN if language=='en' else UK


def rating_block(rating: ContentRating, language='uk') -> str:
    t=texts(language)
    lines=[f'{t["LABELS"][a]} ({t["DEFINITIONS"][a]}): {t["LEVEL"]} {getattr(rating,a)} — {t["DESCRIPTIONS"][a][getattr(rating,a)]}.' for a in AXES]
    return '\n'.join([t['HEADING'],*lines,t['FOOTER']])


def higher_scenes_block(items: list[tuple[int,list[str]]], language='uk') -> str:
    t=texts(language)
    groups: dict[tuple[str,...],list[int]]={}
    for number,axes in items:
        groups.setdefault(tuple(a for a in AXES if a in axes),[]).append(number)
    if not groups:return ''
    text='; '.join(', '.join(map(str,numbers))+' ('+', '.join(t['AXIS_NAMES'][a] for a in axes)+')' for axes,numbers in groups.items())
    return t['HIGHER'].format(groups=text)+'\n'+t['HIGHER_RULE']


def rating_instructions(view,story,scene,stage: str,settings) -> str:
    if scene is None or stage not in INSTRUCTION_STAGES:return ''
    rating=effective_rating(story,scene)
    if rating is None:return ''
    parts=[rating_block(rating,story.language)]
    # Patch/diff edits carry only the draft itself, never other scenes' material.
    if not (stage=='edit' and settings.edit_mode in {'patches','diff'}):
        scenes=view.list_scenes(story.id)
        material={s.id:s for s in scenes if s.position<scene.position}
        material.update({s.id:s for s in selected_plan_scenes(scenes,scene,settings) if s.id!=scene.id})
        items=[]
        for other in sorted(material.values(),key=lambda s:s.position):
            other_rating=effective_rating(story,other)
            axes=higher_axes(other_rating,rating) if other_rating else []
            if axes:items.append((other.position+1,axes))
        block=higher_scenes_block(items,story.language)
        if block:parts.append(block)
    return '\n\n'.join(parts)
