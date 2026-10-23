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


def character_material(view,story,scene):
    validate_scene_participants(view,story,scene)
    if story.characters_version_id:
        ref=view.get_version(story.characters_version_id)
        if ref.stale or not ref.complete:raise ValueError('Картки персонажів застаріли; перегляньте й оновіть їх')
        projection=project_characters(load_characters(view.read_text(ref.id)),view.list_scenes(story.id),scene.id)
        return ('КАРТКИ ПЕРСОНАЖІВ\n'+projection.text if projection.text else '',projection.warnings,[ref.id])
    source=view.active_source(story.id,'source_characters')
    if source:
        if source.stale or not source.complete:raise ValueError('Опис персонажів потребує оновлення')
        return '',[RAW_CHARACTER_WARNING],[]
    return '',[],[]
