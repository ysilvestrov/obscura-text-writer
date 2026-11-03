"""Reason codes must expose hidden errors without relaxing the primary result."""
import copy
import json

import pytest

from .test_round2 import prepared,raw,concern


def check(value,request=None,**kwargs):
    from .scoring import validate_response
    return validate_response(dict(text=json.dumps(value,ensure_ascii=False),finish_reason='stop',**kwargs),request or prepared())


def test_valid_reply_has_no_rejection_or_secondary_candidate():
    result=check(raw())
    assert result['status']=='valid' and result['rejection_codes']==[]
    assert result['secondary_eligible'] is False


def test_incomplete_only_secondary_preserves_primary_and_original():
    req=prepared();value=raw([concern(req)],complete=False);before=copy.deepcopy(value)
    result=check(value,req)
    assert result['status']=='invalid' and result['rejection_codes']==['incomplete_processing']
    assert result['secondary_eligible'] and result['contract_defects']==['incomplete_processing']
    assert result['secondary_candidate']==value and result['secondary_candidate']['complete'] is False
    assert 'result' not in result and 'parsed' not in result and value==before
    assert json.loads(result['text'])==before


@pytest.mark.parametrize('complete',[True,False])
def test_allowed_source_duplicate_and_combination(complete):
    req=prepared();item=concern(req);item['source_refs']*=2
    result=check(raw([item],complete=complete),req)
    assert result['status']=='invalid' and result['secondary_eligible']
    assert 'duplicate_source_reference' in result['rejection_codes']
    assert result['secondary_candidate']['concerns'][0]['source_refs']==item['source_refs']


@pytest.mark.parametrize('field,values,code',[
    ('source_refs',['S999'],'unknown_reference'),
    ('source_refs',['T2'],'wrong_reference_kind'),
    ('source_refs',[],'missing_evidence'),
    ('target_refs',[],'missing_evidence'),
    ('target_refs',['T2','T2'],'duplicate_target_reference'),
    ('change_refs',['C999'],'unknown_change_reference'),
])
def test_other_error_is_not_hidden_by_complete_false(field,values,code):
    req=prepared();item=concern(req);item[field]=values
    result=check(raw([item],complete=False),req)
    assert result['status']=='invalid' and not result['secondary_eligible']
    assert {'incomplete_processing',code}<=set(result['rejection_codes'])


def test_duplicate_unknown_source_is_not_eligible():
    req=prepared();item=concern(req);item['source_refs']=['S999','S999']
    result=check(raw([item]),req)
    assert not result['secondary_eligible'] and 'unknown_reference' in result['rejection_codes']


def test_duplicate_carry_source_is_excluded():
    req=prepared();value=raw(complete=False);value['carry_refs']=['S1','S1']
    result=check(value,req)
    assert not result['secondary_eligible'] and 'duplicate_carry_reference' in result['rejection_codes']


def test_original_schema_limit_cannot_be_laundered_by_deduplication():
    req=prepared();item=concern(req);item['source_refs']*=4
    result=check(raw([item]),req)
    assert not result['secondary_eligible'] and result['rejection_codes']==['schema_invalid']


def test_original_budget_cannot_be_laundered_by_deduplication():
    from storygen.review.wire import compact
    req=prepared();item=concern(req);item['source_refs']*=3;value=raw([item],complete=False)
    req['plan']['result_cap']=compact(value)-1
    result=check(value,req)
    assert not result['secondary_eligible'] and 'response_budget_exceeded' in result['rejection_codes']


def test_dynamic_concern_limit_excludes_secondary():
    req=prepared();value=raw([concern(req) for _ in range(4)],complete=False)
    result=check(value,req)
    assert not result['secondary_eligible'] and 'concerns_limit' in result['rejection_codes']


@pytest.mark.parametrize('response,code',[
    ({'text':'{}','finish_reason':'length'},'output_length'),
    ({'text':'{}','finish_reason':None},'unfinished_response'),
    ({'text':'','finish_reason':'stop'},'empty_response'),
    ({'text':'not json','finish_reason':'stop'},'invalid_json'),
    ({'text':'[]','finish_reason':'stop'},'schema_invalid'),
    ({'text':'{}','finish_reason':'stop','refusal':True},'provider_refusal'),
    ({'text':'{"complete":"false","concerns":[],"carry_refs":[]}','finish_reason':'stop'},'schema_invalid'),
])
def test_all_early_rejections_have_code_and_no_secondary(response,code):
    from .scoring import validate_response
    result=validate_response(response,prepared())
    assert result['rejection_codes']==[code] and not result['secondary_eligible']


def test_unknown_validator_failure_fails_closed(monkeypatch):
    from . import validation
    req=prepared()
    def unexpected(*args):raise ValueError('new rule')
    monkeypatch.setattr(validation,'validate_part',unexpected)
    result=check(raw(complete=False),req)
    assert not result['secondary_eligible'] and 'validator_rejected' in result['rejection_codes']


def test_old_accepted_result_cannot_leak_into_revalidated_invalid_reply():
    from .scoring import validate_response
    req=prepared();old=check(raw(),req)
    old['text']=json.dumps(raw(complete=False))
    result=validate_response(old,req)
    assert result['status']=='invalid' and 'result' not in result and 'parsed' not in result


def test_duplicate_change_is_not_a_secondary_exception_or_new_primary_rule():
    req=prepared();item=concern(req);item['change_refs']=['C1','C1']
    assert check(raw([item]),req)['status']=='valid'  # Existing product semantics preserved.
    result=check(raw([item],complete=False),req)
    assert not result['secondary_eligible']
    assert result['rejection_codes']==['incomplete_processing']
    assert result['secondary_exclusion_codes']==['duplicate_change_reference']


def test_reason_and_exception_registries_are_explicit_before_freeze():
    from .validation import REJECTION_CODES,CONTRACT_DEFECTS,SECONDARY_EXCLUSION_CODES
    assert len(REJECTION_CODES)==len(set(REJECTION_CODES))
    assert set(CONTRACT_DEFECTS)=={'incomplete_processing','duplicate_source_reference'}
    assert set(CONTRACT_DEFECTS)<=set(REJECTION_CODES)
    assert SECONDARY_EXCLUSION_CODES==('duplicate_change_reference',)
    assert {'invalid_json','schema_invalid','missing_evidence','provider_http_error','transport_error'}<=set(REJECTION_CODES)
