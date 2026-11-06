"""Fail closed on incomplete coverage or invented evidence; no fuzzy matching."""
from ..model_json import unwrap_model_json
from .models import DeltaReport,CheckReport


def evidence_sources(target):
    return {c.id+':'+side:getattr(c,side+'_text') for c in target.changes for side in ['old','new']}


def _coverage(actual,expected):
    if len(actual)!=len(set(actual)) or set(actual)!=set(expected):
        raise ValueError('Перевірка впливу не охопила всі змінені передумови')


def _evidence(items,target):
    sources=evidence_sources(target)
    for item in items:
        for evidence in item.evidence:
            if evidence.source_id not in sources or evidence.quote not in sources[evidence.source_id]:
                raise ValueError('Неточна або невідома цитата перевірки впливу')
            if evidence.source_id.rsplit(':',1)[0] not in item.change_ids:
                raise ValueError('Цитата не належить указаній зміні')


def validate_delta(payload,target):
    result=DeltaReport.model_validate(payload)
    changed={c.id for c in target.changes if c.changed}
    _coverage(result.covered_change_ids,changed)
    for item in result.items:
        if not set(item.change_ids)<=changed or len(item.change_ids)!=len(set(item.change_ids)):
            raise ValueError('Дельта посилається на невідому зміну')
        if not item.evidence:raise ValueError('Дельта потребує дослівних цитат')
    _evidence(result.items,target)
    return result


def validate_check(payload,target):
    result=CheckReport.model_validate(payload)
    if len(result.materials)!=1 or result.materials[0].version_id!=target.version_id:
        raise ValueError('Перевірено не той матеріал')
    if result.memory_semantic_impact!='unchecked' and not target.memory_text:raise ValueError('Немає перевірюваного журналу пам’яті')
    material=result.materials[0];changed={c.id for c in target.changes if c.changed}
    _coverage(material.covered_change_ids,changed)
    for finding in material.findings:
        if finding.target_quote not in target.text:raise ValueError('Неточна цитата цільового тексту')
        if not set(finding.change_ids)<=changed:raise ValueError('Невідома зміна у висновку')
    _evidence(material.findings,target)
    return result


def validate_memory_input(context,target,result):
    if result.memory_semantic_impact=='unchecked':return
    import json
    if context.get('fragments',{}).get('impact_memory_included')!='true':raise ValueError('Пам’ять не була передана для перевірки')
    own=json.loads(context.get('user_text','{}')).get('own_memory',{})
    if (not target.memory_text or target.memory_evidence_status not in {'current','historical'}
        or own.get('version_id')!=target.memory_id or own.get('journal')!=json.loads(target.memory_text)):
        raise ValueError('Звіт пам’яті має інший або неповний журнал')


def decode_response(raw):
    import json
    def pairs(values):
        result={}
        for key,value in values:
            if key in result:raise ValueError('Відповідь перевірки має дубльовані поля JSON')
            result[key]=value
        return result
    def invalid(value):raise ValueError('Відповідь перевірки містить нечислову JSON-константу')
    try:return json.loads(unwrap_model_json(raw),object_pairs_hook=pairs,parse_constant=invalid)
    except (json.JSONDecodeError,RecursionError):raise ValueError('Відповідь перевірки не є коректним JSON') from None


def refusal_body(text):
    """Inspect only a failed model response, never author inputs or valid reports."""
    from ..publication_suggestions import text_refusal
    detected=text_refusal(text)
    if detected:return detected
    try:
        data=decode_response(text)
        reason=data.get('refusal') if isinstance(data,dict) else None
        if isinstance(reason,str) and reason.strip():
            from ..evaluation.failures import refusal_detail
            detail=refusal_detail(reason).model_dump(mode='json')
            detail['message']=detail['message'].replace('Оцінювач','Планувальник')
            return detail
    except ValueError:pass
    return None
