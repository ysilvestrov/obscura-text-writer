"""Server-side counterpart of the model picker rules: what the catalog positively knows about a model blocks a save."""
from .catalog import ModelLimitsError, validate_limits
from .discovery import discover_models
from .models import ProviderSettings
from .retirement import retirement_warning

MISMATCH = 'Модель не підтримує JSON Schema. Виберіть іншу модель або режим „JSON за промптом“.'
# The save check is a catalog lookup, not generation: an offline catalog must not stall it for the provider timeout.
CATALOG_TIMEOUT = 10.0


def catalog_check(settings: ProviderSettings, limits=(), http_client=None) -> tuple[str | None, str | None]:
    """(error, warning): the error when the catalog says the model lacks JSON Schema or a (context, output) pair exceeds
    its caps; the warning when the provider retires the model (MODEL-RETIREMENT-S04, never blocks). Both None if unsure."""
    if settings.provider not in {'venice', 'openrouter'}:
        return None, None
    limits = [pair for pair in limits if pair is not None]
    if settings.response_mode != 'json_schema' and not limits:
        return None, None
    try:
        options = discover_models(settings.model_copy(update={'timeout': min(settings.timeout, CATALOG_TIMEOUT)}), http_client)
    except Exception:
        return None, None
    option = next((item for item in options if item.id == settings.model), None)
    if option is None:
        return None, None
    warning = retirement_warning(option.id, option.retirement) if option.retirement else None
    if settings.response_mode == 'json_schema' and option.supports_schema is False:
        return MISMATCH, warning
    for context_tokens, max_output_tokens in limits:
        try:
            validate_limits(option.context_tokens, option.max_output_tokens, context_tokens, max_output_tokens)
        except ModelLimitsError as exc:
            return str(exc), warning
    return None, warning


def catalog_problem(settings: ProviderSettings, limits=(), http_client=None) -> str | None:
    """Error text when the catalog says the model lacks JSON Schema or a (context, output) pair exceeds its caps; None if unsure."""
    return catalog_check(settings, limits, http_client)[0]


def schema_mismatch(settings: ProviderSettings, http_client=None) -> str | None:
    """Return the error text only when the catalog positively says the model lacks JSON Schema; None if unsure."""
    return catalog_problem(settings, (), http_client) if settings.response_mode == 'json_schema' else None


def role_check(role) -> tuple[str | None, list[str]]:
    """Check a role's own model, its writer variant and its classifier, each against its own limits; also collect the
    retirement warnings of those models."""
    warnings = []
    for part in (role, role.low_rating_variant, role.classification):
        if part is not None:
            provider = part.provider
            # The variant always answers in the main writer's response mode.
            if part is role.low_rating_variant:
                provider = provider.model_copy(update={'response_mode': role.provider.response_mode})
            message, warning = catalog_check(provider, [(part.context_tokens, part.max_output_tokens)])
            if warning and warning not in warnings:
                warnings.append(warning)
            if message:
                return message, warnings
    return None, warnings


def role_problem(role) -> str | None:
    """Check a role's own model, its writer variant and its classifier, each against its own limits."""
    return role_check(role)[0]
