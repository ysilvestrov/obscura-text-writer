"""IO adapter for the shared temporal projection; no model inference."""
from .models import load_characters
from .projection import project_characters,TEMPORAL_WARNING


def character_material(view,story,scene):
    if story.characters_version_id:
        ref=view.get_version(story.characters_version_id)
        if ref.stale or not ref.complete:raise ValueError('Картки персонажів застаріли; перегляньте й оновіть їх')
        projection=project_characters(load_characters(view.read_text(ref.id)),view.list_scenes(story.id),scene.id)
        return ('КАРТКИ ПЕРСОНАЖІВ\n'+projection.text if projection.text else '',projection.warnings,[ref.id])
    source=view.active_source(story.id,'source_characters')
    if source:
        if source.stale or not source.complete:raise ValueError('Опис персонажів потребує оновлення')
        return ('НЕПЕРЕВІРЕНІ ЗА ЧАСОМ АВТОРСЬКІ ОПИСИ ПЕРСОНАЖІВ\n'+view.read_text(source.id),[TEMPORAL_WARNING],[source.id])
    return '',[],[]
