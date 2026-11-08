"""Frozen pre-PERF-001 (2c203e8) review planning on public copying reads, without per-capture reuse; the equivalence reference for tests only."""
import json
from storygen.memory.journal import load_memory,validate_memory_journal
from storygen.storage.snapshots import build_author_baseline
from storygen.dependency_models import DependencySelector
from storygen.storage.snapshots import selector_value
from storygen.impact.models import ImpactPlan,ImpactTarget,SourceChange,fingerprint,TEXT_STAMP_EXCLUDE


def _raw(view,id):
    ref=view.versions[id]
    view.get_scene(ref.scene_id) if ref.scene_id else None
    if ref.story_id!=view.story.id or not ref.complete:raise ValueError('Неповне або стороннє джерело')
    return view.read_blob(ref.relative_path,ref.sha256).decode('utf-8')


def capture_target(view,version_id,*,baseline_override=None,current_sources_only=False):
    ref=view.versions[version_id];scene=view.get_scene(ref.scene_id)
    material='brief' if ref.kind=='brief' else 'prose'
    if ref.kind not in {'brief','edited','manual'}:raise ValueError('Непридатний матеріал перевірки')
    from storygen.characters.projection import OTHER_MATERIAL_WARNING
    warnings=set()
    blockers=[];hashes={};selectors={};changes={};baseline_ids={};visited=set();stack=set()
    order=[s.id for s in view.list_scenes(view.story.id) if s.position<=scene.position]
    text=_raw(view,ref.id)
    root_snapshot=view.acceptances[ref.id].baseline if ref.id in view.acceptances else ref.dependency_snapshot
    if baseline_override is not None:root_snapshot=baseline_override
    historic={};pending=[ref.id];searched=set()
    while pending:
        id=pending.pop(0)
        if id in searched:continue
        searched.add(id);value=view.versions[id]
        snapshot=root_snapshot if id==ref.id else view.acceptances[id].baseline if id in view.acceptances else value.dependency_snapshot
        if not snapshot:continue
        for selector in snapshot.selectors:
            if selector.kind=='scene' and selector.owner_id==scene.id and selector.field in {'character_ids','memory_projection_policy'}:
                historic.setdefault(selector.field,selector.expected)
        if not current_sources_only:pending.extend(source for source in snapshot.refs if source in view.versions and view.versions[source].scene_id==scene.id and view.versions[source].kind in {'brief','draft','edited','manual'})
    old_cast=historic.get('character_ids',scene.character_ids)
    from storygen.memory.forwarding import hidden_before
    old_hidden=historic.get('memory_projection_policy',sorted(hidden_before(view,scene.id)))
    def read(id,old=False):
        value=view.versions[id]
        if value.scene_id:
            owner=view.get_scene(value.scene_id)
            if value.kind in {'edited','manual','memory'} and owner.position>scene.position:
                raise ValueError('Майбутня проза або пам’ять не дозволені')
        raw=_raw(view,id);hashes[id]=value.sha256
        if value.kind in {'canon','style','source_plan'} and raw.strip():warnings.add(OTHER_MATERIAL_WARNING)
        baseline_ids[id]=view.acceptances[id].id if id in view.acceptances else None
        if id!=ref.id:
            from storygen.storage.impact_validity import latest
            assessment=latest(view,id)
            if assessment and view.scenes.get(assessment.target.scene_id) and view.scenes[assessment.target.scene_id].heads.get(assessment.target.material)==id:
                baseline_ids[id]='impact:'+assessment.id
            from storygen.review.store import latest as latest_review
            reviewed=latest_review(view,id)
            if reviewed:baseline_ids[id]='review:'+reviewed.id
        if value.kind=='character_cards':
            from storygen.characters.models import load_characters
            from storygen.characters.projection import project_characters
            projected_scenes=view.list_scenes(view.story.id)
            if old:
                for item in projected_scenes:
                    if item.id==scene.id:item.character_ids=old_cast
            projection=project_characters(load_characters(raw),projected_scenes,scene.id)
            warnings.update(projection.warnings)
            return projection.text
        if value.kind=='source_characters':
            return '[Нерозмічені вихідні описи не передаються; використовуйте картки персонажів]'
        if value.kind=='source_plan':
            from storygen.scene_description import SCENE_HEADING
            heading=SCENE_HEADING.search(raw)
            return raw[:heading.start()] if heading else raw
        if value.kind=='memory':
            validated_journal=_validated_journal
            from storygen.memory.projection import project_memory
            from storygen.memory.forwarding import hidden_before
            owner=view.get_scene(value.scene_id)
            if owner.position>=scene.position:raise ValueError('Пам’ять передумов має належати попередній сцені')
            journal,proof_hashes,prefix=validated_journal(view,id,owner)
            hashes.update(proof_hashes)
            numbers={source:item.position+1 for item,source in zip(prefix,journal.source_prose_ids)}
            state='ПОТОЧНІ ДЖЕРЕЛА' if journal.source_prose_ids==[s.heads.get('prose') for s in prefix] else 'ІСТОРИЧНІ ДЖЕРЕЛА — НЕ ПЕРЕПРИВ’ЯЗАНІ ДО НОВОЇ ПРОЗИ'
            return state+'\n'+project_memory(journal,old_cast if old else scene.character_ids,numbers,hidden_claim_ids=old_hidden if old else hidden_before(view,scene.id)).text
        return raw
    def document(value,selector,old=False):
        kinds=({'plan':{'scene_plan'},'brief':{'brief'},'draft':{'draft'},'prose':{'edited','manual'},'memory':{'memory'}}.get(selector.field)
            if selector.kind=='head' else
            {'canon_version_id':{'canon'},'style_version_id':{'style'},'characters_version_id':{'character_cards'}}.get(selector.field)
            if selector.kind=='story' else
            {'source_plan':{'source_plan'},'source_preamble':{'source_plan'},'source_characters':{'source_characters'}}.get(selector.field)
            if selector.kind=='source' else None)
        if kinds is not None and value is not None:
            if not isinstance(value,str) or value not in view.versions:raise ValueError('Версійне джерело передумов відсутнє')
            source=view.versions[value]
            if source.kind not in kinds or source.story_id!=view.story.id or (source.scene_id!=selector.owner_id if selector.kind=='head' else source.scene_id is not None):
                raise ValueError('Версійне джерело передумов має неправильний тип або власника')
            return read(value,old),value
        return json.dumps(value,ensure_ascii=False),None
    def visit(id):
        if id in stack:raise ValueError('Цикл залежностей')
        if id in visited:return
        stack.add(id);visited.add(id);value=view.versions[id];read(id)
        snapshot=root_snapshot if id==ref.id else view.acceptances[id].baseline if id in view.acceptances else value.dependency_snapshot
        if id==ref.id and not snapshot:raise ValueError('Немає відтворюваної історичної бази')
        if snapshot:
            for selector in snapshot.selectors:
                # Historical target self selectors are known inputs, not publish targets.
                current=selector_value(view,selector)
                if selector.kind=='source' and selector.field=='source_characters' and current!=selector.expected and not view.story.characters_version_id:
                    raise ValueError('Змінені описи персонажів без часових карток потребують ручного перегляду')
                if selector.kind=='order' and current!=selector.expected:raise ValueError('Зміна порядку сцен потребує ручного перегляду')
                if selector.kind=='head' and selector.field=='prose' and view.get_scene(selector.owner_id).position>=scene.position:
                    if selector.owner_id==scene.id:continue
                    raise ValueError('Невідповідна майбутня проза')
                old_text,old_ref=document(selector.expected,selector,True);new_text,new_ref=document(current,selector)
                key=fingerprint([selector.model_dump(),current,old_text,new_text])
                label=view.scenes[selector.owner_id].title if selector.owner_id in view.scenes else {'canon_version_id':'Канон','style_version_id':'Стиль','characters_version_id':'Персонажі','source_preamble':'Авторські вказівки','source_plan':'План твору','source_characters':'Описи персонажів'}.get(selector.field,selector.field)
                change=SourceChange(id=key,label=label,input_kind=selector.kind,input_field=selector.field,owner_id=selector.owner_id,old_ref=old_ref,new_ref=new_ref,
                    old_text=old_text,new_text=new_text,changed=old_text!=new_text or selector.expected!=current)
                changes[key]=change
                live=selector.model_copy(update={'expected':current}).model_dump()
                selectors[fingerprint([selector.kind,selector.owner_id,selector.field])]=live
            for source,sha in snapshot.refs.items():
                if source not in view.versions or view.versions[source].sha256!=sha:raise ValueError('Історичне джерело відсутнє або змінене')
                # Avoid self-target prose refs used only as publication CAS.
                if source!=id:
                    if current_sources_only:read(source)
                    else:visit(source)
        stack.remove(id)
    try:visit(ref.id)
    except (KeyError,ValueError,OSError) as exc:blockers.append(str(exc) if isinstance(exc,ValueError) else 'Джерело недоступне або пошкоджене')
    target=ImpactTarget(story_id=view.story.id,scene_id=scene.id,scene_title=scene.title,position=scene.position,material=material,
        version_id=ref.id,sha256=ref.sha256,content_format=ref.content_format,text=text,changes=list(changes.values()),
        source_hashes=hashes,selectors=list(selectors.values()),baseline_ids=baseline_ids,order=order,memory_id=scene.heads.get('memory'),blockers=blockers,warnings=sorted(warnings))
    capture_memory=_capture_memory
    target=target.model_copy(update=capture_memory(view,scene))
    target.group_id=fingerprint([c.model_dump() for c in sorted(target.changes,key=lambda c:c.id) if c.changed])
    target.fingerprint=fingerprint(target.model_dump(exclude=TEXT_STAMP_EXCLUDE))
    return target


