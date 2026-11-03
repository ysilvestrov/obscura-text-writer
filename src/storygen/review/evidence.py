"""Exact statement provenance and deterministic classification; no semantic oracle."""
from ..impact.models import fingerprint


def statement(registry,endpoint):
    row=registry[endpoint['ref']]
    start,end=endpoint['start'],endpoint['end'];quote=endpoint['quote']
    if (type(start) is not int or type(end) is not int or not isinstance(quote,str)
        or not quote or not 0<=start<end<=len(row['text']) or row['text'][start:end]!=quote):
        raise ValueError('Неточна адреса або цитата доказу')
    data=dict(role=row['kind'],version_id=row['version_id'],document_hash=row['document_hash'],
              start=row['start']+start,end=row['start']+end,quote=quote)
    return dict(id=fingerprint(data),**data)


def validate_priorities(decisions,statements):
    preferred=set();superseded=set();by_loser={}
    for decision in decisions:
        a,b=decision['preferred_statement_id'],decision['superseded_statement_id']
        if a==b or any(id not in statements or statements[id]['role']!='source' for id in [a,b]):
            raise ValueError('Пріоритет потребує двох різних відомих source-тверджень')
        if b in by_loser and by_loser[b]!=a:raise ValueError('Суперечливі авторські пріоритети')
        by_loser[b]=a;preferred.add(a);superseded.add(b)
    if preferred&superseded:raise ValueError('Цикл або ланцюжок авторських пріоритетів')
    return decisions


def _overlap(a,b):
    return (a['version_id']==b['version_id'] and a['document_hash']==b['document_hash']
            and max(a['start'],b['start'])<min(a['end'],b['end']))


def classify_candidates(candidates,registry,decisions,*,statements=None):
    known=dict(statements or {});valid=[];rejected=[]
    for index,c in enumerate(candidates):
        try:
            if c['type']=='contradiction':
                left=statement(registry,c['left']);right=statement(registry,c['right'])
                if left['id']==right['id'] or left['role']==right['role']=='target':
                    raise ValueError('Пара потребує різних тверджень і source-доказу')
                if not c['explanation'].strip():raise ValueError('Немає пояснення несумісності')
                for s in [left,right]:known[s['id']]=s
                valid.append((index,c,[left,right]))
            elif c['type']=='information_gap':
                target=statement(registry,c['target'])
                if target['role']!='target' or not c['missing_information'].strip() or not c['why_needed'].strip():
                    raise ValueError('Прогалина потребує target і конкретної причини')
                refs=c['source_refs']
                if len(set(refs))!=len(refs) or any(registry[r]['kind']!='source' for r in refs):raise ValueError('Непридатні джерела прогалини')
                known[target['id']]=target;valid.append((index,c,[target]))
            else:raise ValueError('Невідомий тип кандидата')
        except (ValueError,KeyError,TypeError) as exc:
            rejected.append(dict(index=index,code='invalid_evidence',reason=str(exc)))
    validate_priorities(decisions,known)
    losers={d['superseded_statement_id'] for d in decisions}
    resolved={frozenset([d['preferred_statement_id'],d['superseded_statement_id']]) for d in decisions}
    conflicts=[]
    for _,c,ss in valid:
        if c['type']=='contradiction' and all(s['role']=='source' for s in ss):
            ids=frozenset(s['id'] for s in ss)
            if ids not in resolved:conflicts.append(sorted(ids))
    conflict_ids={id for ids in conflicts for id in ids};concerns={};suppressed=[]
    authority_ids=losers|conflict_ids|{d['preferred_statement_id'] for d in decisions}
    for index,c,ss in valid:
        refs=[c['target']['ref']] if c['type']=='information_gap' else [c['left']['ref'],c['right']['ref']]
        sources=[s for s in ss if s['role']=='source'];targets=[s for s in ss if s['role']=='target']
        if any(s['id'] not in authority_ids and any(_overlap(s,known[id]) for id in authority_ids) for s in sources):
            rejected.append(dict(index=index,code='authority_ambiguous',reason='Уточніть межі твердження щодо авторського рішення або конфлікту'));continue
        if c['type']=='information_gap':kind='question';subtype='information_gap';message=c['missing_information']+' '+c['why_needed']
        elif not targets:
            if frozenset(s['id'] for s in ss) in resolved:
                suppressed.append(dict(index=index,reason='resolved_premise_conflict',statement_ids=[s['id'] for s in ss]));continue
            kind='question';subtype='premise_conflict';message=c['explanation']
        elif any(s['id'] in losers for s in sources):
            suppressed.append(dict(index=index,reason='superseded_source',statement_ids=[s['id'] for s in ss]));continue
        else:
            kind='question' if any(s['id'] in conflict_ids for s in sources) else 'issue'
            subtype='premise_conflict' if kind=='question' else 'contradiction';message=c['explanation']
        key=fingerprint([subtype,sorted(s['id'] for s in ss)])
        provenance=dict(index=index,message=message)
        if key in concerns:concerns[key]['provenance'].append(provenance);continue
        concerns[key]=dict(id=key,kind=kind,subtype=subtype,message=message,statement_ids=[s['id'] for s in ss],
            target_refs=[r for r in refs if registry[r]['kind']=='target'],source_refs=[r for r in refs if registry[r]['kind']=='source'],
            change_refs=list(dict.fromkeys(registry[r]['change_id'] for r in refs if registry[r]['kind']=='source')),
            provenance=[provenance])
    return dict(concerns=list(concerns.values()),suppressed=suppressed,rejected=rejected,statements=known,
                conflicts=list({tuple(c):c for c in conflicts}.values()),execution_state='partial' if rejected else 'complete')
