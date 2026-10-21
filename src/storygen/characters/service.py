"""Author edits, provenance checks and preview over one captured view."""
import copy
import json
from ..domain import RevisionConflict,new_id
from .models import load_characters
from .projection import project_characters,TEMPORAL_WARNING


def _cards(view,story):
    return load_characters(view.read_text(story.characters_version_id)) if story.characters_version_id else []


def _normalize(view,story,payload):
    if not isinstance(payload,list):raise ValueError('Картки мають бути списком')
    previous={card.id:card for card in _cards(view,story)}
    prepared=copy.deepcopy(payload)
    for card in prepared:
        if not isinstance(card,dict):raise ValueError('Некоректна картка')
        id=card.get('id')
        if id is None:card['id']=new_id()
        elif id not in previous:raise ValueError('Невідомий ID персонажа; новий ID призначає сервер')
        card.setdefault('schema_version',2)
        known={e.id for e in previous[id].entries} if id in previous else set()
        for entry in card.get('entries',[]):
            if not isinstance(entry,dict):raise ValueError('Некоректна відомість')
            if entry.get('id') is None:entry['id']=new_id()
            elif entry['id'] not in known:raise ValueError('Невідомий ID відомості; новий ID призначає сервер')
    cards=load_characters(json.dumps(prepared,ensure_ascii=False,allow_nan=False))
    active={scene.id for scene in view.list_scenes(story.id)}
    refs=[]
    for card in cards:
        for entry in card.entries:
            if entry.availability=='from_scene' and entry.available_from_scene_id not in active:
                raise ValueError('Перша сцена доступності недоступна або належить іншому твору')
            for citation in entry.sources:
                try:source=view.get_version(citation.version_id)
                except KeyError:raise ValueError('Джерело відомості недоступне або належить іншому твору') from None
                if source.story_id!=story.id or source.kind not in {'source_characters','source_plan'} or not source.complete:
                    raise ValueError('Невірне джерело відомості персонажа')
                if citation.quote not in view.read_text(source.id):raise ValueError('Цитата відомості відсутня у джерелі')
                refs.append(source.id)
    return cards,list(dict.fromkeys(refs))


def read_character_material(repo,story_id,scene_id=None):
    view=repo.context_view(story_id);story=view.get_story(story_id);cards=_cards(view,story)
    source=view.active_source(story_id,'source_characters') if not story.characters_version_id else None
    warnings=[TEMPORAL_WARNING] if source or any(e.availability=='unclassified' for c in cards for e in c.entries) else []
    result={'story_id':story_id,'revision':story.revision,'version_id':story.characters_version_id,
        'cards':[c.model_dump() for c in cards],
        'scenes':[{'id':s.id,'title':s.title,'position':s.position} for s in view.list_scenes(story_id)],
        'source':{'version_id':source.id,'text':view.read_text(source.id)} if source else None,'warnings':warnings}
    if scene_id:
        projection=project_characters(cards,view.list_scenes(story_id),scene_id)
        result['preview']={'text':projection.text,'warnings':projection.warnings,'excluded_count':projection.excluded_count}
    return result


def preview_character_material(repo,story_id,cards,scene_id):
    view=repo.context_view(story_id);story=view.get_story(story_id)
    normalized,_=_normalize(view,story,cards)
    projection=project_characters(normalized,view.list_scenes(story_id),scene_id)
    return {'text':projection.text,'warnings':projection.warnings,'excluded_count':projection.excluded_count,'revision':story.revision}


def save_character_material(repo,story_id,cards,expected_revision):
    view=repo.context_view(story_id);story=view.get_story(story_id)
    if story.revision!=expected_revision:raise RevisionConflict('Твір змінено. Перезавантажте картки після збереження власних правок окремо.')
    normalized,refs=_normalize(view,story,cards)
    version=repo.save_version(story_id,None,'character_cards',json.dumps([c.model_dump() for c in normalized],ensure_ascii=False),refs)
    repo.publish_story_material(story_id,'characters_version_id',version.id,expected_revision)
    return read_character_material(repo,story_id)
