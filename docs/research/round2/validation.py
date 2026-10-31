"""Strict research validation with fail-closed, read-only secondary eligibility.

The diagnostic shadow is never a primary accepted response. Original schema and
wire budget are checked BEFORE touching any shadow field. Product code is reused,
not weakened, and raw model replies are retained byte-for-byte by the caller.
"""
from copy import deepcopy
import json

from storygen.review.wire import compact,validate_part
from storygen.review.wire_models import CheckResponse


CONTRACT_DEFECTS=('incomplete_processing','duplicate_source_reference')
SECONDARY_EXCLUSION_CODES=('duplicate_change_reference',)
REJECTION_CODES=(
    'provider_refusal','output_length','unfinished_response','empty_response','invalid_json','schema_invalid',
    'incomplete_processing','response_budget_exceeded','concerns_limit','duplicate_carry_reference',
    'unknown_reference','wrong_reference_kind','duplicate_source_reference','duplicate_target_reference',
    'missing_evidence','unknown_change_reference','validator_rejected','malformed_provider_envelope',
    'transport_error','provider_http_error',
)


def diagnose(raw,request):
    try:CheckResponse.model_validate(raw,strict=True)
    except (ValueError,TypeError):
        return dict(codes=['schema_invalid'],secondary_eligible=False,contract_defects=[])
    codes=[];exclusions=[]
    def add(code):
        if code not in codes:codes.append(code)
    if raw['complete'] is False:add('incomplete_processing')
    if compact(raw)>request['plan']['result_cap']:add('response_budget_exceeded')
    maximum=request['body']['response_format']['json_schema']['schema']['properties']['concerns']['maxItems']
    if len(raw['concerns'])>maximum:add('concerns_limit')
    evidence=request['payload']['evidence']
    changes={r['change'] for r in evidence.values() if r['kind']=='source'}
    def refs(values,kind,duplicate_code):
        if len(values)!=len(set(values)):add(duplicate_code)
        for ref in values:
            if ref not in evidence:add('unknown_reference')
            elif kind and evidence[ref]['kind']!=kind:add('wrong_reference_kind')
    refs(raw['carry_refs'],None,'duplicate_carry_reference')
    for item in raw['concerns']:
        refs(item['source_refs'],'source','duplicate_source_reference')
        refs(item['target_refs'],'target','duplicate_target_reference')
        if item['kind']=='issue' and (not item['source_refs'] or not item['target_refs']):add('missing_evidence')
        if any(ref not in changes for ref in item['change_refs']):add('unknown_change_reference')
        # The product accepts repeated change_refs; preserve that primary rule.
        # Owner limited the secondary exception to source_refs: report any other
        # duplicate as a secondary exclusion, not a fabricated primary cause.
        if len(item['change_refs'])!=len(set(item['change_refs'])):
            if 'duplicate_change_reference' not in exclusions:exclusions.append('duplicate_change_reference')
    eligible=False
    if codes and set(codes)<=set(CONTRACT_DEFECTS) and not exclusions:
        shadow=deepcopy(raw);shadow['complete']=True
        for item in shadow['concerns']:
            item['source_refs']=list(dict.fromkeys(item['source_refs']))
        try:
            CheckResponse.model_validate(shadow,strict=True)
            validate_part(shadow,request['plan'],request['spec'],{})
        except (ValueError,TypeError,KeyError):
            add('validator_rejected')
        else:eligible=True
    if not codes:add('validator_rejected')
    return dict(codes=codes,secondary_eligible=eligible,secondary_exclusion_codes=exclusions,
                contract_defects=[c for c in codes if c in CONTRACT_DEFECTS] if eligible else [])


def assess_response(response,request):
    result=dict(response)
    for key in ('status','parsed','result','secondary_candidate','rejection_codes','secondary_eligible',
                'contract_defects','error','secondary_exclusion_codes'):
        result.pop(key,None)
    result.update(rejection_codes=[],secondary_eligible=False,contract_defects=[],secondary_exclusion_codes=[])
    def reject(code,error,status='invalid'):
        return dict(result,status=status,error=error,rejection_codes=[code])
    if response.get('refusal'):return reject('provider_refusal','Provider refusal','refusal')
    if response.get('finish_reason')!='stop':
        code='output_length' if response.get('finish_reason')=='length' else 'unfinished_response'
        return reject(code,'Unfinished response')
    text=response.get('text')
    if not text:return reject('empty_response','Empty response')
    try:parsed=json.loads(text)
    except (ValueError,TypeError):return reject('invalid_json','Invalid JSON')
    try:CheckResponse.model_validate(parsed,strict=True)
    except (ValueError,TypeError):return reject('schema_invalid','Schema validation failed')
    try:
        schema=request['body']['response_format']['json_schema']['schema']
        if len(parsed['concerns'])>schema['properties']['concerns']['maxItems']:raise ValueError('Too many concerns')
        normalized=validate_part(parsed,request['plan'],request['spec'],{})
    except (ValueError,TypeError,KeyError):
        diagnostic=diagnose(parsed,request)
        rejected=dict(result,status='invalid',error='Parse/schema/refs/complete/budget validation failed',
                      rejection_codes=diagnostic['codes'],secondary_eligible=diagnostic['secondary_eligible'],
                      contract_defects=diagnostic['contract_defects'],
                      secondary_exclusion_codes=diagnostic.get('secondary_exclusion_codes',[]))
        if diagnostic['secondary_eligible']:rejected['secondary_candidate']=deepcopy(parsed)
        return rejected
    return dict(result,status='valid',parsed=parsed,result=normalized)
