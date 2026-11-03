"""Task-local exact evidence references; no fuzzy repair or model-owned coverage."""
import json
from typing import Literal
from pydantic import Field
from ..domain import DomainModel
from .models import Finding, Evidence, fingerprint
from .chunk_models import PartResultV2
from ..providers.requests import strict_schema


class WireFinding(DomainModel):
    target_evidence_id: str
    change_ids: list[str] = Field(min_length=1,max_length=1000)
    explanation: str = Field(min_length=1,max_length=8000)
    evidence_ids: list[str] = Field(min_length=1,max_length=100)


class WirePartResult(DomainModel):
    summary: str = Field(min_length=1,max_length=6000)
    verdict: Literal['no_impact','changes_required','uncertain']
    new_findings: list[WireFinding] = Field(max_length=100)
    evidence_ids: list[str] = Field(max_length=100)
    target_evidence_ids: list[str] = Field(max_length=12)
    uncertainty: str | None = None


def quote_windows(text):
    return [text[start:start+160] for start in range(0,len(text),128) if text[start:start+160]]


def build_wire(manifest,payload):
    changes=sorted({c.id for t in manifest.plan.targets for c in t.changes})
    aliases={key:f'C{i+1}' for i,key in enumerate(changes)}
    # Other machine addresses are task-local; change addresses remain stable across tasks.
    for prefix,values in [('D',payload.get('documents',{})),('U',[u['id'] for u in payload.get('sources',[])]),('R',payload.get('results',{}))]:
        aliases.update({key:f'{prefix}{i+1}' for i,key in enumerate(values)})
    for u in payload.get('sources',[]):aliases[u['source_id']]=aliases[u['change_id']]+':'+u['side']
    target=payload.get('target')
    if target:
        aliases[target['id']]='T1';aliases[target['version_id']]='V1';aliases.setdefault(target['document_id'],'TD1')
    registry={};seen={}
    def register(kind,quote,source_id=None):
        key=(kind,source_id,quote)
        if not quote:return
        if key not in seen:
            id=f'E{len(registry)+1}';seen[key]=id
            registry[id]={'kind':kind,'quote':quote,**({'source_id':source_id} if source_id else {})}
    for u in payload.get('sources',[]):
        for quote in quote_windows(payload['documents'][u['document_id']]):register('source',quote,u['source_id'])
    if target:
        for quote in quote_windows(target['text']):register('target',quote)
    for child in payload.get('results',{}).values():
        if 'reserved_result' in child:continue
        parsed=PartResultV2.model_validate(child)
        for e in [*parsed.evidence,*[e for f in parsed.findings for e in f.evidence]]:
            register('source',e.quote,e.source_id)
            cid=e.source_id.rsplit(':',1)[0]
            if cid in aliases:aliases[e.source_id]=aliases[cid]+':'+e.source_id.rsplit(':',1)[1]
        for quote in [*parsed.target_quotes,*[f.target_quote for f in parsed.findings]]:register('target',quote)
    address_fields={'id','document_id','source_id','change_id','version_id'}
    address_lists={'covered_ids','required_coverage','change_ids'}
    def replace(value,field=None):
        if field=='documents':return {aliases.get(k,k):v for k,v in value.items()}
        if isinstance(value,str):return aliases.get(value,value) if field in address_fields or field in address_lists else value
        if isinstance(value,list):return [replace(v,field) for v in value]
        if isinstance(value,dict):return {aliases.get(k,k) if field=='results' else k:replace(v,k) for k,v in value.items()}
        return value
    known_changes={u['change_id'] for u in payload.get('sources',[])}
    for child in payload.get('results',{}).values():
        if 'reserved_result' in child:continue
        for e in [*child['evidence'],*[e for f in child['findings'] for e in f['evidence']]]:known_changes.add(e['source_id'].rsplit(':',1)[0])
        known_changes.update(id for f in child['findings'] for id in f['change_ids'])
    wire=replace(payload)
    changed={c.id for t in manifest.plan.targets for c in t.changes if c.changed}
    wire['allowed_change_ids']=sorted(aliases[id] for id in known_changes & changed)
    for key,child in payload.get('results',{}).items():
        if 'reserved_result' in child:continue
        parsed=PartResultV2.model_validate(child)
        def eid(kind,quote,source=None):return seen[(kind,source,quote)]
        wire['results'][aliases[key]]={
            'summary':parsed.summary,'verdict':parsed.verdict,'uncertainty':parsed.uncertainty,
            'findings':[{'target_evidence_id':eid('target',f.target_quote),
                'change_ids':[aliases[id] for id in f.change_ids],'explanation':f.explanation,
                'evidence_ids':[eid('source',e.quote,e.source_id) for e in f.evidence]} for f in parsed.findings],
            'evidence_ids':[eid('source',e.quote,e.source_id) for e in parsed.evidence],
            'target_evidence_ids':[eid('target',q) for q in parsed.target_quotes]}
    wire.pop('required_coverage',None)
    wire['evidence_registry']={id:replace(entry) for id,entry in registry.items()}
    # Unknown child results may devote their entire cap to short quotations/IDs.
    # Child wire replaces literal quotes/long IDs with refs. The UTF-8 canonical
    # placeholder covers all quote/summary bytes; 1024 extra bytes cover the
    # registry + enum overhead for at most 12 standalone target quotations.
    # Source entries already contain longer source addresses in their canonical cap.
    unknown=sum('reserved_result' in c for c in payload.get('results',{}).values())
    if unknown:wire['reserved_reference_overhead']='x'*(1024*unknown)
    return wire,registry,aliases


