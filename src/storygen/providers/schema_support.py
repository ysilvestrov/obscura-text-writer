"""Server-side counterpart of the model picker rule: a known non-schema model cannot be saved in JSON Schema mode."""
from .discovery import discover_models
from .models import ProviderSettings

MISMATCH = 'Модель не підтримує JSON Schema. Виберіть іншу модель або режим „JSON за промптом“.'


def schema_mismatch(settings: ProviderSettings, http_client=None) -> str | None:
    """Return the error text only when the catalog positively says the model lacks JSON Schema; None if unsure."""
    if settings.response_mode != 'json_schema' or settings.provider not in {'venice', 'openrouter'}:
        return None
    try:
        options = discover_models(settings, http_client)
    except Exception:
        return None
    option = next((item for item in options if item.id == settings.model), None)
    return MISMATCH if option is not None and option.supports_schema is False else None
