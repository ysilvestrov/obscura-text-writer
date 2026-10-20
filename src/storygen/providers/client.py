import os

import httpx
from openai import OpenAI

from .models import ProviderSettings


def build_openai_client(settings: ProviderSettings, http_client: httpx.Client | None = None) -> OpenAI:
    key='local-server' if settings.provider=='local' else os.environ.get(settings.key_env)
    if not key:
        raise ValueError('Ключ провайдера відсутній у серверному середовищі')
    return OpenAI(base_url=settings.base_url,api_key=key,timeout=settings.timeout,max_retries=0,http_client=http_client)