def wire_schema(registry,payload):
    schema=strict_schema(WirePartResult)
    source=[id for id,e in registry.items() if e['kind']=='source']
    target=[id for id,e in registry.items() if e['kind']=='target']
    # Actual alias scope is supplied by build_wire in request_for.
    def references(node,ids):
        if ids:node['items']={'type':'string','enum':ids}
        else:node['maxItems']=0
    references(schema['properties']['evidence_ids'],source)
    references(schema['properties']['target_evidence_ids'],target)
    f=schema['$defs']['WireFinding']['properties']
    references(f['evidence_ids'],source)
    f['target_evidence_id']={'type':'string','enum':target} if target else {'type':'string'}
    if payload.get('phase') in {'delta','reduce_delta'} or not target or not source or not payload.get('allowed_change_ids'):schema['properties']['new_findings']['maxItems']=0
    if payload.get('phase') in {'delta','reduce_delta'}:schema['properties']['verdict']['enum']=['no_impact','uncertain']
    children=payload.get('results',{}).values()
    if any(c.get('findings') for c in children):schema['properties']['verdict']['enum']=['changes_required']
    elif any(c.get('uncertainty') or c.get('verdict')=='uncertain' for c in children):schema['properties']['verdict']['enum']=['uncertain'] if payload.get('phase') in {'delta','reduce_delta'} else ['uncertain','changes_required']
    return schema


def normalize_wire(raw,manifest,task,results):
    from .chunking import task_payload
    payload=task_payload(manifest,task,results)
    _,registry,aliases=build_wire(manifest,payload)
    parsed=WirePartResult.model_validate(raw)
    if len(json.dumps(raw,ensure_ascii=False,separators=(',',':')))>manifest.result_cap:raise ValueError('Wire відповідь перевищила резерв')
    def get(id,kind):
        if id not in registry or registry[id]['kind']!=kind:raise ValueError('Невідоме або стороннє посилання доказу')
        return registry[id]
    def evidence(ids):return [Evidence(source_id=get(id,'source')['source_id'],quote=get(id,'source')['quote']) for id in ids]
    reverse={alias:key for key,alias in aliases.items()}
    known=set(u['change_id'] for u in payload.get('sources',[]))
    findings=[];uncertain=False
    for child in payload.get('results',{}).values():
        c=PartResultV2.model_validate(child)
        uncertain|=bool(c.uncertainty or c.verdict=='uncertain')
        for e in [*c.evidence,*[e for f in c.findings for e in f.evidence]]:known.add(e.source_id.rsplit(':',1)[0])
        if task['phase'].startswith('reduce_'):
            findings.extend(c.findings)
            known.update(id for f in c.findings for id in f.change_ids)
    known&={c.id for t in manifest.plan.targets for c in t.changes if c.changed}
    for f in parsed.new_findings:
        ids=[reverse.get(id) for id in f.change_ids]
        if None in ids or not set(ids)<=known:raise ValueError('Невідома зміна у finding')
        if any(e.source_id.rsplit(':',1)[0] not in ids for e in evidence(f.evidence_ids)):raise ValueError('Цитата не належить указаній зміні')
        findings.append(Finding(target_quote=get(f.target_evidence_id,'target')['quote'],change_ids=ids,explanation=f.explanation,evidence=evidence(f.evidence_ids)))
    findings=list({fingerprint(f):f for f in findings}.values())
    if uncertain and parsed.verdict=='no_impact':raise ValueError('Невизначеність дочірньої частини не дозволяє позитивний висновок')
    if findings and parsed.verdict=='no_impact':raise ValueError('Підтверджені правки не дозволяють позитивний висновок')
    return PartResultV2(covered_ids=task['coverage'],summary=parsed.summary,verdict=parsed.verdict,findings=findings,evidence=evidence(parsed.evidence_ids),target_quotes=[get(id,'target')['quote'] for id in parsed.target_evidence_ids],uncertainty=parsed.uncertainty or ('Невизначеність дочірніх результатів не усунено.' if uncertain else None))