def plan_impact(view):
    targets=[]
    for scene in view.list_scenes(view.story.id):
        for material in ['brief','prose']:
            id=scene.heads.get(material)
            if not id or not (view.get_version(id).stale or material=='prose' and view.effective_scene(scene.id).needs_review):continue
            target=capture_target(view,id)
            if target.text.strip():targets.append(target)
    return ImpactPlan(story_id=view.story.id,targets=targets,fingerprint=fingerprint([t.fingerprint for t in targets]))


# --- 2c203e8 storygen/impact/memory_review.py ---


def _validated_journal(view,id,scene):
    ref=view.versions[id]
    if ref.story_id!=scene.story_id or ref.scene_id!=scene.id or ref.kind!='memory' or not ref.complete:
        raise ValueError('Пам’ять має неправильного власника або незавершене джерело')
    raw=view.read_blob(ref.relative_path,ref.sha256).decode('utf-8');journal=load_memory(raw)
    prefix=[s for s in view.list_scenes(scene.story_id) if s.position<=scene.position]
    if len(journal.source_prose_ids)!=len(prefix):raise ValueError('Пам’ять не відповідає повному префіксу сцен')
    sources={};hashes={}
    for item,source in zip(prefix,journal.source_prose_ids):
        v=view.versions[source]
        if v.scene_id!=item.id or v.story_id!=scene.story_id or v.kind not in {'manual','edited'} or not v.complete:
            raise ValueError('Джерело пам’яті не відповідає префіксу сцен')
        sources[source]=view.read_blob(v.relative_path,v.sha256).decode('utf-8');hashes[source]=v.sha256
    validate_memory_journal(journal,sources)
    return journal,hashes,prefix


