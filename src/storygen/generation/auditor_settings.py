"""Settings of the auditor role (MODEL-001): a story without its own row borrows them on the fly."""
from ..providers.models import RoleSettings

AUDITOR_TEMPERATURE = 0.2
STAGE_PROMPT_KEYS = ('audit_brief', 'audit_memory')


def resolve_auditor(roles: dict[str, RoleSettings]) -> RoleSettings | None:
    """The saved auditor, else the editor's provider with the planner's limits; None while the story has no editor.

    The editor's input limit is 80 000 characters, too small for an audit input, so the three limits come from the planner.
    """
    own = roles.get('auditor')
    if own is not None:
        return own
    editor = roles.get('editor')
    if editor is None:
        return None
    limits = {name: getattr(roles['planner'], name) for name in ('context_tokens', 'max_input_chars', 'max_output_tokens')} if 'planner' in roles else {}
    return RoleSettings(provider=editor.provider, temperature=AUDITOR_TEMPERATURE, **limits)


def is_derived(roles: dict[str, RoleSettings]) -> bool:
    """True when the auditor has no saved settings of its own."""
    return 'auditor' not in roles


def prompt_version_for(settings: RoleSettings, stage: str) -> str | None:
    """Custom prompt version of an audit stage: audit_prose is the main prompt, the other two live in stage_prompt_version_ids."""
    if stage == 'audit_prose':
        return settings.prompt_version_id
    if stage in STAGE_PROMPT_KEYS:
        return settings.stage_prompt_version_ids.get(stage)
    raise ValueError('Невідомий етап перевірки')
