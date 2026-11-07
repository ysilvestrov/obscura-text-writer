"""Independent memory-wire violations: operation label + code only, never model values."""
from collections import Counter
from typing import Callable, NamedTuple

from pydantic import ValidationError

MAX_ITEMS=50
MUTABLE=('character_states','open_threads')


class Violation(NamedTuple):
    operation: str
    code: str


CODES={
    'schema':'Порушено схему операції пам’яті',
    'wire_version':'Відповідь має іншу версію протоколу пам’яті, ніж очікує промпт',
    'evidence_unknown':'Невідомий фрагмент підтвердження пам’яті (evidence_id)',
    'evidence_count':'Кількість доказів поза межами 1–3 або повтор evidence_ids',
    'add_limit':'Перевищено ліміт: до трьох add на категорію',
    'ops_limit':'Перевищено ліміт: до 12 операцій за відповідь',
    'target_unknown':'Update/retire посилається на невідомий, закритий або незмінний claim',
    'target_meta':'Update/retire змінює категорію або scope чинного claim',
    'target_twice':'Один claim змінено кілька разів за відповідь',
    'scope_unknown':'Невідомий scope персонажа: character_ids містить персонажа поза дозволеним списком сцени',
}


def _label(operation):
    if operation=='$':return 'Відповідь'
    if operation.startswith('operations[') and operation.endswith(']') and operation[11:-1].isdigit():
        return f'Операція {int(operation[11:-1])+1}'
    head,dot,tail=operation.partition('.')
    if dot and head in {'facts','character_states','open_threads','timeline'}:
        action,bracket,index=tail.partition('[')
        if action in {'add','update','retire'}:
            if not bracket:return operation
            if index.endswith(']') and index[:-1].isdigit():return f'{head}.{action}, елемент {int(index[:-1])+1}'
    return operation


def _plural(count):
    if 11<=count%100<=14 or count%10 in {0,5,6,7,8,9}:return 'порушень'
    return 'порушення'


class MemoryViolations(ValueError):
    def __init__(self,violations):
        self.violations=list(violations)
        super().__init__(self.message())

    def payload(self):
        return {'items':[{'operation':v.operation,'code':v.code} for v in self.violations[:MAX_ITEMS]],
                'total':len(self.violations)}

    def message(self):
        count=len(self.violations)
        shown='; '.join(f'{_label(v.operation)}: {CODES.get(v.code,CODES["schema"])}' for v in self.violations[:3])
        return f'{count} {_plural(count)}: {shown}'

    def __str__(self):
        return self.message()


def pydantic_violations(exc: ValidationError,label: Callable[[tuple],str]) -> list[Violation]:
    result=[]
    for error in exc.errors(include_input=False,include_url=False):
        item=Violation(label(tuple(error['loc'])),'schema')
        if item not in result:result.append(item)
    return result


def check_v2(data,previous,fragment_ids,allowed_character_ids) -> list[Violation]:
    from .journal import MemoryOperation,replay_memory
    if (not isinstance(data,dict) or data.get('schema_version')!=2 or not isinstance(data.get('operations'),list)
            or set(data)-{'schema_version','operations'}):
        return [Violation('$','schema')]
    operations=data['operations'];result=[]
    active=replay_memory(previous);allowed=set(allowed_character_ids)
    for index,raw in enumerate(operations):
        label=f'operations[{index}]'
        try:op=MemoryOperation.model_validate(raw)
        except ValidationError as exc:
            result.extend(pydantic_violations(exc,lambda _loc,label=label:label));continue
        if op.evidence_id not in fragment_ids:result.append(Violation(label,'evidence_unknown'))
        if op.action=='add':
            if not set(op.character_ids)<=allowed:result.append(Violation(label,'scope_unknown'))
            continue
        claim=active.get(op.claim_id)
        if claim is None or claim.category not in MUTABLE:result.append(Violation(label,'target_unknown'))
        elif claim.category!=op.category or claim.character_ids!=op.character_ids:result.append(Violation(label,'target_meta'))
    rows=[op for op in operations if isinstance(op,dict)]
    if len(operations)>12:result.append(Violation('$','ops_limit'))
    adds=Counter(op.get('category') for op in rows if op.get('action')=='add' and isinstance(op.get('category'),str))
    if any(count>3 for count in adds.values()):result.append(Violation('$','add_limit'))
    targets=Counter(op['claim_id'] for op in rows if op.get('action') in {'update','retire'} and isinstance(op.get('claim_id'),str))
    if any(count>1 for count in targets.values()):result.append(Violation('$','target_twice'))
    return result
