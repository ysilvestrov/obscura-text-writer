import os

import httpx
from openai import OpenAI

from .models import ProviderSettings


def build_openai_client(settings: ProviderSettings, http_client: httpx.Client | None = None) -> OpenAI:
    key_env=getattr(settings,'key_env',None) or getattr(settings,'api_key_env',None)
    key='local-server' if settings.provider=='local' else os.environ.get(key_env)
    if not key:
        raise ValueError('Ключ провайдера відсутній у серверному середовищі')
    timeout=getattr(settings,'timeout',None) or getattr(settings,'timeout_seconds',None) or (3600 if settings.provider=='local' else 180)
    return OpenAI(base_url=settings.base_url,api_key=key,timeout=timeout,max_retries=0,http_client=http_client)
