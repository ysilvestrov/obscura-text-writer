"""Offline, read-only replay of stored memory responses against the current validators.

Output is counters and violation codes only: never prose, model text, claim or character IDs."""
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

from .journal import CATEGORIES, decode_memory, load_memory, parse_memory_result
from .violations import MemoryViolations


def v2_as_v3(data: dict) -> dict:
    """Read a flat v2 answer as grouped v3. Update/retire lose category and scope; evidence_id is split into ids.
    Raises ValueError (no model data in the message) when the answer or an operation cannot be mapped."""
    result={'schema_version':3,**{c:{'add':[]} if c in {'facts','timeline'} else {'add':[],'update':[],'retire':[]} for c in CATEGORIES}}
    if not isinstance(data,dict) or not isinstance(data.get('operations'),list):raise ValueError('unmappable')
    for op in data['operations']:
        if not isinstance(op,dict) or op.get('category') not in CATEGORIES or not isinstance(op.get('action'),str):raise ValueError('unmappable')
        category=op['category'];action=op['action']
        raw=op.get('evidence_id')
        ids=[part for part in re.split(r'[,;\s]+',raw) if part] if isinstance(raw,str) else []
        item={'text':op.get('text'),'evidence_ids':ids}
        if action=='add':
            if category=='character_states':item['character_ids']=op.get('character_ids')
        else:item={'claim_id':op.get('claim_id'),**item}
        result[category].setdefault(action,[]).append(item)
    return result


_FENCE=re.compile(r"^(```|''')[ \t]*(?:json)?[ \t]*\r?\n(.*)\r?\n[ \t]*\1$",re.DOTALL|re.IGNORECASE)
_FENCE_LINE=re.compile(r"^[ \t]*(```|''')",re.MULTILINE)
_QUOTES='`'+"'"


def strip_wrapper(raw: str) -> tuple[str,bool]:
    """Strip exactly one complete outer fence/quote pair around a JSON object; anything else stays unchanged."""
    text=raw.strip();body=None
    match=_FENCE.match(text)
    if match and not _FENCE_LINE.search(match[2]):body=match[2]
    elif len(text)>=2 and text[0] in _QUOTES and text[-1]==text[0] and text[1]!=text[0] and text[1:-1].strip().startswith('{'):
        body=text[1:-1]
    if body is None:return raw,False
    body=body.strip()
    return (body,True) if body.startswith('{') and body.endswith('}') else (raw,False)


def _attempt(raw,previous,prose_id,prose,allowed,wire):
    try:
        parse_memory_result(raw,previous,prose_id,prose,'evidence_delta',allowed,wire_version=wire)
    except MemoryViolations as error:
        return 'fail',[v.code for v in error.violations]
    except Exception:
        # Never surface pydantic/json messages: they can quote model data.
        return 'fail',['other']
    return 'pass',[]


def replay_response(raw: str, fragments: dict, prose_id: str, prose: str) -> dict:
    wire=int(fragments.get('memory_wire_version','2'))
    previous=load_memory(fragments['previous_memory'])
    allowed=json.loads(fragments.get('memory_allowed_character_ids','[]'))
    raw,wrapped=strip_wrapper(raw)
    out={'wire':wire,'wrapped':wrapped,'as_is':None,'as_is_codes':[],'as_v3':None,'as_v3_codes':[]}
    try:data=decode_memory(raw)
    except Exception:
        out['as_is']='json'
        if wire==2:out['as_v3']='json'
        return out
    out['as_is'],out['as_is_codes']=_attempt(raw,previous,prose_id,prose,allowed,wire)
    if wire==2:
        try:translated=json.dumps(v2_as_v3(data))
        except ValueError:out['as_v3'],out['as_v3_codes']='fail',['unmappable']
        else:out['as_v3'],out['as_v3_codes']=_attempt(translated,previous,prose_id,prose,allowed,3)
    return out


SKIPS=('no_raw','no_prose','no_bounds','bad_context')


def summarize(rows: list[dict]) -> dict:
    wires=Counter();as_is=Counter();as_v3=Counter();is_codes=Counter();v3_codes=Counter();skipped=Counter();fixed=0;wrapped=0
    for row in rows:
        if 'skipped' in row:skipped[row['skipped']]+=1;continue
        wires[str(row['wire'])]+=1;wrapped+=bool(row.get('wrapped'));as_is[row['as_is']]+=1;is_codes.update(row['as_is_codes'])
        if row['as_v3'] is not None:
            as_v3[row['as_v3']]+=1;v3_codes.update(row['as_v3_codes'])
            if row['as_is']!='pass' and row['as_v3']=='pass':fixed+=1
    return {'replayed':sum(wires.values()),'attempts_by_wire':dict(wires),
            'as_is':{k:as_is.get(k,0) for k in ('pass','fail','json')},
            'as_v3':{k:as_v3.get(k,0) for k in ('pass','fail','json')},
            'as_is_codes':dict(is_codes),'as_v3_codes':dict(v3_codes),'fixed_by_v3':fixed,'wrapped':wrapped,
            'skipped':{k:skipped.get(k,0) for k in SKIPS}}


def _prose(connection,data,prose_id):
    row=connection.execute('SELECT payload FROM versions WHERE id=?',(prose_id,)).fetchone()
    if row is None:return None
    path=data/json.loads(row[0])['relative_path']
    if path.is_dir():path=path/f'{prose_id}.txt'
    return path.read_text(encoding='utf-8')


def _row(connection,data,payload):
    try:
        raw_path=data/payload['partial_path']
        raw=raw_path.read_text(encoding='utf-8') if raw_path.is_file() else ''
    except Exception:raw=''
    if not raw.strip():return {'skipped':'no_raw'}
    context=payload.get('context')
    fragments=context.get('fragments') if isinstance(context,dict) else None
    if not isinstance(fragments,dict):return {'skipped':'bad_context'}
    try:bounds=json.loads(fragments.get('expected_source_prose_ids') or '[]')
    except Exception:return {'skipped':'bad_context'}
    if not isinstance(bounds,list) or not bounds or not isinstance(bounds[-1],str):return {'skipped':'no_bounds'}
    try:prose=_prose(connection,data,bounds[-1])
    except Exception:prose=None
    if prose is None:return {'skipped':'no_prose'}
    try:return replay_response(raw,fragments,bounds[-1],prose)
    except Exception:return {'skipped':'bad_context'}


def collect(db: Path, data: Path, story: str | None = None) -> list[dict]:
    rows=[]
    connection=sqlite3.connect(f'file:{Path(db).as_posix()}?mode=ro',uri=True)
    try:
        for (text,) in connection.execute("SELECT payload FROM stage_attempts WHERE state IN ('completed','failed')").fetchall():
            try:payload=json.loads(text)
            except Exception:continue
            if not isinstance(payload,dict):continue
            if payload.get('stage')!='memory' or (story is not None and payload.get('story_id')!=story):continue
            context=payload.get('context');settings=context.get('settings') if isinstance(context,dict) else None
            if not isinstance(settings,dict):rows.append({'skipped':'bad_context'});continue
            if settings.get('memory_mode')!='evidence_delta':continue
            rows.append(_row(connection,Path(data),payload))
    finally:connection.close()
    return rows
