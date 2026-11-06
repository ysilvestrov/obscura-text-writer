"""Authoritative full authoring materials for structure preparation."""
def prepare_sources(view,story):
    characters=view.get_version(story.characters_version_id) if story.characters_version_id else view.active_source(story.id,'source_characters')
    return [s for s in [view.active_source(story.id,'source_plan'),characters] if s]
