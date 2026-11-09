"""Read-only old/current narrative inputs with exact provenance and temporal projection."""
import json
from ..dependency_models import DependencySelector
from ..storage.snapshots import rating_fallback,selector_value
from ..rating.levels import from_wire,is_lower
from .models import ImpactPlan,ImpactTarget,SourceChange,fingerprint,TEXT_STAMP_EXCLUDE


def _raw(view,id):
    ref=view.versions[id]
    view.peek_scene(ref.scene_id) if ref.scene_id else None
    if ref.story_id!=view.story.id or not ref.complete:raise ValueError('Неповне або стороннє джерело')
    return view.read_blob(ref.relative_path,ref.sha256).decode('utf-8')


def capture_target(view,version_id,*,baseline_override=None,current_sources_only=False):
    ref=view.versions[version_id];scene=view.get_scene(ref.scene_id)
    material='brief' if ref.kind=='brief' else 'prose'
    if ref.kind not in {'brief','edited','manual'}:raise ValueError('Непридатний матеріал перевірки')
    from ..characters.projection import OTHER_MATERIAL_WARNING
    warnings=set()
    blockers=[];hashes={};selectors={};changes={};baseline_ids={};visited=set();stack=set();seen_selectors=set();seen_live={}
    order=[s.id for s in view.peek_scenes(view.story.id) if s.position<=scene.position]
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
    from ..memory.forwarding import hidden_before
    old_hidden=historic.get('memory_projection_policy',sorted(hidden_before(view,scene.id)))
    read_cache={}
    def read(id,old=False):
        # One capture reaches the same input through many selectors. The text and the side effects (hashes, warnings,
        # baseline_ids) depend only on (id, old) within this capture, so the first successful read is reused.
        if (id,old) not in read_cache:read_cache[id,old]=read_uncached(id,old)
        return read_cache[id,old]
    def read_uncached(id,old):
        value=view.versions[id]
        if value.scene_id:
            owner=view.peek_scene(value.scene_id)
            if value.kind in {'edited','manual','memory'} and owner.position>scene.position:
                raise ValueError('Майбутня проза або пам’ять не дозволені')
        raw=_raw(view,id);hashes[id]=value.sha256
        if value.kind in {'canon','style','source_plan'} and raw.strip():warnings.add(OTHER_MATERIAL_WARNING)
        baseline_ids[id]=view.acceptances[id].id if id in view.acceptances else None
        if id!=ref.id:
            from ..storage.impact_validity import latest
            assessment=latest(view,id)
            if assessment and view.scenes.get(assessment.target.scene_id) and view.scenes[assessment.target.scene_id].heads.get(assessment.target.material)==id:
                baseline_ids[id]='impact:'+assessment.id
            from ..review.store import latest as latest_review
            reviewed=latest_review(view,id)
            if reviewed:baseline_ids[id]='review:'+reviewed.id
        if value.kind=='character_cards':
            from ..characters.models import load_characters
            from ..characters.projection import project_characters
            # Read-only projection over shared view models; the old cast goes into a separate copy of the target scene.
            projected_scenes=view.peek_scenes(view.story.id)
            if old:projected_scenes=[item.model_copy(update={'character_ids':old_cast}) if item.id==scene.id else item for item in projected_scenes]
            projection=project_characters(load_characters(raw),projected_scenes,scene.id)
            warnings.update(projection.warnings)
            return projection.text
        if value.kind=='source_characters':
            return '[Нерозмічені вихідні описи не передаються; використовуйте картки персонажів]'
        if value.kind=='source_plan':
            from ..scene_description import SCENE_HEADING
            heading=SCENE_HEADING.search(raw)
            return raw[:heading.start()] if heading else raw
        if value.kind=='memory':
            from .memory_review import validated_journal
            from ..memory.projection import project_memory
            from ..memory.forwarding import hidden_before
            owner=view.peek_scene(value.scene_id)
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
            snapshot_selectors=list(snapshot.selectors)
            replace,fallback=rating_fallback(view,snapshot)
            if replace and fallback and is_lower(from_wire(selector_value(view,fallback)),from_wire(fallback.expected)):
                # A snapshot without its own rating is judged against the story's initial rating, as freshness does.
                # The baseline joins the capture only when lowered, so fingerprints of unaffected captures stay put.
                snapshot_selectors=[s for s in snapshot_selectors if s.field!='content_rating']+[fallback]
            for selector in snapshot_selectors:
                # An equal selector (all fields) already passed the checks below and wrote the same change; only its
                # live value is written again, because `selectors` is keyed by (kind, owner, field) and the last write wins.
                seen=selector.model_dump_json()
                if seen in seen_selectors:
                    if seen in seen_live:selectors[seen_live[seen][0]]=seen_live[seen][1]
                    continue
                seen_selectors.add(seen)
                # Historical target self selectors are known inputs, not publish targets.
                current=selector_value(view,selector)
                if selector.field=='content_rating' and not is_lower(from_wire(current),from_wire(selector.expected)):
                    # A raised rating is not a changed input: it neither stales the material nor alters the capture.
                    current=selector.expected
                if selector.kind=='source' and selector.field=='source_characters' and current!=selector.expected and not view.story.characters_version_id:
                    raise ValueError('Змінені описи персонажів без часових карток потребують ручного перегляду')
                if selector.kind=='order' and current!=selector.expected:raise ValueError('Зміна порядку сцен потребує ручного перегляду')
                if selector.kind=='head' and selector.field=='prose' and view.peek_scene(selector.owner_id).position>=scene.position:
                    if selector.owner_id==scene.id:continue
                    raise ValueError('Невідповідна майбутня проза')
                old_text,old_ref=document(selector.expected,selector,True);new_text,new_ref=document(current,selector)
                key=fingerprint([selector.model_dump(),current,old_text,new_text])
                label=view.scenes[selector.owner_id].title if selector.owner_id in view.scenes else {'canon_version_id':'Канон','style_version_id':'Стиль','characters_version_id':'Персонажі','source_preamble':'Авторські вказівки','source_plan':'План твору','source_characters':'Описи персонажів'}.get(selector.field,selector.field)
                change=SourceChange(id=key,label=label,input_kind=selector.kind,input_field=selector.field,owner_id=selector.owner_id,old_ref=old_ref,new_ref=new_ref,
                    old_text=old_text,new_text=new_text,changed=old_text!=new_text or selector.expected!=current)
                changes[key]=change
                live=selector.model_copy(update={'expected':current}).model_dump()
                live_key=fingerprint([selector.kind,selector.owner_id,selector.field])
                selectors[live_key]=live;seen_live[seen]=(live_key,live)
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
    from .memory_review import capture_memory
    target=target.model_copy(update=capture_memory(view,scene))
    target.group_id=fingerprint([c.model_dump() for c in sorted(target.changes,key=lambda c:c.id) if c.changed])
    target.fingerprint=fingerprint(target.model_dump(exclude=TEXT_STAMP_EXCLUDE))
    return target


def plan_impact(view):
    targets=[]
    for scene in view.peek_scenes(view.story.id):
        for material in ['brief','prose']:
            id=scene.heads.get(material)
            if not id:continue
            view.peek_version(id)  # The same KeyError as get_version for an absent head; no copy.
            if not (view.is_stale(id) or material=='prose' and view.effective_scene(scene.id).needs_review):continue
            target=capture_target(view,id)
            if target.text.strip():targets.append(target)
    return ImpactPlan(story_id=view.story.id,targets=targets,fingerprint=fingerprint([t.fingerprint for t in targets]))
