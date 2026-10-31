"""Provider envelopes and response normalization. Live calls need explicit gates."""
from copy import deepcopy
import base64
from decimal import Decimal
import json
import os
import time


class ProviderHTTPError(ValueError):
    """Safe HTTP metadata only; body/headers/URL may carry credentials."""
    def __init__(self,status_code):
        self.status_code=status_code
        super().__init__(f'HTTP {status_code}; no automatic retry, response not logged')


def envelope(body: dict, provider: str, config: dict) -> dict:
    model=config['model'];request=deepcopy(body);request['model']=model
    if provider=='local':
        return dict(url='http://localhost:1235/v1/chat/completions',body=request,schema_deviations=[])
    if provider=='openai':
        request.pop('reasoning_effort',None)  # cloud default reasoning, recorded in eventual usage
        request['max_completion_tokens']=request.pop('max_tokens')
        if not config.get('supports_temperature',False):request.pop('temperature',None)
        return dict(url='https://api.openai.com/v1/chat/completions',body=request,schema_deviations=[])
    if provider=='google':
        if model not in {'gemini-3.5-flash-lite','gemini-4-argon'}:raise ValueError('Unapproved Google model')
        messages=request['messages']
        if len(messages)!=2 or messages[0]['role']!='system' or messages[1]['role']!='user':
            raise ValueError('Research Google adapter only supports single-turn system/user')
        payload=dict(systemInstruction=dict(parts=[dict(text=messages[0]['content'])]),
            contents=[dict(role='user',parts=[dict(text=messages[1]['content'])])],
            generationConfig=dict(maxOutputTokens=4096,responseMimeType='application/json',
                responseJsonSchema=request['response_format']['json_schema']['schema']))
        # Native, stateless generateContent; retain provider defaults for cloud thinking/temperature.
        return dict(url=f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                    body=payload,schema_deviations=[dict(keyword='string-length',effect='provider ignores; local validation retained')])
    if provider!='anthropic':raise ValueError('Unsupported provider')
    if config.get('schema_relaxation_approved') is not True:raise ValueError('Anthropic schema deviation requires approval')
    schema=deepcopy(request['response_format']['json_schema']['schema']);removed=[]
    def relax(node,path='$'):
        if isinstance(node,dict):
            for key in list(node):
                if key in {'minLength','maxLength','maxItems'} or key=='minItems' and node[key] not in {0,1}:
                    removed.append(dict(path=path,keyword=key,value=node.pop(key)))
                else:relax(node[key],path+'.'+key)
        elif isinstance(node,list):
            for i,value in enumerate(node):relax(value,path+f'[{i}]')
    relax(schema)
    system=request['messages'][0]['content']+'\nОбмеження результату (перевіряються також локально):\n'+json.dumps(removed,ensure_ascii=False,separators=(',',':'))
    payload=dict(model=model,max_tokens=4096,system=system,messages=request['messages'][1:],stream=False,
                 output_config=dict(format=dict(type='json_schema',schema=schema)))
    # Thinking defaults and temperature are model-dependent: do not silently force off.
    return dict(url='https://api.anthropic.com/v1/messages',body=payload,schema_deviations=removed)


