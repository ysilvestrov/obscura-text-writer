"""Read-only character history validation, separate from current usability."""
from ..characters.models import load_characters


def check_character_versions(report,root,versions,scenes,stories):
    from .integrity import contained_path
    for ref in versions.values():
        if ref.kind!='character_cards':continue
        try:
            cards=load_characters(contained_path(root,ref.relative_path).read_text(encoding='utf-8'))
            for card in cards:
                for entry in card.entries:
                    if entry.availability=='from_scene':
                        anchor=scenes.get(entry.available_from_scene_id)
                        if not anchor or anchor.story_id!=ref.story_id:raise ValueError('Невірна сцена доступності')
                        story=stories.get(ref.story_id)
                        if anchor.trashed_at and story and not story.trashed_at and story.characters_version_id==ref.id:
                            report.limitations.append(ref.id+': archived_character_anchor: сцена доступності в кошику; виправте поточні картки перед генерацією.')
                    for citation in entry.sources:
                        source=versions.get(citation.version_id)
                        if not source or source.story_id!=ref.story_id or source.kind not in {'source_plan','source_characters'} or not source.complete:
                            raise ValueError('Невірне джерело картки')
                        if citation.quote not in contained_path(root,source.relative_path).read_text(encoding='utf-8'):
                            raise ValueError('Цитата відсутня у джерелі')
        except (ValueError,KeyError,OSError,TypeError):
            report.add('invalid_characters',ref.id,'Некоректні картки, джерела або сцена доступності')
