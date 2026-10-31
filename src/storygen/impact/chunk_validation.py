"""Exact delivered-span evidence, complete DAG coverage and replayable v2 proofs."""
import json
from ..providers.models import RoleSettings
from .chunk_models import PartResult,PartResultV2,ChunkManifest
from .chunking import document_id,manifest_stamp,task_payload,settings_for_manifest
from .models import MaterialVerdict,ImpactRecord,fingerprint,TEXT_STAMP_EXCLUDE
from .validation import decode_response,_coverage


def closure(manifest,roots):
    tasks={t['id']:t for t in manifest.tasks};seen=set()
    def visit(id):
        if id in seen:return
        seen.add(id)
        for child in tasks[id]['dependencies']:visit(child)
    for id in roots:
        if id:visit(id)
    return [t for t in manifest.tasks if t['id'] in seen]


def _intervals(parts,length):
    parts=sorted(set(tuple(p) for p in parts))
    if not parts or parts[0][0]!=0 or parts[-1][1]!=length or any(a[1]!=b[0] for a,b in zip(parts,parts[1:])):raise ValueError('Неповне охоплення діапазонів джерела')


def verify_attempt(attempt,manifest,task,results,read_partial,story_id,run_id):
    if attempt.story_id!=story_id or attempt.run_id!=run_id or attempt.scene_id!=task['scene_id'] or attempt.stage!='impact_part' or attempt.state!='completed' or attempt.finish_reason!='stop':raise ValueError('Незавершений доказ частини')
    ctx=attempt.context;expected=task_payload(manifest,task,results)
    from .chunk_requests import request_for
    _,user,body=request_for(manifest,expected)
    if (ctx.get('impact_chunk_manifest')!=manifest.fingerprint or ctx.get('impact_chunk_task')!=task or ctx.get('user_text')!=user or ctx.get('api_request')!=body or RoleSettings.model_validate(ctx.get('settings')).model_dump()!=manifest.settings.model_dump()):raise ValueError('Доказ має інший API-запит частини')
    if ctx.get('system_text')!=manifest.prompt_text:raise ValueError('Інший контракт промпту частини')
    result=validate_part(decode_response(read_partial(attempt.partial_path)),manifest,task,results)
    if result.model_dump()!=ctx.get('impact_result'):raise ValueError('Первинна відповідь не відповідає частині')
    return result


