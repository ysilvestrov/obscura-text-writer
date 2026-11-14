"""Read-only scene statistics. No gateways, dispatch or budget reservations."""
import re
import unicodedata
from ..memory.journal import load_memory,replay_memory,CATEGORIES


def text_statistics(text):
    words=re.findall(r"[^\W_]+(?:['’ʼ\-‐‑][^\W_]+)*",unicodedata.normalize('NFC',text),re.UNICODE)
    return {'characters':len(text),'words':len(words)}


def memory_statistics(view,scene,memory_id,*,first=False,merged=False):
    empty={key:0 for key in CATEGORIES}
    if not memory_id:
        return {'available':True,'version_id':None,'stale':False,'active':empty,'events':empty.copy(),
            'event_count':0,'current_scene_events':0,'operations':{'add':0,'update':0,'retire':0}} if first else {'available':False,'reason':'Пам’ять ще не створена'}
    ref=view.get_version(memory_id)
    try:
        if merged:  # MEMORY-MERGE: the memory before a scene after a merge point is the merged journal
            from ..storage.memory_merges import merge_journal
            journal=merge_journal(view,memory_id)
        else:journal=load_memory(view.read_text(memory_id))
        source_scenes={id:view.scenes[v.scene_id] for id,v in view.versions.items()
            if v.kind in {'manual','edited'} and v.scene_id in view.scenes and not view.scenes[v.scene_id].trashed_at}
        # SERIES: the start snapshot of a series book (scene 0) is a valid source too.
        starts={id for id in journal.source_prose_ids[:1] if id in view.versions and view.versions[id].kind=='series_start'
                and view.versions[id].story_id==scene.story_id}
        if any(id not in starts and (id not in source_scenes or source_scenes[id].position>scene.position) for id in journal.source_prose_ids):
            raise ValueError('Пам’ять містить джерела з майбутніх або недоступних сцен')
        active=replay_memory(journal)
        return {'available':True,'version_id':ref.id,'stale':ref.stale,'complete':ref.complete,
            'active':{key:sum(e.category==key for e in active.values()) for key in CATEGORIES},
            'events':{key:sum(e.category==key for e in journal.events) for key in CATEGORIES},
            'operations':{op:sum(e.operation==op for e in journal.events) for op in ['add','update','retire']},
            'event_count':len(journal.events),
            'current_scene_events':sum(e.source_version_id in source_scenes and source_scenes[e.source_version_id].id==scene.id for e in journal.events)}
    except ValueError:
        return {'available':False,'version_id':ref.id,'stale':ref.stale,'reason':'Журнал не можна порахувати: перевірте структуру та джерела до цієї сцени'}


def scene_statistics(repo,scene_id,stage,editor_source_head=None,editor_source_version_id=None):
    from ..authoring.blueprints import get_role_settings
    from ..generation.context import build_context,ContextOverflow
    from ..generation.editor_loop import context as edit_context
    # One SQL snapshot per request: the scene and all material reads come from one view.
    view=repo.scene_view(scene_id);scene=repo.get_scene(scene_id,view=view);roles=get_role_settings(repo,scene.story_id)
    materials={}
    for kind in ['plan','brief','draft','prose']:
        id=scene.heads.get(kind)
        if not id:
            materials[kind]={'version_id':None,'stale':False,'complete':True,**text_statistics(scene.beats)} if kind=='plan' else None
        else:
            ref=view.get_version(id)
            materials[kind]={'version_id':id,'stale':ref.stale,'complete':ref.complete,**text_statistics(view.read_text(id))}
    from ..memory.previous import previous_memory
    before=previous_memory(view,scene,require=False)
    previous=before.ancestors
    prior=memory_statistics(view,previous[-1],before.memory_id,merged=bool(before.merge_key)) if previous else memory_statistics(view,scene,None,first=True)
    current=memory_statistics(view,scene,scene.heads.get('memory'))
    role=roles.get({'brief':'planner','draft':'writer','edit':'editor','memory':'memory'}[stage])
    context={'available':False,'reason':'Роль не налаштована'}
    if role:
        from ..generation.role_routing import WRITER_STAGES,settings_for
        # MODEL-001: the model shown is the one the request goes to (the writer's variant for scenes rated 0–1), also on overflow.
        shown=settings_for(role,'writer',view.get_story(scene.story_id),scene) if stage in WRITER_STAGES else role
        context.update(reason=None,model=shown.provider.model,provider=shown.provider.provider)
        try:
            if stage=='edit':
                from ..generation.editor_loop import source
                _,ref=source(view,scene_id,source_head=editor_source_head,version_id=editor_source_version_id)
                id=ref.id
                ctx=edit_context(view,scene_id,role,id)
                context['editor_source_version_id']=id
            else:
                if editor_source_head or editor_source_version_id:raise ValueError('Явне джерело дозволено лише для редактури')
                ctx=build_context(view,scene_id,stage,role)
            context.update(available=True,within_limits=True,**ctx.context_breakdown)
            context.update(memory_summary(ctx.memory_metrics))
        except ContextOverflow as exc:
            context.update(available=True,within_limits=False,reason=str(exc),**(exc.breakdown or {}))
        except ValueError as exc:context['reason']=str(exc)
    # The SQL scene filter returns the same attempts as filtering the story list by a.scene_id (tests/storage/test_attempt_filters.py).
    last=next((a for a in reversed(repo.list_attempts(scene.story_id,scene_id=scene.id)) if a.scene_id==scene.id and a.stage==stage and a.context.get('api_request') and a.usage),None)
    usage={'created_at':last.created_at,'model':last.context['api_request'].get('model'),'state':last.state,'usage':last.usage} if last else None
    return {'scene_id':scene.id,'scene_revision':scene.revision,'target_words':scene.target_words,
        'materials':materials,'memory':{'previous':prior,'through_scene':current},'stage':stage,'context':context,'last_usage':usage}


def memory_summary(metrics) -> dict:
    """What memory selection did in this request (#60, MEMORY-SELECT-S08); empty when the full memory fitted."""
    if metrics.get('selection'):
        sel=metrics['selection'];selected=sum(sel['layers'].values());dropped=sum(sel['dropped'].values())
        return {'memory_selection':{'selected':selected,'total':selected+dropped,'dropped':dropped,
            'layers':{k:v for k,v in sel['layers'].items() if v},'dropped_layers':{k:v for k,v in sel['dropped'].items() if v},
            'summaries':len(sel.get('summaries',[]))}}
    if metrics.get('narrow'):return {'memory_narrow':dict(metrics['narrow'])}
    return {}