def normalize(raw: dict, provider: str) -> dict:
    if not isinstance(raw,dict):raise ValueError('Provider envelope must be an object')
    usage=raw.get('usageMetadata',{}) if provider=='google' else raw.get('usage',{})
    if not isinstance(usage,dict):raise ValueError('Invalid usage object')
    reasoning=None
    if provider=='google':
        feedback=raw.get('promptFeedback') or {}
        if not isinstance(feedback,dict):raise ValueError('Invalid prompt feedback')
        candidates=raw.get('candidates') or []
        if not isinstance(candidates,list) or any(not isinstance(c,dict) for c in candidates):raise ValueError('Invalid candidates')
        blocked=feedback.get('blockReason')
        candidate=candidates[0] if len(candidates)==1 else {}
        if len(candidates)>1 or not candidate and not blocked:raise ValueError('Expected one candidate or prompt block')
        content=candidate.get('content') or {}
        if not isinstance(content,dict):raise ValueError('Invalid candidate content')
        parts=content.get('parts') or []
        if not isinstance(parts,list) or any(not isinstance(p,dict) or not isinstance(p.get('text',''),str) for p in parts):
            raise ValueError('Invalid candidate parts')
        stop=candidate.get('finishReason') or blocked
        refusal=stop in {'SAFETY','RECITATION','BLOCKLIST','PROHIBITED_CONTENT','SPII','IMAGE_SAFETY'}
        finish='refusal' if refusal else {'STOP':'stop','MAX_TOKENS':'length'}.get(stop,stop)
        text=''.join(p.get('text','') for p in parts if not p.get('thought'))
        reasoning=usage.get('thoughtsTokenCount')
        reasoning_chars=sum(len(p.get('text','')) for p in parts if p.get('thought'))
    elif provider=='anthropic':
        stop=raw.get('stop_reason');blocks=raw.get('content') or []
        if not isinstance(blocks,list) or any(not isinstance(b,dict) for b in blocks):raise ValueError('Invalid content blocks')
        text=''.join(b.get('text','') for b in blocks if b.get('type')=='text')
        finish={'end_turn':'stop','max_tokens':'length','refusal':'refusal'}.get(stop,stop)
        refusal=stop=='refusal'
        reasoning_chars=sum(len(b.get('thinking','')) for b in blocks if b.get('type')=='thinking')
    else:
        choices=raw['choices']
        if not isinstance(choices,list) or not choices or not isinstance(choices[0],dict):raise ValueError('Invalid choices')
        choice=choices[0];msg=choice['message']
        if not isinstance(msg,dict) or msg.get('content') is not None and not isinstance(msg['content'],str):raise ValueError('Invalid message')
        stop=choice.get('finish_reason');finish=stop
        text=msg.get('content') or '';refusal=bool(msg.get('refusal')) or stop=='content_filter'
        details=usage.get('completion_tokens_details') or {}
        if not isinstance(details,dict):raise ValueError('Invalid token details')
        reasoning=details.get('reasoning_tokens')
        reasoning_chars=len(msg.get('reasoning_content') or msg.get('reasoning') or '')
    return dict(text=text,finish_reason=finish,provider_finish_reason=stop,refusal=refusal,
                usage=usage,reasoning_tokens=reasoning,reasoning_chars=reasoning_chars,
                provider_model=raw.get('modelVersion') if provider=='google' else raw.get('model'))


def dispatch(client,request: dict,provider: str,config: dict,*,authorized=False,reserve=None,available=None) -> dict:
    """One HTTP attempt; caller owns durable reservation and explicit transport retry.

    No dotenv loading, implicit SDK retries, key logging or arbitrary endpoints.
    This low-level adapter is not exposed as a CLI until experiment gates exist.
    """
    if not authorized:raise ValueError('Dispatch not authorized')
    if provider!='local' and (reserve is None or available is None or Decimal(str(reserve))<=0 or Decimal(str(available))<Decimal(str(reserve))):
        raise ValueError('Paid dispatch requires budget reservation')
    wire=envelope(request['body'],provider,config);headers={}
    if provider!='local':
        key=os.environ.get(config.get('key_env',{'openai':'OPENAI_API_KEY','anthropic':'ANTHROPIC_API_KEY','google':'GOOGLE_API_KEY'}[provider]))
        if not key:raise ValueError('Missing API key environment variable')
        headers=({'x-api-key':key,'anthropic-version':'2023-06-01'} if provider=='anthropic' else
                 {'x-goog-api-key':key} if provider=='google' else {'Authorization':'Bearer '+key})
    began=time.monotonic()
    response=client.post(wire['url'],json=wire['body'],headers=headers,timeout=config.get('timeout',300))
    if response.status_code!=200:
        # HTTP errors are not proven pre-inference transport failures. Stop for review.
        raise ProviderHTTPError(response.status_code)
    evidence=dict(raw_body_base64=base64.b64encode(response.content).decode('ascii'))
    raw=None
    try:
        raw=response.json();normalized=normalize(raw,provider)
    except (ValueError,KeyError,TypeError,IndexError):
        usage=raw.get('usageMetadata' if provider=='google' else 'usage') if isinstance(raw,dict) else None
        return dict(status='invalid',error='Malformed provider envelope',seconds=time.monotonic()-began,
                    rejection_codes=['malformed_provider_envelope'],secondary_eligible=False,contract_defects=[],
                    raw_response=raw,usage=usage if isinstance(usage,dict) else None,
                    provider_model=raw.get('modelVersion' if provider=='google' else 'model') if isinstance(raw,dict) else None,
                    **evidence)
    from .scoring import validate_response
    return dict(validate_response(normalized,request),raw_response=raw,
                seconds=time.monotonic()-began,schema_deviations=wire['schema_deviations'],**evidence)
