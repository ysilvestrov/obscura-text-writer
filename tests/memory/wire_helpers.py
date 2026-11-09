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
