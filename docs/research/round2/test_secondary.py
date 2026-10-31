"""Secondary content judgements never replace primary invalid or thresholds."""
import copy

import pytest

from .test_round2 import prepared,raw,concern,case
from .test_validation import check


def candidate():
    req=prepared();return check(raw([concern(req)],complete=False),req)


def judgement(matches=None,refusal=False):
    return dict(content_refusal=refusal,matches={'0':['g0']} if matches is None else matches,question_ok=False)


def test_secondary_tp_is_provisional_and_primary_stays_invalid():
    from .scoring import classify_secondary,classify_call
    response=candidate();before=copy.deepcopy(response)
    result=classify_secondary(response,case()['gold'],judgement())
    assert result['measurement']=='secondary' and result['candidate_eligible']
    assert result['primary_status']=='invalid' and result['owner_review']=='pending'
    assert result['executor']['actor']=='executor' and result['executor']['classification']['outcome']=='TP'
    assert result['executor']['classification']['valid'] is False
    assert classify_call(response,case()['gold'],judgement())['outcome']=='invalid'
    assert response==before


def test_all_secondary_candidates_need_owner_review_including_executor_fn():
    from .scoring import classify_secondary
    from .report import secondary_metrics
    row=classify_secondary(candidate(),case()['gold'],judgement(matches={}))
    preview=secondary_metrics([row])
    assert preview['candidates']==1 and preview['pending_owner']==1
    assert preview['provisional_outcomes']=={'FN':1}
    with pytest.raises(ValueError,match='owner'):secondary_metrics([row],require_owner=True)


def test_owner_can_confirm_or_correct_with_both_records_retained():
    from .scoring import classify_secondary
    from .report import secondary_metrics
    response=candidate()
    confirmed=classify_secondary(response,case()['gold'],judgement(),judgement())
    assert confirmed['owner_review']=='confirmed'
    corrected=classify_secondary(response,case()['gold'],judgement(),judgement(matches={}))
    assert corrected['owner_review']=='corrected'
    assert corrected['executor']['classification']['outcome']=='TP'
    assert corrected['owner']['classification']['outcome']=='FN'
    report=secondary_metrics([confirmed,corrected],require_owner=True)
    assert report['verified_outcomes']=={'TP':1,'FN':1} and report['pending_owner']==0
    assert 'threshold' not in str(report)


def test_secondary_never_enters_primary_metrics():
    from .scoring import classify_secondary
    from .report import metrics
    row=classify_secondary(candidate(),case()['gold'],judgement(),judgement())
    with pytest.raises(ValueError,match='secondary'):metrics([row['owner']['classification']])


def test_refusal_discovered_in_candidate_is_excluded_but_still_reviewed():
    from .scoring import classify_secondary
    from .report import secondary_metrics
    row=classify_secondary(candidate(),case()['gold'],judgement(refusal=True))
    assert not row['eligible'] and row['candidate_eligible'] and row['excluded_reason']=='content_refusal'
    with pytest.raises(ValueError,match='owner'):secondary_metrics([row],require_owner=True)
    verified=classify_secondary(candidate(),case()['gold'],judgement(refusal=True),judgement(refusal=True))
    report=secondary_metrics([verified],require_owner=True)
    assert report['excluded']==1 and report['verified_outcomes']=={}


def test_missing_executor_or_owner_mapping_remains_pending():
    from .scoring import classify_secondary
    from .report import secondary_metrics
    row=classify_secondary(candidate(),case()['gold'],None)
    assert row['executor']['classification']['pending']
    with pytest.raises(ValueError):secondary_metrics([row],require_owner=True)


def test_non_candidate_and_forged_candidate_fail_closed():
    from .scoring import classify_secondary
    assert not classify_secondary(check(raw()),case('clean')['gold'],None)['candidate_eligible']
    altered=candidate();altered['secondary_candidate']['complete']=True
    with pytest.raises(ValueError):classify_secondary(altered,case()['gold'],judgement())
    altered=candidate();altered['contract_defects']=['schema_invalid']
    with pytest.raises(ValueError):classify_secondary(altered,case()['gold'],judgement())


def test_secondary_keeps_partial_E_fact_misses_separate():
    from .scoring import classify_secondary
    from .report import secondary_metrics
    row=classify_secondary(candidate(),case(count=2)['gold'],judgement(),judgement())
    result=secondary_metrics([row],require_owner=True)
    assert result['verified_outcomes']=={'TP':1}
    assert result['verified_found_facts']==1 and result['verified_missed_facts']==1
    assert result['verified_issue_fact_denominator']==2
