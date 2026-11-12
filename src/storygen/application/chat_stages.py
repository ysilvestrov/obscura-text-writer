"""MCP-BRIDGE package 3: a chat client writes the brief, edit and memory stages with the pipeline's own instructions,
and its answer goes through the same `execute_stage` as a model answer. No provider is called and nothing is billed."""
from ..generation.pipeline import STAGE_ROLES
from ..providers.models import ProviderSettings, RoleSettings

CHAT_STAGES=('brief','edit','memory')
# A typical chat window: the standard role default (8192 tokens) would not hold the edit of a long scene.
CHAT_CONTEXT_TOKENS=131072
CHAT_MAX_OUTPUT_TOKENS=8192


def chat_role_settings(repo,story_id: str,stage: str) -> RoleSettings:
    """The role settings the pipeline would use for this scene stage, or chat defaults for a role nobody configured."""
    if stage not in {'brief','draft','edit','memory'}:
        raise ValueError(f'Невідомий етап сцени: {stage}')
    from ..authoring.blueprints import get_role_settings
    role=get_role_settings(repo,story_id).get(STAGE_ROLES[stage])
    if role is not None:
        return role
    return RoleSettings(provider=ProviderSettings(model='external-chat'),memory_mode='evidence_delta',
                        context_tokens=CHAT_CONTEXT_TOKENS,max_output_tokens=CHAT_MAX_OUTPUT_TOKENS)
