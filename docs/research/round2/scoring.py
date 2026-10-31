"""Separate machine validity, human semantic mapping, and fact-level recall."""
from copy import deepcopy
import json

from .validation import assess_response


def validate_response(response: dict, request: dict) -> dict:
    return assess_response(response,request)


def classify_call(response: dict, gold: dict, adjudication: dict | None) -> dict:
    expected={item['id'] for item in gold['contradictions']}
    base=dict(pending=False,outcome=None,gold_verdict=gold['verdict'],tp_ids=[],fn_ids=sorted(expected),
              extra_findings=0,duplicate_findings=0,questions=0,extra_questions=0,valid=response['status']=='valid')
    status=response['status']
    if status=='invalid' and adjudication is not None and adjudication.get('content_refusal') is True:
        # A prose refusal may fail JSON parsing. Human classification takes
        # precedence without repairing/retrying the model's actual answer.
        return dict(base,outcome='refusal',valid=False)
    if status in {'invalid','refusal','transport'}:return dict(base,outcome=status)
    if status!='valid':raise ValueError('Unknown response status')
    rows=response['parsed']['concerns']
    if adjudication is None:return dict(base,pending=True)
    if type(adjudication.get('content_refusal')) is not bool or type(adjudication.get('question_ok')) is not bool:
        raise ValueError('Explicit human refusal/question judgement required')
    if adjudication['content_refusal']:return dict(base,outcome='refusal',valid=False)
    question_indices={str(i) for i,row in enumerate(rows) if row['kind']=='question'}
    question_judgements=adjudication.get('question_judgements',{})
    # A single expected question can use the explicit question_ok label. Extra
    # questions need individual human decisions; neither ignore nor auto-reject.
    if gold['verdict']=='question' and len(question_indices)==1 and not question_judgements:
        question_judgements={next(iter(question_indices)):adjudication['question_ok']}
    if not isinstance(question_judgements,dict) or any(k not in question_indices or type(v) is not bool for k,v in question_judgements.items()):
        raise ValueError('Invalid question adjudication')
    if set(question_judgements)!=question_indices:return dict(base,pending=True,questions=len(question_indices))
    extra_questions=sum(not accepted for accepted in question_judgements.values())
    mapping=adjudication['matches'];found=set();duplicates=0;extras=0
    if not isinstance(mapping,dict):raise ValueError('Invalid adjudication mapping')
    for index,values in mapping.items():
        if index not in {str(i) for i in range(len(rows))} or rows[int(index)]['kind']!='issue':raise ValueError('Unknown finding')
        if not isinstance(values,list) or not values or any(v not in expected for v in values) or len(set(values))!=len(values):raise ValueError('Unknown/duplicate gold ID')
    for i,row in enumerate(rows):
        if row['kind']=='issue':
            matched=set(mapping.get(str(i),[]))
            if not matched:extras+=1
            duplicates+=len(matched & found);found|=matched
    if gold['verdict']=='clean':outcome='FP' if rows else 'TN'
    elif gold['verdict']=='issue':outcome='TP' if found else 'FN'
    else:
        outcome='question-ok' if adjudication['question_ok'] and any(r['kind']=='question' for r in rows) and not any(r['kind']=='issue' for r in rows) else 'question-missed'
    return dict(base,outcome=outcome,tp_ids=sorted(found),fn_ids=sorted(expected-found),extra_findings=extras+extra_questions,
                duplicate_findings=duplicates,questions=len(question_indices),extra_questions=extra_questions)


def baseline(gold: dict, strategy: str) -> dict:
    if strategy not in {'always-issue','always-clean'}:raise ValueError('Unknown baseline')
    issue=strategy=='always-issue';verdict=gold['verdict'];ids=[r['id'] for r in gold['contradictions']]
    return dict(pending=False,gold_verdict=verdict,valid=True,outcome=('TP' if issue else 'FN') if verdict=='issue' else ('FP' if issue else 'TN') if verdict=='clean' else 'question-missed',
                tp_ids=ids if issue else [],fn_ids=[] if issue else ids,extra_findings=0,duplicate_findings=0)


def classify_secondary(response: dict,gold: dict,executor_adjudication,owner_adjudication=None) -> dict:
    """Separate descriptive assessment, never an accepted/normalized response.

    Executor labels are provisional. Owner sees every original eligible candidate,
    including executor FN/FP/refusal labels, and may correct them. The temporary
    status view below invokes the same semantic rules, not the primary validator.
    It is never persisted over the original invalid reply or used for thresholds.
    """
    from .validation import CONTRACT_DEFECTS
    base=dict(measurement='secondary',primary_status=response['status'],candidate_eligible=False,
              eligible=False,executor=None,owner=None,owner_review='not_required',excluded_reason=None)
    if response['status']!='invalid' or not response.get('secondary_eligible'):return base
    defects=response.get('contract_defects')
    candidate=response.get('secondary_candidate')
    if (not defects or not set(defects)<=set(CONTRACT_DEFECTS) or not isinstance(candidate,dict)
            or candidate!=json.loads(response.get('text') or 'null')):
        raise ValueError('Invalid secondary eligibility evidence')
    def assess(actor,adjudication):
        view=dict(status='valid',parsed=deepcopy(candidate))
        result=classify_call(view,gold,adjudication)
        result.update(valid=False,measurement='secondary',primary_status='invalid')
        return dict(actor=actor,adjudication=deepcopy(adjudication),classification=result)
    executor=assess('executor',executor_adjudication)
    owner=assess('owner',owner_adjudication) if owner_adjudication is not None else None
    ready=owner is not None and not executor['classification']['pending'] and not owner['classification']['pending']
    selected=owner['classification'] if ready else executor['classification']
    review=('confirmed' if executor['classification']==owner['classification'] else 'corrected') if ready else 'pending'
    refusal=selected.get('outcome')=='refusal'
    return dict(base,candidate_eligible=True,eligible=not refusal,contract_defects=list(defects),
                executor=executor,owner=owner,owner_review=review,
                excluded_reason='content_refusal' if refusal else None)
