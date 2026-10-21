import threading
import json
from typing import Iterator, Literal, Protocol

import httpx
from pydantic import Field

from ..domain import DomainModel
from ..generation.context import ContextBundle
from ..generation.models import StoryBlueprint, WritersBrief
from ..memory.models import MemorySnapshot, MemoryDelta
from ..memory.journal import MemoryOperations
from ..generation.copyediting import CopyEdits
from .client import build_openai_client
from .models import ProviderSettings
from .venice import validate_model, VeniceModelUnavailable


class GenerationEvent(DomainModel):
    type: Literal['delta','terminal','error','cancelled']
    text: str = ''
    finish_reason: str | None = None
    usage: dict = Field(default_factory=dict)
    message: str = ''
    refusal: bool = False


class GenerationGateway(Protocol):
    def stream(self,context: ContextBundle,cancel: threading.Event) -> Iterator[GenerationEvent]: ...


def strict_schema(model):
    schema=model.model_json_schema()
    def normalize(node):
        if isinstance(node,dict):
            node.pop('default',None)
            if 'properties' in node:
                node['required']=list(node['properties'])
                node['additionalProperties']=False
            for value in node.values():normalize(value)
        elif isinstance(node,list):
            for value in node:normalize(value)
    normalize(schema)
    return schema


class OpenAIGenerationGateway:
    def __init__(self,settings: ProviderSettings,http_client=None):
        self.settings=settings
        self.http_client=http_client

    def stream(self,context: ContextBundle,cancel: threading.Event) -> Iterator[GenerationEvent]:
        if cancel.is_set():
            yield GenerationEvent(type='cancelled')
            return
        finish=None
        usage={}
        has_text=False
        refusal=False
        try:
            with build_openai_client(self.settings,self.http_client) as client:
                options={}
                if context.settings.stop_sequences:
                    options['stop']=context.settings.stop_sequences
                if self.settings.include_usage:
                    options['stream_options']={'include_usage':True}
                structured=context.stage in {'prepare','brief','memory'} or (context.stage=='edit' and context.settings.edit_mode=='patches')
                if self.settings.provider=='venice':
                    validate_model(client,self.settings.model,structured and self.settings.response_mode=='json_schema')
                    options['extra_body']={'venice_parameters':{
                        'include_venice_system_prompt':self.settings.venice_include_system_prompt,
                        'disable_thinking':self.settings.venice_disable_thinking,
                        'enable_web_search':'off',
                        'enable_web_scraping':False,
                        'enable_x_search':False,
                    }}
                if self.settings.response_mode=='json_schema' and structured:
                    model=CopyEdits if context.stage=='edit' else MemoryOperations if context.stage=='memory' and context.settings.memory_mode=='evidence_delta' else {'prepare':StoryBlueprint,'brief':WritersBrief,'memory':MemorySnapshot}[context.stage]
                    schema=strict_schema(model)
                    if context.stage=='memory' and context.settings.memory_mode=='snapshot' and context.fragments.get('expected_source_prose_ids'):
                        allowed=json.loads(context.fragments['expected_source_prose_ids'])
                        sources=schema['properties']['source_prose_ids']
                        sources.update({'minItems':len(allowed),'maxItems':len(allowed),'items':{'type':'string','enum':allowed}})
                        schema['$defs']['MemoryEntry']['properties']['source_version_id']['enum']=allowed
                    options['response_format']={'type':'json_schema','json_schema':{'name':context.stage,'strict':True,'schema':schema}}
                if cancel.is_set():
                    yield GenerationEvent(type='cancelled',usage=usage)
                    return
                with client.chat.completions.create(model=self.settings.model,messages=[{'role':'system','content':context.system_text},{'role':'user','content':context.user_text}],max_tokens=context.settings.max_output_tokens,temperature=context.settings.temperature,stream=True,**options) as stream:
                    for chunk in stream:
                        if cancel.is_set():
                            yield GenerationEvent(type='cancelled',usage=usage)
                            return
                        if chunk.usage:
                            usage.update(chunk.usage.model_dump(exclude_none=True))
                        cost=getattr(chunk,'cost',None)
                        if cost is not None:
                            usage['cost']=cost
                        if getattr(chunk,'error',None):
                            raise RuntimeError('Provider stream error')
                        for choice in chunk.choices or []:
                            if choice.index!=0:
                                continue
                            delta=choice.delta
                            denied=getattr(delta,'refusal',None)
                            if denied:
                                refusal=True
                                yield GenerationEvent(type='delta',text=denied,refusal=True)
                            if delta.content:
                                has_text=True
                                yield GenerationEvent(type='delta',text=delta.content)
                            if choice.finish_reason:
                                finish=choice.finish_reason
                if cancel.is_set():
                    yield GenerationEvent(type='cancelled',usage=usage)
                elif finish=='stop' and has_text and not refusal:
                    yield GenerationEvent(type='terminal',finish_reason=finish,usage=usage)
                elif finish=='length' and not refusal:
                    yield GenerationEvent(type='error',finish_reason=finish,usage=usage,message=f'Модель вичерпала ліміт відповіді ({context.settings.max_output_tokens} токенів). Частковий текст збережено. Збільште резерв відповіді; для пам’яті можна вибрати режим нових фактів за фрагментами. Автоматичного повтору немає.')
                else:
                    yield GenerationEvent(type='error',finish_reason=finish,usage=usage,refusal=refusal,message='Відповідь відхилено моделлю' if refusal else 'Немає повної відповіді з finish_reason=stop')
        except VeniceModelUnavailable as exc:
            yield GenerationEvent(type='error',usage=usage,message=str(exc))
        except Exception:
            # SDK errors may contain request bodies, headers or server echoes. Never serialize them.
            yield GenerationEvent(type='cancelled' if cancel.is_set() else 'error',finish_reason=finish,usage=usage,message='Запит перервано або провайдер недоступний. Автоматичного повтору немає.')


def build_generation_gateway(settings: ProviderSettings,http_client: httpx.Client | None = None) -> GenerationGateway:
    return OpenAIGenerationGateway(settings,http_client)
