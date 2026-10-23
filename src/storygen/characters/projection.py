"""Scene scoped character directions, never a source of proven memory facts."""
from dataclasses import dataclass

TEMPORAL_WARNING='Часову доступність опису не перевірено; він може містити відомості з майбутніх сцен.'
EMPTY_CAST_WARNING='Склад сцени порожній; описи персонажів не передаються. Додайте учасників у план або параметри сцени.'
OTHER_MATERIAL_WARNING='Часові мітки перевіряють лише відомості персонажів. Канон, авторські промпти й інші нерозмічені вказівки можуть містити майбутні відомості.'


@dataclass(frozen=True)
class CharacterProjection:
    text: str
    warnings: list[str]
    included_entry_ids: list[str]
    excluded_count: int


def project_characters(cards,scenes,scene_id):
    active={scene.id:scene for scene in scenes if not scene.trashed_at}
    scene=active.get(scene_id)
    if scene is None:raise ValueError('Сцена проєкції недоступна')
    warnings=[EMPTY_CAST_WARNING] if cards and not scene.character_ids else [];included=[];excluded=0;sections=[]
    labels={'timeless':'ПОЗАЧАСОВІ ВІДОМОСТІ','from_scene':'ДОСТУПНІ АВТОРСЬКІ ВКАЗІВКИ — НЕ ДОКАЗ МИНУЛИХ ПОДІЙ',
        'unclassified':'НЕПЕРЕВІРЕНІ ЗА ЧАСОМ АВТОРСЬКІ ВІДОМОСТІ'}
    for card in cards:
        if card.id not in scene.character_ids:continue
        groups={key:[] for key in labels}
        for entry in card.entries:
            if entry.availability=='from_scene':
                anchor=active.get(entry.available_from_scene_id)
                if anchor is None or anchor.story_id!=scene.story_id:
                    raise ValueError('Сцена доступності відомості персонажа недоступна або належить іншому твору')
                if anchor.position>scene.position:
                    excluded+=1;continue
            if entry.availability=='unclassified' and TEMPORAL_WARNING not in warnings:
                warnings.append(TEMPORAL_WARNING)
            groups[entry.availability].append('— '+entry.text)
            included.append(entry.id)
        body='\n\n'.join(labels[key]+'\n'+'\n'.join(lines) for key,lines in groups.items() if lines)
        if body:sections.append('ПЕРСОНАЖ: '+card.name+'\n'+body)
    missing=set(scene.character_ids)-{card.id for card in cards}
    if missing:warnings.append('Для частини персонажів сцени немає карток; перевірте список персонажів.')
    return CharacterProjection('\n\n'.join(sections),warnings,included,excluded)
