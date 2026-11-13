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
    from ..book.lineage import earlier_scenes
    scene=view.peek_scene(scene_id);choices={}
    for item in earlier_scenes(view,scene,peek=True)+([scene] if inclusive else []):
        choices.update(item.memory_forwarding)
    return choices


def hidden_before(view,scene_id):
    return {id for id,enabled in choices_at(view,scene_id).items() if not enabled}


def forwarded_before(view,scene_id):
    return {id for id,enabled in choices_at(view,scene_id).items() if enabled}


def effective_hidden(journal,hidden_claim_ids,*,forwarded=()):
    # I5: a claim that continues a retired one (resolves_claim_id: a thread's resolution fact, or the atmosphere state
    # of a slot value marked unknown) inherits its hidden mark unless the author chose for the new claim itself.
    # Links point back in journal order, so one ordered pass also follows chains.
    hidden=set(hidden_claim_ids)
    for e in journal.events:
        if e.resolves_claim_id in hidden and e.claim_id not in forwarded:hidden.add(e.claim_id)
    return hidden


def projection_policy(view,scene_id):
    """Selector value scene/memory_projection_policy: the effective hidden set (I5) at the scene's boundary."""
    choices=choices_at(view,scene_id)
    hidden={id for id,enabled in choices.items() if not enabled}
    if not hidden:return []
    scene=view.peek_scene(scene_id)
    from ..book.lineage import earlier_scenes
    previous=earlier_scenes(view,scene,peek=True)
    memory_id=previous[-1].heads.get('memory') if previous else None
    if memory_id:
        # Resolution links only; quotes and prefix are validated where the journal is used for content.
        try:
            ref=view.peek_version(memory_id)  # no freshness recomputation inside selector evaluation
            journal=load_memory(view.read_blob(ref.relative_path,ref.sha256).decode('utf-8'))
        except (ValueError,KeyError,OSError):journal=None
        if journal is not None:
            hidden=effective_hidden(journal,hidden,forwarded={id for id,enabled in choices.items() if enabled})
    return sorted(hidden)


def memory_view_from_view(view,scene_id):
    scene=view.get_scene(scene_id);memory_id=scene.heads.get('memory')
    scenes=view.list_scenes(scene.story_id)
    choices=choices_at(view,scene_id,inclusive=True)
    from ..book.lineage import previous_scenes
    prefix=previous_scenes(view.get_story(scene.story_id),scenes,scene)+[scene]
    stamp={'memory_id':memory_id,'prefix':[(s.id,s.heads.get('prose'),s.memory_forwarding) for s in prefix]}
    digest=hashlib.sha256(json.dumps(stamp,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    result={'scene':scene,'expected_revision':scene.revision,'fingerprint':digest,'rows':[],
        'can_save':False,'reason':'Спершу створіть пам’ять сцени','memory_id':memory_id}
    if not memory_id:return result
    journal=load_memory(view.read_text(memory_id))
    from .reuse import provenance_warnings
    ref=view.get_version(memory_id)
    result['warnings']=provenance_warnings(ref.dependency_snapshot.memory_provenance if ref.dependency_snapshot else [])
    active=replay_memory(journal)
    entries=dict(active)
    for event in journal.events:
        if event.category=='open_threads' and event.operation=='retire':entries[event.claim_id]=event
    sources={s.heads.get('prose'):s for s in scenes}
    labels={'facts':'Факт','character_states':'Стан персонажа','open_threads':'Сюжетна лінія','timeline':'Хронологія'}
    hidden=effective_hidden(journal,{id for id,enabled in choices.items() if not enabled},forwarded={id for id in choices if choices[id]})
    from .kinds import is_core_slot, tracked_ids
    story=view.get_story(scene.story_id);marks=story.memory_kind_overrides;tracked=tracked_ids(view,story,scene)
    result['story_revision']=story.revision
    for event in entries.values():
        # The title and scene follow the version the quote was taken from.
        quoted=event.evidence_version_id or event.source_version_id
        source=sources.get(quoted)
        if source is None:
            historical=view.get_version(quoted)
            source=next((s for s in prefix if s.id==historical.scene_id and historical.story_id==scene.story_id),None)
        result['rows'].append({'claim_id':event.claim_id,'text':event.text,'category':event.category,
            'category_label':labels[event.category],'source_scene':source.position+1 if source else None,
            'source_title':source.title if source else 'Попереднє джерело','quote':event.quote,'supporting_quotes':list(event.supporting_quotes),
            'forward':event.claim_id not in hidden,'closed':event.operation=='retire',
            # MEMORY-SELECT-S08: the author's selection mark; a core slot is always shown and takes none.
            'kind':marks.get(event.claim_id),'slot':is_core_slot(event,tracked)})
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
