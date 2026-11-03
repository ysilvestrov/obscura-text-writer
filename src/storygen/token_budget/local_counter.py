"""Offline, narrowly admitted chat-template token counting. Never calls a provider."""
import json
from .core import digest

REVISION=1
SAFETY=512


class CounterUnavailable(ValueError):
    pass


def admitted(body,profile):
    allowed={'model','messages','reasoning_effort','response_format','max_tokens','temperature','stream','stream_options'}
    if not isinstance(body,dict) or not isinstance(profile,dict):return False
    messages=body.get('messages',[]);fmt=body.get('response_format',{})
    if not isinstance(messages,list) or not all(isinstance(m,dict) for m in messages) or not isinstance(fmt,dict) or not isinstance(fmt.get('json_schema'),dict):return False
    return (not set(body)-allowed and body.get('model')==profile['model'] and body.get('reasoning_effort')=='none'
        and len(messages)==2 and [m.get('role') for m in messages]==['system','user']
        and all(set(m)=={'role','content'} and isinstance(m.get('content'),str) for m in messages)
        and fmt.get('type')=='json_schema' and fmt.get('json_schema',{}).get('name')=='impact_part'
        and fmt.get('json_schema',{}).get('strict') is True
        and digest(messages[0]['content'])==profile['system_sha256'])


def count_known(body,counter):
    profile,tokenizer,template=counter
    if not admitted(body,profile):raise CounterUnavailable('local_counter_scope_mismatch')
    try:
        prompt=template.render(messages=body['messages'],add_generation_prompt=True,enable_thinking=False)
        return len(tokenizer.encode(prompt,add_special_tokens=False).ids)
    except Exception as exc:raise CounterUnavailable('local_counter_render_failed') from exc


def predict_body(body,counter):
    if not admitted(body,counter[0]):raise CounterUnavailable('local_counter_scope_mismatch')
    try:data=json.loads(body['messages'][1]['content'])
    except (ValueError,TypeError):raise CounterUnavailable('local_counter_input_not_json')
    if not isinstance(data,dict) or not isinstance(data.get('results',{}),dict):raise CounterUnavailable('local_counter_input_not_object')
    reserve=0
    # Only planner-owned placeholders use this branch. They are never sent to inference.
    for child in data.get('results',{}).values():
        if not isinstance(child,dict):raise CounterUnavailable('local_counter_invalid_child')
        if 'reserved_result' in child:
            cap=data.get('response_character_limit')
            if type(cap) is not int or not 256<=cap<=6000:raise CounterUnavailable('local_counter_invalid_reserve')
            reserve+=4*cap+1024
            child.clear()
    data.pop('reserved_reference_overhead',None)
    messages=[body['messages'][0],dict(body['messages'][1],content=json.dumps(data,ensure_ascii=False,separators=(',',':')))]
    known_body={**body,'messages':messages} if reserve else body
    return dict(input_tokens=count_known(known_body,counter)+SAFETY+reserve,
        method='qualified_local_tokenizer',confidence='qualified_local',profile_id=counter[0]['id'],reasons=[],reserved_unknown_tokens=reserve)
