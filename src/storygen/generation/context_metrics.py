"""Metadata-only accounting of the exact request; never a tokenizer claim."""
from collections import defaultdict
from ..token_budget.core import canonical


def section_kind(text,stage):
    for prefix,kind in [
        ('МАЙБУТНІ ПОДІЇ','plans'),('ПЕРСОНАЖ','characters'),('КАРТК','characters'),
        ('ЗДІЙСНЕНІ ПОДІЇ','memory'),('ЧИННІ ТВЕРДЖЕННЯ','memory'),('ПОПЕРЕДНЯ ПЕРЕВІРЕНА','memory'),
        ('ЗАВЕРШЕННЯ ПОПЕРЕДНЬОЇ','previous_tail'),('ЗАВДАННЯ ПИСЬМЕННИКУ','brief'),
        ('ЧЕРНЕТКА','draft'),('ПОТОЧНА ПРОЗА','prose')]:
        if text.startswith(prefix):return kind
    return 'other'


def request_breakdown(body,sections,stage,prediction,settings):
    groups=defaultdict(lambda:{'characters':0,'request_bytes':0})
    def add(kind,text):
        groups[kind]['characters']+=len(text)
        groups[kind]['request_bytes']+=len(canonical(text).encode('utf-8'))-2
    add('system',body['messages'][0]['content'])
    for section in sections:add('draft' if stage=='edit' and len(sections)==1 else section_kind(section,stage),section)
    if 'response_format' in body:
        schema=canonical(body['response_format'])
        groups['response_schema']={'characters':len(schema),'request_bytes':len(schema.encode('utf-8'))}
    total=len(canonical(body).encode('utf-8'))
    # Wrappers, escaped separators and provider options stay visible as protocol.
    groups['protocol']={'characters':None,'request_bytes':total-sum(p['request_bytes'] for p in groups.values())}
    estimate=prediction['input_tokens'];parts=[]
    variable=max(0,estimate-256)
    for kind,item in groups.items():
        parts.append({'kind':kind,**item,'estimated_tokens':variable*item['request_bytes']//total if total else 0})
    parts[-1]['estimated_tokens']+=estimate-sum(p['estimated_tokens'] for p in parts)
    return {'parts':parts,'request_bytes':total,'estimated_input_tokens':estimate,
        'method':prediction['method'],'confidence':prediction.get('confidence','unknown'),
        'context_tokens':settings.context_tokens,'output_reserve':settings.max_output_tokens,
        'input_budget':settings.context_tokens-settings.max_output_tokens,
        'max_input_chars':settings.max_input_chars,
        'input_characters':sum(len(m['content']) for m in body['messages']),
        'allocation':'proportional_json_bytes_not_tokenizer'}