def _capture_memory(view,scene):
    id=scene.heads.get('memory')
    result=dict(memory_id=id,memory_sha256=None,memory_text='',memory_source_hashes={},memory_evidence_status='missing' if not id else 'invalid')
    if not id:return result
    try:
        journal,hashes,prefix=_validated_journal(view,id,scene)
        result.update(memory_sha256=view.versions[id].sha256,memory_text=journal.model_dump_json(),memory_source_hashes=hashes,
            memory_evidence_status='current' if journal.source_prose_ids==[s.heads.get('prose') for s in prefix] else 'historical')
    except (KeyError,ValueError,OSError):pass
    return result


# --- 2c203e8 storygen/review/capture.py ---

MODES={'historical_delta','current_consistency'}


def mode_for(view,version_id):
    root=view.acceptances[version_id].baseline if version_id in view.acceptances else view.versions[version_id].dependency_snapshot
    return 'historical_delta' if root is not None else 'current_consistency'


def capture(view,version_id,mode=None):
    mode=mode or mode_for(view,version_id)
    if mode not in MODES:raise ValueError('Невідомий режим бази перевірки')
    if mode=='historical_delta':return capture_target(view,version_id)
    scene_id=view.versions[version_id].scene_id
    baseline=build_author_baseline(view,scene_id)
    if view.versions[version_id].kind!='brief':
        from storygen.dependency_models import DependencySelector
        brief=view.get_scene(scene_id).heads.get('brief')
        baseline.selectors.append(DependencySelector(kind='head',owner_id=scene_id,field='brief',expected=brief))
        if brief:baseline.refs[brief]=view.versions[brief].sha256
    return capture_target(view,version_id,baseline_override=baseline,current_sources_only=True)


def modes_for(view,targets):return {t.version_id:mode_for(view,t.version_id) for t in targets}


def plan_review(view):
    targets=[]
    for scene in view.list_scenes(view.story.id):
        for material in ['brief','prose']:
            id=scene.heads.get(material)
            if not id or not (view.get_version(id).stale or material=='prose' and view.effective_scene(scene.id).needs_review):continue
            t=capture(view,id)
            if t.text.strip():targets.append(t)
    return ImpactPlan(story_id=view.story.id,targets=targets,fingerprint=fingerprint([t.fingerprint for t in targets]))



# --- 2c203e8 storygen/impact/presentation.py (scene_status) ---
from storygen.storage.impact_validity import current_record


def scene_status(view):
    rows={}
    for scene in view.list_scenes(view.story.id):
        values={}
        for material in ['brief','prose']:
            id=scene.heads.get(material)
            record=current_record(view,id) if id else None
            values[material]=(record.verdict.verdict if record else 'pending' if id and (view.get_version(id).stale or material=='prose' and view.effective_scene(scene.id).needs_review) else 'current' if id else 'missing')
        id=scene.heads.get('memory')
        values['memory']='missing' if not id else 'needs_update' if view.get_version(id).stale else 'current'
        rows[scene.id]=values
    return rows