def validate_manifest(manifest):
    m=ChunkManifest.model_validate(manifest)
    if m.fingerprint!=manifest_stamp(m):raise ValueError('Невідповідний fingerprint маніфесту')
    for key,text in m.documents.items():
        if key!=document_id(text):raise ValueError('Змінений документ маніфесту')
    for key,parts in m.coverage.items():_intervals(parts,len(m.documents[key]))
    targets={t.version_id:t for t in m.plan.targets};tasks={};sources={}
    for target in m.plan.targets:
        for c in target.changes:
            for side in ['old','new']:
                key=c.id+':'+side;text=getattr(c,side+'_text')
                if key in sources and sources[key]!=text:raise ValueError('Суперечливе джерело маніфесту')
                sources[key]=text
    for key,u in m.units.items():
        if key!=fingerprint(u) or u['source_id']!=u['change_id']+':'+u['side'] or sources[u['source_id']]!=m.documents[u['document_id']]:raise ValueError('Некоректна одиниця джерела')
        if not 0<=u['start']<=u['core_start']<=u['core_end']<=u['end']<=len(sources[u['source_id']]):raise ValueError('Некоректний діапазон джерела')
    for task in m.tasks:
        key=task['id'];target=targets[task['version_id']]
        value={k:v for k,v in task.items() if k not in {'id','stage'}}
        if key!=fingerprint({'task':value,'settings':settings_for_manifest(m),'cap':m.result_cap}) or key in tasks or task['scene_id']!=target.scene_id or task['stage']!='impact_part':raise ValueError('Некоректна задача маніфесту')
        if any(id not in tasks for id in task['dependencies']):raise ValueError('Відсутня або циклічна залежність частини')
        expected=task['dependencies'] if task['phase'].startswith('reduce_') else [*task['units'],*([task['target_span']['id']] if task.get('target_span') else [])]
        _coverage(task['coverage'],expected)
        if task['phase'] not in {'delta','check','reduce_delta','reduce_check','reduce_memory'}:raise ValueError('Невідома фаза частини')
        allowed={c.id for c in target.changes}
        if any(m.units[id]['change_id'] not in allowed for id in task['units']):raise ValueError('Стороннє джерело частини')
        if task['phase']=='delta' and (task['dependencies'] or any(not m.units[id]['changed'] for id in task['units'])):raise ValueError('Некоректна дельта')
        if task['phase']=='check' and task['dependencies']!=[m.roots[target.version_id]['delta']]:raise ValueError('Неповна глобальна дельта')
        if task['phase'].startswith('reduce_'):
            if not 1<=len(task['dependencies'])<=2 or task['units'] or task.get('target_span'):raise ValueError('Некоректне зведення')
            phase=task['phase'];allowed_phases={'delta','reduce_delta'} if phase=='reduce_delta' else {'check',phase}
            if any(tasks[id]['phase'] not in allowed_phases for id in task['dependencies']):raise ValueError('Стороння фаза зведення')
            if phase!='reduce_delta' and any(tasks[id].get('material', 'memory' if tasks[id]['phase']=='reduce_memory' else target.material)!=('memory' if phase=='reduce_memory' else target.material) for id in task['dependencies']):raise ValueError('Змішана проза й пам’ять')
        tasks[key]=task
    for version,roots in m.roots.items():
        target=targets[version]
        for name in ['text','memory']:
            root=roots[name]
            if not root:continue
            if tasks[root]['phase']!=('reduce_check' if name=='text' else 'reduce_memory'):raise ValueError('Немає завершального синтезу')
            raw=target.text if name=='text' else target.memory_text
            primary=[];by_span={}
            for task in closure(m,[root]):
                if task['phase']!='check':continue
                if task['version_id']!=version:raise ValueError('Інший матеріал у графі')
                span=task['target_span']
                if m.documents[span['document_id']]!=raw or not 0<=span['start']<=span['core_start']<=span['core_end']<=span['end']<=len(raw):raise ValueError('Інший цільовий діапазон')
                if span['id']!=fingerprint([version,task['material'],{k:v for k,v in span.items() if k!='id'}]):raise ValueError('Невідповідний ID діапазону')
                primary.append((span['core_start'],span['core_end']))
                by_span.setdefault(span['id'],set()).update(task['units'])
            _intervals(primary,len(raw))
            for units in by_span.values():
                for c in target.changes:
                    for side in ['old','new']:
                        spans=[[m.units[id]['core_start'],m.units[id]['core_end']] for id in units if m.units[id]['source_id']==c.id+':'+side]
                        _intervals(spans,len(getattr(c,side+'_text')))
        delta_tasks=closure(m,[roots['delta']])
        if any(t['phase'] not in {'delta','reduce_delta'} for t in delta_tasks):raise ValueError('Некоректний граф дельти')
        units={id for t in delta_tasks for id in t['units']}
        for c in target.changes:
            if not c.changed:continue
            for side in ['old','new']:
                _intervals([[m.units[id]['core_start'],m.units[id]['core_end']] for id in units if m.units[id]['source_id']==c.id+':'+side],len(getattr(c,side+'_text')))
    return m


