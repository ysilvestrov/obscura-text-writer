import httpx

from .client import build_openai_client
from .models import ModelOption, ProviderSettings
from .venice import model_options


def discover_models(settings: ProviderSettings, http_client: httpx.Client | None = None) -> list[ModelOption]:
    try:
        with build_openai_client(settings,http_client) as client:
            if settings.provider=='venice':
                return model_options(client)
            return [ModelOption(id=model.id,context_tokens=getattr(model,'context_length',None)) for model in client.models.list()]
    except ValueError:
        raise
    except Exception:
        raise ValueError('Не вдалося отримати список моделей. Перевірте endpoint і серверний ключ.') from None
