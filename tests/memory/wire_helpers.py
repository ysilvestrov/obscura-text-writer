"""Shared fake model responses for memory wire v3 (standard prompt contract)."""
import json

GROUPS={'facts':('add',),'timeline':('add',),
    'character_states':('add','update','retire'),'open_threads':('add','update','retire')}


def v3_response(**groups) -> str:
    """Build a v3 answer; keyword `<category>_<action>` takes a list of wire items, absent groups stay empty."""
    data={'schema_version':3}
    for category,actions in GROUPS.items():
        data[category]={action:list(groups.pop(f'{category}_{action}',())) for action in actions}
    if groups:raise TypeError(f'Невідомі групи: {sorted(groups)}')
    return json.dumps(data,ensure_ascii=False)


V4_GROUPS={'facts':('add',),'timeline':('add',),'character_states':('add','update','retire'),'open_threads':('add',)}


def v4_response(core=None,threads=None,**groups) -> str:
    """Build a v4 answer: `core`/`threads` decisions as given (default empty), groups as in v3_response."""
    data={'schema_version':4,'core':dict(core or {}),'threads':dict(threads or {})}
    for category,actions in V4_GROUPS.items():
        data[category]={action:list(groups.pop(f'{category}_{action}',())) for action in actions}
    if groups:raise TypeError(f'Невідомі групи: {sorted(groups)}')
    return json.dumps(data,ensure_ascii=False)


def core_unchanged(*character_ids) -> dict:
    """Core decisions answering `unchanged` for every registry slot of each tracked character."""
    from storygen.memory.core import SLOTS
    return {cid:{s.name:{'status':'unchanged','text':'','evidence_ids':[],'reason':''} for s in SLOTS} for cid in character_ids}


def threads_open(*claim_ids) -> dict:
    """Thread decisions keeping every listed active thread open."""
    return {claim_id:{'status':'open','resolution':'','evidence_ids':[]} for claim_id in claim_ids}


def v4_answer(context, **groups) -> str:
    """v4 answer for a captured memory context: `unchanged` core and `open` threads from its bounds, groups as given."""
    bounds=json.loads(context.fragments['memory_schema_bounds'])
    return v4_response(core_unchanged(*bounds['tracked']),threads_open(*bounds['threads']),**groups)