def validate_part(payload,manifest,task,results):
    model=PartResultV2 if manifest.wire_schema_version==2 else PartResult
    if manifest.wire_schema_version==2:
        from .reference_wire import normalize_wire
        result=normalize_wire(payload,manifest,task,results)
        payload=result.model_dump()
    else:result=model.model_validate(payload)
    from .result_budget import budget_size,LEGACY_CAP_ERROR
    size=budget_size(payload,manifest.wire_schema_version)
    if size>manifest.result_cap:raise ValueError(f'{LEGACY_CAP_ERROR}: {size} символів модельних даних, доступно {manifest.result_cap}; службове покриття не включено. Текст збережено' if manifest.wire_schema_version==2 else f'{LEGACY_CAP_ERROR}: {size} символів, доступно {manifest.result_cap}. Текст збережено')
    _coverage(result.covered_ids,task['coverage'])
    inputs=task_payload(manifest,task,results)
    allowed={};target_text=inputs.get('target',{}).get('text','');known_changes=set()
    for u in inputs['sources']:
        allowed.setdefault(u['source_id'],[]).append(inputs['documents'][u['document_id']]);known_changes.add(u['change_id'])
    child_findings=[];uncertain=False
    for child in inputs['results'].values():
        parsed=model.model_validate(child);uncertain|=bool(parsed.uncertainty or parsed.verdict=='uncertain')
        for e in [*parsed.evidence,*[e for f in parsed.findings for e in f.evidence]]:
            allowed.setdefault(e.source_id,[]).append(e.quote);known_changes.add(e.source_id.rsplit(':',1)[0])
        if task['phase'].startswith('reduce_'):
            child_findings.extend(parsed.findings)
            target_text+='\n'+parsed.summary+'\n'+'\n'.join(f.target_quote for f in parsed.findings)
            known_changes.update(id for f in parsed.findings for id in f.change_ids)
            if manifest.wire_schema_version==2:target_text+='\n'+'\n'.join(parsed.target_quotes)
    if uncertain and result.verdict=='no_impact':raise ValueError('Невизначеність дочірньої частини не дозволяє позитивний висновок')
    if (result.verdict=='changes_required')!=bool(result.findings):raise ValueError('Конкретні правки потрібні лише для changes_required')
    if task['phase'] in {'delta','reduce_delta'} and result.findings:raise ValueError('Дельта не є висновком щодо сцени')
    if result.uncertainty and result.verdict=='no_impact':raise ValueError('Невизначеність не дозволяє позитивний висновок')
    if manifest.wire_schema_version==2:
        for quote in result.target_quotes:
            if not quote or quote not in target_text:raise ValueError('Неточна цільова цитата синтезу')
    for f in result.findings:
        if f.target_quote not in target_text or not set(f.change_ids)<=known_changes:raise ValueError('Неточна цільова цитата або невідома зміна')
    for e in [*result.evidence,*[e for f in result.findings for e in f.evidence]]:
        if not any(e.quote in text for text in allowed.get(e.source_id,[])):raise ValueError('Неточна або непередана цитата частини')
    required={fingerprint(f.model_dump()) for f in child_findings}
    actual={fingerprint(f.model_dump()) for f in result.findings}
    if not required<=actual:raise ValueError('Зведення втратило підтверджені правки')
    return result


def verify_chunk_record(record,attempts,read_partial):
    m=validate_manifest(record.chunk_manifest)
    target=next(t for t in m.plan.targets if t.version_id==record.target.version_id)
    # Same-run review overlays may advance baseline IDs, but never the narrative inputs.
    if target.model_dump(exclude={'fingerprint','baseline_ids'})!=record.target.model_dump(exclude={'fingerprint','baseline_ids'}):raise ValueError('Інший знімок частин')
    roots=m.roots[target.version_id];tasks=closure(m,[roots['text'],roots['memory']]);results={}
    if set(record.proof_attempt_ids)!={t['id'] for t in tasks}:raise ValueError('Неповний набір доказів частин')
    for task in tasks:
        attempt=attempts[record.proof_attempt_ids[task['id']]]
        result=verify_attempt(attempt,m,task,results,read_partial,record.story_id,record.run_id)
        results[task['id']]=result.model_dump()
    verdict,memory,explanation=combined_result(m,target,results)
    if record.verdict!=verdict or record.memory_semantic_impact!=memory or record.memory_explanation!=explanation:raise ValueError('Зведений висновок не відповідає доказам')
    if record.attempt_id!=record.proof_attempt_ids[roots['text']] or record.delta_attempt_id!=record.proof_attempt_ids[roots['delta']]:raise ValueError('Інший кореневий доказ')
    return results


def combined_result(manifest,target,results):
    model=PartResultV2 if manifest.wire_schema_version==2 else PartResult
    roots=manifest.roots[target.version_id];root=model.model_validate(results[roots['text']])
    verdict=MaterialVerdict(version_id=target.version_id,verdict=root.verdict,covered_change_ids=[c.id for c in target.changes if c.changed],explanation=root.summary,findings=root.findings)
    memory='unchecked';explanation='Журнал пам’яті не перевірявся цим набором частин.'
    if roots['memory']:
        own=model.model_validate(results[roots['memory']])
        from .validation import validate_check
        own_verdict=MaterialVerdict(version_id=target.version_id,verdict=own.verdict,covered_change_ids=[c.id for c in target.changes if c.changed],explanation=own.summary,findings=own.findings)
        validate_check(dict(materials=[own_verdict.model_dump()],memory_semantic_impact='unchecked',memory_explanation=own.summary),target.model_copy(update={'text':target.memory_text}))
        memory='possible' if own.findings else 'none_found' if own.verdict=='no_impact' else 'unchecked';explanation=own.summary
    from .validation import validate_check
    validate_check(dict(materials=[verdict.model_dump()],memory_semantic_impact=memory,memory_explanation=explanation),target)
    return verdict,memory,explanation
