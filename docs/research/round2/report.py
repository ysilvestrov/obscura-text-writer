"""Preliminary aggregation; final reporting waits for frozen data and human scoring."""
from collections import Counter


def model_verdict(response):
    if response['status']!='valid':return response['status']
    kinds={r['kind'] for r in response['parsed']['concerns']}
    return 'mixed' if len(kinds)>1 else next(iter(kinds)) if kinds else 'clean'


def flip_rate(records):
    groups={}
    for r in records:
        draws=groups.setdefault(r['case'],{})
        if r['draw'] in draws:raise ValueError('Duplicate draw')
        draws[r['draw']]=r['verdict']
    if not groups or any(set(d)!={1,2,3} for d in groups.values()):raise ValueError('All three draws required')
    changed=sum(len(set(d.values()))>1 for d in groups.values())
    return dict(changed=changed,cases=len(groups),rate=changed/len(groups))


def primary_summary(records,cases):
    from .scoring import baseline
    by_id={c['id']:c for c in cases};models={}
    def qualifies(m):
        if (m['total'],m['clean_denominator'],m['issue_denominator'])!=(144,60,84):
            raise ValueError('Full primary denominators required')
        return m['fp']<=7 and m['miss']<=10 and m['valid']>=137
    for label in sorted({r['config'] for r in records}):
        rows=[r for r in records if r['config']==label]
        if {(r['case'],r['draw']) for r in rows}!={(c,d) for c in by_id for d in [1,2,3]} or len(rows)!=3*len(cases):
            raise ValueError('Missing/duplicate primary slots')
        aggregate=metrics(rows)
        models[label]=dict(aggregate=aggregate,thresholds_passed=qualifies(aggregate),flip=flip_rate(rows),
            draws={str(d):metrics([r for r in rows if r['draw']==d]) for d in [1,2,3]},
            contexts={ctx:metrics([r for r in rows if by_id[r['case']]['context']==ctx]) for ctx in ['neutral','adult']})
    baselines={}
    for label,strategy in [('K1','always-issue'),('K2','always-clean')]:
        m=metrics([baseline(c['gold'],strategy) for c in cases for _ in range(3)])
        baselines[label]=dict(aggregate=m,thresholds_passed=qualifies(m))
    dominance=l5_dominators(models['L5']['aggregate'],{k:models[k]['aggregate'] for k in ['L1','L2','L3','L4']}) if {'L1','L2','L3','L4','L5'}<=models.keys() else None
    return dict(models=models,baselines=baselines,l5_dominators=dominance,provisional=True,
        controls_support_comparison=bool(dominance) and not any(v['thresholds_passed'] for v in baselines.values()),
        model_conclusion_allowed=False,
        note='Primary only; pending or secondary data cannot establish thresholds')


def final_primary_summary(records,cases,*,owner_review,panel,secondary):
    from .runner import digest
    if {r['config'] for r in records}!={'L1','L2','L3','L4','L5','L6','C1','C2'}:
        raise ValueError('Final report requires all eight participants')
    if (owner_review.get('completed') is not True or owner_review.get('panel_sha256')!=digest(panel)
            or owner_review.get('final_primary_sha256')!=digest(records)):
        raise ValueError('Exact completed owner panel and corrected primary records required')
    expected={tuple(s) for s in owner_review['secondary_candidate_slots']}
    actual={(s['case'],s['draw'],s['config']) for s in secondary if s.get('candidate_eligible')}
    if expected!=actual or len(actual)!=len(secondary):raise ValueError('Every secondary candidate must be retained')
    descriptive=secondary_metrics(secondary,require_owner=True)
    result=primary_summary(records,cases)
    result.update(provisional=False,model_conclusion_allowed=result['controls_support_comparison'],secondary=descriptive)
    return result


def metrics(records: list[dict]) -> dict:
    if any(r.get('measurement')=='secondary' for r in records):
        raise ValueError('secondary measurements cannot enter primary metrics')
    if not records or any(r.get('pending') or r.get('outcome') is None for r in records):
        raise ValueError('Missing or pending semantic adjudication')
    outcomes=Counter(r['outcome'] for r in records)
    clean=sum(r['gold_verdict']=='clean' for r in records)
    facts=sum(len(r['tp_ids'])+len(r['fn_ids']) for r in records)
    return dict(total=len(records),outcomes=dict(outcomes),clean_denominator=clean,issue_denominator=facts,
                fp=sum(r['outcome']=='FP' for r in records),miss=sum(len(r['fn_ids']) for r in records),
                valid=sum(r['valid'] for r in records))


def l5_dominators(baseline: dict,candidates: dict) -> list[str]:
    """29 Oct owner decision: Pareto comparison, no arbitrary composite score.

    Full 48x3 only. Incomparable/tied metrics mean no unequivocal L5 conclusion,
    not permission to suppress a row or invent a total rank.
    """
    if set(candidates)!={'L1','L2','L3','L4'}:raise ValueError('All four paired locals required')
    for row in [baseline,*candidates.values()]:
        if (row.get('total'),row.get('clean_denominator'),row.get('issue_denominator'))!=(144,60,84):
            raise ValueError('Full identical denominators required')
        if any(type(row.get(k)) is not int or not 0<=row[k]<=maximum
               for k,maximum in [('fp',60),('miss',84),('valid',144)]):raise ValueError('Invalid metric')
    return [label for label,row in sorted(candidates.items())
            if row['fp']<=baseline['fp'] and row['miss']<=baseline['miss'] and row['valid']>=baseline['valid']
            and (row['fp']<baseline['fp'] or row['miss']<baseline['miss'] or row['valid']>baseline['valid'])]


def secondary_metrics(records: list[dict],*,require_owner=False) -> dict:
    """Subset-only descriptive counts; deliberately no thresholds/L5 calculation."""
    if any(r.get('measurement')!='secondary' for r in records):raise ValueError('Expected secondary records only')
    rows=[r for r in records if r['candidate_eligible']]
    reviewed=[r for r in rows if r['owner_review'] in {'confirmed','corrected'}]
    if require_owner and len(reviewed)!=len(rows):raise ValueError('Every secondary candidate needs owner review')
    provisional=Counter(r['executor']['classification']['outcome'] for r in rows
                        if not r['executor']['classification']['pending'] and r['executor']['classification']['outcome']!='refusal')
    verified=Counter(r['owner']['classification']['outcome'] for r in reviewed if r['eligible'])
    report=dict(measurement='secondary',candidates=len(rows),reviewed=len(reviewed),pending_owner=len(rows)-len(reviewed),
                provisional_outcomes=dict(provisional),verified_outcomes=dict(verified),
                excluded=sum(not r['eligible'] for r in reviewed),
                provisional_excluded=sum(r['executor']['classification'].get('outcome')=='refusal' for r in rows))
    groups={
        'provisional':[r['executor']['classification'] for r in rows
                       if not r['executor']['classification']['pending'] and r['executor']['classification']['outcome']!='refusal'],
        'verified':[r['owner']['classification'] for r in reviewed if r['eligible']],
    }
    for prefix,items in groups.items():
        found=sum(len(r['tp_ids']) for r in items);missed=sum(len(r['fn_ids']) for r in items)
        report.update({prefix+'_found_facts':found,prefix+'_missed_facts':missed,
                       prefix+'_issue_fact_denominator':found+missed,
                       prefix+'_clean_denominator':sum(r['gold_verdict']=='clean' for r in items),
                       prefix+'_false_alarms':sum(r['outcome']=='FP' for r in items),
                       prefix+'_extra_findings':sum(r['extra_findings'] for r in items)})
    return report
