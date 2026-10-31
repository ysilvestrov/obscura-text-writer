"""Immutable wire contract shared by runtime and offline proof validation."""
import json
from ..providers.requests import generation_request


def request_for(manifest,payload):
    prompt=manifest.prompt_text
    fragments={}
    if manifest.wire_schema_version==2:
        from .reference_wire import build_wire,wire_schema
        payload,registry,aliases=build_wire(manifest,payload)
        schema=wire_schema(registry,payload)
        schema['$defs']['WireFinding']['properties']['change_ids']['items']={'type':'string','enum':payload['allowed_change_ids'] or ['__no_change_available__']}
        fragments['impact_wire_schema']=schema
    user=json.dumps(payload,ensure_ascii=False,separators=(',',':'))
    return prompt,user,generation_request('impact_part',manifest.settings,prompt,user,fragments)
