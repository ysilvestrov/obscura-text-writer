"""MODEL-RETIREMENT-S02: carry an attempt's model-retirement warning into the run, on every execution path."""
from ..run_models import merge_warnings

RETIREMENT_KEY='model_retirement_warnings'
ACCEPTED='Підсумкові правки прийнято.'


def loop_status(warning,status):
    """The editor loop's status line (stop reason or acceptance) replaces the previous one; other warnings stay."""
    from .editor_loop import STOP_NAMES
    statuses=tuple(STOP_NAMES.values())+(ACCEPTED,)
    kept=[line for line in (warning or '').splitlines() if not line.startswith(statuses)]
    return merge_warnings('\n'.join(kept),[status])


def stage_retirement(attempt,gateway,model):
    """Record the provider's removal notice the gateway saw for the called model (OpenAIGenerationGateway.retirement)."""
    from ..providers.models import ModelRetirement
    from ..providers.retirement import retirement_warning
    notice=getattr(gateway,'retirement',None)
    if isinstance(notice,ModelRetirement):
        attempt.context[RETIREMENT_KEY]=[retirement_warning(model,notice)]


def retirement_warnings(attempt):
    return list(attempt.context.get(RETIREMENT_KEY,[]))


def carry(worker,run_id,attempt,stage,scene_id):
    """For runners that call execute_stage directly (impact, review): merge the warning and announce it."""
    warnings=retirement_warnings(attempt)
    if not warnings:return
    with worker.condition:
        current=worker.get_run(run_id)
        current.warning=merge_warnings(current.warning,warnings)
        worker._save(current)
    worker.event(run_id,'context_warning',{'warnings':warnings,'stage':stage,'scene_id':scene_id})
