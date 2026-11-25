"""IO adapter for the shared temporal projection; no model inference."""
from .models import load_characters
from .projection import project_characters
from ..scene_description import parse_scene_description,resolve_participants

RAW_CHARACTER_WARNING="Вихідний опис персонажів не поділено на картки; його не передано в сцену. Підготуйте або додайте картки учасників."


def validate_scene_participants(view,story,scene):
    names=parse_scene_description(scene.beats).participants
    if not names:return
    cards=load_characters(view.read_text(story.characters_version_id)) if story.characters_version_id else []
    _,problems=resolve_participants(names,cards)
    if problems:raise ValueError("Уточніть склад сцени в плані або картках: "+"; ".join(problems[:5]))


def name_spelling_section(view,story,scene):
    """EDITOR-NAME-SPELLING: names of the scene cast available in this scene, for the editor; '' without fresh cards.
    Adds no refs: a hint line, not a dependency of the proposal."""
    if not story.characters_version_id or not scene.character_ids:return ''
    ref=view.get_version(story.characters_version_id)
    if ref.stale or not ref.complete:return ''
    from .names import scene_name,_active
    from ..generation.context_labels import label
    cards={card.id:card for card in load_characters(view.read_text(ref.id))}
    active=_active(view.list_scenes(story.id))
    lines=[]
    for card_id in scene.character_ids:
        card=cards.get(card_id)
        if card is None:continue
        current,earlier=scene_name(card,active,scene)
        lines.append('— '+current+(label('character_also',story.language,names=', '.join(earlier)) if earlier else ''))
    if not lines:return ''
    return '\n'.join([label('name_spelling',story.language),label('name_spelling_rule',story.language),*lines])


def character_material(view,story,scene):
    validate_scene_participants(view,story,scene)
    if story.characters_version_id:
        ref=view.get_version(story.characters_version_id)
        if ref.stale or not ref.complete:raise ValueError('Картки персонажів застаріли; перегляньте й оновіть їх')
        projection=project_characters(load_characters(view.read_text(ref.id)),view.list_scenes(story.id),scene.id,story.language)
        from ..generation.context_labels import label
        return (label('characters',story.language)+'\n'+projection.text if projection.text else '',projection.warnings,[ref.id])
    source=view.active_source(story.id,'source_characters')
    if source:
        if source.stale or not source.complete:raise ValueError('Опис персонажів потребує оновлення')
        return '',[RAW_CHARACTER_WARNING],[]
    return '',[],[]
