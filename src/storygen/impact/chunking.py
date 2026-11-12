"""Deterministic exact-span DAG; packing uses the actual provider request."""
import hashlib
import json
from .models import fingerprint
from .chunk_models import ChunkManifest


def document_id(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()


def task_payload(manifest,task,results,planning=False):
    documents={};units=[]
    for id in task.get('units',[]):
        unit=manifest.units[id];text=manifest.documents[unit['document_id']][unit['start']:unit['end']]
        key=document_id(text);documents[key]=text
        units.append({**unit,'id':id,'document_id':key})
    data={'response_character_limit':manifest.result_cap,'phase':task['phase'],'required_coverage':task['coverage'],'documents':documents,'sources':units}
    if task.get('target_span'):
        span=task['target_span'];text=manifest.documents[span['document_id']][span['start']:span['end']]
        data['target']={**span,'text':text,'version_id':task['version_id'],'material':task.get('material','prose')}
    inputs={}
    for id in task.get('dependencies',[]):
        if planning:inputs[id]={'reserved_result':'😀'*manifest.result_cap}
        elif id in results:inputs[id]=results[id]
        else:raise ValueError('Немає завершеної частини перевірки впливу')
    data['results']=inputs
    return data


def settings_for_manifest(manifest):
    data=manifest.settings.model_dump()
    # The writer-only variant field came later; stored manifests were stamped without it.
    if data.get('low_rating_variant') is None:data.pop('low_rating_variant',None)
    if manifest.wire_schema_version==1 and not data['provider']['local_disable_thinking']:
        data['provider'].pop('local_disable_thinking')
    return data


def manifest_stamp(manifest):
    data=manifest.model_dump(exclude={'fingerprint'})
    data['settings']=settings_for_manifest(manifest)
    if manifest.local_token_counter is None:data.pop('local_token_counter')
    if manifest.wire_schema_version==1:data.pop('wire_schema_version')
    return fingerprint(data)


def wire_version_for(role):
    return 2 if role.provider.provider=='local' and (role.provider.response_mode=='json_schema' or role.provider.local_disable_thinking) else 1


def plan_chunks(repo,plan):
    from ..authoring.blueprints import get_role_settings
    from ..generation.impact_chunk_context import fits_payload
    role=get_role_settings(repo,plan.story_id)['planner']
    cap=min(6000,role.max_input_chars//12,(role.context_tokens-role.max_output_tokens)//20,role.max_output_tokens//2)
    if cap<256:raise ValueError('Ліміти планувальника замалі навіть для службової частини аналізу')
    from importlib.resources import files
    wire=wire_version_for(role)
    from ..language import load_prompt
    prompt=load_prompt(f'impact_part_v{wire}',repo.get_story(plan.story_id).language)
    m=ChunkManifest(wire_schema_version=wire,plan=plan,settings=role,prompt_text=prompt,result_cap=cap,documents={},units={},coverage={},tasks=[],roots={})
    if wire==2:
        from .chunk_requests import request_for
        from ..token_budget.local_profiles import select_snapshot
        body=request_for(m,dict(phase='delta',results={},sources=[],documents={},required_coverage=[]))[2]
        m.local_token_counter=select_snapshot(repo.root,role.provider.provider,role.provider.base_url,body)
    # Reserve two fully serialized child results before freezing any leaf layout.
    while cap>=256:
        m.result_cap=cap
        if fits_payload(repo,m,{'phase':'reduce_check','results':{'a':{'reserved_result':'😀'*cap},'b':{'reserved_result':'😀'*cap}}}):break
        cap=int(cap*.8) if wire==2 else cap//2
    else:raise ValueError('Ліміти планувальника замалі для зведення двох частин')

    def add_doc(text):
        key=document_id(text);m.documents[key]=text;return key

    def add_task(phase,target,units=(),span=None,dependencies=(),material=None):
        value=dict(phase=phase,scene_id=target.scene_id,version_id=target.version_id,units=list(units),dependencies=list(dependencies))
        if span:value['target_span']=span
        if material:value['material']=material
        value['coverage']=list(dependencies) if phase.startswith('reduce_') else [*units,*([span['id']] if span else [])]
        value['id']=fingerprint({'task':value,'settings':settings_for_manifest(m),'cap':cap})
        value['stage']='impact_part';m.tasks.append(value)
        if len(m.tasks)>10000:raise ValueError('Перевірка потребує понад 10000 частин; звузьте обсяг передумов')
        return value['id']

    def reduce_tasks(ids,phase,target):
        # A final synthesis is mandatory even for a single text-check leaf.
        force=phase!='reduce_delta'
        while len(ids)>1 or force:
            ids=[add_task(phase,target,dependencies=ids[i:i+2]) for i in range(0,len(ids),2)]
            force=False
        return ids[0]

    def source_payload(ids):
        task={'phase':'check','units':ids,'coverage':ids+['0'*64],'dependencies':['0'*64]}
        return task_payload(m,task,{},planning=True)

    def ranges(text,predicate,overlap=128):
        if not text:
            if not predicate(0,0,0,0):raise ValueError('Службова частина запиту не вміщується в ліміти планувальника')
            return [[0,0,0,0]]
        result=[];start=0
        while start<len(text):
            low=start+1;high=len(text);best=start
            while low<=high:
                end=(low+high)//2
                if predicate(max(0,start-overlap),min(len(text),end+overlap),start,end):best=end;low=end+1
                else:high=end-1
            if best==start:raise ValueError('Службова частина або перекриття не вміщується в ліміти планувальника')
            if best<len(text):
                cut=max(text.rfind('\n\n',start,best),text.rfind('. ',start,best))
                if cut>start+(best-start)//2:best=cut+1
            result.append([max(0,start-overlap),min(len(text),best+overlap),start,best]);start=best
        return result

    groups={}
    for target in plan.targets:
        if target.blockers:continue
        all_units=[];changed=[]
        for change in target.changes:
            for side in ['old','new']:
                text=getattr(change,side+'_text');doc=add_doc(text)
                base=dict(document_id=doc,change_id=change.id,source_id=change.id+':'+side,side=side,changed=change.changed,label=change.label,input_kind=change.input_kind,input_field=change.input_field)
                def probe(a,b,c,d):
                    unit={**base,'start':a,'end':b,'core_start':c,'core_end':d}
                    key=fingerprint(unit);previous=m.units.get(key);m.units[key]=unit
                    good=fits_payload(repo,m,source_payload([key]),fraction=.65)
                    m.units.pop(key)
                    if previous is not None:m.units[key]=previous
                    return good
                parts=ranges(text,probe)
                # Repeated identical documents share coverage geometry as well as wire text.
                m.coverage.setdefault(doc,[[p[2],p[3]] for p in parts])
                for a,b,c,d in parts:
                    unit={**base,'start':a,'end':b,'core_start':c,'core_end':d};key=fingerprint(unit);m.units[key]=unit
                    all_units.append(key)
                    if change.changed:changed.append(key)
        def packets(ids):
            out=[];current=[]
            for key in dict.fromkeys(ids):
                if current and not fits_payload(repo,m,source_payload(current+[key]),fraction=.65):out.append(current);current=[]
                current.append(key)
            if current:out.append(current)
            return out
        if not changed:continue
        if target.group_id not in groups:
            leaves=[add_task('delta',target,units=batch) for batch in packets(changed)]
            groups[target.group_id]=reduce_tasks(leaves,'reduce_delta',target)
        delta=groups[target.group_id];batches=packets(all_units)
        roots={'delta':delta,'text':None,'memory':None}
        materials=[('text',target.text,target.material)]
        if target.memory_text and target.memory_evidence_status in {'current','historical'}:materials.append(('memory',target.memory_text,'memory'))
        for name,text,material in materials:
            doc=add_doc(text)
            def probe(a,b,c,d):
                span=dict(id='0'*64,document_id=doc,start=a,end=b,core_start=c,core_end=d)
                return all(fits_payload(repo,m,task_payload(m,dict(phase='check',version_id=target.version_id,material=material,target_span=span,units=batch,coverage=batch+['0'*64],dependencies=[delta]),{},planning=True)) for batch in batches)
            parts=ranges(text,probe);m.coverage.setdefault(doc,[[p[2],p[3]] for p in parts]);leaves=[]
            for a,b,c,d in parts:
                span=dict(document_id=doc,start=a,end=b,core_start=c,core_end=d)
                span['id']=fingerprint([target.version_id,material,span])
                for batch in batches:leaves.append(add_task('check',target,batch,span,[delta],material))
            roots[name]=reduce_tasks(leaves,'reduce_memory' if name=='memory' else 'reduce_check',target)
        m.roots[target.version_id]=roots
    m.fingerprint=manifest_stamp(m)
    return m
