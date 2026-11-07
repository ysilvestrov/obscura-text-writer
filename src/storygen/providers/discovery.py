import httpx

from .client import build_openai_client
from .models import ModelOption, ProviderSettings
from .venice import model_options


def discover_models(settings: ProviderSettings, http_client: httpx.Client | None = None, *, repo=None) -> list[ModelOption]:
    try:
        with build_openai_client(settings,http_client) as client:
            if settings.provider=='venice':
                return model_options(client,repo)
            from .catalog import model_option
            return [model_option(settings.provider,model.model_dump(),repo) for model in client.models.list()]
    except ValueError:
        raise
    except Exception:
        raise ValueError('Не вдалося отримати список моделей. Перевірте endpoint і серверний ключ.') from None
