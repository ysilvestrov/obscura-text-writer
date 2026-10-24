"""Read-only scene statistics. No gateways, dispatch or budget reservations."""
import re
import unicodedata
from ..memory.journal import load_memory,replay_memory,CATEGORIES


def text_statistics(text):
    words=re.findall(r"[^\W_]+(?:['’ʼ\-‐‑][^\W_]+)*",unicodedata.normalize('NFC',text),re.UNICODE)
    return {'characters':len(text),'words':len(words)}


def memory_statistics(view,scene,memory_id,*,first=False):
    empty={key:0 for key in CATEGORIES}
    if not memory_id:
        return {'available':True,'version_id':None,'stale':False,'active':empty,'events':empty.copy(),
            'event_count':0,'current_scene_events':0,'operations':{'add':0,'update':0,'retire':0}} if first else {'available':False,'reason':'Пам’ять ще не створена'}
    ref=view.get_version(memory_id)
    try:
        journal=load_memory(view.read_text(memory_id))
        source_scenes={id:view.scenes[v.scene_id] for id,v in view.versions.items()
            if v.kind in {'manual','edited'} and v.scene_id in view.scenes and not view.scenes[v.scene_id].trashed_at}
        if any(id not in source_scenes or source_scenes[id].position>scene.position for id in journal.source_prose_ids):
            raise ValueError('Пам’ять містить джерела з майбутніх або недоступних сцен')
        active=replay_memory(journal)
        return {'available':True,'version_id':ref.id,'stale':ref.stale,'complete':ref.complete,
            'active':{key:sum(e.category==key for e in active.values()) for key in CATEGORIES},
            'events':{key:sum(e.category==key for e in journal.events) for key in CATEGORIES},
            'operations':{op:sum(e.operation==op for e in journal.events) for op in ['add','update','retire']},
            'event_count':len(journal.events),
            'current_scene_events':sum(source_scenes[e.source_version_id].id==scene.id for e in journal.events)}
    except ValueError:
        return {'available':False,'version_id':ref.id,'stale':ref.stale,'reason':'Журнал не можна порахувати: перевірте структуру та джерела до цієї сцени'}


def scene_statistics(repo,scene_id,stage,editor_source_head=None,editor_source_version_id=None):
    from ..authoring.blueprints import get_role_settings
    from ..generation.context import build_context,ContextOverflow
    from ..generation.editor_loop import context as edit_context
    owner=repo.get_scene(scene_id);roles=get_role_settings(repo,owner.story_id)
    view=repo.context_view(owner.story_id);scene=view.effective_scene(scene_id)
    materials={}
    for kind in ['plan','brief','draft','prose']:
        id=scene.heads.get(kind)
        if not id:
            materials[kind]={'version_id':None,'stale':False,'complete':True,**text_statistics(scene.beats)} if kind=='plan' else None
        else:
            ref=view.get_version(id)
            materials[kind]={'version_id':id,'stale':ref.stale,'complete':ref.complete,**text_statistics(view.read_text(id))}
    previous=[s for s in view.list_scenes(scene.story_id) if s.position<scene.position]
    prior=memory_statistics(view,previous[-1],previous[-1].heads.get('memory')) if previous else memory_statistics(view,scene,None,first=True)
    current=memory_statistics(view,scene,scene.heads.get('memory'))
    role=roles.get({'brief':'planner','draft':'writer','edit':'editor','memory':'memory'}[stage])
    context={'available':False,'reason':'Роль не налаштована'}
    if role:
        context.update(reason=None,model=role.provider.model,provider=role.provider.provider)
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
        except ContextOverflow as exc:
            context.update(available=True,within_limits=False,reason=str(exc),**(exc.breakdown or {}))
        except ValueError as exc:context['reason']=str(exc)
    last=next((a for a in reversed(repo.list_attempts(scene.story_id)) if a.scene_id==scene.id and a.stage==stage and a.context.get('api_request') and a.usage),None)
    usage={'created_at':last.created_at,'model':last.context['api_request'].get('model'),'state':last.state,'usage':last.usage} if last else None
    return {'scene_id':scene.id,'scene_revision':scene.revision,'target_words':scene.target_words,
        'materials':materials,'memory':{'previous':prior,'through_scene':current},'stage':stage,'context':context,'last_usage':usage}
