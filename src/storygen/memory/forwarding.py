"""Author selection of literary memory; the evidence journal is never rewritten."""
import hashlib
import json
from ..domain import DomainModel
from pydantic import Field
from .journal import load_memory,replay_memory


class ForwardingChange(DomainModel):
    expected_revision: int = Field(ge=0)
    fingerprint: str
    choices: dict[str,bool] = Field(max_length=10000)


def choices_at(view,scene_id,*,inclusive=False):
    scene=view.get_scene(scene_id);choices={}
    for item in view.list_scenes(scene.story_id):
        if item.position<scene.position or inclusive and item.id==scene_id:
            choices.update(item.memory_forwarding)
    return choices


def hidden_before(view,scene_id):
    return {id for id,enabled in choices_at(view,scene_id).items() if not enabled}


def memory_view_from_view(view,scene_id):
    scene=view.get_scene(scene_id);memory_id=scene.heads.get('memory')
    scenes=view.list_scenes(scene.story_id)
    choices=choices_at(view,scene_id,inclusive=True)
    stamp={'memory_id':memory_id,'prefix':[(s.id,s.heads.get('prose'),s.memory_forwarding) for s in scenes if s.position<=scene.position]}
    digest=hashlib.sha256(json.dumps(stamp,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    result={'scene':scene,'expected_revision':scene.revision,'fingerprint':digest,'rows':[],
        'can_save':False,'reason':'Спершу створіть пам’ять сцени','memory_id':memory_id}
    if not memory_id:return result
    journal=load_memory(view.read_text(memory_id))
    active=replay_memory(journal)
    entries=dict(active)
    for event in journal.events:
        if event.category=='open_threads' and event.operation=='retire':entries[event.claim_id]=event
    sources={s.heads.get('prose'):s for s in scenes}
    labels={'facts':'Факт','character_states':'Стан персонажа','open_threads':'Сюжетна лінія','timeline':'Хронологія'}
    for event in entries.values():
        source=sources.get(event.source_version_id)
        result['rows'].append({'claim_id':event.claim_id,'text':event.text,'category':event.category,
            'category_label':labels[event.category],'source_scene':source.position+1 if source else None,
            'source_title':source.title if source else 'Попереднє джерело','quote':event.quote,
            'forward':choices.get(event.claim_id,True),'closed':event.operation=='retire'})
    stale=view.get_version(memory_id).stale
    result.update(can_save=not stale,reason='Пам’ять застаріла: спершу оновіть її' if stale else None)
    return result


def memory_view(repo,scene_id):
    scene=repo.get_scene(scene_id)
    return memory_view_from_view(repo.context_view(scene.story_id),scene_id)


def save_forwarding(repo,scene_id,choices,expected_revision,fingerprint):
    from ..storage.memory_forwarding import save_forwarding as save
    body=ForwardingChange(choices=choices,expected_revision=expected_revision,fingerprint=fingerprint)
    return save(repo,scene_id,body)
