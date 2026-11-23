"""MODEL-RETIREMENT-S02: carry an attempt's model-retirement warning into the run, on every execution path."""
from ..run_models import merge_warnings, loop_status  # noqa: F401 (loop_status: editor_loop imports it from here)

RETIREMENT_KEY='model_retirement_warnings'


def stage_retirement(attempt,gateway,model):
    """Record the provider's removal notice the gateway saw for the called model (OpenAIGenerationGateway.retirement)."""
    from ..providers.models import ModelRetirement
    from ..providers.retirement import retirement_warning
    notice=getattr(gateway,'retirement',None)
    if isinstance(notice,ModelRetirement):
        attempt.context[RETIREMENT_KEY]=[retirement_warning(model,notice)]


def retirement_warnings(attempt):
    return list(attempt.context.get(RETIREMENT_KEY,[]))
